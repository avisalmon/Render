"""Which image each player gets each round (spec §6.5, Rule 6.5.1).

SPR-Z.3 implements `public_random` only (Normal mode's one real source);
`packs`, `own_only` and `mix` are spec'd and modeled (`Session.packs`,
`Session.image_source`) but wait on SPR-Z.5's uploads/packs UI to be worth
exposing on the create screen. `pool_for` already reads the field, so
turning them on later is a create-screen change, not a dealing change.
"""

import random

from django.db.models import Q

from .models import MemeImage, Session, Submission, Topic


def pool_for(session):
    """The images this session may deal, approved only (Rule 6.4.1)."""
    base = Q(moderation_status=MemeImage.APPROVED)
    if session.image_source == Session.PACKS and session.packs.exists():
        return MemeImage.objects.filter(base, packs__in=session.packs.all()).distinct()
    if session.image_source in (Session.OWN_ONLY, Session.MIX) and session.host_user_id:
        own = Q(owner_id=session.host_user_id)
        if session.image_source == Session.MIX and session.packs.exists():
            own |= Q(packs__in=session.packs.all())
        return MemeImage.objects.filter(base & own).distinct()
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


def deal_round(session, players):
    """One image per player for a new round (Normal/Topics modes): no
    repeats within the session while unseen images remain, and no
    duplicate image within this round while the pool allows (Rule 6.5.1).
    Returns {player: MemeImage}.

    Falls back to reusing images (still no duplicates *within* the round,
    when the pool is at least as big as the player count) once every image
    has been dealt at least once — never crashes a game over a small bank.
    """
    unseen, pool = _unseen_and_pool(session)
    if not pool:
        return {}

    assignment = {}
    used_this_round = set()
    for player in players:
        candidates = [img for img in unseen if img.id not in used_this_round]
        if not candidates:
            candidates = [img for img in pool if img.id not in used_this_round] or pool
        image = candidates[0]
        assignment[player] = image
        used_this_round.add(image.id)
        if image in unseen:
            unseen.remove(image)
    return assignment


def deal_same_image(session, players):
    """Same Meme mode (spec §5.1): one image, shared by everyone this
    round. Still prefers an unseen image while any remain."""
    unseen, pool = _unseen_and_pool(session)
    if not pool:
        return {}
    image = (unseen or pool)[0]
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
