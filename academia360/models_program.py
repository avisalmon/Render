"""Academia360's data, sections 4 to 9 of docs/academia360/data_model.md:
taking part in the program, success measures, budget, review and letters,
the public talking back, AI, plus the audit's access log and the models the
spec added after the data model (meetings 4.3, requests to join 4.5).

Visibility, as in models.py: `CIRCLE`, `INSTITUTION_PATH`, `OWN_PATH`, and
two refinements academia360/access.py understands:

- `PUBLIC_Q`: rows matching it are public although the model is not (the
  mandatory KPI definitions);
- `INSTITUTION_Q`: the institution-circle rule opens only rows matching it
  (a letter once it is sent, and nothing before);
- `CIRCLE = PRIVATE`: the owner and the admin, nobody else (a person's AI
  conversations).

Everything submitted lives in private storage, never under MEDIA_ROOT.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Q

from .models import (
    COMMITTEE,
    INSTITUTION,
    PUBLIC,
    AcademicYear,
    Criterion,
    Institution,
    Program,
    ReviewQuestion,
    Row,
    StudyProgram,
    Unit,
)

PRIVATE = "private"


class PrivateStorage(FileSystemStorage):
    """Files on the persistent disk, outside MEDIA_ROOT, with no URL of their
    own. Reads settings on every use and never touches the disk at import
    (methodology 17)."""

    @property
    def base_location(self):
        return str(settings.ACADEMIA360_PRIVATE_DIR)

    @property
    def location(self):
        import os
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


PRIVATE_FILES = PrivateStorage()
_remote = {"built": False, "storage": None, "problem": ""}


def private_storage():
    """A private Google Cloud Storage bucket of the app's own when one is
    configured (`ACADEMIA360_GCS_BUCKET` plus a key limited to that bucket,
    the Books pattern), else the private folder on the persistent disk. A
    bad key never takes the site down: it is logged and the disk is used."""
    if _remote["built"]:
        return _remote["storage"] or PRIVATE_FILES
    _remote["built"] = True
    bucket = getattr(settings, "ACADEMIA360_GCS_BUCKET", "")
    if bucket:
        try:
            import json
            import logging
            from datetime import timedelta

            from storages.backends.gcloud import GoogleCloudStorage

            raw = getattr(settings, "ACADEMIA360_GCS_CREDENTIALS_JSON", "")
            credentials = None
            if raw:
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_info(json.loads(raw.strip(), strict=False))
            storage = GoogleCloudStorage(bucket_name=bucket, location="academia360", credentials=credentials,
                                         default_acl=None, querystring_auth=True, expiration=timedelta(minutes=10),
                                         file_overwrite=False)
            storage.base_url = None
            _remote["storage"] = storage
        except Exception as exc:  # noqa: BLE001  a broken key is a log line, not an outage
            _remote["problem"] = f"{exc.__class__.__name__}: {str(exc)[:200]}"
            logging.getLogger(__name__).error("academia360: bucket configured but unusable, using the disk: %s",
                                              _remote["problem"])
    return _remote["storage"] or PRIVATE_FILES


def reset_storage_for_tests():
    _remote.update(built=False, storage=None, problem="")


def submitted_path(instance, filename):
    inst = instance.submission.participation.institution_id
    return f"submissions/{inst}/{instance.submission_id}/{filename}"


def letter_path(instance, filename):
    inst = instance.submission.participation.institution_id
    return f"letters/{inst}/{instance.submission_id}/{filename}"


# ----------------------------------------------------- 4. taking part

class Allocation(Row):
    """How much each institution may ask for, and its base numbers (the
    tracking sheet). Committee only: a leader sees no amounts (spec 2.6.5)."""

    CIRCLE = COMMITTEE

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="allocations")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="allocations")
    undergrad_students = models.PositiveIntegerField(null=True, blank=True, help_text="תשפ״ד")
    approved_programs = models.PositiveIntegerField(null=True, blank=True)
    allocation_thousands_nis = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("program", "institution")]


class Participation(Row):
    """One institution in one program: did it apply, where it stands now."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "institution"

    STATUS = [("invited", "הוזמן"), ("submitted", "הגיש"), ("under_review", "בסקירה"), ("responded", "נענה"),
              ("approved", "אושר"), ("declined", "נדחה"), ("reporting", "מדווח"), ("did_not_apply", "לא ניגש")]

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="participations")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="participations")
    applied = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=STATUS, default="invited")
    first_submitted_at = models.DateField(null=True, blank=True)
    lead_title = models.CharField(max_length=200, blank=True, help_text="Who leads it at the institution, as shown publicly")
    committee_notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("program", "institution")]
        ordering = ["program_id", "institution__name_he"]

    def __str__(self):
        return f"{self.institution} · {self.program.short_name or self.program}"


