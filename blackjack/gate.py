"""May this person use the paid features right now, and why.

**This is the only gate in the app that matters.** The free product contains no
path to a language model at all (spec 1.3), so there is nothing else to guard:
everything on the other side of this function is the paid tier, and everything
on this side of it is arithmetic the whole internet is welcome to.

Three sources, which is what Avi's answer contained:

- a **subscription**, asked of babook's `Entitlement`, never stored here
- a **coupon**, worth a week, bearer and one-time
- the **trial**, thirty minutes from first use

One function, asked everywhere, for the same reason `app/portal.py` is one
function: two answers drift, and the drift is invisible until somebody is
charged for something they had or handed something they had not.

**Fail shut.** Every branch ends in an explicit answer and the function ends in
a refusal, so a source nobody has implemented yet closes the door rather than
opening it.
"""

from dataclasses import dataclass

from django.utils import timezone

TRIAL_MINUTES = 30


@dataclass(frozen=True)
class Access:
    """Whether the paid tier is open, and what to say about it.

    A reason rather than a bare boolean, because every screen that asks this
    has to tell somebody something, and a screen inventing its own wording is
    how "your trial ended" becomes four different sentences.
    """

    open: bool
    source: str = ""
    until: object = None

    def __bool__(self):
        return self.open


def is_subscriber(user):
    """babook's answer, not ours.

    `Entitlement` is babook's and one payment will one day cover every app on
    the site. Asking rather than storing is what makes that change free here.
    """
    try:
        from app.models import Entitlement
    except Exception:  # pragma: no cover - babook is always installed here
        return False

    row = Entitlement.objects.filter(user=user).first()
    return bool(row and row.tier in ("base", "master"))


def trial_window(player):
    """The thirty minutes, or None if they have not started playing.

    Measured from the first hand rather than from signup (REQ-B.6.3), so
    somebody who joins on Monday and comes back on Thursday still has it.
    """
    from datetime import timedelta

    if player.first_used_at is None:
        return None
    return player.first_used_at, player.first_used_at + timedelta(minutes=TRIAL_MINUTES)


def ai_is_open(user):
    """The whole question, answered once.

    Order matters only for what the screen says: a subscriber is told they are
    a subscriber rather than that their trial is running.
    """
    from .models import Grant, Player

    if not getattr(user, "is_authenticated", False):
        return Access(False, "anonymous")

    if is_subscriber(user):
        return Access(True, "subscription")

    player = Player.objects.filter(user=user).first()
    if player is None:
        return Access(False, "nothing")

    now = timezone.now()

    grant = (
        Grant.objects.filter(player=player, starts_at__lte=now, ends_at__gt=now)
        .order_by("-ends_at")
        .first()
    )
    if grant is not None:
        return Access(True, grant.source, grant.ends_at)

    window = trial_window(player)
    if window and window[0] <= now < window[1]:
        return Access(True, "trial", window[1])

    return Access(False, "ended" if window else "nothing")


def redeem(user, code):
    """Spend a coupon and open a window. Returns the `Grant`, or None.

    **Never creates the account and never escalates**, which is the repo's own
    BKM for anything that hands out access: the worst a stolen code can do is
    give one person a week of a blackjack tutor.

    Refuses a spent coupon rather than silently extending, because a code that
    works twice is a code that works forever once it reaches a group chat.
    """
    from datetime import timedelta

    from django.db import transaction

    from .models import Coupon, Grant, Player

    cleaned = (code or "").strip().upper().replace("-", "").replace(" ", "")
    if not cleaned:
        return None

    with transaction.atomic():
        coupon = (
            Coupon.objects.select_for_update()
            .filter(code=cleaned, redeemed_by__isnull=True)
            .first()
        )
        if coupon is None:
            return None

        player = Player.for_user(user)
        now = timezone.now()
        coupon.redeemed_by = user
        coupon.redeemed_at = now
        coupon.save(update_fields=["redeemed_by", "redeemed_at"])

        return Grant.objects.create(
            player=player,
            source=Grant.COUPON,
            coupon=coupon,
            starts_at=now,
            ends_at=now + timedelta(days=coupon.days),
        )
