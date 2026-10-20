"""Play in the API (BK8, Rule 6): check-ins, the points ledger, badges, a
circle's leaderboard, the year. Every change goes through books/play.py."""

from django.http import Http404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import circles, play
from ..access import profile_for
from ..models import Badge, Circle, PointEvent, ProfileBadge, ReadingCheckin
from .permissions import HasBooksProfile, StaffWrite


def _me(request):
    return profile_for(request.user)


class CheckinSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingCheckin
        fields = ["id", "day", "minutes", "created_at"]
        read_only_fields = ["day", "created_at"]


class PointEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointEvent
        fields = ["id", "profile", "kind", "points", "deal", "review", "thread", "entry", "note", "reversed_at",
                  "created_at"]
        read_only_fields = fields


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ["id", "key", "name_he", "name_en", "about_he", "about_en"]


class ProfileBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = ProfileBadge
        fields = ["id", "badge", "earned_at"]


class CheckinViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """My reading days. Create = I read today (minutes optional); delete
    removes a day. `summary` gives the streak, freezes and points."""

    serializer_class = CheckinSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return ReadingCheckin.objects.filter(profile=_me(self.request))

    def create(self, request, *args, **kwargs):
        minutes = request.data.get("minutes")
        row = play.checkin(_me(request), minutes=int(minutes) if str(minutes or "").isdigit() else None)
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        s = play.summary(_me(request))
        s["badges"] = ProfileBadgeSerializer(s["badges"], many=True).data
        return Response(s)


class PointEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The ledger: mine; staff see everyone's and may reverse a row. Points
    are never created here, only by the events that earn them."""

    serializer_class = PointEventSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            qs = PointEvent.objects.all()
            if self.request.query_params.get("profile"):
                qs = qs.filter(profile_id=self.request.query_params["profile"])
            return qs
        return PointEvent.objects.filter(profile=_me(self.request))

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        event = self.get_object()  # someone else's row is not found, not forbidden
        if not request.user.is_staff:
            return Response({"detail": "staff only"}, status=status.HTTP_403_FORBIDDEN)
        event = play.reverse(event, by=_me(request), note=request.data.get("note", ""))
        return Response(self.get_serializer(event).data)


class BadgeViewSet(viewsets.ModelViewSet):
    """The badges as named in the catalogue of milestones (staff edit the
    words); `mine` lists the caller's."""

    serializer_class = BadgeSerializer
    permission_classes = [StaffWrite]
    queryset = Badge.objects.all()

    @action(detail=False, methods=["get"])
    def mine(self, request):
        return Response(ProfileBadgeSerializer(ProfileBadge.objects.filter(profile=_me(request))
                                               .select_related("badge"), many=True).data)


class PlayViewSet(viewsets.ViewSet):
    """GET /play/board/?circle= : this week's table for a circle I am in.
    GET /play/year/?year= : my year in books."""

    permission_classes = [HasBooksProfile]

    @action(detail=False, methods=["get"])
    def board(self, request):
        me = _me(request)
        circle = Circle.objects.filter(pk=request.query_params.get("circle") or 0).first()
        if circle is None or circles.membership(me, circle) is None:
            raise Http404
        b = play.leaderboard(circle, me)
        return Response({"since": b["since"], "hidden": b["hidden"], "rows": [
            {"rank": r["rank"], "profile": r["profile"].pk, "display_name": r["profile"].display_name,
             "points": r["points"], "streak": r["streak"], "me": r["me"]} for r in b["rows"]]})

    @action(detail=False, methods=["get"])
    def year(self, request):
        year = int(request.query_params.get("year") or play.today().year)
        y = play.year_in_books(_me(request), year)
        y["read"] = [{"entry": r.entry_id, "title": r.entry.title, "finished_on": r.finished_on} for r in y["read"]]
        y["badges"] = [pb.badge.key for pb in y["badges"]]
        return Response(y)
