"""מט״צים URL space.

Namespaced, so every name in this product is `matazim:*` and can never collide
with a babook name. RULE-1 is enforced against this: a template under
templates/matazim/ may only reverse names in this namespace.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import (
    api,
    certificate_views,
    cohort_views,
    community_views,
    conversation_views,
    entrance_views,
    event_views,
    internal_views,
    invite_views,
    joining_views,
    learn_views,
    notice_views,
    path_views,
    request_views,
    requests_api,
    rights_views,
    roster_views,
    submission_views,
    teaching_views,
    views,
)

app_name = "matazim"

urlpatterns = [
    path("", views.home, name="home"),
    # Litala's nine sections. Nothing here points at the page it is already on.
    path("about/", views.about, name="about"),
    path("track/", views.track, name="track"),
    path("courses/", views.courses, name="courses"),
    path("schools/", views.schools, name="schools"),
    # REQ-M.26, M.131-M.134 — קהילת מט״צים. One door: a visitor or a
    # candidate gets the page about the community, a member gets the feed.
    path("community/", community_views.community, name="community"),
    path("community/<int:post_id>/hide/", community_views.hide_post, name="hide_post"),
    path("community/<int:post_id>/show/", community_views.show_post, name="show_post"),
    path("community/<int:post_id>/remove/", community_views.unshare_post, name="unshare_post"),
    # REQ-M.27, M.129, M.130 — ימי שיא, and the year.
    path("events/", event_views.events_page, name="events"),
    path("calendar/", event_views.calendar, name="calendar"),
    path("staff/events/", event_views.staff_events, name="staff_events"),
    path("staff/events/<int:event_id>/cancel/", event_views.cancel_event, name="cancel_event"),
    # REQ-M.34 — the one machine-triggered endpoint here. A token, a POST,
    # and it can only send reminders.
    # The improvement loop, for the chat that runs the sprints (§4.11).
    # Token-or-superuser, and scoped to Request rows only: see requests_api.py.
    path("internal/requests/", requests_api.RequestQueueView.as_view(), name="api_requests_admin"),
    path("internal/remind/", internal_views.run_reminders, name="run_reminders"),
    # מבחן הכניסה is public: the link gets pasted around, and signing up
    # happens around the test rather than before it (REQ-M.5d).
    path("test/", views.entrance_test, name="entrance_test"),
    path("test/lessons/", entrance_views.test_lessons, name="test_lessons"),
    path("test/lesson/<int:order>/", entrance_views.test_lesson, name="test_lesson"),
    path("test/task/", entrance_views.test_task, name="test_task"),
    path("test/retry/", entrance_views.test_retry, name="test_retry"),
    # Staff curate the bank (REQ-M.55).
    path("staff/", entrance_views.staff_home, name="staff_home"),
    path("staff/admins/", entrance_views.staff_admins, name="staff_admins"),
    path("staff/users/search/", entrance_views.staff_user_search, name="staff_user_search"),
    # REQ-M.87 — what is due for deletion, and the person who approves it.
    path("staff/retention/", entrance_views.staff_retention, name="staff_retention"),
    path("staff/targets/", entrance_views.staff_targets, name="staff_targets"),
    path(
        "staff/targets/<str:target_id>/toggle/",
        entrance_views.staff_target_toggle,
        name="staff_target_toggle",
    ),
    # The threshold. Our screens, babook's accounts (REQ-M.6, REQ-M.7).
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("register/", views.register, name="register"),
    # Google, handed off and returned without the page ever linking out of the
    # prefix (REQ-M.45).
    path("auth/google/", views.google_start, name="google_start"),
    path("auth/done/", views.auth_done, name="auth_done"),
    # First contact (REQ-M.39 to M.41).
    path("welcome/accept/", views.welcome_accept, name="welcome_accept"),
    # Becoming someone: the invite link, the open door, and the leader's page.
    path("join/<str:code>/", joining_views.join, name="join"),
    path("joined/", joining_views.joined, name="joined"),
    path("apply/", joining_views.apply, name="apply"),
    path("leaders/", joining_views.leader_entrance, name="leader_entrance"),
    # SPR-M.14 — the three doors a leader can come through (REQ-M.90 to M.93).
    path("leaders/join/<str:token>/", invite_views.invite_landing, name="invite_landing"),
    path("staff/team/", invite_views.leaders, name="pm_leaders"),
    # REQ-M.24 — the cohort, and the school report Litala's brief asks for.
    path("staff/cohort/", cohort_views.cohort, name="cohort"),
    path("staff/cohort/export.csv", cohort_views.cohort_export, name="cohort_export"),
    path("staff/team/invite/<int:invite_id>/qr.png", invite_views.invite_qr, name="invite_qr"),
    path(
        "staff/team/candidate/<int:leader_id>/reject/",
        invite_views.reject_candidate,
        name="reject_candidate",
    ),
    path("leader/", joining_views.leader_home, name="leader_home"),
    path("leader/confirm/<int:student_id>/", joining_views.leader_confirm, name="leader_confirm"),
    # The desk, once someone is standing at it (SPR-M.8).
    path("leader/students/", roster_views.roster, name="roster"),
    path("leader/students/<int:student_id>/", roster_views.student, name="student"),
    path(
        "leader/students/<int:student_id>/certify/",
        roster_views.certify_student,
        name="certify",
    ),
    path("leader/classes/", roster_views.classes, name="classes"),
    path("leader/<int:leader_id>/qr.png", joining_views.leader_qr, name="leader_qr"),
    path("staff/leaders/", joining_views.staff_leaders, name="staff_leaders"),
    path("staff/leaders/<int:leader_id>/", joining_views.staff_leader, name="staff_leader"),
    # What we do with a fourteen-year-old's data, said where they can reach it
    # (REQ-M.81). RULE-1 means these cannot be links to babook's.
    # REQ-M.85 — see it, take it, or have it deleted. Deletion reuses the
    # mechanism babook's delete_account relies on, behind our own door.
    path("me/data/", rights_views.my_data, name="my_data"),
    path("me/data/export/", rights_views.my_data_export, name="my_data_export"),
    path("me/delete/", rights_views.delete_me, name="delete_me"),
    # REQ-M.84 — an admin records a school's paper consent.
    path("staff/consent/<int:profile_id>/", entrance_views.staff_consent, name="staff_consent"),
    # §4.11 — the improvement loop. Behind the program-manager role and root,
    # and every view refuses everyone else on its own (REQ-M.102). Proposing a
    # change is a conversation (REQ-M.115), so `new_request` opens one.
    path("requests/new/", conversation_views.start, name="new_request"),
    path("requests/<int:request_id>/talk/", conversation_views.talk, name="talk"),
    path("requests/<int:request_id>/adopt/", conversation_views.adopt, name="adopt_wording"),
    path("requests/<int:request_id>/send/", conversation_views.send, name="send_request"),
    path(
        "requests/<int:request_id>/discard/",
        conversation_views.discard,
        name="discard_request",
    ),
    path("requests/", request_views.my_requests, name="my_requests"),
    path("requests/queue/", request_views.request_queue, name="request_queue"),
    path("requests/<int:request_id>/decide/", request_views.decide_request, name="decide_request"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    # A minor's uploaded work, handed out only to people entitled to it
    # (REQ-M.80). It is no longer under the public /media/ tree.
    path("attempt/<int:attempt_id>/file/", entrance_views.attempt_file, name="attempt_file"),
    # REQ-M.12 — the member's own screen, and the only role that had none.
    # REQ-M.33 — the bell.
    path("notices/", notice_views.notices, name="notices"),
    path("notices/clear/", notice_views.clear_notices, name="clear_notices"),
    path("my-path/", path_views.my_path, name="my_path"),
    # REQ-M.19 — יוצרים: work handed in, and the feedback that is the point.
    # REQ-M.32 — פרקטיקום, the stage the whole programme exists to produce.
    path("my-teaching/", teaching_views.my_teaching, name="my_teaching"),
    path("my-teaching/<int:session_id>/off/", teaching_views.cancel_session, name="cancel_session"),
    path("my-work/", submission_views.my_work, name="my_work"),
    path("work/<int:submission_id>/", submission_views.review, name="review"),
    path("work/<int:submission_id>/file/", submission_views.work_file, name="work_file"),
    path("work/<int:submission_id>/say/", submission_views.say_more, name="say_more"),
    # REQ-M.5e — two yeses before anything is public, and either can be
    # taken back. The maker offers, the programme publishes.
    path("work/<int:submission_id>/offer/", submission_views.offer_publicly, name="offer_publicly"),
    path("work/<int:submission_id>/publish/", submission_views.publish, name="publish_work"),
    # REQ-M.20 — what a certified מט״צ can actually show somebody. `verify` is
    # public on purpose: a school checking one has no account.
    path("my-certificate/", certificate_views.my_certificate, name="my_certificate"),
    path("verify/<uuid:public_id>/", certificate_views.verify, name="verify"),
    # REQ-M.13 — the required track, rendered inside our own walls.
    path("learn/<slug:slug>/", learn_views.learn_course, name="learn_course"),
    path("learn/<slug:slug>/<int:order>/", learn_views.learn_lesson, name="learn_lesson"),
    path("profile/", views.profile, name="profile"),
    path("profile/replay-welcome/", views.profile_reset_welcome, name="profile_reset_welcome"),
]

# REQ-M.134, REQ-M.139, methodology Rule 6. Every model in this app, one
# viewset each, registered from `api.ROUTES` so that adding a model and
# forgetting its endpoint is a thing a test can notice. DRF's browsable API
# at /matazim/api/ is the documentation, the same call the site made for
# ustrip.
router = DefaultRouter()
for _prefix, _viewset, _model in api.ROUTES:
    router.register(_prefix, _viewset, basename=f"api-{_prefix}")

urlpatterns += [path("api/", include(router.urls))]
