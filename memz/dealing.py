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
PLAYER_STOCK_MAX_SHARE = 0.30


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
    """The images this session may deal, approved only (Rule 6.4.1)."""
    base = Q(moderation_status=MemeImage.APPROVED)
    if session.image_source == Session.PACKS and session.packs.exists():
        return MemeImage.objects.filter(base, packs__in=session.packs.all()).distinct()
    if session.image_source in (Session.OWN_ONLY, Session.MIX):
        user_ids = _seated_signed_in_user_ids(session)
        own = Q(owner_id__in=user_ids) if user_ids else None
        if session.image_source == Session.MIX and session.packs.exists():
            packs_q = Q(packs__in=session.packs.all())
            own = packs_q if own is None else (own | packs_q)
        if own is not None:
            return MemeImage.objects.filter(base & own).distinct()
        return MemeImage.objects.none()
    return MemeImage.objects.filter(base, owner__isnull=True, visibility=MemeImage.PUBLIC)


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
