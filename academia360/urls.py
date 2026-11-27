"""Routes for Academia360, mounted at /academia360/ (docs/academia360/spec.md)."""

from django.urls import include, path
from rest_framework import permissions, routers

from . import (
    auth_views,
    committee,
    coverage,
    deciding,
    discuss,
    doors,
    letter_pages,
    manage,
    notify,
    talk,
    views,
)
from .api import (
    ROUTES,
    ExtractView,
    InviteView,
    ReplicateFileView,
    ReplicateView,
    RequestDecideView,
    RoleGrantView,
)

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
    path("program/", views.program_page, name="program"),
    path("institutions/", views.institutions, name="institutions"),
    path("search/", views.search, name="search"),
    path("me/", talk.me, name="me"),
    path("notifications/", notify.my_notifications, name="notifications"),
    path("notifications/read-all/", notify.read_all, name="notifications_read_all"),
    path("notifications/<int:pk>/go/", notify.follow, name="notification_follow"),
    path("join/", doors.join, name="join"),
    path("invite/<str:token>/", doors.invite, name="invite"),
    path("manage/", manage.overview, name="manage"),
    path("manage/people/", manage.people_page, name="manage_people"),
    path("manage/act/", manage.act, name="manage_act"),
    path("manage/coverage/", coverage.page, name="manage_coverage"),
    path("manage/coverage/set/", coverage.set_status, name="manage_coverage_set"),
    path("compare/", views.compare, name="compare"),
    path("talk/comment/", talk.comment, name="talk_comment"),
    path("talk/like/", talk.like, name="talk_like"),
    path("talk/correct/", talk.correct, name="talk_correct"),
    path("researchers/", views.researchers, name="researchers"),
    path("researchers/<str:slug>/", views.researcher, name="researcher"),
    path("institutions/<str:slug>/", views.institution, name="institution"),
    path("files/<int:pk>/", views.submitted_file, name="submitted_file"),
    path("files/<int:pk>/text/", committee.file_text, name="file_text"),
    path("letters/<int:pk>/file/", views.letter_file, name="letter_file"),
    path("letters/<int:pk>/", letter_pages.page, name="letter"),
    path("letters/<int:pk>/pdf/", letter_pages.pdf, name="letter_pdf"),
    # the committee's room (D2)
    path("committee/", committee.board, name="committee"),
    path("committee/review/<int:pk>/", committee.review, name="committee_review"),
    path("committee/review/<int:pk>/<int:review_pk>/", committee.review_of, name="committee_review_of"),
    path("committee/analysis/<int:pk>/", committee.analysis, name="committee_analysis"),
    path("committee/discuss/", discuss.index, name="committee_discuss"),
    path("committee/discuss/<int:pk>/", discuss.thread, name="committee_thread"),
    path("committee/decide/<int:pk>/", deciding.decide, name="committee_decide"),
    path("committee/letters/general/", letter_pages.general, name="committee_letters_general"),
    path("committee/letter/<int:pk>/", letter_pages.draft, name="committee_letter"),
    path("committee/<str:slug>/", committee.file, name="committee_file"),
    path("api/admin/extract/", ExtractView.as_view(), name="api_extract"),
    # Before the router, whose `roles/<pk>/` would otherwise swallow "grant".
    path("api/roles/grant/", RoleGrantView.as_view(), name="api_roles_grant"),
    path("api/admin/requests/<int:pk>/decide/", RequestDecideView.as_view(), name="api_request_decide"),
    path("api/admin/invitations/", InviteView.as_view(), name="api_invite"),
    path("api/admin/replicate/", ReplicateView.as_view(), name="api_replicate"),
    path("api/admin/coverage/", coverage.CoverageView.as_view(), name="api_coverage"),
    path("api/admin/replicate/file/<str:model>/<int:pk>/", ReplicateFileView.as_view(), name="api_replicate_file"),
    path("api/", include(router.urls)),
]
