"""SensorLab's own tables.

Rule 2: the site's `User` is the one thing every app here shares, and the
sharing stops at the account. Everything SensorLab knows about a person
that is not "who is this person" lives below, in SensorLab's own table,
reached through `profiles.profile_for()`.

See docs/sensorlab/data_model.md §2 (identity) and §3–4 (the curriculum,
added in SL-B1).
"""

import html
import uuid

import markdown
from django.conf import settings
from django.db import models
from django.utils import timezone, translation
from django.utils.safestring import mark_safe


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


SENSOR_CHOICES = tuple((name, name.replace("-", " ").title()) for name in SENSORS)

#: spec §3's flow, defined once. The assembled API response orders its steps
#: by this, and the lab overview previews them from it — a screen or a
#: serializer that spelled the sequence out again would be a second copy
#: waiting to disagree with the spec the day a step is added.
#:
#: Only three of the five are `ContentBlock.Step` values, because only three
#: are prose (data_model.md §4). The other two have shapes of their own.
LAB_STEPS = ("intro", "learn", "predict", "experiment", "analysis")


# ===========================================================================
# The curriculum (data_model.md §3–4)
#
# Authored once, read by everyone. Kept deliberately apart from the attempt
# half of the model: content is the course, an attempt is one person's run
# through it, and merging them is how a course becomes un-editable without
# destroying student history.
# ===========================================================================


def localised(instance, base, language=None):
    """The `base_en` / `base_he` pair, resolved for one language.

    Falls back to the other language rather than returning nothing
    (data_model.md §11). A half-translated course should look like the wrong
    language for a sentence, never like a page that failed to load — and it
    will be half-translated, because content and translation never land in
    the same commit.
    """
    code = str(language or translation.get_language() or "en").lower()
    primary = "he" if code.startswith("he") else "en"
    other = "en" if primary == "he" else "he"
    return getattr(instance, f"{base}_{primary}", "") or getattr(instance, f"{base}_{other}", "") or ""


def bilingual(base):
    """`obj.title` for a model that stores `title_en` and `title_he`."""
    return property(lambda self: localised(self, base))


#: The same three extensions the rest of this site's Markdown uses
#: (`app/blog.py`, `app/forum_views.py`), so authored text behaves the same
#: wherever it appears.
_MD_EXTENSIONS = ["fenced_code", "tables", "nl2br"]


def render_markdown(text):
    """Author text → HTML, with any HTML the author wrote rendered inert.

    **The decision recorded in docs/sensorlab/backlog.md (SL-B1).** Markdown,
    because `markdown` is already a dependency of this site and plain text
    cannot express the emphasis, lists and tables teaching material needs.
    Raw HTML is escaped *before* conversion rather than stripped afterwards,
    because `bleach` is not installed here and cannot be added — so instead
    of sanitising HTML, none is ever produced from author input. Markdown
    reads `&lt;` as an entity and leaves it alone, so the escape survives
    conversion intact.

    Authoring is admin-only today, which makes the exposure small. It will
    not stay admin-only: data_model.md §12 anticipates teacher-authored
    labs, and a content format is far harder to change once a course is
    written in it than it is to choose carefully now.
    """
    escaped = html.escape(text or "", quote=False)
    return mark_safe(markdown.markdown(escaped, extensions=_MD_EXTENSIONS))


class PublishedManager(models.Manager):
    """Only what is finished.

    Authoring happens against the live database — there is no staging site
    here — so the difference between "written" and "shown" has to be a
    field, or a student meets a lab mid-sentence.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)


class Track(models.Model):
    """One physics topic — spec §3's מסלול."""

    slug = models.SlugField(max_length=64, unique=True)
    title_en = models.CharField(max_length=120)
    title_he = models.CharField(max_length=120, blank=True)
    description_en = models.TextField(blank=True)
    description_he = models.TextField(blank=True)
    icon = models.CharField(max_length=32, blank=True, help_text="Emoji or icon name")
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    objects = models.Manager()
    published = PublishedManager()

    title = bilingual("title")
    description = bilingual("description")

    class Meta:
        ordering = ("order", "slug")

    def __str__(self):
        return self.title_en


