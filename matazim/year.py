"""REQ-M.180, REQ-M.186, REQ-M.187 - the year, and where the programme is in it.

Atid's schedule for תשפ״ז is data (`ProgramMilestone`); this module is what
reads it. Two questions every screen that mentions the year asks, so they are
answered once here and not once per template:

- *Where is the programme today?* `where_are_we`: the milestones under way, and
  the next one to come.
- *How many students does a school have, against the patrol of ten?*
  `patrol_by_school`.

**The patrol is a target, never a cap** (REQ-M.187). Atid asks for "a patrol of
about ten", and "about" is the word. An eleventh student is not refused, because
a rule that turns a keen fourteen-year-old away to keep a number tidy is not
what a programme about leadership wants; the count is there so a leader and the
program manager can see how far from ten a school is while the 15 November
deadline is still ahead.
"""

from django.utils import timezone

PATROL_TARGET = 10


def today():
    return timezone.localdate()


def where_are_we(milestones, on=None):
    """(under way, next) for a list of milestones, as of `on` (default today).

    *Under way* is every milestone whose dates include today, in the client's
    order: in late November the programme is recruiting and learning at once,
    and saying only one of them would be a lie of omission. *Next* is the
    earliest milestone that has not started.
    """
    on = on or today()
    rows = list(milestones)
    under_way = [m for m in rows if m.starts_on <= on <= m.last_day]
    ahead = sorted((m for m in rows if m.starts_on > on), key=lambda m: (m.starts_on, m.order))
    return under_way, (ahead[0] if ahead else None)


def days_until(day, on=None):
    return (day - (on or today())).days


def recruiting_deadline(milestones):
    """The day the patrol has to be chosen by, from the recruiting milestone."""
    for m in milestones:
        if m.stage == "recruiting" and m.ends_on:
            return m.ends_on
    return None


def patrol_by_school(students):
    """Students counted per school against the target, most-short first.

    `students` is a queryset the caller already scoped (`visible_students`), so
    this never decides who may see whom (§4.4). Someone with no class falls back
    to the schools their leader teaches in, and someone with neither is counted
    under an empty name, which the screen prints as "לא צוין בית ספר" rather
    than dropping a person from the count.

    A student who was rejected or whose standing was revoked is not part of a
    patrol.
    """
    from .models import Student

    counted = students.exclude(status__in=(Student.REJECTED, Student.REVOKED)).filter(
        leader__isnull=False
    ).prefetch_related("classes", "leader__classes")

    by_school = {}
    for student in counted:
        names = student.school_names or student.leader.school_names or [""]
        for name in names:
            by_school[name] = by_school.get(name, 0) + 1

    rows = [
        {
            "school": name,
            "count": count,
            "target": PATROL_TARGET,
            "missing": max(PATROL_TARGET - count, 0),
        }
        for name, count in by_school.items()
    ]
    return sorted(rows, key=lambda r: (-r["missing"], r["school"]))


def milestone_dates_ok(starts_on, ends_on):
    """A milestone cannot end before it starts."""
    return ends_on is None or ends_on >= starts_on
