"""DRF serializers — one per model, full CRUD (spec/methodology Rule 6).

`order` fields are read-only everywhere they exist: order is assigned on
create (append to the end) and changed only through a viewset's `move`
action, never by a client setting an arbitrary number directly. `done_by`
and `author` are read-only for the same reason in the other direction —
they are set from `request.user` server-side, never client-supplied.
"""

from rest_framework import serializers

from .models import ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, RentalCar, Trip
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


class ItineraryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItineraryItem
        fields = ["id", "day", "order", "time_label", "description", "tag"]
        read_only_fields = ["order"]


class ItineraryDaySerializer(serializers.ModelSerializer):
    items = ItineraryItemSerializer(many=True, read_only=True)

    class Meta:
        model = ItineraryDay
        fields = ["id", "trip", "order", "label", "date_label", "title", "sleeping", "note", "items"]
        read_only_fields = ["order"]


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
