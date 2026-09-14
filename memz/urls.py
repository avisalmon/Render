from django.urls import include, path

from . import auth_views, views
from .api import router
from .api.profile import ProfileView
from .api.schema import SchemaView

app_name = "memz"

urlpatterns = [
    path("", views.home, name="home"),
    # SPR-Z.1: honest placeholders until SPR-Z.3 (game) and SPR-Z.2 (creator).
    path("new/", views.coming, name="new"),
    path("join/", views.coming, name="join"),
    path("create/", views.coming, name="create"),
    # Auth, in memz's own chrome (spec §3.3).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # The REST API (building_an_app.md Rule 6; spec §12.3).
    path("api/profile/", ProfileView.as_view(), name="api_profile"),
    path("api/schema/", SchemaView.as_view(), name="api_schema"),
    path("api/", include(router.urls)),
]
