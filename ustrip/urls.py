from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

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
router.register(r"checklist-groups", api.ChecklistGroupViewSet, basename="api-checklist-group")
router.register(r"checklist-items", api.ChecklistItemViewSet, basename="api-checklist-item")
router.register(r"journal-posts", api.JournalPostViewSet, basename="api-journal-post")

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.UstripLoginView.as_view(), name="login"),
    path("logout/", views.UstripLogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("itinerary/", views.itinerary_list, name="itinerary_list"),
    path("itinerary/<int:day_id>/", views.itinerary_day, name="itinerary_day"),
    path("itinerary/item/<int:item_id>/", views.itinerary_item_detail, name="itinerary_item_detail"),
    path("itinerary/item/<int:item_id>/edit/", views.itinerary_item_edit, name="itinerary_item_edit"),
    path("flight/<int:flight_id>/edit/", views.flight_edit, name="flight_edit"),
    path("rental-car/<int:rental_car_id>/edit/", views.rental_car_edit, name="rental_car_edit"),
    path("packing/", views.packing, name="packing"),
    path("journal/", views.journal, name="journal"),
    path("api/", include(router.urls)),
]
