"""Routes for Academia360, mounted at /academia360/ (docs/academia360/spec.md)."""

from django.urls import include, path
from rest_framework import permissions, routers

from . import auth_views, views
from .api import ROUTES, ReplicateFileView, ReplicateView, RoleGrantView

app_name = "academia360"


class OpenRoot(routers.APIRootView):
    """The API's index is public, like the program itself; what each route
    then shows is filtered by the asker's circle."""

    permission_classes = [permissions.AllowAny]


class Router(routers.DefaultRouter):
    APIRootView = OpenRoot


router = Router()
for prefix, viewset, _model in ROUTES:
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("no-access/", views.no_access_page, name="no_access"),
    path("institutions/", views.institutions, name="institutions"),
    path("search/", views.search, name="search"),
    path("institutions/<str:slug>/", views.institution, name="institution"),
    path("files/<int:pk>/", views.submitted_file, name="submitted_file"),
    path("letters/<int:pk>/file/", views.letter_file, name="letter_file"),
    # Before the router, whose `roles/<pk>/` would otherwise swallow "grant".
    path("api/roles/grant/", RoleGrantView.as_view(), name="api_roles_grant"),
    path("api/admin/replicate/", ReplicateView.as_view(), name="api_replicate"),
    path("api/admin/replicate/file/<str:model>/<int:pk>/", ReplicateFileView.as_view(), name="api_replicate_file"),
    path("api/", include(router.urls)),
]
