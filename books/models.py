"""Books' data (docs/books/data_model.md, approved 2026-10-18).

Built sprint by sprint. Nothing here touches another app's tables; the only
link to the shared User is Profile.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

# Two decimal places of latitude/longitude is about a kilometre: a
# neighbourhood, never a building (spec 12.9, data model section 9).
AREA_PLACES = Decimal("0.01")


def round_coordinate(value):
    if value is None:
        return None
    return Decimal(str(value)).quantize(AREA_PLACES, rounding=ROUND_HALF_UP)


class Profile(models.Model):
    """The person, inside Books (data model section 4)."""

    LANGUAGES = [("he", "עברית"), ("en", "English")]
    FREE, PLUS, PRO = "free", "plus", "pro"
    TIERS = [(FREE, "Free"), (PLUS, "Plus"), (PRO, "Pro")]
    # Appearance (spec BK1 §1.1b): the defaults Avi chose, everything else selectable.
    THEMES = [("light", "light"), ("dark", "dark"), ("system", "system")]
    PALETTES = [("lamplit", "lamplit"), ("warm", "warm"), ("bright", "bright"), ("den", "den")]
    SHELF_VIEWS = [("lamp", "lamp"), ("bookcase", "bookcase"), ("living", "living")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books_profile")
    display_name = models.CharField(max_length=60)
    language = models.CharField(max_length=2, choices=LANGUAGES, default="he")
    tier = models.CharField(max_length=8, choices=TIERS, default=FREE)
    area_name = models.CharField(max_length=80, blank=True)
    area_lat = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    area_lng = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    radius_km = models.PositiveSmallIntegerField(default=10)
    is_adult_confirmed = models.BooleanField(default=False)
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    profile_public = models.BooleanField(default=False)
    show_points_public = models.BooleanField(default=False)
    theme = models.CharField(max_length=8, choices=THEMES, default="light")
    palette = models.CharField(max_length=8, choices=PALETTES, default="lamplit")
    shelf_view = models.CharField(max_length=10, choices=SHELF_VIEWS, default="lamp")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        # Location is never stored precisely, whoever sets it and however.
        self.area_lat = round_coordinate(self.area_lat)
        self.area_lng = round_coordinate(self.area_lng)
        super().save(*args, **kwargs)


class Job(models.Model):
    """One unit of background work (books/jobs.py). Added in SPR-BK1.5; a
    data-model addition recorded in docs/books/data_model.md section 11."""

    QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
    STATUSES = [(QUEUED, "queued"), (RUNNING, "running"), (DONE, "done"), (FAILED, "failed")]

    kind = models.CharField(max_length=40)
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    status = models.CharField(max_length=10, choices=STATUSES, default=QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} #{self.ref_id} {self.status}"


class ModelCall(models.Model):
    """One call to a paid model, with what it cost (spec BK1 §1.6). Added in
    SPR-BK1.5; recorded in data_model.md section 11."""

    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="model_calls")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="model_calls")
    provider = models.CharField(max_length=30)
    model = models.CharField(max_length=60)
    purpose = models.CharField(max_length=40)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}/{self.model} {self.purpose} ${self.cost_usd}"
