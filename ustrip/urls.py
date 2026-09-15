from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, family_api, views

app_name = "ustrip"

# The REST API (spec/methodology Rule 6) — full CRUD per model, one
# ModelViewSet each. Pages call these with fetch(); see static/ustrip/ustrip.js.
router = DefaultRouter()
router.register(r"trips", api.TripViewSet, basename="api-trip")
router.register(r"itinerary-days", api.ItineraryDayViewSet, basename="api-itinerary-day")
router.register(r"itinerary-items", api.ItineraryItemViewSet, basename="api-itinerary-item")
router.register(r"itinerary-links", api.ItineraryLinkViewSet, basename="api-itinerary-link")
router.register(r"itinerary-photos", api.ItineraryPhotoViewSet, basename="api-itinerary-photo")
router.register(r"itinerary-comments", api.ItineraryCommentViewSet, basename="api-itinerary-comment")
router.register(r"itinerary-likes", api.ItineraryLikeViewSet, basename="api-itinerary-like")
router.register(r"flights", api.FlightViewSet, basename="api-flight")
router.register(r"rental-cars", api.RentalCarViewSet, basename="api-rental-car")
router.register(r"lodgings", api.LodgingViewSet, basename="api-lodging")
router.register(r"trip-notes", api.TripNoteViewSet, basename="api-trip-note")
router.register(r"checklist-groups", api.ChecklistGroupViewSet, basename="api-checklist-group")
router.register(r"checklist-items", api.ChecklistItemViewSet, basename="api-checklist-item")
router.register(r"journal-posts", api.JournalPostViewSet, basename="api-journal-post")

urlpatterns = [
    path("", views.home, name="home"),
    # Offline (spec §0a.2). Open by design — see the note in views.py.
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
    path("login/", views.UstripLoginView.as_view(), name="login"),
    path("logout/", views.UstripLogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("itinerary/", views.itinerary_list, name="itinerary_list"),
    path("itinerary/<int:day_id>/", views.itinerary_day, name="itinerary_day"),
    path("itinerary/item/<int:item_id>/", views.itinerary_item_detail, name="itinerary_item_detail"),
    path("itinerary/item/<int:item_id>/edit/", views.itinerary_item_edit, name="itinerary_item_edit"),
    path("flight/<int:flight_id>/edit/", views.flight_edit, name="flight_edit"),
    path("rental-car/<int:rental_car_id>/edit/", views.rental_car_edit, name="rental_car_edit"),
    path("lodging/new/", views.lodging_edit, name="lodging_new"),
    path("lodging/<int:lodging_id>/edit/", views.lodging_edit, name="lodging_edit"),
    path("packing/", views.packing, name="packing"),
    path("journal/", views.journal, name="journal"),
    # Photo bytes, proxied from Drive (Sprint 15) — see the note in views.py
    # for why these are never a raw Drive URL in an <img src>.
    path("itinerary/photo/<int:pk>/file/", views.item_photo_file, name="item_photo_file"),
    path("journal/photo/<int:pk>/file/", views.journal_photo_file, name="journal_photo_file"),
    # Who is in the family (spec §3). Token-or-superuser, not the family gate:
    # this is how access is granted, so it cannot require access.
    path("api/family/", family_api.FamilyView.as_view(), name="api_family"),
    path("api/", include(router.urls)),
]
