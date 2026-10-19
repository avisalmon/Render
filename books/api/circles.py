"""Circles, feedback and the pilot numbers in the API (BK6, Rule 6). Every
change goes through books/circles.py, like the pages."""

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import circles
from ..access import profile_for
from ..models import Circle, CircleMember, Feedback
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class CircleSerializer(serializers.ModelSerializer):
    n_members = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()
    join_code = serializers.SerializerMethodField()
    code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Circle
        fields = ["id", "name", "kind", "area_name", "description", "is_private", "created_by", "created_at",
                  "n_members", "my_role", "join_code", "code"]
        read_only_fields = ["created_by", "created_at"]

    def _member(self, circle):
        request = self.context.get("request")
        return circles.membership(_me(request), circle) if request else None

    def get_my_role(self, circle):
        m = self._member(circle)
        return m.role if m else None

    def get_join_code(self, circle):
        # The code is the key to a private circle: members only.
        return circle.join_code if self._member(circle) else None


class CircleMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="profile.display_name", read_only=True)

    class Meta:
        model = CircleMember
        fields = ["id", "circle", "profile", "display_name", "role", "joined_at"]
        read_only_fields = ["profile", "joined_at"]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "profile", "path", "body", "status", "created_at"]
        read_only_fields = ["profile", "status", "created_at"]


class CircleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Mine and the open ones. Create makes me its owner. Update takes a
    moderator. Delete does not exist: the last member leaving closes it.
    Actions: join (code for a private one), leave, new-code, books."""

    serializer_class = CircleSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        mine = CircleMember.objects.filter(profile=me).values("circle_id")
        return circles.with_counts().filter(Q(is_private=False) | Q(pk__in=mine))

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            circle = circles.create(_me(request), d.get("name", ""), d.get("kind", "club"), d.get("area_name", ""),
                                    d.get("description", ""), d.get("is_private", True))
        except circles.CircleError as exc:
            return _conflict(exc)
        circle = self.get_queryset().get(pk=circle.pk)
        return Response(self.get_serializer(circle).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        circle = self.get_object()
        ser = self.get_serializer(circle, data=request.data, partial=kwargs.get("partial", False))
        ser.is_valid(raise_exception=True)
        try:
            circles.edit(_me(request), circle, **{k: v for k, v in ser.validated_data.items() if k != "code"})
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(self.get_queryset().get(pk=circle.pk)).data)

    def _step(self, request, fn, *args):
        circle = self.get_object()
        try:
            result = fn(*args) if args else fn(circle)
        except circles.CircleError as exc:
            return _conflict(exc)
        return result

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        circle = self.get_object()
        try:
            circles.join(_me(request), circle, request.data.get("code"))
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(self.get_queryset().get(pk=circle.pk)).data)

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        circle = self.get_object()
        try:
            left = circles.leave(_me(request), circle)
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response({"ok": True, "closed": left is None})

    @action(detail=True, methods=["post"], url_path="new-code")
    def new_code(self, request, pk=None):
        circle = self.get_object()
        try:
            code = circles.new_join_code(_me(request), circle)
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response({"join_code": code})

    @action(detail=True, methods=["get"])
    def books(self, request, pk=None):
        circle = self.get_object()
        rows = circles.books(circle, _me(request))
        return Response([{"copy": c.pk, "entry": c.entry_id, "title": c.entry.title, "creators": c.entry.creator_names,
                          "owner": c.owner.display_name, "km": round(km) if km is not None else None,
                          "offers": [o.kind for o in c.offers.all() if o.is_active]} for c, km in rows])


class CircleMemberViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Members of my circles. Update sets the role (owner only); delete
    removes a member (owner or moderator, per books/circles.py)."""

    serializer_class = CircleMemberSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        mine = CircleMember.objects.filter(profile=me).values("circle_id")
        qs = CircleMember.objects.filter(circle_id__in=mine).select_related("profile")
        if self.request.query_params.get("circle"):
            qs = qs.filter(circle_id=self.request.query_params["circle"])
        return qs

    def update(self, request, *args, **kwargs):
        member = self.get_object()
        role = request.data.get("role")
        try:
            circles.set_role(_me(request), member, role)
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(member).data)

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        try:
            circles.remove(_me(request), member)
        except circles.CircleError as exc:
            return _conflict(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedbackViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Anyone onboarded writes feedback and sees their own; staff see all
    and mark it read."""

    serializer_class = FeedbackSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Feedback.objects.select_related("profile")
        return Feedback.objects.filter(profile=_me(self.request))

    def perform_create(self, serializer):
        serializer.save(profile=_me(self.request))

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise ValidationError({"detail": "staff only"})
        serializer.save(status=self.request.data.get("status") or Feedback.READ)


class PilotViewSet(viewsets.ViewSet):
    """GET /pilot/ : the numbers, staff only (404 for everyone else)."""

    permission_classes = [HasBooksProfile]

    def list(self, request):
        if not request.user.is_staff:
            from django.http import Http404

            raise Http404
        from ..pilot import numbers

        data = numbers(int(request.query_params.get("days") or 7))
        data["circles"] = [{"id": c.pk, "name": c.name, "kind": c.kind, "members": c.n_members, "books": c.n_books}
                           for c in data["circles"]]
        data["feedback"] = FeedbackSerializer(data["feedback"], many=True).data
        data["as_of"] = timezone.now().isoformat()
        return Response(data)
