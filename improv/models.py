"""improv's models (docs/improv/data_model.md).

SPR-I.1.3: the theory reference. Three tables answer every question about what
is in a chord and which scale fits it, so the recognizer, the judge, the
reference screens and the lessons cannot disagree. Seeded once by
manage.py seed_improv_theory and editable after.
"""

from django.db import models


class ChordQuality(models.Model):
    class Family(models.TextChoices):
        MAJOR = "major", "major"
        MINOR = "minor", "minor"
        DOMINANT = "dominant", "dominant"
        DIMINISHED = "diminished", "diminished"
        HALF_DIMINISHED = "half_diminished", "half-diminished"
        SUSPENDED = "suspended", "suspended"
        AUGMENTED = "augmented", "augmented"

    symbol = models.CharField(max_length=20, unique=True, help_text="m7, maj7, 7, m7b5, 7alt ...")
    name = models.CharField(max_length=80)
    intervals = models.JSONField(help_text="Semitones above the root, sorted, from 0: [0,3,7,10].")
    roles = models.JSONField(help_text='Semitone to role: {"0": "root", "3": "third", "10": "seventh"}.')
    aliases = models.JSONField(default=list, blank=True, help_text="Other spellings the chart parser accepts.")
    family = models.CharField(max_length=20, choices=Family.choices)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "symbol"]
        verbose_name_plural = "chord qualities"

    def __str__(self):
        return self.symbol


class Scale(models.Model):
    class Family(models.TextChoices):
        MAJOR_MODES = "major_modes", "major modes"
        MELODIC_MINOR_MODES = "melodic_minor_modes", "melodic minor modes"
        HARMONIC_MINOR_MODES = "harmonic_minor_modes", "harmonic minor modes"
        PENTATONIC = "pentatonic", "pentatonic"
        BLUES = "blues", "blues"
        SYMMETRIC = "symmetric", "symmetric"

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    intervals = models.JSONField(help_text="Semitones above the root, sorted, from 0.")
    family = models.CharField(max_length=24, choices=Family.choices)
    parent_scale = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="modes")
    mode_number = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ChordScale(models.Model):
    """Which scales fit which chord quality, ranked. This is what makes "scale
    tone or outside note" a lookup instead of an opinion.

    Known limit, accepted for v1: Dm7 is Dorian as a ii chord and Aeolian as a
    vi chord, so a lookup by quality alone is right most of the time. A per-chord
    override in the chart is the likely fix and does not change these tables.
    """

    chord_quality = models.ForeignKey(ChordQuality, on_delete=models.CASCADE, related_name="chord_scales")
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name="chord_scales")
    preference = models.PositiveSmallIntegerField(help_text="1 is the first choice.")
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["chord_quality", "preference"]
        constraints = [
            models.UniqueConstraint(fields=["chord_quality", "scale"], name="improv_chordscale_unique"),
        ]

    def __str__(self):
        return f"{self.chord_quality} over {self.scale}"
