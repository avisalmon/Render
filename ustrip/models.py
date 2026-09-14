"""ustrip's data (docs/ustrip/spec.md §4, docs/ustrip/data_model.md).

One trip (spec §0 — this isn't a multi-trip planner), a day-by-day itinerary
whose items carry a computed flow schedule, per-person or shared
packing/task checklists, and a photo journal feed. Nothing here is shared
with `app/` — see spec §2.2.
"""

from datetime import time

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
    since a label like "12-13" doesn't sort correctly as text against "9".

    `start_time` is where the day's flow schedule starts counting from
    (ustrip/schedule.py): items run back to back from here unless one of
    them is pinned to a fixed time, which resets the clock."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="days")
    order = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=10, help_text='e.g. "5" or "12-13"')
    date_label = models.CharField(max_length=60, help_text='e.g. "Tue Sep 22, 2026"')
    title = models.CharField(max_length=200)
    sleeping = models.CharField(max_length=200, blank=True)
    note = models.TextField(
        blank=True, help_text="An open decision or a heads-up for the whole day, not tied to one timeline item."
    )
    start_time = models.TimeField(default=time(9, 0), help_text="Where the day's schedule starts counting from.")

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="unique_day_order_per_trip")
        ]

    def __str__(self):
        return f"Day {self.label} — {self.title}"


class ItineraryItem(models.Model):
    """Spec §4.1 — one line in a day's timeline, and (since the rich detail
    page) the thing everything else about a stop hangs off: links, photos,
    likes, comments.

    Time is not stored on the item. `fixed_start` pins an anchor (a flight,
    a timed ticket); `duration_minutes` is how long it takes; the actual
    start/end are computed by ustrip/schedule.py from the day's `start_time`
    and the items' `order`. Drag an item somewhere else and every time after
    it moves with it — that is the whole point of computing rather than
    storing. `time_label` survives as an optional free-text note ("Boats
    every 15 min, 9:00–17:00") shown next to the computed time."""

    PLAN = "plan"
    OPTIONAL = "optional"
    REJECTED = "rejected"
    TAG_CHOICES = [(PLAN, "Plan"), (OPTIONAL, "Optional"), (REJECTED, "Rejected")]

    BOOKING_NOT_NEEDED = "not_needed"
    BOOKING_TO_BOOK = "to_book"
    BOOKING_BOOKED = "booked"
    BOOKING_CHOICES = [
        (BOOKING_NOT_NEEDED, "No booking needed"),
        (BOOKING_TO_BOOK, "Needs booking"),
        (BOOKING_BOOKED, "Booked"),
    ]

    day = models.ForeignKey(ItineraryDay, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200, blank=True, default="", help_text="Short headline, e.g. 'Top of the Rock'.")
    description = models.TextField()
    time_label = models.CharField(max_length=60, blank=True, default="", help_text="Optional note shown next to the time.")
    location = models.CharField(max_length=200, blank=True, default="")
    cost = models.CharField(max_length=160, blank=True, default="", help_text="Free text, e.g. '~$42/person'.")
    duration_minutes = models.PositiveIntegerField(default=60)
    fixed_start = models.TimeField(
        null=True, blank=True, help_text="Pin to a fixed time (a flight, a timed ticket). Everything after flows from it."
    )
    tips = models.TextField(blank=True, default="")
    booking = models.CharField(max_length=12, choices=BOOKING_CHOICES, default=BOOKING_NOT_NEEDED)
    tag = models.CharField(max_length=10, choices=TAG_CHOICES, default=PLAN)
    enriched_at = models.DateTimeField(
        null=True, blank=True, editable=False,
        help_text="Set once by enrich_ustrip_items. Explicit state, so a redeploy can never mistake an item a "
                  "family member has since edited for one still in its seeded shape.",
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.day} — {self.display_title}"

    @property
    def display_title(self):
        """Older rows have no title yet — fall back to the first clause of the
        description so a list never shows a blank line."""
        if self.title:
            return self.title
        first = self.description.split(". ")[0].split(" — ")[0]
        return first[:80]


class ItineraryLink(models.Model):
    """A place to read more about a stop: the official site, Wikipedia, a map
    pin. The source plan deliberately linked information, never checkout
    pages — `tickets` exists as a kind for when the family adds one."""

    OFFICIAL = "official"
    WIKIPEDIA = "wikipedia"
    MAP = "map"
    TICKETS = "tickets"
    OTHER = "other"
    KIND_CHOICES = [
        (OFFICIAL, "Official site"), (WIKIPEDIA, "Wikipedia"), (MAP, "Map"),
        (TICKETS, "Tickets"), (OTHER, "Other"),
    ]

    item = models.ForeignKey(ItineraryItem, on_delete=models.CASCADE, related_name="links")
    label = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=OFFICIAL)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class ItineraryPhoto(models.Model):
    """Photos that belong to a stop (the poster for the place, or what it
    looked like when we got there). Separate from the journal on purpose:
    the journal is a diary in time order; these are attached to an item."""

    item = models.ForeignKey(ItineraryItem, on_delete=models.CASCADE, related_name="photos")
    photo = models.ImageField(upload_to="ustrip/items/")
    caption = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo for {self.item.display_title}"


class ItineraryLike(models.Model):
    """One per person per item — a toggle, not a counter."""

    item = models.ForeignKey(ItineraryItem, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item", "user"], name="one_like_per_user_per_item")]

    def __str__(self):
        return f"{self.user} likes {self.item.display_title}"


class ItineraryComment(models.Model):
    """Conversation about a stop. Unlike everything else in the itinerary
    (no creator lock), a comment is one person's words: only its author
    (or a superuser) can edit or delete it."""

    item = models.ForeignKey(ItineraryItem, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


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
