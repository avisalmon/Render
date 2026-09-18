"""SensorLab's own tables.

Rule 2: the site's `User` is the one thing every app here shares, and the
sharing stops at the account. Everything SensorLab knows about a person
that is not "who is this person" lives below, in SensorLab's own table,
reached through `profiles.profile_for()`.

See docs/sensorlab/data_model.md §2. The curriculum models arrive in SL-B1.
"""

from django.conf import settings
from django.db import models


class SensorLabProfile(models.Model):
    """What SensorLab knows about a person, kept out of the shared account."""

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HEBREW = "he", "עברית"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sensorlab_profile",
    )

    #: The flip switch from spec §1. Persisted per person on purpose: it is a
    #: choice they made, not something re-inferred from the browser on every
    #: visit. SL-A5 drives it; this is the storage it drives.
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)

    #: Streaks are fields here rather than their own model (data_model.md §2):
    #: profile state, not an entity — nobody edits, lists or deletes a streak.
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    freezes_available = models.PositiveIntegerField(default=0)
    freezes_used = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "SensorLab profile"
        verbose_name_plural = "SensorLab profiles"

    def __str__(self):
        return f"{self.user} ({self.language})"

    @property
    def text_direction(self):
        """What the page's `dir` attribute should be. SL-A5 consumes this."""
        return "rtl" if self.language == self.Language.HEBREW else "ltr"
