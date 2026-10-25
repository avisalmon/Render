"""Every school, and how every מטצ in it is getting on (SPR-M.72).

Lital, by mail, 2026-10-25 18:24: "אני רוצה לראות מבט על של כל בתי הספר כל
ההתקדמות של התלמידים". The cohort page counted per school and stopped at two
numbers; the roster names every student but school by school only through a
search box. This is the one page that answers her question from above: each
school, its leaders, how many are at each stage, and each student's line.

**Read only, and read through the scope functions.** Students come from
`access.visible_students`, so a program manager reads her world and root reads
everybody, exactly as on every other screen (REQ-M.88). Nothing here writes.

**Which school a student is in.** The class they sit in first, because that is
where they actually are; then the school they chose when they signed up
(REQ-M.195); then their leader's school. Somebody with none of the three is
counted under a named bucket rather than dropped.

**People who signed up and have not started.** Before the entrance test is
approved nobody has a `Student` row, so a page built only on students reads
zero at every school at the start of the year. They are counted per school by
the school they chose, as a number and never as names: the names of teenagers
who are nobody's yet are not this page's to print.

**Fixed query count.** Progress for every student is read in one pass through
`progress.cohort_progress`, so the page does not grow a query per teenager.
"""

from django.db.models import Count

from .access import visible_leaders, visible_students
from .content import REQUIRED_COURSE_SLUGS

NO_SCHOOL = "לא צוין בית ספר"

# The public stages in programme order, the same words the cohort page uses.
STAGES = [
    ("applied", "מתמיינים"),
    ("in_training", "לומדים"),
    ("project_submitted", "יוצרים"),
    ("certified", "מדריכים"),
    ("alumnus", "משפיעים"),
]
STAGE_LABELS = dict(STAGES)


def _name(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "display_name", "") or user.email or user.username


def _school_of(student):
    """Class first, then the school they chose, then their leader's."""
    if student.school_names:
        return student.school_names[0]
    profile = getattr(student.user, "matazim_profile", None)
    if profile is not None and profile.school_id:
        return profile.school.name
    if student.leader_id and student.leader.school_names:
        return student.leader.school_names[0]
    return NO_SCHOOL


def _not_started_by_school():
    """Signed up from a school, no `Student` row yet, and not staff: a count."""
    from .models import Institution, MemberProfile

    # Without the filter an institution with no managers puts a NULL in the
    # list, and NOT IN (..., NULL) quietly matches nobody at all.
    managers = Institution.objects.filter(managers__isnull=False).values("managers")
    rows = (
        MemberProfile.objects.filter(school__isnull=False, user__matazim_student__isnull=True,
                                     user__matazim_leader__isnull=True, user__is_superuser=False)
        .exclude(user__in=managers)
        .values("school__name")
        .annotate(n=Count("id"))
    )
    return {row["school__name"]: row["n"] for row in rows}


def school_rows(user):
    """One row per school this person may see, each with its students."""
    from .models import School, Student
    from .progress import cohort_progress, track_summary

    students = list(
        visible_students(user)
        .exclude(status__in=(Student.REJECTED, Student.REVOKED))
        .select_related("user", "user__profile", "user__matazim_profile__school",
                        "leader__user", "leader__user__profile")
        .prefetch_related("classes", "leader__classes")
    )
    progress = cohort_progress(students, REQUIRED_COURSE_SLUGS)

    buckets = {}

    def bucket(name):
        return buckets.setdefault(name, {
            "school": name,
            "students": [],
            "leaders": set(),
            "stages": {key: 0 for key, _ in STAGES},
            "passed_test": 0,
            "finished_track": 0,
            "not_started": 0,
        })

    for student in students:
        row = bucket(_school_of(student))
        profile = getattr(student.user, "matazim_profile", None)
        passed = bool(profile and profile.has_passed_entrance_test())
        track = track_summary(progress.get(student.user_id, {}))
        row["students"].append({
            "student": student,
            "name": _name(student.user),
            "stage": STAGE_LABELS.get(student.status, ""),
            "passed_test": passed,
            "track": track,
            "leader": _name(student.leader.user) if student.leader_id else "",
        })
        if student.status in row["stages"]:
            row["stages"][student.status] += 1
        row["passed_test"] += passed
        row["finished_track"] += bool(track["total"]) and track["pct"] >= 100
        if student.leader_id:
            row["leaders"].add(_name(student.leader.user))

    # Every school a leader teaches in, and every school on the sign-up list,
    # appears even with nobody yet: an empty school is the one she needs to see.
    for leader in (visible_leaders(user).filter(is_active=True, approved_at__isnull=False)
                   .select_related("user", "user__profile").prefetch_related("classes")):
        for name in leader.school_names:
            bucket(name)["leaders"].add(_name(leader.user))
    for name in School.objects.filter(is_active=True).values_list("name", flat=True):
        bucket(name)
    for name, count in _not_started_by_school().items():
        bucket(name)["not_started"] = count

    out = []
    for row in buckets.values():
        row["students"].sort(key=lambda r: r["name"])
        row["leaders"] = sorted(row["leaders"])
        row["total"] = len(row["students"])
        row["stage_list"] = [{"label": label, "count": row["stages"][key]} for key, label in STAGES]
        done = sum(r["track"]["done"] for r in row["students"])
        total = sum(r["track"]["total"] for r in row["students"])
        row["avg_pct"] = int(done / total * 100) if total else 0
        out.append(row)
    # The named bucket last; otherwise the biggest school first.
    return sorted(out, key=lambda r: (r["school"] == NO_SCHOOL, -r["total"], r["school"]))


def totals(rows):
    """The handful of numbers for the top of the page, summed from the rows."""
    return {
        "schools": sum(1 for r in rows if r["school"] != NO_SCHOOL),
        "students": sum(r["total"] for r in rows),
        "not_started": sum(r["not_started"] for r in rows),
        "passed_test": sum(r["passed_test"] for r in rows),
        "finished_track": sum(r["finished_track"] for r in rows),
    }
