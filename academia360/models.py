"""Academia360's data, sections 1 to 3 and 10 of docs/academia360/data_model.md
(people and roles; the program; the institution as public knowledge; audit).
Sections 4 to 9 (taking part, KPIs, budget, review, talk-back, AI) come in
sprint A.2.

Every model declares its visibility circle (`CIRCLE`): `public`, `institution`
(its own leaders) or `committee`. A model in the institution circle names the
path from a row to its institution (`INSTITUTION_PATH`); a committee-circle
row a person may still read when it is about them names that path
(`OWN_PATH`). academia360/access.py reads these; nothing else decides who
sees what.

Nothing here touches the disk or the network at import (methodology 17).
"""

from django.conf import settings
from django.db import models

PUBLIC, INSTITUTION, COMMITTEE = "public", "institution", "committee"
CIRCLES = (PUBLIC, INSTITUTION, COMMITTEE)


class Row(models.Model):
    """Every row knows when it was made and last changed."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------- 1. people

class Role(Row):
    """One role a person holds in this app. A person may hold several; the
    higher one wins (spec 2.6.1). Never a field on the site's User."""

    CIRCLE = COMMITTEE
    OWN_PATH = "user"

    ADMIN, COMMITTEE_MEMBER, LEADER = "admin", "committee", "leader"
    KINDS = [(ADMIN, "מנהל המערכת"), (COMMITTEE_MEMBER, "חבר/ת ועדה"), (LEADER, "מוביל/ת תכנית במוסד")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_roles")
    kind = models.CharField(max_length=20, choices=KINDS)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="a360_roles_granted")
    granted_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "kind")]
        ordering = ["user_id", "kind"]

    def __str__(self):
        return f"{self.user} · {self.get_kind_display()}"


class CommitteeAttribute(Row):
    """A mark on a committee member: `chair` (decides) or `reviewer` of one
    institution. Attributes, not roles (spec 2.6.2, 2.6.3)."""

    CIRCLE = COMMITTEE
    OWN_PATH = "user"

    CHAIR, REVIEWER = "chair", "reviewer"
    KINDS = [(CHAIR, "יו״ר הוועדה"), (REVIEWER, "סוקר/ת")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_attributes")
    kind = models.CharField(max_length=20, choices=KINDS)
    program = models.ForeignKey("Program", on_delete=models.CASCADE, related_name="attributes")
    institution = models.ForeignKey("Institution", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="reviewers", help_text="For reviewers only")
    since = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "kind", "program", "institution")]

    def __str__(self):
        return f"{self.user} · {self.get_kind_display()}"


class LeaderOf(Row):
    """Links a program leader to their institution. Several leaders per
    institution, and a leader of two institutions is two rows (2.6.4)."""

    CIRCLE = INSTITUTION
    INSTITUTION_PATH = "institution"
    OWN_PATH = "user"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_leads")
    institution = models.ForeignKey("Institution", on_delete=models.CASCADE, related_name="leaders")
    title = models.CharField(max_length=160, blank=True, help_text="As shown, e.g. סגנית נשיא לעניינים אקדמיים")
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "institution")]

    def __str__(self):
        return f"{self.user} · {self.institution}"


class Invitation(Row):
    """A role granted to an email before the person has an account, redeemed
    on first sign-in."""

    CIRCLE = COMMITTEE

    email = models.EmailField()
    role_kind = models.CharField(max_length=20, choices=Role.KINDS)
    institution = models.ForeignKey("Institution", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="invitations")
    token = models.CharField(max_length=64, unique=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="a360_invitations_sent")
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email} · {self.role_kind}"


class PublicProfile(Row):
    """What a signed-in member of the public may set: a display name for
    comments."""

    CIRCLE = PUBLIC
    OWN_PATH = "user"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="a360_profile")
    display_name = models.CharField(max_length=80)

    def __str__(self):
        return self.display_name


# --------------------------------------------------------------- 2. program

