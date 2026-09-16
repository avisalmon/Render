"""The game's state machine (spec §4, §5). This is the only place a
`Round.status` changes (spec §12.1). Every public function here is called
with the session row locked (`select_for_update`), so two requests arriving
at once cannot double-advance a round or double-create the next one (spec
Rule 5.4.3) — see `locked()`.

Phase flow per round: captioning -> revealed -> voting -> done. `sync()`
does every *automatic* transition (a deadline passing, everyone having
submitted or voted) and is called at the top of every action and every
state read, so the state is always current before anything reads or acts
on it — nothing waits for a background job. `advance()` is the one thing a
host does on purpose: skip the rest of a reveal, or move from a round's
result to the next round (or the podium).
"""

import secrets
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from . import ai_players, cards, conf, dealing, scoring
from .memes import make_meme
from .models import CODE_ALPHABET, Meme, Player, Round, Session, Submission, Vote, new_token


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
        image_source = Session.PUBLIC_RANDOM   # spec §2.1: guests always draw from the public bank
        packs = None
    elif image_source in (Session.PACKS, Session.MIX) and not packs:
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
    host_player = Player.objects.create(
        session=session, user=host_user if is_logged_in else None,
        nickname=_default_nickname(host_user), is_host=True, seat_order=0,
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
        session.status = Session.PLAYING
        session.started_at = timezone.now()
        session.save(update_fields=["status", "started_at"])
        _create_round(session, 1, players)
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


def cast_vote(session, voter, round_number, submission_id):
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
            _start_voting(round_obj)
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
                if round_obj.reveal_deadline and now >= round_obj.reveal_deadline:
                    _start_voting(round_obj)
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


def _start_reveal(round_obj):
    memes_count = round_obj.submissions.filter(meme__isnull=False).count()
    round_obj.status = Round.REVEALED
    round_obj.reveal_deadline = timezone.now() + timezone.timedelta(
        seconds=conf.get("REVEAL_SECONDS_PER_MEME") * max(1, memes_count)
    )
    round_obj.save(update_fields=["status", "reveal_deadline"])


def _start_voting(round_obj):
    session = round_obj.session
    memes_count = round_obj.submissions.filter(meme__isnull=False).count()

    if session.game_mode == Session.RELAXED:
        # Rule 4.5.3 / §5.1: no voting, no points — the reveal was the
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
        # Rule 4.6.4: fewer than two memes, no vote — the lone meme (or
        # nobody, if zero) wins the round outright.
        _finish_round(round_obj, skip_vote=True, award=memes_count == 1)
        return
    round_obj.status = Round.VOTING
    round_obj.vote_deadline = timezone.now() + timezone.timedelta(seconds=session.vote_seconds)
    round_obj.save(update_fields=["status", "vote_deadline"])


def _finish_round(round_obj, *, skip_vote=False, award=True):
    round_obj.status = Round.DONE
    round_obj.save(update_fields=["status"])
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
