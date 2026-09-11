"""The cohort, and the school report.

REQ-M.24, the last screen the spec names for the program manager and the one it
calls Litala's: the funnel by stage and by leader, grouped by school, with an
export.

**Every number here is counted once, from `access.visible_students`.** A funnel
is a great deal of counting, and a count computed locally rather than read from
the same place as the roster becomes a third opinion about the same teenagers,
which nobody would notice was wrong. Tenancy comes along with that for free:
the queryset is already scoped, so no figure on this page can cross a world
(REQ-M.88). Aggregates are exactly where that kind of leak hides, because a
total of eight instead of four has no name attached to make it obvious.

**The export is aggregate, and that is a decision rather than a limitation.**
Read literally, "can export it" could mean a spreadsheet of named teenagers,
which is also the version somebody asks for first. Spec §4.10 exists because
this product holds data about minors, and a CSV of their names is the one
artefact that leaves the system entirely: it lands in a download folder, gets
mailed to a colleague, and outlives every access rule we wrote. A school-level
report does not need it. Leaders are named, because they are staff and naming
them is the point of a report about who is running what.
"""

import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .access import is_program_manager, visible_leaders, visible_students
from .models import Student
from .views import shell

LOGIN_URL = "/matazim/login/"

# The five public stages, in programme order, so the funnel reads as a funnel
# rather than as whatever order the database returns.
STAGE_ORDER = [
    (Student.APPLIED, "מתמיינים"),
    (Student.IN_TRAINING, "לומדים"),
    (Student.PROJECT_SUBMITTED, "יוצרים"),
    (Student.CERTIFIED, "מדריכים"),
    (Student.ALUMNUS, "משפיעים"),
]

NO_SCHOOL = "בלי בית ספר"


def _report(user):
    """Every figure on the page, counted once from one scoped queryset.

    Returns plain dictionaries rather than querysets so the template and the CSV
    render exactly the same numbers. Two readers over one result, not two
    queries that could drift.
    """
    students = visible_students(user)
    total = students.count()

    # The funnel. Counted in one grouped query rather than five.
    counted = dict(
        students.values_list("status").annotate(n=Count("id")).values_list("status", "n")
    )
    funnel = [
        {"key": key, "label": label, "count": counted.get(key, 0)} for key, label in STAGE_ORDER
    ]

    # By leader. Built from the *leaders* and not by grouping students, because
    # a leader with nobody is the one a program manager most needs to see, and
    # grouping students would drop them entirely.
    per_leader = dict(
        students.exclude(leader__isnull=True)
        .values_list("leader_id")
        .annotate(n=Count("id"))
        .values_list("leader_id", "n")
    )
    certified_per_leader = dict(
        students.filter(status=Student.CERTIFIED)
        .exclude(leader__isnull=True)
        .values_list("leader_id")
        .annotate(n=Count("id"))
        .values_list("leader_id", "n")
    )
    by_leader = [
        {
            "leader": leader,
            "name": _name(leader.user),
            "schools": leader.school_names,
            "total": per_leader.get(leader.pk, 0),
            "certified": certified_per_leader.get(leader.pk, 0),
        }
        for leader in visible_leaders(user)
        .filter(approved_at__isnull=False)
        .select_related("user", "user__profile")
        .prefetch_related("classes")
    ]

    # By school, which is what Litala's brief actually asks for. School lives on
    # the class, a class is offered and never required (Q14), so anybody in none
    # is counted under a named bucket rather than dropped. A school report that
    # silently undercounts is worse than one that admits an unfiled group.
    buckets = {}
    rows = students.values_list("id", "status", "classes__school_name")
    seen = {}
    for student_id, status, school in rows:
        # A student in two classes appears twice; count them once, under the
        # first school named, so the totals still add up to the funnel.
        if student_id in seen:
            continue
        seen[student_id] = True
        key = school or NO_SCHOOL
        bucket = buckets.setdefault(key, {"school": key, "total": 0, "certified": 0})
        bucket["total"] += 1
        if status == Student.CERTIFIED:
            bucket["certified"] += 1
    by_school = sorted(buckets.values(), key=lambda b: (-b["total"], b["school"]))

    return {
        "funnel": funnel,
        "funnel_total": total,
        "by_leader": sorted(by_leader, key=lambda r: -r["total"]),
        "by_school": by_school,
    }


def _name(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "display_name", "") or user.email or user.username


def _manager_or_403(request):
    if not is_program_manager(request.user):
        raise PermissionDenied
    return request.user


@login_required(login_url=LOGIN_URL)
def cohort(request):
    """REQ-M.24 — the programme's shape, in her world."""
    _manager_or_403(request)
    return render(
        request,
        "matazim/cohort.html",
        shell(request, "staff", **_report(request.user)),
    )


@login_required(login_url=LOGIN_URL)
def cohort_export(request):
    """REQ-M.24 — the same report, as a file, naming no minor (§4.10).

    UTF-8 with a BOM because the likeliest destination is Excel on Windows, and
    without it every Hebrew heading arrives as mojibake. A report nobody can
    read is not a report.
    """
    _manager_or_403(request)
    data = _report(request.user)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.now().strftime("%Y-%m-%d")
    response["Content-Disposition"] = f'attachment; filename="matazim-cohort-{stamp}.csv"'
    response.write("﻿")

    writer = csv.writer(response)
    writer.writerow(["דוח מט״צים", stamp])
    writer.writerow([])

    writer.writerow(["שלב", "כמה"])
    for row in data["funnel"]:
        writer.writerow([row["label"], row["count"]])
    writer.writerow(["סך הכול", data["funnel_total"]])
    writer.writerow([])

    writer.writerow(["מוביל/ה", "בתי ספר", "מט״צים", "מתוכם מוסמכים"])
    for row in data["by_leader"]:
        writer.writerow([row["name"], " · ".join(row["schools"]), row["total"], row["certified"]])
    writer.writerow([])

    writer.writerow(["בית ספר", "מט״צים", "מתוכם מוסמכים"])
    for row in data["by_school"]:
        writer.writerow([row["school"], row["total"], row["certified"]])

    return response