class Program(Row):
    """A funding program of ות״ת. Academia 360 is the first row."""

    CIRCLE = PUBLIC

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=40, blank=True)
    body = models.CharField(max_length=120, blank=True, help_text="ות״ת / מל״ג")
    year_from = models.PositiveSmallIntegerField(null=True, blank=True)
    year_to = models.PositiveSmallIntegerField(null=True, blank=True)
    total_budget_nis = models.BigIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    official_url = models.URLField(blank=True)
    STATUS = [("planned", "מתוכננת"), ("open", "פתוחה להגשות"), ("running", "פועלת"), ("closed", "הסתיימה")]
    status = models.CharField(max_length=12, choices=STATUS, default="running")

    def __str__(self):
        return self.name


class AcademicYear(Row):
    """A year the program runs in, with both names."""

    CIRCLE = PUBLIC

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="years")
    hebrew_name = models.CharField(max_length=12, help_text="תשפ״ה")
    gregorian_from = models.PositiveSmallIntegerField()
    gregorian_to = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["program_id", "order"]
        unique_together = [("program", "hebrew_name")]

    def __str__(self):
        return self.hebrew_name


class Criterion(Row):
    """One domain the committee judges by, in order. The frame for every
    analysis and every review."""

    CIRCLE = PUBLIC

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="criteria")
    slug = models.SlugField()
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)
    colour = models.CharField(max_length=7, blank=True, help_text="The arc's colour on the 360 ring, e.g. #63BAC5")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["program_id", "order"]
        unique_together = [("program", "slug")]

    def __str__(self):
        return self.name


class ReviewQuestion(Row):
    """One line of the committee's review form under a criterion."""

    CIRCLE = PUBLIC

    CHECKLIST, TEXT = "checklist", "text"
    KINDS = [(CHECKLIST, "צ׳ק ליסט"), (TEXT, "טקסט")]

    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)
    kind = models.CharField(max_length=10, choices=KINDS, default=CHECKLIST)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["criterion_id", "order"]

    def __str__(self):
        return self.text[:60]


class GuidelineSection(Row):
    """The program's guidelines as the app shows them, section by section,
    editable by the admin."""

    CIRCLE = PUBLIC

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="guidelines")
    title = models.CharField(max_length=200)
    body = models.TextField(help_text="Markdown; sanitized before it is shown")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["program_id", "order"]

    def __str__(self):
        return self.title


# ---------------------------------------------- 3. the institution, public

class Institution(Row):
    """One higher-education institution. Public knowledge that outlives any
    program."""

    CIRCLE = PUBLIC

    UNIVERSITY, COLLEGE, TEACHER, RESEARCH = "university", "academic_college", "teacher_training", "research_institute"
    KINDS = [(UNIVERSITY, "אוניברסיטה"), (COLLEGE, "מכללה אקדמית"), (TEACHER, "מכללה לחינוך"),
             (RESEARCH, "מכון מחקר")]

    slug = models.SlugField(unique=True, allow_unicode=True)
    name_he = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    short_name_he = models.CharField(max_length=80, blank=True, help_text="As it reads in a list: הטכניון")
    kind = models.CharField(max_length=20, choices=KINDS)
    city = models.CharField(max_length=80, blank=True)
    website = models.URLField(blank=True)
    founded = models.PositiveSmallIntegerField(null=True, blank=True)
    founder = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to="academia360/logos/", blank=True)
    identity = models.TextField(blank=True, help_text="A short public paragraph: what makes this place itself")
    budgeted_by_vatat = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name_he"]

    def __str__(self):
        return self.short_name_he or self.name_he

    @property
    def name(self):
        return self.short_name_he or self.name_he


class Campus(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="campuses")
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name_plural = "campuses"

    def __str__(self):
        return self.name


