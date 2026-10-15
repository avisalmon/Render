"""REQ-M.189 - the programme's main site opens to someone who has been through the test.

Atid, 2026-10-15, filed from the site by ליטל and approved by Avi: *"אתר הבית -
הרשמה לתכנית - להכניס את מבחן המיון. רק מי שעבר מבחן מיון יכול להיכנס לאתר
הראשי."* The site's own automatic assessment of that request said it already
existed (REQ-M.36), and it did not: REQ-M.177 of 2026-10-12 had taken the gate
away so that anyone joining by a leader's code is attached at once. Avi
approved the request anyway, so it is built: the gate is back, and it is
approved-by-a-person (REQ-M.182), not merely measured.

**Who it applies to.** Everyone who signs in as a learner: anyone who is not a
leader, a candidate, a program manager or root. Avi, 2026-10-15, on Q28: "Litala's
definition is priority". She wrote that only someone who passed the screening test
can enter the main site, so there is no exemption for someone with no leader. The
open door of SPR-M.59 and the open classes of SPR-M.60 close with it: they were
Avi's own idea of 2026-10-12, and her request is the later and the client's.

**What stays open to them.** The front pages, the entrance test itself, the
annual path, their own path (which says what is next), the bell and their own
rights and data. The test and the notification that it was approved must stay
reachable, or the gate would be a door that cannot be opened.
"""

from functools import wraps

from django.shortcuts import redirect

from .access import candidate_of, is_program_manager, leader_of


def applies(user):
    """Is this person kept out of the main site until the test is approved?"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or is_program_manager(user):
        return False
    if leader_of(user) or candidate_of(user):
        return False

    from .views import member_profile

    return not member_profile(user).has_passed_entrance_test()


def entrance_gated(view):
    """Send a participant who has not passed to the test, saying why."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if applies(request.user):
            return redirect("/matazim/test/?gate=1")
        return view(request, *args, **kwargs)

    return wrapper
