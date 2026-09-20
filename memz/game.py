"""The game's state machine (spec §4, §5). This is the only place a
`Round.status` changes (spec §12.1). Every public function here is called
with the session row locked (`select_for_update`), so two requests arriving
at once cannot double-advance a round or double-create the next one (spec
Rule 5.4.3) — see `locked()`.

Phase flow per round (SPR-Z.10): captioning -> revealed -> done, with
`voting` surviving as a phase of its own **only in Judge mode**. In every
other game the reveal *is* the vote: each meme gets its own slot on
screen, everyone rates it while it's up (`rate_submission`), and when the
last slot ends the round is already decided. That replaced the old
separate grid where everyone picked one favourite at the end.

`sync()` does every *automatic* transition (a deadline passing, everyone
having submitted or voted) and is called at the top of every action and
every state read, so the state is always current before anything reads or
acts on it — nothing waits for a background job. `advance()` is the one
thing a host does on purpose: end a reveal early, or move from a round's
result to the next round (or the podium).
"""

import secrets
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from . import ai_players, cards, conf, dealing, scoring
from .memes import make_meme
from .models import CODE_ALPHABET, Meme, MemeImage, Player, Round, Session, Submission, Vote, new_token


class GameError(Exception):
    """A refused action, with a message safe to show the player."""


@contextmanager
def locked(session):
    with transaction.atomic():
        yield Session.objects.select_for_update().get(pk=session.pk)


def _bump(session):
    Session.objects.filter(pk=session.pk).update(version=session.version + 1)


def generate_code():
    for length in (4, 4, 4, 4, 4, 5):   # 5th+ char only after repeated collisions (spec §12.6)
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
        if not Session.objects.filter(code=code, status__in=Session.ACTIVE).exists():
            return code
    raise GameError("לא הצלחנו למצוא קוד פנוי, נסו שוב.")


# ------------------------------------------------------------- lobby & join


class RememberedCapReached(GameError):
    """Rule 2.4.2: refuse to silently delete anything — the caller (a
    logged-in host at the free-tier cap) gets the oldest remembered
    session back and a chance to release it before trying again."""

    def __init__(self, oldest_session):
        self.oldest_session = oldest_session
        super().__init__(
            f"הגעתם למכסת המשחקים השמורים שלכם ({oldest_session and 'ניתן לשחרר אחד ישן' or ''})."
        )


def create_session(
    *, host_user, round_count, round_seconds, vote_seconds,
    game_mode=Session.NORMAL, caption_mode=Session.TYPED, scoring_mode=Session.VOTE, deck=None,
    image_source=Session.PUBLIC_RANDOM, packs=None, release_session_code=None, ai_player_count=0,
    host_nickname="",
):
    from .tiers import tier_for

    is_logged_in = bool(host_user and host_user.is_authenticated)
    tier = tier_for(host_user)
    max_players = conf.cap("MAX_PLAYERS", tier)
    # spec §4.11: up to AI_PLAYERS_MAX, and always room for the host's own
    # seat — a bot never displaces the one person who has to be able to
    # start the game. Signed-in hosts only (Rule 4.11.1, 2026-09-16): a
    # guest asking for bots is forced back to zero server-side, the same
    # silent downgrade `image_source` already gets for a guest host —
    # never trust the client's own claim about who is asking.
    ai_player_count = 0 if not is_logged_in else max(
        0, min(int(ai_player_count or 0), conf.get("AI_PLAYERS_MAX"), max_players - 1)
    )
    if caption_mode == Session.CARDS:
        if deck is None:
            raise GameError("צריך לבחור חפיסת קלפים.")
        if not cards.deck_size_ok(deck, max_players=max_players, round_count=round_count):
            raise GameError("החפיסה הזאת קטנה מדי למשחק הזה.")

    if not is_logged_in:
        # SPR-Z.11: a guest host still can't *pick* packs or an own-only
        # pool (nothing they own to draw from), but `mix` is now the right
        # floor rather than `public_random`: mix is the public bank plus
        # whatever the *seated signed-in players* have uploaded, and a
        # signed-in player's photos should play wherever they play, not
        # only in rooms a signed-in friend happened to open.
        image_source = Session.MIX
        packs = None
    elif image_source == Session.PACKS and not packs:
        raise GameError("צריך לבחור לפחות חבילה אחת.")

    if is_logged_in:
        remembered_qs = Session.objects.filter(host_user=host_user, remembered=True, expires_at__isnull=True)
        limit = conf.cap("REMEMBERED_SESSIONS", tier)
        if limit is not None and remembered_qs.count() >= limit:
            if release_session_code:
                released = remembered_qs.filter(code=release_session_code).first()
                if released is None:
                    raise GameError("לא מצאנו את המשחק הזה כדי לשחרר אותו.")
                release_session(released)
            else:
                oldest = remembered_qs.order_by("created_at").first()
                raise RememberedCapReached(oldest)

    session = Session.objects.create(
        code=generate_code(),
        host_user=host_user if is_logged_in else None,
        game_mode=game_mode, caption_mode=caption_mode, scoring_mode=scoring_mode, deck=deck,
        image_source=image_source,
        round_count=round_count, round_seconds=round_seconds, vote_seconds=vote_seconds,
        max_players=max_players,
        remembered=is_logged_in,
    )
    if packs:
        session.packs.set(packs)
    # SPR-W.1 (F-W.1.4): the host picks a name like everyone else does when
    # joining. Until now a guest host was "מארח/ת" everywhere, including at
    # the top of the podium, which was nobody's win.
    wanted = (host_nickname or "").strip()[:conf.get("NICKNAME_MAX_CHARS")]
    host_player = Player.objects.create(
        session=session, user=host_user if is_logged_in else None,
        nickname=wanted or _default_nickname(host_user), is_host=True, seat_order=0,
    )
    ai_players.add_ai_players(session, ai_player_count)
    return session, host_player


