from rest_framework.routers import DefaultRouter

from .circles import CircleMemberViewSet, CircleViewSet, FeedbackViewSet, PilotViewSet
from .community import PeopleViewSet, PostViewSet, ReadingLogViewSet, ReviewViewSet, ThreadViewSet
from .discover import DiscoverViewSet
from .hub import (
                  BlockViewSet,
                  DealViewSet,
                  MeetingPlaceViewSet,
                  MessageViewSet,
                  NearViewSet,
                  NotificationViewSet,
                  ReportViewSet,
                  TransferViewSet,
)
from .museum import ExhibitItemViewSet, ExhibitViewSet, RareReviewViewSet
from .plans import PlanViewSet
from .play import BadgeViewSet, CheckinViewSet, PlayViewSet, PointEventViewSet
from .reading import ReadingNoteViewSet, ReadingSessionViewSet
from .viewsets import (
                  BookDetailViewSet,
                  CatalogEntryViewSet,
                  CopyPhotoViewSet,
                  CopyViewSet,
                  CreatorAliasViewSet,
                  CreatorViewSet,
                  EntryCorrectionViewSet,
                  EntryIdentifierViewSet,
                  OfferViewSet,
                  ProfileViewSet,
                  ScanItemViewSet,
                  ShelfScanViewSet,
                  TagViewSet,
                  WishViewSet,
)

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
router.register("circles", CircleViewSet, basename="circle")
router.register("circle-members", CircleMemberViewSet, basename="circle-member")
router.register("feedback", FeedbackViewSet, basename="feedback")
router.register("pilot", PilotViewSet, basename="pilot")
router.register("threads", ThreadViewSet, basename="thread")
router.register("posts", PostViewSet, basename="post")
router.register("reviews", ReviewViewSet, basename="review")
router.register("reading", ReadingLogViewSet, basename="reading")
router.register("people", PeopleViewSet, basename="people")
router.register("checkins", CheckinViewSet, basename="checkin")
router.register("sessions", ReadingSessionViewSet, basename="session")
router.register("notes", ReadingNoteViewSet, basename="note")
router.register("points", PointEventViewSet, basename="point")
router.register("badges", BadgeViewSet, basename="badge")
router.register("play", PlayViewSet, basename="play")
router.register("discover", DiscoverViewSet, basename="discover")
router.register("rare-reviews", RareReviewViewSet, basename="rare-review")
router.register("exhibits", ExhibitViewSet, basename="exhibit")
router.register("exhibit-items", ExhibitItemViewSet, basename="exhibit-item")
router.register("plan", PlanViewSet, basename="plan")
