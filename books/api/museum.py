"""Rare books and the museum in the API (BK10, Rule 6). Every rule is in
books/rare.py: owners send and withdraw, curators decide and invite,
owners answer, visitors see only what owners accepted."""

from django.db.models import Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import rare
from ..access import profile_for
from ..models import Copy, Exhibit, ExhibitItem, RareReview
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


def _refused(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class RareReviewSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="copy.entry.title", read_only=True)

    class Meta:
        model = RareReview
        fields = ["id", "copy", "title", "status", "owner_note", "curator_note", "created_at", "reviewed_at"]
        read_only_fields = ["status", "curator_note", "created_at", "reviewed_at"]


class ExhibitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exhibit
        fields = ["id", "title_he", "title_en", "text_he", "text_en", "is_published", "published_at", "created_at"]
        read_only_fields = ["is_published", "published_at", "created_at"]


class ExhibitItemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="entry.title", read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = ExhibitItem
        fields = ["id", "exhibit", "copy", "title", "note", "rights_statement", "position", "consent",
                  "show_owner_name", "show_photos", "owner_name"]
        read_only_fields = ["consent", "show_owner_name", "show_photos"]

    def get_owner_name(self, item):
        return item.copy.owner.display_name if item.copy and item.show_owner_name else None


class RareReviewViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                        mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Mine (staff: all). Create = send my copy (copy, owner_note); delete =
    withdraw. Staff: `decide` with confirmed and note."""

    serializer_class = RareReviewSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            return RareReview.objects.select_related("copy__entry")
        return RareReview.objects.filter(copy__owner=_me(self.request)).select_related("copy__entry")

    def create(self, request, *args, **kwargs):
        copy = Copy.objects.filter(pk=request.data.get("copy") or 0, owner=_me(request)).first()
        if copy is None:
            return Response({"copy": "one of yours"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            review = rare.send_for_review(_me(request), copy, request.data.get("owner_note", ""))
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        try:
            rare.withdraw(_me(request), review.copy)
        except rare.RareError as exc:
            return _refused(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        review = self.get_object()
        try:
            rare.decide(_me(request), review, str(request.data.get("confirmed", "")).lower() in ("1", "true"),
                        request.data.get("note", ""))
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(review).data)


class ExhibitViewSet(viewsets.ModelViewSet):
    """Published exhibits for everyone; staff create, edit, publish, delete."""

    serializer_class = ExhibitSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Exhibit.objects.all()
        return Exhibit.objects.filter(is_published=True)

    def create(self, request, *args, **kwargs):
        try:
            ex = rare.new_exhibit(_me(request), request.data.get("title_he", ""), request.data.get("title_en", ""),
                                  request.data.get("text_he", ""), request.data.get("text_en", ""))
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(ex).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return _refused(rare.RareError("rare.err.not_allowed"))
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return _refused(rare.RareError("rare.err.not_allowed"))
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        try:
            ex = rare.publish(_me(request), self.get_object(), str(request.data.get("published", "1")) in ("1", "true"))
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(ex).data)

    @action(detail=True, methods=["get"])
    def items(self, request, pk=None):
        ex = self.get_object()
        qs = ex.items.all() if request.user.is_staff else rare.shown_items(ex)
        return Response(ExhibitItemSerializer(qs, many=True).data)


class ExhibitItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                         mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Staff: all items, create = invite (exhibit, copy, note), delete.
    Owners: invitations of their copies, and `answer`."""

    serializer_class = ExhibitItemSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            return ExhibitItem.objects.select_related("entry", "copy__owner")
        return ExhibitItem.objects.filter(Q(copy__owner=_me(self.request))).select_related("entry", "copy__owner")

    def create(self, request, *args, **kwargs):
        ex = Exhibit.objects.filter(pk=request.data.get("exhibit") or 0).first()
        copy = Copy.objects.filter(pk=request.data.get("copy") or 0).first()
        if ex is None or copy is None:
            return Response({"detail": "exhibit and copy"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = rare.invite(_me(request), ex, copy, request.data.get("note", ""))
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return _refused(rare.RareError("rare.err.not_allowed"))
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        item = self.get_object()
        truthy = ("1", "true", "True")
        try:
            rare.answer(_me(request), item, str(request.data.get("accept")) in truthy,
                        str(request.data.get("show_name")) in truthy, str(request.data.get("show_photos", "1")) in truthy)
        except rare.RareError as exc:
            return _refused(exc)
        return Response(self.get_serializer(item).data)