def release_session(session):
    """Rule 2.4.2: free a remembered slot without deleting anything — the
    same fate a guest session eventually gets, just chosen rather than
    automatic."""
    if session.expires_at is None:
        session.expires_at = timezone.now() + timezone.timedelta(hours=conf.get("GUEST_SESSION_TTL_HOURS"))
        session.save(update_fields=["expires_at"])


def attach_account(session, player, user):
    """Rule 3.3.5: signing in mid-session links the account to the seat
    already in play. Idempotent for the same account; refused for a
    different one, so a stray logged-in browser can't take over someone
    else's seat."""
    if player.user_id is not None and player.user_id != user.id:
        raise GameError("המושב הזה כבר שייך לחשבון אחר.")
    if player.user_id == user.id:
        return
    Player.objects.filter(pk=player.pk).update(user=user)
    player.user_id = user.id


def _default_nickname(user):
    if user and user.is_authenticated:
        from .tiers import default_display_name

        return default_display_name(user)[:conf.get("NICKNAME_MAX_CHARS")]
    return "מארח/ת"


def _unique_nickname(session, wanted):
    wanted = (wanted or "").strip()[: conf.get("NICKNAME_MAX_CHARS")] or "אורח"
    if not Player.objects.filter(session=session, nickname=wanted).exists():
        return wanted
    i = 2
    while Player.objects.filter(session=session, nickname=f"{wanted} {i}").exists():
        i += 1
    return f"{wanted} {i}"


def join_session(session, nickname, *, user=None):
    with locked(session):
        session.refresh_from_db()
        if session.status == Session.PLAYING:
            raise GameError("המשחק כבר התחיל, אי אפשר להצטרף באמצע.")
        if session.status != Session.LOBBY:
            raise GameError("החדר הזה כבר לא פעיל.")
        active = session.players.filter(is_active=True).count()
        if active >= session.max_players:
            raise GameError(f"החדר מלא ({active} מתוך {session.max_players}).")
        seat = (session.players.aggregate(models_max=_max_seat())["models_max"] or -1) + 1
        player = Player.objects.create(
            session=session, user=user if (user and user.is_authenticated) else None,
            nickname=_unique_nickname(session, nickname), seat_order=seat,
        )
        _bump(session)
        return player


def _max_seat():
    from django.db.models import Max

    return Max("seat_order")


def get_player(session, token):
    if not token:
        return None
    return Player.objects.filter(session=session, guest_token=token).first()


def touch(player):
    Player.objects.filter(pk=player.pk).update(last_seen_at=timezone.now(), is_active=True)
    player.last_seen_at = timezone.now()
    player.is_active = True


def leave_player(session, player):
    with locked(session):
        Player.objects.filter(pk=player.pk, session=session).update(is_active=False)
        _bump(session)


