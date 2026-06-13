"""CrashTech — hardware hackathon platform (EPIC-6.5).

babook is the host system: CrashTech owns no auth, it grants per-hackathon roles
to existing users. Models live here and are re-exported from app/models.py so
Django registers them under the `app` label. The lifecycle state machine on
``Hackathon`` is the spine — every CrashTech surface gates on ``status``.
"""
import secrets
import uuid as _uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Hackathon(models.Model):
    """A timed, hardware-centric hackathon (REQ-6.5.1).

    Lifecycle: setup → readiness → active (LIVE) → closed → glory (permanent).
    """
    STATUS_ORDER = ["setup", "readiness", "active", "closed", "glory"]
    STATUS_CHOICES = [
        ("setup", "Setup"), ("readiness", "Readiness"), ("active", "Live event"),
        ("closed", "Closed"), ("glory", "Glory"),
    ]
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    submission_deadline = models.DateTimeField()
    team_size = models.PositiveIntegerField(default=3)
    github_repo_url = models.CharField(max_length=500, blank=True, default="")
    hardware_stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="setup")
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crashtech_organized")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "hackathon"
            slug, i = base, 2
            while Hackathon.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    # --- lifecycle state machine (REQ-6.5.1) ---
    def advance(self):
        """Move to the next lifecycle status; return False if already at glory."""
        idx = self.STATUS_ORDER.index(self.status)
        if idx >= len(self.STATUS_ORDER) - 1:
            return False
        self.status = self.STATUS_ORDER[idx + 1]
        self.save(update_fields=["status"])
        return True

    @property
    def can_edit_setup(self):
        """Config + challenge authoring + judge assignment are pre-kickoff only."""
        return self.status in ("setup", "readiness")

    @property
    def challenges_visible(self):
        """Challenges are secret until kickoff (entering 'active')."""
        return self.status in ("active", "closed", "glory")

    @property
    def accepts_submissions(self):
        """Live and before the deadline gate (REQ-6.5.16)."""
        return self.status == "active" and timezone.now() <= self.submission_deadline

    @property
    def is_glory(self):
        return self.status == "glory"

    @property
    def status_label(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class HackRole(models.Model):
    """A per-hackathon role grant (REQ-6.5.2). Many-to-many: a user may hold
    several roles on one event and different roles across events."""
    ROLES = [
        ("organizer", "Organizer"), ("admin", "Admin"),
        ("judge", "Judge"), ("participant", "Participant"),
    ]
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="roles")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crashtech_roles")
    role = models.CharField(max_length=12, choices=ROLES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("hackathon", "user", "role")]

    def __str__(self):
        return f"{self.user.username}:{self.role}@{self.hackathon.slug}"


class Team(models.Model):
    """A hackathon team (REQ-6.5.7). Members are babook users; hardware status
    tracks the physical kit; glory_consent is captured up-front (DEC-58)."""
    HARDWARE = [("pending", "Pending"), ("shipped", "Shipped"), ("received", "Received")]
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=120)
    members = models.ManyToManyField(User, blank=True, related_name="crashtech_teams")
    hardware_status = models.CharField(max_length=10, choices=HARDWARE, default="pending")
    glory_consent = models.BooleanField(default=False)
    # anonymized public label, assigned stably per hackathon (REQ-6.5.15)
    anon_ordinal = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = [("hackathon", "name")]

    def __str__(self):
        return self.name

    @property
    def anon_label(self):
        return f"Team {self.anon_ordinal}" if self.anon_ordinal else "Team ?"


class Challenge(models.Model):
    """A hackathon challenge (REQ-6.5.4). Secret (visible=False) until kickoff.

    Two scoring modes: pass_fail (fixed point_value on approval) and
    performance_creativity (organizer ranks top-N → bonus_points_tiers).
    """
    SCORING_MODES = [
        ("pass_fail", "Pass / Fail"),
        ("performance_creativity", "Performance / Creativity"),
    ]
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="challenges")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")  # markdown brief
    point_value = models.PositiveIntegerField(default=0)
    scoring_mode = models.CharField(max_length=24, choices=SCORING_MODES, default="pass_fail")
    top_submission_count = models.PositiveIntegerField(default=0)
    bonus_points_tiers = models.JSONField(default=list, blank=True)
    visible = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class Submission(models.Model):
    """A team's submission to a challenge (REQ-6.5.11). Video demo (YouTube link
    or QR-uploaded file) + source code zip. Resubmission resets to pending."""
    STATUS = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="submissions")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="submissions")
    video_url = models.CharField(max_length=500, blank=True, default="")   # YouTube link
    video_file = models.FileField(upload_to="crashtech/videos/", blank=True, null=True)  # QR upload
    source_code = models.FileField(upload_to="crashtech/code/", blank=True, null=True)   # zip (DEC-56)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    points_awarded = models.PositiveIntegerField(default=0)
    bonus_points_awarded = models.PositiveIntegerField(default=0)
    feedback_note = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["submitted_at"]
        unique_together = [("challenge", "team")]

    def __str__(self):
        return f"{self.team.name} → {self.challenge.title} ({self.status})"

    @property
    def has_video(self):
        return bool(self.video_url or self.video_file)


class QRToken(models.Model):
    """Per-team, per-challenge token that authenticates a phone video upload
    (REQ-6.5.11) — the QR encodes a tokenized URL so the upload binds to the
    right team+challenge without the phone being logged in."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="qr_tokens")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="qr_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("team", "challenge")]

    @property
    def is_valid(self):
        return timezone.now() <= self.expires_at

    @classmethod
    def get_or_refresh(cls, team, challenge, ttl_hours=6):
        """Return a valid token for this team+challenge, refreshing if expired."""
        tok, _ = cls.objects.get_or_create(
            team=team, challenge=challenge,
            defaults={"token": secrets.token_urlsafe(24),
                      "expires_at": timezone.now() + timezone.timedelta(hours=ttl_hours)},
        )
        if not tok.is_valid:
            tok.token = secrets.token_urlsafe(24)
            tok.expires_at = timezone.now() + timezone.timedelta(hours=ttl_hours)
            tok.save(update_fields=["token", "expires_at"])
        return tok


class Certificate(models.Model):
    """A CrashTech certificate (REQ-6.5.17): participation for all teams,
    winner / runner-up for the top two by final ranking."""
    TYPES = [("participation", "Participation"), ("winner", "Winner"),
             ("runner_up", "Runner-up")]
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="certificates")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="certificates")
    type = models.CharField(max_length=14, choices=TYPES, default="participation")
    cert_id = models.UUIDField(default=_uuid.uuid4, unique=True, editable=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("hackathon", "team")]

    @property
    def type_label_he(self):
        return {"winner": "מקום ראשון", "runner_up": "מקום שני",
                "participation": "השתתפות"}.get(self.type, self.type)


class GloryPage(models.Model):
    """Permanent public memorial for a finished hackathon (REQ-6.5.18)."""
    hackathon = models.OneToOneField(Hackathon, on_delete=models.CASCADE, related_name="glory_page")
    published = models.BooleanField(default=False)
    highlights = models.TextField(blank=True, default="")  # markdown
    published_at = models.DateTimeField(null=True, blank=True)


class GloryPhoto(models.Model):
    """A curated event photo on the Glory Page (REQ-6.5.18)."""
    glory_page = models.ForeignKey(GloryPage, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="crashtech/glory/")
    caption = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
