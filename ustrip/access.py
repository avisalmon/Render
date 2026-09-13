"""Who gets in (spec §3).

A person is in the `family` auth Group, or they see nothing — no email
pattern, no domain check. One deliberate exception: a babook superuser
always gets in, so the site admin never has to remember to add themself
to `family` before they can see their own app. The group itself is
created by a migration (0002) so it always exists.
"""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import render

FAMILY_GROUP = "family"


def is_family(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=FAMILY_GROUP).exists()


def family_required(view_func):
    """Spec §3: non-members (including anonymous visitors) get a plain
    access-denied page, not a 404 — ustrip has no reason to hide that it
    exists, unlike /home."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_family(request.user):
            return render(request, "ustrip/access_denied.html", status=403)
        return view_func(request, *args, **kwargs)

    return wrapped


def family_required_api(view_func):
    """Same rule as `family_required`, for the JSON endpoints under
    `/ustrip/api/` — a plain 403 body instead of the HTML access-denied
    page, since these are called from fetch(), not navigated to."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_family(request.user):
            return JsonResponse({"error": "forbidden"}, status=403)
        return view_func(request, *args, **kwargs)

    return wrapped
