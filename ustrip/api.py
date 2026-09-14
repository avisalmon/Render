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

from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryComment, ItineraryDay, ItineraryItem, ItineraryLike,
    ItineraryLink, ItineraryPhoto, JournalPost, RentalCar, Trip,
)
from .permissions import IsFamilyMember, IsOwnerOrReadOnly
from .reorder import move as reorder_move
from .serializers import (
    ChecklistGroupSerializer, ChecklistItemSerializer, FlightSerializer, ItineraryCommentSerializer,
    ItineraryDaySerializer, ItineraryItemSerializer, ItineraryLikeSerializer, ItineraryLinkSerializer,
    ItineraryPhotoSerializer, JournalPostSerializer, RentalCarSerializer, TripSerializer,
)


def _renumber(queryset):
    """Close the gaps after items leave a day: 0, 1, 2, ... in current order."""
    for index, row in enumerate(queryset.order_by("order", "id")):
        if row.order != index:
            row.order = index
            row.save(update_fields=["order"])


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsFamilyMember]


class ItineraryDayViewSet(viewsets.ModelViewSet):
    queryset = ItineraryDay.objects.prefetch_related("items").all()
    serializer_class = ItineraryDaySerializer
    permission_classes = [IsFamilyMember]

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
    """No creator lock on delete — like the item it belongs to."""

    queryset = ItineraryPhoto.objects.select_related("uploaded_by").all()
    serializer_class = ItineraryPhotoSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        item = serializer.validated_data["item"]
        serializer.save(uploaded_by=self.request.user, order=item.photos.count())


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


class ChecklistGroupViewSet(viewsets.ModelViewSet):
    queryset = ChecklistGroup.objects.prefetch_related("items").all()
    serializer_class = ChecklistGroupSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        serializer.save(order=trip.checklists.count())


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
    family member, set here rather than trusted from the request body."""

    queryset = JournalPost.objects.select_related("author").all()
    serializer_class = JournalPostSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
