"""Books' data (docs/books/data_model.md, approved 2026-10-18).

Built sprint by sprint: SPR-BK1.1 adds Profile only. Nothing here touches
another app's tables; the only link to the shared User is Profile.
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
