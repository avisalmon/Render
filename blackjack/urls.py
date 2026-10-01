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
    path("api/", include(router.urls)),
]
