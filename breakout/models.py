"""breakout's data (docs/breakout/data_model.md, approved 2026-11-26).

Four things shape this file:

1. Everything is a row. An experience, a station, a hint, a material, a
   printable, a like, a comment: a model each, never a blob or a file the
   app keeps reading.
2. The printable kit is derived from these rows every time; it is not a
   model. Attached files (Printable) are rows that point to files.
3. The genre boundary is a table (Material); an experience lists what it
   needs from it.
4. Only the author edits; everyone else reacts (Like, Comment, Run,
   Download, Report). A curator hides, never edits.

Nothing here touches another app. The one shared thing is the site's `User`,
reached through `Profile` (one-to-one) and plain foreign keys.
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone

User = get_user_model()


class PrivateStorage(FileSystemStorage):
    """Attached printables live outside the public media folder and are
    handed out by `views.printable_file` to signed-in people only. The
    folder is read from settings on every use, never fixed at import
    (methodology 17: nothing at import touches the disk)."""

    @property
    def base_location(self):
        return str(settings.BREAKOUT_PRIVATE_DIR)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


PRIVATE = PrivateStorage()


def private_storage():
    return PRIVATE


def printable_path(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext.lower()[:8]
    return f"printables/{instance.experience_id}/{timezone.now():%Y%m%d%H%M%S}{ext}"


def cover_path(instance, filename):
    _base, ext = os.path.splitext(filename)
    return f"covers/{instance.pk or 'new'}-{timezone.now():%Y%m%d%H%M%S}{ext.lower()[:8]}"


# ------------------------------------------------------------------ people


class Profile(models.Model):
    """The app's own one-to-one to the shared account (Rule 2). Made on a
    person's first visit by `access.profile_for`."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="breakout_profile")
    display_name = models.CharField(max_length=80, blank=True)
    school = models.CharField(max_length=120, blank=True)
    is_curator = models.BooleanField(default=False)
    curator_since = models.DateTimeField(null=True, blank=True)
    curator_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    joined_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.display_name or self.user.first_name or self.user.get_username()


# -------------------------------------------------------------- experience


