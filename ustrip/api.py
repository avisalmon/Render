"""The REST API (spec/methodology Rule 6): full CRUD, one ModelViewSet per
model, registered on a router under /ustrip/api/... . Pages consume this
API with fetch() (static/ustrip/ustrip.js) instead of a separate hand-rolled
JSON layer — this *is* the infrastructure now, not an add-on for the
screens that happened to need one.

Every viewset shares one permission: IsFamilyMember (spec §3). Comments and
likes add IsOwnerOrReadOnly on top — one person's words or gesture. The
custom actions are the things that aren't one of the four CRUD verbs:
`move` (swap with a neighbour), `reorder` (a whole day's new order, which
is what a drag-and-drop produces, and which may pull items in from other
days), and `like` (toggle).
"""

import time

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app import drive

from .models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryComment, ItineraryDay, ItineraryItem, ItineraryLike,
    ItineraryLink, ItineraryPhoto, JournalPost, Lodging, RentalCar, Trip, TripNote,
)
from .permissions import IsFamilyMember, IsOwnerOrReadOnly
from .reorder import move as reorder_move
from .serializers import (
    ChecklistGroupSerializer, ChecklistItemSerializer, FlightSerializer, ItineraryCommentSerializer,
    ItineraryDaySerializer, ItineraryItemSerializer, ItineraryLikeSerializer, ItineraryLinkSerializer,
    ItineraryPhotoSerializer, JournalPostSerializer, LodgingSerializer, RentalCarSerializer, TripNoteSerializer,
    TripSerializer,
)


def _renumber(queryset):
    """Close the gaps after items leave a day: 0, 1, 2, ... in current order."""
    for index, row in enumerate(queryset.order_by("order", "id")):
        if row.order != index:
            row.order = index
            row.save(update_fields=["order"])


def _attach_drive_photo(instance, upload):
    """Push an uploaded photo to Drive and record where it landed (Sprint 15).

    Called from `perform_create` after the row is saved, so `instance.pk`
    exists for the filename. Raises loudly when Drive is not configured or the
    upload fails — never a silent fallback to local disk, which is the exact
    1GB-shared-disk risk this sprint exists to close (spec §0a.3). `upload`
    being empty is a normal case for `JournalPost` (a text-only post) and a
    no-op here, not an error.
    """
    if not upload:
        return
    client = drive.from_env("ustrip")
    if client is None:
        raise ValidationError({
            "photo": "Photo storage isn't set up yet — ask Avi to set the Drive keys in Render.",
        })
    content_type = getattr(upload, "content_type", "") or "image/jpeg"
    name = f"{instance._meta.model_name}-{instance.pk}-{int(time.time())}.jpg"
    uploaded = client.upload_bytes(upload.read(), name, mime=content_type)
    if uploaded is None:
        raise ValidationError({"photo": "Could not upload the photo. Try again in a moment."})
    instance.drive_file_id = uploaded.file_id
    instance.drive_url = uploaded.url
    instance.content_type = content_type
    instance.save(update_fields=["drive_file_id", "drive_url", "content_type"])


def _detach_drive_photo(instance):
    """Best-effort delete of the Drive file behind `instance`, mirroring the
    security app's own "best-effort" note (relay_api.md §6.4): a Drive
    hiccup on delete must not block the family from removing the row, and
    `DriveClient.delete` already treats "already gone" as success."""
    if not instance.drive_file_id:
        return
    client = drive.from_env("ustrip")
    if client is not None:
        client.delete(instance.drive_file_id)


def with_counts_for(queryset, user):
    """Put an item's like count, comment count and whether *this* user has
    liked it onto the row itself.

    Without this the item serializer asks three questions per item, which on a
    13-day trip meant hundreds of queries for one list response (measured
    2026-09-14: 425 on the days endpoint, 342 on the items one). The
    serializer reads `*_a` when present and falls back to asking, so a lone
    unannotated instance still serializes correctly."""
    liked = ItineraryLike.objects.filter(item=OuterRef("pk"), user=user.pk if user and user.is_authenticated else None)
    return queryset.annotate(
        like_count_a=Count("likes", distinct=True),
        comment_count_a=Count("comments", distinct=True),
        liked_by_me_a=Exists(liked),
    )


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsFamilyMember]


