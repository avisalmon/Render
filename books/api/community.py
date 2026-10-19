"""The club in the API (BK7, Rule 6): threads, posts, reviews, the reading
log, people. Every change goes through books/community.py, like the pages."""

from django.db.models import Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import community
from ..access import profile_for
from ..models import CatalogEntry, CircleMember, Post, Profile, ReadingLog, Review, Thread
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class ThreadSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)
    body = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Thread
        fields = ["id", "kind", "circle", "author", "author_name", "title", "entry", "is_locked", "is_pinned",
                  "created_at", "last_post_at", "body"]
        read_only_fields = ["author", "is_locked", "is_pinned", "created_at", "last_post_at"]


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "thread", "author", "author_name", "body", "status", "created_at", "edited_at"]
        read_only_fields = ["author", "status", "created_at", "edited_at"]


class ReviewSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="profile.display_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "profile", "author_name", "entry", "rating", "body", "has_spoilers", "status", "created_at",
                  "updated_at"]
        read_only_fields = ["profile", "status", "created_at", "updated_at"]


class ReadingLogSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="entry.title", read_only=True)

    class Meta:
        model = ReadingLog
        fields = ["id", "entry", "title", "status", "started_on", "finished_on", "note", "updated_at"]
        read_only_fields = ["updated_at"]


class ThreadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    viewsets.GenericViewSet):
    """Open threads and my circles'. Create = start (kind, title, body,
    circle, entry). Actions: reply, lock, unlock, pin, unpin (moderators).
    Delete is the first post's delete, by its author."""

    serializer_class = ThreadSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        qs = community.visible_threads(me, kind=self.request.query_params.get("kind") or None,
                                       q=self.request.query_params.get("q"))
        if self.request.query_params.get("entry"):
            qs = qs.filter(entry_id=self.request.query_params["entry"])
        if self.request.query_params.get("circle"):
            qs = qs.filter(circle_id=self.request.query_params["circle"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            thread = community.start_thread(_me(request), d.get("kind", Thread.DISCUSSION), d.get("title", ""),
                                            d.get("body", ""), circle=d.get("circle"), entry=d.get("entry"))
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(thread).data, status=status.HTTP_201_CREATED)

    def _step(self, request, fn, *args):
        thread = self.get_object()
        try:
            fn(_me(request), thread, *args)
        except community.CommunityError as exc:
            return _conflict(exc)
        thread.refresh_from_db()
        return Response(self.get_serializer(thread).data)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        thread = self.get_object()
        try:
            post = community.reply(_me(request), thread, request.data.get("body", ""))
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(PostSerializer(post).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def posts(self, request, pk=None):
        thread = self.get_object()
        return Response(PostSerializer(community.posts_for(thread, _me(request)), many=True).data)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        return self._step(request, community.lock_thread, True)

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        return self._step(request, community.lock_thread, False)

    @action(detail=True, methods=["post"])
    def pin(self, request, pk=None):
        return self._step(request, community.pin_thread, True)

    @action(detail=True, methods=["post"])
    def unpin(self, request, pk=None):
        return self._step(request, community.pin_thread, False)


class PostViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """One post: edit (author), delete (author), hide / unhide (moderators).
    Listing is through the thread's `posts` action."""

    serializer_class = PostSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        mine = CircleMember.objects.filter(profile=me).values("circle_id")
        return Post.objects.filter(Q(thread__circle__isnull=True) | Q(thread__circle_id__in=mine)) \
            .select_related("thread", "author")

    def update(self, request, *args, **kwargs):
        post = self.get_object()
        try:
            community.edit_post(_me(request), post, request.data.get("body", ""))
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(post).data)

    def destroy(self, request, *args, **kwargs):
        try:
            community.delete_post(_me(request), self.get_object())
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        post = self.get_object()
        try:
            community.hide_post(_me(request), post, True)
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(post).data)

    @action(detail=True, methods=["post"])
    def unhide(self, request, pk=None):
        post = self.get_object()
        try:
            community.hide_post(_me(request), post, False)
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(post).data)


class ReviewViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Visible reviews (filter ?entry=). Create sets or replaces mine for
    that book; delete removes mine."""

    serializer_class = ReviewSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        qs = Review.objects.filter(Q(status=Review.VISIBLE) | Q(profile=me)).select_related("profile", "entry")
        if self.request.query_params.get("entry"):
            qs = qs.filter(entry_id=self.request.query_params["entry"])
        if self.request.query_params.get("mine") == "1":
            qs = qs.filter(profile=me)
        return qs

    def create(self, request, *args, **kwargs):
        entry = CatalogEntry.objects.filter(pk=request.data.get("entry") or 0).first()
        if entry is None:
            return Response({"entry": "required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            review = community.set_review(_me(request), entry, request.data.get("rating"), request.data.get("body", ""),
                                          str(request.data.get("has_spoilers", "")).lower() in ("1", "true"))
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if review.profile_id != _me(request).pk:
            return _conflict(community.CommunityError("club.err.not_yours"))
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                        mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """My own log only. Create sets the status for a book (one row per book)."""

    serializer_class = ReadingLogSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        qs = ReadingLog.objects.filter(profile=_me(self.request)).select_related("entry")
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        entry = CatalogEntry.objects.filter(pk=request.data.get("entry") or 0).first()
        if entry is None:
            return Response({"entry": "required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            row = community.log_reading(_me(request), entry, request.data.get("status", ""),
                                        request.data.get("note", ""))
        except community.CommunityError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)


class PeopleViewSet(viewsets.ViewSet):
    """Public profiles, each showing only what its person opened."""

    permission_classes = [HasBooksProfile]

    def list(self, request):
        me = _me(request)
        rows = community.people_with_public_profiles(me, request.query_params.get("q"))
        return Response([{"id": p.pk, "display_name": p.display_name, "area_name": p.area_name} for p in rows])

    def retrieve(self, request, pk=None):
        me = _me(request)
        who = Profile.objects.filter(pk=pk).first()
        view = community.public_view(who, me) if who else None
        if view is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": who.pk, "display_name": who.display_name, "area_name": who.area_name, "rep": view["rep"],
            "offered": view["offered"], "completed": view["completed"],
            "library": [{"copy": c.pk, "entry": c.entry_id, "title": c.entry.title} for c in view["library"]],
            "reading": [{"entry": r.entry_id, "title": r.entry.title, "status": r.status} for r in view["reading"]],
            "reviews": ReviewSerializer(view["reviews"], many=True).data,
            "threads": ThreadSerializer(view["threads"], many=True).data,
        })


