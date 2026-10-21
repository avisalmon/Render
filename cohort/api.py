"""The REST API under /cohort/api/ (Rule 6, REQ-C.44). Every viewset asks the
same question the pages ask (`access.can_enter`), and a row that is not yours
to change is a refusal, never a quiet success."""

from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import access, mail, shots
from .models import Comment, Exhibit, Like, Material, Member, Star, Track
from .serializers import (
    CommentSerializer, ExhibitSerializer, LikeSerializer, MaterialSerializer,
    MemberAdminSerializer, MemberSerializer, StarSerializer, TrackSerializer,
)


class Inside(permissions.BasePermission):
    def has_permission(self, request, view):
        ok = access.can_enter(request.user)
        if ok and request.user.is_superuser:
            access.ensure_admin_member(request.user)
        return ok


class AdminWrites(Inside):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.method in permissions.SAFE_METHODS or access.is_admin(request.user)


def me(request):
    return access.member_of(request.user)


class MemberViewSet(viewsets.ModelViewSet):
    """Participants see who is in (names only); admins see and decide
    everything. Asking to join is a POST by anybody signed in."""

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return [Inside()]

    def get_serializer_class(self):
        return MemberAdminSerializer if access.is_admin(self.request.user) else MemberSerializer

    def get_queryset(self):
        qs = Member.objects.select_related("user")
        return qs if access.is_admin(self.request.user) else qs.filter(status=Member.APPROVED)

    def create(self, request, *args, **kwargs):
        member = me(request)
        if member is None:
            member = Member.objects.create(user=request.user, display_name=access.display_name_for(request.user))
            return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)
        return Response(MemberSerializer(member).data)

    def perform_update(self, serializer):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("רק מנהל ההשתלמות יכול לשנות משתתפים.")
        serializer.save()

    def perform_destroy(self, instance):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("רק מנהל ההשתלמות יכול להסיר משתתפים.")
        instance.delete()

    def _decide(self, request, status_):
        if not access.is_admin(request.user):
            raise PermissionDenied("רק מנהל ההשתלמות מאשר בקשות.")
        member = self.get_object()
        member.status, member.decided_at, member.decided_by = status_, timezone.now(), request.user
        member.save(update_fields=["status", "decided_at", "decided_by"])
        if status_ == Member.APPROVED:
            mail.welcome(member, request)
        return Response(MemberAdminSerializer(member).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, Member.APPROVED)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._decide(request, Member.DECLINED)


class ExhibitViewSet(viewsets.ModelViewSet):
    serializer_class = ExhibitSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        return Exhibit.objects.select_related("owner")

    def _check(self, exhibit):
        member = me(self.request)
        if exhibit.owner_id != member.pk and not member.admin:
            raise PermissionDenied("זה לא האתר שלך.")

    def perform_create(self, serializer):
        exhibit = serializer.save(owner=me(self.request))
        shots.take(exhibit)

    def perform_update(self, serializer):
        self._check(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance)
        if instance.shot:
            instance.shot.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["post"])
    def retake(self, request, pk=None):
        exhibit = self.get_object()
        self._check(exhibit)
        exhibit.shot_status, exhibit.shot_tries = Exhibit.WAITING, 0
        exhibit.save(update_fields=["shot_status", "shot_tries"])
        shots.take(exhibit)
        return Response(ExhibitSerializer(exhibit).data)

    def _toggle(self, request, model):
        exhibit = self.get_object()
        member = me(request)
        row = model.objects.filter(member=member, exhibit=exhibit).first()
        if row:
            row.delete()
            on = False
        else:
            model.objects.get_or_create(member=member, exhibit=exhibit)
            on = True
        body = {"on": on}
        if model is Like:
            body["count"] = exhibit.likes.count()
        return Response(body)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        return self._toggle(request, Like)

    @action(detail=True, methods=["post"])
    def star(self, request, pk=None):
        return self._toggle(request, Star)


class LikeViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Likes are public: anybody inside may list them. You add and remove your own."""

    serializer_class = LikeSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        qs = Like.objects.all()
        exhibit = self.request.query_params.get("exhibit")
        return qs.filter(exhibit_id=exhibit) if exhibit else qs

    def perform_create(self, serializer):
        member = me(self.request)
        existing = Like.objects.filter(member=member, exhibit=serializer.validated_data["exhibit"]).first()
        serializer.instance = existing or serializer.save(member=member)

    def perform_destroy(self, instance):
        if instance.member_id != me(self.request).pk:
            raise PermissionDenied("זה לא הלייק שלך.")
        instance.delete()


class StarViewSet(LikeViewSet):
    """Stars are private: the queryset is your own, and nothing else exists."""

    serializer_class = StarSerializer

    def get_queryset(self):
        return Star.objects.filter(member=me(self.request))

    def perform_create(self, serializer):
        member = me(self.request)
        existing = Star.objects.filter(member=member, exhibit=serializer.validated_data["exhibit"]).first()
        serializer.instance = existing or serializer.save(member=member)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        qs = Comment.objects.select_related("author")
        exhibit = self.request.query_params.get("exhibit")
        return qs.filter(exhibit_id=exhibit) if exhibit else qs

    def perform_create(self, serializer):
        serializer.save(author=me(self.request))

    def perform_update(self, serializer):
        c = serializer.instance
        if c.author_id != me(self.request).pk:
            raise PermissionDenied("אפשר לערוך רק תגובה שלך.")
        if c.deleted_at:
            raise PermissionDenied("התגובה נמחקה.")
        serializer.save(edited_at=timezone.now())

    def perform_destroy(self, instance):
        member = me(self.request)
        if instance.author_id != member.pk and not member.admin:
            raise PermissionDenied("אפשר למחוק רק תגובה שלך.")
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])


class TrackViewSet(viewsets.ModelViewSet):
    serializer_class = TrackSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        return Track.objects.select_related("owner")

    def perform_create(self, serializer):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("מגמות נוספות דרך אבי.")
        serializer.save()

    def perform_update(self, serializer):
        t, member = serializer.instance, me(self.request)
        if member.admin:
            serializer.save()
            return
        if t.owner_id != member.pk:
            raise PermissionDenied("רק הבעלים של המגמה מעדכן את הקישורים שלה.")
        links = {k: v for k, v in serializer.validated_data.items() if k in ("vision_url", "graduate_url", "project_url")}
        if set(serializer.validated_data) - set(links):
            raise PermissionDenied("הבעלים מעדכן רק את שלושת הקישורים.")
        serializer.save()

    def perform_destroy(self, instance):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("רק אבי מסיר מגמות.")
        instance.delete()


class MaterialViewSet(viewsets.ModelViewSet):
    serializer_class = MaterialSerializer
    permission_classes = [AdminWrites]
    queryset = Material.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()


ROUTES = [
    ("members", MemberViewSet, Member),
    ("exhibits", ExhibitViewSet, Exhibit),
    ("likes", LikeViewSet, Like),
    ("stars", StarViewSet, Star),
    ("comments", CommentViewSet, Comment),
    ("tracks", TrackViewSet, Track),
    ("materials", MaterialViewSet, Material),
]
