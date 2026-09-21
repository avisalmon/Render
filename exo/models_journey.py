"""The builder journey's models (data_model.md §3).

Split into its own module purely for readability — `models.py` imports
everything here, so Django sees one app's models as usual and the migration
chain is unaffected. The reference/access models live in `models.py`; this is
the part that belongs to one person's journey.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_reference import DEFAULT_LANGUAGE, ExoAttribute, NewspaperStyle


class Concept(models.Model):
    """One person's exponential-organization concept, in progress.

    The journey's state lives here — `stage` is the single answer to "where am
    I", and resuming is just reading it. Everything downstream hangs off this
    row, so deleting it takes the whole journey with it (spec §5.0).
    """

    class Stage(models.TextChoices):
        INTERVIEW = "interview", "Interview"
        BRAINSTORM = "brainstorm", "Brainstorm"
        OPTIONS = "options", "Options"
        OUTPUT = "output", "Output"

    #: The order the stages are walked, used by the progress rail and by the
    #: "have I reached this yet" check. One list, so no template counts stages.
    STAGE_ORDER = ["interview", "brainstorm", "options", "output"]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exo_concepts",
    )
    title = models.CharField(max_length=160)
    stage = models.CharField(
        max_length=12, choices=Stage.choices, default=Stage.INTERVIEW,
    )
    language = models.CharField(max_length=2, default=DEFAULT_LANGUAGE)

    #: The settled output of the interview (spec §5.1). Plain fields rather
    #: than a model: data_model.md decision 2.
    mtp = models.TextField(blank=True)
    special = models.TextField(blank=True)
    unique = models.TextField(blank=True)

    position = models.PositiveIntegerField(default=0)
    #: Set when the user goes back a stage, so downstream work can be shown as
    #: possibly out of date without deleting any of it (spec §5.5).
    downstream_stale = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "-updated_at")

    def __str__(self):
        return self.title

    def stage_index(self):
        try:
            return self.STAGE_ORDER.index(self.stage)
        except ValueError:
            return 0

    def has_reached(self, stage):
        try:
            return self.stage_index() >= self.STAGE_ORDER.index(stage)
        except ValueError:
            return False

    def advance_to(self, stage):
        """Move forward only. Going back is `return_to`, which has different
        consequences and should read differently at the call site."""
        if self.STAGE_ORDER.index(stage) > self.stage_index():
            self.stage = stage
            self.save(update_fields=["stage", "updated_at"])
        return self

    def return_to(self, stage):
        """Go back, keeping everything downstream but marking it as possibly
        out of date (spec §5.5, D5.2). Nothing is deleted by navigation."""
        self.stage = stage
        self.downstream_stale = True
        self.save(update_fields=["stage", "downstream_stale", "updated_at"])
        return self


class InterviewMessage(models.Model):
    """One turn of the stage-1 chat. Rows, so a refresh or a failed AI call
    can never lose the transcript (spec §5.1, G7)."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    concept = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class BrainstormEntry(models.Model):
    """One idea the user wrote themselves, for one attribute (spec §5.2).

    Their own thinking, captured before the AI says anything — which is the
    point of the stage, and what the AI is required to build on.
    """

    concept = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="entries",
    )
    attribute = models.ForeignKey(
        ExoAttribute, on_delete=models.CASCADE, related_name="entries",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Framework order; see the note on ExoAttribute.Meta.
        ordering = ("attribute__order", "id")

    def __str__(self):
        return f"{self.attribute.key}: {self.text[:40]}"


class GeneratedOption(models.Model):
    """One AI-proposed option for one attribute, or one the user typed.

    `is_user_authored` matters at regenerate time: the user's own option, and
    anything they selected, is never swept away by asking for more (spec §5.3).
    """

    concept = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="options",
    )
    attribute = models.ForeignKey(
        ExoAttribute, on_delete=models.CASCADE, related_name="options",
    )
    content = models.TextField()
    research_note = models.TextField(blank=True)
    is_selected = models.BooleanField(default=False)
    is_user_authored = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Framework order; see the note on ExoAttribute.Meta.
        ordering = ("attribute__order", "order", "id")

    def __str__(self):
        return f"{self.attribute.key}: {self.content[:40]}"


class PressRelease(models.Model):
    """The result: a detailed document and an Amazon-style press release, set
    in a newspaper (spec §5.4, §6).

    Visibility is **computed, not scheduled** (spec §7.1): a `timed` release
    stops matching the museum query the moment its time passes, so there is no
    expiry job to run and nothing to go wrong while nobody is watching.
    """

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public forever"
        TIMED = "timed", "Public until a time"
        SPECIFIC = "specific", "Specific people"
        PRIVATE = "private", "Only me"

    concept = models.OneToOneField(
        Concept, on_delete=models.CASCADE, related_name="release",
    )
    headline = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    document_body = models.TextField(blank=True)
    language = models.CharField(max_length=2, default=DEFAULT_LANGUAGE)

    newspaper_style = models.ForeignKey(
        NewspaperStyle, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="releases",
    )
    exponential_score = models.PositiveIntegerField(null=True, blank=True)
    score_rationale = models.TextField(blank=True)
    stress_test_feedback = models.TextField(blank=True)

    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC,
    )
    public_until = models.DateTimeField(null=True, blank=True)
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="exo_shared_releases",
    )
    #: Moderation, independent of the owner's choice (spec §7.2, F2.5).
    hidden_by_admin = models.BooleanField(default=False)
    #: Set when the text has been edited by hand, so regenerate must confirm.
    edited_by_owner = models.BooleanField(default=False)

    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.headline or f"release {self.pk}"

    # -- visibility, computed rather than scheduled --------------------- #

    def is_public_now(self, now=None):
        """Is this on the public wall at this moment?"""
        if self.hidden_by_admin:
            return False
        if self.visibility == self.Visibility.PUBLIC:
            return True
        if self.visibility == self.Visibility.TIMED:
            now = now or timezone.now()
            return bool(self.public_until and self.public_until > now)
        return False

    def visible_to(self, user, now=None):
        """May this person open it?"""
        user_id = getattr(user, "id", None)
        if user_id is not None and user_id == self.concept.owner_id:
            return True  # the owner always sees their own work
        if self.is_public_now(now=now):
            return True
        if self.hidden_by_admin:
            return False
        if self.visibility == self.Visibility.SPECIFIC:
            if user is None or not getattr(user, "is_authenticated", False):
                return False
            return self.shared_with.filter(pk=user.pk).exists()
        return False

    @property
    def like_count(self):
        return self.like_rows.count()


class PressReleaseLike(models.Model):
    """One like, by one person, on one release — attributable, and impossible
    to double-count (spec §7.3)."""

    release = models.ForeignKey(
        PressRelease, on_delete=models.CASCADE, related_name="like_rows",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exo_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["release", "user"], name="exo_one_like_per_person",
            )
        ]


class AiCall(models.Model):
    """Every call to a provider, logged (spec §8, G5).

    Not for billing precision — for answering "what is this costing, and who is
    spending it" without guessing, and to give the daily guard something real
    to count.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exo_ai_calls",
    )
    concept = models.ForeignKey(
        Concept, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ai_calls",
    )
    #: Which slot the call was for, where that applies (the options stage).
    #: Recorded because the per-stage ceiling has to be counted *per slot*:
    #: a member filling all thirteen slots is doing the workshop exactly as
    #: intended, and a budget shared across the slots would lock them out
    #: partway through. Found by running the real journey, not by reading.
    attribute = models.ForeignKey(
        ExoAttribute, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ai_calls",
    )
    task = models.CharField(max_length=40)
    model = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens
