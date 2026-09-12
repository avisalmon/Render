"""What makes a מט״צ, and who is allowed to say so.

Avi, 2026-09-11. Three conditions, all of them required (REQ-M.76):

1. The entrance test is passed. Ours, and already built.
2. babook has issued a `CourseCertificate` for **both** Scratch courses.
3. The student's own leader has approved them, by hand, having taught them.

The first two are facts babook already owns. A certificate is issued by
babook's Finish button, through babook's own certification process, and a
review-gated course puts a human in front of it first. Nothing here re-derives
what a certificate means; it reads rows (RULE-3). Counting finished lessons
instead would be the subtle version of the same mistake, and would let a leader
certify someone babook has not.

The two halves deliberately pull in opposite directions, and this is the part
worth getting right.

The automatic half is **binding**. A leader cannot certify someone who has not
met it. Not discouraged, not warned: refused, here on the server, whatever the
page happened to render (REQ-M.77). A button that is only hidden is a button
that gets posted anyway.

The human half is **the decision**. Meeting the prerequisites earns a student
the right to be considered and never the status itself, and nothing in this
file promotes anyone because a count reached two (REQ-M.78).

Note that this is the exact inverse of the entrance test, where the machine's
check is advice and there is no machine rejection, only "not yet". Here the
machine only ever refuses, and only a person can grant.

Eligibility is computed on every read and stored nowhere. A stored flag is a
flag that goes stale the moment a certificate is revoked, and someone would
stay eligible on paper with nothing to notice it.
"""

from dataclasses import dataclass, field

from django.utils import timezone

from app.models import CourseCertificate

from .access import is_program_manager, leader_of
from .content import REQUIRED_COURSE_SLUGS
from .history import set_status
from .models import MatazCertificate, MemberProfile, Student


@dataclass
class Eligibility:
    """Why someone can or cannot be certified, in a form a screen can explain.

    A bare boolean would leave a leader guessing, and a leader who is guessing
    asks the teenager. So this carries what is missing, not merely that
    something is.
    """

    entrance_test_passed: bool = False
    certified_courses: list = field(default_factory=list)
    missing_courses: list = field(default_factory=list)

    @property
    def courses_certified(self):
        return not self.missing_courses

    @property
    def is_eligible(self):
        """All three minus the human one: what the gate checks (REQ-M.77)."""
        return self.entrance_test_passed and self.courses_certified

    @property
    def missing(self):
        """Everything outstanding, in the order a student would do it."""
        out = []
        if not self.entrance_test_passed:
            out.append("entrance_test")
        out.extend(self.missing_courses)
        return out


def eligibility(student):
    """The two automatic conditions, read fresh (REQ-M.76)."""
    profile = MemberProfile.objects.filter(user=student.user_id).first()
    held = set(
        CourseCertificate.objects.filter(
            user_id=student.user_id, course__slug__in=REQUIRED_COURSE_SLUGS
        ).values_list("course__slug", flat=True)
    )
    return Eligibility(
        entrance_test_passed=bool(profile and profile.has_passed_entrance_test()),
        certified_courses=[s for s in REQUIRED_COURSE_SLUGS if s in held],
        missing_courses=[s for s in REQUIRED_COURSE_SLUGS if s not in held],
    )


def eligibility_for_many(students):
    """The same answer for a whole roster, without a query per teenager.

    Same motivation as `progress.cohort_progress`, and the same shape of fix.
    """
    students = list(students)
    if not students:
        return {}

    user_ids = [s.user_id for s in students]
    passed = set(
        MemberProfile.objects.filter(
            user_id__in=user_ids, entrance_test_passed_at__isnull=False
        ).values_list("user_id", flat=True)
    )
    held = {}
    rows = CourseCertificate.objects.filter(
        user_id__in=user_ids, course__slug__in=REQUIRED_COURSE_SLUGS
    ).values_list("user_id", "course__slug")
    for uid, slug in rows:
        held.setdefault(uid, set()).add(slug)

    out = {}
    for s in students:
        mine = held.get(s.user_id, set())
        out[s.user_id] = Eligibility(
            entrance_test_passed=s.user_id in passed,
            certified_courses=[x for x in REQUIRED_COURSE_SLUGS if x in mine],
            missing_courses=[x for x in REQUIRED_COURSE_SLUGS if x not in mine],
        )
    return out


