"""Chapter 10 - מט״צים (Young Technology Leaders).

A selective program: 20-40 teenagers per cohort learn technology on babook, are
certified **by hand** as מובילי טכנולוגיה צעירים, and then teach groups of
younger kids from YouTube playlists.

Three laws shape everything here (spec §10.0):

1. **Status, not permission** (DEC-69). Certification unlocks nothing on babook.
   Any member can already open a class and teach. What certification does is make
   the activity *count*. So nothing in this module touches permissions.
2. **Reads learning state, never writes it** (DEC-71). Every training figure is a
   live query over Enrollment / UserVideoProgress / CourseCertificate. No model
   here stores a course, a lesson, or a progress number.
3. **Only מט״צים are tracked** (DEC-72). The children a מט״צ teaches receive
   YouTube links. They never sign up, are not members, and are not modelled. No
   field in this module holds, or can hold, a child's identity.

`Program` is deliberately generic - מט״צים is its first instance (DEC-76).
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .classroom_models import gen_join_code  # noqa: F401  (same code shape as Ch.9)


def current_year():
    """Callable default - a bare `timezone.now().year` would freeze the year at
    import time and bake it into the migration."""
    return timezone.now().year


class Program(models.Model):
    """A leadership program with its own space, branding and cohort.

    Generic on purpose: adding a second program is data, not code (DEC-76).
    """

    slug = models.SlugField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    tagline = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    # Branding lives on the record, never hardcoded in templates (REQ-10.2/10.33).
    # Defaults are the matazim.co.il palette, read from its live CSS 2026-08-08.
    # NOTE: `color_primary` fails WCAG AA on both light and indigo backgrounds
    # (~1.9:1 and ~2.6:1). It is an *accent* - fills, borders, badges, the logo.
    # Body text on light surfaces uses `color_ink`. See REQ-10.34.
    color_primary = models.CharField(max_length=9, default="#00d4a4")
    color_ink = models.CharField(max_length=9, default="#585ba8")
    color_surface = models.CharField(max_length=9, default="#e6e7f6")
    logo = models.ImageField(upload_to="program_logos/", blank=True, null=True)
    current_cohort_year = models.PositiveIntegerField(default=current_year)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # The matazim admins (Avi, Litala). **The** authority on who may open a
    # school, assign a leader, and grant the מט״צ status. Site superusers are
    # treated as staff too, matching the admin override used across Classrooms.
    # Staff are not cohort members: adults running the program never get a
    # ProgramMembership, which is reserved for the teenagers.
    staff = models.ManyToManyField(
        User, blank=True, related_name="programs_staffed", verbose_name="צוות התוכנית")

    class Meta:
        ordering = ["name"]
        verbose_name = "תוכנית"
        verbose_name_plural = "תוכניות"

    def __str__(self):
        return self.name


class School(models.Model):
    """A participating school. Referenced by memberships; scopes what a school
    leader is allowed to see (REQ-10.17)."""

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="schools")
    name = models.CharField(max_length=150)
    city = models.CharField(max_length=100, blank=True, default="")
    contact_name = models.CharField(max_length=150, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # The teachers who run this school's מט״צים. **The** single source of truth
    # for "is a school leader", and therefore for what a leader may see: their
    # scope is exactly the schools they appear in. M2M because a coordinator may
    # cover more than one school. Assigned by program staff only.
    leaders = models.ManyToManyField(
        User, blank=True, related_name="schools_led", verbose_name="מובילי בית הספר")
    # The teacher's own door into the program (Avi, 2026-08-08). A teen who
    # arrives through it is attached to this school with no further step,
    # because the teacher handed out the link: the school assignment *is* their
    # approval. What the teacher still has to grant is level 1 (DEC-84).
    # Same shape as the Chapter 9 class join code, deliberately: unguessable,
    # rotatable, and it powers a link + a QR.
    join_code = models.CharField(
        max_length=24, unique=True, default=gen_join_code, db_index=True)
    is_open = models.BooleanField(default=True, verbose_name="פתוח להרשמה")

    class Meta:
        ordering = ["name"]
        unique_together = [("program", "name")]
        verbose_name = "בית ספר"
        verbose_name_plural = "בתי ספר"

    def __str__(self):
        return f"{self.name}{f' ({self.city})' if self.city else ''}"


class ProgramMembership(models.Model):
    """A person's place in a program.

    `status` **is** Litala's five-stage funnel, not a diagram of it:
    מתמיינים -> לומדים -> יוצרים -> מדריכים -> משפיעים, plus the two ends a
    real program needs (alumnus / revoked) and the applied/rejected entry.

    Only `CERTIFIED` counts as a current מט״צ. The transition into it is made by
    hand, by program staff, and by nothing else (REQ-10.7).
    """

    # --- the funnel -------------------------------------------------------
    APPLIED = "applied"            # מתמיינים
    IN_TRAINING = "in_training"    # לומדים
    PROJECT_SUBMITTED = "project_submitted"  # יוצרים
    CERTIFIED = "certified"        # מדריכים / משפיעים - a מט״צ
    ALUMNUS = "alumnus"
    REJECTED = "rejected"
    REVOKED = "revoked"
    STATUS_CHOICES = [
        (APPLIED, "מתמיין"),
        (IN_TRAINING, "לומד"),
        (PROJECT_SUBMITTED, "הגיש תוצר"),
        (CERTIFIED, "מט״צ מוסמך"),
        (ALUMNUS, "בוגר"),
        (REJECTED, "לא התקבל"),
        (REVOKED, "הסמכה בוטלה"),
    ]
    # The ordered spine of the track (REQ-10.4). Terminal states are absent on
    # purpose: they are not positions on the path.
    TRACK_STAGES = [APPLIED, IN_TRAINING, PROJECT_SUBMITTED, CERTIFIED]
    STAGE_LABELS = {
        APPLIED: "מתמיינים",
        IN_TRAINING: "לומדים",
        PROJECT_SUBMITTED: "יוצרים",
        CERTIFIED: "מדריכים",
    }

    # --- joining a school -------------------------------------------------
    # "Member picks, leader confirms" (Avi, 2026-08-08; closes ACT-33 and matches
    # Litala's "שהתלמיד יבחר את המוביל שלו"). The teen names their school; it
    # only counts once that school's leader confirms them onto the roster.
    SCHOOL_PENDING = "pending"
    SCHOOL_CONFIRMED = "confirmed"
    SCHOOL_STATUS_CHOICES = [
        (SCHOOL_PENDING, "ממתין לאישור המוביל"),
        (SCHOOL_CONFIRMED, "אושר"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="program_memberships")
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="memberships")
    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")
    school_join_status = models.CharField(
        max_length=12, choices=SCHOOL_STATUS_CHOICES, default=SCHOOL_PENDING)
    cohort_year = models.PositiveIntegerField(default=current_year)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=APPLIED, db_index=True)

    # --- the two grants ---------------------------------------------------
    # A school owner grants both levels (DEC-83, Avi 2026-08-08, superseding
    # DEC-78's "endorse only"):
    #   level 1  ACCEPTED  - into the program, gated on the entrance test
    #   level 2  CERTIFIED - as a מט״צ
    # Each records who granted it and when, because a status that confers
    # standing has to be traceable to a person (REQ-10.8).
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matazim_acceptances_granted")
    acceptance_note = models.CharField(max_length=300, blank=True, default="")

    # Certification: who granted it, when, and why. A status that confers
    # prestige has to be traceable (REQ-10.8) - and neither Avi nor Litala will
    # remember in a year.
    certified_at = models.DateTimeField(null=True, blank=True)
    certified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matazim_certifications_granted")
    certification_note = models.TextField(blank=True, default="")

    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "program", "cohort_year")]
        ordering = ["-updated_at"]
        verbose_name = "חברות בתוכנית"
        verbose_name_plural = "חברויות בתוכנית"


    def __str__(self):
        return f"{self.user.username} @ {self.program.slug} [{self.status}]"

    # --- status helpers ---------------------------------------------------

    @property
    def is_certified(self):
        """A *current* מט״צ. Alumni and revoked memberships keep their history
        and their certificate but are deliberately not current (REQ-10.9)."""
        return self.status == self.CERTIFIED

    @property
    def is_on_roster(self):
        """Confirmed onto a school's roster by that school's leader."""
        return self.school_id is not None and self.school_join_status == self.SCHOOL_CONFIRMED

    @property
    def is_accepted(self):
        """Level 1 granted: past the entrance test and into the program."""
        return self.status in (self.IN_TRAINING, self.PROJECT_SUBMITTED,
                               self.CERTIFIED, self.ALUMNUS)

    @property
    def can_be_accepted(self):
        """Level 1 is available while they are still an applicant."""
        return self.status == self.APPLIED

    @property
    def can_be_certified(self):
        """Level 2 is available once they are in the program and not yet a
        מט״צ. Deliberately not gated on `project_submitted`: the project flow
        lands in SPR-10.4, and until then a school owner would have no route to
        the grant at all."""
        return self.status in (self.IN_TRAINING, self.PROJECT_SUBMITTED)

    @property
    def stage_index(self):
        """Position on the track, or -1 for the terminal states."""
        try:
            return self.TRACK_STAGES.index(self.status)
        except ValueError:
            return -1

    @property
    def stage_label(self):
        return self.STAGE_LABELS.get(self.status, self.get_status_display())

    def track_steps(self):
        """The five-stage spine rendered as a path: each stage with whether it is
        done, current, or still ahead (REQ-10.4)."""
        here = self.stage_index
        steps = []
        for i, stage in enumerate(self.TRACK_STAGES):
            steps.append({
                "key": stage,
                "label": self.STAGE_LABELS[stage],
                "done": here > i,
                "current": here == i,
            })
        return steps


class ProgramApplication(models.Model):
    """What a teen wrote when they applied (REQ-10.4).

    Kept short on purpose: every extra field is a teenager who does not finish
    the form. The point of the application is not to assess them - the entrance
    test does that (§10.7) - it is to give the school owner enough context to
    recognise who this is.
    """

    membership = models.OneToOneField(
        ProgramMembership, on_delete=models.CASCADE, related_name="application")
    grade = models.CharField(max_length=40, blank=True, default="", verbose_name="כיתה")
    motivation = models.TextField(blank=True, default="", verbose_name="למה אתם רוצים להיות מט״צים")
    built_before = models.TextField(blank=True, default="", verbose_name="מה כבר בניתם")
    # True when they arrived through a school's own invite link rather than
    # picking a school from the list. Worth knowing: it is the difference
    # between "the teacher recruited them" and "they found us".
    via_invite_link = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "בקשת הצטרפות"
        verbose_name_plural = "בקשות הצטרפות"

    def __str__(self):
        return f"Application: {self.membership}"


class EntranceAttempt(models.Model):
    """One go at the entrance test (§10.7).

    A row is created the moment a target is handed out, not when something is
    uploaded, so "assigned but never submitted" is visible rather than silent -
    it is the difference between a kid who tried and one who never opened it.

    Retries are unlimited and each gets a **fresh target**, so a second attempt
    is another honest build rather than a chance to nudge the same file until it
    passes. The attempt history is deliberately kept: somebody who missed, read
    the feedback and came back has shown more of what this program selects for
    than somebody who passed first time (REQ-10.28).
    """

    membership = models.ForeignKey(
        ProgramMembership, on_delete=models.CASCADE, related_name="entrance_attempts")
    target_id = models.CharField(max_length=16)
    number = models.PositiveIntegerField(default=1)
    model_file = models.FileField(upload_to="entrance_tests/", blank=True, null=True)
    # What we measured, and what we made of it. Stored so a teacher can see the
    # reasoning behind a verdict, and so a tolerance change can be replayed
    # against past attempts instead of guessed at.
    measured = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    passed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("membership", "number")]
        verbose_name = "ניסיון במבחן הכניסה"
        verbose_name_plural = "ניסיונות במבחן הכניסה"

    def __str__(self):
        return f"{self.membership.user.username} #{self.number} {self.target_id}"

    @property
    def is_submitted(self):
        return self.submitted_at is not None


class ProgramStatusLog(models.Model):
    """Append-only audit of every membership status change (REQ-10.8).

    A status that confers prestige has to be traceable: who granted it, when, and
    why. Neither Avi nor Litala will remember in a year, and if a certification
    is ever disputed or revoked the trail is the only evidence. Never edited,
    never deleted.
    """

    membership = models.ForeignKey(
        ProgramMembership, on_delete=models.CASCADE, related_name="status_log")
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matazim_status_changes")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "יומן שינויי סטטוס"
        verbose_name_plural = "יומן שינויי סטטוס"

    def __str__(self):
        return f"{self.membership_id}: {self.from_status} -> {self.to_status}"
