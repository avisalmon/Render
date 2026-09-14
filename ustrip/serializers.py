"""DRF serializers — one per model, full CRUD (spec/methodology Rule 6).

`order` fields are read-only everywhere they exist: order is assigned on
create (append to the end) and changed only through a viewset's `move` /
`reorder` action, never by a client setting an arbitrary number directly.
`done_by`, `author`, `uploaded_by` and a like's `user` are read-only for
the same reason in the other direction — they are set from `request.user`
server-side, never client-supplied.

An itinerary item's `start`/`end` are computed by ustrip/schedule.py, so
they are read-only here too: the client changes `duration_minutes`,
`fixed_start`, or the order, and reads the times back.
"""

from rest_framework import serializers

from . import schedule
from .models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryComment, ItineraryDay, ItineraryItem, ItineraryLike,
    ItineraryLink, ItineraryPhoto, JournalPost, Lodging, RentalCar, Trip, TripNote,
)
from .templatetags.ustrip_extras import avatar_initials, avatar_style


class UserSummarySerializer(serializers.Serializer):
    """Just enough about a `User` for an avatar — spec §1's family members,
    reused wherever a row shows who did something."""

    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    avatar_style = serializers.SerializerMethodField()

    def get_name(self, user):
        return user.first_name or user.get_username()

    def get_initials(self, user):
        return avatar_initials(user)

    def get_avatar_style(self, user):
        return avatar_style(user)


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["id", "name", "start_date", "end_date", "route_summary", "timezone"]


