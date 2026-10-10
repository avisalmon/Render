"""improv's REST API. Rule 6: every model has an endpoint, documented in docs/improv/api.md.

Reference rows are read-only here and edited in the admin. The tables are a few
dozen rows, so they come back whole rather than paged.

Content a player can own (styles, progressions) is shown as the presets plus the
player's own rows. Presets are read-only; an own row is fully editable; another
player's row does not exist as far as this player can tell.
"""

import datetime as dt

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import SAFE_METHODS

from .models import ChordQuality, ChordScale, Completion, DrillAttempt, Exercise, Feedback, Lesson, Phrase, Piece, PiecePhrase, PieceTake, PracticeSession, Progression, ReadingTake, Scale, ScaleFingering, ScaleRun, Style, Tag, Take
from . import bests, practice, progress, reading, repertoire, retention, trainer, weakness, workout
from .access import profile_for
from .feedback_mail import send_feedback_mail
from .permissions import IsPlayer
from .serializers import (
    ChordQualitySerializer,
    ChordScaleSerializer,
    CompletionSerializer,
    DrillAttemptSerializer,
    ExerciseSerializer,
    FeedbackSerializer,
    LessonSerializer,
    PhraseSerializer,
    PieceSerializer,
    PiecePhraseSerializer,
    PieceTakeSerializer,
    PlayerSerializer,
    visible_exercises,
    visible_lessons,
    visible_pieces,
    PracticeSessionSerializer,
    ReadingTakeSerializer,
    TakeSerializer,
    ProgressionSerializer,
    ScaleFingeringSerializer,
    ScaleRunSerializer,
    ScaleSerializer,
    StyleSerializer,
    TagSerializer,
)
from .slugs import unique_slug
from .teaching import track_rank


MAX_OWN_ROWS = 1000
MAX_LOG_ROWS = 20000


def check_room(user, count, ceiling):
    """Anyone but the owner may keep only so many rows of one kind; the owner has no limit."""
    if user.is_superuser:
        return
    if count >= ceiling:
        raise ValidationError(
            f"You have reached the limit of {ceiling} saved items of this kind. Delete some you no longer need, then try again."
        )


class ReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlayer]
    pagination_class = None


class ChordQualityViewSet(ReferenceViewSet):
    queryset = ChordQuality.objects.prefetch_related("chord_scales__scale")
    serializer_class = ChordQualitySerializer


class ScaleViewSet(ReferenceViewSet):
    queryset = Scale.objects.select_related("parent_scale")
    serializer_class = ScaleSerializer


class ScaleFingeringViewSet(ReferenceViewSet):
    queryset = ScaleFingering.objects.select_related("scale")
    serializer_class = ScaleFingeringSerializer

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        if params.get("root_pc"):
            rows = rows.filter(root_pc=params["root_pc"]) if params["root_pc"].isdigit() else rows.none()
        if params.get("hand"):
            rows = rows.filter(hand=params["hand"])
        return rows


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
        return rows.annotate(track_rank=track_rank()).order_by(F("path_order").asc(nulls_last=True), "level", "track_rank", "order")


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


class PieceViewSet(ReferenceViewSet):
    """The repertoire, easiest first. A draft is hidden from everyone but the superuser who reads it."""

    queryset = Piece.objects.all()
    serializer_class = PieceSerializer

    def get_queryset(self):
        rows = visible_pieces(self.request.user)
        if self.request.query_params.get("level", "").isdigit():
            rows = rows.filter(level=self.request.query_params["level"])
        return rows


class PiecePhraseViewSet(ReferenceViewSet):
    queryset = PiecePhrase.objects.select_related("piece")
    serializer_class = PiecePhraseSerializer

    def get_queryset(self):
        rows = super().get_queryset()
        if not self.request.user.is_superuser:
            rows = rows.filter(piece__status=Piece.Status.PUBLISHED)
        if self.request.query_params.get("piece"):
            rows = rows.filter(piece__slug=self.request.query_params["piece"])
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
        model = self.queryset.model
        check_room(self.request.user, model.objects.filter(owner=self.request.user, is_preset=False).count(), MAX_OWN_ROWS)
        slug = unique_slug(model, serializer.validated_data.get(self.slug_source, ""))
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
    is_log = False

    def get_queryset(self):
        return super().get_queryset().filter(player__user=self.request.user)

    def check_room(self):
        count = self.queryset.model.objects.filter(player__user=self.request.user).count()
        check_room(self.request.user, count, MAX_LOG_ROWS if self.is_log else MAX_OWN_ROWS)

    def perform_create(self, serializer):
        self.check_room()
        serializer.save(player=profile_for(self.request.user))


class FeedbackViewSet(MineViewSet):
    """What the signed-in person told the owner. Theirs to list, fix and withdraw; a flood from one
    person is stopped, because anyone who signs up may write here."""

    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    PER_HOUR = 20

    def perform_create(self, serializer):
        player = profile_for(self.request.user)
        since = timezone.now() - dt.timedelta(hours=1)
        if player.feedback.filter(created_at__gte=since).count() >= self.PER_HOUR:
            raise Throttled(detail="That is a lot of feedback in one hour. Thank you; try again a little later.")
        self.check_room()
        note = serializer.save(player=player)
        send_feedback_mail(note, self.request.user)


