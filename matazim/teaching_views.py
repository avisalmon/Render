"""פרקטיקום: what a מט״צ actually taught.

REQ-M.32. The stage the whole programme exists to produce, and the last one
without a screen.

Two screens and one panel. A מט״צ writes down what they ran and sees their own
record; their leader reads it on the student's page, because a leader who can
approve work and certify somebody should be able to see the teaching they are
certifying; and המסלול שלי carries the count, because a total that only appears
on a page you have to remember to open is a total nobody sees.

**Counts, never names.** The children are not rows (REQ-M.29), so this records
how many were there and nothing about who. The one place that rule can be broken
is prose, so the form says so where somebody is about to type.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import visible_sessions
from .models import Student, TeachingSession
from .views import shell

LOGIN_URL = "/matazim/login/"


def summary_for(student):
    """What a member's teaching adds up to, for the panels that show a total.

    Cancelled sessions are excluded from every figure. A session that did not
    happen is worth keeping as a row and worth nothing as an hour taught.
    """
    from django.db.models import Sum

    rows = TeachingSession.objects.filter(student=student, cancelled_at__isnull=True)
    done = rows.filter(happened_on__lte=timezone.localdate())
    totals = done.aggregate(minutes=Sum("minutes"), learners=Sum("learners"))
    return {
        "sessions": done.count(),
        "minutes": totals["minutes"] or 0,
        "hours": round((totals["minutes"] or 0) / 60, 1),
        "learners": totals["learners"] or 0,
        "planned": rows.filter(happened_on__gt=timezone.localdate()).count(),
    }


def _mine(user):
    return Student.objects.filter(user=user).order_by("-cohort_year").first()


@login_required(login_url=LOGIN_URL)
def my_teaching(request):
    """REQ-M.32 — the מט״צ's own record."""
    student = _mine(request.user)
    error = ""

    if request.method == "POST" and student is not None:
        title = (request.POST.get("title") or "").strip()
        when = (request.POST.get("happened_on") or "").strip()

        happened_on = None
        if when:
            try:
                happened_on = timezone.datetime.strptime(when, "%Y-%m-%d").date()
            except ValueError:
                happened_on = None

        if not title:
            error = "צריך לכתוב מה לימדתם."
        elif happened_on is None:
            error = "צריך תאריך."
        else:
            TeachingSession.objects.create(
                student=student,
                title=title,
                happened_on=happened_on,
                minutes=_number(request.POST.get("minutes"), 45),
                learners=_number(request.POST.get("learners"), 0),
                place=(request.POST.get("place") or "").strip(),
                went_well=(request.POST.get("went_well") or "").strip(),
                was_hard=(request.POST.get("was_hard") or "").strip(),
            )
            return redirect("matazim:my_teaching")

    rows = list(visible_sessions(request.user).filter(student=student)) if student else []
    return render(
        request,
        "matazim/my_teaching.html",
        shell(
            request,
            "teaching",
            student=student,
            sessions=rows,
            totals=summary_for(student) if student else None,
            error=error,
            posted=request.POST if request.method == "POST" else None,
            today=timezone.localdate().isoformat(),
        ),
    )


def _number(raw, fallback):
    try:
        value = int((raw or "").strip())
    except (TypeError, ValueError):
        return fallback
    return max(0, min(value, 10000))


@require_POST
@login_required(login_url=LOGIN_URL)
def cancel_session(request, session_id):
    """Cancelled rather than deleted, and only by the person who wrote it.

    A session that was planned and did not happen is worth more to a leader
    than a gap in a list, so the row stays and stops counting. Deleting is not
    offered at all: this is the member's own account of their own year, and the
    thing they would actually want is to correct it, which is REQ-M.142's job
    and is not built yet.
    """
    session = get_object_or_404(
        visible_sessions(request.user), pk=session_id, student__user=request.user
    )
    if not session.is_cancelled:
        session.cancelled_at = timezone.now()
        session.save(update_fields=["cancelled_at"])
    return redirect("matazim:my_teaching")
