"""dentist's data (docs/dentist/data_model.md, approved 2026-10-26).

Four things shape everything here, and each is a line of code somewhere
below rather than a sentence in a document:

1. **Everything belongs to a clinic.** Every model has a `clinic` or reaches
   one through its patient, and `access.py` scopes every query to one.
2. **A patient record can start with a first name.** Every other field on
   `Patient` is blank-able.
3. **Medical facts are dated, authored rows, never overwritten.** The chart
   is the latest `ToothState` per tooth and surface; a signed `Visit` is
   read-only.
4. **Every look is logged** in `AccessLog`.

Reverse accessors on `User` are prefixed `dn_` so they cannot collide with
another app's (CrashTech learned this against the 2026 platform).
"""

import secrets
import uuid as _uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import media_storage, upload_path

USER = settings.AUTH_USER_MODEL

# Patient-facing languages (spec Rule 10.1). The language of India is not
# named yet; `hi` stands in and falls back to English until the clinic says.
LANGUAGES = [
    ("he", "עברית"), ("en", "English"), ("ru", "Русский"), ("ar", "العربية"),
    ("ti", "ትግርኛ"), ("hi", "हिन्दी"),
]
RTL_LANGUAGES = {"he", "ar"}


def new_token():
    return secrets.token_urlsafe(24)


# ------------------------------------------------------- the clinic, people


class Clinic(models.Model):
    """One clinic. The pilot is one row; a second clinic is a second row that
    shares nothing with the first (Rule 3.1)."""

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    timezone_name = models.CharField(max_length=64, default="Asia/Jerusalem")
    address = models.CharField(max_length=240, blank=True, default="")
    # Which patient-facing languages this clinic offers, as codes.
    languages = models.JSONField(default=list, blank=True)
    # Rule 2.7: the banner is on while this is true, and it cannot be turned
    # off in the pilot from any screen.
    is_pilot = models.BooleanField(default=True)
    opening_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClinicMember(models.Model):
    """A person's role at one clinic (Rule 3.2). The app's own model with a
    link to the shared account; it never adds a field to `User`."""

    DENTIST, ADMIN = "dentist", "admin"
    ROLES = [(DENTIST, "Dentist"), (ADMIN, "Administrator")]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="dn_memberships")
    role = models.CharField(max_length=10, choices=ROLES)
    # What patients see: a dentist may prefer "Dr. Noa" to a full name.
    display_name = models.CharField(max_length=120, blank=True, default="")
    active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["clinic", "user"], name="dn_one_membership_per_clinic")]
        ordering = ["clinic", "role", "id"]

    def __str__(self):
        return f"{self.display_name or self.user} ({self.role} at {self.clinic})"


class Invitation(models.Model):
    """A role granted to an email before the person has an account, redeemed
    on sign-up (Rule 3.2). The only way a staff role comes to exist."""

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=ClinicMember.ROLES)
    token = models.CharField(max_length=64, unique=True, default=new_token)
    invited_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-sent_at"]

    @property
    def is_pending(self):
        return self.accepted_at is None


class Chair(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="chairs")
    name = models.CharField(max_length=60)
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


# ------------------------------------------------------------- the patient


def next_clinic_number(clinic):
    """The number on the patient's card: made by the app, unique per clinic,
    never an Israeli ID (Rule 4.1, 4.2)."""
    last = clinic.patients.order_by("-id").values_list("clinic_number", flat=True).first()
    try:
        n = int(last.split("-")[-1]) + 1 if last else 1
    except ValueError:
        n = clinic.patients.count() + 1
    return f"{clinic.slug[:6].upper()}-{n:05d}"