class Lab(models.Model):
    """One experiment inside a track."""

    class Mode(models.TextChoices):
        """The three experiment modalities spec §4 commits to.

        Code, not content: which modalities exist is a capability of the app
        — each has capture code behind it — not a row someone adds.
        """

        LIVE_SENSOR = "live_sensor", "Live sensor"
        VIDEO_TRACKING = "video_tracking", "Video tracking"
        SIGNAL_GENERATOR = "signal_generator", "Signal generator"

    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="labs")

    #: Unique site-wide, not merely within its track (tightened in SL-B2).
    #: `/sensorlab/api/labs/<slug>/` is a flat URL and a lab is the thing
    #: people link to and share (spec §6); a shareable link that needs two
    #: slugs to be unambiguous is a worse link.
    slug = models.SlugField(max_length=64, unique=True)
    title_en = models.CharField(max_length=120)
    title_he = models.CharField(max_length=120, blank=True)
    summary_en = models.TextField(blank=True)
    summary_he = models.TextField(blank=True)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.LIVE_SENSOR)
    estimated_minutes = models.PositiveIntegerField(default=10)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    #: Explicit unlocking rather than "the previous one by `order`", so a
    #: track can branch later without a migration (data_model.md §3).
    prerequisite_lab = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="unlocks"
    )

    objects = models.Manager()
    published = PublishedManager()

    title = bilingual("title")
    summary = bilingual("summary")

    class Meta:
        ordering = ("order", "slug")

    def __str__(self):
        return f"{self.track.title_en} — {self.title_en}"


class ContentBlock(models.Model):
    """A block of authored prose or media, for Intro, Learn, or Analysis.

    One model for three of the five steps, because those three are the same
    shape (data_model.md §4): ordered bilingual prose. Three near-identical
    tables differing only by name would buy nothing.

    Each block is a real object — addable, editable, reorderable — rather
    than one long text field per step, so a worked example can be moved
    without retyping the concept above it.
    """

    class Step(models.TextChoices):
        INTRO = "intro", "Intro"
        LEARN = "learn", "Learn"
        ANALYSIS = "analysis", "Analysis"

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        FORMULA = "formula", "Formula"
        CALLOUT = "callout", "Callout"

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name="content_blocks")
    step = models.CharField(max_length=10, choices=Step.choices, default=Step.INTRO)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TEXT)
    order = models.PositiveIntegerField(default=0)
    body_en = models.TextField(blank=True)
    body_he = models.TextField(blank=True)
    media = models.ImageField(upload_to="sensorlab/content/", blank=True)

    body = bilingual("body")

    class Meta:
        ordering = ("step", "order", "id")

    def __str__(self):
        return f"{self.lab.slug}/{self.step}#{self.order}"

    #: The one kind whose body is not prose. A formula is symbols, and
    #: Markdown would read `*`, `_` and `|` in one as emphasis and table
    #: pipes — mangling the very characters that carry the meaning.
    LITERAL_KINDS = ("formula",)

    def render(self, language=None):
        """This block's body as HTML for one language.

        **Corrected in SL-B3, by reading a real seeded lab.** This used to
        render Markdown for `text` only, on the reasoning that images,
        formulas, video and callouts are structured kinds rather than markup.
        Half of that was right and half of it was a conflation: the `kind`
        governs the *container* — what box it is drawn in, how instrument
        mode styles it — not whether the words inside are prose.

        A callout is prose in a box. An image's body is its caption. Both
        came back in a field called `body_html` containing literal `\\n\\n`
        and backticks, which a student would have read as backticks. Only a
        formula is genuinely not prose.
        """
        text = localised(self, "body", language)
        if self.kind in self.LITERAL_KINDS:
            return mark_safe(html.escape(text, quote=False))
        return render_markdown(text)


class PredictionQuestion(models.Model):
    """One thing the student commits to before any data exists.

    A quiz is data, not a JSON blob — Rule 1's exact case. Questions in a
    file are unqueryable, so "which prediction do students get wrong most
    often" becomes unanswerable, and that question is the pedagogical point
    of the Predict step (spec §3).
    """

    class Kind(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
        NUMERIC = "numeric", "Numeric"
        FREE_TEXT = "free_text", "Free text"
        GRAPH_SKETCH = "graph_sketch", "Graph sketch"

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name="prediction_questions")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MULTIPLE_CHOICE)
    order = models.PositiveIntegerField(default=0)
    prompt_en = models.TextField()
    prompt_he = models.TextField(blank=True)

    #: `numeric` only. A prediction is right if it lands within `tolerance`
    #: percent — the point is the reasoning, not the decimal places.
    correct_value = models.FloatField(null=True, blank=True)
    tolerance = models.FloatField(default=10.0, help_text="Percent")

    prompt = bilingual("prompt")

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.lab.slug}: {self.prompt_en[:40]}"


