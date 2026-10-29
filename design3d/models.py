"""design3d: 3D design through a chat.

docs/design3d/spec.md and docs/design3d/data_model.md. The only thing shared
with the rest of the site is the User table, reached through Maker (Rule 2).
"""

from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


class PrivateStorage(FileSystemStorage):
    """Pictures, STLs and previews live outside the public media folder and
    are handed out by `views.file` after a permission check. The folder is
    read from settings on every use, never fixed at import (methodology 17)."""

    @property
    def base_location(self):
        return str(settings.DESIGN3D_PRIVATE_DIR)

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


class Maker(models.Model):
    """A person who asked to come in. Their status decides everything they
    see (REQ-D3.2, D3.3); `access.can_enter` is the one place that reads it."""

    PENDING, APPROVED, DECLINED = "pending", "approved", "declined"
    STATUSES = [(PENDING, "Waiting"), (APPROVED, "In"), (DECLINED, "Not approved")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="design3d_maker")
    display_name = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING, db_index=True)
    reason = models.CharField(max_length=300, blank=True)
    is_admin = models.BooleanField(default=False)
    daily_limit_usd = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    welcomed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.display_name} ({self.status})"

    @property
    def admin(self):
        return self.is_admin or self.user.is_superuser

    @property
    def limit(self):
        """Dollars a day, or None for no limit (admins)."""
        if self.admin:
            return None
        return self.daily_limit_usd if self.daily_limit_usd is not None else Decimal(str(settings.DESIGN3D_DAILY_LIMIT_USD))


def picture_path(instance, filename):
    return f"pictures/{timezone.now():%Y%m}/{instance.message.design_id}-{timezone.now():%d%H%M%S%f}.jpg"


def stl_path(instance, filename):
    return f"stl/{instance.design_id}/v{instance.number}-{timezone.now():%Y%m%d%H%M%S}.stl"


def preview_path(instance, filename):
    return f"previews/{instance.design_id}/v{instance.number}-{timezone.now():%Y%m%d%H%M%S}.png"


class Design(models.Model):
    """One project: its own chat, pictures and versions (REQ-D3.10)."""

    owner = models.ForeignKey(Maker, on_delete=models.CASCADE, related_name="designs")
    title = models.CharField(max_length=100, default="New design")
    current = models.ForeignKey("Version", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_shared = models.BooleanField(default=False, db_index=True)
    shared_at = models.DateTimeField(null=True, blank=True)
    copied_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="copies")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title


class Message(models.Model):
    """One turn of the chat, in order. The history sent to the model is
    built from these rows. An assistant turn runs in the background; its
    `state` is what the page polls (REQ-D3.12)."""

    PERSON, ASSISTANT = "person", "assistant"
    ROLES = [(PERSON, "Person"), (ASSISTANT, "Assistant")]
    THINKING, BUILDING, DONE, FAILED = "thinking", "building", "done", "failed"
    STATES = [(THINKING, "Thinking"), (BUILDING, "Building"), (DONE, "Done"), (FAILED, "Failed")]

    design = models.ForeignKey(Design, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLES)
    state = models.CharField(max_length=10, choices=STATES, default=DONE)
    step = models.CharField(max_length=80, blank=True, help_text="What a running turn is doing now, for the page")
    trail = models.JSONField(default=list, blank=True,
                             help_text="How the turn went: [seconds from the start, what happened], for the page")
    text = models.TextField(blank=True)
    assumptions = models.JSONField(default=list, blank=True)
    version = models.ForeignKey("Version", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    model = models.CharField(max_length=40, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_cached = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=Decimal("0"))
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]


class Picture(models.Model):
    """An image sent with a message (REQ-D3.14). Its owner's only, never
    shown with a shared design."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="pictures")
    image = models.ImageField(upload_to=picture_path, storage=private_storage)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)


class Version(models.Model):
    """One build of the part, from the chat or from the sliders (REQ-D3.22).
    It keeps its whole code, so it can be rebuilt or continued from alone."""

    CHAT, SLIDERS = "chat", "sliders"
    MADE_BY = [(CHAT, "Chat"), (SLIDERS, "Sliders")]
    BUILDING, READY, FAILED = "building", "ready", "failed"
    STATES = [(BUILDING, "Building"), (READY, "Ready"), (FAILED, "Failed")]

    design = models.ForeignKey(Design, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    made_by = models.CharField(max_length=10, choices=MADE_BY, default=CHAT)
    code = models.TextField()
    status = models.CharField(max_length=10, choices=STATES, default=BUILDING)
    error = models.TextField(blank=True)
    stl = models.FileField(upload_to=stl_path, storage=private_storage, blank=True)
    preview = models.ImageField(upload_to=preview_path, storage=private_storage, blank=True)
    size_mm = models.CharField(max_length=40, blank=True)
    build_seconds = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    checks = models.JSONField(null=True, blank=True,
                              help_text="Print-ready findings (design3d/printcheck.py); [] is ready to print, null not checked yet")
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def warnings(self):
        return [c for c in self.checks or [] if c.get("level") == "warn"]

    @property
    def print_summary(self):
        """One line for the chat: ready to print, or how many warnings."""
        if self.checks is None:
            return ""
        n = len(self.warnings)
        return "ready to print" if not n else f"{n} print warning{'s' if n > 1 else ''}"

    class Meta:
        ordering = ["design", "number"]
        unique_together = [("design", "number")]

    def __str__(self):
        return f"{self.design} v{self.number}"


class Parameter(models.Model):
    """One slider: a key size the chat named at the top of the code
    (REQ-D3.23)."""

    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name="parameters")
    name = models.CharField(max_length=40)
    label = models.CharField(max_length=60)
    value = models.DecimalField(max_digits=9, decimal_places=3)
    minimum = models.DecimalField(max_digits=9, decimal_places=3)
    maximum = models.DecimalField(max_digits=9, decimal_places=3)
    step = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("1"))
    unit = models.CharField(max_length=8, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["version", "position", "id"]
