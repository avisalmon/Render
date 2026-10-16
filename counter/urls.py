from django.urls import include, path

from . import views
from .api import router
from .api import public

app_name = "counter"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sites/<int:pk>/", views.site_detail, name="site"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # The snippet a static page loads.
    path("c.js", views.snippet_js, name="snippet"),
    # Public, key-based (api/public.py). Listed before the router so the
    # router's own root view never shadows them.
    path("api/hit/", public.hit, name="api_hit"),
    path("api/stats/<str:key>/", public.site_stats, name="api_stats"),
    path("api/promo/<str:key>/", public.promo_for, name="api_promo"),
    # Owner side: full CRUD, browsable API (Rule 6).
    path("api/", include(router.urls)),
]
