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
    # Community (EPIC-6.1): public member identity. Private by default.
    is_public = models.BooleanField(default=False)
    bio = models.CharField(max_length=300, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    open_to_collab = models.BooleanField(default=False)
    guidelines_accepted_at = models.DateTimeField(blank=True, null=True)
    leaderboard_opt_out = models.BooleanField(default=False)
    # Email verification (REQ-7.2.1): password signups must verify; Google trusted.
    email_verified = models.BooleanField(default=False)
    # Weekly community digest opt-in (REQ-6.4.4) — dormant until ~50 active members.
    digest_opt_in = models.BooleanField(default=False)
    # DM control (REQ-6.6.3 / DEC-61): default ON for adults, always off for students.
    dms_enabled = models.BooleanField(default=True)

    @property
    def public_name(self):
        return self.display_name or self.user.first_name or self.user.username

    def __str__(self):
        return f"{self.user.username} ({self.role})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class LearnerProfile(models.Model):
    """Onboarding + personalization profile (EPIC-5, REQ-5.6.1).

    Created at signup (with first-touch attribution) and filled by the AI
    interview or the static fallback. Pre-EPIC-5 users have none, so they are
    never routed into onboarding and keep the generic homepage.
    """
    LEVELS = [("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")]
    ROLE_TYPES = [
        ("student", "Student"), ("teacher", "Teacher"), ("professor", "Professor"),
        ("industry_engineer", "Industry engineer"), ("other", "Other"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="learner_profile")
    # Welcome basics (captured before the interview): who they are + contact
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")  # optional extra email
    interests = models.JSONField(default=list, blank=True)  # taxonomy domain keys
    goal = models.CharField(max_length=200, blank=True, default="")
    experience_level = models.CharField(max_length=20, choices=LEVELS, blank=True, default="")
    persona = models.CharField(max_length=200, blank=True, default="")
    time_per_week = models.CharField(max_length=50, blank=True, default="")
    recommended_track = models.CharField(max_length=50, blank=True, default="")
    recommended_course = models.ForeignKey(
        "Course", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    onboarding_skipped_at = models.DateTimeField(null=True, blank=True)
    # First-touch attribution carried over from the anonymous session (REQ-5.4.4)
    source_entry_path = models.CharField(max_length=500, blank=True, default="")
    source_entry_type = models.CharField(max_length=20, blank=True, default="")
    source_course = models.CharField(max_length=200, blank=True, default="")  # slug
    source_referrer = models.CharField(max_length=500, blank=True, default="")
    source_utm = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def needs_onboarding(self):
        return self.onboarding_completed_at is None and self.onboarding_skipped_at is None

    def __str__(self):
        return f"LearnerProfile({self.user.username})"


# ---------------------------------------------------------------------------
# Community foundation (EPIC-6.1) — reputation, badges, follow, notifications,
# moderation. Badge/point definitions live in app/community.py.
# ---------------------------------------------------------------------------

class CommunityReputation(models.Model):
    """Denormalized total points per member (REQ-6.1.3)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reputation")
    points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}: {self.points}"


class ReputationEvent(models.Model):
    """Point ledger — lets the leaderboard compute monthly windows (REQ-6.1.3)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reputation_events")
    points = models.IntegerField()
    reason = models.CharField(max_length=50)
    ref = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class BadgeAward(models.Model):
    """A badge earned by a member; definitions in community.BADGES (REQ-6.1.4)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    slug = models.CharField(max_length=50)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "slug")]

    @property
    def meta(self):
        from .community import BADGES
        return BADGES.get(self.slug, {"title": self.slug, "icon": "bi-award", "description": ""})


class Follow(models.Model):
    """Member follows member (REQ-6.1.5)."""
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("follower", "followed")]


class Notification(models.Model):
    """In-app notification (REQ-6.1.6). Created via community.notify()."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="+")
    verb = models.CharField(max_length=30)  # answer / accepted / badge / follow / ...
    text = models.CharField(max_length=300)
    url = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]


class ContentReport(models.Model):
    """Member report on any community object → staff queue (REQ-6.1.8)."""
    STATUS = [("open", "Open"), ("actioned", "Actioned"), ("dismissed", "Dismissed")]
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_filed")
    content_type = models.CharField(max_length=30)  # thread / post / project / ...
    object_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=STATUS, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    handled_at = models.DateTimeField(blank=True, null=True)
    action_note = models.CharField(max_length=300, blank=True, default="")


# ---------------------------------------------------------------------------
# Forums & Q&A (EPIC-6.2). Categories are code-defined (community.forum_categories).
# ---------------------------------------------------------------------------

class ForumThread(models.Model):
    KINDS = [("question", "שאלה"), ("discussion", "דיון")]
    category = models.CharField(max_length=30)  # slug from community.forum_categories()
    kind = models.CharField(max_length=12, choices=KINDS, default="question")
    title = models.CharField(max_length=200)
    body = models.TextField()  # markdown
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_threads")
    tags = models.JSONField(default=list, blank=True)
    course = models.ForeignKey("Course", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="forum_threads")
    video = models.ForeignKey("Video", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="forum_threads")
    is_pinned = models.BooleanField(default=False)
    is_canonical = models.BooleanField(default=False)  # staff-marked (REQ-6.2.6)
    is_hidden = models.BooleanField(default=False)  # moderation
    ai_summary = models.TextField(blank=True, default="")  # REQ-6.2.7b
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-updated_at"]

    @property
    def accepted_post(self):
        return self.posts.filter(is_accepted=True).first()

    def __str__(self):
        return self.title


class ForumPost(models.Model):
    """An answer/reply in a thread (REQ-6.2.2)."""
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_posts")
    body = models.TextField()  # markdown
    is_accepted = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_accepted", "created_at"]

    @property
    def upvotes(self):
        return self.votes.count()


class PostVote(models.Model):
    """Upvote-only (DEC-38)."""
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("post", "user")]


class ThreadSubscription(models.Model):
    """Follow a thread (or a whole category when thread is null) (REQ-6.2.8)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="thread_subs")
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, null=True, blank=True,
                               related_name="subscriptions")
    category = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        unique_together = [("user", "thread", "category")]


# ---------------------------------------------------------------------------
# Showcase — דוכן השוויץ (EPIC-6.3). Stand definitions live in app/community.py.
# ---------------------------------------------------------------------------

class ShowcaseProject(models.Model):
    """A member's published project (REQ-6.3.1). Star count drives wall ranking."""
    STATUS = [("draft", "טיוטה"), ("pending", "בבדיקה"), ("published", "פורסם")]
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="showcase_projects")
    stand = models.CharField(max_length=30, default="other")  # slug from community.SHOWCASE_STANDS
    title = models.CharField(max_length=200)
    tagline = models.CharField(max_length=200, blank=True, default="")
    story = models.TextField(blank=True, default="")  # markdown
    cover = models.ImageField(upload_to="showcase/", blank=True, null=True)
    video_url = models.CharField(max_length=500, blank=True, default="")  # YouTube/Bunny
    repo_url = models.CharField(max_length=500, blank=True, default="")
    live_url = models.CharField(max_length=500, blank=True, default="")
    course = models.ForeignKey("Course", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="showcase_projects")
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="draft")
    is_featured = models.BooleanField(default=False)
    star_count = models.PositiveIntegerField(default=0)  # denormalized for ranking
    is_hidden = models.BooleanField(default=False)  # moderation
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    @property
    def stand_meta(self):
        from .community import SHOWCASE_STANDS
        return SHOWCASE_STANDS.get(self.stand, {"title": self.stand, "icon": "bi-stars"})

    # Domains that are themselves a viewable live site (so a repo_url pointing
    # at GitHub Pages / Vercel / etc. is treated as the site, REQ-6.3.16).
    _LIVE_HOSTS = ("github.io", ".vercel.app", ".netlify.app", ".pages.dev",
                   ".web.app", ".streamlit.app", ".onrender.com", ".fly.dev")

    @property
    def site_url(self):
        """Best 'visit the live site' URL: the live-demo field, else a repo_url
        that is itself a hosted site (github.io, vercel, netlify, ...)."""
        if self.live_url:
            return self.live_url
        if self.repo_url and any(h in self.repo_url for h in self._LIVE_HOSTS):
            return self.repo_url
        return ""

    @property
    def site_host(self):
        from urllib.parse import urlparse
        return urlparse(self.site_url).netloc if self.site_url else ""

    @property
    def favicon_url(self):
        """The site's own icon (REQ-6.3.16) — always resolves."""
        return f"https://www.google.com/s2/favicons?domain={self.site_host}&sz=128" if self.site_host else ""

    @property
    def screenshot_url(self):
        """A live screenshot of the site for an auto-cover (REQ-6.3.16). thum.io
        renders synchronously + is loaded directly by the browser (fast, free,
        no token cost); mShots was dropped after it started returning 403."""
        return (f"https://image.thum.io/get/width/640/crop/400/noanimate/{self.site_url}"
                if self.site_url else "")

    @property
    def is_live(self):
        return self.status == "published" and not self.is_hidden

    def __str__(self):
        return self.title


