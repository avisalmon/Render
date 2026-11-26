"""Routes for breakout, mounted at /breakout/ (docs/breakout/spec.md)."""

from django.urls import include, path
from rest_framework import routers

from . import auth_views, edit_views, views
from .api import ROUTES

app_name = "breakout"

router = routers.DefaultRouter()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", auth_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("files/<int:pk>/", views.printable_file, name="printable_file"),
    path("api/", include(router.urls)),
    path("new/", edit_views.new, name="new"),
    path("x/<slug:slug>/", views.experience, name="experience"),
    path("x/<slug:slug>/kit/", views.kit_pdf, name="kit"),
    path("x/<slug:slug>/cover/", edit_views.cover_file, name="cover_file"),
    # The editor (spec 5): the author's screens.
    path("x/<slug:slug>/edit/", edit_views.hub, name="edit"),
    path("x/<slug:slug>/edit/about/", edit_views.about, name="edit_about"),
    path("x/<slug:slug>/edit/story/", edit_views.story, name="edit_story"),
    path("x/<slug:slug>/edit/stations/", edit_views.stations, name="edit_stations"),
    path("x/<slug:slug>/edit/stations/<int:pk>/", edit_views.station, name="edit_station"),
    path("x/<slug:slug>/edit/stations/<int:pk>/move/", edit_views.station_move, name="station_move"),
    path("x/<slug:slug>/edit/stations/<int:pk>/delete/", edit_views.station_delete, name="station_delete"),
    path("x/<slug:slug>/edit/stations/<int:pk>/hints/", edit_views.hint_add, name="hint_add"),
    path("x/<slug:slug>/edit/stations/<int:pk>/hints/<int:hint_pk>/move/", edit_views.hint_move, name="hint_move"),
    path("x/<slug:slug>/edit/stations/<int:pk>/hints/<int:hint_pk>/delete/", edit_views.hint_delete, name="hint_delete"),
    path("x/<slug:slug>/edit/stations/<int:pk>/materials/", edit_views.material_add, name="material_add"),
    path("x/<slug:slug>/edit/stations/<int:pk>/materials/<int:use_pk>/delete/", edit_views.material_delete, name="material_delete"),
    path("x/<slug:slug>/edit/stations/<int:pk>/materials/request/", edit_views.material_request, name="material_request"),
    path("x/<slug:slug>/edit/stations/<int:pk>/printables/", edit_views.printable_add, name="printable_add"),
    path("x/<slug:slug>/edit/stations/<int:pk>/printables/<int:printable_pk>/delete/", edit_views.printable_delete, name="printable_delete"),
    path("x/<slug:slug>/edit/lock/", edit_views.lock, name="edit_lock"),
    path("x/<slug:slug>/edit/publish/", edit_views.publish, name="publish"),
    path("x/<slug:slug>/edit/unpublish/", edit_views.unpublish, name="unpublish"),
    path("x/<slug:slug>/edit/delete/", edit_views.delete, name="delete"),
]
