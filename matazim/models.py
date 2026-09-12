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

    # REQ-M.68 — granted here and seeded in production, never self-served:
    # there is no screen that makes the first one, because they could never have
    # used it. `manage.py matazim_admins` sets it.
    #
    # Renamed from `is_admin` on 2026-09-11 (spec §4.3). "admin" pointed at root
    # in conversation and at the program manager on screen, an ambiguity that
    # had already produced one wrong grant of superuser. The Hebrew was right
    # all along; only the English was lying.
    #
    # This is a boolean and not the "role column" the spec forbids. That rule is
    # about a role having exactly one source: a role field on Student would
    # compete with the leader FK and the two could disagree. Nothing competes
    # with this one.
    is_program_manager = models.BooleanField(default=False, verbose_name="מנהל/ת התוכנית")

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
    # pointing at them so no roster is lost. A program manager moves people
    # deliberately.
    is_active = models.BooleanField(default=True, verbose_name="פעיל")

    # REQ-M.93 — a candidate is a row that exists and grants nothing.
    #
    # Somebody who signed up through an open invite has a Leader row and is not
    # a leader. `leader_of()` refuses to return an unapproved row, which is what
    # stops them having a roster, an invite link and a view of named minors
    # before any person said yes. Distinct from `is_active`: unapproved means
    # never yet a leader, inactive means was one and has stopped.
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="אושר/ה בתאריך")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="אושר/ה על ידי",
    )

    # REQ-M.88 — who owns this leader, and therefore which world they are in.
    #
    # This one FK is what makes two institutions two products rather than one
    # shared list. It is the leader rule moved up a floor: a program manager
    # cannot reach another's leaders for the same reason a leader cannot reach
    # another's students, which is that the queryset never contained them.
    #
    # Nullable, and null means orphaned rather than shared. A leader whose
    # program manager was deleted is visible to root alone until somebody
    # reassigns them, which is the safe direction to fail in: invisible is
    # recoverable, visible-to-everyone is not.
    program_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matazim_leaders",
        verbose_name="מנהל/ת התוכנית",
    )

    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "מוביל"
        verbose_name_plural = "מובילים"

    def __str__(self):
        return self.user.email or self.user.username

    @property
    def school_names(self):
        """Where this leader teaches, each school named once.

        A leader with two classes in one school was rendering "עתיד רמלה ·
        עתיד רמלה", because the list was built by looping classes. Mirrors
        `Student.school_names`, which had already solved this.
        """
        return sorted({c.school_name for c in self.classes.all() if c.school_name})

    @property
    def is_approved(self):
        """REQ-M.93 — approval is an act by a person, and this is its record.

        Read by `access.leader_of`, which is what makes an unapproved row grant
        nothing at all rather than merely look different on a screen.
        """
        return self.approved_at is not None


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


# The five public stages plus the two ways out, defined once because both
# `Student.status` and `StatusLog` describe the same vocabulary and a second
# copy is a second thing to keep in step.
STATUS_CHOICES = [
    ("applied", "מתמיינים"),
    ("in_training", "לומדים"),
    ("project_submitted", "יוצרים"),
    ("certified", "מדריכים"),
    ("alumnus", "משפיעים"),
    ("rejected", "לא התקבל"),
    ("revoked", "הוסר"),
]


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
    STATUS_CHOICES = STATUS_CHOICES

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


def new_invite_token():
    """Unguessable. This one is a credential to *become staff*, so it is longer
    than a leader's join code: that one attaches a teenager to a teacher, this
    one can end in somebody seeing named minors."""
    import secrets

    return secrets.token_urlsafe(24)


class LeaderInvite(models.Model):
    """An invitation to become a leader, in one of two shapes (REQ-M.91, M.92).

    **Personal.** Named to a person by the program manager, and single-use. She
    may get the name wrong: it is a label, not a check, and the real name
    arrives when they register and set it themselves. It may be forwarded, which
    is tolerated, but the first registration spends it and the link dies.

    **Open.** Nobody named, reusable, handed to a staff room. Precisely because
    anyone holding it could use it, it confers nothing: whoever registers
    through it becomes a candidate and waits for a person to approve them
    (REQ-M.93).

    Both belong to the program manager who made them, which is how someone
    arriving through a link lands in the right world (REQ-M.88).
    """

    PERSONAL = "personal"
    OPEN = "open"
    KIND_CHOICES = [(PERSONAL, "אישית"), (OPEN, "פתוחה")]

    program_manager = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matazim_invites"
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=PERSONAL)
    token = models.CharField(max_length=64, unique=True, default=new_invite_token, db_index=True)

    # A label, never a check. Blank on an open invite, because nobody is named.
    label = models.CharField(max_length=120, blank=True, default="", verbose_name="עבור")
    email = models.EmailField(blank=True, default="", verbose_name="אימייל")

    # Personal invites only. An open invite is reusable by design, which is
    # exactly why it cannot make anyone a leader.
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    revoked_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "הזמנת מוביל/ה"
        verbose_name_plural = "הזמנות מובילים"

    def __str__(self):
        return f"{self.get_kind_display()} · {self.label or 'ללא שם'}"

    @property
    def is_spent(self):
        """A personal invite dies on first use. An open one never does."""
        return self.kind == self.PERSONAL and self.used_at is not None

    @property
    def is_live(self):
        return self.revoked_at is None and not self.is_spent


