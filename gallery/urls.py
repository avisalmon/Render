"""Routes for the gallery, mounted at /gallery/ (docs/gallery/spec.md)."""

from django.urls import include, path
from rest_framework import permissions, routers

from . import auth_views, manage_views, views
from .api import ROUTES

app_name = "gallery"


class OpenRoot(routers.APIRootView):
    """The API's index is public, like everything it lists (REQ-G.1)."""

    permission_classes = [permissions.AllowAny]


class Router(routers.DefaultRouter):
    APIRootView = OpenRoot


router = Router()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", auth_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("new/", views.exhibit_new, name="exhibit_new"),
    path("e/<int:pk>/", views.exhibit, name="exhibit"),
    path("e/<int:pk>/edit/", views.exhibit_edit, name="exhibit_edit"),
    path("skills/", views.skills_home, name="skills"),
    path("skills/new/", views.skill_new, name="skill_new"),
    path("skills/guide/", views.skill_guide, name="skill_guide"),
    path("skills/chat/<int:pk>/", views.skill_chat, name="skill_chat"),
    path("skills/chat/<int:pk>/act/", views.skill_chat_act, name="skill_chat_act"),
    path("e/<int:pk>/update/", views.skill_new, name="skill_update"),
    path("e/<int:pk>/download/<str:platform>/", views.skill_download, name="skill_download"),
    path("manage/", manage_views.home, name="manage"),
    path("manage/people/", manage_views.people, name="manage_people"),
    path("manage/people/<int:pk>/", manage_views.person, name="manage_person"),
    path("manage/trainings/", manage_views.trainings, name="manage_trainings"),
    path("manage/topics/", manage_views.topics, name="manage_topics"),
    path("u/<str:slug>/", views.person_page, name="person"),
    path("settings/", views.settings_page, name="settings"),
    path("training/", views.training, name="training"),
    path("language/<str:code>/", views.set_language, name="set_language"),
    path("files/<path:path>", views.file, name="file"),
    path("api/", include(router.urls)),
]