class Submission(Row):
    """One package the institution sent in. Each is reviewed and answered on
    its own, so the cycle repeats cleanly (spec 2.1 step 6)."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "participation__institution"

    KINDS = [("proposal", "הצעה"), ("updated_plan", "תכנית מעודכנת"), ("execution_report", "דוח ביצוע"),
             ("kpi_report", "דוח מדדים"), ("budget_report", "דוח תקציבי")]
    STATUS = [("draft", "טיוטה"), ("submitted", "הוגש"), ("under_review", "בסקירה"), ("responded", "נענה")]

    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="submissions")
    kind = models.CharField(max_length=20, choices=KINDS, default="proposal")
    academic_year = models.ForeignKey(AcademicYear, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    submitted_at = models.DateField(null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="a360_submissions")
    status = models.CharField(max_length=14, choices=STATUS, default="draft")
    cover_note = models.TextField(blank=True)

    class Meta:
        ordering = ["participation_id", "-submitted_at", "-pk"]

    def __str__(self):
        return f"{self.participation.institution} · {self.get_kind_display()}"

    @property
    def institution(self):
        return self.participation.institution


class SubmittedFile(Row):
    """One file of a submission, in private storage."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    KINDS = [("plan", "התכנית"), ("annex_a", "נספח א׳ מדדים"), ("annex_b", "נספח ב׳ תקציב"),
             ("commitment", "התחייבות למימון משלים"), ("declaration", "הצהרה"), ("cover_letter", "מכתב נלווה"),
             ("signature", "דף חתימות"), ("report", "דוח"), ("research", "מחקר רקע"), ("other", "אחר")]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(max_length=14, choices=KINDS, default="other")
    file = models.FileField(upload_to=submitted_path, storage=private_storage)
    original_name = models.CharField(max_length=300)
    size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="a360_uploads")
    extracted_text = models.TextField(blank=True)
    extracted_at = models.DateTimeField(null=True, blank=True, help_text="When the text was last read out of the file")
    extraction_note = models.CharField(max_length=200, blank=True,
                                       help_text="What the extraction found: pages, sheets, no text, unsupported, an error")

    def __str__(self):
        return self.original_name

    @property
    def extension(self):
        return (self.original_name or self.file.name or "").rsplit(".", 1)[-1].lower() if "." in (self.original_name or self.file.name or "") else ""


class ContactPerson(Row):
    """Who speaks for the institution on the program, as the submission
    names them. Committee material (spec 4.9)."""

    CIRCLE = COMMITTEE

    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=160)
    title = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    is_primary = models.BooleanField(default=False)


class GraduateProfile(Row):
    """דמות הבוגר: the graduate the institution says it is shaping."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="graduate_profile")
    text = models.TextField()


class GraduateSkill(Row):
    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "profile__submission__participation__institution"

    profile = models.ForeignKey(GraduateProfile, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["profile_id", "order"]


class Standard(Row):
    """The institution's תו תקן: what makes a program count as updated."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="standard")
    description = models.TextField()
    levels = models.CharField(max_length=200, blank=True, help_text="institution / faculty / program / course")
    minimum_bar = models.TextField(blank=True)
    review_mechanism = models.TextField(blank=True)