class ProjectImage(models.Model):
    """Gallery image for a showcase project (REQ-6.3.1)."""
    project = models.ForeignKey(ShowcaseProject, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="showcase/gallery/")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class ProjectReaction(models.Model):
    """Star (primary) + emoji reactions, one per member per kind (REQ-6.3.3)."""
    KINDS = [("star", "⭐"), ("fire", "🔥"), ("love", "❤️"), ("clap", "👏"), ("wow", "🤯")]
    project = models.ForeignKey(ShowcaseProject, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_reactions")
    kind = models.CharField(max_length=10, default="star")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "user", "kind")]


class ProjectComment(models.Model):
    """A comment on a showcase project (REQ-6.3.10)."""
    project = models.ForeignKey(ShowcaseProject, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_comments")
    body = models.TextField()  # markdown
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class DirectMessage(models.Model):
    """Member-to-member DM (REQ-6.3.12). Student role blocked both ways (DEC-41)."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["created_at"]


class MessageBlock(models.Model):
    """One member blocks another from messaging them (REQ-6.3.12)."""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="message_blocks")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("blocker", "blocked")]


class Tip(models.Model):
    """Short-form community tip (REQ-6.4.2) — 10x easier to share than a project.
    Markdown body (≤2000 chars), optional tags + link; reactions award the
    author points and feed the activity stream."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tips")
    body = models.TextField()  # markdown, capped at 2000 chars in the view
    tags = models.JSONField(default=list, blank=True)  # tool/domain tags
    link_url = models.CharField(max_length=500, blank=True, default="")
    is_hidden = models.BooleanField(default=False)  # moderation
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def reaction_count(self):
        return self.reactions.count()

    def __str__(self):
        return f"Tip({self.author.username}: {self.body[:30]})"


