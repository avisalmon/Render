"""Which image each player gets each round (spec §6.5, Rule 6.5.1).

SPR-Z.3 implements `public_random` only (Normal mode's one real source);
`packs`, `own_only` and `mix` are spec'd and modeled (`Session.packs`,
`Session.image_source`) but wait on SPR-Z.5's uploads/packs UI to be worth
exposing on the create screen. `pool_for` already reads the field, so
turning them on later is a create-screen change, not a dealing change.

SPR-Z.9 (Rule 6.5.3): `own_only`/`mix` now draw from every currently
seated signed-in player's own approved uploads, not only the host's —
"own" stopped meaning "the host's" and started meaning "whoever's actually
in the room." A player is never (best-effort — see `deal_round`'s own
note) dealt their own upload, and a session-wide 30% ceiling on how many
dealt images may come from anyone's personal stock is enforced in
`deal_round`/`deal_same_image`, not in the pool itself (the pool is just
"what's eligible"; the cap is about "how often did we actually reach for
it").
"""

import random

from django.db.models import Q

from .models import MemeImage, Player, Session, Submission, Topic

# Rule 6.5.3: never more than this share of a session's dealt images comes
# from a player's own stock. Checked before adding one more, so the ratio
# can sit at or just under this line, never meaningfully over it.
#
# SPR-Z.11 (2026-09-19): 0.30 -> 0.50, Avi's call. At 30% the players'
# own photos were seasoning; the ask is for them to be half the game
# ("whenever he's playing, a random picture will be chosen from his
# pictures"). A ceiling still earns its place: it keeps the public bank
# present, so a room where exactly one person uploaded doesn't turn into
# an evening of that one person's camera roll.
PLAYER_STOCK_MAX_SHARE = 0.50


def _seated_signed_in_user_ids(session):
    """Rule 6.5.3: a guest contributes nothing — uploading requires an
    account (Rule 6.2.1) — so this is exactly the seated players who
    *could* have anything to contribute, AI seats excluded (they own
    nothing)."""
    return set(
        Player.objects.filter(session=session, user_id__isnull=False, is_ai=False)
        .values_list("user_id", flat=True)
    )


def pool_for(session):
    """The images this session may deal, approved only (Rule 6.4.1).

    `mix` is the default from SPR-Z.11 on, and means what the screen has
    always said it means: **everyone's own uploads plus the public bank**,
    plus any packs the host picked. It did not, before: with no packs
    chosen it quietly fell through to own-uploads-only, so a room where
    nobody had uploaded anything had an empty pool, and one where somebody
    had got nothing but that person's photos. The label promised the
    public bank and the query never included it."""
    base = Q(moderation_status=MemeImage.APPROVED)
    public = Q(owner__isnull=True, visibility=MemeImage.PUBLIC)

    if session.image_source == Session.PACKS and session.packs.exists():
        return MemeImage.objects.filter(base, packs__in=session.packs.all()).distinct()

    if session.image_source == Session.OWN_ONLY:
        user_ids = _seated_signed_in_user_ids(session)
        if not user_ids:
            return MemeImage.objects.none()
        return MemeImage.objects.filter(base & Q(owner_id__in=user_ids)).distinct()

    if session.image_source == Session.MIX:
        user_ids = _seated_signed_in_user_ids(session)
        sources = public
        if user_ids:
            sources = sources | Q(owner_id__in=user_ids)
        if session.packs.exists():
            sources = sources | Q(packs__in=session.packs.all())
        return MemeImage.objects.filter(base & sources).distinct()

    return MemeImage.objects.filter(base, public)


def _unseen_and_pool(session):
    pool = list(pool_for(session))
    if not pool:
        return [], []
    seen_ids = set(Submission.objects.filter(round__session=session).values_list("image_id", flat=True))
    unseen = [img for img in pool if img.id not in seen_ids]
    random.shuffle(unseen)
    random.shuffle(pool)
    return unseen, pool


def _dealt_stock_counts(session):
    """(total images dealt so far, how many were someone's own stock) —
    Submission rows exist from the moment a round starts (data_model.md),
    so this is the true dealt history, not just what's been captioned."""
    qs = Submission.objects.filter(round__session=session, image__isnull=False)
    total = qs.count()
    personal = qs.filter(image__owner__isnull=False).count()
    return total, personal


def _under_stock_cap(total, personal, adding=1):
    """Would dealing `adding` more personal-stock images still keep the
    session at or under Rule 6.5.3's 30% ceiling? True at the very start
    (nothing dealt yet to compute a ratio from) so "at least one per
    round when available" can actually take effect from round one."""
    if total == 0:
        return True
    return (personal + adding) / (total + adding) <= PLAYER_STOCK_MAX_SHARE


