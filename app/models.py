from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# ---------------------------------------------------------------------------
# User profile & notes
# ---------------------------------------------------------------------------

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
    github_username = models.CharField(max_length=100, blank=True, default="")
    # Authoring Studio: may create/edit courses. Staff are implicitly authors.
    is_author = models.BooleanField(default=False)

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


# ---------------------------------------------------------------------------
# Courses & video (SPR-1.4 / SPR-2.2)
# ---------------------------------------------------------------------------

class Course(models.Model):
    CATEGORY_CHOICES = [
        ("foundations", "Foundations"),
        ("copilot", "Copilot"),
        ("agents", "Agents"),
        ("mcp", "MCP"),
        ("prompting", "Prompting"),
    ]
    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]
    DOMAIN_CHOICES = [
        ("matazim", "מטצים"),
        ("ai", "בינה מלאכותית"),
        ("innovation", "הובלת חדשנות"),
    ]

    title = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="foundations")
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="beginner")
    # Training taxonomy (Domain → Track). Keys are defined in app/taxonomy.py.
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default="matazim")
    track = models.CharField(max_length=40, blank=True, default="")
    thumbnail = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Video(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="videos")
    bunny_video_id = models.CharField(max_length=100, blank=True)  # empty = text-only lesson
    title = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    lesson_order = models.PositiveIntegerField(default=1)
    is_free_preview = models.BooleanField(default=False)
    is_final_lesson = models.BooleanField(default=False)
    notes_markdown = models.TextField(blank=True)
    summary_he = models.TextField(blank=True)
    # If set, the lesson ends with an AI "reflection" question (free-text) instead of a quiz.
    reflection_prompt = models.TextField(blank=True, default="")
    has_code_example = models.BooleanField(default=False)
    github_file = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lesson_order"]
        unique_together = [("course", "lesson_order")]

    def __str__(self):
        return f"{self.course.slug} – {self.lesson_order}. {self.title}"


class UserVideoProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="video_progress")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="user_progress")
    last_position_seconds = models.PositiveIntegerField(default=0)
    percent_watched = models.FloatField(default=0.0)
    quiz_passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "video")]

    def __str__(self):
        return f"{self.user.username} – {self.video}"


class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = [("user", "course")]

    def __str__(self):
        return f"{self.user.username} → {self.course.slug}"


import uuid as _uuid  # noqa: E402


class LessonQuiz(models.Model):
    """Optional quiz shown at the end of a lesson before continuing."""

    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="quiz")
    question = models.TextField()
    options_json = models.JSONField(
        default=list,
        help_text='[{"text": "...", "is_correct": true/false}, ...]',
    )
    requires_correct = models.BooleanField(
        default=False,
        help_text="True → only correct answer unlocks Next. False → any answer unlocks Next.",
    )

    class Meta:
        verbose_name = "שאלת סיכום"
        verbose_name_plural = "שאלות סיכום"

    def __str__(self):
        return f"Quiz: {self.video}"


class LessonReflection(models.Model):
    """A learner's free-text reflection on a lesson + the AI's encouraging reply.

    Used by experiential lessons (e.g. the Level-1 'try it yourself' AI journey)
    where, instead of a quiz, we ask the learner what they tried and respond.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reflections")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="reflections")
    prompt = models.TextField(blank=True, default="")
    user_text = models.TextField()
    ai_reply = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "רפלקציה"
        verbose_name_plural = "רפלקציות"

    def __str__(self):
        return f"Reflection: {self.user.username} – {self.video}"


class CourseCertificate(models.Model):
    """Issued when a user completes a course via the Finish button."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    certificate_id = models.UUIDField(default=_uuid.uuid4, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "course")]
        verbose_name = "תעודת סיום"
        verbose_name_plural = "תעודות סיום"

    def __str__(self):
        return f"Cert {self.certificate_id}: {self.user.username} – {self.course.slug}"


class CourseMaterial(models.Model):
    """Downloadable files or links attached to a course (shown on detail + lesson pages)."""

    LINK = "link"
    FILE = "file"
    TYPE_CHOICES = [(LINK, "קישור"), (FILE, "קובץ")]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=200)
    material_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=LINK)
    url = models.URLField(blank=True, help_text="URL for link-type materials")
    file = models.FileField(
        upload_to="course_materials/", blank=True, null=True,
        help_text="File for file-type materials"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower = first)")

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "חומר לימוד"
        verbose_name_plural = "חומרי לימוד"

    def __str__(self):
        return f"{self.course.slug} — {self.title}"


# ---------------------------------------------------------------------------
# Billing / entitlements (SPR-1.5)
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

    @property
    def has_video_access(self):
        return self.tier in ("base", "master")

    @property
    def has_copilot_access(self):
        return self.tier == "master"

    def __str__(self):
        return f"{self.user.username} ({self.tier})"


# ---------------------------------------------------------------------------
# Copilot seat provisioning (SPR-1.6)
# ---------------------------------------------------------------------------

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
    invited_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    assigned_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    last_activity_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.status})"


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
        return f"{self.seat.user.username} – {self.event_type}"


# ---------------------------------------------------------------------------
# AI Chat (SPR-1.8)
# ---------------------------------------------------------------------------

CONTEXT_TYPE_CHOICES = [
    ("course_tutor", "Course Tutor"),
    ("code_helper", "Code Helper"),
    ("general_assistant", "General Assistant"),
]


class SystemPrompt(models.Model):
    context_type = models.CharField(max_length=30, choices=CONTEXT_TYPE_CHOICES, unique=True)
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.context_type


class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, blank=True, null=True)
    context_type = models.CharField(
        max_length=30, choices=CONTEXT_TYPE_CHOICES, default="general_assistant"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]

    def __str__(self):
        return f"{self.user.username} – {self.context_type} – {self.created_at:%Y-%m-%d}"


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
        return f"{self.session_id} [{self.role}]"


class UsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usage_logs")
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="usage_logs")
    model = models.CharField(max_length=50)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – {self.model} – ${self.cost_usd:.4f}"


class ModerationLog(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="moderation_logs", blank=True, null=True
    )
    content = models.TextField()
    flagged_categories = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_id} – {self.created_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# Corporate lead capture (SPR-2.1.1)
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
        return f"{self.name} @ {self.company}"


# ---------------------------------------------------------------------------
# Newsletter (SPR-2.1.3)
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
    confirmed_at = models.DateTimeField(blank=True, null=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class AuthoringJob(models.Model):
    """Tracks an automated 'video -> draft course' build for the Authoring Studio."""

    SOURCE_CHOICES = [("youtube", "YouTube URL"), ("upload", "Uploaded file")]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("error", "Error"),
    ]

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="authoring_jobs"
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="authoring_jobs"
    )
    title = models.CharField(max_length=200)
    domain = models.CharField(max_length=20, default="matazim")
    track = models.CharField(max_length=40, blank=True, default="")
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="youtube")
    source_url = models.CharField(max_length=500, blank=True, default="")
    source_file = models.FileField(upload_to="authoring_uploads/", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    progress = models.PositiveSmallIntegerField(default=0)  # 0-100
    step = models.CharField(max_length=200, blank=True, default="")
    log = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Authoring job"

    def __str__(self):
        return f"Job #{self.pk} {self.title} ({self.status})"

    def append_log(self, message):
        self.log = (self.log or "") + message + "\n"

    def mark(self, *, status=None, progress=None, step=None, log=None, save=True):
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = progress
        if step is not None:
            self.step = step
        if log:
            self.append_log(log)
        if save:
            self.save()
