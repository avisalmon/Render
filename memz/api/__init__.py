"""memz's REST API (building_an_app.md Rule 6; spec §12.3).

Full CRUD on every bank resource, one ModelViewSet each, on a router under
/memz/api/. Closed by default (the site's DRF defaults), opened one
resource at a time with owner-scoped querysets (spec §12.3.3).
"""

from rest_framework.routers import DefaultRouter

from .renderers import StaffOnlyBrowsableRenderer
from .viewsets import (
    APIRootView, CaptionCardViewSet, CaptionDeckViewSet, MemeImageViewSet, MemeViewSet, PackImageViewSet,
    PackViewSet, SavedMemeViewSet, TopicViewSet,
)


class MemzRouter(DefaultRouter):
    APIRootView = APIRootView


router = MemzRouter()
router.register(r"images", MemeImageViewSet, basename="api-image")
router.register(r"packs", PackViewSet, basename="api-pack")
router.register(r"pack-images", PackImageViewSet, basename="api-pack-image")
router.register(r"decks", CaptionDeckViewSet, basename="api-deck")
router.register(r"deck-cards", CaptionCardViewSet, basename="api-deck-card")
router.register(r"topics", TopicViewSet, basename="api-topic")
router.register(r"memes", MemeViewSet, basename="api-meme")
router.register(r"saved", SavedMemeViewSet, basename="api-saved")

__all__ = ["router", "StaffOnlyBrowsableRenderer"]
