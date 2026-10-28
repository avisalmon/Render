"""Who may see what (REQ-D3.41). One question, asked by every page and every
API view: signed in, and approved or an admin. Everyone else sees the door.

A superuser (Avi) is admin regardless, and is a maker the first time he
opens the app; nobody asks Avi to ask himself for permission.
"""

from functools import wraps
from urllib.parse import quote

from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone

from .models import Maker


def display_name_for(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or (user.email.split("@")[0] if user.email else user.get_username())


def maker_of(user):
    if not getattr(user, "is_authenticated", False):
        return None
    maker = Maker.objects.filter(user=user).select_related("user").first()
    if maker is None and user.is_superuser:
        maker = Maker.objects.create(user=user, display_name=display_name_for(user), status=Maker.APPROVED,
                                     is_admin=True, decided_at=timezone.now())
    return maker


def can_enter(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    maker = maker_of(user)
    return bool(maker and (maker.status == Maker.APPROVED or maker.is_admin))


def is_admin(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    maker = maker_of(user)
    return bool(maker and maker.is_admin)


def inside(view):
    """A page for people who are in. Anyone else is sent to the door."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/design3d/login/?next=" + quote(request.get_full_path()))
        if not can_enter(request.user):
            return redirect("design3d:door")
        request.maker = maker_of(request.user)
        return view(request, *args, **kwargs)

    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            raise Http404
        request.maker = maker_of(request.user)
        return view(request, *args, **kwargs)

    return wrapped
