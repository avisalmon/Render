from django.urls import path

from . import auth_views, views

app_name = "dentist"

urlpatterns = [
    path("", views.home, name="home"),
    path("clinics/new/", views.clinic_new, name="clinic_new"),

    # The clinic's own doors to the shared accounts (spec Rule 2.4). No
    # sign-up route: members arrive by invitation (D.2), patients by a
    # one-time link (D.3).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # One clinic. Kept last so these never shadow a named route above.
    path("c/<slug:slug>/", views.clinic_home, name="clinic_home"),
]
