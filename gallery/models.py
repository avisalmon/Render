"""gallery: the public exhibition of Avi's 10x engineer training.

docs/gallery/spec.md and docs/gallery/data_model.md. The only thing shared with
the rest of the site is the User table, reached through Person (Rule 2).

The skill tables (Skill, SkillVersion, SkillFile, SkillChat, ChatMessage,
AICall, Strike) arrive with their own sprints, SPR-G.5 to G.7.
"""

import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


class GalleryStorage(FileSystemStorage):
    """Screenshots live on the persistent disk under the app's own folder, not
    in babook's MEDIA_ROOT, and are handed out by `views.file`. The folder is
    read from settings on every use, never fixed when the code loads
    (methodology 17)."""

    @property
    def base_location(self):
        return str(settings.GALLERY_FILES_DIR)

    @property
    def location(self):
        import os

        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


FILES = GalleryStorage()


def gallery_storage():
    return FILES


class Bilingual:
    """`tr("name", "en")` reads `name_en`, falling back to the other language
    rather than showing nothing."""

    def tr(self, field, language):
        mine = getattr(self, f"{field}_{language}", "")
        other = getattr(self, f"{field}_{'en' if language == 'he' else 'he'}", "")
        return mine or other


class Training(Bilingual, models.Model):
    """Avi's list for "which training did you join" (REQ-G.4, G.91). A closed
    training leaves the question's list and keeps its people."""

    name_he = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    position = models.PositiveIntegerField(default=0)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name_he


class Topic(Bilingual, models.Model):
    """Avi's list of areas (REQ-G.33). People pick from it; nobody else adds."""

    name_he = models.CharField(max_length=60)
    name_en = models.CharField(max_length=60)
    slug = models.SlugField(max_length=60, unique=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name_en


class Person(models.Model):
    """The gallery's own record of a person (Rule 2). Created the first time a
    signed-in person does something here, never by merely looking."""

    HE, EN = "he", "en"
    LANGUAGES = [(HE, "עברית"), (EN, "English")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gallery_person")
    display_name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, allow_unicode=True)
    language = models.CharField(max_length=2, choices=LANGUAGES, default=HE)
    # Private: the person and Avi only (REQ-G.5). Never in a public answer.
    training = models.ForeignKey(Training, null=True, blank=True, on_delete=models.SET_NULL, related_name="people")
    training_other = models.CharField(max_length=200, blank=True)
    training_set_at = models.DateTimeField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    unlimited_skills = models.BooleanField(default=False)
    skills_blocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["display_name", "id"]

    def __str__(self):
        return self.display_name

    @property
    def admin(self):
        return self.is_admin or self.user.is_superuser

    @property
    def answered_training(self):
        return self.training_set_at is not None


def shot_path(instance, filename):
    return f"shots/{instance.pk or 'new'}-{timezone.now():%Y%m%d%H%M%S}.jpg"


class Exhibit(models.Model):
    """One card in the gallery: a page, a skill or a BKM (REQ-G.10 to G.13)."""

    PAGE, SKILL, BKM = "page", "skill", "bkm"
    KINDS = [(PAGE, "page"), (SKILL, "skill"), (BKM, "bkm")]
    AUTO, UPLOAD, NONE = "auto", "upload", "none"
    SOURCES = [(AUTO, "auto"), (UPLOAD, "upload"), (NONE, "none")]
    WAITING, OK, FAILED = "waiting", "ok", "failed"
    SHOT_STATES = [(WAITING, "waiting"), (OK, "ok"), (FAILED, "failed")]

    owner = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="exhibits")
    kind = models.CharField(max_length=8, choices=KINDS, default=PAGE, db_index=True)
    title = models.CharField(max_length=120)
    blurb = models.CharField(max_length=400, blank=True)
    url = models.URLField(max_length=500, blank=True)
    topics = models.ManyToManyField(Topic, blank=True, related_name="exhibits")
    shot = models.FileField(upload_to=shot_path, storage=gallery_storage, blank=True)
    shot_source = models.CharField(max_length=8, choices=SOURCES, default=NONE)
    shot_status = models.CharField(max_length=8, choices=SHOT_STATES, default=WAITING)
    shot_tried_at = models.DateTimeField(null=True, blank=True)
    shot_tries = models.PositiveSmallIntegerField(default=0)
    shot_taken_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class Like(models.Model):
    """Public: everybody sees the count (REQ-G.20)."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="likes")
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("person", "exhibit")]


class Star(models.Model):
    """Private: only its own person ever reads it (REQ-G.21). A table apart
    from Like, so a filter mistake on one cannot leak the other."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="stars")
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="stars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("person", "exhibit")]


