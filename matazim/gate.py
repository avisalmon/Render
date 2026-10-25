"""REQ-M.189, REQ-M.191 - the three stages of a learner, and what each one may see.

Atid, 2026-10-15, filed from the site by ליטל and approved by Avi: *"רק מי שעבר
מבחן מיון יכול להיכנס לאתר הראשי."* And later the same day, through Avi, her
description of the whole entrance:

1. A student who signs in sees nothing open. They begin with the test, and the
   site is minimal and pointed at that.
2. Only after passing do they join a leader: by a code, or from an open list of
   leaders they can sort by school.
3. Once attached to a leader the site opens, in the state before being a מטצ.
4. After joining, the home screen is big tiles.

So a learner is always at exactly one of three stages, and this module is the one
place that says which:

- ``test``    has not been approved: the only thing there is the test
- ``join``    approved, with no leader: the only thing there is choosing one
- ``member``  approved and attached: the whole site

Not a learner at all: a leader, a candidate, a program manager, root. The test
measures a teenager's commitment and none of them is one. They get ``None``.

Avi, 2026-10-15, on Q28: "Litala's definition is priority". That is why there is
no exemption for the open door of SPR-M.59 and the open classes of SPR-M.60: both
were his own idea of 2026-10-12 and her description is the later and the
client's. What stays open at every stage is how a person gets through: the test,
choosing a leader, their own path, the bell, their rights and data.
"""

from functools import wraps

from django.shortcuts import redirect

from .access import candidate_of, is_program_manager, leader_of

TEST, JOIN, MEMBER = "test", "join", "member"

WHERE = {
    TEST: "/matazim/test/?gate=1",
    JOIN: "/matazim/join-leader/",
}


def learner_stage(user):
    """test, join or member for a learner; None for anybody who is not one."""
    if not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser or is_program_manager(user):
        return None
    if leader_of(user) or candidate_of(user):
        return None

    from .views import _has_leader, member_profile

    if not member_profile(user).has_passed_entrance_test():
        return TEST
    if not _has_leader(user):
        return JOIN
    return MEMBER


PREVIEW_KEY = "mz_preview_stage"


def may_preview(user):
    """Who can look at the site as a student: root, a program manager, a leader.

    Lital, 2026-10-15: "we want to see how the site shows to the student". They are
    not students, so they cannot be at a stage, and a way to look is the answer.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        user.is_superuser or is_program_manager(user) or leader_of(user) or candidate_of(user)
    )


def preview_stages(user):
    """The stages this person may look at. SPR-M.71.

    Lital, 2026-10-25: a leader who registers through the link should see the
    students' entry, the screening test and the path while waiting for approval.
    A candidate is anyone who held an open link, so they see the two stages that
    show nothing of anybody (the test, and choosing a leader); the whole site,
    with its community, waits for a person to approve them, as everything else does.
    """
    if not may_preview(user):
        return ()
    if user.is_superuser or is_program_manager(user) or leader_of(user):
        return (TEST, JOIN, MEMBER)
    return (TEST, JOIN)


def preview_stage(request):
    """The stage a manager has chosen to look at, or None."""
    chosen = request.session.get(PREVIEW_KEY)
    return chosen if chosen in preview_stages(request.user) else None


def stage_for(request):
    """The stage to treat this request as: the one being previewed, else the person's own."""
    return preview_stage(request) or learner_stage(request.user)


def applies(user):
    """Is this person kept out of the main site for now?"""
    return learner_stage(user) in (TEST, JOIN)


def entrance_gated(view):
    """Send a learner who is not yet through to the one thing they can do."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        stage = stage_for(request)
        if stage in WHERE:
            return redirect(WHERE[stage])
        return view(request, *args, **kwargs)

    return wrapper