class Subject(models.Model):
    """A school subject or theme. Seeded; curators add more."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Experience(models.Model):
    """One breakout experience, the unit of the library."""

    DRAFT, PUBLISHED, HIDDEN = "draft", "published", "hidden"
    STATUSES = [(DRAFT, "טיוטה"), (PUBLISHED, "מפורסם"), (HIDDEN, "מוסתר")]
    EASY, MEDIUM, HARD = "easy", "medium", "hard"
    DIFFICULTIES = [(EASY, "קל"), (MEDIUM, "בינוני"), (HARD, "מאתגר")]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_experiences")
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, allow_unicode=True)
    tagline = models.CharField(max_length=160, blank=True)
    story = models.TextField(blank=True)
    teacher_notes = models.TextField(blank=True)
    audience_from = models.PositiveSmallIntegerField(default=7, help_text="כיתה")
    audience_to = models.PositiveSmallIntegerField(default=9, help_text="כיתה")
    group_size_min = models.PositiveSmallIntegerField(default=4)
    group_size_max = models.PositiveSmallIntegerField(default=6)
    duration_minutes = models.PositiveSmallIntegerField(default=45)
    prep_minutes = models.PositiveSmallIntegerField(default=30)
    difficulty = models.CharField(max_length=8, choices=DIFFICULTIES, default=MEDIUM)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)
    hidden_reason = models.CharField(max_length=200, blank=True)
    hidden_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_flagship = models.BooleanField(default=False)
    cover = models.ImageField(upload_to=cover_path, storage=private_storage, blank=True)
    subjects = models.ManyToManyField(Subject, through="ExperienceSubject", related_name="experiences", blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == self.PUBLISHED

    def grades(self):
        if self.audience_from == self.audience_to:
            return f"כיתה {hebrew_grade(self.audience_from)}"
        return f"כיתות {hebrew_grade(self.audience_from)}-{hebrew_grade(self.audience_to)}"


GRADES = {1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה", 6: "ו", 7: "ז", 8: "ח", 9: "ט", 10: "י", 11: "יא", 12: "יב"}


def hebrew_grade(n):
    return GRADES.get(int(n), str(n))


class ExperienceSubject(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("experience", "subject")]


class Station(models.Model):
    """One puzzle in the chain. Ordered."""

    MECHANICS = [
        ("decode", "פענוח"),
        ("logic", "לוגיקה"),
        ("find_the_error", "מציאת השגיאה"),
        ("order", "סידור"),
        ("sort", "מיון"),
        ("cipher", "צופן"),
        ("assemble", "הרכבה"),
        ("other", "אחר"),
    ]

    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="stations")
    order = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=80)
    story_text = models.TextField(blank=True)
    puzzle_text = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    solution_explained = models.TextField(blank=True)
    contribution = models.CharField(max_length=200, blank=True)
    mechanic = models.CharField(max_length=16, choices=MECHANICS, default="other")
    estimated_minutes = models.PositiveSmallIntegerField(default=8)
    setup_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["experience", "order", "pk"]

    def __str__(self):
        return f"{self.order}. {self.name}"


class Hint(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="hints")
    order = models.PositiveSmallIntegerField(default=1)
    text = models.TextField()

    class Meta:
        ordering = ["station", "order", "pk"]


class FinalLock(models.Model):
    """How the experience ends. One per experience."""

    experience = models.OneToOneField(Experience, on_delete=models.CASCADE, related_name="final_lock")
    description = models.TextField(blank=True)
    code_rule = models.TextField(blank=True)
    final_code = models.CharField(max_length=60, blank=True)
    final_message = models.TextField(blank=True)
    setup_notes = models.TextField(blank=True)


# --------------------------------------------------------------- materials


class Material(models.Model):
    """One thing from the office-supply shop. The catalogue is the boundary
    of the genre (spec 1.3)."""

    CATEGORIES = [
        ("paper", "נייר"),
        ("tool", "כלי"),
        ("fastener", "חיבור"),
        ("writing", "כתיבה"),
        ("container", "אריזה"),
        ("other", "אחר"),
    ]

    name = models.CharField(max_length=80, unique=True)
    unit = models.CharField(max_length=30, default="יחידה")
    category = models.CharField(max_length=12, choices=CATEGORIES, default="other")
    approx_cost_ils = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    where_to_get = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class StationMaterial(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="materials")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="uses")
    quantity = models.DecimalField(max_digits=7, decimal_places=2, default=1)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["station", "pk"]


class MaterialRequest(models.Model):
    OPEN, APPROVED, DECLINED = "open", "approved", "declined"
    STATUSES = [(OPEN, "פתוח"), (APPROVED, "אושר"), (DECLINED, "נדחה")]

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_material_requests")
    name = models.CharField(max_length=80)
    why = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=OPEN)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    created_material = models.ForeignKey(Material, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)


# -------------------------------------------------------------- printables


class Printable(models.Model):
    """A ready-made page the author attaches, for a station or the whole
    experience. The generated kit is not stored."""

    KINDS = [
        ("player_page", "דף לשחקנים"),
        ("cut_out", "דף גזירה"),
        ("teacher_page", "דף למורה"),
        ("image", "תמונה"),
    ]

    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="printables")
    station = models.ForeignKey(Station, null=True, blank=True, on_delete=models.CASCADE, related_name="printables")
    kind = models.CharField(max_length=14, choices=KINDS, default="player_page")
    title = models.CharField(max_length=120)
    file = models.FileField(upload_to=printable_path, storage=private_storage)
    page_count = models.PositiveSmallIntegerField(default=1)
    width_px = models.PositiveIntegerField(null=True, blank=True)
    height_px = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["experience", "order", "pk"]


# --------------------------------------------------------------- community


class Like(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_likes")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("experience", "user")]


class Comment(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_comments")
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["created_at"]


class Run(models.Model):
    """A teacher ran this with a real group and reports back. Counts only,
    never names (data model 6)."""

    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="runs")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_runs")
    ran_on = models.DateField(default=timezone.localdate)
    group_count = models.PositiveSmallIntegerField(default=1)
    kids_count = models.PositiveSmallIntegerField(default=0)
    actual_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(default=3)
    what_worked = models.TextField(blank=True)
    what_to_change = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-ran_on", "-created_at"]


class Download(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="downloads")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_downloads")
    groups = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)


class Report(models.Model):
    OPEN, RESOLVED = "open", "resolved"
    STATUSES = [(OPEN, "פתוח"), (RESOLVED, "טופל")]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="breakout_reports")
    experience = models.ForeignKey(Experience, null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=STATUSES, default=OPEN)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
