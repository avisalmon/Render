"""The REST API under /bkm/api/ (Rule 6, REQ-B.40). The wall is public, so
`bkms` reads for everybody (without the links, for a visitor); everything
else needs a signed-in person, and a row that is not yours to change is a
refusal, never a quiet success."""

from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import access
from .models import Bkm, Comment, Like, Project, ProjectComment, ProjectLike, Reader, Star
from .serializers import (
    BkmSerializer, CommentSerializer, LikeSerializer, ProjectCommentSerializer, ProjectLikeSerializer,
    ProjectSerializer, PublicBkmSerializer, PublicProjectSerializer, ReaderSerializer, StarSerializer,
)


class SignedIn(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class ReadAllWriteAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or access.is_admin(request.user)


def me(request):
    return access.reader_for(request.user)


class BkmViewSet(viewsets.ModelViewSet):
    """Everybody reads the wall; only Avi (an admin) adds, changes or removes a
    BKM (REQ-B.20). A hidden BKM is seen by admins only."""

    permission_classes = [ReadAllWriteAdmin]
    lookup_field = "slug"

    def get_queryset(self):
        qs = Bkm.objects.all()
        return qs if access.is_admin(self.request.user) else qs.filter(is_published=True)

    def get_serializer_class(self):
        return BkmSerializer if self.request.user.is_authenticated else PublicBkmSerializer

    def get_permissions(self):
        if self.action in ("like", "star"):
            return [SignedIn()]
        return super().get_permissions()

    def _toggle(self, model):
        bkm, reader = self.get_object(), me(self.request)
        row = model.objects.filter(reader=reader, bkm=bkm).first()
        if row:
            row.delete()
        else:
            model.objects.create(reader=reader, bkm=bkm)
        return Response({"on": row is None, "count": model.objects.filter(bkm=bkm).count() if model is Like else None})

    @action(detail=True, methods=["post"])
    def like(self, request, slug=None):
        """Toggle your like; answers with the new public count."""
        return self._toggle(Like)

    @action(detail=True, methods=["post"])
    def star(self, request, slug=None):
        """Toggle your star. Only you ever see it."""
        return self._toggle(Star)


class ReaderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Your own row: the name shown on your comments."""

    serializer_class = ReaderSerializer
    permission_classes = [SignedIn]

    def get_queryset(self):
        return Reader.objects.filter(pk=me(self.request).pk)


class LikeViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Likes are public to people signed in. You add and remove your own."""

    serializer_class = LikeSerializer
    permission_classes = [SignedIn]
    model = Like

    def get_queryset(self):
        qs = Like.objects.filter(bkm__is_published=True)
        bkm = self.request.query_params.get("bkm")
        return qs.filter(bkm_id=bkm) if bkm else qs

    def perform_create(self, serializer):
        reader, bkm = me(self.request), serializer.validated_data["bkm"]
        if not bkm.is_published:
            raise PermissionDenied("This BKM is not on the wall.")
        existing = self.model.objects.filter(reader=reader, bkm=bkm).first()
        serializer.instance = existing or serializer.save(reader=reader)

    def perform_destroy(self, instance):
        if instance.reader_id != me(self.request).pk:
            raise PermissionDenied("That is not yours.")
        instance.delete()


class StarViewSet(LikeViewSet):
    """Stars are private: the queryset is your own, and nothing else exists."""

    serializer_class = StarSerializer
    model = Star

    def get_queryset(self):
        return Star.objects.filter(reader=me(self.request))


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [SignedIn]

    def get_queryset(self):
        qs = Comment.objects.select_related("author").filter(bkm__is_published=True)
        bkm = self.request.query_params.get("bkm")
        return qs.filter(bkm_id=bkm) if bkm else qs

    def perform_create(self, serializer):
        if not serializer.validated_data["bkm"].is_published:
            raise PermissionDenied("This BKM is not on the wall.")
        serializer.save(author=me(self.request))

    def perform_update(self, serializer):
        c = serializer.instance
        if c.author_id != me(self.request).pk:
            raise PermissionDenied("You can edit only your own comment.")
        if c.deleted_at:
            raise PermissionDenied("This comment was deleted.")
        serializer.save(edited_at=timezone.now())

    def perform_destroy(self, instance):
        if instance.author_id != me(self.request).pk and not access.is_admin(self.request.user):
            raise PermissionDenied("You can delete only your own comment.")
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])


class ProjectViewSet(viewsets.ModelViewSet):
    """The exhibition (REQ-B.30 to B.35). Everybody reads it (a visitor
    without the links); anybody signed in adds their own; the owner or Avi
    changes or removes one. `?q=&bkm=&topic=&kind=&purpose=&sort=` filter
    the same way the page does."""

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [SignedIn()]

    def get_queryset(self):
        from .views import search_projects

        return search_projects(self.request.query_params)[0]

    def get_serializer_class(self):
        return ProjectSerializer if self.request.user.is_authenticated else PublicProjectSerializer

    def _photo(self, serializer):
        """The same check, shrink and strip as the form (bkm/images.py)."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        from . import images

        upload = serializer.validated_data.get("image")
        if upload:
            try:
                serializer.validated_data["image"] = images.prepare(upload, self.request.user)
            except DjangoValidationError as exc:
                raise ValidationError({"image": exc.messages})

    def perform_create(self, serializer):
        self._photo(serializer)
        serializer.save(owner=me(self.request))

    def _check(self, project):
        if project.owner.user_id != self.request.user.pk and not access.is_admin(self.request.user):
            raise PermissionDenied("This is not your project.")

    def perform_update(self, serializer):
        self._check(serializer.instance)
        self._photo(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Toggle your like; answers with the new public count."""
        project, reader = self.get_object(), me(request)
        row = ProjectLike.objects.filter(reader=reader, project=project).first()
        if row:
            row.delete()
        else:
            ProjectLike.objects.create(reader=reader, project=project)
        return Response({"on": row is None, "count": ProjectLike.objects.filter(project=project).count()})


class ProjectLikeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Likes on projects, public to people signed in; you remove your own.
    Adding goes through `projects/{id}/like/`."""

    serializer_class = ProjectLikeSerializer
    permission_classes = [SignedIn]

    def get_queryset(self):
        qs = ProjectLike.objects.all()
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs

    def perform_destroy(self, instance):
        if instance.reader_id != me(self.request).pk:
            raise PermissionDenied("That is not yours.")
        instance.delete()


class ProjectCommentViewSet(CommentViewSet):
    serializer_class = ProjectCommentSerializer

    def get_queryset(self):
        qs = ProjectComment.objects.select_related("author")
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs

    def perform_create(self, serializer):
        serializer.save(author=me(self.request))


ROUTES = [
    ("projects", ProjectViewSet, Project),
    ("project-likes", ProjectLikeViewSet, ProjectLike),
    ("project-comments", ProjectCommentViewSet, ProjectComment),
    ("bkms", BkmViewSet, Bkm),
    ("readers", ReaderViewSet, Reader),
    ("likes", LikeViewSet, Like),
    ("stars", StarViewSet, Star),
    ("comments", CommentViewSet, Comment),
]