class Patient(models.Model):
    """One person the clinic treats. Starts with a first name (Rule 4.1)."""

    ID_KINDS = [
        ("none", "No identification"), ("passport", "Passport"), ("unhcr", "UNHCR number"),
        ("clinic", "Clinic's own number"), ("other", "Other"),
    ]
    SEX = [("", "Not recorded"), ("f", "Female"), ("m", "Male"), ("x", "Other")]
    ACTIVE, ARCHIVED = "active", "archived"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="patients")
    clinic_number = models.CharField(max_length=24)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True, default="")
    preferred_language = models.CharField(max_length=5, choices=LANGUAGES, default="en")
    needs_interpreter = models.BooleanField(default=False)
    phone = models.CharField(max_length=32, blank=True, default="")
    whatsapp = models.CharField(max_length=32, blank=True, default="")
    # A year, not a date: enough for treatment, less to leak (Rule 4.3).
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEX, blank=True, default="")
    id_kind = models.CharField(max_length=10, choices=ID_KINDS, default="none")
    id_number = models.CharField(max_length=64, blank=True, default="")
    front_desk_notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=[(ACTIVE, "Active"), (ARCHIVED, "Archived")], default=ACTIVE)
    # The patient's own login, once they have one (Rule 3.4).
    user = models.OneToOneField(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="dn_patient")
    is_demo = models.BooleanField(default=False)
    created_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["clinic", "clinic_number"], name="dn_clinic_number_unique")]
        ordering = ["first_name", "last_name", "id"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.clinic_number

    def save(self, *args, **kwargs):
        if not self.clinic_number:
            self.clinic_number = next_clinic_number(self.clinic)
        super().save(*args, **kwargs)

    @property
    def alerts(self):
        return self.history.filter(alert=True, active=True)


class PatientLink(models.Model):
    """The one-time link that connects a patient's new account to their
    record (Rule 3.4): expires, works once, logged."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="links")
    token = models.CharField(max_length=64, unique=True, default=new_token)
    made_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    made_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() <= self.expires_at


class HistoryItem(models.Model):
    """One fact of medical history, with who noted it and when (Rule 4.4)."""

    KINDS = [("allergy", "Allergy"), ("medication", "Medication"), ("condition", "Condition"), ("other", "Other")]
    # The short coded list; "other" plus free text covers the rest.
    WHAT = [
        ("penicillin", "Penicillin allergy"), ("latex", "Latex allergy"),
        ("anaesthetic", "Local anaesthetic allergy"), ("other_allergy", "Other allergy"),
        ("anticoagulant", "Blood thinners"), ("bisphosphonate", "Bisphosphonates"),
        ("other_medication", "Other medication"),
        ("diabetes", "Diabetes"), ("heart", "Heart condition"), ("hypertension", "High blood pressure"),
        ("pregnancy", "Pregnancy"), ("epilepsy", "Epilepsy"), ("bleeding", "Bleeding disorder"),
        ("infectious", "Infectious disease"), ("other_condition", "Other condition"),
    ]
    # These change what a dentist may safely do, so they alert by default.
    ALERT_BY_DEFAULT = {"penicillin", "latex", "anaesthetic", "anticoagulant", "bisphosphonate",
                        "diabetes", "heart", "pregnancy", "epilepsy", "bleeding", "infectious"}

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="history")
    kind = models.CharField(max_length=12, choices=KINDS)
    what = models.CharField(max_length=24, choices=WHAT)
    detail = models.CharField(max_length=240, blank=True, default="")
    alert = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    noted_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    noted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-alert", "-noted_at"]

    def save(self, *args, **kwargs):
        if self._state.adding and self.what in self.ALERT_BY_DEFAULT:
            self.alert = True
        super().save(*args, **kwargs)


class AccessLog(models.Model):
    """Who looked, who changed, who exported (Rule 4.5). Ids only, never
    names or medical text (Rule 9.4)."""

    ACTIONS = [("viewed", "Viewed"), ("edited", "Edited"), ("exported", "Exported"),
               ("printed", "Printed"), ("deleted", "Deleted")]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="access_log")
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name="access_log")
    user = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="dn_access_log")
    action = models.CharField(max_length=10, choices=ACTIONS)
    what = models.CharField(max_length=120, blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]


# ---------------------------------------------------------- the mouth, plan


FDI_ADULT = [n for n in range(11, 49) if n % 10 in range(1, 9)]
FDI_CHILD = [n for n in range(51, 86) if n % 10 in range(1, 6)]
SURFACES = [("", "Whole tooth"), ("M", "Mesial"), ("D", "Distal"), ("B", "Buccal"), ("L", "Lingual"), ("O", "Occlusal")]


class ToothState(models.Model):
    """One observation of one tooth, or one surface of it, at one moment
    (Rule 5.1). The chart on screen is the latest row per (tooth, surface)."""

    CONDITIONS = [
        ("sound", "Sound"), ("decay", "Decay"), ("filling", "Filling"), ("crown", "Crown"),
        ("root_canal", "Root canal"), ("missing", "Missing"), ("implant", "Implant"),
        ("fracture", "Fracture"), ("to_extract", "To extract"), ("other", "Other"),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="teeth")
    tooth = models.PositiveSmallIntegerField()
    surface = models.CharField(max_length=1, choices=SURFACES, blank=True, default="")
    condition = models.CharField(max_length=12, choices=CONDITIONS)
    note = models.CharField(max_length=240, blank=True, default="")
    noted_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    noted_at = models.DateTimeField(default=timezone.now)
    visit = models.ForeignKey("Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="tooth_states")

    class Meta:
        # The chart is the latest row per tooth and surface. Two rows in the
        # same second tie on time, and then the later id is the later
        # observation; without "-id" the older one won (the D.1 suite).
        ordering = ["tooth", "surface", "-noted_at", "-id"]


class ProcedureType(models.Model):
    """The clinic's catalogue, seeded once from a standard list and editable
    (Rule 6.2)."""

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="procedures")
    code = models.CharField(max_length=16)
    name_en = models.CharField(max_length=120)
    name_he = models.CharField(max_length=120, blank=True, default="")
    needs_consent = models.BooleanField(default=False)
    default_cost = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["clinic", "code"], name="dn_procedure_code_unique")]
        ordering = ["order", "code"]

    def __str__(self):
        return self.name_en


class PlanItem(models.Model):
    """One thing to do, usually to one tooth, in an order (Rule 5.3)."""

    STATUSES = [("planned", "Planned"), ("in_progress", "In progress"), ("done", "Done"), ("dropped", "Dropped")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="plan")
    tooth = models.PositiveSmallIntegerField(null=True, blank=True)
    procedure = models.ForeignKey(ProcedureType, on_delete=models.PROTECT, related_name="+")
    priority = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUSES, default="planned")
    note = models.CharField(max_length=240, blank=True, default="")
    planned_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    planned_at = models.DateTimeField(default=timezone.now)
    done_in = models.ForeignKey("Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="completed_items")

    class Meta:
        ordering = ["status", "priority", "id"]


# ---------------------------------------------------- visits, files, consent


class Visit(models.Model):
    """One patient in one chair with one dentist (Rule 6.1). Signed means
    read-only (Rule 6.3)."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="visits")
    dentist = models.ForeignKey(ClinicMember, on_delete=models.PROTECT, related_name="visits")
    chair = models.ForeignKey(Chair, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    appointment = models.OneToOneField("Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="visit")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-started_at"]

    @property
    def is_signed(self):
        return self.signed_at is not None


class VisitProcedure(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="procedures")
    procedure = models.ForeignKey(ProcedureType, on_delete=models.PROTECT, related_name="+")
    tooth = models.PositiveSmallIntegerField(null=True, blank=True)
    surface = models.CharField(max_length=1, choices=SURFACES, blank=True, default="")
    anaesthetic = models.CharField(max_length=120, blank=True, default="")
    note = models.CharField(max_length=240, blank=True, default="")
    plan_item = models.ForeignKey(PlanItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["id"]


class Attachment(models.Model):
    """A private file (Rule 6.4): X-ray, photo, scanned consent, document."""

    KINDS = [("xray", "X-ray"), ("photo", "Photo"), ("consent", "Consent"), ("document", "Document")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="attachments")
    visit = models.ForeignKey(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    tooth = models.PositiveSmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=KINDS, default="photo")
    file = models.FileField(upload_to=upload_path, storage=media_storage)
    caption = models.CharField(max_length=200, blank=True, default="")
    taken_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    # Kept here; never read from the file on a page (mistake 37).
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-taken_at"]


class Consent(models.Model):
    """Informed consent with the wording agreed to (Rule 6.5)."""

    HOW = [("on_screen", "On screen"), ("paper", "On paper, scanned")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="consents")
    plan_item = models.ForeignKey(PlanItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="consents")
    procedure = models.ForeignKey(ProcedureType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    language = models.CharField(max_length=5, choices=LANGUAGES, default="en")
    text_version = models.CharField(max_length=40)
    text = models.TextField()
    given_at = models.DateTimeField(default=timezone.now)
    how = models.CharField(max_length=10, choices=HOW, default="on_screen")
    attachment = models.ForeignKey(Attachment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    witnessed_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-given_at"]


# ---------------------------------------------------------------- the day


class Shift(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="shifts")
    dentist = models.ForeignKey(ClinicMember, on_delete=models.CASCADE, related_name="shifts")
    chair = models.ForeignKey(Chair, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    note = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        ordering = ["starts_at"]


class Appointment(models.Model):
    """A booked slot or a walk-in: one model, two kinds (Rule 7.2)."""

    BOOKED, WALK_IN = "booked", "walk_in"
    KINDS = [(BOOKED, "Booked"), (WALK_IN, "Walk-in")]
    STATUSES = [
        ("booked", "Booked"), ("arrived", "Arrived"), ("in_chair", "In the chair"), ("done", "Done"),
        ("no_show", "Did not come"), ("left", "Left before being seen"), ("cancelled", "Cancelled"),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    dentist = models.ForeignKey(ClinicMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    chair = models.ForeignKey(Chair, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    kind = models.CharField(max_length=8, choices=KINDS, default=BOOKED)
    starts_at = models.DateTimeField(null=True, blank=True)
    expected_minutes = models.PositiveSmallIntegerField(default=30)
    arrived_at = models.DateTimeField(null=True, blank=True)
    pain_level = models.PositiveSmallIntegerField(null=True, blank=True)  # 0 to 10, walk-ins
    reason = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUSES, default="booked")
    created_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "arrived_at", "id"]


class ReminderTemplate(models.Model):
    """The wording per clinic and language. Only these placeholders exist:
    {first_name} {date} {time} {clinic} {address}. Nothing medical can be
    placed in it (Rule 7.5), and a test proves the text has nothing else."""

    KINDS = [("reminder", "Reminder"), ("confirmation", "Confirmation"), ("cancelled", "Cancelled")]
    PLACEHOLDERS = {"first_name", "date", "time", "clinic", "address"}

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="reminder_templates")
    language = models.CharField(max_length=5, choices=LANGUAGES)
    kind = models.CharField(max_length=14, choices=KINDS, default="reminder")
    text = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["clinic", "language", "kind"], name="dn_template_unique")]


class Reminder(models.Model):
    CHANNELS = [("sms", "SMS"), ("whatsapp", "WhatsApp")]
    STATUSES = [("scheduled", "Scheduled"), ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled")]

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="reminders")
    channel = models.CharField(max_length=10, choices=CHANNELS)
    language = models.CharField(max_length=5, choices=LANGUAGES)
    scheduled_for = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="scheduled")
    provider_id = models.CharField(max_length=120, blank=True, default="")
    error = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        ordering = ["scheduled_for"]


# ------------------------------------------------------------------- money


class CostRecord(models.Model):
    """Something that cost money. A record; the app never takes, asks for or
    calculates a payment (Rule 8.1)."""

    KINDS = [("medicine", "Medicine"), ("lab", "Lab work"), ("material", "Materials"), ("other", "Other")]
    PAID_BY = [("clinic", "The clinic"), ("donor", "A donor"), ("patient", "The patient"), ("other", "Other")]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="costs")
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name="costs")
    visit = models.ForeignKey(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name="costs")
    kind = models.CharField(max_length=10, choices=KINDS)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    currency = models.CharField(max_length=3, default="ILS")
    paid_by = models.CharField(max_length=10, choices=PAID_BY)
    recorded_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-at"]


# Every model, for the isolation test and the export: anything new added
# here has to carry a clinic or reach one through a patient.
CLINIC_SCOPED = {
    "clinic": [ClinicMember, Invitation, Chair, Patient, AccessLog, ProcedureType, Shift, Appointment,
               ReminderTemplate, CostRecord],
    "patient": [PatientLink, HistoryItem, ToothState, PlanItem, Visit, Attachment, Consent],
    "visit": [VisitProcedure],
    "appointment": [Reminder],
}
EXPORT_ID = _uuid.uuid4  # one id per export run, for the log
