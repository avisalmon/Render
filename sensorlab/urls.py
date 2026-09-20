from django.urls import include, path

from . import auth_views, views
from .api import router
from .api.attempts import SharedAttemptView
from .api.consent import SensorConsentItemView, SensorConsentView
from .api.profile import MyProfileView
from .api.schema import SchemaView

app_name = "sensorlab"

urlpatterns = [
    path("", views.home, name="home"),
    path("lab/", views.lab, name="lab"),
    # SL-B4. After `lab/` so the member home keeps that URL, and a slug can
    # never shadow it.
    path("lab/<slug:slug>/", views.lab_overview, name="lab_overview"),
    # SL-D2. Before the overview pattern would ever match "run" as a
    # slug — it cannot, since these are longer, but order is the thing
    # nobody checks until a lab is called "run".
    path("lab/<slug:slug>/run/", views.run, name="run"),
    path("lab/<slug:slug>/run/<str:step>/", views.run_step, name="run_step"),
    # Epic C spike: does this device actually give a web page its sensors?
    path("sensor-check/", views.sensor_check, name="sensor_check"),
    path("design/", views.design, name="design"),
    path("sensors/", views.sensors, name="sensors"),
    # SL-A5: the switch, reachable without an account (spec §1).
    path("language/<str:code>/", views.set_language, name="set_language"),
    # Auth in SensorLab's own chrome (SL-A2). The accounts are the site's.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    # The REST platform (SL-A3). Rule 6: infrastructure from the start, not
    # added later for the screens that happen to need it.
    path("api/profile/me/", MyProfileView.as_view(), name="api_profile_me"),
    path("api/sensor-consent/", SensorConsentView.as_view(), name="api_sensor_consent"),
    path("api/sensor-consent/<str:sensor>/", SensorConsentItemView.as_view(),
         name="api_sensor_consent_item"),
    path("api/schema/", SchemaView.as_view(), name="api_schema"),
    # SL-D3. Before the router include, so "shared" is never read as
    # an attempt primary key.
    path("api/attempts/shared/<uuid:share_slug>/", SharedAttemptView.as_view(),
         name="api_shared_attempt"),
    path("api/", include(router.urls)),
]
