"""Who may see and do what (spec chapter 9). One function per question,
used by the screens and the API alike, so the two cannot drift.

The whole app is behind the shared sign-in, and behind one more door: the
site is for teachers (Avi, 2026-11-27: "students have no access to the
site, and that is that"), so a signed-in person who is not yet an approved
teacher sees one page, /breakout/welcome/, where they tell us about
themselves; a curator approves them once. Beyond that, two facts decide
everything: is this person the author of the experience, and is their
Profile a curator. A superuser is a curator (so the site admin is not
locked out of their own app; spec chapter 7 names this exception), and a
curator is a teacher.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone

from .models import Experience, Profile

LOGIN_URL = "/breakout/login/"
WELCOME_URL = "/breakout/welcome/"


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


def is_teacher(user):
    """Through the teachers' door: approved, or a curator (a superuser too)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return Profile.objects.filter(user=user).filter(Q(is_teacher=True) | Q(is_curator=True)).exists()


def pending_teachers():
    """Who asked and waits, oldest first: the curator's queue."""
    return Profile.objects.filter(asked_at__isnull=False, is_teacher=False, is_curator=False).select_related("user").order_by("asked_at")


def approve_teacher(profile, by):
    profile.is_teacher = True
    profile.teacher_since = timezone.now()
    profile.teacher_by = by
    profile.save(update_fields=["is_teacher", "teacher_since", "teacher_by"])


def decline_teacher(profile):
    """Not a teacher: the ask is cleared, the person may ask again."""
    profile.asked_at = None
    profile.save(update_fields=["asked_at"])


def may_write(user):
    """Who may start a new experience. Avi, 2026-11-26: "only I put up
    challenges" for now, so writing is the curators'; opening it to every
    teacher (spec 5 as first written) is one line here, when he says so."""
    return is_curator(user)


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
    """The app's own door, not babook's: a stranger lands on /breakout/login/,
    and a signed-in person who is not an approved teacher on /breakout/welcome/.
    Every screen and file of the app stands behind this one decorator."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_teacher(request.user):
            return redirect(WELCOME_URL)
        return view(request, *args, **kwargs)

    return login_required(wrapped, login_url=LOGIN_URL)