class TipReaction(models.Model):
    """A reaction on a tip (REQ-6.4.2). One per member per kind; mirrors
    ProjectReaction. No 'star' here — tips use lightweight emoji only."""
    KINDS = [("love", "❤️"), ("fire", "🔥"), ("clap", "👏"), ("bulb", "💡")]
    tip = models.ForeignKey(Tip, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tip_reactions")
    kind = models.CharField(max_length=10, default="love")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("tip", "user", "kind")]


class CookieConsent(models.Model):
    """Server-side record that a visitor accepted the cookie notice (REQ-7.1.8)."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="cookie_consents")
    session_key = models.CharField(max_length=40, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]


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
    # Set whenever the course is changed in the Authoring Studio (i.e. directly on
    # the running instance). Lets the local<->prod sync warn before overwriting.
    studio_edited_at = models.DateTimeField(blank=True, null=True)

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


class EmailSendLog(models.Model):
    """One row per outbound email send, written by the anymail post_send signal
    (app/apps.py). Lets the Resend cost adapter count real monthly usage against
    the 3,000/mo free tier (Resend exposes no usage API). Lightweight: just a
    timestamp + recipient count."""

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recipients = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.recipients} recipient(s) @ {self.sent_at:%Y-%m-%d %H:%M}"


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


# ---------------------------------------------------------------------------
# CrashTech — hardware hackathon platform (EPIC-6.5). Defined in a dedicated
# module, re-exported here so Django registers them under the `app` label.
# ---------------------------------------------------------------------------
from .chat_models import (  # noqa: E402,F401
    Channel,
    ChannelMessage,
    ChannelRead,
)
from .crashtech_models import (  # noqa: E402,F401
    Certificate,
    Challenge,
    GloryPage,
    GloryPhoto,
    Hackathon,
    HackRole,
    QRToken,
    Submission,
    Team,
)
from .dashboard_models import (  # noqa: E402,F401
    AlertEvent,
    AlertRule,
    CostRecord,
    DashboardSnapshot,
)
from .events_models import (  # noqa: E402,F401
    CommunityEvent,
    EventPhoto,
    EventRSVP,
    EventSeries,
)
