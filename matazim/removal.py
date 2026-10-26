"""REQ-M.203 - taking a student out of the programme, and bringing them back.

Lital, 2026-10-26: "מבקשת לוודא שכל מוביל יכול וגם ליטל ונעמי שיש להן הרשאה יכולות
להוציא תלמידים שנרשמו ולהסיר אותן". Naomi the same morning: leaders should be able
"לאשר או למחוק תלמיד".

Nothing is deleted. `StudentViewSet` has refused delete since SPR-M.9 with the
sentence this module puts on a screen: leaving the programme is a change of status,
kept with who decided and when. Deleting a teenager's account is a different act
(their own, through babook's account deletion, or Avi's), and no button here does it.

What removing does, in one write and one line of history:

- the status becomes ``revoked`` (הוסר), which the school overview and the year's
  counts already leave out;
- the student leaves their leader, any request they had waiting, and the leader's
  classes, so they are off that leader's list at once;
- the line in the history keeps the leader they had, so bringing them back puts
  them back where they were.

A leader may remove their own students. A program manager may remove and bring back
anyone in their world. Bringing back is the program manager's, because once a
student has left a leader that leader no longer sees them.
"""

from .history import set_status
from .models import StatusLog, Student


def remove_student(student, *, by, note=""):
    """Out of the programme, nothing deleted. Returns the history line, or None."""
    if student.status == Student.REVOKED:
        return None

    previous_leader = student.leader
    student.leader = None
    student.pending_leader = None
    line = set_status(
        student,
        Student.REVOKED,
        by=by,
        note=((note or "").strip() or "הוצאה מהתוכנית")[:200],
        extra_fields=("leader", "pending_leader"),
        from_leader=previous_leader,
    )
    if previous_leader is not None:
        student.classes.remove(*student.classes.filter(leader=previous_leader))
    return line


def restore_student(student, *, by):
    """Back to the stage and the leader they had before they were removed."""
    if student.status != Student.REVOKED:
        return None

    last = (
        StatusLog.objects.filter(student=student, to_status=Student.REVOKED)
        .select_related("from_leader")
        .order_by("-at", "-pk")
        .first()
    )
    back_to = (last.from_status if last else "") or Student.APPLIED
    if back_to == Student.REVOKED:
        back_to = Student.APPLIED

    leader = last.from_leader if last else None
    if leader is not None and leader.approved_at is None:
        leader = None
    if leader is not None and student.leader_id is None:
        student.leader = leader
        student.save(update_fields=["leader", "updated_at"])

    return set_status(student, back_to, by=by, note="החזרה לתוכנית")
