from django.urls import path

from . import auth_views, views

app_name = "crashtech"

urlpatterns = [
    path("", views.home, name="home"),

    # Auth, in CrashTech's own chrome against the shared User table
    # (spec Rule 2.2.2).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # One event. The role-aware home every signed-in person lands on
    # (Rule 11.3). Kept last so it never shadows a named route above.
    path("e/<slug:slug>/", views.event_home, name="event_home"),
]