class PredictionChoice(models.Model):
    """An option on a `multiple_choice` question."""

    question = models.ForeignKey(
        PredictionQuestion, on_delete=models.CASCADE, related_name="choices"
    )
    text_en = models.CharField(max_length=200)
    text_he = models.CharField(max_length=200, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    text = bilingual("text")

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return self.text_en


class ExperimentConfig(models.Model):
    """What the phone is asked to do, and what the student is asked to do."""

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        THRESHOLD = "threshold", "Threshold"

    lab = models.OneToOneField(Lab, on_delete=models.CASCADE, related_name="experiment")
    instructions_en = models.TextField(blank=True)
    instructions_he = models.TextField(blank=True)

    #: **Requested, not configured.** spec §4.1: the phone that ran the spike
    #: delivered ~63 Hz against an assumed 200. A lab asks; the device
    #: answers; the recording stores what actually arrived. The data model
    #: called this `default_sample_rate_hz`, which read like a setting the
    #: app controls — it never was, and the name was quietly promising
    #: something no browser will honour.
    requested_hz = models.PositiveIntegerField(default=60)
    max_duration_ms = models.PositiveIntegerField(default=10_000)

    trigger_kind = models.CharField(max_length=10, choices=Trigger.choices, default=Trigger.MANUAL)
    trigger_threshold = models.FloatField(null=True, blank=True)

    uses_signal_generator = models.BooleanField(default=False)
    tone_frequency_hz = models.PositiveIntegerField(null=True, blank=True)
    strobe_rate_hz = models.PositiveIntegerField(null=True, blank=True)

    instructions = bilingual("instructions")

    class Meta:
        # Ordered because paginating an unordered queryset can repeat or skip
        # rows between pages — pytest warned about exactly that in SL-B2, and
        # a warning describing a wrong answer is a defect, not noise.
        ordering = ("lab_id",)
        verbose_name = "experiment configuration"

    def __str__(self):
        return f"experiment for {self.lab.slug}"


class SensorRequirement(models.Model):
    """One sensor this lab needs, from the one sensor vocabulary.

    `sensor` draws its choices from `SENSORS` — the same tuple `SensorConsent`
    validates against. If the two ever diverged, a lab could require
    something consent has no name for, and nothing would raise: the lab
    would simply refuse forever, for a reason no error message could state.
    A test in tests/test_spr_sl_8.py holds them together.

    There is deliberately no fallback or degradation field. spec §1 decided
    SensorLab does not reshape itself around a phone missing a sensor; it
    says so plainly instead.
    """

    config = models.ForeignKey(
        ExperimentConfig, on_delete=models.CASCADE, related_name="sensor_requirements"
    )
    sensor = models.CharField(max_length=32, choices=SENSOR_CHOICES)
    is_required = models.BooleanField(default=True)
    axis_filter = models.CharField(
        max_length=8, blank=True, help_text="e.g. 'z' when only one axis matters"
    )

    class Meta:
        ordering = ("config_id", "sensor")
        unique_together = ("config", "sensor")

    def __str__(self):
        return f"{self.config.lab.slug} needs {self.sensor}"


class AnalysisConfig(models.Model):
    """What to compute from the capture, and what to compare it against."""

    class Computation(models.TextChoices):
        PEAK = "peak", "Peak"
        MEAN = "mean", "Mean"
        SLOPE = "slope", "Slope"
        PERIOD = "period", "Period"
        FFT_PEAK = "fft_peak", "FFT peak"
        CURVE_FIT = "curve_fit", "Curve fit"
        AREA = "area", "Area"

    class ExpectedSource(models.TextChoices):
        CONSTANT = "constant", "A known constant"
        FORMULA = "formula", "Derived from the student's own inputs"

    lab = models.OneToOneField(Lab, on_delete=models.CASCADE, related_name="analysis")
    computation = models.CharField(max_length=12, choices=Computation.choices)
    expected_source = models.CharField(
        max_length=10, choices=ExpectedSource.choices, default=ExpectedSource.CONSTANT
    )
    expected_value = models.FloatField(null=True, blank=True)
    expected_formula = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=16, blank=True)
    pass_tolerance = models.FloatField(default=10.0, help_text="Percent error still counted a pass")
    explanation_en = models.TextField(blank=True)
    explanation_he = models.TextField(blank=True)

    explanation = bilingual("explanation")

    class Meta:
        ordering = ("lab_id",)
        verbose_name = "analysis configuration"

    def __str__(self):
        return f"analysis for {self.lab.slug}"

    def rendered_explanation(self, language=None):
        return render_markdown(localised(self, "explanation", language))