class LodgingSerializer(serializers.ModelSerializer):
    nights = serializers.IntegerField(read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Lodging
        fields = ["id", "trip", "check_in", "check_out", "name", "address", "confirmed", "note", "nights", "display_name"]


class TripNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripNote
        fields = ["id", "trip", "text", "order"]
        read_only_fields = ["order"]


class ItineraryLinkSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = ItineraryLink
        fields = ["id", "item", "label", "url", "kind", "kind_display", "order"]
        read_only_fields = ["order"]


class ItineraryPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_info = UserSummarySerializer(source="uploaded_by", read_only=True)

    class Meta:
        model = ItineraryPhoto
        fields = ["id", "item", "photo", "caption", "uploaded_by", "uploaded_by_info", "created_at", "order"]
        read_only_fields = ["uploaded_by", "created_at", "order"]


class ItineraryCommentSerializer(serializers.ModelSerializer):
    author_info = UserSummarySerializer(source="author", read_only=True)

    class Meta:
        model = ItineraryComment
        fields = ["id", "item", "author", "author_info", "text", "created_at"]
        read_only_fields = ["author", "created_at"]


class ItineraryLikeSerializer(serializers.ModelSerializer):
    user_info = UserSummarySerializer(source="user", read_only=True)

    class Meta:
        model = ItineraryLike
        fields = ["id", "item", "user", "user_info", "created_at"]
        read_only_fields = ["user", "created_at"]


class ItineraryItemSerializer(serializers.ModelSerializer):
    """The computed schedule rides along on every representation. When a
    whole day is serialized the day serializer computes once and hands the
    annotated items in; a lone item computes its own day (cheap: a day is
    a dozen rows)."""

    display_title = serializers.CharField(read_only=True)
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    overrun_minutes = serializers.SerializerMethodField()
    overrun_into = serializers.SerializerMethodField()
    gap_before_minutes = serializers.SerializerMethodField()
    past_day_end = serializers.SerializerMethodField()
    tag_display = serializers.CharField(source="get_tag_display", read_only=True)
    booking_display = serializers.CharField(source="get_booking_display", read_only=True)
    links = ItineraryLinkSerializer(many=True, read_only=True)
    photos = ItineraryPhotoSerializer(many=True, read_only=True)
    like_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = ItineraryItem
        fields = [
            "id", "day", "order", "kind", "title", "display_title", "description", "time_label", "location", "cost",
            "duration_minutes", "fixed_start", "start", "end", "overrun_minutes", "overrun_into",
            "gap_before_minutes", "past_day_end", "tips", "booking", "booking_display",
            "tag", "tag_display", "links", "photos", "like_count", "liked_by_me", "comment_count",
        ]
        read_only_fields = ["order"]

    def _scheduled(self, item):
        """Annotate `item` with its computed times, computing its whole day at
        most once per request.

        The day serializer hands items in already annotated. A flat list of
        items does not, and computing each one on its own used to re-`compute()`
        the entire day per item — 84 items over 13 days meant 84 full day
        passes. The cache lives on the serializer context, which DRF shares
        between a ListSerializer and its child, so one request computes each
        day once."""
        if hasattr(item, "start"):
            return item
        cache = self.context.setdefault("_ustrip_days", {})
        if item.day_id not in cache:
            cache[item.day_id] = {i.pk: i for i in schedule.compute(item.day)}
        annotated = cache[item.day_id].get(item.pk)
        if annotated is None:
            return schedule.annotate(item)
        if annotated is not item:
            for attr in schedule.ITEM_ANNOTATIONS:
                setattr(item, attr, getattr(annotated, attr))
        return item

    def get_start(self, item):
        start = self._scheduled(item).start
        return start.strftime("%H:%M") if start else None

    def get_end(self, item):
        end = self._scheduled(item).end
        return end.strftime("%H:%M") if end else None

    def get_overrun_minutes(self, item):
        return self._scheduled(item).overrun_minutes

    def get_overrun_into(self, item):
        into = self._scheduled(item).overrun_into
        return into.display_title if into is not None else None

    def get_gap_before_minutes(self, item):
        return self._scheduled(item).gap_before_minutes

    def get_past_day_end(self, item):
        return self._scheduled(item).past_day_end

    # These three used to be a query each, per item — three more round trips
    # for every row in a list. The viewsets now annotate them onto the
    # queryset (see api.py `with_counts_for`); the per-item fallbacks are kept
    # for the paths that serialize a lone unannotated instance.
    def get_like_count(self, item):
        annotated = getattr(item, "like_count_a", None)
        return annotated if annotated is not None else item.likes.count()

    def get_comment_count(self, item):
        annotated = getattr(item, "comment_count_a", None)
        return annotated if annotated is not None else item.comments.count()

    def get_liked_by_me(self, item):
        annotated = getattr(item, "liked_by_me_a", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return item.likes.filter(user=request.user).exists()


class ItineraryDaySerializer(serializers.ModelSerializer):
    """The day's items with the computed schedule, plus the day-level
    summary the pages show: when it ends, how far past `end_time`, and how
    many planned items don't fit."""

    items = serializers.SerializerMethodField()
    schedule_ends_at = serializers.SerializerMethodField()
    schedule_over_minutes = serializers.SerializerMethodField()
    schedule_conflicts = serializers.SerializerMethodField()

    class Meta:
        model = ItineraryDay
        fields = [
            "id", "trip", "order", "label", "date_label", "date", "date_end", "title", "sleeping", "note",
            "start_time", "end_time", "schedule_ends_at", "schedule_over_minutes", "schedule_conflicts", "items",
        ]
        read_only_fields = ["order"]

    def _scheduled(self, day):
        if not hasattr(day, "_ustrip_scheduled"):
            day._ustrip_scheduled = schedule.compute(day)
        return day._ustrip_scheduled

    def get_items(self, day):
        return ItineraryItemSerializer(self._scheduled(day), many=True, context=self.context).data

    def get_schedule_ends_at(self, day):
        self._scheduled(day)
        return day.schedule_ends_at.strftime("%H:%M") if day.schedule_ends_at else None

    def get_schedule_over_minutes(self, day):
        self._scheduled(day)
        return day.schedule_over_minutes

    def get_schedule_conflicts(self, day):
        self._scheduled(day)
        return day.schedule_conflicts


class FlightSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)

    class Meta:
        model = Flight
        fields = [
            "id", "trip", "direction", "direction_display", "flight_number",
            "departure_label", "arrival_label", "order",
        ]
        read_only_fields = ["order"]


class RentalCarSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalCar
        fields = [
            "id", "trip", "pickup_date", "pickup_location", "dropoff_date",
            "dropoff_location", "vehicle_class", "note", "confirmed",
        ]


class ChecklistItemSerializer(serializers.ModelSerializer):
    done_by_info = UserSummarySerializer(source="done_by", read_only=True)

    class Meta:
        model = ChecklistItem
        fields = ["id", "group", "text", "done", "done_by", "done_by_info", "order"]
        read_only_fields = ["done_by", "order"]


class ChecklistGroupSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)
    assigned_to_info = UserSummarySerializer(source="assigned_to", read_only=True)

    class Meta:
        model = ChecklistGroup
        fields = ["id", "trip", "name", "assigned_to", "assigned_to_info", "order", "items"]
        read_only_fields = ["order"]


class JournalPostSerializer(serializers.ModelSerializer):
    author_info = UserSummarySerializer(source="author", read_only=True)

    class Meta:
        model = JournalPost
        fields = ["id", "trip", "author", "author_info", "photo", "caption", "location", "created_at"]
        read_only_fields = ["author", "created_at"]
