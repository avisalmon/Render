"""
SPR-5.5 — Personalization, activation & measurement (REQ-5.6.2-5.6.5, REQ-5.7).
The deterministic recommender, the homepage rail + checklist, and the
funnel events in the rendered pages.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models import Course, Enrollment, LearnerProfile, UserVideoProgress, Video
from app.onboarding import first_lesson_url, recommend


def _course(slug, domain="ai", track="ai-l1", published=True):
    c = Course.objects.create(slug=slug, title=f"קורס {slug}", is_published=published,
                              domain=domain, track=track)
    Video.objects.create(course=c, lesson_order=1, title="L1", is_free_preview=True)
    return c


def _onboarded_user(username="fan1", course=None):
    u = User.objects.create_user(username, password="pass12345")
    LearnerProfile.objects.create(
        user=u, interests=["ai"], experience_level="beginner",
        recommended_course=course, onboarding_completed_at=timezone.now(),
    )
    return u


# --- recommender (REQ-5.6.2, DEC-32) ---

@pytest.mark.django_db
def test_recommend_ai_beginner_maps_to_l1_intro():
    intro = _course("ai-user-journey")
    _course("other-ai", track="ai-l2")
    track, course = recommend(["ai"], "beginner")
    assert track == "ai-l1" and course == intro


@pytest.mark.django_db
def test_recommend_level_picks_ai_track():
    advanced = _course("ai-fundamentals", track="ai-l3")
    track, course = recommend(["ai"], "advanced")
    assert track == "ai-l3" and course == advanced


@pytest.mark.django_db
def test_recommend_entry_course_wins():
    """REQ-5.2.3: the course the visitor came for beats everything."""
    _course("ai-user-journey")
    came_for = _course("press-release", domain="innovation", track="presentation")
    track, course = recommend(["ai"], "beginner", came_for)
    assert course == came_for and track == "presentation"


@pytest.mark.django_db
def test_recommend_non_ai_domain_first_track():
    c3d = _course("print3d", domain="matazim", track="3d")
    track, course = recommend(["matazim"], "beginner")
    assert track == "3d" and course == c3d


@pytest.mark.django_db
def test_first_lesson_url():
    c = _course("hop")
    assert first_lesson_url(c) == "/courses/hop/lesson/1/"
    assert first_lesson_url(None) == "/courses/"


# --- homepage rail + checklist (REQ-5.6.3/5.6.5) ---

@pytest.mark.django_db
def test_home_shows_personalized_rail():
    course = _course("ai-user-journey")
    u = _onboarded_user(course=course)
    c = Client()
    c.force_login(u)
    body = c.get("/").content.decode()
    assert "מומלץ עבורך" in body
    assert "ai-user-journey" in body


@pytest.mark.django_db
def test_home_generic_without_learner_profile():
    """Pre-EPIC-5 users keep the generic homepage (REQ-5.6.3 fallback)."""
    u = User.objects.create_user("legacy", password="pass12345")
    c = Client()
    c.force_login(u)
    body = c.get("/").content.decode()
    assert "מומלץ עבורך" not in body
    assert "העולמות של babook" in body


@pytest.mark.django_db
def test_checklist_reflects_progress_and_completes_away():
    course = _course("ai-user-journey")
    u = _onboarded_user("checker", course=course)
    c = Client()
    c.force_login(u)
    assert "צעדים ראשונים" in c.get("/").content.decode()

    # Complete all four steps -> checklist disappears
    from app.models import LessonReflection
    video = course.videos.first()
    Enrollment.objects.create(user=u, course=course)
    UserVideoProgress.objects.create(user=u, video=video, quiz_passed=True)
    LessonReflection.objects.create(user=u, video=video, user_text="היה מעולה")
    assert "צעדים ראשונים" not in c.get("/").content.decode()


# --- funnel events (REQ-5.7.1) ---

@pytest.mark.django_db
def test_entry_event_fires_once():
    c = Client()
    first = c.get("/courses/").content.decode()
    assert "plausible('entry'" in first
    second = c.get("/").content.decode()
    assert "plausible('entry'" not in second


@pytest.mark.django_db
def test_wall_and_lesson_events_present():
    _course("evented")
    c = Client()
    wall = c.get("/join/?course=evented").content.decode()
    assert "wall_shown" in wall
    lesson = c.get("/courses/evented/lesson/1/").content.decode()
    assert "free_lesson_watched" in lesson


@pytest.mark.django_db
def test_onboarding_events_in_welcome_page():
    c = Client()
    c.post("/register/", {
        "username": "evt1", "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    body = c.get("/welcome/").content.decode()
    assert "onboarding_started" in body and "plausible('registered')" in body
