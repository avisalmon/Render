"""REQ-M.186 - the year's schedule: read by everybody, written by the program manager.

Atid's schedule for תשפ״ז is rows (`ProgramMilestone`). This module is the
screen the program manager edits them on, and `year_context`, the one place a
page asks where the programme is today.
"""

import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import institution_of, is_program_manager, visible_milestones
from .models import ProgramMilestone
from .views import shell
from .year import days_until, milestone_dates_ok, recruiting_deadline, where_are_we

LOGIN_URL = "/matazim/login/"


def year_context(user):
    """What a page needs to say where the programme is: one call, one query."""
    rows = list(visible_milestones(user))
    under_way, upcoming = where_are_we(rows)
    return {
        "milestones": rows,
        "under_way": under_way,
        "next_milestone": upcoming,
        "days_to_next": days_until(upcoming.starts_on) if upcoming else None,
        "recruiting_deadline": recruiting_deadline(rows),
    }


def _date(raw):
    try:
        return datetime.date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def _read_form(post):
    """(fields, error). A row is refused whole rather than saved half-written."""
    title = (post.get("title") or "").strip()
    when_text = (post.get("when_text") or "").strip()
    starts_on = _date(post.get("starts_on"))
    ends_on = _date(post.get("ends_on")) if (post.get("ends_on") or "").strip() else None
    stage = post.get("stage") or ""

    if not title:
        return None, "צריך שם לשלב."
    if not when_text:
        return None, "צריך לכתוב את התאריך כפי שיוצג."
    if starts_on is None:
        return None, "צריך תאריך התחלה."
    if (post.get("ends_on") or "").strip() and ends_on is None:
        return None, "תאריך הסיום לא תקין."
    if not milestone_dates_ok(starts_on, ends_on):
        return None, "אבן דרך לא יכולה להסתיים לפני שהתחילה."
    if stage not in dict(ProgramMilestone.STAGE_CHOICES):
        return None, "בחרו שלב."

    try:
        order = int(post.get("order") or 0)
    except ValueError:
        order = 0
    return {
        "title": title[:120],
        "when_text": when_text[:80],
        "starts_on": starts_on,
        "ends_on": ends_on,
        "stage": stage,
        "activities": (post.get("activities") or "").strip(),
        "is_peak_day": post.get("is_peak_day") == "on",
        "order": order,
    }, ""


@login_required(login_url=LOGIN_URL)
def staff_milestones(request):
    """REQ-M.186 - the schedule as rows: see them, add one."""
    if not is_program_manager(request.user):
        raise PermissionDenied

    error = ""
    if request.method == "POST":
        fields, error = _read_form(request.POST)
        if fields is not None:
            institution = institution_of(request.user)
            if institution is None:
                raise PermissionDenied
            if not fields["order"]:
                last = visible_milestones(request.user).order_by("-order").first()
                fields["order"] = (last.order if last else 0) + 1
            ProgramMilestone.objects.create(institution=institution, **fields)
            return redirect("matazim:staff_milestones")

    return render(
        request,
        "matazim/staff_milestones.html",
        shell(
            request,
            "staff",
            rows=list(visible_milestones(request.user)),
            stages=ProgramMilestone.STAGE_CHOICES,
            error=error,
            posted=request.POST if request.method == "POST" else None,
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def edit_milestone(request, milestone_id):
    if not is_program_manager(request.user):
        raise PermissionDenied
    row = get_object_or_404(visible_milestones(request.user), pk=milestone_id)
    fields, error = _read_form(request.POST)
    if fields is None:
        return render(
            request,
            "matazim/staff_milestones.html",
            shell(
                request, "staff",
                rows=list(visible_milestones(request.user)),
                stages=ProgramMilestone.STAGE_CHOICES,
                error=error, posted=None,
            ),
            status=400,
        )
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()
    return redirect("matazim:staff_milestones")


@require_POST
@login_required(login_url=LOGIN_URL)
def delete_milestone(request, milestone_id):
    if not is_program_manager(request.user):
        raise PermissionDenied
    get_object_or_404(visible_milestones(request.user), pk=milestone_id).delete()
    return redirect("matazim:staff_milestones")
