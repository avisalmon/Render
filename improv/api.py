"""improv's REST API. Rule 6: every model has an endpoint, documented in docs/improv/api.md.

Reference rows are read-only here and edited in the admin. The tables are a few
dozen rows, so they come back whole rather than paged.

Content a player can own (styles, progressions) is shown as the presets plus the
player's own rows. Presets are read-only; an own row is fully editable; another
player's row does not exist as far as this player can tell.
"""

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import generics, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS

from .models import ChordQuality, ChordScale, Completion, Exercise, Lesson, Phrase, PracticeSession, Progression, Scale, Style, Tag, Take
from . import bests, practice, progress, retention, weakness, workout
from .access import profile_for
from .permissions import IsPlayer
from .serializers import (
    ChordQualitySerializer,
    ChordScaleSerializer,
    CompletionSerializer,
    ExerciseSerializer,
    LessonSerializer,
    PhraseSerializer,
    PlayerSerializer,
    visible_exercises,
    visible_lessons,
    PracticeSessionSerializer,
    TakeSerializer,
    ProgressionSerializer,
    ScaleSerializer,
    StyleSerializer,
    TagSerializer,
)
from .slugs import unique_slug
from .teaching import track_rank


class ReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlayer]
    pagination_class = None


class ChordQualityViewSet(ReferenceViewSet):
    queryset = ChordQuality.objects.prefetch_related("chord_scales__scale")
    serializer_class = ChordQualitySerializer


class ScaleViewSet(ReferenceViewSet):
    queryset = Scale.objects.select_related("parent_scale")
    serializer_class = ScaleSerializer


class ChordScaleViewSet(ReferenceViewSet):
    queryset = ChordScale.objects.select_related("chord_quality", "scale")
    serializer_class = ChordScaleSerializer

    def get_queryset(self):
        rows = super().get_queryset()
        quality = self.request.query_params.get("quality")
        scale = self.request.query_params.get("scale")
        if quality:
            rows = rows.filter(chord_quality__symbol=quality)
        if scale:
            rows = rows.filter(scale__slug=scale)
        return rows


