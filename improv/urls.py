"""Routes for improv. Mounted at /improv/ in mysite/urls.py, before the
catch-all include of babook's own urls. The gate is improv.middleware."""

from django.urls import include, path

from . import signin, views

app_name = "improv"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", signin.login_view, name="login"),
    path("signup/", signin.signup_view, name="signup"),
    path("logout/", signin.logout_view, name="logout"),
    path("feedback/", views.feedback, name="feedback"),
    path("play/", views.play, name="play"),
    path("library/", views.library, name="library"),
    path("editor/", views.editor, name="editor"),
    path("setup/", views.setup, name="setup"),
    path("reference/", views.reference, name="reference"),
    path("scales/", views.scales, name="scales"),
    path("chords/", views.chords, name="chords"),
    path("takes/", views.takes, name="takes"),
    path("practice/", views.practice, name="practice"),
    path("challenges/", views.challenges, name="challenges"),
    path("progress/", views.progress, name="progress"),
    path("lessons/", views.lessons, name="lessons"),
    path("lessons/<slug:slug>/", views.lesson, name="lesson"),
    path("spike/", views.spike, name="spike"),
    path("api/", include("improv.api_urls")),
]
