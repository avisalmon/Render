"""מט״צים URL space.

Namespaced, so every name in this product is `matazim:*` and can never collide
with a babook name. RULE-1 is enforced against this: a template under
templates/matazim/ may only reverse names in this namespace.
"""

from django.urls import path

from . import (
    cohort_views,
    entrance_views,
    invite_views,
    joining_views,
    learn_views,
    path_views,
    rights_views,
    roster_views,
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
    path("community/", views.community, name="community"),
    path("events/", views.events, name="events"),
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
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    # A minor's uploaded work, handed out only to people entitled to it
    # (REQ-M.80). It is no longer under the public /media/ tree.
    path("attempt/<int:attempt_id>/file/", entrance_views.attempt_file, name="attempt_file"),
    # REQ-M.12 — the member's own screen, and the only role that had none.
    path("my-path/", path_views.my_path, name="my_path"),
    # REQ-M.13 — the required track, rendered inside our own walls.
    path("learn/<slug:slug>/", learn_views.learn_course, name="learn_course"),
    path("learn/<slug:slug>/<int:order>/", learn_views.learn_lesson, name="learn_lesson"),
    path("profile/", views.profile, name="profile"),
    path("profile/replay-welcome/", views.profile_reset_welcome, name="profile_reset_welcome"),
]
