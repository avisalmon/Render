from django.contrib.auth import views as auth_views
from django.urls import path

from . import (
    community_views,
    course_api,
    forum_views,
    onboarding_views,
    showcase_views,
    studio_views,
    tips_views,
    views,
)

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
    path("cookie-consent/", views.cookie_consent, name="cookie_consent"),
    path("verify-email/", views.verify_email, name="verify_email"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
    path("profile/", views.profile, name="profile"),
    path("account/delete/", views.delete_account, name="delete_account"),
    path("staff/copilot-dashboard/", views.CopilotDashboardView.as_view(), name="copilot_dashboard"),
    path("corporate/", views.corporate, name="corporate"),

    # --- Community (EPIC-6.1) ---
    path("community/", community_views.community_home, name="community"),
    path("community/guidelines/", community_views.guidelines, name="community_guidelines"),
    path("community/leaderboard/", community_views.leaderboard, name="community_leaderboard"),
    path("community/notifications/", community_views.notifications_page, name="community_notifications"),
    path("community/members/", community_views.members_directory, name="community_members"),
    path("community/settings/", community_views.community_settings_save, name="community_settings"),
    path("community/join/", community_views.community_go_public, name="community_go_public"),
    path("community/report/", community_views.report_content, name="community_report"),
    path("c/<str:username>/", community_views.public_profile, name="community_profile"),
    path("c/<str:username>/follow/", community_views.follow_toggle, name="community_follow"),
    # --- Tips & Feed (EPIC-6.4) ---
    path("community/tips/", tips_views.tips_list, name="tips_list"),
    path("community/tips/new/", tips_views.tip_create, name="tip_create"),
    path("community/tips/<int:tip_id>/", tips_views.tip_detail, name="tip_detail"),
    path("community/tips/<int:tip_id>/react/", tips_views.tip_react, name="tip_react"),
    # --- Forums & Q&A (EPIC-6.2) ---
    path("community/forum/", forum_views.forum_home, name="forum_home"),
    path("community/forum/new/", forum_views.thread_new, name="forum_new"),
    path("community/forum/similar/", forum_views.similar_threads, name="forum_similar"),
    path("community/forum/preview/", forum_views.forum_preview, name="forum_preview"),
    path("community/forum/thread/<int:thread_id>/", forum_views.thread_detail, name="forum_thread"),
    path("community/forum/thread/<int:thread_id>/answer/", forum_views.post_answer, name="forum_answer"),
    path("community/forum/thread/<int:thread_id>/subscribe/", forum_views.subscribe_thread, name="forum_subscribe"),
    path("community/forum/thread/<int:thread_id>/curate/", forum_views.thread_curate, name="forum_curate"),
    path("community/forum/thread/<int:thread_id>/summarize/", forum_views.summarize_thread, name="forum_summarize"),
    path("community/forum/thread/<int:thread_id>/draft/", forum_views.draft_answer, name="forum_draft"),
    path("community/forum/post/<int:post_id>/vote/", forum_views.vote_post, name="forum_vote"),
    path("community/forum/post/<int:post_id>/accept/", forum_views.accept_answer, name="forum_accept"),
    # --- Showcase / דוכן השוויץ (EPIC-6.3) ---
    path("community/showcase/", showcase_views.showcase_wall, name="showcase_wall"),
    path("community/showcase/feed/", showcase_views.showcase_feed, name="showcase_feed"),
    path("community/showcase/new/", showcase_views.project_create, name="showcase_new"),
    path("community/showcase/stand/<slug:stand>/", showcase_views.showcase_wall, name="showcase_stand"),
    path("community/showcase/p/<int:project_id>/", showcase_views.project_detail, name="showcase_project"),
    path("community/showcase/p/<int:project_id>/edit/", showcase_views.project_edit, name="showcase_edit"),
    path("community/showcase/p/<int:project_id>/delete/", showcase_views.project_delete, name="showcase_delete"),
    path("community/showcase/p/<int:project_id>/react/", showcase_views.project_react, name="showcase_react"),
    path("community/showcase/p/<int:project_id>/comment/", showcase_views.project_comment, name="showcase_comment"),
    path("community/showcase/p/<int:project_id>/feature/", showcase_views.project_feature, name="showcase_feature"),
    # --- Direct messages (EPIC-6.3, REQ-6.3.12) ---
    path("community/messages/", community_views.messages_inbox, name="messages_inbox"),
    path("community/messages/<str:username>/", community_views.message_thread, name="messages_thread"),
    path("community/messages/<str:username>/block/", community_views.message_block, name="messages_block"),

    # Apex section placeholders (coming soon)
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
