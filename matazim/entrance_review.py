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


def is_model(name):
    """True for a file the measuring script can read (an STL)."""
    return str(name or "").lower().endswith(".stl")


def attempt_state(attempt):
    """waiting, approved, returned, or retry (the script found something to fix).

    REQ-M.205 (Naomi, 2026-10-26): "אפשר להעלות כל קובץ כהגשה, גם אם ירצו לעלות
    תמונה". A file that is not an STL is not measured at all, so there is nothing
    for the script to send back: it goes to a person, and is waiting.
    """
    if attempt.decision == EntranceAttempt.APPROVED:
        return EntranceAttempt.APPROVED
    if attempt.decision == EntranceAttempt.RETURNED:
        return EntranceAttempt.RETURNED
    if attempt.passed:
        return EntranceAttempt.WAITING
    if attempt.model_file and not is_model(attempt.model_file.name):
        return EntranceAttempt.WAITING
    return RETRY


def latest_submitted(member):
    return (
        EntranceAttempt.objects.filter(member=member, submitted_at__isnull=False)
        .order_by("-number")
        .first()
    )


PATROL_TEXT = "עברת את מבחני המיון לתכנית מטצים ונכנסת לסיירת. ברוכים הבאים."


def approve(attempt, by, *, tell=True):
    """The team says yes: the attempt is approved and the member is through.

    `tell=False` is the leader's path (REQ-M.209): the leader chooses whether
    the student is told, and with which words (`tell_patrol`).
    """
    attempt.decision = EntranceAttempt.APPROVED
    attempt.decided_by = by
    attempt.decided_at = timezone.now()
    attempt.decision_note = ""
    attempt.save(update_fields=["decision", "decided_by", "decided_at", "decision_note"])

    member = attempt.member
    if member.entrance_test_passed_at is None:
        member.entrance_test_passed_at = timezone.now()
        member.save(update_fields=["entrance_test_passed_at", "updated_at"])

    if not tell:
        return attempt
    notify(
        member.user,
        Notification.ENTRANCE_APPROVED,
        "מבחן הכניסה אושר. ברוכים הבאים.",
        url="/matazim/path/",
        actor=by,
    )
    return attempt


GOOD_LUCK_TEXT = "הפעם לא עברת את מבחן המיון לתכנית מטצים. אנחנו מאחלים לך המון הצלחה."


def return_attempt(attempt, by, note, *, good_luck=False):
    """The team asks for another go, and says what to change. Refuses an empty note.

    `good_luck` is the leader's other message (REQ-M.211): the student did not
    pass, and hears it with a wish instead of "back for fixing". Then the note
    may be empty, since the message itself is the words.
    """
    note = (note or "").strip()
    if good_luck:
        note = note or GOOD_LUCK_TEXT
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
    if good_luck:
        tell_good_luck(attempt.member, by)
        return attempt
    notify(
        attempt.member.user,
        Notification.ENTRANCE_RETURNED,
        "מבחן הכניסה הוחזר לתיקון. יש הערה בשבילכם.",
        url="/matazim/test/task/",
        actor=by,
    )
    return attempt


def tell_patrol(member, by):
    """REQ-M.209 - the student hears they passed the screening and entered the patrol.

    Lital, 2026-10-31: "שיישלח לתלמיד הודעה שעבר את מבחני המיון לתכנית מטצים ונכנס
    לסיירת", and it is the leader's option. A bell and a mail, like every other
    entrance decision. No names in it: the mail rule of `notify._mail`.
    """
    return notify(member.user, Notification.ENTRANCE_APPROVED, PATROL_TEXT, url="/matazim/", actor=by)


def tell_good_luck(member, by):
    """REQ-M.211 - the student hears they did not pass, with a wish of good luck.

    Lital, 2026-10-31: "אופציה לשלוח הודעה לתלמיד שלא עבר את מבחן המיון ונאחל לו
    המון בהצלחה". A bell and a mail, no names in it, like `tell_patrol`. It links
    to the test page, where the leader's note is and another go is open.
    """
    return notify(member.user, Notification.ENTRANCE_RETURNED, GOOD_LUCK_TEXT, url="/matazim/test/task/", actor=by)


def take_into_group(member, leader, by):
    """REQ-M.209 - after the test, the leader puts the student in their own group.

    Lital, 2026-10-31: "שיהיה למוביל אופציה לאחר שראה את מבחן המיון להכניס את
    התלמיד לקבוצה של המוביל". C14 made joining the student's own act; this adds
    the leader's door beside it and closes none. Returns the `Student`, or raises
    ValueError with the reason a screen prints:

    - `passed`: the test is not approved yet, so there is nothing to join (C10).
    - `consent`: a minor without a guardian's consent; their data reaches a
      leader only after it (REQ-M.84), so they join when it is given.
    - `out`: taken out of the programme (REQ-M.203); bringing back is the team's.
    - `other`: already another leader's student; moving is not this leader's act.
    """
    from .consent import needs_guardian_consent
    from .history import record_arrival, set_status
    from .models import Student

    if not member.has_passed_entrance_test():
        raise ValueError("passed")
    student = Student.objects.filter(user=member.user).order_by("-cohort_year").first()
    if student is not None and student.leader_id == leader.pk:
        return student
    if student is not None and student.status in (Student.REJECTED, Student.REVOKED):
        raise ValueError("out")
    if student is not None and student.leader_id:
        raise ValueError("other")
    if needs_guardian_consent(member):
        raise ValueError("consent")

    note = "הוכנס/ה לסיירת על ידי המוביל/ה, אחרי מבחן המיון"
    if student is None:
        student = Student.objects.create(user=member.user, leader=leader, status=Student.IN_TRAINING)
        record_arrival(student, by=by, note=note)
    else:
        student.leader = leader
        student.pending_leader = None
        student.save(update_fields=["leader", "pending_leader", "updated_at"])
        set_status(student, Student.IN_TRAINING, by=by, note=note)
    return student