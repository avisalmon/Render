"""`/sensorlab/api/recordings/` — captures, over REST (SL-F1).

Shipped **with** the model this time rather than as a debt. SL-E1 added
`PredictionAnswer` without an API and SL-E4 paid for it; the lesson is
cheaper applied than repeated.

Two things here are not boilerplate.

**A list is a list of headers.** Ten captures at a few thousand samples each
is megabytes for a screen that shows three lines per row, so `samples` is
absent from the list representation and present on the detail. The payload
is one fetch away when something actually needs it.

**The cap answers 413, not 500.** §9.0 item 1's decision is inline POST with
a hard limit, and a limit is only useful if the caller can read the refusal.
A stack trace tells a phone nothing it can act on.
"""

from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import LabAttempt, SensorRecording
from .pagination import SensorLabPagination


class SensorRecordingSerializer(serializers.ModelSerializer):
    attempt = serializers.PrimaryKeyRelatedField(queryset=LabAttempt.objects.none())

    class Meta:
        model = SensorRecording
        fields = (
            "id", "attempt", "sensor", "requested_hz", "achieved_hz",
            "duration_ms", "sample_count", "samples", "label", "recorded_at",
        )
        #: `achieved_hz` and `sample_count` are measured from the payload,
        #: never accepted from the caller — a record that repeats a claim is
        #: not evidence (spec §4.1).
        read_only_fields = ("id", "achieved_hz", "sample_count", "recorded_at")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            fields["attempt"].queryset = LabAttempt.objects.filter(user=request.user)
        return fields


class SensorRecordingListSerializer(SensorRecordingSerializer):
    """The same recording without its payload. See the module header."""

    class Meta(SensorRecordingSerializer.Meta):
        fields = tuple(f for f in SensorRecordingSerializer.Meta.fields if f != "samples")


class SensorRecordingViewSet(viewsets.ModelViewSet):
    serializer_class = SensorRecordingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = SensorLabPagination
    queryset = SensorRecording.objects.select_related("attempt").all()

    def get_queryset(self):
        return self.queryset.filter(attempt__user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return SensorRecordingListSerializer
        return SensorRecordingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            recording = SensorRecording.objects.record(
                attempt=data["attempt"],
                sensor=data["sensor"],
                requested_hz=data["requested_hz"],
                samples=request.data.get("samples") or [],
                duration_ms=data.get("duration_ms", 0),
                label=data.get("label", ""),
            )
        except SensorRecording.TooLarge as too_big:
            return Response({"detail": str(too_big)},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        except ValueError as wrong_sensor:
            return Response({"sensor": [str(wrong_sensor)]},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(SensorRecordingSerializer(recording).data,
                        status=status.HTTP_201_CREATED)
