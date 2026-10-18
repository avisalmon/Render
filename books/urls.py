from django.urls import include, path

from . import auth_views, internal, views
from .api import router

app_name = "books"

urlpatterns = [
    path("", views.home, name="home"),
    path("welcome/", views.onboarding, name="onboarding"),
    path("settings/", views.settings_page, name="settings"),
    path("me/data/", views.my_data, name="my_data"),
    path("me/data/export.json", views.my_data_export, name="my_data_export"),
    path("lang/<str:code>/", views.set_language, name="set_language"),
    path("theme/<str:theme>/", views.set_theme, name="set_theme"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    # Staff only, linked from nowhere: every component once (spec BK1 §1.1).
    path("design/", views.design_entry, name="design"),
    # Auth, in Books' own look (spec BK1 §1.5).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # A scheduler's door: re-run dropped background jobs (books/internal.py).
    path("internal/run-jobs/", internal.run_jobs, name="run_jobs"),
    # The API (Rule 6).
    path("api/", include(router.urls)),
]
