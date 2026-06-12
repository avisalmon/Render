from django.contrib.auth import views as auth_views
from django.urls import path

from . import course_api, onboarding_views, studio_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("add_note/", views.add_note, name="add_note"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    # Onboarding & first-time experience (EPIC-5)
    path("join/", onboarding_views.join_wall, name="join_wall"),
    path("welcome/", onboarding_views.welcome, name="welcome"),
    path("welcome/basics/", onboarding_views.welcome_basics, name="welcome_basics"),
    path("welcome/chat/", onboarding_views.welcome_chat, name="welcome_chat"),
    path("welcome/complete/", onboarding_views.welcome_complete, name="welcome_complete"),
    path("welcome/skip/", onboarding_views.welcome_skip, name="welcome_skip"),
    path("profile/", views.profile, name="profile"),
    path("staff/copilot-dashboard/", views.CopilotDashboardView.as_view(), name="copilot_dashboard"),
    path("corporate/", views.corporate, name="corporate"),

    # Apex section placeholders (coming soon)
    path("community/", views.coming_soon, {"section": "community"}, name="community"),
    path("services/", views.coming_soon, {"section": "services"}, name="services"),
    path("workshops/", views.coming_soon, {"section": "workshops"}, name="workshops"),
    path("nostalgia/", views.coming_soon, {"section": "nostalgia"}, name="nostalgia"),
    path("research/", views.coming_soon, {"section": "research"}, name="research"),
    path("newsletter/signup/", views.newsletter_signup, name="newsletter_signup"),
    path("newsletter/confirm/<str:token>", views.newsletter_confirm, name="newsletter_confirm"),
    # Courses (plural — SPR-2.2)
    path("courses/", views.courses_catalog, name="courses_catalog"),
    path("courses/topic/<slug:domain>/", views.courses_domain, name="courses_domain"),
    path("courses/topic/<slug:domain>/<slug:track>/", views.courses_track, name="courses_track"),
    path("courses/<slug:slug>/", views.courses_detail, name="courses_detail"),
    path("courses/<slug:slug>/enroll/", views.courses_enroll, name="courses_enroll"),
    path("courses/<slug:slug>/finish/", views.course_finish, name="course_finish"),
    path("courses/<slug:slug>/lesson/<int:lesson_order>/", views.courses_lesson, name="courses_lesson"),
    # Courses (singular — SPR-1.4/1.5 entitlement-gated)
    path("course/<slug:slug>/", views.course_detail_view, name="course_detail"),
    path("course/<slug:slug>/lesson/<int:lesson_order>/", views.lesson_view, name="lesson_view"),
    # Certificate
    path("certificate/<uuid:cert_id>/", views.certificate_view, name="certificate_view"),
    # Video progress heartbeat (SPR-1.4)
    path("api/video-progress/", views.video_progress_heartbeat, name="video_progress"),
    path("api/lesson/<int:video_id>/reflect/", views.lesson_reflect, name="lesson_reflect"),
    # Legacy heartbeat alias (used by lesson.html prev/next)
    path("courses/<slug:slug>/heartbeat/", views.video_progress_heartbeat, name="video_heartbeat"),
    # Pricing (SPR-1.5)
    path("pricing/", views.pricing, name="pricing"),
    path("pricing/choose/", views.choose_tier, name="choose_tier"),
    # AI Chat (SPR-1.8)
    path("chat/", views.chat_page, name="chat_page"),
    path("api/chat/", views.chat_api, name="chat_api"),
    path("api/chat/sessions/", views.chat_sessions_api, name="chat_sessions_api"),
    path("staff/ai-usage/", views.AiUsageDashboardView.as_view(), name="ai_usage_dashboard"),

    # Course Management API (SPR-2.3)
    # --- Authoring Studio (EPIC-4) ---
    path("studio/", studio_views.studio_home, name="studio_home"),
    path("studio/course/new/", studio_views.course_create, name="studio_course_create"),
    path("studio/new-from-video/", studio_views.new_from_video, name="studio_new_from_video"),
    path("studio/preview/", studio_views.markdown_preview, name="studio_markdown_preview"),
    path("studio/job/<int:job_id>/", studio_views.job_status, name="studio_job"),
    path("studio/job/<int:job_id>/status/", studio_views.job_status_api, name="studio_job_api"),
    path("studio/course/<slug:slug>/", studio_views.course_edit, name="studio_course_edit"),
    path("studio/course/<slug:slug>/delete/", studio_views.course_delete, name="studio_course_delete"),
    path("studio/course/<slug:slug>/publish/", studio_views.course_publish, name="studio_course_publish"),
    path("studio/course/<slug:slug>/reorder/", studio_views.lesson_reorder, name="studio_lesson_reorder"),
    path("studio/course/<slug:slug>/lesson/new/", studio_views.lesson_edit, name="studio_lesson_new"),
    path("studio/course/<slug:slug>/lesson/<int:order>/", studio_views.lesson_edit, name="studio_lesson_edit"),
    path("studio/course/<slug:slug>/lesson/<int:order>/delete/", studio_views.lesson_delete, name="studio_lesson_delete"),

    path("api/v1/courses/", course_api.list_courses, name="api_courses_list"),
    path("api/v1/courses/sync/", course_api.sync_course, name="api_courses_sync"),
    path("api/v1/courses/<slug:slug>/", course_api.course_detail, name="api_courses_detail"),
    path("api/v1/media/upload/", course_api.upload_media, name="api_media_upload"),
]
