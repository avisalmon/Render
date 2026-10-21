"""Routes for the course site, mounted at /cohort/ (docs/cohort/spec.md)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, views
from .api import ROUTES

app_name = "cohort"

router = DefaultRouter()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.door, name="door"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", auth_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("exhibition/", views.exhibition, name="exhibition"),
    path("exhibition/new/", views.exhibit_new, name="exhibit_new"),
    path("exhibition/<int:pk>/", views.exhibit, name="exhibit"),
    path("exhibition/<int:pk>/edit/", views.exhibit_edit, name="exhibit_edit"),
    path("tracks/", views.tracks, name="tracks"),
    path("tracks/<str:slug>/", views.track, name="track"),
    path("tracks/<str:slug>/edit/", views.track_edit, name="track_edit"),
    path("materials/", views.materials, name="materials"),
    path("examples/t-project/", views.project_example, name="project_example"),
    path("materials/new/", views.material_edit, name="material_new"),
    path("materials/<int:pk>/edit/", views.material_edit, name="material_edit"),
    path("requests/", views.requests_admin, name="requests"),
    path("files/<path:path>", views.private_file, name="file"),
    path("api/", include(router.urls)),
]