class Unit(Row):
    """A faculty, school or department, nested."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    FACULTY, SCHOOL, DEPARTMENT = "faculty", "school", "department"
    KINDS = [(FACULTY, "פקולטה"), (SCHOOL, "בית ספר"), (DEPARTMENT, "מחלקה / חוג")]

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="units")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=KINDS, default=FACULTY)
    website = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["institution_id", "order", "name"]

    def __str__(self):
        return self.name


class StudyProgram(Row):
    """A degree program ("learning track"). The thing the 20% target counts."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    UNDERGRAD, MASTERS, PHD = "undergrad", "masters", "phd"
    LEVELS = [(UNDERGRAD, "תואר ראשון"), (MASTERS, "תואר שני"), (PHD, "דוקטורט")]
    # The 15 למ"ס fields of study, as the CBS names them.
    FIELDS = [
        ("humanities", "מדעי הרוח"), ("education", "חינוך והכשרה להוראה"), ("arts", "אמנויות"),
        ("social", "מדעי החברה"), ("business", "עסקים ומדעי הניהול"), ("law", "משפטים"),
        ("medicine", "רפואה"), ("paramedical", "מקצועות עזר רפואיים"), ("math_cs", "מתמטיקה, סטטיסטיקה ומדעי המחשב"),
        ("physical", "מדעים פיזיקליים"), ("biological", "מדעים ביולוגיים"), ("agriculture", "חקלאות"),
        ("engineering", "הנדסה ואדריכלות"), ("general", "כללי"), ("other", "אחר"),
    ]

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="study_programs")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.SET_NULL, related_name="study_programs")
    name = models.CharField(max_length=200)
    degree = models.CharField(max_length=20, blank=True, help_text="B.A., B.Sc., B.Ed. ...")
    field = models.CharField(max_length=20, choices=FIELDS, blank=True)
    level = models.CharField(max_length=10, choices=LEVELS, default=UNDERGRAD)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["institution_id", "name"]

    def __str__(self):
        return self.name


class StudyProgramCount(Row):
    """Students and graduates of a program in a year (נספח א, sheet 2)."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "study_program__institution"

    study_program = models.ForeignKey(StudyProgram, on_delete=models.CASCADE, related_name="counts")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="+")
    year1 = models.PositiveIntegerField(null=True, blank=True)
    year2 = models.PositiveIntegerField(null=True, blank=True)
    year3 = models.PositiveIntegerField(null=True, blank=True)
    year4 = models.PositiveIntegerField(null=True, blank=True)
    graduates = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("study_program", "academic_year")]


class InstitutionMetric(Row):
    """A number about the institution at a point in time, with its source."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="metrics")
    key = models.CharField(max_length=60, help_text="students_total, faculty_total, students_undergrad ...")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    unit = models.CharField(max_length=30, blank=True, help_text="headcount, percent, NIS")
    source = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(blank=True)
    as_of = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=True, help_text="Unverified facts stay off the public page")

    class Meta:
        ordering = ["institution_id", "key", "year"]

    def __str__(self):
        return f"{self.institution} {self.key} {self.year}: {self.value}"