class ItineraryDayViewSet(viewsets.ModelViewSet):
    queryset = ItineraryDay.objects.all()
    serializer_class = ItineraryDaySerializer
    permission_classes = [IsFamilyMember]

    def get_queryset(self):
        """The nested items carry their own counts, so serializing a day does
        not fan out into three queries per item."""
        items = with_counts_for(ItineraryItem.objects.prefetch_related("links", "photos"), self.request.user)
        return super().get_queryset().prefetch_related(Prefetch("items", queryset=items))

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        """Body: {"item_ids": [...]} — the day's new order, first to last.
        This is what a drag-and-drop ends in. An id that belongs to another
        day is moved into this one at that position (drag between days,
        spec §4.1); the day it left is renumbered. Ids of this day's items
        that are missing from the list keep their relative order after the
        listed ones, so a partial list never loses anything."""
        day = self.get_object()
        item_ids = request.data.get("item_ids")
        if not isinstance(item_ids, list) or not all(isinstance(i, int) for i in item_ids):
            return Response({"error": "item_ids must be a list of integers"}, status=400)
        items = {item.pk: item for item in ItineraryItem.objects.filter(pk__in=item_ids)}
        if len(items) != len(set(item_ids)):
            return Response({"error": "unknown item id"}, status=400)

        with transaction.atomic():
            source_days = set()
            ordered = [items[i] for i in item_ids]
            leftover = [item for item in day.items.order_by("order", "id") if item.pk not in items]
            for index, item in enumerate(ordered + leftover):
                changed = []
                if item.day_id != day.pk:
                    source_days.add(item.day_id)
                    item.day = day
                    changed.append("day")
                if item.order != index:
                    item.order = index
                    changed.append("order")
                if changed:
                    item.save(update_fields=changed)
            for source_day_id in source_days:
                _renumber(ItineraryItem.objects.filter(day_id=source_day_id))

        # `day` came out of get_object() with its items already prefetched —
        # the order before this call. Re-read it so the response is the
        # order after, with the times recomputed from it.
        fresh = ItineraryDay.objects.get(pk=day.pk)
        return Response(self.get_serializer(fresh).data)


class ItineraryItemViewSet(viewsets.ModelViewSet):
    """Spec §4.1: any family member can add/edit/delete/reorder — no
    creator-only lock."""

    queryset = ItineraryItem.objects.select_related("day").prefetch_related("links", "photos")
    serializer_class = ItineraryItemSerializer
    permission_classes = [IsFamilyMember]

    def get_queryset(self):
        """`day__items` matters as much as the counts: the serializer computes
        each item's day once, and that pass walks `day.items.all()`. Prefetched,
        the whole list costs one extra query instead of one per day."""
        return with_counts_for(
            super().get_queryset().prefetch_related("day__items"), self.request.user
        )

    def perform_create(self, serializer):
        day = serializer.validated_data["day"]
        serializer.save(order=day.items.count())

    def perform_update(self, serializer):
        """Changing `day` on an item ("move to another day" from the detail
        page) appends it to the new day and closes the gap in the old one."""
        item = serializer.instance
        old_day_id = item.day_id
        new_day = serializer.validated_data.get("day")
        if new_day is not None and new_day.pk != old_day_id:
            with transaction.atomic():
                serializer.save(order=new_day.items.count())
                _renumber(ItineraryItem.objects.filter(day_id=old_day_id))
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        item = self.get_object()
        direction = request.data.get("direction")
        if direction not in ("up", "down"):
            return Response({"error": "direction must be up or down"}, status=400)
        moved = reorder_move(item, item.day.items.order_by("order", "id"), direction)
        return Response({"moved": moved})

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Toggle the caller's like. Returns the new state and count."""
        item = self.get_object()
        existing = ItineraryLike.objects.filter(item=item, user=request.user)
        if existing.exists():
            existing.delete()
            liked = False
        else:
            ItineraryLike.objects.create(item=item, user=request.user)
            liked = True
        return Response({"liked": liked, "like_count": item.likes.count()})


class ItineraryLinkViewSet(viewsets.ModelViewSet):
    queryset = ItineraryLink.objects.all()
    serializer_class = ItineraryLinkSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        serializer.save(order=item.links.count())


class ItineraryPhotoViewSet(viewsets.ModelViewSet):
    """No creator lock on delete — like the item it belongs to.

    Sprint 15: `photo` in the request body is the uploaded bytes, not a model
    field write — it goes to Drive via `_attach_drive_photo`, not to disk."""

    queryset = ItineraryPhoto.objects.select_related("uploaded_by").all()
    serializer_class = ItineraryPhotoSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        upload = serializer.validated_data.pop("photo", None)
        # Atomic: a failed Drive upload must leave no trace, not an empty
        # photo row with nothing behind it. Found by the test written for
        # exactly this case — the row was landing in the database before the
        # upload was even attempted.
        with transaction.atomic():
            instance = serializer.save(uploaded_by=self.request.user, order=item.photos.count())
            _attach_drive_photo(instance, upload)

    def perform_destroy(self, instance):
        _detach_drive_photo(instance)
        instance.delete()