def remove_player(session, host_player, target_id):
    with locked(session):
        if not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה להסיר שחקנים.")
        target = Player.objects.filter(session=session, pk=target_id).first()
        if target is None:
            raise GameError("לא נמצא שחקן כזה.")
        if target.pk == host_player.pk:
            raise GameError("אי אפשר להסיר את עצמך.")
        Player.objects.filter(pk=target.pk).update(is_active=False, guest_token=new_token())
        _bump(session)


# --------------------------------------------------------------- the rounds


def _active_players(session):
    return list(session.players.filter(is_active=True).order_by("seat_order"))


def _minimum_players(session):
    """Rule 5.4.1: 3 for vote/judge, 2 for Relaxed — keyed by game mode
    for Relaxed since it has no real scoring_mode of its own."""
    table = conf.get("MIN_PLAYERS")
    if session.game_mode == Session.RELAXED:
        return table["relaxed"]
    return table.get(session.scoring_mode, table["vote"])


def start_session(session, host_player):
    with locked(session):
        session.refresh_from_db()
        if not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה להתחיל.")
        if session.status != Session.LOBBY:
            raise GameError("המשחק כבר התחיל.")
        players = _active_players(session)
        minimum = _minimum_players(session)
        if len(players) < minimum:
            raise GameError(f"צריך לפחות {minimum} שחקנים כדי להתחיל.")

        # SPR-W.2 (Rule 5.5.1): photo-booth mode opens the booth instead of
        # round one. Thirty seconds in which the room photographs itself,
        # and only then does the game begin -- with those photos as the
        # whole pool. Everything after the booth is an ordinary game.
        if session.game_mode == Session.PHOTO_BOOTH:
            session.status = Session.BOOTH
            session.started_at = timezone.now()
            session.booth_deadline = timezone.now() + timezone.timedelta(seconds=conf.get("BOOTH_SECONDS"))
            session.save(update_fields=["status", "started_at", "booth_deadline"])
            _bump(session)
            return

        session.status = Session.PLAYING
        session.started_at = timezone.now()
        session.save(update_fields=["status", "started_at"])
        _create_round(session, 1, players)
        _bump(session)


def add_booth_photo(session, player, processed_file, *, verdict, note, original_name="booth.jpg"):
    """Rule 5.5.2: one photo into this session's booth, and nowhere else.

    The caller has already processed and moderated the bytes (the API view
    does, exactly as every other upload path does). This is the part that
    must not be got wrong: the image is written with `session` set and
    `owner` null, which is what keeps it out of every bank query in the
    app -- `visible_images` looks for an owner or the public bank, and
    `pool_for` only reaches it for this one session."""
    with locked(session):
        session.refresh_from_db()
        if session.game_mode != Session.PHOTO_BOOTH:
            raise GameError("המשחק הזה לא במצב צילום.")
        if session.status != Session.BOOTH:
            raise GameError("תא הצילום סגור.")
        per_player = conf.get("BOOTH_PHOTOS_PER_PLAYER")
        if dealing.booth_photo_count(session, player) >= per_player:
            raise GameError(f"אפשר עד {per_player} תמונות לכל אחד.")

        image = MemeImage(
            owner=None, session=session, booth_taken_by=player,
            visibility=MemeImage.PRIVATE,
            moderation_status=verdict, moderation_note=note, seed_key="", title="",
        )
        image.file.save(original_name, processed_file, save=True)
        _bump(session)
    return image


def _end_booth(session, *, extend_if_short):
    """The booth -> the game. **The session lock must already be held.**

    Returns True when the game actually started. On too few photos a game
    with nothing to deal is not a game, so it doesn't start -- but what
    happens instead depends on who asked, which is what `extend_if_short`
    decides (Rule 5.5.4). The timer firing on its own is a room that ran
    out of time, and it gets more: another BOOTH_SECONDS, and one more
    mark against the booth, because a booth that has failed to fill itself
    is the one thing that unlocks the way out (Rule 5.5.6). A host
    pressing the button early is not that: they are simply told to keep
    shooting, and the clock they still have is left exactly as it was."""
    minimum = conf.get("BOOTH_MIN_PHOTOS")
    if dealing.pool_for(session).count() < minimum:
        if extend_if_short:
            session.booth_deadline = timezone.now() + timezone.timedelta(seconds=conf.get("BOOTH_SECONDS"))
            session.booth_extensions += 1
            session.save(update_fields=["booth_deadline", "booth_extensions"])
            _bump(session)
        return False

    session.status = Session.PLAYING
    session.booth_deadline = None
    session.save(update_fields=["status", "booth_deadline"])
    _create_round(session, 1, _active_players(session))
    _bump(session)
    return True


