"""improv's REST API. Rule 6: every model has an endpoint, documented in docs/improv/api.md.

Reference rows are read-only here and edited in the admin. The tables are a few
dozen rows, so they come back whole rather than paged.
"""

from rest_framework import viewsets

from .models import ChordQuality, ChordScale, Scale
from .permissions import IsPlayer
from .serializers import ChordQualitySerializer, ChordScaleSerializer, ScaleSerializer


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


ENDPOINTS = {
    "chord-qualities": ChordQualityViewSet,
    "scales": ScaleViewSet,
    "chord-scales": ChordScaleViewSet,
}