class Comment(models.Model):
    """One thread per card; a reply quotes the comment it answers (REQ-G.22).
    Deleting is soft, so a quote never points at nothing (REQ-G.23)."""

    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="comments")
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    @property
    def deleted(self):
        return self.deleted_at is not None


# ---------------------------------------------------------------- skills (SPR-G.5)


def skill_path(instance, filename):
    return f"skills/{instance.skill_id}/v{instance.number}-{filename}"


class SkillChat(models.Model):
    """The upload conversation, from the first file to the end (REQ-G.50 to
    G.56). SPR-G.5 runs the plain checks; the AI joins in SPR-G.6."""

    OPEN, PUBLISHED, REFUSED, ABANDONED, OUT_OF_BUDGET = "open", "published", "refused", "abandoned", "out_of_budget"
    STATUSES = [(s, s) for s in (OPEN, PUBLISHED, REFUSED, ABANDONED, OUT_OF_BUDGET)]
    CLEAN, RISKY = "clean", "risky"

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="skill_chats")
    skill = models.ForeignKey("Skill", null=True, blank=True, on_delete=models.SET_NULL, related_name="chats")
    status = models.CharField(max_length=16, choices=STATUSES, default=OPEN, db_index=True)
    upload = models.FileField(upload_to="chats/", storage=gallery_storage, blank=True)
    upload_name = models.CharField(max_length=200, blank=True)
    similar_to = models.ForeignKey("Skill", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verdict = models.CharField(max_length=8, blank=True, choices=[(CLEAN, CLEAN), (RISKY, RISKY)])
    findings = models.TextField(blank=True)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    # Where the conversation stands (SPR-G.6): waiting for "go on" after a
    # similar skill, for a fixed file after a risky reading, for "publish"
    # after a clean one, or for a retry after the model failed.
    SIMILAR, FIXING, CONFIRM, RETRY = "similar", "fixing", "confirm", "retry"
    STAGES = [(s, s) for s in (SIMILAR, FIXING, CONFIRM, RETRY)]
    stage = models.CharField(max_length=10, choices=STAGES, blank=True)
    # What the assistant proposes to publish, so "publish" publishes exactly
    # what the person saw (REQ-G.54).
    proposed_blurb = models.CharField(max_length=400, blank=True)
    proposed_topics = models.ManyToManyField("Topic", blank=True, related_name="+")
    platform_note = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]


class ChatMessage(models.Model):
    PERSON, ASSISTANT, SYSTEM = "person", "assistant", "system"
    ROLES = [(PERSON, PERSON), (ASSISTANT, ASSISTANT), (SYSTEM, SYSTEM)]

    chat = models.ForeignKey(SkillChat, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLES)
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]


