"""bkm: the wall of Avi's BKMs.

docs/bkm/spec.md and docs/bkm/data_model.md. The only thing shared with the
rest of the site is the User table, reached through Reader (Rule 2).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


def picture_path(instance, filename):
    return f"bkm/{instance.slug}-{timezone.now():%Y%m%d%H%M%S}.jpg"


class Bkm(models.Model):
    """One BKM, one card on the wall. Only Avi adds and changes them, through
    the chat (REQ-B.20); nobody else can."""

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=160)
    repo_url = models.URLField(max_length=300)
    page_url = models.URLField(max_length=300)
    picture = models.ImageField(upload_to=picture_path, blank=True)
    position = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=True)
    added_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "added_at", "id"]

    def __str__(self):
        return self.name

    @property
    def clone_url(self):
        url = self.repo_url.rstrip("/")
        return url if url.endswith(".git") else url + ".git"

    @property
    def folder(self):
        """The folder `git clone` makes: the repo's last path part."""
        return self.repo_url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]


class Reader(models.Model):
    """The app's own record of a signed-in person, made the first time they do
    something here. Nothing is added to babook's User."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bkm_reader")
    display_name = models.CharField(max_length=80)
    joined_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.display_name


class Like(models.Model):
    """Public: everybody sees the count (REQ-B.13)."""

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="likes")
    bkm = models.ForeignKey(Bkm, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("reader", "bkm")]


class Star(models.Model):
    """Private: only its own reader ever reads it (REQ-B.14). A table apart
    from Like, so a filter mistake on one cannot leak the other."""

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="stars")
    bkm = models.ForeignKey(Bkm, on_delete=models.CASCADE, related_name="stars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("reader", "bkm")]


def project_image_path(instance, filename):
    return f"bkm/projects/{timezone.now():%Y%m}/{timezone.now():%d%H%M%S%f}.jpg"


YOUTUBE_ID = r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})"


def youtube_id(url):
    import re

    m = re.search(YOUTUBE_ID, url or "")
    return m.group(1) if m else ""


class Project(models.Model):
    """Something a person made, pinned to the public exhibition (REQ-B.30).
    A YouTube video, a site, or a photo. Anybody signed in adds their own;
    everybody sees the cards, and only signed-in people open them."""

    VIDEO, SITE, IMAGE = "video", "site", "image"
    KINDS = [(VIDEO, "YouTube video"), (SITE, "Website"), (IMAGE, "Photo")]

    TOPICS = [
        ("electronics", "Electronics"), ("robotics", "Robotics"), ("fpga", "FPGA and chips"),
        ("iot", "IoT and sensors"), ("web", "Web and full stack"), ("ai", "AI"),
        ("games", "Games"), ("science", "Science"), ("art", "Art and design"), ("other", "Other"),
    ]
    PURPOSES = [
        ("learning", "I built it to learn"), ("teaching", "For teaching others"),
        ("tool", "A tool people use"), ("fun", "Just for fun"),
    ]
    LEVELS = [("first", "My first project"), ("some", "Some experience"), ("advanced", "Advanced")]

    owner = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=400, blank=True)
    kind = models.CharField(max_length=8, choices=KINDS)
    url = models.URLField(max_length=500, blank=True)
    youtube_id = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to=project_image_path, blank=True)
    bkm = models.ForeignKey(Bkm, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    topic = models.CharField(max_length=16, choices=TOPICS, default="other", db_index=True)
    purpose = models.CharField(max_length=10, choices=PURPOSES, blank=True)
    level = models.CharField(max_length=10, choices=LEVELS, blank=True)
    tags = models.CharField(max_length=120, blank=True, help_text="A few words, separated by commas")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.youtube_id = youtube_id(self.url) if self.kind == self.VIDEO else ""
        super().save(*args, **kwargs)

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()][:6]

    @property
    def picture_url(self):
        """What the card shows: an uploaded photo, else the video's
        thumbnail, else a screenshot of the site taken by WordPress's free
        mShots service (loaded by the browser, nothing stored here)."""
        if self.image:
            return self.image.url
        if self.youtube_id:
            return f"https://i.ytimg.com/vi/{self.youtube_id}/hqdefault.jpg"
        if self.kind == self.SITE and self.url:
            from urllib.parse import quote

            return f"https://s0.wp.com/mshots/v1/{quote(self.url, safe='')}?w=960&h=600"
        return ""


class ProjectLike(models.Model):
    """Public, like a BKM's likes (REQ-B.33)."""

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="project_likes")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("reader", "project")]


class ProjectComment(models.Model):
    """One thread per project, the same shape as a BKM's (REQ-B.34)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="project_comments")
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]


class Comment(models.Model):
    """One thread per BKM; a reply quotes the comment it answers (REQ-B.15).
    Deleting is soft, so a quote never points at nothing."""

    bkm = models.ForeignKey(Bkm, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="comments")
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.author} on {self.bkm}"
