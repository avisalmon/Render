"""ustrip's data (docs/ustrip/spec.md §4).

One trip (spec §0 — this isn't a multi-trip planner), a day-by-day itinerary,
per-person or shared packing/task checklists, and a photo journal feed.
Nothing here is shared with `app/` — see spec §2.2.
"""

from django.conf import settings
from django.db import models


class Trip(models.Model):
    """Spec §0: one specific trip, not a general trip-management feature."""

    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    route_summary = models.CharField(
        max_length=300, blank=True, help_text='e.g. "NYC → Finger Lakes → Niagara Falls → ... → home"'
    )

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return self.name


class Flight(models.Model):
    """Spec §0 — harvested into trip-data/usa-2026.json's `flights` block but
    never modeled until now (sat there as inert JSON, not a real object)."""

    OUTBOUND = "outbound"
    RETURN = "return"
    DIRECTION_CHOICES = [(OUTBOUND, "Outbound"), (RETURN, "Return")]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="flights")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    flight_number = models.CharField(max_length=20, blank=True)
    departure_label = models.CharField(max_length=120, blank=True, help_text='Free text, e.g. "EWR 15:25 2026-10-01"')
    arrival_label = models.CharField(max_length=120, blank=True, help_text='Free text, e.g. "Newark (EWR) ~15:50"')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.get_direction_display()} {self.flight_number}".strip()


class RentalCar(models.Model):
    """Spec §0 — same story as `Flight`. `confirmed` matters on its own: as
    harvested this was a researched proposal, not a booking (spec sprint
    note 2026-09-13) — Avi flips it once it's actually reserved. Reseeding
    never resets it (see seed_ustrip.py)."""

    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="rental_car")
    pickup_date = models.DateField(null=True, blank=True)
    pickup_location = models.CharField(max_length=200, blank=True)
    dropoff_date = models.DateField(null=True, blank=True)
    dropoff_location = models.CharField(max_length=200, blank=True)
    vehicle_class = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    confirmed = models.BooleanField(default=False, help_text="Actually booked, not just researched.")

    def __str__(self):
        return f"Rental car — {self.trip}"


class ItineraryDay(models.Model):
    """Spec §4.1. `label` carries the sortable slot (e.g. "12-13" spans two
    calendar days in the source plan) — `order` is what actually sorts it,
    since a label like "12-13" doesn't sort correctly as text against "9"."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="days")
    order = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=10, help_text='e.g. "5" or "12-13"')
    date_label = models.CharField(max_length=60, help_text='e.g. "Tue Sep 22, 2026"')
    title = models.CharField(max_length=200)
    sleeping = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="unique_day_order_per_trip")
        ]

    def __str__(self):
        return f"Day {self.label} — {self.title}"


class ItineraryItem(models.Model):
    """Spec §4.1 — one line in a day's timeline."""

    PLAN = "plan"
    OPTIONAL = "optional"
    TAG_CHOICES = [(PLAN, "Plan"), (OPTIONAL, "Optional")]

    day = models.ForeignKey(ItineraryDay, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField()
    time_label = models.CharField(max_length=30, blank=True, help_text='e.g. "15:50", "Evening", or blank')
    description = models.TextField()
    tag = models.CharField(max_length=10, choices=TAG_CHOICES, default=PLAN)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.day} — {self.description[:40]}"


class ChecklistGroup(models.Model):
    """Spec §4.2 — 'Packing — Dad', 'Before we leave', etc."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="checklists")
    name = models.CharField(max_length=120)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Optional — leave blank for a shared list.",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class ChecklistItem(models.Model):
    group = models.ForeignKey(ChecklistGroup, on_delete=models.CASCADE, related_name="items")
    text = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class JournalPost(models.Model):
    """Spec §4.3 — reverse-chronological shared photo diary. No likes,
    no comments, just what a family member posted and when."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="journal_posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to="ustrip/journal/", blank=True, null=True)
    caption = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} — {self.caption[:40]}"
