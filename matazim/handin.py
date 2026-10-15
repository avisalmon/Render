"""REQ-M.179 — a certificate follows the hand-in.

Atid, 2026-06-25, repeated by Naomi on 2026-10-15: "הענקת תעודה מהאתר רק לאחר
הגשת התוצר למוביל." The programme treats each course's product as "an
inseparable part of the learning", so the certificate a member can press for
here waits for the product to have been put in front of their leader.

Two decisions, both recorded in the spec (Q25, Q27) and both one line here:

- **Handed in, not approved.** The leader's approval stays their own decision on
  top of the hand-in. A returned hand-in still counts, because the leader has
  seen it and said something about it; what the gate measures is that the work
  reached a person.
- **Only for someone who has a leader.** A member who came through the open door
  has nobody to hand to, and a gate nobody can open is a broken site, not a rule.

This is the gate in מט״צים only. babook's own finish button is outside this
product and is not touched (RULE-2).
"""

from .models import Submission


def needs_handin(student, course_slug):
    """True when this member owes a hand-in for the course and has not made one."""
    if student is None or student.leader_id is None:
        return False
    return not Submission.objects.filter(student=student, course_slug=course_slug).exists()
