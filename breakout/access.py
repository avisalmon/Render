"""Who may see and do what (spec chapter 9). One function per question,
used by the screens and the API alike, so the two cannot drift.

The whole app is behind the shared sign-in. Beyond that, two facts decide
everything: is this person the author of the experience, and is their
Profile a curator. A superuser is a curator (so the site admin is not
locked out of their own app; spec chapter 7 names this exception).
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import Experience, Profile

LOGIN_URL = "/breakout/login/"


def profile_for(user):
    """The person's Profile, made on first sight. None when signed out."""
    if not getattr(user, "is_authenticated", False):
        return None
    profile, _made = Profile.objects.get_or_create(user=user)
    return profile


def is_curator(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return Profile.objects.filter(user=user, is_curator=True).exists()


def may_edit(user, experience):
    return bool(getattr(user, "is_authenticated", False) and experience.author_id == user.pk)


def may_see(user, experience):
    """Published: everyone signed in. Draft or hidden: the author and curators."""
    if not getattr(user, "is_authenticated", False):
        return False
    if experience.status == Experience.PUBLISHED:
        return True
    return may_edit(user, experience) or is_curator(user)


def visible_experiences(user):
    """The queryset every list and lookup goes through."""
    if not getattr(user, "is_authenticated", False):
        return Experience.objects.none()
    if is_curator(user):
        return Experience.objects.all()
    return Experience.objects.filter(Q(status=Experience.PUBLISHED) | Q(author=user))


def signed_in(view):
    """The app's own door, not babook's: a stranger lands on /breakout/login/."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        return login_required(view, login_url=LOGIN_URL)(request, *args, **kwargs)

    return wrapped