class PracticeSessionViewSet(MineViewSet):
    queryset = PracticeSession.objects.all()
    serializer_class = PracticeSessionSerializer
    is_log = True


class TakeViewSet(MineViewSet):
    queryset = Take.objects.select_related("progression", "style", "exercise", "completion")
    serializer_class = TakeSerializer

    def perform_create(self, serializer):
        # The take and what it earns are one fact or neither: a take that passed an exercise and a
        # completion that was never written would be XP lost for good.
        with transaction.atomic():
            player = profile_for(self.request.user)
            retention.prune(player)
            self.check_room()
            take = serializer.save(player=player)
            progress.award(take)
            if take.exercise_id and take.exercise.lesson_id:
                progress.move_to(player, take.exercise.lesson)
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


class ScaleRunViewSet(MineViewSet):
    queryset = ScaleRun.objects.select_related("scale")
    serializer_class = ScaleRunSerializer
    is_log = True

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        for name in ("root_pc", "octaves"):
            if params.get(name):
                rows = rows.filter(**{name: params[name]}) if params[name].isdigit() else rows.none()
        return rows


class DrillAttemptViewSet(MineViewSet):
    queryset = DrillAttempt.objects.all()
    serializer_class = DrillAttemptSerializer
    is_log = True

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        if params.get("key_pc"):
            rows = rows.filter(key_pc=params["key_pc"]) if params["key_pc"].isdigit() else rows.none()
        if params.get("kind"):
            rows = rows.filter(kind=params["kind"])
        return rows


class ReadingTakeViewSet(MineViewSet):
    """One read-through in the reading trainer. The page judges and posts the result; the pass line is the
    server's, and a Step take never passes."""

    queryset = ReadingTake.objects.all()
    serializer_class = ReadingTakeSerializer
    is_log = True

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        if params.get("key"):
            rows = rows.filter(key=params["key"])
        if params.get("hands"):
            rows = rows.filter(hands=params["hands"])
        if params.get("mode"):
            rows = rows.filter(mode=params["mode"])
        return rows


class PieceTakeViewSet(MineViewSet):
    """One go at a rung of a piece, or a drill of any bars of it. The page judges and posts the result; the
    pass line and the tempo are the server's (improv/ladder.py)."""

    queryset = PieceTake.objects.select_related("piece")
    serializer_class = PieceTakeSerializer
    is_log = True

    def get_queryset(self):
        rows = super().get_queryset()
        params = self.request.query_params
        if params.get("piece"):
            rows = rows.filter(piece__slug=params["piece"])
        if params.get("rung"):
            rows = rows.filter(rung=params["rung"])
        if params.get("mode"):
            rows = rows.filter(mode=params["mode"])
        return rows


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


class StartHereView(APIView):
    """Where the player chooses to be in the path (spec ch. 6). POST {"lesson": slug} points Today and
    Continue at that lesson and opens everything before it; the answer is the continue read."""

    permission_classes = [IsPlayer]

    def post(self, request):
        slug = str(request.data.get("lesson") or "")[:60]
        lesson = visible_lessons(request.user).filter(slug=slug).first()
        if lesson is None:
            raise NotFound("There is no lesson by that name.")
        player = profile_for(request.user)
        progress.move_to(player, lesson)
        return Response(progress.continue_lesson(player))


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


class ReadingView(APIView):
    """Where the player is in the reading ladder and what they misread: a read over reading takes, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(reading.report(profile_for(request.user)))


class RepertoireView(APIView):
    """Every piece with its ladder, what the player has passed and where to go next: a read over piece takes, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(repertoire.report(profile_for(request.user), request.user))


class TrainerView(APIView):
    """What to work on in the scales and chords trainer: a read over runs and attempts, stored nowhere."""

    permission_classes = [IsPlayer]

    def get(self, request):
        return Response(trainer.report(profile_for(request.user)))


REFERENCE_ENDPOINTS = {
    "chord-qualities": ChordQualityViewSet,
    "scales": ScaleViewSet,
    "scale-fingerings": ScaleFingeringViewSet,
    "chord-scales": ChordScaleViewSet,
    "tags": TagViewSet,
    "lessons": LessonViewSet,
    "exercises": ExerciseViewSet,
    "pieces": PieceViewSet,
    "piece-phrases": PiecePhraseViewSet,
}
OWNED_ENDPOINTS = {
    "styles": StyleViewSet,
    "progressions": ProgressionViewSet,
    "phrases": PhraseViewSet,
}
MINE_ENDPOINTS = {
    "feedback": FeedbackViewSet,
    "sessions": PracticeSessionViewSet,
    "takes": TakeViewSet,
    "scale-runs": ScaleRunViewSet,
    "drill-attempts": DrillAttemptViewSet,
    "reading-takes": ReadingTakeViewSet,
    "piece-takes": PieceTakeViewSet,
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
    "trainer": TrainerView,
    "reading": ReadingView,
    "repertoire": RepertoireView,
}
# Actions: a POST that changes one thing about the player and answers with a read.
ACTIONS = {"start-here": StartHereView}
ENDPOINTS = {**REFERENCE_ENDPOINTS, **OWNED_ENDPOINTS, **MINE_ENDPOINTS}
