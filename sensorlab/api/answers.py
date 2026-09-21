"""`/sensorlab/api/prediction-answers/` — what a person predicted (SL-E4).

Rule 6 says a model ships its API as part of the epic that introduces it.
SL-E1 added `PredictionAnswer` and no API, so this is a debt being paid.

**There is no `grade` verb, and its absence is the design.** The backlog
asked for one. SL-E1 then decided grading happens at submission and
`is_correct` is stored, never recomputed — because a question edited later
would otherwise silently rewrite what a student got right, and spec §6
counts these rows as a learning signal. Those two cannot both hold: a
`grade/` action either re-grades (breaking the rule) or does nothing (a verb
that lies about doing something). So recording and grading are one action,
and *revealing* is a separate question answered by `should_reveal`.

**`is_correct` is on the row from the moment an answer is saved**, which
makes it the easiest thing in this sprint to serialise by accident — and
sending it before Analysis hands a student the answer at exactly the moment
spec §3 needs them not to have it. So the field is removed from the
representation unless the attempt has reached Analysis.

Revealing *your result* is not revealing the key. Which option was correct,
and the numeric target, stay server-side even then — otherwise one finished
attempt hands over every future one.
"""

from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import LabAttempt, PredictionAnswer, PredictionQuestion
from .pagination import SensorLabPagination


class PredictionAnswerSerializer(serializers.ModelSerializer):
    #: Both relations are validated against the caller rather than trusted:
    #: `attempt` has to come from the body (one person may have several), so
    #: the queryset is narrowed per request in `get_fields` below.
    attempt = serializers.PrimaryKeyRelatedField(queryset=LabAttempt.objects.none())
    question = serializers.PrimaryKeyRelatedField(queryset=PredictionQuestion.objects.all())

    class Meta:
        model = PredictionAnswer
        fields = (
            "id", "attempt", "question", "selected_choice",
            "numeric_value", "text_value", "curve_points", "is_correct", "answered_at",
        )
        read_only_fields = ("id", "is_correct", "answered_at")

        #: DRF builds a UniqueTogetherValidator from the model's
        #: `(attempt, question)` constraint, which would reject the second
        #: POST for a question with 400 — turning "change your mind before
        #: the lock", the thing SL-E1 deliberately allows, into an error.
        #: Uniqueness is still enforced twice: `record()` upserts, and the
        #: database constraint stands behind it. What is dropped here is only
        #: DRF's *pre-emptive* check, which is wrong for an upsert endpoint.
        validators = []

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            fields["attempt"].queryset = LabAttempt.objects.filter(user=request.user)
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # See this module's header. The field exists on the row long before
        # a student may see it.
        if not instance.should_reveal:
            data.pop("is_correct", None)
        return data


class PredictionAnswerViewSet(viewsets.ModelViewSet):
    """Your own predictions. No verbs — see the header for why."""

    serializer_class = PredictionAnswerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = SensorLabPagination
    queryset = PredictionAnswer.objects.select_related(
        "attempt", "question", "selected_choice"
    ).all()

    def get_queryset(self):
        # Scoped through the attempt, which is what owns an answer — the
        # scoping that makes 404 the honest answer for somebody else's row.
        return self.queryset.filter(attempt__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            answer = PredictionAnswer.objects.record(
                attempt=data["attempt"],
                question=data["question"],
                selected_choice=data.get("selected_choice"),
                numeric_value=data.get("numeric_value"),
                text_value=data.get("text_value", ""),
                curve_points=data.get("curve_points"),
            )
        except PredictionAnswer.Locked as locked:
            # The lock is the model's, and it has to hold against a client
            # with no screen — otherwise it was never a rule, only a layout.
            return Response({"detail": str(locked)}, status=status.HTTP_409_CONFLICT)
        except ValueError as mismatch:
            return Response({"question": [str(mismatch)]},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(answer).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Editing an answer is `record()` again, so the lock applies."""
        answer = self.get_object()
        if answer.attempt.predictions_locked:
            return Response(
                {"detail": "These predictions are locked — the experiment has started."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)
