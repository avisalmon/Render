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

    path("e/<slug:slug>/challenges/", views.event_challenges, name="challenges"),
    path("e/<slug:slug>/challenges/new/", views.challenge_edit, name="challenge_new"),
    path("e/<slug:slug>/challenges/<int:pk>/edit/", views.challenge_edit, name="challenge_edit"),
    # A separate route from the editor on purpose: the point is to look at
    # the participant's screen, not at a rendering of the editor.
    path("e/<slug:slug>/challenges/<int:pk>/preview/", views.challenge_preview, name="challenge_preview"),
    path("e/<slug:slug>/challenges/<int:pk>/submit/", views.challenge_submit, name="challenge_submit"),
    path("e/<slug:slug>/standings/", views.event_standings, name="standings"),

    path("e/<slug:slug>/judging/", views.event_judging, name="judging"),
    path("e/<slug:slug>/judging/<int:pk>/shortlist/", views.challenge_shortlist, name="shortlist"),
    path("e/<slug:slug>/judging/entry/<int:pk>/", views.submission_grade, name="grade"),
    path("e/<slug:slug>/verify/", views.event_verify, name="verify"),
    path("e/<slug:slug>/publish/", views.event_publish, name="publish"),

    # Rule 9.2: reading the museum needs no account, which is why it is not
    # behind @signed_in and why it is worth saying so here too.
    path("e/<slug:slug>/museum/", views.event_museum, name="museum"),
    path("e/<slug:slug>/museum/edit/", views.event_museum_edit, name="museum_edit"),
    path("e/<slug:slug>/consent/", views.team_consent, name="consent"),
]

urlpatterns += [
    path("museum/", views.museum_index, name="museum_index"),
]

# Public and permanent, with no account behind it (Rule 8.6): the person
# who needs to open this is a recruiter following a link on a CV two years
# later, and an account wall is how they decide it is not worth it.
urlpatterns += [
    path("c/<uuid:cert_id>/", views.certificate, name="certificate"),
]

# The QR target. Deliberately short, deliberately outside /e/<slug>/, and
# deliberately without a login: it is typed or scanned by a phone that is
# not signed in and never will be (Rule 7.6).
urlpatterns += [
    path("u/<str:token>/", views.upload_by_token, name="upload_by_token"),
]
