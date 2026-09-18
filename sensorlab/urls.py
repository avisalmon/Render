from django.urls import path

from . import views

app_name = "sensorlab"

urlpatterns = [
    path("", views.home, name="home"),
]
