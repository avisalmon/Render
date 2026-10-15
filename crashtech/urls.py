from django.urls import path

from . import auth_views, views

app_name = "crashtech"

urlpatterns = [
    path("", views.home, name="home"),
    # `create/` rather than `new/`: the 2026 platform still owns
    # /crashtech/new/ and keeps working until C.8 retires it (Rule 13.3).
    # Shadowing it here broke two of its tests, which is exactly what the
    # fall-through mounting was chosen to avoid.
    path("create/", views.event_create, name="event_create"),

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

    # Rule 4.3: the link in a role invitation, which works whether or not
    # the person already has an account.
    path("invite/<str:token>/", views.accept_invitation, name="accept_invitation"),

    # One event. Kept last so these never shadow a named route above.
    path("e/<slug:slug>/", views.event_home, name="event_home"),
    path("e/<slug:slug>/settings/", views.event_settings, name="settings"),
    path("e/<slug:slug>/milestones/", views.event_milestones, name="milestones"),
    path("e/<slug:slug>/people/", views.event_people, name="people"),
    path("e/<slug:slug>/readiness/", views.event_readiness, name="readiness"),
    path("e/<slug:slug>/advance/", views.event_advance, name="advance"),
    path("e/<slug:slug>/apply/", views.event_apply, name="apply"),
    path("e/<slug:slug>/registrations/", views.event_registrations, name="registrations"),
    path("e/<slug:slug>/teams/", views.event_teams, name="teams"),
    path("e/<slug:slug>/kit/", views.event_kit, name="kit"),
    # The one event screen an admin owns: a queue of people, a box of
    # boards, five seconds each (Rule 6.4).
    path("e/<slug:slug>/kit-desk/", views.event_kit_desk, name="kit_desk"),
]
