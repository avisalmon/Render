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

    PENDING, APPROVED, DECLINED, WAITING_SEAT = "pending", "approved", "declined", "waiting_seat"
    STATUSES = [(PENDING, "Waiting"), (APPROVED, "In"), (DECLINED, "Not approved"), (WAITING_SEAT, "Waiting for a seat")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="design3d_maker")
    display_name = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=STATUSES, default=PENDING, db_index=True)
    reason = models.CharField(max_length=300, blank=True)
    is_admin = models.BooleanField(default=False)
    daily_limit_usd = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    welcomed_at = models.DateTimeField(null=True, blank=True)
    # Friends (Avi, 2026-10-30): every person has a link of their own to send
    # friends; whoever asks to join through it is remembered here, for the
    # points of the gamification plan.
    ref_code = models.CharField(max_length=16, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals")
    # Chapter 8 (Avi, 2026-10-30): turns, seats and the tour.
    turns_left = models.IntegerField(null=True, blank=True, help_text="Turns left; null is no limit")
    invited = models.BooleanField(default=False, help_text="Came in by an invitation: counts against the seats")
    rewarded_at = models.DateTimeField(null=True, blank=True, help_text="When their first part gave their friend 30 turns")
    tour_done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def code(self):
        """This person's link code, made on first use."""
        if not self.ref_code:
            import secrets

            while True:
                code = secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")
                if not Maker.objects.filter(ref_code=code).exists():
                    break
            Maker.objects.filter(pk=self.pk, ref_code__isnull=True).update(ref_code=code)
            self.refresh_from_db(fields=["ref_code"])
        return self.ref_code

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


def mf_path(instance, filename):
    return f"stl/{instance.design_id}/v{instance.number}-{timezone.now():%Y%m%d%H%M%S}.3mf"


def preview_path(instance, filename):
    return f"previews/{instance.design_id}/v{instance.number}-{timezone.now():%Y%m%d%H%M%S}.png"


def _friend_code():
    import secrets

    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")


class FriendLink(models.Model):
    """One friend's link, made fresh for every send (Avi, 2026-10-30: "rotate
    the key every time I access the page or copy it or share it, so I won't
    send the same one twice"). It lets one person in, like a one-time link,
    and credits the person who sent it. That same person may open it again."""

    maker = models.ForeignKey(Maker, on_delete=models.CASCADE, related_name="friend_links")
    code = models.CharField(max_length=16, unique=True, default=_friend_code)
    created_at = models.DateTimeField(default=timezone.now)
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Settings(models.Model):
    """design3d's own settings, one row (Chapter 8)."""

    seat_limit = models.PositiveIntegerField(default=20, help_text="Invited newcomers who may be in")
    last_export_at = models.DateTimeField(null=True, blank=True, help_text="When the chats were last sent for analysis")

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]


def export_path(instance, filename):
    return f"exports/{timezone.now():%Y%m%d-%H%M%S}-design3d.zip"


class Export(models.Model):
    """One send of the chats for analysis (REQ-D3.75)."""

    created_at = models.DateTimeField(default=timezone.now)
    since = models.DateTimeField(null=True, blank=True)
    file = models.FileField(upload_to=export_path, storage=private_storage, blank=True)
    designs = models.PositiveIntegerField(default=0)
    messages = models.PositiveIntegerField(default=0)
    pictures = models.PositiveIntegerField(default=0)
    sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


def _invite_token():
    import secrets

    return secrets.token_urlsafe(32)


def _invite_expiry():
    from datetime import timedelta

    return timezone.now() + timedelta(days=14)


class Invite(models.Model):
    """A one-time invitation link, like a coupon (Avi, 2026-10-30): Avi makes
    one with a tap and sends it however he likes (WhatsApp, mail, any share
    sheet). Whoever opens it first, signed in or after signing up, is let in
    and the token is burned. That same person may open it again; nobody else
    can (methodology 55). Unused, it ends after 14 days or when Avi revokes it.
    `email` and `name` are optional notes; nothing is mailed by design3d."""

    email = models.EmailField(blank=True)
    name = models.CharField(max_length=80, blank=True)
    token = models.CharField(max_length=64, unique=True, default=_invite_token)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=_invite_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite for {self.email} ({self.status})"

    @property
    def status(self):
        if self.used_at:
            return "used"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "open"


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
    pin = models.JSONField(null=True, blank=True,
                           help_text="A point the person tapped on the part: {x, y, z, nx, ny, nz, version}, mm in the code's coordinates")
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