def close_booth(session, host_player=None):
    """The host ending the booth early: the game begins now, with the
    evening's own photos as the pool."""
    with locked(session):
        session.refresh_from_db()
        if session.status != Session.BOOTH:
            raise GameError("תא הצילום כבר נסגר.")
        if host_player is not None and not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה לסגור את תא הצילום.")
        if not _end_booth(session, extend_if_short=False):
            raise GameError(f"צריך לפחות {conf.get('BOOTH_MIN_PHOTOS')} תמונות. צלמו עוד קצת!")


def booth_was_extended(session):
    """Has this booth already run its clock out without enough photos?

    Just a field read (`Session.booth_extensions`), and deliberately so --
    an earlier version derived it by comparing `booth_deadline` against
    `started_at + BOOTH_SECONDS`, which is really a measurement of
    wall-clock time having passed and is therefore only true in a room."""
    return session.status == Session.BOOTH and session.booth_extensions > 0


def abandon_booth(session, host_player=None):
    """The way out of a booth that cannot fill itself (Rule 5.5.6).

    A room on laptops, a table that said no to being photographed, a phone
    whose camera permission is refused: without this the booth extends its
    own deadline forever and the host stares at a disabled button. So the
    host may drop the mode and play an ordinary game with the ordinary
    pool. The photos already taken are deleted rather than carried over,
    because they were taken under "these stay in this game and are deleted
    at the end of it" and this is the end of that game as promised -- the
    mode it turns into is a different one, and a photo of somebody's face
    is not a thing to quietly re-purpose."""
    with locked(session):
        session.refresh_from_db()
        if session.status != Session.BOOTH:
            raise GameError("תא הצילום כבר נסגר.")
        if host_player is not None and not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה לבטל את תא הצילום.")

        MemeImage.objects.filter(session=session).delete()
        session.game_mode = Session.NORMAL
        session.image_source = Session.MIX
        session.status = Session.PLAYING
        session.booth_deadline = None
        session.save(update_fields=["game_mode", "image_source", "status", "booth_deadline"])
        _create_round(session, 1, _active_players(session))
        _bump(session)


def _judge_for(session, number, players):
    """Rotation by seat order, starting with the player after the host
    (spec §5.3 judge mode), recomputed from whoever is active right now —
    a player who leaves mid-game simply drops out of the rotation."""
    if session.scoring_mode != Session.JUDGE or not players:
        return None
    ordered = sorted(players, key=lambda p: p.seat_order)
    host = next((p for p in ordered if p.is_host), ordered[0])
    start = ordered.index(host)
    rotation = ordered[start + 1:] + ordered[:start + 1]
    return rotation[(number - 1) % len(rotation)]


def _create_round(session, number, players):
    topic = dealing.deal_topic(session) if session.game_mode == Session.TOPICS else None
    judge = _judge_for(session, number, players)
    round_obj = Round.objects.create(
        session=session, number=number, status=Round.CAPTIONING, started_at=timezone.now(),
        topic=topic, judge=judge,
        caption_deadline=timezone.now() + timezone.timedelta(seconds=session.round_seconds),
    )
    if session.game_mode == Session.SAME_MEME:
        dealt = dealing.deal_same_image(session, players)
    else:
        dealt = dealing.deal_round(session, players)
    Submission.objects.bulk_create([
        Submission(round=round_obj, player=player, image=image) for player, image in dealt.items()
    ])
    if session.caption_mode == Session.CARDS and session.deck_id:
        for player in players:
            cards.top_up_hand(player, session.deck, number)
    return round_obj


def current_round(session):
    return session.rounds.order_by("-number").first()


