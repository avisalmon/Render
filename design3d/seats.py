"""Seats and turns (Chapter 8, Avi 2026-10-30).

- An invitation (a friend's link, or a one-time link) lets a newcomer in at
  once with 30 turns, while there are seats; past the seat limit the
  newcomer waits (`Maker.WAITING_SEAT`) and is let in, oldest first, when
  Avi raises the limit.
- Asking with no invitation still waits for Avi, and whom he approves has
  no turn limit (`turns_left` None; the daily dollar limit still holds).
- One message to the chat is one turn. When someone a person brought builds
  a first part, that person gets 30 turns, once per friend.
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import access
from .models import Maker, Settings

STARTER_TURNS = 30
FRIEND_TURNS = 30


def seats_used():
    return Maker.objects.filter(invited=True, status=Maker.APPROVED).count()


def seats_free():
    return max(0, Settings.get().seat_limit - seats_used())


def admit(user, referrer, request=None):
    """Someone opened an invitation. Returns their Maker: in with 30 turns,
    or waiting for a seat. Someone already in is left as they are."""
    maker = access.maker_of(user)
    if referrer is not None and maker is not None and referrer.pk == maker.pk:
        referrer = None
    if maker is None:
        maker = Maker.objects.create(user=user, display_name=access.display_name_for(user), reason="Invited",
                                     referred_by=referrer, invited=True, status=Maker.WAITING_SEAT)
    elif maker.status == Maker.APPROVED or maker.is_admin:
        return maker
    else:
        maker.invited = True
        maker.referred_by = maker.referred_by or referrer
        maker.status = Maker.WAITING_SEAT
        maker.save(update_fields=["invited", "referred_by", "status"])
    with transaction.atomic():
        if seats_free() > 0:
            maker.turns_left = STARTER_TURNS
            maker.save(update_fields=["turns_left"])
            access.let_in(maker, referrer.user if referrer else None, request)
    maker.refresh_from_db()
    return maker


def fill(request=None):
    """Let the waiting in, oldest first, while there are seats. Returns how many."""
    n = 0
    while seats_free() > 0:
        nxt = Maker.objects.filter(status=Maker.WAITING_SEAT).order_by("requested_at", "pk").first()
        if nxt is None:
            break
        nxt.turns_left = STARTER_TURNS
        nxt.save(update_fields=["turns_left"])
        access.let_in(nxt, None, request)
        n += 1
    return n


def take_turn(maker):
    """One turn for one message. False when none are left."""
    if maker.turns_left is None:
        return True
    taken = Maker.objects.filter(pk=maker.pk, turns_left__gt=0).update(turns_left=F("turns_left") - 1)
    maker.refresh_from_db(fields=["turns_left"])
    return bool(taken)


def give_back(maker):
    """A turn that never reached the chat (a refused upload) is returned."""
    if maker.turns_left is not None:
        Maker.objects.filter(pk=maker.pk).update(turns_left=F("turns_left") + 1)


def reward_friend(maker):
    """The first part this person's chat built gives their friend 30 turns, once."""
    if maker.referred_by_id is None or maker.rewarded_at is not None:
        return False
    done = Maker.objects.filter(pk=maker.pk, rewarded_at__isnull=True).update(rewarded_at=timezone.now())
    if done:
        Maker.objects.filter(pk=maker.referred_by_id, turns_left__isnull=False).update(
            turns_left=F("turns_left") + FRIEND_TURNS)
    return bool(done)