class ItineraryCommentViewSet(viewsets.ModelViewSet):
    queryset = ItineraryComment.objects.select_related("author").all()
    serializer_class = ItineraryCommentSerializer
    permission_classes = [IsFamilyMember, IsOwnerOrReadOnly]
    owner_field = "author"

    def get_queryset(self):
        queryset = super().get_queryset()
        item_id = self.request.query_params.get("item")
        return queryset.filter(item_id=item_id) if item_id else queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class ItineraryLikeViewSet(viewsets.ModelViewSet):
    """Full CRUD for Rule 6's sake; the page uses the item's `like` toggle."""

    queryset = ItineraryLike.objects.select_related("user").all()
    serializer_class = ItineraryLikeSerializer
    permission_classes = [IsFamilyMember, IsOwnerOrReadOnly]
    owner_field = "user"

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        like, _ = ItineraryLike.objects.get_or_create(item=item, user=self.request.user)
        serializer.instance = like


class FlightViewSet(viewsets.ModelViewSet):
    """No delete in the UI (there are exactly two, always) but the endpoint
    is real CRUD — nothing stops a genuine cleanup via the browsable API."""

    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        serializer.save(order=trip.flights.count())


class RentalCarViewSet(viewsets.ModelViewSet):
    queryset = RentalCar.objects.all()
    serializer_class = RentalCarSerializer
    permission_classes = [IsFamilyMember]


class LodgingViewSet(viewsets.ModelViewSet):
    """Where we sleep — full CRUD; the UI offers edit (and add, for a stay
    the plan didn't have)."""

    queryset = Lodging.objects.all()
    serializer_class = LodgingSerializer
    permission_classes = [IsFamilyMember]


class TripNoteViewSet(viewsets.ModelViewSet):
    queryset = TripNote.objects.all()
    serializer_class = TripNoteSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        serializer.save(order=trip.notes.count())

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        note = self.get_object()
        direction = request.data.get("direction")
        if direction not in ("up", "down"):
            return Response({"error": "direction must be up or down"}, status=400)
        moved = reorder_move(note, note.trip.notes.order_by("order", "id"), direction)
        return Response({"moved": moved})


class ChecklistGroupViewSet(viewsets.ModelViewSet):
    queryset = ChecklistGroup.objects.prefetch_related("items").all()
    serializer_class = ChecklistGroupSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        serializer.save(order=trip.checklists.count())

    @action(detail=True, methods=["post"])
    def add_items(self, request, pk=None):
        """Body: {"text": "socks\\nshoes\\ncharger"} — one item per line.

        Packing is not one thought at a time: it is standing over a suitcase
        reeling off eight things, or pasting last year's list. One item per
        round trip made that a chore on a phone, which is where this gets
        used. Commas split too, since a typed list tends to come out that way.
        Blank lines and duplicates-in-one-paste are dropped; an item that
        already exists in the list is *not* skipped, because "two chargers"
        is a legitimate thing to pack."""
        group = self.get_object()
        raw = request.data.get("text") or ""
        if isinstance(raw, list):
            parts = [str(p) for p in raw]
        else:
            parts = str(raw).replace(",", "\n").splitlines()
        texts = [p.strip()[:200] for p in parts if p.strip()]
        if not texts:
            return Response({"error": "nothing to add"}, status=400)

        start = group.items.count()
        created = ChecklistItem.objects.bulk_create(
            [ChecklistItem(group=group, text=text, order=start + i) for i, text in enumerate(texts)]
        )
        return Response(ChecklistItemSerializer(created, many=True).data, status=201)


class ChecklistItemViewSet(viewsets.ModelViewSet):
    queryset = ChecklistItem.objects.all()
    serializer_class = ChecklistItemSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        group = serializer.validated_data["group"]
        serializer.save(order=group.items.count())

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        item = self.get_object()
        item.done = not item.done
        item.done_by = request.user if item.done else None
        item.save()
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        item = self.get_object()
        direction = request.data.get("direction")
        if direction not in ("up", "down"):
            return Response({"error": "direction must be up or down"}, status=400)
        moved = reorder_move(item, item.group.items.order_by("order", "id"), direction)
        return Response({"moved": moved})


class JournalPostViewSet(viewsets.ModelViewSet):
    """Spec §4.3. `author` is never client-supplied — always the logged-in
    family member, set here rather than trusted from the request body.

    Sprint 15: same Drive-upload split as `ItineraryPhotoViewSet`, except a
    post can be text-only, so a missing `photo` is not an error here."""

    # `trip` joined too (not just `author`): F11's `day_label` reads
    # `post.trip.timezone`, and without this every post in a list response
    # would fetch its own Trip row fresh — the same class of N+1 F5 fixed
    # on the itinerary endpoints, just on a much smaller table here.
    queryset = JournalPost.objects.select_related("author", "trip").all()
    serializer_class = JournalPostSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        upload = serializer.validated_data.pop("photo", None)
        with transaction.atomic():
            instance = serializer.save(author=self.request.user)
            _attach_drive_photo(instance, upload)

    def perform_destroy(self, instance):
        _detach_drive_photo(instance)
        instance.delete()
