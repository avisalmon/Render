"""improv's models (docs/improv/data_model.md).

SPR-I.1.3: the theory reference. Three tables answer every question about what
is in a chord and which scale fits it, so the recognizer, the judge, the
reference screens and the lessons cannot disagree. Seeded once by
manage.py seed_improv_theory and editable after.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower

from .grooves import beats_in, check_groove


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


# ---------------------------------------------------------------- SPR-I.2.2
# The band and the charts. A groove (`Style`) and a chord chart (`Progression`) are
# rows because people will add and tune them; the JSON in a groove is the shape of
# one cell, checked by improv/grooves.py.


class Genre(models.TextChoices):
    JAZZ = "jazz", "jazz"
    BLUES = "blues", "blues"
    POP = "pop", "pop"
    ROCK = "rock", "rock"
    GOSPEL = "gospel", "gospel"
    LATIN = "latin", "latin"
    FUNK = "funk", "funk"


def _not_blank(value):
    if not str(value).strip():
        raise ValidationError("This cannot be empty.")


def _signature_is_playable(value):
    if beats_in(value) is None:
        raise ValidationError("The band plays 2/4 to 12/4. Write it like 4/4 or 3/4.")


tempo_limits = [MinValueValidator(20), MaxValueValidator(300)]
key_name = RegexValidator(r"^[A-G][#b]?m?$", "A key is a note name with an optional # or b and an m for minor: C, Eb, F#m.")


class Tag(models.Model):
    name = models.CharField(max_length=40)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = [Lower("name")]

    def __str__(self):
        return self.name


class Style(models.Model):
    class Feel(models.TextChoices):
        SWING = "swing", "swing"
        STRAIGHT = "straight", "straight"
        SHUFFLE = "shuffle", "shuffle"

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=60, unique=True)
    genre = models.CharField(max_length=12, choices=Genre.choices)
    feel = models.CharField(max_length=10, choices=Feel.choices)
    swing_ratio = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.5,
        validators=[MinValueValidator(Decimal("0.50")), MaxValueValidator(Decimal("0.75"))],
        help_text="0.50 is straight, about 0.67 is a hard swing.",
    )
    time_signature = models.CharField(max_length=5, default="4/4", validators=[_signature_is_playable])
    default_tempo = models.PositiveSmallIntegerField(default=100, validators=tempo_limits)
    min_tempo = models.PositiveSmallIntegerField(default=60, validators=tempo_limits)
    max_tempo = models.PositiveSmallIntegerField(default=200, validators=tempo_limits)
    drums = models.JSONField(help_text="{instrument: [16 strengths 0..1]} for a 4/4 bar. See improv/grooves.py.")
    bass = models.JSONField(help_text='{"rule": "walking", "range": [33, 55]}')
    comp = models.JSONField(help_text='{"rhythm": [[0, 6], [6, 4]], "voicing": "shell", "register": [52, 76]}')
    is_preset = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="improv_styles"
    )

    class Meta:
        ordering = [Lower("name")]

    def __str__(self):
        return self.name

    def clean(self):
        problems = {}
        for field, message in check_groove(self.time_signature, self.drums, self.bass, self.comp).items():
            if field != "time_signature":
                problems[field] = message
        if self.min_tempo is not None and self.max_tempo is not None and self.default_tempo is not None:
            if not self.min_tempo <= self.default_tempo <= self.max_tempo:
                problems["default_tempo"] = "The default tempo has to sit between the minimum and the maximum."
        if problems:
            raise ValidationError(problems)


class Progression(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=60, unique=True)
    genre = models.CharField(max_length=12, choices=Genre.choices)
    tags = models.ManyToManyField(Tag, blank=True, related_name="progressions")
    chart = models.TextField(
        validators=[_not_blank, MaxLengthValidator(20000)],
        help_text="The only copy of the harmony. | Dm7 | G7 | Cmaj7 | % | See docs/improv/api.md, Chart grammar.",
    )
    home_key = models.CharField(max_length=3, validators=[key_name], help_text="The key the chart is written in.")
    time_signature = models.CharField(max_length=5, default="4/4", validators=[_signature_is_playable])
    default_tempo = models.PositiveSmallIntegerField(default=100, validators=tempo_limits)
    default_style = models.ForeignKey(Style, null=True, blank=True, on_delete=models.SET_NULL, related_name="progressions")
    difficulty = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    description = models.TextField(blank=True)
    is_preset = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="improv_progressions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["difficulty", Lower("title")]

    def __str__(self):
        return self.title