class PlanProgram(Row):
    """A study program the plan commits to update, with its state."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    STATUS = [("planned", "מתוכנן"), ("in_progress", "בתהליך"), ("updated", "עודכן")]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="plan_programs")
    study_program = models.ForeignKey(StudyProgram, on_delete=models.CASCADE, related_name="plan_rows")
    planned_year = models.ForeignKey(AcademicYear, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=12, choices=STATUS, default="planned")
    students_covered = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("submission", "study_program")]


class PlanComponent(Row):
    """One concrete thing the plan does, under a criterion."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="components")
    criterion = models.ForeignKey(Criterion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    years_active = models.CharField(max_length=60, blank=True)
    leverages_other_program = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["submission_id", "order"]


class Governance(Row):
    """The institutional set-up for running the program."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="governance")
    lead_name = models.CharField(max_length=160, blank=True)
    lead_title = models.CharField(max_length=160, blank=True)
    steering_body = models.TextField(blank=True)
    reward_mechanism = models.TextField(blank=True)
    description = models.TextField(blank=True)


# ----------------------------------------------------------- 5. KPIs

class KpiDefinition(Row):
    """A measure: the mandatory ones ות״ת set for everyone (public, no
    submission) and the 2 to 4 an institution adds (its own)."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"
    PUBLIC_Q = Q(is_mandatory=True)

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="kpis")
    submission = models.ForeignKey(Submission, null=True, blank=True, on_delete=models.CASCADE, related_name="kpis")
    name = models.CharField(max_length=300)
    explanation = models.TextField(blank=True)
    how_measured = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["program_id", "-is_mandatory", "order"]

    def __str__(self):
        return self.name[:80]


class KpiValue(Row):
    """One number for one KPI in one year: baseline, forecast or actual."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "participation__institution"

    KINDS = [("baseline", "מצב נוכחי"), ("forecast", "צפי"), ("actual", "בפועל")]

    kpi = models.ForeignKey(KpiDefinition, on_delete=models.CASCADE, related_name="values")
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="kpi_values")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=KINDS)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    text_value = models.CharField(max_length=200, blank=True, help_text="When the sheet held words, not a number")
    notes = models.TextField(blank=True)
    reported_in = models.ForeignKey(Submission, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        unique_together = [("kpi", "participation", "academic_year", "kind")]


class TargetChoice(Row):
    """Which of the two 20% targets the institution chose."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "participation__institution"

    participation = models.OneToOneField(Participation, on_delete=models.CASCADE, related_name="target")
    basis = models.CharField(max_length=10, choices=[("programs", "תכניות לימוד"), ("students", "סטודנטים")])
    total_programs = models.PositiveIntegerField(null=True, blank=True)
    total_undergrads = models.PositiveIntegerField(null=True, blank=True)
    rationale = models.TextField(blank=True)


# --------------------------------------------------------- 6. budget

class BudgetLine(Row):
    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    CATEGORIES = [("staff", "כוח אדם"), ("activity", "פעילות"), ("infrastructure", "תשתיות"), ("other", "אחר")]
    KINDS = [("planned", "מתוכנן"), ("transferred", "הועבר"), ("spent", "הוצא")]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="budget_lines")
    academic_year = models.ForeignKey(AcademicYear, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    category = models.CharField(max_length=16, choices=CATEGORIES, default="other")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=12, choices=KINDS, default="planned")
    amount_nis = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)


class Commitment(Row):
    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    KINDS = [("matching", "מימון משלים"), ("additions_only", "תקצוב לתוספות בלבד"), ("other", "אחר")]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="commitments")
    kind = models.CharField(max_length=16, choices=KINDS)
    amount_nis = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    signed_by = models.CharField(max_length=200, blank=True)
    signed_at = models.DateField(null=True, blank=True)
    file = models.ForeignKey(SubmittedFile, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")


class CommunityShare(Row):
    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "submission__participation__institution"

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="community_share")
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    amount_nis = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)


# ------------------------------------------- 7. review, decision, letter

class Analysis(Row):
    """The committee-side reading of a submission against the criteria."""

    CIRCLE = COMMITTEE

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="analysis")
    summary = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="a360_analyses")
    drafted_by_ai = models.BooleanField(default=False)
    confirmed = models.BooleanField(default=False)


class CriterionFinding(Row):
    CIRCLE = COMMITTEE

    KINDS = [("finding", "ממצא"), ("strength", "חוזקה"), ("challenge", "אתגר")]

    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="findings")
    criterion = models.ForeignKey(Criterion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=10, choices=KINDS, default="finding")
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["analysis_id", "order"]


class Review(Row):
    """One committee member's review of one submission, following the form."""

    CIRCLE = COMMITTEE
    OWN_PATH = "reviewer"

    STATUS = [("in_progress", "בעבודה"), ("done", "הושלמה")]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_reviews")
    status = models.CharField(max_length=12, choices=STATUS, default="in_progress")
    done_at = models.DateTimeField(null=True, blank=True)
    overall_note = models.TextField(blank=True)

    class Meta:
        unique_together = [("submission", "reviewer")]


