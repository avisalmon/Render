"""The two reports SPR-M.53 adds, and nothing else.

Both are read-only on purpose. Avi asked for נעמי and ליטל to *see* the
programme; the screens that change it already exist and already have their own
guards. A report that also edits is a report somebody is afraid to open.

The guard is `access.is_program_manager`, which is true for root as well, so one
test covers both and neither screen has its own idea of who staff are.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .access import is_program_manager
from .overview import course_rows, leader_rows, programme_counts
from .views import shell

LOGIN_URL = "/matazim/login/"


def _staff_or_403(request):
    """One door for both reports.

    `PermissionDenied` rather than a redirect: somebody who reached this URL
    without the role did not mistype their way here, and bouncing them to a
    login screen they are already past reads as a fault.
    """
    if not is_program_manager(request.user):
        raise PermissionDenied
    return request.user


@login_required(login_url=LOGIN_URL)
def staff_courses(request):
    """REQ-M.148 — every הדרכה babook publishes, and what it is to us.

    The whole catalogue, not the offered pool. Root already has a screen for
    *setting* the pool (`learn_views.staff_offered`); this one is for looking,
    and it is the first time a program manager can see the catalogue at all.
    """
    _staff_or_403(request)
    rows = course_rows(request.user)
    return render(
        request,
        "matazim/staff_courses.html",
        shell(
            request,
            "allcourses",
            rows=rows,
            # Counted here rather than in the template, where `{% if %}` over a
            # list of two hundred courses is a loop nobody can see.
            offered=sum(1 for r in rows if r["offered"]),
            withdrawn=sum(1 for r in rows if r["withdrawn"]),
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_people(request):
    """REQ-M.149 — every מוביל, how far through the training, and the test.

    Separate from `staff_leaders` and `pm_leaders`, which are the screens that
    appoint, approve, deactivate and move people. This one answers "how is
    everybody doing" without a single button that changes anything, which is
    what makes it safe to leave open on a laptop in a meeting.
    """
    _staff_or_403(request)
    rows = leader_rows(request.user)
    return render(
        request,
        "matazim/staff_people.html",
        shell(
            request,
            "people",
            rows=[r for r in rows if not r["is_candidate"]],
            candidates=[r for r in rows if r["is_candidate"]],
            counts=programme_counts(request.user),
        ),
    )
