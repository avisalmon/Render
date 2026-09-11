"""What מט״צים is entitled to know about a person.

The identity itself is not ours. Name, avatar, email and every הדרכה a person
has done live in babook's shared tables, and a name edited here changes there
too, because a person has one name. What is ours is the handful of facts that
only exist because מט״צים exists: did they find us through this door, have they
been told this is a prototype, and have they passed the entrance test.

Keeping those here rather than on babook's `UserProfile` is what lets RULE-3
stay true while still meeting "use the same profile model": the shared facts
stay shared, and only our own flags are ours. See docs/matazim/spec.md §4.
"""

from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from .storage import entrance_upload_path, private_storage


class MemberProfile(models.Model):
    """מט״צים's companion to babook's UserProfile. One row per person we meet."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="matazim_profile")

    # REQ-M.35 — did this person find us here, or are they a babook member who
    # wandered over? Without it the funnel cannot be read later.
    entered_via_matazim = models.BooleanField(default=False, verbose_name="נכנס דרך מט״צים")
    first_seen_at = models.DateTimeField(auto_now_add=True)

    # REQ-M.40 — the prototype disclaimer was put in front of them, and they
    # acknowledged it. Stored so we can say who was told and when.
    welcome_accepted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="אישר את הודעת אב הטיפוס"
    )

    # Provisional (spec §4): a stored flag while the entrance test is a
    # placeholder, derived from EntranceAttempt once REQ-M.17 lands. Every
    # caller goes through has_passed_entrance_test() so that swap changes
    # nothing outside this file.
    entrance_test_passed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="עבר את מבחן הכניסה"
    )

    # REQ-M.68 — adminship is granted here and seeded in production, never
    # self-served: there is no screen that makes someone an admin, because the
    # first one could never have used it. `manage.py matazim_admins` sets it.
    #
    # This is a boolean and not the "role column" the spec forbids. That rule is
    # about a role having exactly one source: a role field on Student would
    # compete with the leader FK and the two could disagree. Nothing competes
    # with this one.
    is_admin = models.BooleanField(default=False, verbose_name="מנהל/ת התוכנית")

    # REQ-M.84 — the programme is ninth-graders, so a parent consents.
    #
    # Only the year, never a full date of birth. The question this has to answer
    # is "is this person a minor", and a year answers it. A date would be more
    # data about a child for no extra ability to decide anything, which is the
    # definition of collecting too much.
    #
    # A blank year does not mean adult, it means we have to ask. Everyone who
    # registered before this shipped has one, and reading blank as adult would
    # silently exempt the entire existing population.
    birth_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="שנת לידה")

    guardian_name = models.CharField(
        max_length=120, blank=True, default="", verbose_name="הורה/אפוטרופוס"
    )
    guardian_email = models.EmailField(blank=True, default="", verbose_name="אימייל של ההורה")
    guardian_consent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="הסכמת הורה התקבלה"
    )
    # Set when an admin records consent a school collected on paper, left null
    # when the consent was given here at registration. Which of the two it was
    # is a question somebody will eventually ask.
    guardian_consent_recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="ההסכמה נרשמה על ידי",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "פרופיל מט״צים"
        verbose_name_plural = "פרופילי מט״צים"

    def __str__(self):
        return f"{self.user.email or self.user.username} · מט״צים"

    def has_passed_entrance_test(self):
        return self.entrance_test_passed_at is not None

    def has_accepted_welcome(self):
        return self.welcome_accepted_at is not None


class EntranceTarget(models.Model):
    """One object in the entrance-test bank.

    The geometry lives in files that a management command generated offline:
    an STL, a dimensioned drawing, and an answer key the web process never
    exposes. This row exists so a **person** can take an object out of
    circulation without anything being deleted (REQ-M.55). Litala and Avi decide
    what a 14-year-old should be asked to build; the generator only proposes.
    """

    target_id = models.CharField(max_length=16, unique=True, db_index=True)
    shape = models.CharField(max_length=40)
    title = models.CharField(max_length=120, blank=True, default="")
    brief = models.TextField(blank=True, default="")

    is_retired = models.BooleanField(default=False, verbose_name="הוצא משימוש")
    retired_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["target_id"]
        verbose_name = "משימת מבחן כניסה"
        verbose_name_plural = "משימות מבחן כניסה"

    def __str__(self):
        return f"{self.target_id} · {self.title}"

    @property
    def drawing_url(self):
        return f"/static/matazim/targets/{self.target_id}.svg"

    @property
    def model_url(self):
        return f"/static/matazim/targets/{self.target_id}.stl"


class EntranceAttempt(models.Model):
    """One go at the entrance test.

    A retry is a new row rather than an edit, because the history is the point:
    someone who missed, read the feedback and came back has shown more of what
    this program selects for than someone who passed first time (REQ-M.53).
    """

    member = models.ForeignKey("MemberProfile", on_delete=models.CASCADE, related_name="attempts")
    target_id = models.CharField(max_length=16)
    number = models.PositiveIntegerField(default=1)

    # Not under MEDIA_ROOT, and not under the name the teenager chose. Both
    # halves matter: /media/ is served with no authentication at all, and school
    # work is named after the pupil roughly always (spec §4.10 P2, REQ-M.80).
    model_file = models.FileField(
        upload_to=entrance_upload_path,
        storage=private_storage,
        blank=True,
        null=True,
    )
    measured = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    passed = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        unique_together = [("member", "number")]
        verbose_name = "ניסיון מבחן כניסה"
        verbose_name_plural = "ניסיונות מבחן כניסה"

    def __str__(self):
        return f"{self.member.user.email} · ניסיון {self.number} · {self.target_id}"

    @property
    def is_open(self):
        """Waiting for an upload. There is at most one of these per member."""
        return self.submitted_at is None


def current_year():
    from django.utils import timezone

    return timezone.now().year


def new_join_code():
    """Unguessable and short enough to read off a WhatsApp message."""
    import secrets

    return secrets.token_urlsafe(9)


class Leader(models.Model):
    """מוביל. A teacher who runs classes and carries students.

    This row *is* the role: having one makes you a leader, and there is no role
    column anywhere to disagree with it. Scope follows from `Student.leader`, so
    a leader cannot reach anyone else's students because the query cannot get
    there (spec §4.4).

    Adminship, not leadership, is what assigns these. Nobody makes themselves a
    leader (REQ-M.25).
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="matazim_leader")
    contact = models.CharField(max_length=200, blank=True, default="")

    join_code = models.CharField(
        max_length=32,
        unique=True,
        default=new_join_code,
        db_index=True,
        verbose_name="קוד הצטרפות",
    )

    # REQ-M.67 — deactivating destroys nothing. They leave the join list, take
    # no new students and lose the leader view, but every Student row keeps
    # pointing at them so no roster is lost. An admin moves people deliberately.
    is_active = models.BooleanField(default=True, verbose_name="פעיל")

    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "מוביל"
        verbose_name_plural = "מובילים"

    def __str__(self):
        return self.user.email or self.user.username


