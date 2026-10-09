"""Two tutorials: what the role is and how to actually do it (SPR-M.57).

Avi asked for a training page for a program manager and another for a leader
— what their role is in general, and how to do it. Neither role came with an
onboarding screen before this: a leader's first visit to האזור שלי is a link
to hand out and, eventually, a queue, with nothing that says what the queue
*is* or what happens after somebody joins. A program manager's ניהול door is
eight tools with no sentence connecting them to the job.

**Every link on both pages is a real `{% url %}` to a screen that already
exists and already enforces its own guard.** This file explains the product;
it does not add a second copy of any rule in it. If a link here is wrong,
Django raises `NoReverseMatch` at render time and the page 500s rather than
quietly pointing nowhere — which is the same contract `_newfeature.html` and
every other cross-reference in this codebase relies on.

**Read-only, like the SPR-M.53 reports.** A tutorial that could also change
something is a tutorial somebody is afraid to open.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .access import candidate_of, is_program_manager, leader_of
from .views import shell

LOGIN_URL = "/matazim/login/"


@login_required(login_url=LOGIN_URL)
def leader_guide(request):
    """REQ-M.157 — what a leader is, and how the screens work.

    Same gate as `leader_home` (REQ-M.73, SPR-M.44): an approved leader opens
    it, a candidate still waiting is sent to ההרשאה שלי rather than refused
    outright, and everyone else is turned away. A tutorial for a role is not
    a preview of the role for somebody who does not hold it yet.
    """
    if leader_of(request.user) is None:
        if candidate_of(request.user):
            return redirect("matazim:leader_entrance")
        raise PermissionDenied
    return render(request, "matazim/guide_leader.html", shell(request, "leader"))


@login_required(login_url=LOGIN_URL)
def staff_guide(request):
    """REQ-M.157 — what a program manager is, and how the screens work.

    Same gate as every PM screen since SPR-M.53 made the role sufficient for
    reading the whole programme. Root reads it too (root is always also a
    program manager, REQ-M.88), which is correct: it is accurate about root's
    own tools as well.
    """
    if not is_program_manager(request.user):
        raise PermissionDenied
    return render(request, "matazim/guide_pm.html", shell(request, "staff"))
