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
from .models import (
    Attempt,
    BatchNote,
    Cell,
    Chart,
    Coupon,
    Grant,
    Mastery,
    Player,
    RuleSet,
    Session,
)
from .serializers import (
    AttemptSerializer,
    BatchNoteSerializer,
    CellSerializer,
    ChartSerializer,
    CouponSerializer,
    GrantSerializer,
    MasterySerializer,
    PlayerSerializer,
    RuleSetSerializer,
    SessionSerializer,
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

        from .models import Session

        attempt = serializer.save(
            player=player,
            rule_set=player.rule_set,
            session=Session.current(player),
            correct=cell.action,
            correct_fallback=cell.fallback,
            is_correct=data["chosen"] == cell.action,
        )

        # The mastery row is folded here rather than in a signal, so the one
        # place a hand is recorded is the one place everything about a hand
        # happens. A signal would make this invisible to anybody reading the
        # endpoint, which is where somebody looks when the numbers are wrong.
        from . import mastery, notes

        mastery.record(attempt)
        notes.maybe_write(player, attempt.session)


class SessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Runs of practice. Created, renamed, and never deleted.

    Creating one closes whatever was open, which is what "reset my stats"
    means here: a fresh count, with every hand still exactly where it was
    (REQ-B.5.6). Deleting a session is refused because it is the one verb that
    would let somebody quietly disown a bad evening, and a product whose
    numbers can be curated has no numbers.
    """

    serializer_class = SessionSerializer
    permission_classes = [IsSignedIn]

    def get_queryset(self):
        return access.visible_sessions(self.request.user)

    def perform_create(self, serializer):
        from django.utils import timezone

        player = Player.for_user(self.request.user)
        Session.objects.filter(player=player, ended_at__isnull=True).update(
            ended_at=timezone.now()
        )
        serializer.save(player=player)

    def perform_update(self, serializer):
        if serializer.instance.player.user_id != self.request.user.id:
            raise PermissionDenied("זה הסשן של מישהו אחר.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            request.method,
            detail="סשן לא נמחק. אפשר להתחיל חדש, וההיסטוריה נשארת.",
        )


class BatchNoteViewSet(ReadOnlyScoped):
    """The notes. Read-only, like the chart and for the same reason: a writable
    note is a client writing its own coaching."""

    serializer_class = BatchNoteSerializer
    scope = staticmethod(access.visible_notes)


class MasteryViewSet(ReadOnlyScoped):
    """The grid, read-only.

    Derived from `Attempt` and rebuildable from it, so there is nothing a
    client could honestly tell us here that playing a hand would not. A
    writable row would let somebody hand themselves a finished grid, and the
    grid is what a learner reads when deciding they are ready.
    """

    serializer_class = MasterySerializer
    scope = staticmethod(access.visible_mastery)


class IsRoot(permissions.BasePermission):
    """Not staff, not a tier. REQ-B.7.3."""

    message = "ההחלטה היא של מנהל המוצר."

    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_superuser", False))


class CouponViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Coupons, for root (REQ-B.7.1).

    Created by minting, never by choosing a code. Never updated, because the
    only fields worth editing are the ones that would change what a code
    already in somebody's WhatsApp is worth. Never deleted, because a redeemed
    coupon is the record of who was let in and when.
    """

    serializer_class = CouponSerializer
    permission_classes = [IsRoot]

    def get_queryset(self):
        return access.visible_coupons(self.request.user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = Coupon.mint(
            by=self.request.user,
            days=max(1, min(int(data.get("days") or 7), 365)),
            label=data.get("label", ""),
        )


class GrantViewSet(ReadOnlyScoped):
    """Your own windows of access, read-only. A writable grant is a client
    handing itself the paid tier."""

    serializer_class = GrantSerializer
    scope = staticmethod(access.visible_grants)


# Every model this app owns, and the route it answers on. Kept here rather than
# in urls.py so that adding a model and forgetting its endpoint is visible in
# one place: `test_every_model_has_an_endpoint` reads this.
ROUTES = [
    ("rule-sets", RuleSetViewSet, RuleSet),
    ("players", PlayerViewSet, Player),
    ("charts", ChartViewSet, Chart),
    ("cells", CellViewSet, Cell),
    ("attempts", AttemptViewSet, Attempt),
    ("sessions", SessionViewSet, Session),
    ("notes", BatchNoteViewSet, BatchNote),
    ("mastery", MasteryViewSet, Mastery),
    ("coupons", CouponViewSet, Coupon),
    ("grants", GrantViewSet, Grant),
]
