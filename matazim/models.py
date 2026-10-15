"""What מטצים is entitled to know about a person.

The identity itself is not ours. Name, avatar, email and every הדרכה a person
has done live in babook's shared tables, and a name edited here changes there
too, because a person has one name. What is ours is the handful of facts that
only exist because מטצים exists: did they find us through this door, have they
been told this is a prototype, and have they passed the entrance test.

Keeping those here rather than on babook's `UserProfile` is what lets RULE-3
stay true while still meeting "use the same profile model": the shared facts
stay shared, and only our own flags are ours. See docs/matazim/spec.md §4.
"""

from django.contrib.auth.models import User
from django.db import models
from django.dispatch import receiver

from .storage import entrance_upload_path, private_storage, submission_upload_path


class Institution(models.Model):
    """The thing a programme belongs to, and the people who run it.

    Added 2026-09-14 on Avi's "Go" to the proposal in `data_model.md` §6. Until
    then the tenancy root was a person: `Leader`, `Event`, `LeaderInvite` and
    `Post` all pointed at the `User` who ran the programme, and the day she left
    her successor would have signed in to an empty programme. §4.8 had argued
    that a second network becomes a table on the day one exists, and never
    considered the first manager leaving.

    **`managers` is the role.** Being a program manager means being in this
    m:n, and nothing else says so: `MemberProfile.is_program_manager` was the
    flag and is gone, because a flag beside the m:n is a second copy of one
    fact. `access.is_program_manager(user)` reads this. More than one manager
    is allowed and is the point: Litala's brief describes צוות התכנית as two
    people.

    **One row today**, made by the migration from whoever held the flag, and
    `Institution.default()` returns it while there is one. The day a second
    network arrives it is a second row, not a redesign.
    """

    name = models.CharField(max_length=120, verbose_name="שם")
    managers = models.ManyToManyField(
        User, blank=True, related_name="matazim_institutions", verbose_name="מנהלי/ות התוכנית"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "מוסד"
        verbose_name_plural = "מוסדות"

    def __str__(self):
        return self.name

    @classmethod
    def default(cls):
        """The one institution, while there is one. None before any exists.

        Callers that stamp ownership use this. When a second row exists this
        stops being the right answer and the caller has to ask which one, which
        is the day `institution_of()` grows a real decision.
        """
        return cls.objects.order_by("created_at").first()


class School(models.Model):
    """A school a person signs up from (Lital, 2026-10-15).

    Her sign-up asks for a full name and a school, chosen from a list: the
    network's own schools, so a name is never typed three different ways. It is a
    row and not a list in a template (Rule 1), seeded once by a migration and
    maintained afterwards by the programme team. A school here is where a person
    *says* they are from; the schools a leader teaches in (`StudyClass.school_name`)
    stay what they were.
    """

    name = models.CharField(max_length=150, unique=True, verbose_name="שם בית הספר")
    is_active = models.BooleanField(default=True, verbose_name="מוצג ברשימה")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "בית ספר"
        verbose_name_plural = "בתי ספר"

    def __str__(self):
        return self.name


class MemberProfile(models.Model):
    """מטצים's companion to babook's UserProfile. One row per person we meet."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="matazim_profile")

    # REQ-M.35 — did this person find us here, or are they a babook member who
    # wandered over? Without it the funnel cannot be read later.
    entered_via_matazim = models.BooleanField(default=False, verbose_name="נכנס דרך מטצים")
    school = models.ForeignKey(
        "School", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="members", verbose_name="בית ספר",
    )
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

    # The program-manager role lived here as a flag from SPR-M.6 to SPR-M.40,
    # renamed from `is_admin` on 2026-09-11 (spec §4.3) because "admin" pointed
    # at root in conversation and at the program manager on screen. It is
    # `Institution.managers` now, and `access.is_program_manager` reads it
    # there. REQ-M.68 still holds: granted by root or seeded on deploy, never
    # self-served, through `roles.grant_program_manager`.

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
        verbose_name = "פרופיל מטצים"
        verbose_name_plural = "פרופילי מטצים"

    def __str__(self):
        return f"{self.user.email or self.user.username} · מטצים"

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

    # REQ-M.182 - a person decides. `passed` above is the script's measurement
    # and stays what it always was, advice. Atid, 2026-06-25: the product goes
    # to שקד and to Avi "לאישור". Only an approval sets
    # `MemberProfile.entrance_test_passed_at`, which every downstream reader
    # (the joining door, certification, the overview) already asks.
    WAITING = "waiting"
    APPROVED = "approved"
    RETURNED = "returned"
    DECISION_CHOICES = [
        (WAITING, "מחכה לצוות"),
        (APPROVED, "אושר"),
        (RETURNED, "הוחזר לתיקון"),
    ]
    decision = models.CharField(
        max_length=10, choices=DECISION_CHOICES, default=WAITING, db_index=True,
        verbose_name="החלטת הצוות",
    )
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    # A return carries words (the same rule as REQ-M.123): "returned" alone tells
    # a fourteen-year-old they failed and not what to change.
    decision_note = models.TextField(blank=True, default="", verbose_name="מה לתקן")

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

    # SPR-M.59 (REQ-M.178) — whether this leader asks their members to pass the
    # entrance test to be officially accepted. Avi, 2026-10-12: the test is an
    # optional thing a leader can choose, and it runs beside the road rather
    # than across it. Leaders that existed when this shipped are on, so nothing
    # changes for anyone today; new leaders start off.
    requires_entrance_test = models.BooleanField(
        default=False, verbose_name="דורש/ת מבחן כניסה"
    )

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
    # The tenancy root (§4.4). A leader belongs to an institution, and the
    # people who run that institution are `Institution.managers`. Required,
    # unlike the user FK it replaced: a leader row is created with an
    # institution now (`approve_leader`, the invite flows, the API) rather than
    # placed into one later, because there is exactly one institution to place
    # it into and asking "which one" before a second exists is a question with
    # no answer. PROTECT because deleting an institution with leaders in it is
    # not a thing to do by accident.
    institution = models.ForeignKey(
        "Institution",
        on_delete=models.PROTECT,
        related_name="leaders",
        verbose_name="מוסד",
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

    def save(self, *args, **kwargs):
        # `school_name` is free text by decision (§4.8) and it now feeds a public
        # counter (REQ-M.5f), so "עתיד רמלה" with a trailing space was a second
        # school on the front page. Normalised here, at the one door every write
        # goes through, rather than in the view that happened to strip it and
        # the API that did not. Collapsed inner whitespace too: two spaces
        # between the words is the same school.
        self.school_name = " ".join((self.school_name or "").split())
        self.name = " ".join((self.name or "").split())
        super().save(*args, **kwargs)

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
    """מטצ. One row per person per cohort.

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
        verbose_name = "מטצ"
        verbose_name_plural = "מטצים"

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
    cleanly into `MemberProfile`, `Student` and `EntranceAttempt`. So מטצים
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

    institution = models.ForeignKey(
        "Institution", on_delete=models.CASCADE,
        related_name="invites", verbose_name="מוסד",
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
    """What a certified מטצ actually gets (REQ-M.20).

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
        verbose_name = "תעודת מטצ"
        verbose_name_plural = "תעודות מטצ"

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


class Submission(models.Model):
    """REQ-M.19 — the יוצרים stage: a member puts work in front of their leader.

    **The feedback is the point, not the flag.** The spec has said so since it
    was written, and it is why this model exists at all: before it, a leader
    could accept a student, read a roster and certify them, which is
    administration. A programme about mentorship needs the place where somebody
    looks at a teenager's work and tells them something about it.

    **Each attempt is its own row** (REQ-M.125). A resubmission that overwrote
    the first would destroy the thing the feedback was about, and a member
    reading "you should change the base" wants the version that had the base.

    **The file is a minor's work** (REQ-M.122). Outside `MEDIA_ROOT`, random
    name, reachable only through a view that asks who is looking — the same
    machinery the entrance test uses, because §4.10 P2 already found these
    sitting in public `/media/` under names like `יובל כהן מודל.stl`.
    """

    WAITING = "waiting"
    RETURNED = "returned"
    APPROVED = "approved"
    STATUS_CHOICES = [
        (WAITING, "מחכה למוביל/ה"),
        (RETURNED, "הוחזר לתיקון"),
        (APPROVED, "אושר"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="submissions"
    )
    # Who it was handed to. Kept beside the row because `Student.leader` can
    # change (REQ-M.98), and a year from now "who gave this feedback" has to
    # still answer correctly.
    leader = models.ForeignKey(
        Leader, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="submissions", verbose_name="הוגש ל",
    )

    # REQ-M.179 - which course this product is the product of. A slug, not a
    # foreign key into babook's tables (RULE-4), and blank for a free-standing
    # hand-in. The certificate for a course is issued only after one of these
    # exists for it.
    course_slug = models.CharField(
        max_length=80, blank=True, default="", db_index=True,
        verbose_name="ההדרכה שזה התוצר שלה",
    )
    title = models.CharField(max_length=160, verbose_name="מה זה")
    about = models.TextField(blank=True, default="", verbose_name="כמה מילים על זה")
    # A file, a link, or both. A Scratch project is a link and an STL is a file,
    # and this stage has to hold either without asking a teenager to care which
    # kind of thing the product prefers.
    work_file = models.FileField(
        upload_to=submission_upload_path,
        storage=private_storage,
        blank=True,
        null=True,
        verbose_name="קובץ",
    )
    link = models.URLField(blank=True, default="", verbose_name="קישור")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=WAITING, db_index=True
    )
    # REQ-M.125 — a new version answers a returned one, and both are kept.
    answers = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="revisions", verbose_name="תשובה להגשה",
    )

    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    # REQ-M.5e, REQ-M.30a — publishing a minor's work takes two yeses, and
    # either can be taken back.
    #
    # **Two fields rather than one flag, and deliberately not the community
    # share.** §4.12 says an internal feed and a public gallery are different
    # products: a fourteen-year-old putting work in front of the people in their
    # programme has not agreed to put it in front of the internet, and treating
    # one as the other would be the worst misreading available in this codebase.
    #
    # The maker's yes and the programme's yes. Both nullable, both needed, and
    # clearing either takes the work off the public page at once.
    public_consent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="הסכמת היוצר/ת לפרסום"
    )
    published_at = models.DateTimeField(
        null=True, blank=True, verbose_name="אושר לפרסום"
    )
    published_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "הגשה"
        verbose_name_plural = "הגשות"

    def __str__(self):
        return f"{self.title} · {self.get_status_display()}"

    @property
    def is_waiting(self):
        return self.status == self.WAITING

    @property
    def is_public(self):
        """Both yeses, and the work approved. Any one missing means no.

        Read rather than stored, so there is no third field to fall out of step
        with the two that decide it (§4.6, derived never stored).
        """
        return bool(
            self.public_consent_at
            and self.published_at
            and self.status == self.APPROVED
        )


class Feedback(models.Model):
    """REQ-M.123 — what the leader said, written to be read.

    Its own table rather than a field on the submission, because a leader may
    say more than one thing and because the thing a member comes back to read
    is the words, dated and attributed. A row here is never edited or deleted:
    the same reasoning as `StatusLog` (§4.7), except that this one is read by a
    fourteen-year-old rather than by an auditor.
    """

    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="feedback"
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    body = models.TextField(verbose_name="מה נכתב")
    # What the leader did in the same act, so the member reads the words and
    # the decision together rather than inferring one from the other.
    outcome = models.CharField(
        max_length=20, choices=Submission.STATUS_CHOICES, blank=True, default=""
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "משוב"
        verbose_name_plural = "משובים"

    def __str__(self):
        return f"{self.body[:40]}"


class Notification(models.Model):
    """REQ-M.33 — something happened, and the person it happened to is told.

    **A pointer, not a record.** The truth is the submission, the feedback, the
    roster row; this says where to look. That is what makes it safe to delete
    one or expire the lot, and it is the difference between a bell and a second
    inbox nobody keeps in step with the first.

    **Ours rather than the shared engine's** (REQ-M.127). That table feeds the
    other product's bell in the other product's chrome, so a מטצים event
    landing there would put this product inside theirs, which is the mirror
    image of what RULE-1 forbids. The cost is that somebody using both has two
    bells, which for a ninth-grader in this programme is close to theoretical.

    **Never the only telling** (REQ-M.128). Everything here also appears on the
    screen it belongs to, because bells are dismissed by accident constantly and
    a product where that loses information is broken.
    """

    FEEDBACK = "feedback"
    WORK_APPROVED = "work_approved"
    WORK_RETURNED = "work_returned"
    WORK_WAITING = "work_waiting"
    JOINED = "joined"
    OPEN_JOINED = "open_joined"
    CERTIFIED = "certified"
    EVENT = "event"
    ENTRANCE_APPROVED = "entrance_approved"
    ENTRANCE_RETURNED = "entrance_returned"
    SITE_UPDATE = "site_update"
    KIND_CHOICES = [
        (FEEDBACK, "משוב חדש"),
        (WORK_APPROVED, "עבודה אושרה"),
        (WORK_RETURNED, "עבודה הוחזרה"),
        (WORK_WAITING, "עבודה מחכה לך"),
        (JOINED, "צירוף למוביל/ה"),
        (OPEN_JOINED, "הצטרפות לכיתה פתוחה"),
        (CERTIFIED, "הסמכה"),
        (EVENT, "יום שיא"),
        (ENTRANCE_APPROVED, "מבחן הכניסה אושר"),
        (ENTRANCE_RETURNED, "מבחן הכניסה הוחזר"),
        (SITE_UPDATE, "עדכון באתר"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matazim_notifications"
    )
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    text = models.CharField(max_length=300, verbose_name="מה קרה")
    # Always a path inside /matazim/. Checked when one is raised rather than
    # trusted, because a notification that navigates out of the walls would
    # break RULE-1 from the one place nobody thinks to look.
    url = models.CharField(max_length=300, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "התראה"
        verbose_name_plural = "התראות"

    def __str__(self):
        return f"{self.get_kind_display()} · {self.text[:40]}"

    @property
    def is_unread(self):
        return self.read_at is None


class Event(models.Model):
    """REQ-M.27 — a יום שיא, or anything else with a date on it.

    **Aimed, not broadcast.** For everybody in the programme, or for named
    leaders, or for named classes. A day for one school's ninth-graders showing
    on every member's screen as though they were invited is worse than not
    telling them: it is an invitation that turns out not to be one.

    **Owned by a program manager** (§4.4), like leaders and students. Her
    institution's events are hers; another's are not merely hidden but
    unreachable, because the queryset never contained them.

    **Public is a decision, not a default** (REQ-M.129). A public page about a
    programme for fourteen-year-olds is a public statement of when and where
    children gather, so the programme's own diary stays the programme's own
    business unless somebody ticks a box.
    """

    institution = models.ForeignKey(
        "Institution", on_delete=models.CASCADE,
        related_name="events", verbose_name="מוסד",
    )

    title = models.CharField(max_length=160, verbose_name="מה")
    about = models.TextField(blank=True, default="", verbose_name="פרטים")
    starts_at = models.DateTimeField(db_index=True, verbose_name="מתי")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="עד מתי")
    place = models.CharField(max_length=200, blank=True, default="", verbose_name="איפה")

    # Who it is for. Empty audience with `for_everyone` false is an event for
    # nobody, which the form refuses rather than storing.
    for_everyone = models.BooleanField(default=True, verbose_name="לכל התוכנית")
    leaders = models.ManyToManyField(
        Leader, blank=True, related_name="events", verbose_name="למובילים"
    )
    classes = models.ManyToManyField(
        StudyClass, blank=True, related_name="events", verbose_name="לכיתות"
    )

    is_public = models.BooleanField(
        default=False, verbose_name="להציג בעמוד הפומבי"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="בוטל")

    # REQ-M.34 — the guard on the reminder job, and deliberately a stamp on the
    # row rather than a window the job recalculates. A job that runs twice, or a
    # deploy that shifts the schedule, must not ring the same bell again: a
    # member told twice about one day stops reading the bell, and the bell is
    # how they hear about everything else.
    reminded_at = models.DateTimeField(null=True, blank=True, verbose_name="נשלחה תזכורת")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "יום שיא"
        verbose_name_plural = "ימי שיא"

    def __str__(self):
        return f"{self.title} · {self.starts_at:%d.%m.%Y}"

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None


class Post(models.Model):
    """REQ-M.26 — קהילת מטצים, the feed inside the walls (§4.12).

    **Three kinds, one stream.** An announcement from the program manager, a
    member's own words, and a piece of work a leader approved that its maker
    chose to share. Three because they are the three things people in this
    programme have to say to each other, and one stream because nobody should
    have to learn which of three tabs a thing lives in.

    **Owned by an institution** (§4.4), like every other row here. The owner is
    stamped at write time from the author's own leader rather than read back
    through the author later, because `Student.leader` can change (REQ-M.98) and
    a post must not move to a different school when a teenager does.

    **Taken down, never deleted** (REQ-M.131). A post that vanishes teaches its
    writer nothing, and a writer who cannot tell whether they were moderated or
    glitched learns to distrust the room. So a hidden post keeps its row, its
    words and its author, and carries who hid it and why.
    """

    ANNOUNCEMENT = "announcement"
    POST = "post"
    WORK = "work"
    KIND_CHOICES = [
        (ANNOUNCEMENT, "הודעה מהתוכנית"),
        (POST, "פוסט"),
        (WORK, "תוצר"),
    ]

    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matazim_posts",
        verbose_name="מי כתב",
    )
    # The institution this belongs to. Stamped once, at write time.
    institution = models.ForeignKey(
        "Institution", on_delete=models.CASCADE,
        related_name="posts", verbose_name="מוסד",
    )

    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default=POST, db_index=True
    )
    body = models.TextField(verbose_name="מה לספר")

    # REQ-M.132 — sharing approved work is a separate act from making it, so
    # this is a link to a submission and never a copy of one. The file stays
    # where it was, behind the view that asks who is looking (REQ-M.122).
    submission = models.ForeignKey(
        "Submission", on_delete=models.CASCADE, null=True, blank=True,
        related_name="shared_as", verbose_name="תוצר משותף",
    )

    hidden_at = models.DateTimeField(null=True, blank=True, verbose_name="הוסתר")
    hidden_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    hidden_reason = models.CharField(
        max_length=200, blank=True, default="", verbose_name="למה הוסתר"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "פוסט"
        verbose_name_plural = "קהילה"

    def __str__(self):
        return f"{self.get_kind_display()} · {self.body[:40]}"

    @property
    def is_hidden(self):
        return self.hidden_at is not None


class TeachingSession(models.Model):
    """REQ-M.32 — פרקטיקום: the מטצ actually standing in front of a class.

    The thing the whole programme exists to produce, and the last stage that had
    no model. Everything around it was tracked and it was not: a leader could
    read a roster, approve work and certify somebody without ever seeing what
    that teenager had taught.

    **Counts, never names** (REQ-M.29). The hardest constraint here, and the one
    that shapes the model. The children being taught are not users, not members
    and not rows, so a session records how many were there and nothing about who
    they were. `learners` is an integer for that reason and there is deliberately
    no field it could be written into instead.

    `place` is free text and is therefore the one field where a fourteen-year-old
    could type a child's name by accident. The form says not to, the same way the
    request box does (§4.11), and the guard test that walks this app's schema
    cannot catch prose. That residual risk is recorded rather than pretended
    away.

    **Declared, not verified.** A מטצ writes down what they ran. Nobody
    counter-signs it and no attendance is taken, because verification would mean
    a record about the children. Their leader can read it and talk to them about
    it, which is the mechanism this programme actually runs on.

    **Cancelled rather than deleted**, like an event and a post, for a session
    that was planned and did not happen: the fact that it was planned and fell
    through is worth more to a leader than a gap.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="teaching",
        verbose_name="מטצ",
    )

    title = models.CharField(max_length=160, verbose_name="מה לימדתם")
    happened_on = models.DateField(db_index=True, verbose_name="מתי")
    minutes = models.PositiveIntegerField(default=45, verbose_name="כמה זמן")
    # A count. Never a name, never a list, never a link to a person.
    learners = models.PositiveIntegerField(default=0, verbose_name="כמה תלמידים")
    place = models.CharField(
        max_length=200, blank=True, default="", verbose_name="איפה"
    )

    # The two questions worth asking a teenager who just taught, and the reason
    # this is a reflection rather than a timesheet. A leader reading "ניסיתי
    # להסביר לולאות ואיבדתי אותם" has something to talk about; a leader reading
    # "45 דקות, 12 תלמידים" has a number.
    went_well = models.TextField(blank=True, default="", verbose_name="מה עבד")
    was_hard = models.TextField(blank=True, default="", verbose_name="מה היה קשה")

    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="בוטל")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-happened_on", "-created_at"]
        verbose_name = "מפגש הדרכה"
        verbose_name_plural = "פרקטיקום"

    def __str__(self):
        return f"{self.title} · {self.happened_on:%d.%m.%Y}"

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    @property
    def is_planned(self):
        """Ahead of today. Not a second status field: the date already says it."""
        from django.utils import timezone

        return self.happened_on > timezone.localdate()


