"""One ModelViewSet per bank resource, all owner-scoped in the queryset
itself (spec Rule 12.3.3.2), so another user's things are a 404 on every
verb. Creates take identity from the caller, never the body."""

from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.routers import APIRootView as DRFAPIRootView

from ..memes import make_meme
from ..models import CaptionCard, CaptionDeck, Meme, MemeImage, Pack, PackImage, SavedMeme, Topic
from ..tiers import profile_for
from .permissions import IsOwnerOrPublicReadOnly
from .renderers import StaffOnlyBrowsableRenderer
from .serializers import (
    CaptionCardSerializer, CaptionDeckSerializer, MemeImageSerializer, MemeSerializer, PackImageSerializer,
    PackSerializer, SavedMemeSerializer, TopicSerializer, visible_images,
)
from .throttles import MemeCreateAnonThrottle, MemeCreateUserThrottle

RENDERERS = [JSONRenderer, StaffOnlyBrowsableRenderer]


class APIRootView(DRFAPIRootView):
    renderer_classes = RENDERERS


class MemzViewSet(viewsets.ModelViewSet):
    """Shared behaviour: authenticated only, owner-or-public-read-only,
    staff-only browsable API, the profile created on first use, small lists
    with no pagination (a bank is tens of rows, not thousands)."""

    permission_classes = [IsAuthenticated, IsOwnerOrPublicReadOnly]
    renderer_classes = RENDERERS
    pagination_class = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.is_authenticated:
            profile_for(request.user)

    def owner_id_of(self, obj):
        return obj.owner_id


def _own_or_public(user, model, public_field="is_public"):
    return model.objects.filter(Q(owner=user) | Q(owner__isnull=True, **{public_field: True}))


class MemeImageViewSet(MemzViewSet):
    serializer_class = MemeImageSerializer

    def get_queryset(self):
        return visible_images(self.request.user)

    def perform_create(self, serializer):
        # Upload caps and the moderation call arrive in SPR-Z.5; the verdict
        # starts `pending` regardless, so the gate (Rule 6.4.1) already holds.
        serializer.save(owner=self.request.user, visibility=MemeImage.PRIVATE,
                        moderation_status=MemeImage.PENDING, seed_key="")


class PackViewSet(MemzViewSet):
    serializer_class = PackSerializer

    def get_queryset(self):
        return _own_or_public(self.request.user, Pack).prefetch_related("images")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, is_public=False)

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        """Body: {"pack_image_ids": [...]}, first to last. Ids from another
        pack are refused, not silently moved."""
        pack = self.get_object()
        self.check_object_permissions(request, pack)
        ids = request.data.get("pack_image_ids")
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return Response({"pack_image_ids": "רשימה של מזהים, בבקשה."}, status=status.HTTP_400_BAD_REQUEST)
        rows = {row.id: row for row in pack.images.all()}
        if set(ids) != set(rows):
            return Response({"pack_image_ids": "המזהים לא תואמים את החבילה."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for position, row_id in enumerate(ids):
                PackImage.objects.filter(id=row_id).update(order=position)
        return Response(PackImageSerializer(pack.images.all(), many=True, context={"request": request}).data)


class PackImageViewSet(MemzViewSet):
    serializer_class = PackImageSerializer

    def get_queryset(self):
        user = self.request.user
        return PackImage.objects.filter(
            Q(pack__owner=user) | Q(pack__owner__isnull=True, pack__is_public=True)
        ).select_related("pack", "image")

    def owner_id_of(self, obj):
        return obj.pack.owner_id

    def perform_create(self, serializer):
        pack = serializer.validated_data["pack"]
        last = pack.images.order_by("-order").first()
        serializer.save(order=(last.order + 1) if last else 0)


class CaptionDeckViewSet(MemzViewSet):
    serializer_class = CaptionDeckSerializer

    def get_queryset(self):
        return _own_or_public(self.request.user, CaptionDeck).prefetch_related("cards")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, is_public=False)

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        deck = self.get_object()
        self.check_object_permissions(request, deck)
        ids = request.data.get("card_ids")
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return Response({"card_ids": "רשימה של מזהים, בבקשה."}, status=status.HTTP_400_BAD_REQUEST)
        rows = {row.id: row for row in deck.cards.all()}
        if set(ids) != set(rows):
            return Response({"card_ids": "המזהים לא תואמים את החפיסה."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for position, row_id in enumerate(ids):
                CaptionCard.objects.filter(id=row_id).update(order=position)
        return Response(CaptionCardSerializer(deck.cards.all(), many=True).data)


class CaptionCardViewSet(MemzViewSet):
    serializer_class = CaptionCardSerializer

    def get_queryset(self):
        user = self.request.user
        return CaptionCard.objects.filter(
            Q(deck__owner=user) | Q(deck__owner__isnull=True, deck__is_public=True)
        ).select_related("deck")

    def owner_id_of(self, obj):
        return obj.deck.owner_id

    def perform_create(self, serializer):
        deck = serializer.validated_data["deck"]
        last = deck.cards.order_by("-order").first()
        serializer.save(order=(last.order + 1) if last else 0)


class TopicViewSet(MemzViewSet):
    serializer_class = TopicSerializer

    def get_queryset(self):
        return _own_or_public(self.request.user, Topic)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, is_public=False)


class MemeViewSet(MemzViewSet):
    """The memes/ resource (spec §12.3, §7): create is the one deliberate,
    narrow exception to "no anonymous writes" (spec Rule 12.3.3.1) — a
    guest solo-creates a meme with no account, same as spec §7 describes.
    The exception is scoped the way the site's own BKM asks: it can only
    create a `Meme` (`source=solo`) from an image already visible in the
    bank (`MemeSerializer.validate_image`), it cannot set its own owner,
    verdict, or expiry, and it is throttled (spec Rule 12.3.3.7). Every
    other verb — list, retrieve, delete — is owner-only, like the rest of
    the API; a guest simply has no rows to see here (they keep their memes
    by the share link, spec §8.2)."""

    serializer_class = MemeSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    throttle_classes = [MemeCreateAnonThrottle, MemeCreateUserThrottle]

    def get_permissions(self):
        return [AllowAny()] if self.action == "create" else [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Meme.objects.none()
        return Meme.objects.filter(created_by_user=user, source=Meme.SOLO)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        meme = make_meme(
            image=serializer.validated_data["image"], caption_text=serializer.validated_data["caption_text"],
            source=Meme.SOLO, user=user,
        )
        out = self.get_serializer(meme)
        return Response(out.data, status=status.HTTP_201_CREATED, headers={"Location": f"/memz/m/{meme.share_slug}/"})


class SavedMemeViewSet(MemzViewSet):
    """A person's collection (spec §8.4). Saving clears the meme's expiry."""

    serializer_class = SavedMemeSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return SavedMeme.objects.filter(user=self.request.user).select_related("meme")

    def owner_id_of(self, obj):
        return obj.user_id

    def perform_create(self, serializer):
        with transaction.atomic():
            saved = serializer.save(user=self.request.user)
            if saved.meme.expires_at is not None:
                saved.meme.expires_at = None
                saved.meme.save(update_fields=["expires_at"])


__all__ = [
    "APIRootView", "BrowsableAPIRenderer", "MemeImageViewSet", "PackViewSet", "PackImageViewSet",
    "CaptionDeckViewSet", "CaptionCardViewSet", "TopicViewSet", "MemeViewSet", "SavedMemeViewSet",
]
