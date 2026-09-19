"""What the API is willing to say, and willing to be told.

The read-only list is the load-bearing part. Streaks, freezes and (later)
badges and scores are the app's to grant — spec §6. A client that can PATCH
its own streak makes the gamification meaningless and Epic L's leaderboards
fiction, so those fields are readable and never writable.

**Two shapes for the curriculum, on purpose (SL-B2).** The eight CRUD
resources below serve `_en` and `_he` side by side, because an author edits
both columns. The assembled lab read in `curriculum.py` does the opposite
— one resolved string per field — because a client that reproduced the
fallback rule would be the second implementation of it, and the two would
disagree the first time a translation was missing. Neither shape is the
"real" one; they have different readers.
"""

from rest_framework import serializers

from ..models import (
    AnalysisConfig,
    ContentBlock,
    ExperimentConfig,
    Lab,
    PredictionChoice,
    PredictionQuestion,
    SensorLabProfile,
    SensorRequirement,
    Track,
)


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


# ===========================================================================
# The curriculum, for authors (SL-B2)
#
# Rule 6: full CRUD as infrastructure. Writes are gated to staff by
# `permissions.ReadAnyWriteStaff`, not by anything here — a serializer is the
# wrong place to keep an authorisation rule, because the next viewset will
# use a different serializer.
# ===========================================================================


class LabSummarySerializer(serializers.ModelSerializer):
    """A lab as it appears inside a track list — enough for a row, no steps."""

    class Meta:
        model = Lab
        fields = ("slug", "title_en", "title_he", "summary_en", "summary_he",
                  "mode", "order", "estimated_minutes", "is_published",
                  "prerequisite_lab")


class TrackSerializer(serializers.ModelSerializer):
    lab_count = serializers.SerializerMethodField()
    labs = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = ("slug", "title_en", "title_he", "description_en", "description_he",
                  "icon", "order", "is_published", "lab_count", "labs")

    def _visible(self, track):
        """The nested queryset gets the same filter as the outer one.

        This is the leak a nested serializer introduces quietly: the view
        filters `Track` for a student and the labs come back through the
        relation unfiltered, so a draft lab is invisible in `labs/` and
        listed inside its track. There is a test for it.
        """
        labs = track.labs.all()
        request = self.context.get("request")
        staff = bool(request and request.user.is_staff)
        return labs if staff else labs.filter(is_published=True)

    def get_lab_count(self, track):
        return self._visible(track).count()

    def get_labs(self, track):
        return LabSummarySerializer(self._visible(track), many=True).data


class LabSerializer(serializers.ModelSerializer):
    #: A track by its slug, not its primary key. An author writing a lab
    #: knows "free-fall"; nobody knows track 7.
    track = serializers.SlugRelatedField(slug_field="slug", queryset=Track.objects.all())

    class Meta:
        model = Lab
        fields = ("slug", "track", "title_en", "title_he", "summary_en", "summary_he",
                  "mode", "order", "estimated_minutes", "is_published", "prerequisite_lab")


class ContentBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentBlock
        fields = ("id", "lab", "step", "kind", "order", "body_en", "body_he", "media")


class PredictionQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionQuestion
        fields = ("id", "lab", "kind", "order", "prompt_en", "prompt_he",
                  "correct_value", "tolerance")


class PredictionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionChoice
        fields = ("id", "question", "text_en", "text_he", "is_correct", "order")


class ExperimentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentConfig
        fields = ("id", "lab", "instructions_en", "instructions_he",
                  "requested_hz", "max_duration_ms",
                  "trigger_kind", "trigger_threshold",
                  "uses_signal_generator", "tone_frequency_hz", "strobe_rate_hz")


class SensorRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorRequirement
        fields = ("id", "config", "sensor", "is_required", "axis_filter")


class AnalysisConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisConfig
        fields = ("id", "lab", "computation", "expected_source", "expected_value",
                  "expected_formula", "unit", "pass_tolerance",
                  "explanation_en", "explanation_he")
