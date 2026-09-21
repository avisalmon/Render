"""exo — the data model (docs/exo/data_model.md).

Three groups of models, in the order the data model document describes them:
reference/content that is seeded once, access, and the builder journey.

**Bilingual by field pairs, not by row.** Every user-facing string on a
reference model exists as `<field>_he` and `<field>_en`. This is the same
decision `sensorlab` made and for the same reason (spec §0.3): the app owns
its copy outright, and a second row per language would let the two drift
apart with nothing to notice. `BilingualMixin.tr()` is the single reader, and
it **falls back to the other language rather than rendering blank**, because a
half-authored page should still be useful.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

# The two languages this app speaks. Hebrew is the default (spec §0.3).
LANGUAGES = ("he", "en")
DEFAULT_LANGUAGE = "he"


class BilingualMixin:
    """Read a `<field>_he` / `<field>_en` pair in the active language."""

    def tr(self, field, language=DEFAULT_LANGUAGE):
        language = language if language in LANGUAGES else DEFAULT_LANGUAGE
        other = "en" if language == "he" else "he"
        value = (getattr(self, f"{field}_{language}", "") or "").strip()
        if value:
            return value
        # Fall back rather than show an empty page: a resource authored in one
        # language only is still worth reading (spec §0.3).
        return (getattr(self, f"{field}_{other}", "") or "").strip()


class ExoAttribute(BilingualMixin, models.Model):
    """One slot of the framework: MTP, the five SCALE, the five IDEAS, and the
    two extra ExO-Canvas blocks. Shared by the public Learn pages and by the
    builder's brainstorm and options, so the two can never disagree about what
    the eleven attributes are."""

    class Category(models.TextChoices):
        MTP = "MTP", "MTP"
        SCALE = "SCALE", "SCALE"
        IDEAS = "IDEAS", "IDEAS"
        EXTRA = "EXTRA", "Extra"

    #: Stable identifier used in URLs, seed matching and prompts. Never changes.
    key = models.SlugField(max_length=40, unique=True)
    category = models.CharField(max_length=6, choices=Category.choices)
    order = models.PositiveIntegerField(default=0)

    name_he = models.CharField(max_length=120, blank=True)
    name_en = models.CharField(max_length=120, blank=True)
    short_def_he = models.TextField(blank=True)
    short_def_en = models.TextField(blank=True)
    #: Shown beside the slot while brainstorming — the question that unsticks
    #: someone staring at an empty box (spec §5.2).
    prompt_hint_he = models.TextField(blank=True)
    prompt_hint_en = models.TextField(blank=True)

    class Meta:
        # Framework order, not alphabetical. `order` is already globally
        # sequenced (MTP 0, SCALE 1-5, IDEAS 6-10, the two extras 11-12),
        # and sorting by `category` first put EXTRA before IDEAS before
        # MTP because those are alphabetical -- which is how the builder
        # came to open on "First launch steps" with the purpose halfway
        # down the page.
        ordering = ("order", "key")

    def __str__(self):
        return f"{self.key} ({self.category})"

    @property
    def is_extra(self):
        return self.category == self.Category.EXTRA


class LearnResource(BilingualMixin, models.Model):
    """A piece of the public handout. Attached to an attribute (the summary of
    that principle) or standing alone (intro, how to read the book)."""

    key = models.SlugField(max_length=60, unique=True)
    attribute = models.ForeignKey(
        ExoAttribute, null=True, blank=True,
        on_delete=models.CASCADE, related_name="resources",
    )
    title_he = models.CharField(max_length=200, blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    body_he = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    #: May be the same video in both languages, or empty.
    youtube_url_he = models.URLField(blank=True)
    youtube_url_en = models.URLField(blank=True)
    book_reference_he = models.CharField(max_length=200, blank=True)
    book_reference_en = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "key")

    def __str__(self):
        return self.key


class NewspaperStyle(BilingualMixin, models.Model):
    """One selectable look for a press release (spec §6, E1).

    A style is a data row plus a template partial, so Avi can add one without
    touching Python. `supports_rtl` / `supports_ltr` exist because a masthead
    designed for Hebrew does not automatically work for English.
    """

    key = models.SlugField(max_length=40, unique=True)
    name_he = models.CharField(max_length=120, blank=True)
    name_en = models.CharField(max_length=120, blank=True)
    description_he = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    #: CSS class applied to the paper frame; the stylesheet defines the look.
    css_class = models.CharField(max_length=60, default="paper-classic")
    supports_rtl = models.BooleanField(default=True)
    supports_ltr = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "key")

    def __str__(self):
        return self.key

    def supports(self, language):
        return self.supports_rtl if language == "he" else self.supports_ltr


class Membership(models.Model):
    """What `exo` knows about a person, kept out of the shared account
    (building_an_app.md Rule 2).

    It carries two unrelated-looking things for one good reason: this is the
    app's *only* per-user row, so the language choice and the approval workflow
    both live here rather than inviting a second profile model. The **gate** is
    the Django group `exo_members`; this row is the **workflow** behind it.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exo_membership",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.REQUESTED,
    )
    #: The person's own language choice, so it follows them to a new device
    #: rather than depending on a cookie (spec §0.3).
    language = models.CharField(max_length=2, default=DEFAULT_LANGUAGE)
    #: What a new press release starts as. Default is "share forever".
    default_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC,
    )

    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exo_decisions",
    )

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self):
        return f"{self.user} — {self.status}"

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED
