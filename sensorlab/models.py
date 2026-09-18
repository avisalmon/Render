"""SensorLab's own tables.

Rule 2: the site's `User` is the one thing every app here shares, and the
sharing stops at the account. Everything SensorLab knows about a person
that is not "who is this person" lives below, in SensorLab's own table,
reached through `profiles.profile_for()`.

See docs/sensorlab/data_model.md §2. The curriculum models arrive in SL-B1.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


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


#: Everything SensorLab may ask a phone for. A consent row is refused for
#: anything not on this list, so the table cannot fill with typos nothing
#: will ever match against.
SENSORS = (
    "accelerometer",
    "linear-accelerometer",
    "gyroscope",
    "magnetometer",
    "barometer",
    "light",
    "proximity",
    "microphone",
    "camera",
    "gps",
)


class SensorConsentManager(models.Manager):
    def grant(self, profile, sensor):
        row, _ = self.get_or_create(profile=profile, sensor=sensor)
        row.granted_at = timezone.now()
        row.revoked_at = None
        row.save(update_fields=["granted_at", "revoked_at"])
        return row

    def revoke(self, profile, sensor):
        """Withdraw, without erasing that it happened.

        The row stays. "Agreed on Tuesday, withdrew on Friday" is the honest
        record; deleting it would read as though they never agreed at all,
        which is a worse answer to give if anybody ever asks.
        """
        row = self.filter(profile=profile, sensor=sensor).first()
        if row is None:
            return None
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        return row

    def granted(self, profile, sensor):
        return self.filter(profile=profile, sensor=sensor,
                           granted_at__isnull=False, revoked_at__isnull=True).exists()


class SensorConsent(models.Model):
    """Permission this person gave SensorLab, per sensor (spec §2).

    **Why this table exists when the browser demands nothing.** On Android a
    page can read the accelerometer the moment it loads — no prompt, no
    gesture, which the spike confirmed. That silent availability is the
    documented fingerprinting exposure spec §2 names, and it is exactly why
    SensorLab asks anyway: a promise the platform does not enforce is still
    a promise, and this is the record of it.

    Per sensor rather than one blanket yes, because agreeing to let a lab
    read the accelerometer is not agreeing to let it open the camera.
    """

    profile = models.ForeignKey(
        "sensorlab.SensorLabProfile", on_delete=models.CASCADE, related_name="sensor_consents"
    )
    sensor = models.CharField(max_length=32)
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = SensorConsentManager()

    class Meta:
        unique_together = ("profile", "sensor")
        verbose_name = "sensor consent"
        verbose_name_plural = "sensor consents"

    def __str__(self):
        state = "granted" if self.is_current else "withdrawn"
        return f"{self.profile.user} — {self.sensor} ({state})"

    @property
    def is_current(self):
        return self.granted_at is not None and self.revoked_at is None
