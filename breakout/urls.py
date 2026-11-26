"""Routes for breakout, mounted at /breakout/ (docs/breakout/spec.md)."""

from django.urls import include, path
from rest_framework import routers

from . import auth_views, views
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
    path("x/<slug:slug>/", views.experience, name="experience"),
]
