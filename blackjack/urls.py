"""Routes for blackjack. Mounted at /blackjack/ in mysite/urls.py, before
the catch-all include of babook's own urls."""

from django.urls import path

from . import views

app_name = "blackjack"

urlpatterns = [
    path("", views.home, name="home"),
]
