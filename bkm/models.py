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
