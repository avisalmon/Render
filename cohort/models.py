"""cohort: the home of Avi's teachers' course on leading innovation with AI.

docs/cohort/spec.md and docs/cohort/data_model.md. The only thing shared with
the rest of the site is the User table, reached through Member (Rule 2).
"""

import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


class PrivateStorage(FileSystemStorage):
    """Screenshots and documents live outside MEDIA_ROOT, which is served to
    anybody, and are handed out by `views.private_file` to people inside.
    The folder is read from settings on every use rather than fixed when the
    code loads, so the view and the storage can never disagree about it."""

    @property
    def base_location(self):
        return str(settings.COHORT_PRIVATE_DIR)

    @property
    def location(self):
        import os

        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


PRIVATE = PrivateStorage()


def private_storage():
    return PRIVATE


class Member(models.Model):
    """A person who asked to join. Their status decides everything they see
    (REQ-C.2 to C.5); `access.can_enter` is the one place that reads it."""

    PENDING, APPROVED, DECLINED = "pending", "approved", "declined"
    STATUSES = [(PENDING, "ממתין לאישור"), (APPROVED, "מאושר"), (DECLINED, "לא אושר")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cohort_member")
    display_name = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING, db_index=True)
    is_admin = models.BooleanField(default=False)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    welcomed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"

    @property
    def admin(self):
        return self.is_admin or self.user.is_superuser


def shot_path(instance, filename):
    return f"shots/{instance.pk or 'new'}-{timezone.now():%Y%m%d%H%M%S}.jpg"


class Exhibit(models.Model):
    """A site hung in the exhibition (REQ-C.10 to C.12)."""

    AUTO, UPLOAD, NONE = "auto", "upload", "none"
    SOURCES = [(AUTO, "צילום אוטומטי"), (UPLOAD, "תמונה שהועלתה"), (NONE, "אין")]
    WAITING, OK, FAILED = "waiting", "ok", "failed"
    SHOT_STATES = [(WAITING, "מצלם"), (OK, "צולם"), (FAILED, "לא הצליח")]

    owner = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="exhibits")
    title = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    blurb = models.CharField(max_length=280, blank=True)
    shot = models.FileField(upload_to=shot_path, storage=private_storage, blank=True)
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
    """Public: everybody sees the count (REQ-C.13)."""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="likes")
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("member", "exhibit")]


class Star(models.Model):
    """Private: only its own member ever reads it (REQ-C.14). A table apart
    from Like, so a filter mistake on one cannot leak the other."""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="stars")
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="stars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("member", "exhibit")]


class Comment(models.Model):
    """One thread per exhibit; a reply quotes the comment it answers, the way
    WhatsApp does (REQ-C.15). Deleting is soft, so a quote never points at
    nothing (REQ-C.16)."""

    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="comments")
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


class Track(models.Model):
    """A subject track: a container of three links its owner keeps
    (REQ-C.20 to C.23). Created through the chat, by `cohort_track`."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=60, unique=True, allow_unicode=True)
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="tracks")
    is_example = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)
    vision_url = models.URLField(max_length=500, blank=True)
    graduate_url = models.URLField(max_length=500, blank=True)
    project_url = models.URLField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


def material_path(instance, filename):
    safe = re.sub(r"[^\w.\-]", "_", filename)[-80:]
    return f"materials/{timezone.now():%Y%m%d%H%M%S}-{safe}"


YOUTUBE_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([\w-]{11})")


def youtube_id(url):
    m = YOUTUBE_ID.search(url or "")
    return m.group(1) if m else ""


class Material(models.Model):
    """Avi's shelf (REQ-C.30 to C.34), in the order he added it."""

    VIDEO, FILE, COURSE = "video", "file", "course"
    KINDS = [(VIDEO, "סרטון"), (FILE, "מסמך"), (COURSE, "הדרכה ב-babook")]

    kind = models.CharField(max_length=8, choices=KINDS)
    title = models.CharField(max_length=160)
    line = models.CharField(max_length=280)
    url = models.URLField(max_length=500, blank=True)
    youtube_id = models.CharField(max_length=20, blank=True)
    file = models.FileField(upload_to=material_path, storage=private_storage, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        self.youtube_id = youtube_id(self.url) if self.kind == self.VIDEO else ""
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
