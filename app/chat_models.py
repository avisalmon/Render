"""Chat & Groups (EPIC-6.6) - channels + messages.

Polling-based real-time-feel (DEC-60), reusing the community spine. Re-exported
from app/models.py so Django registers them under the `app` label.
"""
from django.contrib.auth.models import User
from django.db import models


class Channel(models.Model):
    """A chat room. Kinds: topic (per taxonomy domain + general), course (cohort
    room), hackathon (live event buzz). Read-public; posting requires login."""
    KINDS = [("topic", "Topic"), ("course", "Course"), ("hackathon", "Hackathon")]
    kind = models.CharField(max_length=12, choices=KINDS, default="topic")
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=160)
    icon = models.CharField(max_length=40, blank=True, default="bi-chat-dots")
    domain = models.CharField(max_length=40, blank=True, default="")  # taxonomy key (topic)
    course = models.ForeignKey("Course", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="channels")
    hackathon = models.ForeignKey("Hackathon", on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="channels")
    is_readonly = models.BooleanField(default=False)  # e.g. a closed hackathon's room
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "title"]

    def __str__(self):
        return self.title


class ChannelMessage(models.Model):
    """A single chat message (REQ-6.6.1)."""
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channel_messages")
    body = models.TextField()
    is_hidden = models.BooleanField(default=False)  # moderation (REQ-6.6.6)
    promoted_to = models.CharField(max_length=10, blank=True, default="")  # forum/tip (REQ-6.12.4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author.username}: {self.body[:30]}"


class ChannelRead(models.Model):
    """Per-user read marker for unread indicators (REQ-6.6.6)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channel_reads")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="reads")
    last_seen_id = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("user", "channel")]
