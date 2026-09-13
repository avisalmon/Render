"""Who gets in (spec §3).

One rule, checked one way, everywhere: a person is in the `family` auth
Group, or they see nothing. No email pattern, no domain check, no
"babook admin implies access" shortcut — closed by default, no exceptions.
The group itself is created by a migration (0002) so it always exists.
"""

from functools import wraps

from django.shortcuts import render

FAMILY_GROUP = "family"


def is_family(user):
    if not user.is_authenticated:
        return False
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
