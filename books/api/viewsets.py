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

from .. import catalog
from ..access import profile_for
from ..models import BookDetail, CatalogEntry, Creator, CreatorAlias, EntryCorrection, EntryIdentifier, Profile, Tag
from ..textnorm import identifier_scheme
from .permissions import CatalogueWrite, HasBooksProfile, StaffWrite
from .serializers import (BookDetailSerializer, CatalogEntrySerializer, CreatorAliasSerializer, CreatorSerializer,
                          EntryCorrectionSerializer, EntryIdentifierSerializer, ProfileSerializer, TagSerializer)


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
