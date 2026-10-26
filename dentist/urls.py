from django.urls import include, path

from . import api, auth_views, views

app_name = "dentist"

urlpatterns = [
    path("", views.home, name="home"),
    path("clinics/new/", views.clinic_new, name="clinic_new"),

    # The clinic's own doors to the shared accounts (spec Rule 2.4). No
    # sign-up route: members arrive by invitation, patients by a one-time
    # link, and both of those are below.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # The two ways a person comes to exist in a clinic (Rule 3.2, 3.4).
    path("accept/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path("join/<str:token>/", views.join, name="join"),

    # The patient's own screen.
    path("me/", views.me, name="me"),

    # The API, scoped to one clinic in the URL (Rule 2.6).
    path("api/c/<slug:slug>/", include(api.router.urls)),

    # One clinic. Kept last so these never shadow a named route above.
    path("c/<slug:slug>/", views.clinic_home, name="clinic_home"),
    path("c/<slug:slug>/people/", views.people_screen, name="people"),
    path("c/<slug:slug>/try-as/", views.try_as, name="try_as"),
    path("c/<slug:slug>/people/<int:pk>/toggle/", views.member_toggle, name="member_toggle"),
    path("c/<slug:slug>/people/invitations/<int:pk>/<str:what>/", views.invitation_action, name="invitation_action"),
    path("c/<slug:slug>/setup/", views.setup, name="setup"),
    path("c/<slug:slug>/setup/chairs/<int:pk>/toggle/", views.chair_toggle, name="chair_toggle"),
    path("c/<slug:slug>/patients/", views.patients, name="patients"),
    path("c/<slug:slug>/patients/new/", views.patient_new, name="patient_new"),
    path("c/<slug:slug>/p/<int:pk>/", views.patient, name="patient"),
    path("c/<slug:slug>/p/<int:pk>/edit/", views.patient_edit, name="patient_edit"),
    path("c/<slug:slug>/p/<int:pk>/history/<int:item>/resolve/", views.history_resolve, name="history_resolve"),
    path("c/<slug:slug>/p/<int:pk>/link/", views.patient_link_new, name="patient_link_new"),
    path("c/<slug:slug>/p/<int:pk>/export/", views.patient_export, name="patient_export"),
    path("c/<slug:slug>/p/<int:pk>/delete/", views.patient_delete, name="patient_delete"),
    path("c/<slug:slug>/p/<int:pk>/mouth/", views.mouth_screen, name="mouth"),
    path("c/<slug:slug>/p/<int:pk>/mouth/record/", views.tooth_record, name="tooth_record"),
    path("c/<slug:slug>/p/<int:pk>/plan/add/", views.plan_add, name="plan_add"),
    path("c/<slug:slug>/p/<int:pk>/plan/<int:item>/<str:what>/", views.plan_item_action, name="plan_item_action"),
    path("c/<slug:slug>/p/<int:pk>/print/", views.patient_print, name="patient_print"),
    path("c/<slug:slug>/log/", views.access_log, name="access_log"),
]
