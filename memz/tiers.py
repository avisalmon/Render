"""Who is this, as far as memz is concerned (spec §2, §3.3.4).

Three tiers, one function. `tier_for` never creates anything; `profile_for`
creates the one-to-one profile the first time a logged-in person actually
uses memz, and never for a babook user who has not.
"""

from django.utils import timezone

from .models import MemzProfile

GUEST = "guest"
FREE = "free"
PAID = "paid"


def tier_for(user):
    """`guest` for nobody or an anonymous visitor; `paid` only while
    `paid_until` is in the future; `free` otherwise, profile or not."""
    if user is None or not getattr(user, "is_authenticated", False):
        return GUEST
    profile = MemzProfile.objects.filter(user=user).only("tier", "paid_until").first()
    if profile is None:
        return FREE
    if profile.tier == PAID and profile.paid_until and profile.paid_until > timezone.now():
        return PAID
    return FREE


def default_display_name(user):
    return (user.first_name or "").strip() or user.get_username()


def profile_for(user):
    """The profile, created on first use (Rule 3.3.4)."""
    profile, _created = MemzProfile.objects.get_or_create(
        user=user, defaults={"display_name": default_display_name(user)}
    )
    return profile