class Researcher(Row):
    """A professor or researcher worth showing."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    ALGORITHMIC, APPLIED, OTHER = "algorithmic", "applied", "other"
    KINDS = [(ALGORITHMIC, "אלגוריתמי"), (APPLIED, "יישומי"), (OTHER, "אחר")]

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="researchers")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.SET_NULL, related_name="researchers")
    slug = models.SlugField(allow_unicode=True)
    name_he = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160, blank=True)
    title = models.CharField(max_length=80, blank=True, help_text="פרופ׳, ד״ר")
    areas = models.CharField(max_length=300, blank=True)
    focus = models.TextField(blank=True)
    kind = models.CharField(max_length=12, choices=KINDS, default=OTHER)
    is_leading = models.BooleanField(default=False)
    photo = models.ImageField(upload_to="academia360/researchers/", blank=True)
    bio = models.TextField(blank=True)
    verified = models.BooleanField(default=True)

    class Meta:
        ordering = ["institution_id", "-is_leading", "name_he"]
        unique_together = [("institution", "slug")]

    def __str__(self):
        return self.name_he


class ResearcherMetric(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "researcher__institution"

    H_INDEX, CITATIONS = "h_index", "citations"
    METRICS = [(H_INDEX, "h-index"), (CITATIONS, "ציטוטים")]

    researcher = models.ForeignKey(Researcher, on_delete=models.CASCADE, related_name="metrics")
    metric = models.CharField(max_length=12, choices=METRICS)
    value = models.PositiveIntegerField()
    approximate = models.BooleanField(default=False)
    as_of = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["researcher_id", "metric", "-as_of"]


class ResearcherLink(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "researcher__institution"

    KINDS = [("scholar", "Google Scholar"), ("orcid", "ORCID"), ("dblp", "DBLP"), ("homepage", "דף אישי"),
             ("other", "אחר")]

    researcher = models.ForeignKey(Researcher, on_delete=models.CASCADE, related_name="links")
    kind = models.CharField(max_length=12, choices=KINDS)
    url = models.URLField()
    verified_at = models.DateField(null=True, blank=True)


class Publication(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "researcher__institution"

    researcher = models.ForeignKey(Researcher, on_delete=models.CASCADE, related_name="publications")
    title = models.CharField(max_length=300)
    venue = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    citations = models.PositiveIntegerField(null=True, blank=True)
    url = models.URLField(blank=True)

    class Meta:
        ordering = ["researcher_id", "-year"]


class Grant(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "researcher__institution"

    researcher = models.ForeignKey(Researcher, on_delete=models.CASCADE, related_name="grants")
    funder = models.CharField(max_length=160)
    title = models.CharField(max_length=300, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)


class ResearchCenter(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="centers")
    name = models.CharField(max_length=200)
    full_name = models.CharField(max_length=300, blank=True)
    founded = models.PositiveSmallIntegerField(null=True, blank=True)
    focus = models.TextField(blank=True)
    equipment = models.TextField(blank=True)
    partners = models.TextField(blank=True)
    url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["institution_id", "order", "name"]

    def __str__(self):
        return self.name


class Collaboration(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    KINDS = [("academic", "אקדמי"), ("industry", "תעשייה"), ("government", "ממשלה"), ("community", "קהילה")]

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="collaborations")
    kind = models.CharField(max_length=12, choices=KINDS)
    partner = models.CharField(max_length=200)
    description = models.TextField(blank=True)


class ProfileSection(Row):
    """Long-form public text about the institution, by kind."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    KINDS = [("overview", "סקירה"), ("research", "מחקר"), ("innovation", "חדשנות ויזמות"), ("rankings", "דירוגים"),
             ("program_public", "מה המוסד פרסם על התכנית"), ("other", "אחר")]

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="sections")
    kind = models.CharField(max_length=20, choices=KINDS, default="overview")
    title = models.CharField(max_length=200)
    body = models.TextField(help_text="Markdown; sanitized before it is shown")
    order = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=200, blank=True)
    as_of = models.DateField(null=True, blank=True)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["institution_id", "order"]

    def __str__(self):
        return self.title


class TimelineEvent(Row):
    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="timeline")
    year = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=300)

    class Meta:
        ordering = ["institution_id", "year"]


class PublicDocument(Row):
    """A public file worth linking: a strategic plan the institution chose to
    publish, a press item."""

    CIRCLE = PUBLIC
    INSTITUTION_PATH = "institution"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="public_documents")
    title = models.CharField(max_length=300)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to="academia360/public/", blank=True)
    kind = models.CharField(max_length=40, blank=True)
    published_at = models.DateField(null=True, blank=True)


# ---------------------------------------------------------------- 10. audit

class ChangeLog(Row):
    """Who changed what, when, from what to what. The actor is a person in the
    app, Avi's agent working from the chat, or an import (spec chapter 3)."""

    CIRCLE = COMMITTEE

    PERSON, AGENT, IMPORT = "person", "agent", "import"
    ACTORS = [(PERSON, "אדם"), (AGENT, "הסוכן"), (IMPORT, "ייבוא")]

    model = models.CharField(max_length=80, help_text="app_label.ModelName")
    row_id = models.CharField(max_length=40)
    field = models.CharField(max_length=80, blank=True, help_text="Empty for create/delete")
    old = models.TextField(blank=True)
    new = models.TextField(blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                           related_name="a360_changes")
    actor_kind = models.CharField(max_length=10, choices=ACTORS, default=PERSON)
    reason = models.CharField(max_length=300, blank=True, help_text="The source the agent worked from")
    run = models.ForeignKey("AgentRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="changes")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model}#{self.row_id} {self.field or 'row'}"


class AgentRun(Row):
    """One piece of work the agent did from the chat: what it was asked, which
    sources it used, how many rows it touched."""

    CIRCLE = COMMITTEE

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=300)
    sources = models.TextField(blank=True, help_text="One url or file per line")
    rows_touched = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                           related_name="a360_runs")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return self.purpose


from .models_program import *  # noqa: E402,F401,F403  (sections 4 to 9 live in their own file)