class ReviewAnswer(Row):
    CIRCLE = COMMITTEE
    OWN_PATH = "review__reviewer"

    CHECKS = [("yes", "כן"), ("partly", "חלקית"), ("no", "לא"), ("na", "לא רלוונטי")]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ReviewQuestion, on_delete=models.CASCADE, related_name="answers")
    answer = models.CharField(max_length=8, choices=CHECKS, blank=True, help_text="The checklist mark")
    main_points = models.TextField(blank=True)
    improvement_notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("review", "question")]


class Discussion(Row):
    CIRCLE = COMMITTEE

    submission = models.ForeignKey(Submission, null=True, blank=True, on_delete=models.CASCADE, related_name="discussions")
    program = models.ForeignKey(Program, null=True, blank=True, on_delete=models.CASCADE, related_name="discussions")
    title = models.CharField(max_length=200)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="a360_discussions")
    summary = models.TextField(blank=True, help_text="An AI or human summary, confirmed by a member")

    def __str__(self):
        return self.title


class DiscussionPost(Row):
    CIRCLE = COMMITTEE
    OWN_PATH = "author"

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="a360_posts")
    body = models.TextField(help_text="Markdown; sanitized before it is shown")
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["discussion_id", "created_at"]


class Meeting(Row):
    """A committee meeting: date, who came, agenda, notes, a summary with
    decisions and action items (spec 4.3)."""

    CIRCLE = COMMITTEE

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="meetings")
    held_at = models.DateTimeField()
    title = models.CharField(max_length=200, blank=True)
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="a360_meetings")
    agenda = models.ManyToManyField(Submission, blank=True, related_name="meetings")
    notes = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    action_items = models.TextField(blank=True)
    summary_confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                             related_name="+")

    class Meta:
        ordering = ["-held_at"]


class Decision(Row):
    """The chair's decision on a submission (spec 2.6.3)."""

    CIRCLE = COMMITTEE

    OUTCOMES = [("approved", "אושר"), ("conditional", "אושר בתנאים"), ("revise", "לתיקון והגשה מחדש"),
                ("declined", "נדחה")]

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="decision")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="a360_decisions")
    outcome = models.CharField(max_length=12, choices=OUTCOMES)
    approved_amount_nis = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    conditions = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)


class LetterTemplateSection(Row):
    """A general-comments section written once per round and used by every
    letter of that round."""

    CIRCLE = COMMITTEE

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="letter_templates")
    academic_year = models.ForeignKey(AcademicYear, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=200)
    body = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["program_id", "order"]


class ResponseLetter(Row):
    """The committee's letter back. A draft is the committee's; once sent,
    the institution's leaders read it too (spec 2.3)."""

    CIRCLE = COMMITTEE
    INSTITUTION_PATH = "submission__participation__institution"
    INSTITUTION_Q = Q(sent_at__isnull=False)

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name="letter")
    addressee_name = models.CharField(max_length=160, blank=True)
    addressee_title = models.CharField(max_length=160, blank=True)
    drafted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="a360_letters_drafted")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="a360_letters_sent")
    sent_at = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to=letter_path, storage=private_storage, blank=True,
                            help_text="The signed PDF, if any")
    extracted_text = models.TextField(blank=True)

    @property
    def is_sent(self):
        return self.sent_at is not None


class LetterSection(Row):
    CIRCLE = COMMITTEE
    INSTITUTION_PATH = "letter__submission__participation__institution"
    INSTITUTION_Q = Q(letter__sent_at__isnull=False)

    KINDS = [("general", "הערות כלליות"), ("specific", "הערות פרטניות"), ("closing", "סיום")]

    letter = models.ForeignKey(ResponseLetter, on_delete=models.CASCADE, related_name="sections")
    kind = models.CharField(max_length=10, choices=KINDS, default="specific")
    template = models.ForeignKey(LetterTemplateSection, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="uses")
    body = models.TextField(blank=True, help_text="Empty when the template carries the text")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["letter_id", "order"]

    @property
    def text(self):
        return self.body or (self.template.body if self.template_id else "")


