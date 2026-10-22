"""Friends in the API (Rule 6): my invite link, who I follow and who
follows me, requests and answers. Every change goes through books/friends.py."""

from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import friends
from ..access import profile_for
from ..models import Follow, Invite, Profile
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


class InviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invite
        fields = ["id", "code", "joined", "is_active", "created_at"]
        read_only_fields = fields


class FollowSerializer(serializers.ModelSerializer):
    follower_name = serializers.CharField(source="follower.display_name", read_only=True)
    followee_name = serializers.CharField(source="followee.display_name", read_only=True)

    class Meta:
        model = Follow
        fields = ["id", "follower", "follower_name", "followee", "followee_name", "status", "source", "created_at",
                  "accepted_at"]
        read_only_fields = ["follower", "status", "source", "created_at", "accepted_at"]


class InviteViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """My invite link (made on first ask)."""

    serializer_class = InviteSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        friends.invite_for(_me(self.request))
        return Invite.objects.filter(inviter=_me(self.request))


class FollowViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Follows I am part of. `?as=follower` (I follow), `?as=followee` (they
    follow me, requests included). POST {followee} asks to follow; POST
    `{id}/accept` and `{id}/decline` answer a request; DELETE unfollows (as
    follower) or quietly removes a follower (as followee)."""

    serializer_class = FollowSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        qs = Follow.objects.select_related("follower", "followee")
        role = self.request.query_params.get("as")
        if role == "follower":
            return qs.filter(follower=me)
        if role == "followee":
            return qs.filter(followee=me)
        return qs.filter(follower=me) | qs.filter(followee=me)

    def create(self, request, *args, **kwargs):
        other = get_object_or_404(Profile, pk=request.data.get("followee") or 0)
        try:
            row = friends.follow(_me(request), other)
        except friends.FriendsError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(FollowSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        row = self.get_object()
        try:
            friends.accept(_me(request), row)
        except friends.FriendsError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(FollowSerializer(row).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        row = self.get_object()
        try:
            friends.decline(_me(request), row)
        except friends.FriendsError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        me = _me(self.request)
        if instance.follower_id == me.pk:
            friends.unfollow(me, instance.followee)
        else:
            friends.remove_follower(me, instance.follower)
