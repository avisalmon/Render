"""מט״צים URL space.

Namespaced, so every name in this product is `matazim:*` and can never collide
with a babook name. RULE-1 is enforced against this: a template under
templates/matazim/ may only reverse names in this namespace.
"""

from django.urls import path

from . import entrance_views, joining_views, roster_views, views

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
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    # A minor's uploaded work, handed out only to people entitled to it
    # (REQ-M.80). It is no longer under the public /media/ tree.
    path("attempt/<int:attempt_id>/file/", entrance_views.attempt_file, name="attempt_file"),
    path("profile/", views.profile, name="profile"),
    path("profile/replay-welcome/", views.profile_reset_welcome, name="profile_reset_welcome"),
]
