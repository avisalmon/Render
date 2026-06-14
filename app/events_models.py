"""Events & Meetups (EPIC-6.7). Re-exported from app/models.py."""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class EventSeries(models.Model):
    """A recurring series, e.g. «שעת מומחה חודשית עם אבי» (REQ-6.7.4)."""
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "series"
            slug, i = base, 2
            while EventSeries.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CommunityEvent(models.Model):
    """A community event (REQ-6.7.1): online or venue, capacity + waitlist."""
    TYPES = [
        ("live_coding", "Live coding"), ("ama", "AMA"),
        ("hackathon_kickoff", "Hackathon kickoff"), ("meetup", "Meetup"),
        ("conference", "כנס"),
    ]
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default="")  # markdown
    event_type = models.CharField(max_length=20, choices=TYPES, default="ama")
    is_online = models.BooleanField(default=True)
    online_url = models.CharField(max_length=500, blank=True, default="")
    venue = models.CharField(max_length=200, blank=True, default="")  # physical (REQ-6.7.5)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=0)  # 0 = unlimited
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="hosted_events")
    series = models.ForeignKey(EventSeries, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="events")
    hackathon = models.ForeignKey("Hackathon", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="events")
    course = models.ForeignKey("Course", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="events")
    recording_bunny_id = models.CharField(max_length=120, blank=True, default="")
    reminded_24h = models.BooleanField(default=False)  # REQ-6.7.2 reminder bookkeeping
    reminded_1h = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "event"
            slug, i = base, 2
            while CommunityEvent.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def is_past(self):
        return self.end_at < timezone.now()

    @property
    def going_count(self):
        return self.rsvps.filter(status="going").count()

    @property
    def is_full(self):
        return bool(self.capacity) and self.going_count >= self.capacity

    @property
    def location_label(self):
        return self.venue if (self.venue and not self.is_online) else "אונליין"


class EventRSVP(models.Model):
    """An RSVP (REQ-6.7.2). status going / waitlist."""
    STATUS = [("going", "Going"), ("waitlist", "Waitlist")]
    event = models.ForeignKey(CommunityEvent, on_delete=models.CASCADE, related_name="rsvps")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_rsvps")
    status = models.CharField(max_length=10, choices=STATUS, default="going")
    attended = models.BooleanField(default=False)  # check-in (REQ-6.7.5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("event", "user")]
        ordering = ["created_at"]


class EventPhoto(models.Model):
    """A photo from a (physical) event, surfaced to the feed (REQ-6.7.5)."""
    event = models.ForeignKey(CommunityEvent, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="events/")
    caption = models.CharField(max_length=200, blank=True, default="")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
