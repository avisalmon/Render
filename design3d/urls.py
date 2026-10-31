"""Routes for design3d, mounted at /design3d/ (docs/design3d/spec.md)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, views
from .api import ROUTES

app_name = "design3d"

router = DefaultRouter()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.door, name="door"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", auth_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("ask/", views.ask, name="ask"),
    path("welcome/", views.welcome, name="welcome"),
    path("i/<str:token>/", views.invited, name="invited"),
    path("r/new/", views.friend_new, name="friend_new"),
    path("r/<str:code>/", views.friend_link, name="friend_link"),
    path("designs/", views.designs, name="designs"),
    path("designs/new/", views.new_design, name="new"),
    path("d/<int:pk>/", views.design, name="design"),
    path("d/<int:pk>/send/", views.send, name="send"),
    path("d/<int:pk>/say/", views.say, name="say"),
    path("d/<int:pk>/poll/", views.poll, name="poll"),
    path("d/<int:pk>/sliders/", views.sliders, name="sliders"),
    path("d/<int:pk>/edit/", views.edit, name="edit"),
    path("d/<int:pk>/email/", views.email_chat, name="email_chat"),
    path("d/<int:pk>/done/", views.done, name="done"),
    path("d/<int:pk>/send-files/", views.send_files, name="send_files"),
    path("x/a/<str:token>/", views.analysis_zip, name="analysis_zip"),
    path("x/<str:token>/", views.export, name="export"),
    path("d/<int:pk>/v/<int:number>/use/", views.use_version, name="use_version"),
    path("d/<int:pk>/v/<int:number>/<str:kind>/", views.download, name="download"),
    path("d/<int:pk>/v/<int:number>/<str:kind>/<str:part>/", views.download, name="download_part"),
    path("shared/", views.shared, name="shared"),
    path("shared/<int:pk>/", views.shared_design, name="shared_design"),
    path("shared/<int:pk>/copy/", views.copy_design, name="copy"),
    path("people/", views.people, name="people"),
    path("files/<path:path>", views.file, name="file"),
    path("api/", include(router.urls)),
]
