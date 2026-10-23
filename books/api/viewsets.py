"""The API (Rule 6): the caller's Profile, and the shared catalogue.

Catalogue reads are open to anyone onboarded; the catalogue says nothing
about who owns what. Writes follow CatalogueWrite. Merged entries are
hidden from lists and resolve to their winner on retrieve.
"""

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from rest_framework.parsers import FormParser, MultiPartParser

from .. import catalog
from .. import shelf as shelf_service
from ..access import profile_for
from ..models import (BookDetail, CatalogEntry, Copy, CopyPhoto, Creator, CreatorAlias, EntryCorrection,
                      EntryIdentifier, Offer, Profile, ScanItem, ShelfScan, Tag, Wish)
from ..textnorm import identifier_scheme
from .permissions import CatalogueWrite, HasBooksProfile, StaffWrite
from .serializers import (BookDetailSerializer, CatalogEntrySerializer, CopyPhotoSerializer, CopySerializer,
                          CreatorAliasSerializer, CreatorSerializer, EntryCorrectionSerializer,
                          EntryIdentifierSerializer, OfferSerializer, ProfileSerializer, ScanItemSerializer,
                          ShelfScanSerializer, TagSerializer, WishSerializer)


class ProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [StaffWrite]
    queryset = Tag.objects.all()


class CreatorViewSet(viewsets.ModelViewSet):
    serializer_class = CreatorSerializer
    permission_classes = [StaffWrite]

    def get_queryset(self):
        qs = Creator.objects.prefetch_related("aliases")
        q = self.request.query_params.get("q")
        if q:
            from ..textnorm import normalize
            key = normalize(q)
            qs = qs.filter(Q(search_name__contains=key) | Q(aliases__search_name__contains=key)).distinct()
        return qs


class CreatorAliasViewSet(viewsets.ModelViewSet):
    serializer_class = CreatorAliasSerializer
    permission_classes = [StaffWrite]
    queryset = CreatorAlias.objects.all()


class CatalogEntryViewSet(viewsets.ModelViewSet):
    serializer_class = CatalogEntrySerializer
    permission_classes = [CatalogueWrite]

    def get_queryset(self):
        qs = CatalogEntry.objects.prefetch_related("creators", "identifiers", "tags").select_related("book")
        if self.action == "list":
            qs = qs.filter(merged_into__isnull=True)
            if self.request.query_params.get("unverified") == "1":
                qs = qs.filter(is_verified=False)
            if self.request.query_params.get("mine") == "1":
                qs = qs.filter(created_by=profile_for(self.request.user))
            tag = self.request.query_params.get("tag")
            if tag:
                qs = qs.filter(tags__key=tag)
            creator = self.request.query_params.get("creator")
            if creator:
                qs = qs.filter(creators__pk=creator)
        return qs

    def get_object(self):
        obj = super().get_object()
        return obj.merged_into or obj

    def perform_create(self, serializer):
        names = serializer.validated_data.pop("creator_names", [])
        entry = serializer.save(collection_type=catalog.book_type(), created_by=profile_for(self.request.user),
                                source="manual", is_verified=False)
        if names:
            catalog.set_creators(entry, names)
        else:
            entry.refresh_search_text()
        BookDetail.objects.get_or_create(entry=entry)

    def perform_update(self, serializer):
        names = serializer.validated_data.pop("creator_names", None)
        entry = serializer.save()
        if names is not None:
            catalog.set_creators(entry, names)
        else:
            entry.refresh_search_text()

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Local first; `?sources=1` also asks the sources and copies the
        results in, which is what the confirmation screen does when the
        local catalogue is thin."""
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response({"results": [], "imported": 0})
        found = catalog.search_local(q)
        imported = 0
        if request.query_params.get("sources") == "1" and len(found) < 5:
            ident = identifier_scheme(q)
            entries = catalog.import_lookup(query=None if ident else q, isbn=ident[1] if ident and ident[0] == "isbn13" else None,
                                            created_by=profile_for(request.user))
            imported = len(entries)
            found = catalog.search_local(q) or entries
        return Response({"results": CatalogEntrySerializer(found, many=True, context={"request": request}).data,
                         "imported": imported})

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        entry = catalog.verify(self.get_object())
        return Response(CatalogEntrySerializer(entry, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def merge(self, request, pk=None):
        """POST {"into": <id>}: this entry is merged into that one."""
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        loser = self.get_object()
        winner = CatalogEntry.objects.filter(pk=request.data.get("into")).first()
        if winner is None or winner.pk == loser.pk:
            raise ValidationError({"into": "an existing, different entry"})
        winner = catalog.merge(loser, winner)
        return Response(CatalogEntrySerializer(winner, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def suggest(self, request, pk=None):
        """Anyone onboarded may suggest a correction; a curator decides."""
        # Suggesting is not editing: no write permission on the entry is needed.
        entry = CatalogEntry.objects.filter(pk=pk).first()
        if entry is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        entry = entry.merged_into or entry
        ser = EntryCorrectionSerializer(data={**request.data, "entry": entry.pk})
        ser.is_valid(raise_exception=True)
        ser.save(profile=profile_for(request.user))
        return Response(ser.data, status=status.HTTP_201_CREATED)


class EntryIdentifierViewSet(viewsets.ModelViewSet):
    serializer_class = EntryIdentifierSerializer
    permission_classes = [StaffWrite]
    queryset = EntryIdentifier.objects.select_related("entry")


class BookDetailViewSet(viewsets.ModelViewSet):
    serializer_class = BookDetailSerializer
    permission_classes = [CatalogueWrite]
    queryset = BookDetail.objects.select_related("entry")

    def check_object_permissions(self, request, obj):
        # The detail belongs with its entry: same rule, judged on the entry.
        super().check_object_permissions(request, obj.entry)


class EntryCorrectionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                             mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Mine to list and add; a curator sees all and sets the status."""

    serializer_class = EntryCorrectionSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        qs = EntryCorrection.objects.select_related("entry", "profile")
        if self.request.user.is_staff:
            return qs
        return qs.filter(profile=profile_for(self.request.user))

    def perform_create(self, serializer):
        serializer.save(profile=profile_for(self.request.user))

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        correction = self.get_object()
        decision = request.data.get("status")
        me = profile_for(request.user)
        if decision == EntryCorrection.ACCEPTED:
            catalog.accept_correction(correction, me)
        elif decision == EntryCorrection.DECLINED:
            catalog.decline_correction(correction, me)
        else:
            raise ValidationError({"status": "accepted or declined"})
        return Response(self.get_serializer(correction).data)


