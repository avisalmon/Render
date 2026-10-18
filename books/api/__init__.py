from rest_framework.routers import DefaultRouter

from .viewsets import (BookDetailViewSet, CatalogEntryViewSet, CreatorAliasViewSet, CreatorViewSet,
                       EntryCorrectionViewSet, EntryIdentifierViewSet, ProfileViewSet, TagViewSet)

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("catalog", CatalogEntryViewSet, basename="catalog")
router.register("creators", CreatorViewSet, basename="creator")
router.register("creator-aliases", CreatorAliasViewSet, basename="creator-alias")
router.register("tags", TagViewSet, basename="tag")
router.register("identifiers", EntryIdentifierViewSet, basename="identifier")
router.register("book-details", BookDetailViewSet, basename="book-detail")
router.register("corrections", EntryCorrectionViewSet, basename="correction")
