from django.urls import path

from . import views

app_name = "ustrip"

urlpatterns = [
    path("", views.home, name="home"),
    path("itinerary/", views.itinerary_list, name="itinerary_list"),
    path("itinerary/<int:day_id>/", views.itinerary_day, name="itinerary_day"),
    path("packing/", views.packing, name="packing"),
    path("journal/", views.journal, name="journal"),
]
