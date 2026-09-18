"""What the API is willing to say, and willing to be told.

The read-only list is the load-bearing part. Streaks, freezes and (later)
badges and scores are the app's to grant — spec §6. A client that can PATCH
its own streak makes the gamification meaningless and Epic L's leaderboards
fiction, so those fields are readable and never writable.
"""

from rest_framework import serializers

from ..models import SensorLabProfile


class SensorLabProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = SensorLabProfile
        fields = (
            "username",
            "language",
            "text_direction",
            "current_streak",
            "longest_streak",
            "last_activity_date",
            "freezes_available",
            "freezes_used",
        )
        #: Everything except `language`: the switch is the only thing a
        #: person may set about themselves through this endpoint.
        read_only_fields = (
            "username",
            "text_direction",
            "current_streak",
            "longest_streak",
            "last_activity_date",
            "freezes_available",
            "freezes_used",
        )
