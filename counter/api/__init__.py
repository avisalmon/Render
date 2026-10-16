from rest_framework.routers import DefaultRouter

from .viewsets import EventViewSet, PageViewSet, PromoPlacementViewSet, PromoViewSet, SiteViewSet

router = DefaultRouter()
router.register("sites", SiteViewSet, basename="site")
router.register("pages", PageViewSet, basename="page")
router.register("events", EventViewSet, basename="event")
router.register("promos", PromoViewSet, basename="promo")
router.register("placements", PromoPlacementViewSet, basename="placement")