class StatusLog(models.Model):
    """Every change to a student's stage, and who made it (REQ-M.21).

    Append-only. Nothing in this product updates or deletes one of these rows,
    and a guard test asserts no code path tries.

    Why it exists at all. Every other record here answers "what is true now";
    this one answers "who decided, and when". For a system holding data about
    minors that is not bookkeeping, it is the difference between being able to
    answer a parent's question and having to say we do not know. Certification
    already records its own author (REQ-M.78) because it is the most
    consequential transition, and this generalises that to all of them rather
    than leaving four other transitions anonymous.

    `note` is deliberately free text and deliberately optional. A reason nobody
    can be bothered to type is a reason that gets typed badly.
    """

    student = models.ForeignKey("Student", on_delete=models.CASCADE, related_name="history")
    # The same choices `Student.status` carries, so `get_to_status_display()`
    # resolves to Hebrew. Without them the field is a bare CharField, that
    # method does not exist, and the history renders raw keys: a teenager's
    # record reading "in_training ← certified" to a Hebrew-speaking teacher.
    from_status = models.CharField(
        max_length=20, blank=True, default="", choices=STATUS_CHOICES, verbose_name="משלב"
    )
    to_status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="לשלב")
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="על ידי",
    )
    # REQ-M.98 — a move between leaders is a thing that happened to this person
    # and belongs in the same timeline as everything else. A teacher leaves, a
    # child changes school, a pairing does not work; none of that is a status
    # change, and until now none of it was recorded anywhere. Nullable because
    # almost every row is a status transition with no move in it.
    from_leader = models.ForeignKey(
        "Leader",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="ממוביל/ה",
    )
    to_leader = models.ForeignKey(
        "Leader",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="למוביל/ה",
    )

    note = models.CharField(max_length=200, blank=True, default="", verbose_name="הערה")
    at = models.DateTimeField(auto_now_add=True, verbose_name="מתי")

    class Meta:
        ordering = ["-at"]
        verbose_name = "שינוי שלב"
        verbose_name_plural = "שינויי שלב"

    def __str__(self):
        return f"{self.student_id}: {self.from_status or '—'} → {self.to_status}"


class MatazCertificate(models.Model):
    """What a certified מט״צ actually gets (REQ-M.20).

    Before this, being certified was a status flag: the payoff of the whole
    programme was a sentence on a page nobody else could see. A certification is
    the thing a fourteen-year-old shows a parent, a school puts in a file, and
    somebody attaches to an application two years later, and none of that works
    if it only exists behind a login.

    **The name is captured, not looked up.** A certificate says who it was
    awarded to on the day. Reading it live would mean somebody correcting their
    display name in 2029 silently rewrote a document a school is holding a
    printed copy of.

    **One per student, never reissued.** Revoking and re-certifying keeps the
    same `public_id`, because printed copies carry it and reissuing would
    invalidate paper that is still perfectly true.

    **`public_id` is a UUID, and that is a privacy decision rather than a
    style.** The verification page is readable by strangers by design, since a
    school checking one is not a member. A sequential id there would be an
    invitation to enumerate every certified child in the programme, which is the
    mistake the QR endpoint made in SPR-M.9 (spec §4.10, finding P1).
    """

    import uuid as _uuid_module

    student = models.OneToOneField("Student", on_delete=models.CASCADE, related_name="certificate")
    public_id = models.UUIDField(default=_uuid_module.uuid4, unique=True, db_index=True)

    name_on_certificate = models.CharField(max_length=200, verbose_name="השם על התעודה")
    awarded_by_name = models.CharField(
        max_length=200, blank=True, default="", verbose_name="הוסמך על ידי"
    )
    awarded_at = models.DateTimeField(verbose_name="תאריך ההסמכה")

    # A certificate is a *current* fact, not a permanent one: certification is
    # revocable (REQ-M.78). A printed copy outlives a revocation, which cannot
    # be helped, but the page somebody checks against must say what is true when
    # they ask rather than what was true when it was printed.
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="בוטלה בתאריך")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "תעודת מט״צ"
        verbose_name_plural = "תעודות מט״צ"

    def __str__(self):
        return f"{self.name_on_certificate} · {self.public_id}"

    @property
    def is_valid(self):
        return self.revoked_at is None


