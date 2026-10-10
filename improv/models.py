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
from .teaching import check_notes, check_scoring


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


class Player(models.Model):
    """The app's own profile for a person, one to one with the shared User.

    Rule 2: an app never changes the shared User. Everything improv needs to know
    about a person that babook has no business knowing lives here, and the row is
    made on the person's first visit rather than by a signal, so a player who was
    added to the group before this app existed gets one too.
    """

    class NoteNames(models.TextChoices):
        SHARPS = "sharps", "sharps (C#)"
        FLATS = "flats", "flats (Db)"

    class DemoOutput(models.TextChoices):
        PIANO = "piano", "the piano, over MIDI"
        LAPTOP = "laptop", "the laptop, as a plain tone"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="improv_player")
    current_lesson = models.ForeignKey(
        "Lesson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="players_here",
        help_text="Where the player chose to be in the path: Today and Continue follow from here. Moves when they press Start here or play an exercise of another lesson.",
    )
    daily_goal_minutes = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(5), MaxValueValidator(240)]
    )
    latency_offset_ms = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-500), MaxValueValidator(500)],
        help_text="Measured by calibration (SPR-I.3.4). Judging subtracts it from every note time.",
    )
    midi_input_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="The keyboard last used, by name: a port's id is not promised to stay the same.",
    )
    note_names = models.CharField(max_length=6, choices=NoteNames.choices, default=NoteNames.SHARPS)
    demo_output = models.CharField(max_length=6, choices=DemoOutput.choices, default=DemoOutput.PIANO)
    trainer_tempo = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(30), MaxValueValidator(160)],
        help_text="The scale trainer's tempo in bpm. Changing it on the screen saves it here.",
    )
    reading_tempo = models.PositiveSmallIntegerField(
        default=72,
        validators=[MinValueValidator(30), MaxValueValidator(160)],
        help_text="The reading trainer's tempo in bpm. Changing it on the screen saves it here.",
    )
    timezone = models.CharField(
        max_length=40,
        default="Asia/Jerusalem",
        help_text="IANA name. The site runs on UTC and a streak is made of the player's own days.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"improv player {self.user}"


class PracticeSession(models.Model):
    """One sitting at the piano. The practice log (feature 16) is this table."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="sessions")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    active_seconds = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(24 * 3600)],
        help_text="Time the band was running or a note was played, not time the tab was open.",
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"session {self.pk} of {self.player}"


class Take(models.Model):
    """One play-through: the source of truth for everything the app says about how the
    person plays. It carries its own chart, key, tempo and feel, because whether a note
    was right depends on what it was played over, and the progression may be edited
    tomorrow. judge_version does the same job for the judging code.

    Added after the data model was approved: home_key, time_signature, swing_ratio, loop_from
    and loop_to, because re-judging or replaying a take needs the key the chart text is written
    in, the bar length, the feel, and which bars of the chart were played, and none of those is
    in the chart text; a snapshot that needs another row to be read is not a snapshot.
    exercise (SPR-I.5.1) names the task the take was played for, if there was one; deleting an
    exercise keeps the take, because the take is a record of what the player did.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="takes")
    session = models.ForeignKey(PracticeSession, on_delete=models.CASCADE, related_name="takes")
    progression = models.ForeignKey(Progression, null=True, blank=True, on_delete=models.SET_NULL, related_name="takes")
    style = models.ForeignKey(Style, null=True, blank=True, on_delete=models.SET_NULL, related_name="takes")
    exercise = models.ForeignKey("Exercise", null=True, blank=True, on_delete=models.SET_NULL, related_name="takes")
    chart = models.TextField(validators=[_not_blank, MaxLengthValidator(20000)], help_text="Snapshot of the chart as played.")
    home_key = models.CharField(max_length=3, validators=[key_name], help_text="The key the chart text is written in.")
    key = models.CharField(max_length=3, validators=[key_name], help_text="The key it was played in.")
    time_signature = models.CharField(max_length=5, default="4/4", validators=[_signature_is_playable])
    tempo = models.PositiveSmallIntegerField(validators=tempo_limits)
    swing_ratio = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.50"),
        validators=[MinValueValidator(Decimal("0.50")), MaxValueValidator(Decimal("0.75"))],
    )
    loop_from = models.PositiveSmallIntegerField(default=0, help_text="First bar played, 0-based.")
    loop_to = models.PositiveSmallIntegerField(help_text="One past the last bar played.")
    started_at = models.DateTimeField()
    duration_ms = models.PositiveIntegerField(validators=[MaxValueValidator(6 * 3600 * 1000)])
    bars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    events = models.JSONField(default=list, help_text="{t_ms, type: on/off, note, velocity} as the MIDI arrived.")
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    metrics = models.JSONField(default=dict)
    judge_version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    is_kept = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"take {self.pk} of {self.player}"


