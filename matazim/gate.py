"""REQ-M.189 - the programme's main site opens to someone who has been through the test.

Atid, 2026-10-15, filed from the site by ליטל and approved by Avi: *"אתר הבית -
הרשמה לתכנית - להכניס את מבחן המיון. רק מי שעבר מבחן מיון יכול להיכנס לאתר
הראשי."* The site's own automatic assessment of that request said it already
existed (REQ-M.36), and it did not: REQ-M.177 of 2026-10-12 had taken the gate
away so that anyone joining by a leader's code is attached at once. Avi
approved the request anyway, so it is built: the gate is back, and it is
approved-by-a-person (REQ-M.182), not merely measured.

**Who it applies to.** A programme participant: someone who has a leader, or has
asked for one. They are in the programme, so the programme's main site waits for
their entrance product to be approved. Not a leader, a program manager or root:
the test measures a teenager's commitment and none of them is one.

**Who it does not apply to.** Someone with no leader and no request out: the open
door of SPR-M.59 and the open classes of SPR-M.60 are a separate promise Avi made
on 2026-10-12, that anyone who registers can learn the open basics, and nothing in
Litala's request says to take that back. She asked about "הרשמה לתכנית", the
programme's registration. If she meant the open door too, `applies()` is the one
function to widen (spec Q28).

**What stays open to them.** The front pages, the entrance test itself, the
annual path, their own path (which says what is next), the bell and their own
rights and data. The test and the notification that it was approved must stay
reachable, or the gate would be a door that cannot be opened.
"""

from functools import wraps

from django.shortcuts import redirect

from .access import candidate_of, is_program_manager, leader_of
from .models import Student


def applies(user):
    """Is this person kept out of the main site until the test is approved?"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or is_program_manager(user):
        return False
    if leader_of(user) or candidate_of(user):
        return False

    student = Student.objects.filter(user=user).only("leader_id", "pending_leader_id").first()
    if student is None or (student.leader_id is None and student.pending_leader_id is None):
        return False  # the open door: nobody to answer to, and a separate promise

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