# ---- the person's shelf (BK3): everything scoped to the caller ---------------------


class ShelfScanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Create through POST /scans/upload/ (multipart: photo, shelf_label,
    default_visibility, default_offers, single=1 for one book). The photo itself is never in the API."""

    serializer_class = ShelfScanSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return ShelfScan.objects.filter(owner=profile_for(self.request.user)).prefetch_related("items__candidates")

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        photo = request.FILES.get("photo")
        if photo is None:
            raise ValidationError({"photo": "required"})
        me = profile_for(request.user)
        if shelf_service.room_left(me) == 0:
            return Response({"detail": "cap"}, status=status.HTTP_409_CONFLICT)
        offers = request.data.getlist("default_offers") if hasattr(request.data, "getlist") else []
        scan = shelf_service.start_scan(me, photo, request.data.get("shelf_label", ""),
                                        request.data.get("default_visibility", "private"), offers,
                                        single=request.data.get("single") in ("1", "true", "True", True))
        scan.refresh_from_db()
        return Response(ShelfScanSerializer(scan).data, status=status.HTTP_201_CREATED)


class ScanItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ScanItemSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return ScanItem.objects.filter(scan__owner=profile_for(self.request.user)).prefetch_related("candidates")

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        item = self.get_object()
        entry_id = request.data.get("entry")
        if entry_id:
            cand = item.candidates.filter(entry_id=entry_id).select_related("entry").first()
            if cand is None:
                raise ValidationError({"entry": "one of this item's candidates"})
            entry = cand.entry.merged_into or cand.entry
        elif request.data.get("title"):
            entry = shelf_service.entry_from_text(request.data["title"], request.data.get("author", ""), item.scan.owner)
        else:
            raise ValidationError({"entry": "a candidate, or a title"})
        offers = request.data.get("offers") or []
        try:
            copy = shelf_service.accept(item, entry, request.data.get("visibility", "private"), offers,
                                        request.data.get("location_note", item.scan.shelf_label))
        except shelf_service.CapReached:
            return Response({"detail": "cap"}, status=status.HTTP_409_CONFLICT)
        return Response(CopySerializer(copy).data)

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        shelf_service.skip(self.get_object())
        return Response({"ok": True})


class CopyViewSet(viewsets.ModelViewSet):
    serializer_class = CopySerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Copy.objects.filter(owner=profile_for(self.request.user)).select_related("entry").prefetch_related("offers")

    def perform_create(self, serializer):
        me = profile_for(self.request.user)
        if shelf_service.room_left(me) == 0:
            raise ValidationError({"detail": "cap"})
        serializer.save(owner=me, added_via="manual", position=shelf_service.next_position(me))

    def perform_update(self, serializer):
        copy = serializer.save()
        if copy.visibility == Copy.HIDDEN:
            copy.offers.all().delete()  # "only me" means no offers; friends-only keeps them (2026-10-23)


class OfferViewSet(viewsets.ModelViewSet):
    serializer_class = OfferSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Offer.objects.filter(copy__owner=profile_for(self.request.user))

    def perform_create(self, serializer):
        if serializer.validated_data["copy"].owner != profile_for(self.request.user):
            raise ValidationError({"copy": "not yours"})
        serializer.save()

    def perform_update(self, serializer):
        copy = serializer.validated_data.get("copy")
        if copy is not None and copy.owner != profile_for(self.request.user):
            raise ValidationError({"copy": "not yours"})
        serializer.save()


class CopyPhotoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """List, retrieve, relabel, delete. Upload through the copy page (the
    photo goes through the same metadata stripping as a shelf photo)."""

    serializer_class = CopyPhotoSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return CopyPhoto.objects.filter(copy__owner=profile_for(self.request.user))

    def perform_update(self, serializer):
        copy = serializer.validated_data.get("copy")
        if copy is not None and copy.owner != profile_for(self.request.user):
            raise ValidationError({"copy": "not yours"})
        serializer.save()

    def perform_destroy(self, instance):
        instance.image.delete(save=False)
        instance.delete()


class WishViewSet(viewsets.ModelViewSet):
    serializer_class = WishSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Wish.objects.filter(profile=profile_for(self.request.user))

    def perform_create(self, serializer):
        me = profile_for(self.request.user)
        entry = serializer.validated_data.get("entry")
        if entry is not None and Wish.objects.filter(profile=me, entry=entry).exists():
            raise ValidationError({"entry": "already wished"})
        serializer.save(profile=me)