class TagViewSet(ReferenceViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_queryset(self):
        mine = Q(progressions__is_preset=True) | Q(progressions__owner=self.request.user)
        return Tag.objects.annotate(progression_count=Count("progressions", filter=mine, distinct=True))


class ProgressContextMixin:
    """Adds what this player has done to the serializer context, so a lesson or an exercise can
    say whether it is open, locked or done for them. Read from the completions on every request,
    never stored."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        player = profile_for(self.request.user)
        done = progress.done_exercise_ids(player)
        context["done_exercises"] = done
        context["lesson_states"] = progress.lesson_states(player, done)
        return context


class LessonViewSet(ProgressContextMixin, ReferenceViewSet):
    """The lessons, in the order a player meets them. A draft is hidden from everyone but the
    superuser who reads it before it is published."""

    queryset = Lesson.objects.select_related("progression", "prerequisite").prefetch_related("exercises")
    serializer_class = LessonSerializer

    def get_queryset(self):
        rows = visible_lessons(self.request.user).select_related("progression", "prerequisite").prefetch_related("exercises")
        if self.request.query_params.get("track"):
            rows = rows.filter(track=self.request.query_params["track"])
        return rows.annotate(track_rank=track_rank()).order_by("track_rank", "order")


class ExerciseViewSet(ProgressContextMixin, ReferenceViewSet):
    queryset = Exercise.objects.select_related("lesson", "progression")
    serializer_class = ExerciseSerializer

    def get_queryset(self):
        rows = visible_exercises(self.request.user)
        params = self.request.query_params
        if params.get("lesson"):
            rows = rows.filter(lesson__slug=params["lesson"])
        if params.get("challenge"):
            rows = rows.filter(lesson__isnull=True)
        if params.get("daily"):
            rows = rows.filter(daily_eligible=True)
        return rows


class OwnedViewSet(viewsets.ModelViewSet):
    """Presets plus my own rows. A subclass names the model's queryset, the field the
    slug is made from, and the filters its screens need."""

    permission_classes = [IsPlayer]
    pagination_class = None
    slug_source = "name"
    has_genre = True

    def get_queryset(self):
        user = self.request.user
        rows = super().get_queryset().filter(Q(is_preset=True) | Q(owner=user))
        params = self.request.query_params
        if params.get("mine"):
            rows = rows.filter(owner=user)
        if self.has_genre and params.get("genre"):
            rows = rows.filter(genre=params["genre"])
        return self.filter_more(rows, params).distinct()

    def filter_more(self, rows, params):
        return rows

    def get_object(self):
        row = super().get_object()
        if self.request.method not in SAFE_METHODS and (row.is_preset or row.owner_id != self.request.user.pk):
            raise PermissionDenied("Presets are read-only here. They are edited in the admin.")
        return row

    def perform_create(self, serializer):
        slug = unique_slug(self.queryset.model, serializer.validated_data.get(self.slug_source, ""))
        serializer.save(owner=self.request.user, is_preset=False, slug=slug)


class StyleViewSet(OwnedViewSet):
    queryset = Style.objects.all()
    serializer_class = StyleSerializer
    slug_source = "name"

    def filter_more(self, rows, params):
        return rows.filter(feel=params["feel"]) if params.get("feel") else rows


class ProgressionViewSet(OwnedViewSet):
    queryset = Progression.objects.prefetch_related("tags")
    serializer_class = ProgressionSerializer
    slug_source = "title"

    def filter_more(self, rows, params):
        if params.get("tag"):
            rows = rows.filter(tags__slug=params["tag"])
        if params.get("difficulty"):
            try:
                rows = rows.filter(difficulty=int(params["difficulty"]))
            except ValueError:
                rows = rows.none()
        if params.get("q"):
            rows = rows.filter(Q(title__icontains=params["q"]) | Q(description__icontains=params["q"]))
        return rows


class PhraseViewSet(OwnedViewSet):
    queryset = Phrase.objects.all()
    serializer_class = PhraseSerializer
    slug_source = "name"
    has_genre = False

    def filter_more(self, rows, params):
        return rows.filter(kind=params["kind"]) if params.get("kind") else rows


class PlayerView(generics.RetrieveUpdateAPIView):
    """The person's own profile: one row, reached without an id.

    A singleton on purpose, and the documented shape in docs/improv/api.md. There is
    exactly one profile per person, made on their first visit, so there is nothing to
    create and nothing to list; an id in the route would only invite asking for
    somebody else's row, which this app will not answer. Delete is absent too: it
    would throw away the calibration that makes timing mean anything.
    """

    serializer_class = PlayerSerializer
    permission_classes = [IsPlayer]

    def get_object(self):
        return profile_for(self.request.user)


class MineViewSet(viewsets.ModelViewSet):
    """Rows that are the player's own and nobody else's: sessions and takes. Another
    player's row does not exist as far as this player can tell, and a new row is theirs."""

    permission_classes = [IsPlayer]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(player__user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(player=profile_for(self.request.user))


class PracticeSessionViewSet(MineViewSet):
    queryset = PracticeSession.objects.all()
    serializer_class = PracticeSessionSerializer


class TakeViewSet(MineViewSet):
    queryset = Take.objects.select_related("progression", "style", "exercise", "completion")
    serializer_class = TakeSerializer

    def perform_create(self, serializer):
        # The take and what it earns are one fact or neither: a take that passed an exercise and a
        # completion that was never written would be XP lost for good.
        with transaction.atomic():
            player = profile_for(self.request.user)
            take = serializer.save(player=player)
            progress.award(take)
            retention.prune(player)

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        if params.get("kept"):
            rows = rows.filter(is_kept=True)
        if params.get("exercise"):
            rows = rows.filter(exercise__slug=params["exercise"])
        if params.get("progression"):
            rows = rows.filter(progression__slug=params["progression"])
        return rows

    def perform_update(self, serializer):
        # A take is a record of what happened. After it is posted, only whether it is kept may change.
        allowed = {"is_kept"}
        extra = set(serializer.validated_data) - allowed
        if extra:
            raise PermissionDenied(f"A take cannot be changed after it is posted, only kept or not: {sorted(extra)}")
        if serializer.validated_data.get("is_kept") and retention.is_cleared(serializer.instance):
            raise ValidationError(
                f"The notes of this take were cleared after {retention.RETENTION_DAYS} days, so it cannot be kept."
            )
        serializer.save()


class CompletionViewSet(viewsets.ReadOnlyModelViewSet):
    """The exercises this player has passed. Read-only for everyone: the server makes a
    completion as the consequence of a take, because one a client could write would be an XP
    counter the client could set."""

    permission_classes = [IsPlayer]
    pagination_class = None
    queryset = Completion.objects.select_related("exercise__lesson")
    serializer_class = CompletionSerializer

    def get_queryset(self):
        rows = super().get_queryset().filter(player__user=self.request.user)
        params = self.request.query_params
        if params.get("exercise"):
            rows = rows.filter(exercise__slug=params["exercise"])
        if params.get("lesson"):
            rows = rows.filter(exercise__lesson__slug=params["lesson"])
        return rows


class SummaryView(APIView):
    """XP, level and how far through the lessons the player is: a read over their completions,
    in one place so every screen says the same thing."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(progress.summary(profile_for(request.user)))


class ContinueView(APIView):
    """The lesson to go back to: a read over the completions, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(progress.continue_lesson(profile_for(request.user)))


class PracticeView(APIView):
    """Today against the daily goal, the streak and the practice log: a read over the player's
    sittings in their own timezone, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", practice.LOG_DAYS))
        except ValueError:
            days = practice.LOG_DAYS
        if not 1 <= days <= practice.MOST_LOG_DAYS:
            days = practice.LOG_DAYS
        return Response(practice.report(profile_for(request.user), days=days))


class WorkoutView(APIView):
    """Today's workout: up to three exercises that stay the same all day for this player, a read
    over their completions and takes, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(workout.report(profile_for(request.user)))


class WeaknessView(APIView):
    """Where to work: what the last thirty days of takes say, with the twenty-note floor. A read
    over takes, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(weakness.report(profile_for(request.user)))


class BestsView(APIView):
    """The best take of each challenge and each exercise played: a read over takes, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(bests.report(profile_for(request.user)))


REFERENCE_ENDPOINTS = {
    "chord-qualities": ChordQualityViewSet,
    "scales": ScaleViewSet,
    "chord-scales": ChordScaleViewSet,
    "tags": TagViewSet,
    "lessons": LessonViewSet,
    "exercises": ExerciseViewSet,
}
OWNED_ENDPOINTS = {
    "styles": StyleViewSet,
    "progressions": ProgressionViewSet,
    "phrases": PhraseViewSet,
}
MINE_ENDPOINTS = {
    "sessions": PracticeSessionViewSet,
    "takes": TakeViewSet,
    "completions": CompletionViewSet,
}
# Not a router endpoint: see PlayerView.
SINGLETONS = {"player": PlayerView}
# Derived reads: no model of their own, the same rule (IsPlayer, 404 for everyone else).
DERIVED = {
    "summary": SummaryView,
    "continue": ContinueView,
    "practice": PracticeView,
    "workout": WorkoutView,
    "weakness": WeaknessView,
    "bests": BestsView,
}
ENDPOINTS = {**REFERENCE_ENDPOINTS, **OWNED_ENDPOINTS, **MINE_ENDPOINTS}
