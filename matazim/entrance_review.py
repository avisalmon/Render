"""REQ-M.182, REQ-M.183 - a person approves the entrance product.

Atid's schedule says the entrance test is "a digital TinkerCAD test and the
presentation of a product for acceptance to the programme", and the kickoff mail
says the products go to שקד and to Avi "לאישור". Until 2026-10-15 the script's
measurement was the whole decision: a passing STL set
`MemberProfile.entrance_test_passed_at` the moment it was uploaded.

Now the script's measurement is advice shown to the reviewer, and the flag is set
by a program manager's approval, which is the only thing that sets it. Everything
downstream (the joining door, certification condition one, the overview) already
asked that flag and did not change.

**A return carries words** (the rule of REQ-M.123): "returned" with nothing
beside it tells a fourteen-year-old they failed and not what to change.

**The script can still be overruled in both directions.** A person may approve an
attempt the measurement failed (a good object the checker mis-measured) and may
return one it passed.
"""

from django.utils import timezone

from .models import EntranceAttempt, Notification
from .notify import notify

RETRY = "retry"  # the measurement did not pass: the member has not been through yet


def attempt_state(attempt):
    """waiting, approved, returned, or retry (the script found something to fix)."""
    if attempt.decision == EntranceAttempt.APPROVED:
        return EntranceAttempt.APPROVED
    if attempt.decision == EntranceAttempt.RETURNED:
        return EntranceAttempt.RETURNED
    return EntranceAttempt.WAITING if attempt.passed else RETRY


def latest_submitted(member):
    return (
        EntranceAttempt.objects.filter(member=member, submitted_at__isnull=False)
        .order_by("-number")
        .first()
    )


def approve(attempt, by):
    """The team says yes: the attempt is approved and the member is through."""
    attempt.decision = EntranceAttempt.APPROVED
    attempt.decided_by = by
    attempt.decided_at = timezone.now()
    attempt.decision_note = ""
    attempt.save(update_fields=["decision", "decided_by", "decided_at", "decision_note"])

    member = attempt.member
    if member.entrance_test_passed_at is None:
        member.entrance_test_passed_at = timezone.now()
        member.save(update_fields=["entrance_test_passed_at", "updated_at"])

    notify(
        member.user,
        Notification.ENTRANCE_APPROVED,
        "מבחן הכניסה אושר. ברוכים הבאים.",
        url="/matazim/path/",
        actor=by,
    )
    return attempt


def return_attempt(attempt, by, note):
    """The team asks for another go, and says what to change. Refuses an empty note."""
    note = (note or "").strip()
    if not note:
        raise ValueError("a return needs words")

    attempt.decision = EntranceAttempt.RETURNED
    attempt.decided_by = by
    attempt.decided_at = timezone.now()
    attempt.decision_note = note
    attempt.save(update_fields=["decision", "decided_by", "decided_at", "decision_note"])

    # A returned attempt is not a pass, whatever an earlier approval did: if this
    # member had been approved on a previous attempt, that approval stands, so the
    # flag is left alone here. Un-passing someone is a different act.
    notify(
        attempt.member.user,
        Notification.ENTRANCE_RETURNED,
        "מבחן הכניסה הוחזר לתיקון. יש הערה בשבילכם.",
        url="/matazim/test/task/",
        actor=by,
    )
    return attempt