# ===========================================================================
# One person's run through one lab (data_model.md §5, spec §9.4)
#
# The first table in this app that holds a person's own work rather than
# authored content. Everything Epics E through H produce — predictions,
# recordings, notebook entries, results — hangs off a row here, which is why
# the rules about who may read one, and about what survives a deletion, are
# settled in this sprint rather than in whichever epic first trips over them.
# ===========================================================================


class LabAttemptManager(models.Manager):
    def start(self, user, lab):
        """Begin a lab, or pick up where this person left off.

        **The decision, recorded in docs/sensorlab/backlog.md (SL-D1).**
        Unfinished work resumes; finished work is never reopened.

        Resuming rather than duplicating, because two half-done attempts at
        one lab is a state nothing downstream can read — which of them owns
        the prediction? Better prevented here than tolerated and
        disambiguated in four later epics.

        A completed run stays completed and a new attempt begins beside it,
        because spec §6 wants improvement over time as a learning signal,
        and overwriting the first run throws away precisely that signal. The
        cost is that "the attempt" becomes "which attempt" everywhere after
        this — accepted, and much cheaper than the history being gone.
        """
        open_attempt = self.filter(
            user=user, lab=lab, status=self.model.Status.IN_PROGRESS
        ).order_by("-started_at").first()
        if open_attempt is not None:
            return open_attempt
        return self.create(user=user, lab=lab)

    def shared(self, share_slug):
        """The attempt behind a share link, or None.

        `is_public` is what decides — holding the slug is not permission.
        Returns None rather than raising for an unknown or private slug, so
        a caller cannot tell "no such attempt" from "not shared", which is
        the same reason a draft lab 404s instead of 403ing (SL-B2).
        """
        if not share_slug:
            return None
        return self.filter(share_slug=share_slug, is_public=True).first()


class LabAttempt(models.Model):
    """One run, by one person, through one lab."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sensorlab_attempts"
    )

    #: PROTECT, not CASCADE, and the asymmetry with `user` above is the whole
    #: point. An author tidying an old lab out of the admin would otherwise
    #: take every student's run of it along, with no warning and no undo — so
    #: being refused is the correct answer, and removing a lab that has
    #: history becomes a decision somebody makes out loud. Deleting a person,
    #: by contrast, should take their work with them: a lab belongs to the
    #: course, an attempt belongs to them.
    lab = models.ForeignKey("sensorlab.Lab", on_delete=models.PROTECT, related_name="attempts")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)

    #: A step *name*, from `LAB_STEPS`. Stored rather than computed, because
    #: resuming has to survive the server restarting. See `resume_step` for
    #: what happens when the flow changes under a stored value.
    current_step = models.CharField(max_length=20, default=LAB_STEPS[0])

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    #: Minted at creation, because minting it later means a second write at
    #: the moment somebody is trying to share — and a failure there is a
    #: failure in front of a person. It is inert until `is_public`.
    share_slug = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_public = models.BooleanField(default=False)

    objects = LabAttemptManager()

    class Meta:
        ordering = ("-started_at",)
        indexes = [models.Index(fields=["user", "lab", "status"])]

    def __str__(self):
        return f"{self.user} — {self.lab.slug} ({self.status})"

    # ------------------------------------------------------ the flow

    @property
    def step_is_known(self):
        """Whether `current_step` still names a step this app has.

        A stored step name points at a flow that can grow or lose one, so a
        row written before such a change points at nothing.
        """
        return self.current_step in LAB_STEPS

    @property
    def resume_step(self):
        """Where to actually put this person, whatever is stored.

        Throwing would lock a student out of their own work over a word.
        Silently resetting would throw their progress away without saying
        so. So it falls back and *reports*: `step_is_known` is False, and a
        screen can tell them what happened — the same answer a missing
        translation gets, degrade visibly rather than blank.
        """
        return self.current_step if self.step_is_known else LAB_STEPS[0]

    def advance(self):
        """Move to the next step, or complete. Returns whether it moved.

        Ordered by `LAB_STEPS` rather than by a sequence written here: SL-B4
        made that the one definition of spec §3's flow, and a third copy
        would be the first to disagree.
        """
        if self.status != self.Status.IN_PROGRESS:
            return False

        position = LAB_STEPS.index(self.resume_step)
        if position + 1 < len(LAB_STEPS):
            self.current_step = LAB_STEPS[position + 1]
            self.save(update_fields=["current_step"])
            return True

        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])
        return False
