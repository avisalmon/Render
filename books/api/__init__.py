from rest_framework.routers import DefaultRouter

from .hub import (BlockViewSet, DealViewSet, MeetingPlaceViewSet, MessageViewSet, NearViewSet,
                  NotificationViewSet, ReportViewSet, TransferViewSet)
from .viewsets import (BookDetailViewSet, CatalogEntryViewSet, CopyPhotoViewSet, CopyViewSet, CreatorAliasViewSet,
                       CreatorViewSet, EntryCorrectionViewSet, EntryIdentifierViewSet, OfferViewSet, ProfileViewSet,
                       ScanItemViewSet, ShelfScanViewSet, TagViewSet, WishViewSet)

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("catalog", CatalogEntryViewSet, basename="catalog")
router.register("creators", CreatorViewSet, basename="creator")
router.register("creator-aliases", CreatorAliasViewSet, basename="creator-alias")
router.register("tags", TagViewSet, basename="tag")
router.register("identifiers", EntryIdentifierViewSet, basename="identifier")
router.register("book-details", BookDetailViewSet, basename="book-detail")
router.register("corrections", EntryCorrectionViewSet, basename="correction")
router.register("scans", ShelfScanViewSet, basename="scan")
router.register("scan-items", ScanItemViewSet, basename="scan-item")
router.register("copies", CopyViewSet, basename="copy")
router.register("offers", OfferViewSet, basename="offer")
router.register("copy-photos", CopyPhotoViewSet, basename="copy-photo")
router.register("wishes", WishViewSet, basename="wish")
router.register("near", NearViewSet, basename="near")
router.register("deals", DealViewSet, basename="deal")
router.register("messages", MessageViewSet, basename="message")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("blocks", BlockViewSet, basename="block")
router.register("reports", ReportViewSet, basename="report")
router.register("meeting-places", MeetingPlaceViewSet, basename="meeting-place")
router.register("transfers", TransferViewSet, basename="transfer")
