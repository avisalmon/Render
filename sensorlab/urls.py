from django.urls import include, path

from . import auth_views, views
from .api import router
from .api.profile import MyProfileView
from .api.schema import SchemaView

app_name = "sensorlab"

urlpatterns = [
    path("", views.home, name="home"),
    path("lab/", views.lab, name="lab"),
    path("design/", views.design, name="design"),
    # SL-A5: the switch, reachable without an account (spec §1).
    path("language/<str:code>/", views.set_language, name="set_language"),
    # Auth in SensorLab's own chrome (SL-A2). The accounts are the site's.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    # The REST platform (SL-A3). Rule 6: infrastructure from the start, not
    # added later for the screens that happen to need it.
    path("api/profile/me/", MyProfileView.as_view(), name="api_profile_me"),
    path("api/schema/", SchemaView.as_view(), name="api_schema"),
    path("api/", include(router.urls)),
]
