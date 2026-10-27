"""Routes for the BKM gateway, mounted at /bkm/ (docs/bkm/spec.md)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, views
from .api import ROUTES

app_name = "bkm"

router = DefaultRouter()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.wall, name="wall"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", auth_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("projects/", views.projects, name="projects"),
    path("projects/new/", views.project_edit, name="project_new"),
    path("projects/<int:pk>/", views.project_page, name="project"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("api/", include(router.urls)),
    path("new/", views.bkm_edit, name="bkm_new"),
    path("<slug:slug>/", views.bkm_page, name="bkm"),
    path("<slug:slug>/edit/", views.bkm_edit, name="bkm_edit"),
]