# --------------------------------------------- 8. the public talks back

class RoleRequest(Row):
    """A signed-in person asks to be a leader or a committee member; the
    admin approves or declines (spec 4.5)."""

    CIRCLE = COMMITTEE
    OWN_PATH = "user"

    STATUS = [("open", "ממתין"), ("approved", "אושר"), ("declined", "נדחה")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_role_requests")
    role_kind = models.CharField(max_length=20, choices=[("committee", "חבר/ת ועדה"), ("leader", "מוביל/ת תכנית במוסד")])
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=160, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="open")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True)


class PublicComment(Row):
    CIRCLE = PUBLIC
    OWN_PATH = "author"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_comments")
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.CASCADE, related_name="comments")
    researcher = models.ForeignKey("Researcher", null=True, blank=True, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField(help_text="Sanitized before it is shown")
    hidden = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]


class Like(Row):
    CIRCLE = PUBLIC
    OWN_PATH = "user"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_likes")
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.CASCADE, related_name="likes")
    researcher = models.ForeignKey("Researcher", null=True, blank=True, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        unique_together = [("user", "institution", "researcher")]


class CorrectionProposal(Row):
    """"This fact is wrong, here is the right one." Committee members see
    them; the admin or a chair accepts (spec 2.6.6)."""

    CIRCLE = COMMITTEE
    OWN_PATH = "proposer"

    STATUS = [("open", "פתוחה"), ("accepted", "התקבלה"), ("rejected", "נדחתה")]

    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_corrections")
    model = models.CharField(max_length=80, help_text="app_label.ModelName")
    row_id = models.CharField(max_length=40)
    field = models.CharField(max_length=80, blank=True)
    current_value = models.TextField(blank=True)
    proposed_value = models.TextField()
    reason = models.TextField(blank=True, help_text="Where the right value comes from")
    status = models.CharField(max_length=10, choices=STATUS, default="open")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)


# ------------------------------------------------------------------ 9. AI

class AiConversation(Row):
    CIRCLE = PRIVATE
    OWN_PATH = "user"

    KINDS = [("search", "חיפוש חכם"), ("proposal", "דיון על ההצעה"), ("guide", "הנחיות"), ("kpi", "מדדים"),
             ("draft", "ניסוח")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_conversations")
    kind = models.CharField(max_length=10, choices=KINDS, default="search")
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    submission = models.ForeignKey(Submission, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class AiMessage(Row):
    CIRCLE = PRIVATE
    OWN_PATH = "conversation__user"

    ROLES = [("user", "user"), ("assistant", "assistant"), ("system", "system")]

    conversation = models.ForeignKey(AiConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLES)
    body = models.TextField()
    cited = models.TextField(blank=True, help_text="Chunk or row references, one per line")
    model = models.CharField(max_length=60, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)

    class Meta:
        ordering = ["conversation_id", "created_at"]


class IndexChunk(Row):
    """A piece of text the search retrieves over. Carries the circle and the
    institution of its source, so retrieval filters by what the asker may
    see before the model ever sees it (spec 1.4)."""

    CIRCLE = COMMITTEE
    INSTITUTION_PATH = "institution"

    source_model = models.CharField(max_length=80)
    source_id = models.CharField(max_length=40)
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.CASCADE, related_name="chunks")
    circle = models.CharField(max_length=12, choices=[(PUBLIC, "public"), (INSTITUTION, "institution"),
                                                      (COMMITTEE, "committee")])
    text = models.TextField()
    embedding = models.BinaryField(null=True, blank=True)
    built_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["source_model", "source_id"])]


class AiUsage(Row):
    CIRCLE = PRIVATE
    OWN_PATH = "user"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_usage")
    date = models.DateField()
    calls = models.PositiveIntegerField(default=0)
    tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    class Meta:
        unique_together = [("user", "date")]


# ---------------------------------------------------------------- 10. audit

class AccessLog(Row):
    """Every opening or download of a submitted file or a letter."""

    CIRCLE = COMMITTEE

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="a360_access")
    target_model = models.CharField(max_length=80)
    target_id = models.CharField(max_length=40)
    action = models.CharField(max_length=10, choices=[("view", "view"), ("download", "download")], default="view")

    class Meta:
        ordering = ["-created_at"]
