"""Who may see what. One question, asked by every page and every API view
(REQ-C.42): signed in, and approved or an admin. Everything else sees the door.

Avi's account is a superuser and is admin regardless; that bypass is
deliberate (spec Chapter 7), so the course's own teacher is never locked out.
"""

from functools import wraps

from django.shortcuts import redirect
from django.utils import timezone

from .models import Member


def member_of(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return Member.objects.filter(user=user).select_related("user").first()


def ensure_admin_member(user):
    """A superuser who opens the app is a member already; nobody asks Avi to
    ask himself for permission."""
    member = member_of(user)
    if member is None:
        member = Member.objects.create(
            user=user, display_name=display_name_for(user), status=Member.APPROVED,
            is_admin=True, decided_at=timezone.now(),
        )
    return member


def display_name_for(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or (user.email.split("@")[0] if user.email else user.get_username())


def can_enter(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    member = member_of(user)
    return bool(member and (member.status == Member.APPROVED or member.is_admin))


def is_admin(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    member = member_of(user)
    return bool(member and member.is_admin)


def inside(view):
    """A page for approved participants. Anybody else is sent to the door."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_enter(request.user):
            return redirect("cohort:door")
        if request.user.is_superuser:
            ensure_admin_member(request.user)
        request.cohort_member = member_of(request.user)
        return view(request, *args, **kwargs)

    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            from django.http import Http404

            raise Http404
        if request.user.is_superuser:
            ensure_admin_member(request.user)
        request.cohort_member = member_of(request.user)
        return view(request, *args, **kwargs)

    return wrapped
