"""The improvement loop: she asks, Avi decides, a sprint answers.

§4.11 and REQ-M.105 to M.113. Three screens and one action:

- `new_request` — the form, reached from the lamp, carrying the screen she was
  on when she pressed it.
- `my_requests` — what she asked for and what happened to it. Without this the
  whole thing is a suggestion box.
- `request_queue` — Avi's screen: every request, its assessment, and approve or
  decline in one press.

**Nothing here starts work** (REQ-M.110). Approving marks a row ready. It sends
no task, schedules nothing, and wakes nobody. A sprint happens when Avi says so
in conversation, and `tests/test_spr_m_25.py` fails if anything in this module
grows the ability to trigger it.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import is_program_manager, role_of
from .assess import assess, split_assessment
from .models import Request
from .views import shell

LOGIN_URL = "/matazim/login/"


def may_use_requests(user):
    """REQ-M.102, REQ-M.107 — the program-manager role and root, nobody else.

    Scoped to the role rather than to נעמי by name. Today that is exactly her
    and Avi because she is the only program manager, and the second institution
    then works without a rewrite.
    """
    return is_program_manager(user)


def visible_requests(user):
    """A manager sees their own, root sees all (§4.4).

    Same shape as `visible_students` and `visible_leaders`: scope as a property
    of the queryset, so no screen has to remember to filter.
    """
    if not may_use_requests(user):
        return Request.objects.none()
    if user.is_superuser:
        return Request.objects.all()
    return Request.objects.filter(author=user)


def may_decide(user):
    """REQ-M.108 — the press is Avi's.

    Not "staff": a program manager cannot approve, including their own request.
    The whole design is one human gate, and a gate everybody can open is not
    one.
    """
    return bool(getattr(user, "is_authenticated", False) and user.is_superuser)


def _entry(row):
    """One row, with its assessment split into a verdict and the reasoning."""
    verdict, reasoning = split_assessment(row.assessment)
    return {"row": row, "verdict": verdict, "reasoning": reasoning}


@login_required(login_url=LOGIN_URL)
def new_request(request):
    """REQ-M.105 — three questions, and it remembers where she was."""
    if not may_use_requests(request.user):
        raise PermissionDenied

    error = ""
    # Where she was standing when she pressed the lamp. Sent by the lamp itself
    # rather than read from the Referer header, which is missing often enough
    # to make the field unreliable exactly when it matters.
    from_screen = (request.POST.get("from_screen") or request.GET.get("from") or "").strip()[:300]

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        kind = request.POST.get("kind") or Request.IDEA
        if len(body) < 5:
            error = "כתבו משפט או שניים על מה שצריך לשנות."
        elif kind not in dict(Request.KIND_CHOICES):
            error = "בחרו סוג מהרשימה."
        else:
            row = Request.objects.create(
                author=request.user,
                author_role=role_of(request.user),
                body=body,
                kind=kind,
                from_screen=from_screen,
                # REQ-M.108 — Avi's own requests arrive approved. Asking him to
                # approve his own is a ceremony with no reader.
                status=Request.APPROVED if request.user.is_superuser else Request.NEW,
                decided_by=request.user if request.user.is_superuser else None,
                decided_at=timezone.now() if request.user.is_superuser else None,
            )
            # REQ-M.109 — advisory, and fail-open: if the model is unreachable
            # the request is already saved and the assessment stays empty.
            assess(row)
            return redirect("matazim:my_requests")

    return render(
        request,
        "matazim/request_new.html",
        shell(
            request,
            "requests",
            error=error,
            from_screen=from_screen,
            kinds=Request.KIND_CHOICES,
            posted=request.POST if request.method == "POST" else None,
        ),
    )


@login_required(login_url=LOGIN_URL)
def my_requests(request):
    """REQ-M.107, REQ-M.111 — what she asked, and what happened to it."""
    if not may_use_requests(request.user):
        raise PermissionDenied

    rows = list(visible_requests(request.user).select_related("author", "decided_by"))
    return render(
        request,
        "matazim/request_log.html",
        shell(
            request,
            "requests",
            rows=[_entry(r) for r in rows],
            waiting=sum(1 for r in rows if r.waiting_on_avi),
            can_decide=may_decide(request.user),
        ),
    )


@login_required(login_url=LOGIN_URL)
def request_queue(request):
    """REQ-M.108 — Avi's screen. Read it, read the assessment, press once."""
    if not may_decide(request.user):
        raise PermissionDenied

    rows = list(Request.objects.all().select_related("author", "decided_by"))
    groups = {
        "waiting": [r for r in rows if r.status == Request.NEW],
        "approved": [r for r in rows if r.status == Request.APPROVED],
        "done": [r for r in rows if r.status == Request.DONE],
        "declined": [r for r in rows if r.status == Request.DECLINED],
    }
    return render(
        request,
        "matazim/request_queue.html",
        shell(
            request,
            "requests",
            groups={
                name: [_entry(r) for r in group]
                for name, group in groups.items()
            },
            total=len(rows),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def decide_request(request, request_id):
    """REQ-M.108, REQ-M.110 — one press, recorded, and it starts nothing.

    Worth being explicit about what this function deliberately does not do: it
    does not queue a job, notify anybody, or schedule a sprint. It moves a row
    to approved or declined and writes who did it. The trigger for work is Avi
    in conversation, every time.
    """
    if not may_decide(request.user):
        raise PermissionDenied

    row = get_object_or_404(Request, pk=request_id)
    action = request.POST.get("action")
    if action == "approve":
        row.status = Request.APPROVED
    elif action == "decline":
        row.status = Request.DECLINED
    elif action == "assess":
        # Re-run the assessment by hand, for a row that arrived while the model
        # was unreachable.
        assess(row)
        return redirect("matazim:request_queue")
    else:
        return redirect("matazim:request_queue")

    row.decided_by = request.user
    row.decided_at = timezone.now()
    row.save(update_fields=["status", "decided_by", "decided_at"])
    return redirect("matazim:request_queue")