# --------------------------------------------- the shelf of הדרכות (§4.13)


class OfferedCourse(models.Model):
    """A babook course מטצים is allowed to put in front of its members.

    SPR-M.52. Avi, 2026-09-19: "I want to be able as a leader to decide what
    training I want to expose for my students... it's about just exposing them
    to opportunity to take trainings that are available in Babook."

    **Two layers, and this is the outer one.** Avi picks which of babook's
    catalogue is available to the programme at all; a leader then picks from
    what he picked. Seventeen published courses is not a list to hand a
    fourteen-year-old whole, and it is not a list a leader should have to
    audit either.

    **A slug rather than a foreign key**, which is what `REQUIRED_COURSE_SLUGS`
    already is. It keeps מטצים's tables free of a database-level dependency on
    another app's (Rule 2), and the cost is a slug that can outlive its course,
    which the screens already handle: ההדרכות says "ההדרכה הזאת לא נטענה" and
    carries on.

    **Retiring is a flag, never a delete.** A member part-way through a course
    that is withdrawn keeps their progress and their certificate, because those
    live in babook's tables and never belonged to this row. What stops is new
    members starting it.
    """

    slug = models.CharField(max_length=80, unique=True, verbose_name="מזהה ההדרכה")
    is_active = models.BooleanField(default=True, verbose_name="זמינה")
    note = models.TextField(blank=True, default="", verbose_name="למה היא כאן")
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    added_at = models.DateTimeField(auto_now_add=True)
    # SPR-M.59 (REQ-M.163) — open to any signed-in account, with no leader and
    # no shelf entry. Avi, 2026-10-12: the basics are free for everyone who
    # registers. A flag on the pool rather than a list in code, so root changes
    # the set on the screen that already exists.
    open_to_all = models.BooleanField(default=False, verbose_name="פתוחה לכולם")

    # REQ-M.181, REQ-M.185 - which stage of Atid's year this הדרכה is for. Blank
    # means unstaged: still offered, shown after the staged ones with no tag.
    SCRATCH = "scratch"
    THREE_D = "3d"
    ELECTIVE = "elective"
    STAGE_CHOICES = [
        (SCRATCH, "Scratch"),
        (THREE_D, "תלת־ממד"),
        (ELECTIVE, "הדרכת בחירה"),
    ]
    stage = models.CharField(
        max_length=10, choices=STAGE_CHOICES, blank=True, default="", verbose_name="שלב בשנה"
    )

    class Meta:
        ordering = ["slug"]
        verbose_name = "הדרכה זמינה"
        verbose_name_plural = "הדרכות זמינות"

    def __str__(self):
        return self.slug


