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
    ItineraryLink, ItineraryPhoto, JournalPost, RentalCar, Trip,
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
        fields = ["id", "name", "start_date", "end_date", "route_summary"]


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
            "id", "day", "order", "title", "display_title", "description", "time_label", "location", "cost",
            "duration_minutes", "fixed_start", "start", "end", "tips", "booking", "booking_display",
            "tag", "tag_display", "links", "photos", "like_count", "liked_by_me", "comment_count",
        ]
        read_only_fields = ["order"]

    def _times(self, item):
        if not hasattr(item, "start"):
            item.start, item.end = schedule.for_item(item)
        return item.start, item.end

    def get_start(self, item):
        start, _ = self._times(item)
        return start.strftime("%H:%M") if start else None

    def get_end(self, item):
        _, end = self._times(item)
        return end.strftime("%H:%M") if end else None

    def get_like_count(self, item):
        return item.likes.count()

    def get_liked_by_me(self, item):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return item.likes.filter(user=request.user).exists()

    def get_comment_count(self, item):
        return item.comments.count()


class ItineraryDaySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = ItineraryDay
        fields = ["id", "trip", "order", "label", "date_label", "title", "sleeping", "note", "start_time", "items"]
        read_only_fields = ["order"]

    def get_items(self, day):
        scheduled = schedule.compute(day)
        return ItineraryItemSerializer(scheduled, many=True, context=self.context).data


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
