"""The owner side of the API: full CRUD on every model (Rule 6), owner-scoped.
Public, key-based endpoints (hit, stats, promo) live in public.py."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import stats
from ..access import sites_for
from ..models import Event, Page, Promo, PromoPlacement
from .permissions import IsCounterOwner
from .serializers import (EventSerializer, PageSerializer, PromoPlacementSerializer, PromoSerializer,
                          SiteSerializer)


class _Owned:
    permission_classes = [IsCounterOwner]

    def _own_site(self, site):
        if site is None or not sites_for(self.request.user).filter(pk=site.pk).exists():
            raise ValidationError({"site": "Not one of your sites."})


class _SiteChild(_Owned):
    """A model that belongs to a site: scoped to the caller's sites, and the
    site on a write must be one of theirs."""

    model = None

    def get_queryset(self):
        qs = self.model.objects.filter(site__in=sites_for(self.request.user))
        site = self.request.query_params.get("site")
        return qs.filter(site_id=site) if site else qs

    def perform_create(self, serializer):
        self._own_site(serializer.validated_data.get("site"))
        serializer.save()

    def perform_update(self, serializer):
        self._own_site(serializer.validated_data.get("site", serializer.instance.site))
        serializer.save()


class SiteViewSet(_Owned, viewsets.ModelViewSet):
    serializer_class = SiteSerializer

    def get_queryset(self):
        return sites_for(self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        try:
            days = max(1, min(int(request.query_params.get("days", 30)), 365))
        except ValueError:
            days = 30
        return Response(stats.summary(self.get_object(), days=days))


class PageViewSet(_SiteChild, viewsets.ModelViewSet):
    serializer_class = PageSerializer
    model = Page


class EventViewSet(_SiteChild, viewsets.ModelViewSet):
    serializer_class = EventSerializer
    model = Event


class PromoViewSet(_Owned, viewsets.ModelViewSet):
    serializer_class = PromoSerializer

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Promo.objects.none()
        return Promo.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class PromoPlacementViewSet(_Owned, viewsets.ModelViewSet):
    serializer_class = PromoPlacementSerializer

    def get_queryset(self):
        return PromoPlacement.objects.filter(site__in=sites_for(self.request.user))

    def _check(self, serializer):
        inst = serializer.instance
        self._own_site(serializer.validated_data.get("site", getattr(inst, "site", None)))
        promo = serializer.validated_data.get("promo", getattr(inst, "promo", None))
        if promo is None or promo.owner_id != self.request.user.id:
            raise ValidationError({"promo": "Not one of your promos."})

    def perform_create(self, serializer):
        self._check(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check(serializer)
        serializer.save()