def deal_round(session, players):
    """One image per player for a new round (Normal/Topics modes): no
    repeats within the session while unseen images remain, and no
    duplicate image within this round while the pool allows (Rule 6.5.1).
    Returns {player: MemeImage}.

    Rule 6.5.3: when the pool has any of a *seated* player's own images in
    it, one image this round is preferentially drawn from someone's own
    stock (never that same player's own — the pool otherwise doesn't
    distinguish who a personal image belongs to), while the session-wide
    30% cap allows it; once the cap is reached the round instead prefers a
    non-personal image, if the pool has one. In `own_only` mode the pool
    is *entirely* personal by design — this doesn't try to force a public
    fallback that doesn't exist, it just keeps dealing personal images.

    "Never that player's own" is best-effort, not absolute: if a pool is
    small enough that a player's own uploads are the only candidates left
    (own_only, one uploader, few images), they still get dealt one rather
    than the round breaking — same "never crashes a game over a small
    bank" philosophy as the fallback below.

    Falls back to reusing images (still no duplicates *within* the round,
    when the pool is at least as big as the player count) once every image
    has been dealt at least once — never crashes a game over a small bank.
    """
    unseen, pool = _unseen_and_pool(session)
    if not pool:
        return {}

    # The cap decision is made once, from the state *before* this round —
    # not re-checked per player as the round's own non-personal picks come
    # in, which would otherwise make an early self-excluded player (their
    # own upload was the only personal candidate, so they got a public
    # image instead) poison the cap check for every later player in the
    # same round, well before the round is even a third personal.
    total, personal = _dealt_stock_counts(session)
    allow_personal_this_round = _under_stock_cap(total, personal)
    personal_used_this_round = False

    assignment = {}
    used_this_round = set()
    for player in players:
        candidates = [img for img in unseen if img.id not in used_this_round]
        if not candidates:
            candidates = [img for img in pool if img.id not in used_this_round] or pool

        image = None
        if not personal_used_this_round and allow_personal_this_round:
            personal_candidates = [
                img for img in candidates if img.owner_id is not None and img.owner_id != player.user_id
            ]
            if personal_candidates:
                image = personal_candidates[0]

        if image is None:
            non_personal = [img for img in candidates if img.owner_id is None]
            own_excluded = [img for img in candidates if img.owner_id != player.user_id]
            image = (non_personal or own_excluded or candidates)[0]

        if image.owner_id is not None:
            personal_used_this_round = True

        assignment[player] = image
        used_this_round.add(image.id)
        if image in unseen:
            unseen.remove(image)
    return assignment


def deal_same_image(session, players):
    """Same Meme mode (spec §5.1): one image, shared by everyone this
    round. Still prefers an unseen image while any remain.

    Rule 6.5.3: the shared image may itself be a seated player's own
    upload, subject to the same session-wide 30% cap as every other mode.
    Self-exclusion doesn't apply the way it does in `deal_round` — every
    player, including the image's own owner if they're seated, sees and
    captions the one shared image, so there is no "other player" to
    prefer instead."""
    unseen, pool = _unseen_and_pool(session)
    if not pool:
        return {}

    total, personal = _dealt_stock_counts(session)
    image = None
    if _under_stock_cap(total, personal):
        personal_candidates = [img for img in (unseen or pool) if img.owner_id is not None]
        if personal_candidates:
            image = personal_candidates[0]
    if image is None:
        non_personal = [img for img in (unseen or pool) if img.owner_id is None]
        image = (non_personal or unseen or pool)[0]
    return {player: image for player in players}


def deal_replacement(session, submission):
    """SPR-Z.10 (Rule 4.4.5): one fresh image for a player who threw back
    the one they were dealt. Returns a `MemeImage`, or None if the pool
    has nothing else to give.

    Same preferences as `deal_round`, scoped to one seat: an image nobody
    in this session has been dealt yet if any remain, never the one they
    are holding right now, and never one already in someone else's hands
    this same round (a swap must not create the duplicate within a round
    that Rule 6.5.1 exists to prevent). A player's own upload is still
    avoided where the pool allows. The 30% personal-stock cap is checked
    the same way, just for this single image.

    Deliberately does NOT re-run the whole round's deal: everyone else has
    already seen their image, some may already be typing, and re-dealing
    the table because one player didn't like their photo would be a much
    bigger surprise than the one they asked for."""
    unseen, pool = _unseen_and_pool(session)
    if not pool:
        return None

    # Off limits: what anyone else is holding this round, what this player
    # is holding now, and everything they have already thrown back --
    # `Submission.image` only ever remembers the current picture, so
    # without the third of those a refused image quietly returns to the
    # "nobody has seen this" pool and can be dealt straight back.
    held_now = set(
        Submission.objects.filter(round=submission.round)
        .exclude(pk=submission.pk)
        .values_list("image_id", flat=True)
    )
    held_now.add(submission.image_id)
    refused = set(submission.swapped_away_image_ids or [])
    off_limits = held_now | refused

    def free(images):
        return [img for img in images if img.id not in off_limits]

    candidates = free(unseen) or free(pool)
    if not candidates:
        # Every image in the pool is either on someone's phone this round
        # or one this player already said no to. Better to hand back
        # something seen before than to refuse a swap they were told they
        # had -- but still never the one already in front of them.
        candidates = [img for img in pool if img.id not in held_now] or \
            [img for img in pool if img.id != submission.image_id] or pool

    total, personal = _dealt_stock_counts(session)
    own_user_id = submission.player.user_id
    if _under_stock_cap(total, personal):
        personal_candidates = [
            img for img in candidates if img.owner_id is not None and img.owner_id != own_user_id
        ]
        if personal_candidates:
            return personal_candidates[0]

    non_personal = [img for img in candidates if img.owner_id is None]
    own_excluded = [img for img in candidates if img.owner_id != own_user_id]
    return (non_personal or own_excluded or candidates)[0]


def deal_topic(session):
    """Topics mode (spec §5.1, Rule 5.1.1): one topic per round, no
    repeats within the session while unused ones remain. Public topics
    plus, for a logged-in host, their own."""
    base = Q(owner__isnull=True, is_public=True)
    if session.host_user_id:
        base |= Q(owner_id=session.host_user_id)
    pool = list(Topic.objects.filter(base))
    if not pool:
        return None
    used_ids = set(session.rounds.exclude(topic=None).values_list("topic_id", flat=True))
    unused = [t for t in pool if t.id not in used_ids]
    return random.choice(unused or pool)
