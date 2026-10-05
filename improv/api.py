"""improv's REST API. Rule 6: every model has an endpoint, documented in docs/improv/api.md.

Reference rows are read-only here and edited in the admin. The tables are a few
dozen rows, so they come back whole rather than paged.

Content a player can own (styles, progressions) is shown as the presets plus the
player's own rows. Presets are read-only; an own row is fully editable; another
player's row does not exist as far as this player can tell.
"""

from django.db.models import Count, Q
from rest_framework import generics, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

from .models import ChordQuality, ChordScale, Progression, Scale, Style, Tag
from .access import profile_for
from .permissions import IsPlayer
from .serializers import (
    ChordQualitySerializer,
    ChordScaleSerializer,
    PlayerSerializer,
    ProgressionSerializer,
    ScaleSerializer,
    StyleSerializer,
    TagSerializer,
)
from .slugs import unique_slug


class ReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlayer]
    pagination_class = None


class ChordQualityViewSet(ReferenceViewSet):
    queryset = ChordQuality.objects.prefetch_related("chord_scales__scale")
    serializer_class = ChordQualitySerializer


class ScaleViewSet(ReferenceViewSet):
    queryset = Scale.objects.select_related("parent_scale")
    serializer_class = ScaleSerializer


class ChordScaleViewSet(ReferenceViewSet):
    queryset = ChordScale.objects.select_related("chord_quality", "scale")
    serializer_class = ChordScaleSerializer

    def get_queryset(self):
        rows = super().get_queryset()
        quality = self.request.query_params.get("quality")
        scale = self.request.query_params.get("scale")
        if quality:
            rows = rows.filter(chord_quality__symbol=quality)
        if scale:
            rows = rows.filter(scale__slug=scale)
        return rows


class TagViewSet(ReferenceViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_queryset(self):
        mine = Q(progressions__is_preset=True) | Q(progressions__owner=self.request.user)
        return Tag.objects.annotate(progression_count=Count("progressions", filter=mine, distinct=True))


class OwnedViewSet(viewsets.ModelViewSet):
    """Presets plus my own rows. A subclass names the model's queryset, the field the
    slug is made from, and the filters its screens need."""

    permission_classes = [IsPlayer]
    pagination_class = None
    slug_source = "name"

    def get_queryset(self):
        user = self.request.user
        rows = super().get_queryset().filter(Q(is_preset=True) | Q(owner=user))
        params = self.request.query_params
        if params.get("mine"):
            rows = rows.filter(owner=user)
        if params.get("genre"):
            rows = rows.filter(genre=params["genre"])
        return self.filter_more(rows, params).distinct()

    def filter_more(self, rows, params):
        return rows

    def get_object(self):
        row = super().get_object()
        if self.request.method not in SAFE_METHODS and (row.is_preset or row.owner_id != self.request.user.pk):
            raise PermissionDenied("Presets are read-only here. They are edited in the admin.")
        return row

    def perform_create(self, serializer):
        slug = unique_slug(self.queryset.model, serializer.validated_data.get(self.slug_source, ""))
        serializer.save(owner=self.request.user, is_preset=False, slug=slug)


class StyleViewSet(OwnedViewSet):
    queryset = Style.objects.all()
    serializer_class = StyleSerializer
    slug_source = "name"

    def filter_more(self, rows, params):
        return rows.filter(feel=params["feel"]) if params.get("feel") else rows


class ProgressionViewSet(OwnedViewSet):
    queryset = Progression.objects.prefetch_related("tags")
    serializer_class = ProgressionSerializer
    slug_source = "title"

    def filter_more(self, rows, params):
        if params.get("tag"):
            rows = rows.filter(tags__slug=params["tag"])
        if params.get("difficulty"):
            try:
                rows = rows.filter(difficulty=int(params["difficulty"]))
            except ValueError:
                rows = rows.none()
        if params.get("q"):
            rows = rows.filter(Q(title__icontains=params["q"]) | Q(description__icontains=params["q"]))
        return rows


class PlayerView(generics.RetrieveUpdateAPIView):
    """The person's own profile: one row, reached without an id.

    A singleton on purpose, and the documented shape in docs/improv/api.md. There is
    exactly one profile per person, made on their first visit, so there is nothing to
    create and nothing to list; an id in the route would only invite asking for
    somebody else's row, which this app will not answer. Delete is absent too: it
    would throw away the calibration that makes timing mean anything.
    """

    serializer_class = PlayerSerializer
    permission_classes = [IsPlayer]

    def get_object(self):
        return profile_for(self.request.user)


REFERENCE_ENDPOINTS = {
    "chord-qualities": ChordQualityViewSet,
    "scales": ScaleViewSet,
    "chord-scales": ChordScaleViewSet,
    "tags": TagViewSet,
}
OWNED_ENDPOINTS = {
    "styles": StyleViewSet,
    "progressions": ProgressionViewSet,
}
# Not a router endpoint: see PlayerView.
SINGLETONS = {"player": PlayerView}
ENDPOINTS = {**REFERENCE_ENDPOINTS, **OWNED_ENDPOINTS}
