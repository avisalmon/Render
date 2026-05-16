from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("add_note/", views.add_note, name="add_note"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("staff/copilot-dashboard/", views.copilot_dashboard, name="copilot_dashboard"),
    path("course/<slug:slug>/", views.course_detail, name="course_detail"),
    path("course/<slug:slug>/lesson/<int:lesson_order>/", views.lesson, name="lesson"),
    path("api/video-progress/", views.video_progress, name="video_progress"),
]
