"""The REST API for blackjack (methodology Rule 6).

Full CRUD over every model this app owns, one viewset each, on a router under
`/blackjack/api/`. DRF's browsable API is the documentation, which is the call
this site already made for ustrip and מט״צים.

**Every queryset comes from `blackjack/access.py`.** Scope is a property of the
data, not a rule each viewset remembers, so there is exactly one answer to "who
may see this" and the screens and the API share it.

**Three verbs are refused, and each refusal is a requirement rather than a gap:**

1. **A rule set is never updated.** REQ-B.2.3: the correct play only exists
   relative to a rule set, so editing one rewrites the right answer for every
   hand already dealt against it. Changing your table creates a different row,
   which is what `POST` here does.
2. **A rule set is never deleted.** Hands point at it. Deleting it would orphan
   the only thing that makes them judgeable.
3. **A chart cell is never written, by anybody, ever.** The correct play comes
   from `blackjack.strategy` through the seeding command. A writable cell would
   be a second source of truth for the one thing this product exists to get
   right, and the first thing a competitor gets wrong.

Where a verb is refused the viewset says so in words, and a test holds each one.
"""

from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError

from . import access
from .models import Attempt, Cell, Chart, Player, RuleSet
from .serializers import (
    AttemptSerializer,
    CellSerializer,
    ChartSerializer,
    PlayerSerializer,
    RuleSetSerializer,
)


class IsSignedIn(permissions.BasePermission):
    """The floor. There is no anonymous product (REQ-B.6.1), so there is no
    anonymous API either."""

    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_authenticated", False))


class Scoped(viewsets.ModelViewSet):
    permission_classes = [IsSignedIn]
    scope = None

    def get_queryset(self):
        assert self.scope is not None, "a viewset here must name its access scope"
        return self.scope(self.request.user)


class ReadOnlyScoped(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Readable, never written through the API. A refused verb answers 405,
    which is the honest reply: the route exists and that method is not part of
    it."""

    permission_classes = [IsSignedIn]
    scope = None

    def get_queryset(self):
        assert self.scope is not None
        return self.scope(self.request.user)


class RuleSetViewSet(Scoped):
    """Tables. Created by asking for rules that nobody has played yet."""

    serializer_class = RuleSetSerializer
    scope = staticmethod(access.visible_rule_sets)

    def perform_create(self, serializer):
        """Goes through `RuleSet.for_rules`, the one door rules come through.

        So asking for a table somebody already plays returns that row instead
        of making a duplicate, which is what keeps a chart per rule set
        affordable rather than a chart per request.
        """
        rules = {
            field: serializer.validated_data[field]
            for field in serializer.validated_data
            if field != "name"
        }
        serializer.instance = RuleSet.for_rules(**rules)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            request.method,
            detail=(
                "שולחן לא נערך. החוקים קובעים מה התשובה הנכונה, ועריכה שלהם "
                "משכתבת בשקט כל יד שכבר שוחקה מולם. אפשר ליצור שולחן אחר."
            ),
        )

    partial_update = update

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            request.method,
            detail="שולחן לא נמחק: ידיים שכבר שוחקו מצביעות עליו.",
        )


class PlayerViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Your own row.

    No create: the row is made on first sight, so a client making one is a
    client guessing at something the server already knows. No delete: removing
    a person is account deletion, which belongs to babook and takes everything
    with it, not to a blackjack endpoint.
    """

    serializer_class = PlayerSerializer
    permission_classes = [IsSignedIn]

    def get_queryset(self):
        return access.visible_players(self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied("זה החשבון של מישהו אחר.")
        serializer.save()


class ChartViewSet(ReadOnlyScoped):
    """Charts are built by `manage.py seed_blackjack_chart`, never posted."""

    serializer_class = ChartSerializer
    scope = staticmethod(access.visible_charts)


class CellViewSet(ReadOnlyScoped):
    """The correct plays. Read-only to everybody including root.

    This is the strictest thing in the app and the reason is the whole product:
    a cell that can be written through an API is a correct play that two
    sources disagree about, and the learner is the one who finds out.
    """

    serializer_class = CellSerializer
    scope = staticmethod(access.visible_cells)

    def get_queryset(self):
        rows = super().get_queryset()
        chart = self.request.query_params.get("chart")
        kind = self.request.query_params.get("kind")
        if chart:
            rows = rows.filter(chart_id=chart)
        if kind:
            rows = rows.filter(kind=kind)
        return rows


class AttemptViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Recording what somebody played (REQ-B.4.4).

    **Create and read only.** An attempt is a record of something that
    happened. Updating one would rewrite history, and deleting one would let a
    person quietly erase the hands they got wrong, which is the one thing that
    would make every number in the product meaningless. A person who wants a
    clean slate starts a new session (REQ-B.5.6); the history stays.

    **The server decides whether they were right.** The chart ships with the
    page, so the browser knows the answer and could report any accuracy it
    liked. The numbers are what is being sold, so `correct`, `correct_fallback`
    and `is_correct` are read off the chart row here and the client's opinion is
    not consulted. This is also what makes the offline queue safe: a queued
    attempt sent an hour later is judged against the same row it was asked from.
    """

    serializer_class = AttemptSerializer
    permission_classes = [IsSignedIn]

    def get_queryset(self):
        return access.visible_attempts(self.request.user)

    def perform_create(self, serializer):
        from django.utils import timezone

        from .models import Chart

        player = Player.for_user(self.request.user)
        chart = Chart.objects.filter(rule_set=player.rule_set).first()
        if chart is None:
            raise ValidationError({"detail": "אין טבלה לשולחן הזה."})

        data = serializer.validated_data
        cell = chart.cells.filter(
            kind=data["cell_kind"],
            player=data["cell_player"],
            dealer=data["cell_dealer"],
        ).first()
        if cell is None:
            raise ValidationError({"detail": "אין תא כזה בטבלה."})

        # REQ-B.6.3 — the thirty minutes start at the first hand, not at
        # signup. Set once, here, because this is the first moment the app can
        # honestly say somebody has used it.
        if player.first_used_at is None:
            player.first_used_at = timezone.now()
            player.save(update_fields=["first_used_at"])

        serializer.save(
            player=player,
            rule_set=player.rule_set,
            correct=cell.action,
            correct_fallback=cell.fallback,
            is_correct=data["chosen"] == cell.action,
        )


# Every model this app owns, and the route it answers on. Kept here rather than
# in urls.py so that adding a model and forgetting its endpoint is visible in
# one place: `test_every_model_has_an_endpoint` reads this.
ROUTES = [
    ("rule-sets", RuleSetViewSet, RuleSet),
    ("players", PlayerViewSet, Player),
    ("charts", ChartViewSet, Chart),
    ("cells", CellViewSet, Cell),
    ("attempts", AttemptViewSet, Attempt),
]
