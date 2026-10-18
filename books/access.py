"""Who may be where in Books. One place, used by every view.

A page needs a signed-in person (else Books' own sign-in) who has finished
onboarding (else onboarding). The API uses the same rule through
api/permissions.py.
"""

from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse


def profile_for(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "books_profile", None)


def books_page(view):
    """Signed in and onboarded, or sent to the step that is missing."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('books:login')}?next={request.path}")
        profile = profile_for(request.user)
        if profile is None:
            return redirect(f"{reverse('books:onboarding')}?next={request.path}")
        request.books_profile = profile
        return view(request, *args, **kwargs)

    return wrapper
