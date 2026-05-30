from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from . import course_api

urlpatterns = [
    path("", views.home, name="home"),
    path("add_note/", views.add_note, name="add_note"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("staff/copilot-dashboard/", views.CopilotDashboardView.as_view(), name="copilot_dashboard"),
    path("corporate/", views.corporate, name="corporate"),
    path("newsletter/signup/", views.newsletter_signup, name="newsletter_signup"),
    path("newsletter/confirm/<str:token>", views.newsletter_confirm, name="newsletter_confirm"),
    # Courses (plural — SPR-2.2)
    path("courses/", views.courses_catalog, name="courses_catalog"),
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
    path("api/v1/courses/", course_api.list_courses, name="api_courses_list"),
    path("api/v1/courses/sync/", course_api.sync_course, name="api_courses_sync"),
    path("api/v1/media/upload/", course_api.upload_media, name="api_media_upload"),
]
