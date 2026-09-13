"""The REST API (spec/methodology Rule 6): full CRUD, one ModelViewSet per
model, registered on a router under /ustrip/api/... . Pages consume this
API with fetch() (static/ustrip/ustrip.js) instead of a separate hand-rolled
JSON layer — this *is* the infrastructure now, not an add-on for the
screens that happened to need one.

Every viewset shares one permission: IsFamilyMember (spec §3). `move` is a
custom action on the two viewsets with a real ordering — reordering isn't
one of the four CRUD verbs, so it doesn't belong on create/update.
"""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, RentalCar, Trip
from .permissions import IsFamilyMember
from .reorder import move as reorder_move
from .serializers import (
    ChecklistGroupSerializer, ChecklistItemSerializer, FlightSerializer, ItineraryDaySerializer,
    ItineraryItemSerializer, JournalPostSerializer, RentalCarSerializer, TripSerializer,
)


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsFamilyMember]


class ItineraryDayViewSet(viewsets.ModelViewSet):
    queryset = ItineraryDay.objects.prefetch_related("items").all()
    serializer_class = ItineraryDaySerializer
    permission_classes = [IsFamilyMember]


class ItineraryItemViewSet(viewsets.ModelViewSet):
    """Spec §4.1: any family member can add/edit/delete/reorder — no
    creator-only lock."""

    queryset = ItineraryItem.objects.all()
    serializer_class = ItineraryItemSerializer
    permission_classes = [IsFamilyMember]

    def perform_create(self, serializer):
        day = serializer.validated_data["day"]
        serializer.save(order=day.items.count())

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        item = self.get_object()
        direction = request.data.get("direction")
        if direction not in ("up", "down"):
            return Response({"error": "direction must be up or down"}, status=400)
        moved = reorder_move(item, item.day.items.order_by("order", "id"), direction)
        return Response({"moved": moved})


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
