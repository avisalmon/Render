"""Who may do what (REQ-B.2, B.3). The wall is public; everything on it that
opens, counts or talks needs a signed-in person. Admin is a superuser: only
Avi changes the BKMs (REQ-B.20)."""

from functools import wraps
from urllib.parse import quote

from django.shortcuts import redirect

from .models import Reader


def display_name_for(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or (user.email.split("@")[0] if user.email else user.get_username())


def reader_for(user, create=True):
    if not getattr(user, "is_authenticated", False):
        return None
    reader = Reader.objects.filter(user=user).first()
    if reader is None and create:
        reader, _ = Reader.objects.get_or_create(user=user, defaults={"display_name": display_name_for(user)})
    return reader


def is_admin(user):
    return bool(getattr(user, "is_authenticated", False) and user.is_superuser)


def login_url(next_path):
    return "/bkm/login/?next=" + quote(next_path)


def signed_in(view):
    """A page for signed-in people. Anybody else goes to sign in, and comes
    back to the page they wanted."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(login_url(request.get_full_path()))
        request.bkm_reader = reader_for(request.user)
        return view(request, *args, **kwargs)

    return wrapped
