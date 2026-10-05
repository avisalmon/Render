"""Routes for improv. Mounted at /improv/ in mysite/urls.py, before the
catch-all include of babook's own urls. The gate is improv.middleware."""

from django.urls import include, path

from . import views

app_name = "improv"

urlpatterns = [
    path("", views.home, name="home"),
    path("play/", views.play, name="play"),
    path("library/", views.library, name="library"),
    path("editor/", views.editor, name="editor"),
    path("setup/", views.setup, name="setup"),
    path("reference/", views.reference, name="reference"),
    path("spike/", views.spike, name="spike"),
    path("api/", include("improv.api_urls")),
]
