"""Routes for blackjack. Mounted at /blackjack/ in mysite/urls.py, before
the catch-all include of babook's own urls."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .api import ROUTES

app_name = "blackjack"

router = DefaultRouter()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.home, name="home"),
    path("table/", views.table, name="table"),
    path("sheet/", views.sheet, name="sheet"),
    path("drill/", views.drill, name="drill"),
    path("play/", views.simulator, name="play"),
    path("progress/", views.progress, name="progress"),
    path("history/", views.history, name="history"),
    path("redeem/", views.redeem, name="redeem"),
    path("redeem/<str:code>/", views.redeem, name="redeem_code"),
    path("share/", views.share, name="share"),
    path("friends/", views.friends, name="friends"),
    path("r/<str:token>/", views.shared, name="shared"),
    path("advanced/", views.advanced, name="advanced"),
    path("advanced/explain/", views.explain, name="explain"),
    path("staff/coupons/", views.admin_coupons, name="admin_coupons"),
    path("api/", include(router.urls)),
]