class LeaderCourse(models.Model):
    """One leader putting one הדרכה in front of their own מטצים.

    Chosen out of `OfferedCourse`, checked when it is chosen rather than when it
    is read: a course Avi later retires stays on the shelves of the leaders who
    had already picked it, and their members keep what they started.

    **This is exposure, not a requirement.** Avi settled that on 2026-09-16, and
    again on the 19th: certification is the entrance test, both Scratch courses
    and the leader's approval (REQ-M.76), and nothing here changes it. A leader
    who wants more of somebody weighs it in the approval they already give by
    hand. So there is no `required` field, and its absence is the design.
    """

    leader = models.ForeignKey(
        "Leader", on_delete=models.CASCADE, related_name="shelf", verbose_name="מוביל/ה"
    )
    slug = models.CharField(max_length=80, verbose_name="מזהה ההדרכה")
    chosen_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    chosen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]
        unique_together = [("leader", "slug")]
        verbose_name = "הדרכה שהמוביל/ה הציע/ה"
        verbose_name_plural = "הדרכות שהמוביל/ה הציע/ה"

    def __str__(self):
        return f"{self.leader} · {self.slug}"


def new_class_code():
    """A code no leader and no other class holds (REQ-M.171).

    One generator for both kinds of code, and uniqueness checked against both
    tables, so the single "יש לי קוד" box can never meet a string that names
    two things. The space is 72 bits; the loop is a seatbelt.
    """
    while True:
        code = new_join_code()
        if not Leader.objects.filter(join_code=code).exists() and not OpenClass.objects.filter(
            code=code
        ).exists():
            return code