class Skill(models.Model):
    """What a skill card carries beyond the card (REQ-G.40 to G.42)."""

    CLAUDE, COPILOT = "claude", "copilot"
    ORIGINS = [(CLAUDE, "Claude Code"), (COPILOT, "GitHub Copilot")]
    MAX_UPDATES = 4

    exhibit = models.OneToOneField(Exhibit, on_delete=models.CASCADE, related_name="skill")
    name = models.SlugField(max_length=64)
    origin = models.CharField(max_length=8, choices=ORIGINS, default=CLAUDE)
    current = models.ForeignKey("SkillVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updates_used = models.PositiveSmallIntegerField(default=0)
    downloads = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class SkillVersion(models.Model):
    """One published state of a skill: the first upload, then each update."""

    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveSmallIntegerField()
    upload = models.FileField(upload_to=skill_path, storage=gallery_storage)
    package_claude = models.FileField(upload_to=skill_path, storage=gallery_storage)
    package_copilot = models.FileField(upload_to=skill_path, storage=gallery_storage)
    changes_note = models.TextField(blank=True)
    chat = models.OneToOneField(SkillChat, null=True, blank=True, on_delete=models.SET_NULL, related_name="version")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-number"]
        unique_together = [("skill", "number")]


class SkillFile(models.Model):
    """Each file inside a version, so the check, the page and the download all
    see the same list (Rule 1). Skills are text; the text is kept here so the
    page can show it without opening a zip."""

    version = models.ForeignKey(SkillVersion, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    text = models.TextField(blank=True)

    class Meta:
        ordering = ["path"]


class AICall(models.Model):
    """Every model call, for the 40-cent ceiling, the daily caps and Avi's
    cost per person (REQ-G.63, G.64). Kept when a card or a person is deleted."""

    DUPLICATE, SAFETY, CONVERT, TAG, REPLY = "duplicate", "safety", "convert", "tag", "reply"
    PURPOSES = [(p, p) for p in (DUPLICATE, SAFETY, CONVERT, TAG, REPLY)]

    # SET_NULL, not PROTECT: a cost record must never stop an account from
    # being deleted elsewhere on the site (security sweep, 2026-11-09).
    person = models.ForeignKey(Person, null=True, on_delete=models.SET_NULL, related_name="ai_calls")
    chat = models.ForeignKey(SkillChat, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_calls")
    purpose = models.CharField(max_length=10, choices=PURPOSES)
    model = models.CharField(max_length=60)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]


class Strike(models.Model):
    """A risky skill upload (REQ-G.70 to G.72). The first is a warning; the
    second blocks the person and mails Avi once."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="strikes")
    chat = models.ForeignKey(SkillChat, null=True, on_delete=models.SET_NULL, related_name="strikes")
    findings = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    emailed_at = models.DateTimeField(null=True, blank=True)
    # Set when Avi lifts a block: kept for the record, no longer counted.
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


# ---------------------------------------------------------------- materials (SPR-G.11)


def material_path(instance, filename):
    import re

    safe = re.sub(r"[^\w.\-]", "_", filename)[-80:]
    return f"materials/{timezone.now():%Y%m%d%H%M%S}-{safe}"


YOUTUBE_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([\w-]{11})")


def youtube_id(url):
    m = YOUTUBE_ID.search(url or "")
    return m.group(1) if m else ""


class Material(models.Model):
    """Two shelves (REQ-G.120 to G.126), the same as cohort's (copied, not
    shared, Rule 2). With no owner: the shared shelf, Avi's, seen by every
    signed-in person in the order he sets. With an owner: that person's own
    shelf, seen by them alone, Avi included."""

    VIDEO, FILE, COURSE, LINK = "video", "file", "course", "link"
    KINDS = [(VIDEO, "video"), (FILE, "file"), (COURSE, "course"), (LINK, "link")]

    kind = models.CharField(max_length=8, choices=KINDS)
    title = models.CharField(max_length=160)
    line = models.CharField(max_length=280)
    url = models.URLField(max_length=500, blank=True)
    youtube_id = models.CharField(max_length=20, blank=True)
    file = models.FileField(upload_to=material_path, storage=gallery_storage, blank=True)
    owner = models.ForeignKey(Person, null=True, blank=True, on_delete=models.CASCADE, related_name="materials")
    position = models.PositiveIntegerField(default=0, db_index=True)
    # Where a copied item came from ("cohort:<id>"), so the one-time copy never
    # brings an item twice (SPR-G.11).
    source = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["position", "created_at", "id"]

    def save(self, *args, **kwargs):
        self.youtube_id = youtube_id(self.url) if self.kind == self.VIDEO else ""
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
