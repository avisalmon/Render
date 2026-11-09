"""Who may do what (REQ-G.1, G.2). Looking is open to everybody; doing needs a
sign-in, and nothing more: no request, no approval.

Avi's account is a superuser and is admin regardless; that bypass is
deliberate (spec Chapter 10), so the gallery's owner is never locked out.
"""

from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.utils.text import slugify

from .models import Person


def person_of(user):
    """The person's row, or None. Read-only: looking never creates one."""
    if not getattr(user, "is_authenticated", False):
        return None
    return Person.objects.filter(user=user).select_related("user", "training").first()


def display_name_for(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or (user.email.split("@")[0] if user.email else user.get_username())


def _free_slug(name, user_pk):
    base = slugify(name, allow_unicode=True)[:80] or f"u{user_pk}"
    if base == "me":
        base = f"me-{user_pk}"
    slug, n = base, 2
    while Person.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def ensure_person(user, language=None):
    """The row for a signed-in person who is about to do something."""
    person = person_of(user)
    if person is None:
        name = display_name_for(user)
        person = Person.objects.create(
            user=user, display_name=name, slug=_free_slug(name, user.pk),
            language=language if language in ("he", "en") else Person.HE,
            is_admin=user.is_superuser,
        )
    return person


def is_admin(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    person = person_of(user)
    return bool(person and person.is_admin)


def login_url(next_path):
    return "/gallery/login/?" + urlencode({"next": next_path})


def signed_in(view):
    """A page for doing things. A visitor is sent to sign in and back."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(login_url(request.get_full_path()))
        request.gallery_person = ensure_person(request.user, getattr(request, "gallery_language", None))
        return view(request, *args, **kwargs)

    return wrapped


def with_training(view):
    """Posting asks the training first, once (REQ-G.4). Use under `signed_in`."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.gallery_person.answered_training:
            return redirect("/gallery/training/?" + urlencode({"next": request.get_full_path()}))
        return view(request, *args, **kwargs)

    return wrapped
