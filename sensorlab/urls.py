from django.urls import path

from . import auth_views, views

app_name = "sensorlab"

urlpatterns = [
    path("", views.home, name="home"),
    path("lab/", views.lab, name="lab"),
    # Auth in SensorLab's own chrome (SL-A2). The accounts are the site's.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
]