def may_certify(user, student):
    """Is this person allowed to decide about this student at all?

    Their own leader, or an admin. An admin is included on purpose: they see
    everyone (REQ-M.22), and a student whose leader is away should not be stuck
    at the last step of a year's work.

    This answers *who*, never *whether*. `eligibility` answers whether, and
    `certify` insists on both.
    """
    if is_program_manager(user):
        return True
    leader = leader_of(user)
    return bool(leader and student.leader_id == leader.pk)


def certify(user, student):
    """Grant it. Returns True if the status changed.

    Refuses here rather than in a template, because the template is not what
    receives the POST (REQ-M.77).
    """
    if not may_certify(user, student):
        raise PermissionError("not this person's student")
    if not eligibility(student).is_eligible:
        # REQ-M.77 — the gate is a gate. The caller turns this into a message;
        # what matters is that no path through the app can get past it.
        return False

    student.certified_at = timezone.now()
    student.certified_by = user
    # REQ-M.21 — through the one door, so the transition and its record are a
    # single write. The certified_* columns ride along in the same save.
    set_status(
        student,
        Student.CERTIFIED,
        by=user,
        note="הסמכה",
        extra_fields=("certified_at", "certified_by"),
    )
    _issue_certificate(student, user)
    return True


def _display_name(user):
    """Whatever a person is actually called, read from the database."""
    from app.models import UserProfile

    if user is None:
        return ""
    name = UserProfile.objects.filter(user=user).values_list("display_name", flat=True).first()
    return (name or "").strip() or (user.email or user.username or "")


def _issue_certificate(student, by):
    """REQ-M.20 — certifying produces one, and re-certifying revives it.

    The same row and the same `public_id` come back rather than a new
    certificate being issued, because printed copies carry that id and reissuing
    would invalidate paper that is still perfectly true.

    The name is captured here rather than read at display time: a certificate
    says who it was awarded to on the day.
    """
    # Queried rather than read off `user.profile`. babook creates a blank
    # UserProfile in a post_save signal, so an in-memory User can carry a cached
    # profile with an empty name while the row has the real one, and the
    # certificate would be issued to an email address. The same signal caused a
    # silently dropped display_name once before.
    name = _display_name(student.user)
    awarder = _display_name(by)

    certificate, created = MatazCertificate.objects.get_or_create(
        student=student,
        defaults={
            "name_on_certificate": name,
            "awarded_by_name": awarder,
            "awarded_at": student.certified_at or timezone.now(),
        },
    )
    if not created and certificate.revoked_at is not None:
        certificate.revoked_at = None
        certificate.save(update_fields=["revoked_at"])
    return certificate


def revoke(user, student):
    """Take it back. Granted by hand means revocable by hand (REQ-M.78).

    Drops back to לומדים rather than to מתמיינים: they have not un-passed the
    entrance test, and sending someone back to the selection stage would say
    they had.
    """
    if not may_certify(user, student):
        raise PermissionError("not this person's student")

    student.certified_at = None
    student.certified_by = None
    set_status(
        student,
        Student.IN_TRAINING,
        by=user,
        note="ביטול הסמכה",
        extra_fields=("certified_at", "certified_by"),
    )
    # REQ-M.78, REQ-M.20 — the certificate is invalidated, never deleted. A
    # printed copy is out there carrying this id, and somebody checking it
    # deserves "withdrawn" rather than "not found", which would let a revoked
    # certificate pass as merely unverifiable.
    MatazCertificate.objects.filter(student=student, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return True