class Application(models.Model):
    """REQ-M.16 — what somebody wrote when they asked to join.

    This existed in the spec and not in the database. The apply form asked a
    fourteen-year-old for their grade, why they want to join, and what they have
    built; it required the first two, validated them, and then dropped all
    three. The leader being asked to accept that person saw a name and an email.
    So we made a child write why they wanted in, threw the answer away, and then
    had somebody decide about them with nothing to read. Found 2026-09-12 by
    signing a fake person up through the real forms and then searching every
    text column in the database for the sentence they had typed.

    **A row per asking, not per person.** Somebody can be turned down and apply
    again, to the same leader or a different one, and the second answer is not a
    correction of the first. Same reasoning as `StatusLog` (§4.7): the history is
    the point, and an overwriting row would quietly lose the thing a leader most
    wants to see, which is whether this person has asked before.

    **It is a minor's free text**, so it is covered by everything §4.10 says:
    it appears in their own data export (REQ-M.85), it dies with their account
    through the same cascade as everything else, and it is readable only by the
    leader who was asked, the program manager who owns that leader, and root.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="applications"
    )
    # Who was asked. Kept beside the answers because `Student.pending_leader` is
    # cleared the moment somebody accepts or declines, and then nothing would
    # say who this was written for.
    asked = models.ForeignKey(
        Leader,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        verbose_name="הבקשה הופנתה אל",
    )

    grade = models.CharField(max_length=40, blank=True, default="", verbose_name="כיתה")
    motivation = models.TextField(blank=True, default="", verbose_name="מה מושך אותם לתוכנית")
    # Explicitly optional on the form, and the form says so. Somebody who has
    # built nothing yet is exactly who this programme is for.
    built_before = models.TextField(
        blank=True, default="", verbose_name="מה כבר בנו"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "בקשת הצטרפות"
        verbose_name_plural = "בקשות הצטרפות"

    def __str__(self):
        return f"{self.student_id} → {self.asked_id or '-'} ({self.created_at:%Y-%m-%d})"


class Request(models.Model):
    """REQ-M.105 — what the person who runs the programme actually asked for.

    Every review in this project has ended on the same sentence: it checks the
    product against itself and cannot say what a real person tried to do and
    could not. This is the row that answers it.

    **The text is hers and is never edited** (REQ-M.112). An assessment, a
    status and a sprint reference are added around it, and nothing rewrites it.
    Not politeness: the exact words are the evidence, and a paraphrase of a
    complaint is a complaint that has already been answered.

    **`from_screen` is the cheapest useful field here.** "The roster is
    confusing" and "the roster is confusing, sent from the roster with two
    classes in one school" are different reports, and the second one is the
    only one anybody can act on.

    **Approving does not start anything** (REQ-M.110). This is a queue with a
    human at both ends: she writes, Avi approves, and a sprint happens when Avi
    says so in conversation. Nothing on this model schedules, signals or
    triggers work, and `tests/test_spr_m_25.py` fails if that changes.
    """

    NEW = "new"
    APPROVED = "approved"
    DECLINED = "declined"
    DONE = "done"
    STATUS_CHOICES = [
        (NEW, "חדשה"),
        (APPROVED, "אושרה"),
        (DECLINED, "לא מתאימה כרגע"),
        (DONE, "בוצעה"),
    ]

    IDEA = "idea"
    PROBLEM = "problem"
    COPY = "copy"
    QUESTION = "question"
    KIND_CHOICES = [
        (IDEA, "רעיון לשיפור"),
        (PROBLEM, "משהו לא עובד או מבלבל"),
        (COPY, "נוסח או מילה"),
        (QUESTION, "שאלה"),
    ]

    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matazim_requests", verbose_name="נכתב על ידי"
    )
    # The role as it was when they wrote, because roles change and a request
    # read a year later should still say who was speaking.
    author_role = models.CharField(max_length=40, blank=True, default="")

    body = models.TextField(verbose_name="הבקשה")
    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default=IDEA, verbose_name="סוג"
    )
    from_screen = models.CharField(
        max_length=300, blank=True, default="", verbose_name="נשלח מהמסך"
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=NEW, db_index=True, verbose_name="מצב"
    )
    # REQ-M.108 — one press, with a name and a time on it (§4.7).
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="הוכרע על ידי",
    )
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name="הוכרע בתאריך")

    # REQ-M.109 — advisory, machine-written, and it decides nothing.
    assessment = models.TextField(blank=True, default="", verbose_name="הערכה")
    assessed_at = models.DateTimeField(null=True, blank=True)

    # REQ-M.111 — what actually happened, and where to read it.
    sprint = models.CharField(max_length=40, blank=True, default="", verbose_name="ספרינט")
    outcome = models.TextField(blank=True, default="", verbose_name="מה נעשה")
    done_at = models.DateTimeField(null=True, blank=True)
    summary_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "בקשה"
        verbose_name_plural = "בקשות"

    def __str__(self):
        return f"{self.get_status_display()} · {self.body[:48]}"

    @property
    def is_open(self):
        return self.status in (self.NEW, self.APPROVED)

    @property
    def waiting_on_avi(self):
        return self.status == self.NEW
