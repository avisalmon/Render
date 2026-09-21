"""Who gets in (spec §3).

A person is in the `family` auth Group, or they see nothing — no email
pattern, no domain check. One deliberate exception: a babook superuser
always gets in, so the site admin never has to remember to add themself
to `family` before they can see their own app. The group itself is
created by a migration (0002) so it always exists.

`is_family` is the one rule, used both here (page views) and by
`ustrip.permissions.IsFamilyMember` (the DRF API) — same check everywhere.
"""

from functools import wraps

from django.shortcuts import render

FAMILY_GROUP = "family"


def is_family(user):
    """The one rule, and since F-13.4 it is babook's copy of it.

    The rule has not changed: the `family` group, plus a superuser, for the
    reason in the module docstring. What changed is where it is written.
    `app.portal` decides who sees which app, and the portal on babook's home
    page asks the same function, so a card that appears and a door that opens
    cannot drift apart. They already had: the portal hid ustrip from an admin
    while this function let them in.

    The direction of the dependency is the allowed one. An app may ask babook;
    babook asks no app anything, and `app/portal.py` imports nothing from here.
    """
    from app.portal import may_enter

    return may_enter(user, "ustrip")


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