def submit_caption(session, player, round_number, caption_text=None, hand_card_id=None):
    with locked(session):
        round_obj = session.rounds.filter(number=round_number).first()
        if round_obj is None or round_obj.status != Round.CAPTIONING:
            raise GameError("אי אפשר לשלוח כיתוב עכשיו.")
        submission = Submission.objects.filter(round=round_obj, player=player).first()
        if submission is None:
            raise GameError("אין לך תמונה בסבב הזה.")
        if submission.meme_id is not None:
            raise GameError("כבר שלחת כיתוב לסבב הזה.")

        if session.caption_mode == Session.CARDS:
            if not hand_card_id:
                raise GameError("צריך לבחור קלף.")
            card = cards.play_card(player, round_number, hand_card_id)
            if card is None:
                raise GameError("הקלף הזה כבר לא ביד שלך.")
            meme = make_meme(image=submission.image, caption_text=card.text, source=Meme.GAME,
                             user=player.user, caption_card=card)
        else:
            caption_text = (caption_text or "").strip()
            if not caption_text:
                raise GameError("אי אפשר בלי כיתוב.")
            if len(caption_text) > conf.get("CAPTION_MAX_CHARS"):
                raise GameError(f"עד {conf.get('CAPTION_MAX_CHARS')} תווים.")
            meme = make_meme(image=submission.image, caption_text=caption_text, source=Meme.GAME, user=player.user)

        submission.meme = meme
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["meme", "submitted_at"])
        _bump(session)
    sync(session)


def swap_hand_card(session, player, hand_card_id):
    """Rule 5.2.2: one mercy swap per game, cards mode only."""
    with locked(session):
        if session.caption_mode != Session.CARDS:
            raise GameError("אין קלפים במשחק הזה.")
        if not cards.swap_card(player, hand_card_id):
            raise GameError("אי אפשר להחליף את הקלף הזה עכשיו.")
        _bump(session)


def swap_image(session, player, round_number):
    """Rule 4.4.5 (SPR-Z.10): throw back the dealt image for another one,
    up to `IMAGE_SWAPS_PER_ROUND` times per round, while still writing.

    Refused in Same Meme mode: the whole point of that mode is that
    everyone is captioning the *same* picture (spec §5.1), so one player
    swapping out of it would break the round for everybody."""
    limit = conf.get("IMAGE_SWAPS_PER_ROUND")
    with locked(session):
        if session.game_mode == Session.SAME_MEME:
            raise GameError("במצב אותו מם כולם מקבלים את אותה תמונה.")
        round_obj = session.rounds.filter(number=round_number).first()
        if round_obj is None or round_obj.status != Round.CAPTIONING:
            raise GameError("אי אפשר להחליף תמונה עכשיו.")
        submission = Submission.objects.filter(round=round_obj, player=player).first()
        if submission is None:
            raise GameError("אין לך תמונה בסבב הזה.")
        if submission.meme_id is not None:
            raise GameError("כבר שלחת כיתוב לסבב הזה.")
        if submission.image_swaps_used >= limit:
            raise GameError(f"אפשר להחליף עד {limit} פעמים בסבב.")

        image = dealing.deal_replacement(session, submission)
        if image is None:
            raise GameError("אין תמונה אחרת להחליף אליה.")

        if submission.image_id is not None:
            submission.swapped_away_image_ids = list(submission.swapped_away_image_ids) + [submission.image_id]
        submission.image = image
        submission.image_swaps_used += 1
        submission.save(update_fields=["image", "image_swaps_used", "swapped_away_image_ids"])
        _bump(session)
    return image


