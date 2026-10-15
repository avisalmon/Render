"""REQ-M.179 - a certificate follows the leader's approval of the product.

Atid, 2026-06-25, repeated by Naomi on 2026-10-15: "הענקת תעודה מהאתר רק לאחר
הגשת התוצר למוביל." The programme treats each course's product as "an
inseparable part of the learning", so the certificate a member can press for
here waits for the product to have been put in front of their leader.

**Avi, 2026-10-15 (Q27): the hand-in must be approved by the leader.** The first
build counted a hand-in in any state. It is now the leader's approval that opens
the certificate: handed in and waiting is not enough, and neither is returned.

One decision, recorded in the spec (Q25) and one line here:

- **Only for someone who has a leader.** A member who came through the open door
  has nobody to approve, and a gate nobody can open is a broken site, not a rule.

This is the gate in מט״צים only. babook's own finish button is outside this
product and is not touched (RULE-2).
"""

from .models import Submission

NONE, WAITING, RETURNED, APPROVED = "none", "waiting", "returned", "approved"


def handin_state(student, course_slug):
    """Where this member's product for the course stands with their leader.

    The furthest it has got: approved beats waiting beats returned beats none,
    because a member who was returned and has handed in again is waiting, and one
    whose later version was approved is approved whatever the earlier ones said.
    """
    states = set(
        Submission.objects.filter(student=student, course_slug=course_slug)
        .values_list("status", flat=True)
    )
    for state in (Submission.APPROVED, Submission.WAITING, Submission.RETURNED):
        if state in states:
            return state
    return NONE


def needs_handin(student, course_slug):
    """True when this member owes the leader's approval for the course."""
    if student is None or student.leader_id is None:
        return False
    return handin_state(student, course_slug) != APPROVED
