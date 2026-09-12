"""The one way a student's stage ever changes.

REQ-M.21. Until now five different places set `Student.status` directly, and
only one of them recorded who had done it: certification, because REQ-M.78 made
that transition's author part of the record. The other four were anonymous.

So this is the single door. `set_status` writes the field and the log together,
which is the only arrangement where the two cannot disagree. A status changed
without a log is a question nobody can answer later, and for a system holding
data about minors "we do not know who did that" is a bad sentence to have to
say to a parent.

The guard in `tests/test_spr_m_18.py` fails if any module outside this one
assigns to `.status` again, which is the same shape as the RULE-3 guard: the
rule is only real while something checks it.
"""

from .models import StatusLog, Student


def set_status(student, to_status, *, by=None, note="", extra_fields=()):
    """Move a student to a stage and record that it happened.

    `extra_fields` lets a caller save other columns in the same write, so
    certification can set `certified_at` and `certified_by` without a second
    trip and without the two rows briefly disagreeing.

    A move to the stage somebody is already on writes nothing. Otherwise every
    page refresh that happened to re-run a transition would add a line to a
    history meant to be read by a person.
    """
    previous = student.status
    if previous == to_status and not extra_fields:
        return None

    student.status = to_status
    student.save(update_fields=["status", *extra_fields, "updated_at"])

    if previous == to_status:
        return None

    return StatusLog.objects.create(
        student=student,
        from_status=previous or "",
        to_status=to_status,
        changed_by=by,
        note=note,
    )


def record_arrival(student, *, by=None, note=""):
    """The first line of a student's history, written when the row is created.

    A `Student` begins at מתמיינים by field default, which means the first
    transition has no "before" and would otherwise never be logged: their
    history would start at whatever happened second.
    """
    return StatusLog.objects.create(
        student=student,
        from_status="",
        to_status=student.status or Student.APPLIED,
        changed_by=by,
        note=note,
    )


def record_leader_change(student, to_leader, *, by=None, note=""):
    """REQ-M.98 — move a student to another leader, and say so in the timeline.

    Field and log in one place, for the same reason `set_status` exists: doing
    this by hand in Django's admin writes the field and no log, and §4.7 says
    that is the one thing which must not happen. The status is deliberately
    untouched — somebody who was לומדים under one leader is still לומדים under
    the next, and moving them is not progress or regress.

    Returns `None` when nothing moved, so a double-submitted form does not put
    two identical lines in a history meant to be read by a person.
    """
    previous = student.leader
    if previous is not None and to_leader is not None and previous.pk == to_leader.pk:
        return None

    student.leader = to_leader
    student.save(update_fields=["leader", "updated_at"])

    return StatusLog.objects.create(
        student=student,
        from_status=student.status or "",
        to_status=student.status or "",
        from_leader=previous,
        to_leader=to_leader,
        changed_by=by,
        note=note,
    )