def reveal_index(round_obj):
    """Which meme the reveal is showing *right now*, or None if the phase
    isn't running. The same arithmetic every client does (spec §4.5), kept
    here so the server can check a rating against it rather than trust a
    submission id a phone sends (Rule 4.5.4) — without this, one client
    could rate every meme in the round the moment the reveal opened."""
    if round_obj.status != Round.REVEALED or not round_obj.reveal_deadline:
        return None
    count = round_obj.submissions.filter(meme__isnull=False).count()
    if count == 0:
        return None
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    started = round_obj.reveal_deadline - timezone.timedelta(seconds=per_meme * count)
    elapsed = (timezone.now() - started).total_seconds()
    return max(0, min(count - 1, int(elapsed // per_meme)))


def reveal_order(round_obj):
    """The order the reveal walks the round's memes in. `id` order, which
    is the order submissions were created (one per player at round start),
    so it is stable across every client and every poll."""
    return list(round_obj.submissions.filter(meme__isnull=False).order_by("id"))


def rate_submission(session, voter, round_number, submission_id, value):
    """Rule 4.6.1 (SPR-Z.10): one verdict per meme per player, cast while
    that meme is the one on screen. Final on tap, like the old single vote
    was -- no changing your mind once it's in."""
    valid_values = {v for v, _label in Vote.VALUES}
    with locked(session):
        round_obj = session.rounds.filter(number=round_number).first()
        if round_obj is None or round_obj.status != Round.REVEALED:
            raise GameError("אי אפשר לדרג עכשיו.")
        if session.game_mode == Session.RELAXED:
            raise GameError("במצב רגוע לא מדרגים.")
        if session.scoring_mode == Session.JUDGE:
            raise GameError("בסבב הזה השופט/ת בוחר/ת בסוף.")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise GameError("דירוג לא תקין.")
        if value not in valid_values:
            raise GameError("דירוג לא תקין.")

        submission = round_obj.submissions.filter(pk=submission_id, meme__isnull=False).first()
        if submission is None:
            raise GameError("המם הזה לא קיים בסבב.")
        if submission.player_id == voter.pk:
            raise GameError("תעשה פרצוף תמים, אי אפשר לדרג את עצמך.")
        if Vote.objects.filter(round=round_obj, voter=voter, submission=submission).exists():
            raise GameError("כבר דירגת את המם הזה.")

        order = reveal_order(round_obj)
        index = reveal_index(round_obj)
        if index is None or order[index].pk != submission.pk:
            raise GameError("המם הזה כבר לא על המסך.")

        Vote.objects.create(round=round_obj, voter=voter, submission=submission, value=value)
        _bump(session)
    sync(session)


def cast_vote(session, voter, round_number, submission_id):
    """Judge mode only, from SPR-Z.10 on: the judge's single pick, in the
    separate voting phase that now exists only for that mode. Every other
    game rates during the reveal instead (`rate_submission`)."""
    with locked(session):
        round_obj = session.rounds.filter(number=round_number).first()
        if round_obj is None or round_obj.status != Round.VOTING:
            raise GameError("אי אפשר להצביע עכשיו.")
        if session.scoring_mode == Session.JUDGE and round_obj.judge_id != voter.pk:
            raise GameError("רק השופט/ת מחליט/ה בסבב הזה.")
        submission = round_obj.submissions.filter(pk=submission_id, meme__isnull=False).first()
        if submission is None:
            raise GameError("המם הזה לא קיים בסבב.")
        if submission.player_id == voter.pk:
            raise GameError("אי אפשר להצביע לעצמך.")
        if Vote.objects.filter(round=round_obj, voter=voter).exists():
            raise GameError("כבר הצבעת בסבב הזה.")
        Vote.objects.create(round=round_obj, voter=voter, submission=submission)
        _bump(session)
    sync(session)


def advance(session, host_player):
    """The host's own button: skip the rest of a reveal, or move on from a
    round's result to the next round (or the podium)."""
    with locked(session):
        if not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה להמשיך.")
        round_obj = current_round(session)
        if round_obj is None:
            raise GameError("אין סבב פעיל.")
        if round_obj.status == Round.REVEALED:
            # SPR-Z.10: ending the reveal early also ends everyone's chance
            # to rate whatever hadn't come up yet. That is the host's call
            # to make -- the same call they always had here -- but it is a
            # bigger one now than when the reveal was only a slideshow.
            _end_reveal(round_obj)
        elif round_obj.status == Round.DONE:
            _next_round_or_finish(session, round_obj)
        else:
            raise GameError("אי אפשר להמשיך בשלב הזה.")
        _bump(session)
    sync(session)


# ------------------------------------------------------- automatic advance


def sync(session):
    """Everything that happens on a deadline or a completed action, not on
    a host's tap. Idempotent, safe to call on every read."""
    with locked(session):
        session.refresh_from_db()
        _mark_inactive(session)
        _maybe_handoff_host(session)
        # SPR-W.2: the photo booth closes on its own when its thirty
        # seconds are up, the same way every other phase ends on its
        # deadline. The lock is already held here, so this calls the
        # transition body directly rather than `close_booth`, which takes
        # the lock itself.
        if session.status == Session.BOOTH:
            if session.booth_deadline and timezone.now() >= session.booth_deadline:
                _end_booth(session, extend_if_short=True)
            return
        if session.status != Session.PLAYING:
            return
        round_obj = current_round(session)
        if round_obj is None:
            return
        now = timezone.now()
        changed = True
        while changed:
            changed = False
            round_obj.refresh_from_db()
            if round_obj.status == Round.CAPTIONING:
                if ai_players.resolve_captioning(session, round_obj):
                    changed = True
                players = _active_players(session)
                submitted = set(round_obj.submissions.filter(meme__isnull=False).values_list("player_id", flat=True))
                everyone_in = players and all(p.id in submitted for p in players)
                if everyone_in or (round_obj.caption_deadline and now >= round_obj.caption_deadline):
                    _start_reveal(round_obj)
                    changed = True
            elif round_obj.status == Round.REVEALED:
                # SPR-Z.10: everyone rates each meme while it is on screen,
                # so by the time the last slot ends the round is already
                # decided -- `_end_reveal` finishes it outright, except in
                # Judge mode, where the separate voting phase still follows.
                if ai_players.resolve_rating(session, round_obj):
                    changed = True
                if round_obj.reveal_deadline and now >= round_obj.reveal_deadline:
                    _end_reveal(round_obj)
                    changed = True
            elif round_obj.status == Round.VOTING:
                if ai_players.resolve_voting(session, round_obj):
                    changed = True
                if session.scoring_mode == Session.JUDGE:
                    decided = round_obj.judge_id and Vote.objects.filter(
                        round=round_obj, voter_id=round_obj.judge_id
                    ).exists()
                else:
                    eligible = _active_players(session)
                    voted = set(Vote.objects.filter(round=round_obj).values_list("voter_id", flat=True))
                    decided = bool(eligible) and all(p.id in voted for p in eligible)
                if decided or (round_obj.vote_deadline and now >= round_obj.vote_deadline):
                    _finish_round(round_obj)
                    changed = True
            elif round_obj.status == Round.DONE:
                # SPR-W.5 (Rule 4.7.3). Deliberately last in the chain and
                # deliberately in `sync`: Rule 5.4.3 says a phase change
                # happens on the server, on the first request after its
                # deadline, so two phones reporting it at once cannot
                # double-advance. A client counting down and then POSTing
                # /advance/ would have been three clients racing.
                if round_obj.result_deadline and now >= round_obj.result_deadline:
                    _advance_from_result(session, round_obj)
                    changed = True


def _start_reveal(round_obj):
    memes_count = round_obj.submissions.filter(meme__isnull=False).count()
    round_obj.status = Round.REVEALED
    round_obj.reveal_deadline = timezone.now() + timezone.timedelta(
        seconds=conf.get("REVEAL_SECONDS_PER_MEME") * max(1, memes_count)
    )
    round_obj.save(update_fields=["status", "reveal_deadline"])


def _end_reveal(round_obj):
    """What happens when the last meme's slot on screen is over (SPR-Z.10).

    In every mode but Judge the ratings are already in — they were cast
    meme by meme as the reveal ran — so the round simply finishes and
    scores. Judge mode is the one flow that still needs a phase of its
    own afterwards: the judge picks one winner from the whole round, which
    can only happen once they have seen all of them."""
    session = round_obj.session
    memes_count = round_obj.submissions.filter(meme__isnull=False).count()

    if session.game_mode == Session.RELAXED:
        # Rule 4.5.3 / §5.1: no rating, no points — the reveal was the
        # whole point, the round just ends.
        _finish_round(round_obj, award=False)
        return

    if session.scoring_mode == Session.JUDGE:
        if memes_count == 0:
            _finish_round(round_obj, award=False)
            return
        round_obj.status = Round.VOTING
        # Rule 4.6.2: the judge's timer is twice the ordinary vote timer.
        round_obj.vote_deadline = timezone.now() + timezone.timedelta(seconds=session.vote_seconds * 2)
        round_obj.save(update_fields=["status", "vote_deadline"])
        return

    if memes_count < 2:
        # Rule 4.6.4: fewer than two memes, nothing to compare — the lone
        # meme (or nobody, if zero) takes the round outright. Any rating
        # that did land on it during the reveal is deliberately ignored;
        # a round of one is not a contest.
        _finish_round(round_obj, skip_vote=True, award=memes_count == 1)
        return

    _finish_round(round_obj)


def _finish_round(round_obj, *, skip_vote=False, award=True):
    round_obj.status = Round.DONE
    # SPR-W.5 (Rule 4.7.3): the result screen moves on by itself. Spec'd
    # since SPR-Z.3 and never built, which left the one place memz can
    # stall with nothing on screen explaining why: the host puts their
    # phone down at the result and the room waits indefinitely. The host's
    # button still works and still wins -- this is the floor under it, not
    # a replacement for it.
    round_obj.result_deadline = timezone.now() + timezone.timedelta(
        seconds=conf.get("RESULT_AUTO_ADVANCE_SECONDS")
    )
    round_obj.save(update_fields=["status", "result_deadline"])
    if not award:
        return
    if skip_vote:
        lone = round_obj.submissions.filter(meme__isnull=False).first()
        if lone is not None:
            Player.objects.filter(pk=lone.player_id).update(score=lone.player.score + 1)
        return
    points = scoring.round_scores(round_obj)
    for submission in round_obj.submissions.filter(meme__isnull=False):
        delta = points.get(submission.id, 0)
        if delta:
            Player.objects.filter(pk=submission.player_id).update(score=submission.player.score + delta)


def _advance_from_result(session, finished_round):
    """SPR-W.5: the result screen's own deadline firing. The deadline is
    cleared first so a round that somehow gets looked at again cannot
    advance the session twice -- `sync` loops until nothing changes, and a
    condition that stays true is how that loop stops terminating."""
    Round.objects.filter(pk=finished_round.pk).update(result_deadline=None)
    finished_round.result_deadline = None
    _next_round_or_finish(session, finished_round)
    _bump(session)


def _next_round_or_finish(session, finished_round):
    players = _active_players(session)
    minimum = _minimum_players(session)
    if finished_round.number >= session.round_count or len(players) < minimum:
        finish_session(session)
    else:
        _create_round(session, finished_round.number + 1, players)


def finish_session(session):
    session.status = Session.FINISHED
    session.ended_at = timezone.now()
    if not session.remembered:
        session.expires_at = session.ended_at + timezone.timedelta(hours=conf.get("GUEST_SESSION_TTL_HOURS"))
    session.save(update_fields=["status", "ended_at", "expires_at"])


# ----------------------------------------------------------- presence & host


def _mark_inactive(session):
    # AI players have no "last seen" — nothing ever polls on their behalf,
    # so a real staleness check would mark every bot inactive within one
    # threshold window (spec §4.11).
    cutoff = timezone.now() - timezone.timedelta(seconds=conf.get("INACTIVE_AFTER_SECONDS"))
    session.players.filter(is_active=True, is_ai=False, last_seen_at__lt=cutoff).update(is_active=False)


def _maybe_handoff_host(session):
    if session.status != Session.PLAYING:
        return
    host = session.players.filter(is_host=True).first()
    if host is None or host.is_active:
        return
    # Never to a bot (spec §4.11): nobody is behind it to tap "start" or
    # "advance" for the group.
    successor = session.players.filter(is_active=True, is_ai=False).exclude(pk=host.pk).order_by("seat_order").first()
    if successor is None:
        return
    Player.objects.filter(pk=host.pk).update(is_host=False)
    Player.objects.filter(pk=successor.pk).update(is_host=True)


# --------------------------------------------------------------- play again


def play_again(session, host_player):
    with locked(session):
        session.refresh_from_db()
        if not host_player.is_host:
            raise GameError("רק המארח/ת יכול/ה להתחיל עוד סבב.")
        if session.status != Session.FINISHED:
            raise GameError("המשחק עוד לא נגמר.")
        if session.next_session_id:
            return session.next_session
        new_session = Session.objects.create(
            code=generate_code(), host_user=session.host_user, game_mode=session.game_mode,
            caption_mode=session.caption_mode, scoring_mode=session.scoring_mode,
            image_source=session.image_source, round_count=session.round_count,
            round_seconds=session.round_seconds, vote_seconds=session.vote_seconds,
            max_players=session.max_players, remembered=session.remembered,
        )
        for old_player in session.players.filter(is_active=True).order_by("seat_order"):
            Player.objects.create(
                session=new_session, user=old_player.user, nickname=old_player.nickname,
                is_host=old_player.is_host, seat_order=old_player.seat_order, carried_from=old_player,
            )
        session.next_session = new_session
        session.save(update_fields=["next_session"])
        return new_session
