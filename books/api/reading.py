"""Reading in the API (Rule 6): my sessions and my notes on a book. Every
change goes through books/reading.py and books/notes.py."""

from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .. import notes, reading
from ..access import profile_for
from ..models import CatalogEntry, ReadingNote, ReadingSession
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


class ReadingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingSession
        fields = ["id", "entry", "copy", "started_at", "ended_at", "start_page", "end_page", "seconds",
                  "finished_book"]
        read_only_fields = fields


class ReadingSessionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """My sittings. POST `start` {entry, page, total_pages (optional, fills
    an empty catalogue count)}; POST `{id}/end` {end_page, finished,
    total_pages}; POST `{id}/discard`."""

    serializer_class = ReadingSessionSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return ReadingSession.objects.filter(profile=_me(self.request))

    @action(detail=False, methods=["post"])
    def start(self, request):
        entry = CatalogEntry.objects.filter(pk=request.data.get("entry") or 0).first()
        if entry is None:
            raise ValidationError({"entry": "required"})
        if request.data.get("total_pages"):
            reading.set_pages(entry, request.data["total_pages"])
        try:
            s = reading.start(_me(request), entry, request.data.get("page"))
        except (reading.ReadingError, ValueError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ReadingSessionSerializer(s).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        s = self.get_object()
        if request.data.get("total_pages"):
            reading.set_pages(s.entry, request.data["total_pages"], at_least=s.start_page)
        try:
            s = reading.end(_me(request), s, request.data.get("end_page"),
                            str(request.data.get("finished")).lower() in ("1", "true"))
        except (reading.ReadingError, ValueError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ReadingSessionSerializer(s).data)

    @action(detail=True, methods=["post"])
    def discard(self, request, pk=None):
        reading.discard(_me(request), self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingNote
        fields = ["id", "entry", "session", "page", "body", "source", "created_at", "updated_at"]
        read_only_fields = ["session", "created_at", "updated_at"]


class ReadingNoteViewSet(viewsets.ModelViewSet):
    """My notes on books, oldest first; `?entry=` for one book. POST `voice`
    (multipart: audio, seconds) returns the words to save as a note."""

    serializer_class = ReadingNoteSerializer
    permission_classes = [HasBooksProfile]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        qs = ReadingNote.objects.filter(profile=_me(self.request))
        if self.request.query_params.get("entry"):
            qs = qs.filter(entry_id=self.request.query_params["entry"])
        return qs

    def perform_create(self, serializer):
        d = serializer.validated_data
        try:
            serializer.instance = notes.add(_me(self.request), d["entry"], d.get("body"), d.get("source", "typed"),
                                            session=reading.active(_me(self.request)), page=d.get("page"))
        except notes.NoteError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def perform_update(self, serializer):
        try:
            notes.edit(_me(self.request), serializer.instance, serializer.validated_data.get(
                "body", serializer.instance.body))
        except notes.NoteError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def perform_destroy(self, instance):
        notes.remove(_me(self.request), instance)

    @action(detail=False, methods=["post"])
    def voice(self, request):
        try:
            text = notes.transcribe(_me(request), request.FILES.get("audio"), request.data.get("seconds"))
        except notes.NoteError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response({"text": text})