# ---------------------------------------------------------------- SPR-I.5.1
# Teaching. A lesson is Read, Hear, Play: the explanation, a demo phrase over the band, and
# exercises the judge scores. The rows are written during development and seeded once; the
# app never makes a lesson at runtime. The JSON shapes are checked by improv/teaching.py.


class Phrase(models.Model):
    """A short run of notes: the demo in a lesson, the prompt in call and response, or a lick of
    the player's own. A phrase is read whole, so its notes are JSON."""

    class Kind(models.TextChoices):
        DEMO = "demo", "demo"
        CALL = "call", "call"
        ANSWER = "answer", "answer"
        LICK = "lick", "lick"

    name = models.CharField(max_length=80, validators=[_not_blank])
    slug = models.SlugField(max_length=60, unique=True)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.LICK)
    notes = models.JSONField(help_text="[{midi, beat, length, velocity}]: beats counted from 0 at the start of the phrase.")
    length_beats = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(Decimal("64"))],
    )  # fmt: skip
    chart_context = models.TextField(blank=True, validators=[MaxLengthValidator(2000)], help_text="The chords underneath, if it only makes sense over them.")
    written_in_key = models.CharField(max_length=3, default="C", validators=[key_name], help_text="So it can be transposed with the chart.")
    is_preset = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="improv_phrases"
    )

    class Meta:
        ordering = [Lower("name")]

    def __str__(self):
        return self.name

    def clean(self):
        if self.length_beats is not None:
            problem = check_notes(self.notes, self.length_beats)
            if problem:
                raise ValidationError({"notes": problem})


