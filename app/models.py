from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("member", "Member"),
        ("staff", "Staff"),
        ("admin", "Admin"),
        ("guest", "Guest"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    github_username = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="notes/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Course(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Video(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="videos")
    bunny_video_id = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    duration_seconds = models.PositiveIntegerField(default=0)
    lesson_order = models.PositiveIntegerField(default=1)
    is_free_preview = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lesson_order"]
        unique_together = [("course", "lesson_order")]

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class UserVideoProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="video_progress")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="user_progress")
    last_position_seconds = models.PositiveIntegerField(default=0)
    percent_watched = models.FloatField(default=0.0)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "video")]

    def __str__(self):
        return f"{self.user.username} — {self.video.title} ({self.percent_watched:.0f}%)"


class CopilotSeat(models.Model):
    STATUS_CHOICES = [
        ("none", "None"),
        ("invite_pending", "Invite Pending"),
        ("active", "Active"),
        ("expiring", "Expiring"),
        ("revoked", "Revoked"),
        ("waitlisted", "Waitlisted"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="copilot_seat")
    github_username = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="none")
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.github_username} ({self.status})"


class SeatEvent(models.Model):
    EVENT_CHOICES = [
        ("invited", "Invited"),
        ("accepted", "Accepted"),
        ("assigned", "Assigned"),
        ("revoked", "Revoked"),
        ("reclaimed", "Reclaimed"),
        ("warned", "Warned"),
        ("waitlisted", "Waitlisted"),
    ]
    seat = models.ForeignKey(CopilotSeat, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    actor = models.CharField(max_length=100, default="system")
    reason = models.CharField(max_length=200, blank=True)
    api_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seat.github_username} — {self.event_type} ({self.created_at})"


# ---------------------------------------------------------------------------
# AI Chat (OpenAI) — SPR-1.8
# ---------------------------------------------------------------------------


class SystemPrompt(models.Model):
    CONTEXT_CHOICES = [
        ("course_tutor", "Course Tutor"),
        ("code_helper", "Code Helper"),
        ("general_assistant", "General Assistant"),
    ]
    context_type = models.CharField(max_length=30, choices=CONTEXT_CHOICES, unique=True)
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.context_type


class ChatSession(models.Model):
    CONTEXT_CHOICES = [
        ("course_tutor", "Course Tutor"),
        ("code_helper", "Code Helper"),
        ("general_assistant", "General Assistant"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    context_type = models.CharField(max_length=30, choices=CONTEXT_CHOICES, default="general_assistant")
    course = models.ForeignKey("Course", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]

    def __str__(self):
        return f"{self.user.username} — {self.context_type} ({self.created_at:%Y-%m-%d})"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    tokens_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class UsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usage_logs")
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="usage_logs")
    model = models.CharField(max_length=50)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.model} ({self.prompt_tokens}+{self.completion_tokens} tokens)"


class ModerationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="moderation_logs")
    content = models.TextField()
    flagged_categories = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_str = self.user.username if self.user else "anonymous"
        return f"Flagged: {user_str} ({self.created_at})"


# ---------------------------------------------------------------------------
# Billing — SPR-1.5 (mock mode: no real payment, users choose tier freely)
# ---------------------------------------------------------------------------


class Entitlement(models.Model):
    TIER_CHOICES = [
        ("free", "Free"),
        ("base", "Base"),
        ("master", "Master"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="entitlement")
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default="free")
    activated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.tier}"

    @property
    def has_video_access(self):
        """Base and Master tiers have full video library access."""
        return self.tier in ("base", "master")

    @property
    def has_copilot_access(self):
        """Only Master tier includes Copilot seat."""
        return self.tier == "master"


# ---------------------------------------------------------------------------
# Corporate Page — SPR-2.1.1 conversion MVP
# ---------------------------------------------------------------------------


class CorporateLead(models.Model):
    TEAM_SIZE_CHOICES = [
        ("1-5", "1-5"),
        ("6-15", "6-15"),
        ("16-50", "16-50"),
        ("50+", "50+"),
    ]
    TRAINING_TYPE_CHOICES = [
        ("workshop", "Workshop"),
        ("bootcamp", "Bootcamp"),
        ("keynote", "Keynote"),
        ("not_sure", "Not sure"),
    ]
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("meeting_scheduled", "Meeting Scheduled"),
        ("proposal_sent", "Proposal Sent"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    name = models.CharField(max_length=100)
    company = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    team_size = models.CharField(max_length=10, choices=TEAM_SIZE_CHOICES)
    training_type = models.CharField(max_length=20, choices=TRAINING_TYPE_CHOICES)
    message = models.TextField(blank=True)
    source_page = models.CharField(max_length=100, default="/corporate/")
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    referrer_url = models.URLField(max_length=500, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="new")
    status_changed_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company} — {self.name} ({self.training_type})"


# ---------------------------------------------------------------------------
# Newsletter Capture — SPR-2.1.3 MVP
# ---------------------------------------------------------------------------


class NewsletterSubscriber(models.Model):
    LANGUAGE_CHOICES = [
        ("he", "Hebrew"),
        ("en", "English"),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="he")
    source_page = models.CharField(max_length=200, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
