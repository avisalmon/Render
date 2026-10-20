"""Tiers (spec BK11, 12.11): one function decides what a person may do,
used everywhere. Payment is not open yet (Avi, 2026-10-20): the plans are
shown, paying is blocked, and the code "helpavi" gives the 4.99 tier free
for 90 days.

| feature            | free | plus (4.99) | pro (20) |
| ask                |  no  |     yes     |   yes    |  start a request (a free person answers one)
| club_post          |  no  |     yes     |   yes    |  start a thread or comment (reading is free)
| circle_create      |  no  |     yes     |   yes    |  start a circle (joining is free)
| web_lookup         |  no  |     yes     |   yes    |  better recognition: find a book on the web
| unlimited_library  |  no  |     yes     |   yes    |  more than 1,000 books

Staff are never refused (so the site's owner is never locked out of it). The
old pilot switch BOOKS_PILOT_EVERYONE_ASKS, when on, opens everything.
"""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Coupon, Profile, Subscription

ORDER = [Profile.FREE, Profile.PLUS, Profile.PRO]
FEATURES = {
    "ask": Profile.PLUS,
    "club_post": Profile.PLUS,
    "circle_create": Profile.PLUS,
    "web_lookup": Profile.PLUS,
    "unlimited_library": Profile.PLUS,
}


class TierError(Exception):
    """A refused coupon; the message is a catalogue key (plans.err.*)."""


def _rank(tier):
    return ORDER.index(tier) if tier in ORDER else 0


def active(profile, now=None):
    now = now or timezone.now()
    return Subscription.objects.filter(profile=profile, started_at__lte=now, ends_at__gt=now)


def effective(profile, now=None):
    """The highest tier in force: the hand-set one, or any subscription."""
    best = profile.tier if profile.tier in ORDER else Profile.FREE
    for sub in active(profile, now):
        if _rank(sub.tier) > _rank(best):
            best = sub.tier
    return best


def until(profile):
    """When the paid tier in force ends (None for a hand-set or free one)."""
    sub = active(profile).order_by("-ends_at").first()
    return sub.ends_at if sub else None


def allows(profile, feature):
    if profile is None:
        return False
    if getattr(settings, "BOOKS_PILOT_EVERYONE_ASKS", False):
        return True
    if profile.user.is_staff:
        return True
    return _rank(effective(profile)) >= _rank(FEATURES[feature])


@transaction.atomic
def redeem(profile, code):
    """A code, once per person: the tier for the coupon's days, starting now
    or when the person's current period of that tier ends."""
    code = (code or "").strip().lower()
    coupon = Coupon.objects.select_for_update().filter(code=code).first()
    now = timezone.now()
    if coupon is None or not coupon.is_active or (coupon.expires_at and coupon.expires_at <= now):
        raise TierError("plans.err.code")
    if coupon.max_uses is not None and coupon.uses >= coupon.max_uses:
        raise TierError("plans.err.used_up")
    if Subscription.objects.filter(profile=profile, coupon=coupon).exists():
        raise TierError("plans.err.already")
    start = now
    current = active(profile).filter(tier=coupon.tier).order_by("-ends_at").first()
    if current:
        start = current.ends_at
    try:
        sub = Subscription.objects.create(profile=profile, tier=coupon.tier, started_at=start,
                                          ends_at=start + timezone.timedelta(days=coupon.days),
                                          provider=Subscription.COUPON, coupon=coupon, note=f"code {code}")
    except IntegrityError:
        raise TierError("plans.err.already") from None
    Coupon.objects.filter(pk=coupon.pk).update(uses=F("uses") + 1)
    return sub