class StudyClass(models.Model):
    """כיתה. A leader's group of students at one school.

    `class` is a reserved word, hence the name.

    **School lives here, not on the leader** (Avi, 2026-09-10). A leader running
    classes at two schools works without a second leader record, and the label
    lands where the students actually sit. בתי הספר המשתתפים is the distinct set
    of `school_name`.
    """

    leader = models.ForeignKey(Leader, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=80, verbose_name="שם הכיתה")
    school_name = models.CharField(max_length=150, blank=True, default="", verbose_name="בית ספר")
    year = models.PositiveIntegerField(default=current_year)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["school_name", "name"]
        verbose_name = "כיתה"
        verbose_name_plural = "כיתות"

    def __str__(self):
        return f"{self.name} · {self.school_name}" if self.school_name else self.name


class Student(models.Model):
    """מט״צ. One row per person per cohort.

    `leader` is nullable on purpose (REQ-M.65): someone registers, passes the
    entrance test, and is nobody's yet. That is a normal state, not an error.
    From there it goes either way, and both happen: they ask to join a leader,
    or a leader invites them through their link.
    """

    APPLIED = "applied"
    IN_TRAINING = "in_training"
    PROJECT_SUBMITTED = "project_submitted"
    CERTIFIED = "certified"
    ALUMNUS = "alumnus"
    REJECTED = "rejected"
    REVOKED = "revoked"
    STATUS_CHOICES = [
        (APPLIED, "מתמיינים"),
        (IN_TRAINING, "לומדים"),
        (PROJECT_SUBMITTED, "יוצרים"),
        (CERTIFIED, "מדריכים"),
        (ALUMNUS, "משפיעים"),
        (REJECTED, "לא התקבל"),
        (REVOKED, "הוסר"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matazim_student")
    leader = models.ForeignKey(
        Leader, on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    classes = models.ManyToManyField(StudyClass, blank=True, related_name="students")

    # Asking is not the same as being accepted (REQ-M.10). `leader` is who has
    # them; `pending_leader` is who they asked and are waiting on. An invite
    # link sets `leader` directly, because the leader handed out the link and
    # the choice is already theirs (REQ-M.9).
    pending_leader = models.ForeignKey(
        Leader,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
        verbose_name="ממתין לאישור של",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=APPLIED, db_index=True)
    cohort_year = models.PositiveIntegerField(default=current_year)

    # REQ-M.78 — certification is an act by a person, so the record says which
    # person and when. Without that, "certified" is a status that appeared from
    # nowhere and nobody can be asked about it. Both are cleared on revoke, so
    # they always describe the certification that is currently in force rather
    # than the last one that ever was.
    certified_at = models.DateTimeField(null=True, blank=True, verbose_name="הוסמך בתאריך")
    certified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matazim_certified",
        verbose_name="הוסמך על ידי",
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "cohort_year")]
        ordering = ["-cohort_year", "user__email"]
        verbose_name = "מט״צ"
        verbose_name_plural = "מט״צים"

    def __str__(self):
        return f"{self.user.email or self.user.username} · {self.cohort_year}"

    @property
    def school_names(self):
        """Where this student actually sits. Derived from their classes."""
        return sorted({c.school_name for c in self.classes.all() if c.school_name})


@receiver(models.signals.post_delete, sender=EntranceAttempt)
def _delete_upload_with_attempt(sender, instance, **kwargs):
    """When the row goes, the file goes.

    Found by taking Avi's advice to reuse babook's infrastructure rather than
    build a parallel one. babook already has self-service account deletion
    (`app.views.delete_account`, REQ-7.2.10), and `User.delete()` cascades
    cleanly into `MemberProfile`, `Student` and `EntranceAttempt`. So מט״צים
    needs no deletion machinery of its own, which is the right answer.

    But Django has not deleted files on row deletion since 1.3. Without this,
    a teenager who asked for their account to be deleted would have every row
    removed and their uploaded model left sitting on the disk, which is the one
    piece of it that is unmistakably theirs. Reuse is correct; reuse without
    reading what it does is how that happens.
    """
    if instance.model_file:
        instance.model_file.delete(save=False)


class RetentionRun(models.Model):
    """One approved deletion, and who approved it.

    REQ-M.87. Retention here runs behind a review rather than on a timer,
    because deletion is the one action in this product where an unattended bug
    is irreversible. The same shape as certification (REQ-M.78) and retiring a
    target (REQ-M.55): the machine proposes, a person decides, and the decision
    has a name on it.

    This row is also the answer to "does the retention policy actually run".
    Without it, a process that has never once executed looks exactly like one
    that runs perfectly, and the privacy page would be making a promise nobody
    could check.
    """

    ran_at = models.DateTimeField(auto_now_add=True, verbose_name="בוצע בתאריך")
    ran_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="אושר על ידי",
    )
    deleted_count = models.PositiveIntegerField(default=0, verbose_name="רשומות שנמחקו")
    kind = models.CharField(max_length=40, default="failed_attempts")

    class Meta:
        ordering = ["-ran_at"]
        verbose_name = "ניקוי מידע ישן"
        verbose_name_plural = "ניקויי מידע ישן"

    def __str__(self):
        who = self.ran_by.email if self.ran_by else "אוטומטי"
        return f"{self.ran_at:%Y-%m-%d} · {self.deleted_count} · {who}"
