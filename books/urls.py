from django.urls import include, path

from . import auth_views, views
from .api import router

app_name = "books"

urlpatterns = [
    path("", views.home, name="home"),
    path("welcome/", views.onboarding, name="onboarding"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    # Auth, in Books' own look (spec BK1 §1.5).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # The API (Rule 6).
    path("api/", include(router.urls)),
]
