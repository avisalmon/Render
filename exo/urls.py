from django.urls import include, path

from . import (
    auth_views,
    concept_views,
    journey_views,
    manage_views,
    museum_views,
    views,
)
from .api import router
from .approve_api import ApproveView

app_name = "exo"

urlpatterns = [
    # ---- the public half: no login, and no prompt to (spec §3) --------
    path("", views.home, name="home"),
    path("learn/", views.learn, name="learn"),
    # Before the attribute pattern, so a handout page can never shadow an
    # attribute and the two namespaces stay obviously separate.
    path("learn/page/<slug:key>/", views.learn_page, name="learn_page"),
    path("learn/<slug:key>/", views.learn_attribute, name="learn_attribute"),
    path("museum/", museum_views.museum, name="museum"),
    path("museum/<int:pk>/", museum_views.museum_item, name="museum_item"),
    path("museum/<int:pk>/like/", museum_views.like, name="museum_like"),
    # The switch, reachable without an account (spec §0.3).
    path("language/<str:code>/", views.set_language, name="set_language"),

    # ---- access (spec §4) --------------------------------------------
    path("join/", auth_views.join, name="join"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("waiting/", auth_views.waiting, name="waiting"),

    # ---- the builder (spec §5) ---------------------------------------
    path("concepts/", concept_views.concepts, name="concepts"),
    path("concepts/new/", concept_views.create, name="concept_create"),
    path("concepts/<int:pk>/", concept_views.resume, name="concept_resume"),
    path("concepts/<int:pk>/rename/", concept_views.rename, name="concept_rename"),
    path("concepts/<int:pk>/delete/", concept_views.delete, name="concept_delete"),
    path("concepts/<int:pk>/reorder/", concept_views.reorder, name="concept_reorder"),
    path("concepts/<int:pk>/back/", concept_views.go_back, name="concept_back"),

    # stage 1
    path("concepts/<int:pk>/interview/", journey_views.interview,
         name="concept_interview"),
    path("concepts/<int:pk>/interview/send/", journey_views.interview_send,
         name="concept_interview_send"),
    path("concepts/<int:pk>/interview/summary/", journey_views.interview_summary,
         name="concept_interview_summary"),
    path("concepts/<int:pk>/settle/", journey_views.settle, name="concept_settle"),

    # stage 2
    path("concepts/<int:pk>/brainstorm/", journey_views.brainstorm,
         name="concept_brainstorm"),
    path("concepts/<int:pk>/entries/", journey_views.entry_add, name="entry_add"),
    path("concepts/<int:pk>/entries/<int:entry_id>/", journey_views.entry_edit,
         name="entry_edit"),
    path("concepts/<int:pk>/entries/<int:entry_id>/delete/",
         journey_views.entry_delete, name="entry_delete"),
    path("concepts/<int:pk>/to-options/", journey_views.to_options,
         name="concept_to_options"),

    # stage 3
    path("concepts/<int:pk>/options/", journey_views.options, name="concept_options"),
    path("concepts/<int:pk>/options/generate/", journey_views.options_generate,
         name="options_generate"),
    path("concepts/<int:pk>/options/own/", journey_views.option_add_own,
         name="option_add_own"),
    path("concepts/<int:pk>/options/<int:option_id>/select/",
         journey_views.option_select, name="option_select"),
    path("concepts/<int:pk>/to-output/", journey_views.to_output,
         name="concept_to_output"),

    # stage 4
    path("concepts/<int:pk>/output/", journey_views.output, name="concept_output"),
    path("concepts/<int:pk>/output/generate/", journey_views.output_generate,
         name="output_generate"),
    path("concepts/<int:pk>/output/edit/", journey_views.output_edit,
         name="output_edit"),
    path("concepts/<int:pk>/output/style/", journey_views.output_style,
         name="output_style"),
    path("concepts/<int:pk>/output/stress-test/", journey_views.output_stress_test,
         name="output_stress_test"),
    path("concepts/<int:pk>/output/visibility/", journey_views.output_visibility,
         name="output_visibility"),

    # ---- Avi's cockpit (spec §11) ------------------------------------
    path("manage/requests/", manage_views.requests, name="manage_requests"),
    path("manage/requests/<int:pk>/", manage_views.decide, name="manage_decide"),
    path("manage/releases/", manage_views.releases, name="manage_releases"),
    path("manage/releases/<int:pk>/", manage_views.moderate, name="manage_moderate"),
    path("manage/usage/", manage_views.usage, name="manage_usage"),

    # ---- the REST platform (Rule 6) ----------------------------------
    # Before the router, so "approve" is never read as a resource lookup.
    path("api/approve/", ApproveView.as_view(), name="api_approve"),
    path("api/", include(router.urls)),
]
