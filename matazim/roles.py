"""Granting and revoking the program-manager role, in one place.

REQ-M.114 says only root hands this out. REQ-M.137 says that handing it out is
itself an approval, so this module exists to make those two facts one function
rather than two screens that each remember half of it.

Avi, 2026-09-14: "If I assign a leader as a program manager, no need to wait for
me to approve it. It's approved."

Which is right, and the symptom was real: a teacher whose leader row was still
pending got made a program manager and went on being shown ההרשאה שלי, the
screen that tells a candidate they are waiting on somebody's decision. The
person they were waiting on had already decided. Worse, `leader_of()` refuses an
unapproved row, so she held the highest role in the product and simultaneously
could not reach her own students.

Nothing here creates a `Leader`. Being a program manager is not being a leader
(§4.9, §4.3), and a program manager who never taught a class should not acquire
a leader record as a side effect of being given a role. This only ends a wait
that is already over.
"""

from django.utils import timezone


def grant_program_manager(user, *, by=None, institutions=None):
    """Give somebody the role, and stop them waiting for anything.

    Returns the `Leader` row that was approved as a result, or None if there was
    nothing pending. Callers use that to say what happened, because "you are now
    a program manager" and "you are now a program manager and your teaching
    account is live" are different pieces of news.

    `institutions`, when given, is which institution(s) to make them a manager
    of. Every ordinary caller passes nothing and gets the one institution that
    exists today (`Institution.default()`, created if there is none yet).
    `handover.hand_over` is the exception: it is handing over specific
    institutions and must not also splice the successor into an unrelated
    default one, which is exactly the bug that happened the first time this
    function was reused for a handover without the parameter — the successor
    ended up managing both the institution being handed over and whichever one
    a fixture or a migration had created first, and `institution_of()` picked
    the wrong one because it reads the earliest by creation date.
    """
    from .models import Institution, Leader

    if institutions is None:
        inst = Institution.default()
        if inst is None:
            from django.conf import settings

            inst = Institution.objects.create(
                name=getattr(settings, "MATAZIM_INSTITUTION_NAME", "") or "רשת עתיד"
            )
        institutions = [inst]

    for inst in institutions:
        inst.managers.add(user)

    pending = Leader.objects.filter(user=user, approved_at__isnull=True).first()
    if pending is None:
        return None

    pending.approved_at = timezone.now()
    pending.approved_by = by
    pending.save(update_fields=["approved_at", "approved_by"])
    return pending


def revoke_program_manager(user):
    """Take the role away, and leave the leader row alone.

    Deliberately not the mirror image of `grant_program_manager`. Un-approving
    somebody's leader row because a separate role was withdrawn would cut them
    off from students they are in the middle of teaching, over a decision that
    was about something else. Approval was an act by a person (REQ-M.93) and is
    undone by a person, on the screen that is about leaders.
    """
    from .models import Institution

    for inst in Institution.objects.filter(managers=user):
        inst.managers.remove(user)