class OpenClass(models.Model):
    """כיתה פתוחה (SPR-M.60, REQ-M.167).

    Anybody who is signed in can open one. Its owner is a מורה on screen and a
    role nowhere: it is derived from owning a row here, the way a leader is
    derived from having a `Leader` row, and nothing stored says "teacher".

    **Nothing joins this half to the official one.** No key to `Leader`,
    `Student`, `StudyClass` or `MatazCertificate`, and none the other way, so no
    query on the roster side can return an open class and an owner can never
    reach a roster (REQ-M.172).

    **The code is a bearer credential** and is shown to the owner alone, like a
    leader's. Replacing it kills the old one at once.
    """

    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="matazim_open_classes",
        verbose_name="בעלים",
    )
    name = models.CharField(max_length=80, verbose_name="שם הכיתה")
    code = models.CharField(
        max_length=32, unique=True, default=new_class_code, db_index=True,
        verbose_name="קוד הכיתה",
    )
    is_open = models.BooleanField(default=True, verbose_name="פתוחה להצטרפות")
    # The owner read "I am not a leader, I cannot certify, I see only this".
    # A decision carries a time (REQ-M.21), and no default on purpose: a row
    # that cannot say when its owner agreed should not exist.
    terms_accepted_at = models.DateTimeField(verbose_name="התנאים אושרו")
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "כיתה פתוחה"
        verbose_name_plural = "כיתות פתוחות"

    def __str__(self):
        return self.name

    @property
    def is_archived(self):
        return self.archived_at is not None


