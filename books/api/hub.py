"""The hub's API (BK5, Rule 6). Every state change goes through books/hub.py,
the same functions the pages use, so the API can never skip a rule the
screens keep. Querysets scope to the caller: nobody reads a deal, message,
notification or block they are not part of."""

from django.db.models import Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import hub
from ..access import profile_for
from ..models import Block, Copy, CopyTransfer, Deal, MeetingPlace, Message, Notification, Profile, Report
from .permissions import HasBooksProfile, StaffWrite


def _me(request):
    return profile_for(request.user)


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


# ---- serializers -----------------------------------------------------------------------------

class MeetingPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingPlace
        fields = ["id", "name", "kind", "area_name", "lat", "lng", "is_partner", "notes", "is_active"]


class DealSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="copy.entry.title", read_only=True)
    message = serializers.CharField(write_only=True, required=False, allow_blank=True)
    contact = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = ["id", "copy", "title", "kind", "status", "owner", "requester", "swap_copy", "loan_days",
                  "price_amount", "due_date", "meeting_place", "meeting_note", "owner_confirmed_handover_at",
                  "requester_confirmed_handover_at", "requester_marked_returned_at", "returned_confirmed_at",
                  "returned_late", "owner_shares", "requester_shares", "closed_note", "created_at", "updated_at",
                  "message", "contact"]
        read_only_fields = [f for f in fields if f not in ("copy", "kind", "swap_copy", "message")]

    def get_contact(self, deal):
        request = self.context.get("request")
        return hub.contact_for(deal, _me(request)) if request else {}


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "deal", "sender", "body", "created_at", "read_at"]
        read_only_fields = ["sender", "created_at", "read_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "deal", "entry", "copy", "read_at", "created_at"]
        read_only_fields = ["kind", "deal", "entry", "copy", "created_at"]


class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ["id", "blocked", "created_at"]
        read_only_fields = ["created_at"]


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "copy", "profile", "deal", "reason", "status", "created_at"]
        read_only_fields = ["status", "created_at"]


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopyTransfer
        fields = ["id", "copy", "from_profile", "to_profile", "deal", "kind", "transferred_at"]


# ---- viewsets ----------------------------------------------------------------------------------

class NearViewSet(viewsets.ViewSet):
    """GET /near/?kind=&q=&tag=&language= : offered books within the radius.
    A neighbourhood and a rounded distance, never an owner's point."""

    permission_classes = [HasBooksProfile]

    def list(self, request):
        rows = hub.offered_copies(_me(request), kind=request.query_params.get("kind") or None,
                                  q=request.query_params.get("q"), tag=request.query_params.get("tag") or None,
                                  language=request.query_params.get("language") or None)
        return Response([{
            "copy": c.pk, "entry": c.entry_id, "title": c.entry.title, "creators": c.entry.creator_names,
            "area_name": c.owner.area_name, "km": round(km) if km is not None else None,
            "offers": [{"kind": o.kind, "loan_days": o.loan_days, "price_amount": o.price_amount,
                        "wants_note": o.wants_note} for o in c.offers.all() if o.is_active],
        } for c, km in rows])


class DealViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Create = ask (copy, kind, message, swap_copy). Delete = cancel; a deal
    is history and is never erased. Every other step is an action."""

    serializer_class = DealSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        return Deal.objects.filter(Q(owner=me) | Q(requester=me)).select_related("copy__entry")

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            deal = hub.ask(_me(request), d["copy"], d["kind"], d.get("message", ""), swap_copy=d.get("swap_copy"))
        except hub.DealError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(deal).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        deal = self.get_object()
        try:
            hub.cancel(deal, _me(request), request.data.get("note", "") if hasattr(request, "data") else "")
        except hub.DealError as exc:
            return _conflict(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _step(self, request, fn, *args):
        deal = self.get_object()
        try:
            fn(deal, _me(request), *args)
        except hub.DealError as exc:
            return _conflict(exc)
        deal.refresh_from_db()
        return Response(self.get_serializer(deal).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._step(request, hub.approve)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._step(request, hub.decline)

    @action(detail=True, methods=["post"])
    def handover(self, request, pk=None):
        return self._step(request, hub.confirm_handover)

    @action(detail=True, methods=["post"])
    def returned(self, request, pk=None):
        return self._step(request, hub.mark_returned)

    @action(detail=True, methods=["post"], url_path="got-back")
    def got_back(self, request, pk=None):
        return self._step(request, hub.confirm_returned)

    @action(detail=True, methods=["post"])
    def dispute(self, request, pk=None):
        return self._step(request, hub.dispute, request.data.get("note", ""))

    @action(detail=True, methods=["post"])
    def meeting(self, request, pk=None):
        place = MeetingPlace.objects.filter(pk=request.data.get("meeting_place") or 0, is_active=True).first()
        return self._step(request, hub.set_meeting, place, request.data.get("meeting_note", ""))

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        ways = request.data.get("ways") or []
        if isinstance(ways, str):
            ways = [w for w in ways.split(",") if w]
        return self._step(request, hub.set_shares, ways)


class MessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    """Messages are the record between two people: written, read, never
    edited or deleted by one side alone."""

    serializer_class = MessageSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        qs = Message.objects.filter(Q(deal__owner=me) | Q(deal__requester=me))
        if self.request.query_params.get("deal"):
            qs = qs.filter(deal_id=self.request.query_params["deal"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        me = _me(request)
        deal = ser.validated_data["deal"]
        if deal.role(me) is None:
            raise ValidationError({"deal": "not yours"})
        try:
            msg = hub.send_message(deal, me, ser.validated_data["body"])
        except hub.DealError as exc:
            return _conflict(exc)
        return Response(self.get_serializer(msg).data, status=status.HTTP_201_CREATED)


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """The app sends these itself; a person reads, marks and clears them."""

    serializer_class = NotificationSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Notification.objects.filter(profile=_me(self.request))

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        from django.utils import timezone

        n = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"read": n})


class BlockViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = BlockSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Block.objects.filter(blocker=_me(self.request))

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        me = _me(request)
        try:
            hub.block(me, ser.validated_data["blocked"])
        except hub.DealError as exc:
            return _conflict(exc)
        row = Block.objects.get(blocker=me, blocked=ser.validated_data["blocked"])
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)


class ReportViewSet(viewsets.ModelViewSet):
    """Anyone onboarded files a report and sees their own; staff see all and
    set the status."""

    serializer_class = ReportSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Report.objects.all()
        return Report.objects.filter(reporter=_me(self.request))

    def perform_create(self, serializer):
        me = _me(self.request)
        d = serializer.validated_data
        if not (d.get("copy") or d.get("profile") or d.get("deal")):
            raise ValidationError({"detail": "a copy, a person or a deal"})
        if d.get("deal") is not None and d["deal"].role(me) is None:
            raise ValidationError({"deal": "not yours"})
        serializer.save(reporter=me)

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise ValidationError({"detail": "staff only"})
        status_value = self.request.data.get("status")
        if status_value in (Report.OPEN, Report.HANDLED):
            serializer.save(status=status_value, handled_by=_me(self.request))
        else:
            serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise ValidationError({"detail": "staff only"})
        instance.delete()


class MeetingPlaceViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingPlaceSerializer
    permission_classes = [StaffWrite]
    queryset = MeetingPlace.objects.all()


class TransferViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read only: a transfer is written once, by a completed deal."""

    serializer_class = TransferSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        me = _me(self.request)
        return CopyTransfer.objects.filter(Q(from_profile=me) | Q(to_profile=me))
