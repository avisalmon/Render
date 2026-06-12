"""Authoring Studio access control (REQ-4.1.1)."""
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import redirect


def is_author(user):
    """Staff are implicitly authors; others need UserProfile.is_author."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_author)


def author_required(view_func):
    """Guard a studio view: anonymous -> login; authenticated non-author -> 403."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if not is_author(request.user):
            return HttpResponse("Authoring access required.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped
