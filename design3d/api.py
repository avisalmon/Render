"""The REST API under /design3d/api/ (Rule 6, REQ-D3.42). Every viewset asks
the same question the pages ask (`access.can_enter`); a row that is not
yours is not there. Starting a chat turn and building from sliders go
through the pages' own endpoints, which run them in the background."""

from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import access
from .models import Design, Export, FriendLink, Invite, Maker, Message, Parameter, Part, Picture, Settings, Version


class Inside(permissions.BasePermission):
    def has_permission(self, request, view):
        return access.can_enter(request.user)


def me(request):
    return access.maker_of(request.user)


class MakerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Maker
        fields = ["id", "display_name", "email", "status", "reason", "is_admin", "daily_limit_usd", "requested_at", "decided_at"]
        read_only_fields = ["id", "email", "status", "is_admin", "requested_at", "decided_at"]


class DesignSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    current_number = serializers.IntegerField(source="current.number", read_only=True, default=None)

    class Meta:
        model = Design
        fields = ["id", "title", "owner", "owner_name", "current", "current_number", "is_shared", "shared_at", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "owner_name", "current_number", "shared_at", "created_at", "updated_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "design", "role", "state", "text", "assumptions", "version", "model",
                  "tokens_in", "tokens_cached", "tokens_out", "cost_usd", "created_at"]
        read_only_fields = fields


class PictureSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Picture
        fields = ["id", "message", "url", "width", "height", "created_at"]
        read_only_fields = fields

    def get_url(self, obj):
        return f"/design3d/files/{obj.image.name}"


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ["id", "version", "name", "label", "value", "minimum", "maximum", "step", "unit", "position"]
        read_only_fields = fields


class VersionSerializer(serializers.ModelSerializer):
    stl_url = serializers.SerializerMethodField()
    parameters = ParameterSerializer(many=True, read_only=True)

    class Meta:
        model = Version
        fields = ["id", "design", "number", "parent", "made_by", "code", "status", "error", "stl_url", "size_mm",
                  "build_seconds", "parameters", "created_at"]
        read_only_fields = fields

    def get_stl_url(self, obj):
        return f"/design3d/files/{obj.stl.name}" if obj.stl else None


class MakerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Your own row; every row for Avi, with approve and decline."""

    serializer_class = MakerSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        qs = Maker.objects.select_related("user")
        return qs if access.is_admin(self.request.user) else qs.filter(pk=me(self.request).pk)

    def perform_update(self, serializer):
        if "daily_limit_usd" in serializer.validated_data and not access.is_admin(self.request.user):
            raise PermissionDenied("Only Avi sets limits.")
        serializer.save()

    def _decide(self, status):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("Only Avi decides.")
        from django.utils import timezone

        m = self.get_object()
        m.status, m.decided_at, m.decided_by = status, timezone.now(), self.request.user
        m.save(update_fields=["status", "decided_at", "decided_by"])
        if status == Maker.APPROVED:
            from . import mail

            mail.welcome(m, self.request)
        return Response(MakerSerializer(m).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(Maker.APPROVED)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._decide(Maker.DECLINED)


class DesignViewSet(viewsets.ModelViewSet):
    """Your designs; shared ones read-only for everyone in."""

    serializer_class = DesignSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        mine = Design.objects.filter(owner=me(self.request))
        if self.request.method in permissions.SAFE_METHODS:
            return (mine | Design.objects.filter(is_shared=True, current__isnull=False)).distinct().select_related("owner", "current")
        return mine

    def perform_create(self, serializer):
        serializer.save(owner=me(self.request))

    def perform_update(self, serializer):
        current = serializer.validated_data.get("current")
        if current is not None and current.design_id != serializer.instance.pk:
            raise PermissionDenied("That version belongs to another design.")
        from django.utils import timezone

        shared = serializer.validated_data.get("is_shared")
        extra = {"shared_at": timezone.now() if shared else None} if shared is not None else {}
        serializer.save(**extra)


class _OwnedReadOnly(viewsets.ReadOnlyModelViewSet):
    permission_classes = [Inside]
    design_path = "design"

    def get_queryset(self):
        qs = self.model.objects.filter(**{f"{self.design_path}__owner": me(self.request)})
        design = self.request.query_params.get("design")
        return qs.filter(**{f"{self.design_path}_id": design}) if design else qs


class MessageViewSet(_OwnedReadOnly):
    """A design's chat (read). A turn starts at /design3d/d/<id>/send/."""

    serializer_class = MessageSerializer
    model = Message


class PictureViewSet(_OwnedReadOnly):
    serializer_class = PictureSerializer
    model = Picture
    design_path = "message__design"


class VersionViewSet(_OwnedReadOnly):
    serializer_class = VersionSerializer
    model = Version


class ParameterViewSet(_OwnedReadOnly):
    serializer_class = ParameterSerializer
    model = Parameter
    design_path = "version__design"


class PartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Part
        fields = ["id", "version", "name", "label", "position", "count", "printed", "orientation", "size_mm", "checks", "color"]


class PartViewSet(_OwnedReadOnly):
    """A version's parts (Chapter 7). Built by the server, so read only."""

    serializer_class = PartSerializer
    model = Part
    design_path = "version__design"


class Admin(permissions.BasePermission):
    def has_permission(self, request, view):
        return access.is_admin(request.user)


class InviteSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Invite
        fields = ["id", "email", "name", "status", "created_at", "expires_at", "used_at", "used_by", "revoked_at"]
        read_only_fields = ["id", "status", "created_at", "expires_at", "used_at", "used_by"]


class InviteViewSet(viewsets.ModelViewSet):
    """Avi's invitations (2026-10-29). Admin only. Creating one sends the
    email; the token itself never leaves the server except in that email."""

    serializer_class = InviteSerializer
    permission_classes = [Admin]
    queryset = Invite.objects.all()

    def perform_create(self, serializer):
        from . import mail

        inv = serializer.save(created_by=self.request.user)
        mail.invite(inv, self.request)


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = ["id", "seat_limit", "last_export_at"]
        read_only_fields = ["id", "last_export_at"]


class SettingsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """design3d's one settings row (Chapter 8). Admin only; raising the seat
    limit lets the waiting in, as on the People screen."""

    serializer_class = SettingsSerializer
    permission_classes = [Admin]

    def get_queryset(self):
        Settings.get()
        return Settings.objects.all()

    def perform_update(self, serializer):
        from . import seats

        serializer.save()
        seats.fill(self.request)


class ExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Export
        fields = ["id", "created_at", "since", "designs", "messages", "pictures", "sent"]


class ExportViewSet(viewsets.ReadOnlyModelViewSet):
    """The chats sent for analysis (REQ-D3.75). Admin only, read only: a send
    starts on the People screen."""

    serializer_class = ExportSerializer
    permission_classes = [Admin]
    queryset = Export.objects.all()


class FriendLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = FriendLink
        fields = ["id", "code", "created_at", "used_by", "used_at"]


class FriendLinkViewSet(viewsets.ReadOnlyModelViewSet):
    """Your own unique friend links (2026-10-30), read only: a new one is made
    on My designs or at /design3d/r/new/."""

    serializer_class = FriendLinkSerializer
    permission_classes = [Inside]

    def get_queryset(self):
        return FriendLink.objects.filter(maker=me(self.request))


ROUTES = [
    ("makers", MakerViewSet, Maker),
    ("designs", DesignViewSet, Design),
    ("messages", MessageViewSet, Message),
    ("pictures", PictureViewSet, Picture),
    ("versions", VersionViewSet, Version),
    ("parameters", ParameterViewSet, Parameter),
    ("invites", InviteViewSet, Invite),
    ("parts", PartViewSet, Part),
    ("settings", SettingsViewSet, Settings),
    ("exports", ExportViewSet, Export),
    ("friend-links", FriendLinkViewSet, FriendLink),
]