def reference_path(instance, filename):
    ext = ".png" if filename.endswith(".png") else ".stl"
    return f"stl/{instance.message.design_id}/ref-{timezone.now():%Y%m%d%H%M%S%f}{ext}"


class Reference(models.Model):
    """An STL a person attached to a message (Avi, 2026-10-30): its sizes and
    three views go to the chat as reference measures, and the code may build
    on it with import("reference.stl"), the one file it may read."""

    message = models.ForeignKey("Message", on_delete=models.CASCADE, related_name="references")
    file = models.FileField(upload_to=reference_path, storage=private_storage)
    sheet = models.FileField(upload_to=reference_path, storage=private_storage, blank=True)
    name = models.CharField(max_length=120)
    size_mm = models.CharField(max_length=40, blank=True)
    triangles = models.PositiveIntegerField(default=0)
    bounds = models.JSONField(default=list, blank=True, help_text="[[min x, y, z], [max x, y, z]] in the file's own mm")
    created_at = models.DateTimeField(default=timezone.now)


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

    CHAT, SLIDERS, COPY = "chat", "sliders", "copy"
    MADE_BY = [(CHAT, "Chat"), (SLIDERS, "Sliders"), (COPY, "A copy of a shared design")]
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
    file_3mf = models.FileField(upload_to=mf_path, storage=private_storage, blank=True,
                                help_text="Several parts: every printed part as its own object, on the plate (Chapter 7)")
    fit = models.JSONField(null=True, blank=True, help_text="Several parts: findings between parts in the assembly")
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def warnings(self):
        return [c for c in (self.checks or []) + (self.fit or []) if c.get("level") == "warn"]

    @property
    def all_checks(self):
        """Print findings and fit findings together; None until checked."""
        if self.checks is None:
            return None
        return list(self.checks) + list(self.fit or [])

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


def part_path(part, filename):
    """Under stl/, so the private file view (REQ-D3.41) serves it after its check."""
    return f"stl/{part.version.design_id}/v{part.version.number}-{timezone.now():%Y%m%d%H%M%S}-{filename}"


class Part(models.Model):
    """One part of a version that has several (Chapter 7, approved by Avi
    2026-10-29). A one-part version has none and works as before; for several,
    `Version.stl` is the print plate."""

    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=40)
    label = models.CharField(max_length=80)
    position = models.PositiveIntegerField(default=0)
    count = models.PositiveIntegerField(default=1)
    printed = models.BooleanField(default=True)
    stl = models.FileField(upload_to=part_path, storage=private_storage, blank=True)
    print_stl = models.FileField(upload_to=part_path, storage=private_storage, blank=True)
    orientation = models.CharField(max_length=40, blank=True)
    size_mm = models.CharField(max_length=40, blank=True)
    checks = models.JSONField(null=True, blank=True)
    color = models.CharField(max_length=7, default="#ff7a1a")

    class Meta:
        ordering = ["version", "position"]
        unique_together = [("version", "name")]

    def __str__(self):
        return f"{self.label} (v{self.version.number})"

    @property
    def rotation(self):
        """The rotation it was printed with, as the model's hint for next time."""
        try:
            return [float(r) for r in self.orientation.split()[0].split(",")][:3]
        except (ValueError, IndexError):
            return [0.0, 0.0, 0.0]

    def declaration(self):
        return {"name": self.name, "label": self.label, "count": self.count, "printed": self.printed, "print": self.rotation}


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
    # Sizes on the part (Avi, 2026-10-30): D1, D2 for what the chat knows, M1,
    # M2 for what the person must measure; `dim` is where the size runs on the
    # part, {"from": [x, y, z], "to": [x, y, z], "at": value}, in the code's mm.
    tag = models.CharField(max_length=8, blank=True)
    needs_measuring = models.BooleanField(default=False)
    dim = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["version", "position", "id"]