class OpenClassMember(models.Model):
    """Somebody who joined an open class, by their own act (REQ-M.168).

    **Nothing is stored about the person** beyond the fact and the dates. No
    role, stage, score, consent flag or copy of progress: progress is read from
    babook's tables by account (RULE-3), and consent is asked at the moment of
    joining. A snapshot here would be a second answer that drifts.

    **The only inserter is `open_class.join_class`**, and it inserts the
    requesting user. There is no function, form or API field that makes a row
    for somebody else.
    """

    open_class = models.ForeignKey(
        OpenClass, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matazim_open_memberships"
    )
    joined_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        unique_together = [("open_class", "user")]
        ordering = ["joined_at"]
        verbose_name = "חבר/ה בכיתה פתוחה"
        verbose_name_plural = "חברים בכיתות פתוחות"

    def __str__(self):
        return f"{self.user_id} in {self.open_class_id}"

    @property
    def is_active(self):
        return self.ended_at is None


class ProgramMilestone(models.Model):
    """REQ-M.186 - one row of the year's schedule, as the client wrote it.

    Atid's kickoff mail for תשפ״ז carries a table of ten milestones, and Avi's
    instruction on 2026-10-15 was that the site follows it. So the schedule is
    data: a program manager edits a date here, and every screen that says what
    comes next changes with it. It is not a paragraph in a template and not a
    list in a module (Rule 1).

    **Two kinds of date on purpose.** `when_text` is what the client wrote
    ("עד אמצע נובמבר 2026", "דצמבר–פברואר") and is what a person reads.
    `starts_on` and `ends_on` are what the code reads, to say which milestone is
    now and which is next. Keeping both avoids two failures: a screen that
    prints a precise date nobody promised, and a "next" that cannot be worked
    out because the client's wording is a sentence.

    **Order is the table's order.** `order` is the client's own sequence, which
    is the one thing the sorted dates would get wrong ("February" appears twice).

    Owned by an `Institution` like every other institutional row (§4.4), and
    seeded once by a migration; after that the database is the only source.
    """

    SCREENING = "screening"
    TRAINING = "training"
    RECRUITING = "recruiting"
    LEARNING = "learning"
    PEAK = "peak"
    PRACTICUM = "practicum"
    STAGE_CHOICES = [
        (SCREENING, "מיון וקבלה"),
        (TRAINING, "הכשרת מובילים"),
        (RECRUITING, "גיוס תלמידים"),
        (LEARNING, "למידה עצמאית"),
        (PEAK, "יום שיא"),
        (PRACTICUM, "פרקטיקום"),
    ]

    institution = models.ForeignKey(
        "Institution", on_delete=models.CASCADE,
        related_name="milestones", verbose_name="מוסד",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="סדר")
    when_text = models.CharField(max_length=80, verbose_name="תאריך, כפי שנכתב")
    starts_on = models.DateField(verbose_name="מתחיל")
    ends_on = models.DateField(null=True, blank=True, verbose_name="מסתיים")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=LEARNING)
    title = models.CharField(max_length=120, verbose_name="שלב")
    activities = models.TextField(blank=True, default="", verbose_name="עיקרי הפעילות")
    is_peak_day = models.BooleanField(default=False, verbose_name="יום שיא")

    class Meta:
        ordering = ["order", "starts_on"]
        verbose_name = "אבן דרך"
        verbose_name_plural = "אבני דרך"

    def __str__(self):
        return f"{self.when_text} · {self.title}"

    @property
    def last_day(self):
        return self.ends_on or self.starts_on


class SiteUpdate(models.Model):
    """REQ-M.184 - one note about what changed on the site.

    Atid's list for the site includes "עדכון שינויים באתר": the people who use
    the site are told when it changes. A note is a row, not a deploy log: a
    program manager writes it in plain words, everybody in the programme can read
    the list, and posting one rings each person's bell once.

    Owned by an `Institution` like every other institutional row (§4.4).
    """

    institution = models.ForeignKey(
        "Institution", on_delete=models.CASCADE,
        related_name="site_updates", verbose_name="מוסד",
    )
    title = models.CharField(max_length=160, verbose_name="מה השתנה")
    body = models.TextField(blank=True, default="", verbose_name="פרטים")
    posted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pinned = models.BooleanField(default=False, verbose_name="להצמיד למעלה")
    posted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-pinned", "-posted_at"]
        verbose_name = "עדכון באתר"
        verbose_name_plural = "עדכונים באתר"

    def __str__(self):
        return self.title