class Lesson(models.Model):
    """One unit on one track. The explanation and the demo live here; the playing tasks live
    in Exercise. authorship says who wrote it, so "what has Avi actually read" is a query."""

    class Track(models.TextChoices):
        CHORD_TONES = "chord_tones", "chord tones"
        GUIDE_TONES = "guide_tones", "guide tones"
        SCALES_MODES = "scales_modes", "scales and modes"
        APPROACH_NOTES = "approach_notes", "approach notes"
        RHYTHM_MOTIFS = "rhythm_motifs", "rhythm motifs"
        CALL_AND_RESPONSE = "call_and_response", "call and response"
        VOICINGS_COMPING = "voicings_comping", "voicings and comping"

    class Authorship(models.TextChoices):
        AI_DRAFTED = "ai_drafted", "drafted by AI, not yet read"
        REVIEWED = "reviewed", "drafted by AI, read and corrected"
        AVI_WRITTEN = "avi_written", "written by Avi"

    class Status(models.TextChoices):
        DRAFT = "draft", "draft"
        PUBLISHED = "published", "published"

    track = models.CharField(max_length=20, choices=Track.choices)
    order = models.PositiveSmallIntegerField(help_text="Position within the track.")
    title = models.CharField(max_length=100, validators=[_not_blank])
    slug = models.SlugField(max_length=60, unique=True)
    level = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(4)])
    summary = models.CharField(max_length=200, validators=[_not_blank], help_text="One line for the card.")
    explanation = models.TextField(validators=[_not_blank, MaxLengthValidator(20000)], help_text="The short teaching text, in markdown.")
    demo_phrase = models.ForeignKey(Phrase, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    progression = models.ForeignKey(Progression, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons", help_text="The changes the lesson is taught over.")
    style = models.ForeignKey(Style, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    prerequisite = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="unlocks")
    authorship = models.CharField(max_length=12, choices=Authorship.choices, default=Authorship.AI_DRAFTED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    path_order = models.PositiveSmallIntegerField(
        null=True, blank=True, unique=True, help_text="Position in the whole path, across tracks. Empty sorts after every numbered lesson, by level, track and order."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["track", "order"]
        constraints = [
            models.UniqueConstraint(fields=["track", "order"], name="improv_lesson_track_order_unique"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.prerequisite_id and self.prerequisite_id == self.pk:
            raise ValidationError({"prerequisite": "A lesson cannot be its own prerequisite."})


class Exercise(models.Model):
    """A playing task with a way of being scored. A challenge is an exercise with no lesson."""

    class ScoringKind(models.TextChoices):
        CHORD_TONES_ON_BEATS = "chord_tones_on_beats", "chord tones on beats"
        GUIDE_TONES = "guide_tones", "guide tones"
        SCALE_ONLY = "scale_only", "scale only"
        APPROACH_NOTES = "approach_notes", "approach notes"
        RHYTHM_MOTIF = "rhythm_motif", "rhythm motif"
        CALL_AND_RESPONSE = "call_and_response", "call and response"
        COMPING_VOICINGS = "comping_voicings", "comping voicings (a later version)"
        FREE_PLAY = "free_play", "free play"

    lesson = models.ForeignKey(Lesson, null=True, blank=True, on_delete=models.CASCADE, related_name="exercises", help_text="Empty means a standalone challenge or a daily-workout candidate.")
    order = models.PositiveSmallIntegerField(default=1, help_text="Within the lesson.")
    title = models.CharField(max_length=100, validators=[_not_blank])
    slug = models.SlugField(max_length=60, unique=True)
    instructions = models.TextField(validators=[_not_blank, MaxLengthValidator(4000)])
    progression = models.ForeignKey(Progression, on_delete=models.PROTECT, related_name="exercises")
    key = models.CharField(max_length=3, validators=[key_name])
    tempo = models.PositiveSmallIntegerField(validators=tempo_limits)
    style = models.ForeignKey(Style, null=True, blank=True, on_delete=models.SET_NULL, related_name="exercises")
    bars = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(64)], help_text="How much to play.")
    scoring_kind = models.CharField(max_length=24, choices=ScoringKind.choices)
    scoring_params = models.JSONField(default=dict, blank=True, help_text='The judge reads these by kind, e.g. {"beats": [1, 3]}. See improv/teaching.py.')
    pass_score = models.PositiveSmallIntegerField(default=70, validators=[MaxValueValidator(100)])
    xp = models.PositiveSmallIntegerField(default=10, validators=[MaxValueValidator(1000)])
    daily_eligible = models.BooleanField(default=False, help_text="May the daily workout pick it.")

    class Meta:
        ordering = ["lesson__track", "lesson__order", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["lesson", "order"], name="improv_exercise_lesson_order_unique"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        beats = beats_in(self.progression.time_signature) if self.progression_id else 4
        problem = check_scoring(self.scoring_kind, self.scoring_params, beats_per_bar=beats or 4, bars=self.bars or 1)
        if problem:
            raise ValidationError({"scoring_params": problem})


# ---------------------------------------------------------------- SPR-I.5.2


class Completion(models.Model):
    """The first time a player passed an exercise. A fact, not a status.

    Only the server makes one, as the consequence of a take (improv/progress.py), and the XP is
    frozen from the exercise row at that moment. XP, level and what is unlocked are reads over
    these rows. The take is SET_NULL because pruning old takes must never un-earn anything."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="completions")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="completions")
    take = models.OneToOneField(Take, null=True, blank=True, on_delete=models.SET_NULL, related_name="completion")
    xp_awarded = models.PositiveSmallIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["player", "exercise"], name="improv_completion_player_exercise_unique"),
        ]

    def __str__(self):
        return f"{self.player} passed {self.exercise}"


# ---------------------------------------------------------------- SPR-I.8.1


def _check_fingers(value, name):
    if not isinstance(value, list) or len(value) != 7 or any(isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 5 for n in value):
        raise ValidationError({name: "Seven finger numbers, each from 1 to 5, one for each degree of the scale."})


class ScaleFingering(models.Model):
    """The standard fingering of a scale for one hand in one key (spec chapter 10, data model 6a).

    Going down is the list going up, reversed. The two seven-number cells are JSON because the
    screen reads each whole and nothing ever asks about a single finger."""

    class Hand(models.TextChoices):
        LEFT = "L", "left hand"
        RIGHT = "R", "right hand"

    class Authorship(models.TextChoices):
        AI_DRAFTED = "ai_drafted", "taken from a published chart, not yet read at the piano"
        REVIEWED = "reviewed", "read and checked by Avi"

    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name="fingerings")
    root_pc = models.PositiveSmallIntegerField(validators=[MaxValueValidator(11)], help_text="The tonic as a pitch class, C is 0.")
    hand = models.CharField(max_length=1, choices=Hand.choices)
    first_octave = models.JSONField(help_text="Seven fingers, one per scale degree, for the first octave. 1 is the thumb.")
    next_octaves = models.JSONField(help_text="Seven fingers for every later octave.")
    last_note = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="The finger on the top note.")
    authorship = models.CharField(max_length=12, choices=Authorship.choices, default=Authorship.AI_DRAFTED)

    class Meta:
        ordering = ["scale_id", "root_pc", "hand"]
        constraints = [
            models.UniqueConstraint(fields=["scale", "root_pc", "hand"], name="improv_scalefingering_scale_key_hand_unique"),
        ]

    def __str__(self):
        return f"{self.scale} {self.root_pc} {self.get_hand_display()}"

    def clean(self):
        _check_fingers(self.first_octave, "first_octave")
        _check_fingers(self.next_octaves, "next_octaves")


# ---------------------------------------------------------------- SPR-I.8.2

SCALE_PASS_SCORE = 80
MOST_SCALE_STEPS = 57  # four octaves, up and down: 14 * 4 + 1


def _check_missed_steps(value):
    ok = isinstance(value, list) and len(value) <= MOST_SCALE_STEPS
    ok = ok and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n < MOST_SCALE_STEPS for n in value)
    if not ok:
        raise ValidationError(f"A list of step numbers, each from 0 to {MOST_SCALE_STEPS - 1}.")


class ScaleRun(models.Model):
    """One attempt at a scale in time, with its score (spec chapter 10, data model 6a).

    The page judges and posts the result, as it does for a take; the pass line is the one thing the
    server decides, so `passed` is always the score measured against it."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="scale_runs")
    scale = models.ForeignKey(Scale, on_delete=models.PROTECT, related_name="runs")
    root_pc = models.PositiveSmallIntegerField(validators=[MaxValueValidator(11)])
    octaves = models.PositiveSmallIntegerField(validators=[MinValueValidator(2), MaxValueValidator(4)])
    notes_per_beat = models.PositiveSmallIntegerField(validators=[MinValueValidator(2), MaxValueValidator(4)])
    tempo_bpm = models.PositiveSmallIntegerField(validators=[MinValueValidator(30), MaxValueValidator(160)])
    score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    pitch_accuracy = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    timing_accuracy = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    mean_offset_ms = models.IntegerField(validators=[MinValueValidator(-5000), MaxValueValidator(5000)], help_text="Negative is early.")
    passed = models.BooleanField(default=False, editable=False)
    missed_steps = models.JSONField(default=list, validators=[_check_missed_steps], help_text="0-based step numbers where a note was missed.")
    judge_version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.player} {self.root_pc} x{self.octaves} {self.score}"

    def save(self, *args, **kwargs):
        self.passed = self.score >= SCALE_PASS_SCORE
        super().save(*args, **kwargs)


# ---------------------------------------------------------------- SPR-I.8.4

DRILL_KINDS = [("chord_position", "A chord in a position")]


class DrillAttempt(models.Model):
    """One prompt of the chord trainer, answered or skipped (spec chapter 10, data model section 7).

    `is_correct` is "got it with no wrong try" and a skipped prompt is never correct. The response time
    runs from the prompt appearing to the right chord and includes any wrong tries; it is empty when
    the prompt was skipped."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="drill_attempts")
    kind = models.CharField(max_length=24, choices=DRILL_KINDS, default="chord_position")
    key_pc = models.PositiveSmallIntegerField(validators=[MaxValueValidator(11)])
    level = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    prompt = models.JSONField(default=dict)
    answer = models.JSONField(default=dict, blank=True)
    is_correct = models.BooleanField(default=False)
    wrong_tries = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(200)])
    hint_used = models.BooleanField(default=False)
    skipped = models.BooleanField(default=False)
    response_ms = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(3_600_000)])
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-answered_at", "-id"]

    def __str__(self):
        return f"{self.player} {self.kind} {self.key_pc} {'ok' if self.is_correct else 'miss'}"

    def clean(self):
        if self.skipped and self.response_ms is not None:
            raise ValidationError({"response_ms": "A skipped prompt has no response time."})
        if self.skipped and self.is_correct:
            raise ValidationError({"is_correct": "A skipped prompt is not correct."})


# ---------------------------------------------------------------- SPR-I.12.1

READING_PASS_SCORE = 80
MOST_READING_NOTES = 200
MOST_READING_EVENTS = 4000


def _check_reading_list(value, most, name):
    if not isinstance(value, list) or len(value) > most or not all(isinstance(row, dict) for row in value):
        raise ValidationError(f"{name} is a list of at most {most} objects.")


class ReadingTake(models.Model):
    """One read-through of a generated exercise in the reading trainer (spec chapter 11, data model 6c).

    The exercise is stored with the take (`notes`), because it was generated and exists nowhere else; `events`
    is what the piano sent and `results` what the judge said of every written note, so a take can be shown again
    and re-judged. The pass line is the server's: only a Flow take at the line or above passes; Step mode waits
    for the right note, so it can never pass."""

    class Hands(models.TextChoices):
        RIGHT = "R", "right hand"
        LEFT = "L", "left hand"
        BOTH = "B", "both hands"

    class Mode(models.TextChoices):
        FLOW = "flow", "flow: the pulse never waits"
        STEP = "step", "step: it waits for the right note"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="reading_takes")
    key = models.CharField(max_length=3, validators=[key_name], help_text="The major key, as written: C, F#, Bb.")
    hands = models.CharField(max_length=1, choices=Hands.choices)
    difficulty = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    tempo_bpm = models.PositiveSmallIntegerField(validators=[MinValueValidator(30), MaxValueValidator(160)])
    mode = models.CharField(max_length=4, choices=Mode.choices, default=Mode.FLOW)
    curtain = models.BooleanField(default=False, help_text="Whether the notes behind the cursor were hidden.")
    seed = models.PositiveIntegerField(help_text="The generator's seed: the same stage and seed give the same exercise.")
    notes = models.JSONField(default=list, help_text="The exercise as written: {hand, step, acc, midi, beat, dur} per note.")
    events = models.JSONField(default=list, help_text="{t_ms, type: on/off, note, velocity} as the MIDI arrived.")
    results = models.JSONField(default=list, help_text="The judge's word on each written note: {state, timing, offset_ms, played}.")
    score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    pitch_accuracy = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    timing_accuracy = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    passed = models.BooleanField(default=False, editable=False)
    judge_version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.player} reading {self.key} {self.hands} {self.score}"

    def clean(self):
        _check_reading_list(self.notes, MOST_READING_NOTES, "notes")
        _check_reading_list(self.events, MOST_READING_EVENTS, "events")
        _check_reading_list(self.results, MOST_READING_NOTES, "results")

    def save(self, *args, **kwargs):
        self.passed = self.mode == self.Mode.FLOW and self.score >= READING_PASS_SCORE
        super().save(*args, **kwargs)


class Feedback(models.Model):
    """What a person tells the owner about the app (SPR-I.9.3). Theirs to read, fix or withdraw;
    the owner reads all of it in the admin."""

    class Kind(models.TextChoices):
        IDEA = "idea", "an idea"
        PROBLEM = "problem", "something is wrong"
        PRAISE = "praise", "something I liked"
        OTHER = "other", "something else"

    MESSAGE_MAX = 2000

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="feedback")
    kind = models.CharField(max_length=7, choices=Kind.choices, default=Kind.IDEA)
    message = models.TextField(max_length=MESSAGE_MAX)
    page = models.CharField(max_length=200, blank=True, help_text="The improv screen they were on, e.g. /improv/play/.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "feedback"

    def __str__(self):
        return f"{self.kind}: {self.message[:40]}"

