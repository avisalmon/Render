"""
SPR-5.2 — Intent capture & return-to-intent (REQ-5.2, REQ-5.4.2/5.4.4).
First-touch session capture, entry classification, attribution at signup,
and ?next= preserved through registration -> onboarding -> landing.
"""
import pytest
from django.test import Client

from app.models import Course, LearnerProfile, Video
from app.onboarding import FIRST_TOUCH_KEY, classify_entry


# --- entry classification (REQ-5.2.2) ---

@pytest.mark.parametrize("path,expected_type,expected_course", [
    ("/", "home", ""),
    ("/courses/", "home", ""),
    ("/courses/topic/ai/", "home", ""),
    ("/corporate/", "corporate", ""),
    ("/courses/python/", "course", "python"),
    ("/courses/python/lesson/3/", "lesson_locked", "python"),
    ("/course/python/lesson/1/", "lesson_locked", "python"),
    ("/pricing/", "other", ""),
])
def test_classify_entry(path, expected_type, expected_course):
    t, c = classify_entry(path)
    assert (t, c) == (expected_type, expected_course)


# --- first-touch capture (REQ-5.2.1) ---

@pytest.mark.django_db
def test_first_touch_captured_once():
    c = Client()
    c.get("/courses/?utm_source=newsletter&utm_campaign=june")
    ft = c.session.get(FIRST_TOUCH_KEY)
    assert ft["entry_path"] == "/courses/"
    assert ft["entry_type"] == "home"
    assert ft["utm"] == {"utm_source": "newsletter", "utm_campaign": "june"}
    # Second request never overwrites (first touch is first touch)
    c.get("/corporate/")
    assert c.session[FIRST_TOUCH_KEY]["entry_path"] == "/courses/"


@pytest.mark.django_db
def test_first_touch_course_entry_seeds_interest():
    course = Course.objects.create(slug="seeded", title="S", is_published=True)
    Video.objects.create(course=course, lesson_order=1, title="L1")
    c = Client()
    c.get("/courses/seeded/")
    ft = c.session[FIRST_TOUCH_KEY]
    assert ft["entry_type"] == "course"
    assert ft["entry_course"] == "seeded"


@pytest.mark.django_db
def test_first_touch_skips_non_page_paths():
    c = Client()
    c.get("/healthz")
    assert FIRST_TOUCH_KEY not in c.session


# --- attribution at signup (REQ-5.4.4) ---

@pytest.mark.django_db
def test_register_persists_attribution():
    Course.objects.create(slug="attrme", title="A", is_published=True)
    c = Client()
    c.get("/courses/attrme/?utm_source=x")  # anonymous first touch
    resp = c.post("/register/", {
        "username": "newbie1", "name": "ניב", "email": "newbie1@example.com",
        "password": "StrongPass123!",
    })
    assert resp.status_code == 302
    lp = LearnerProfile.objects.get(user__username="newbie1")
    assert lp.source_course == "attrme"
    assert lp.source_entry_type == "course"
    assert lp.source_utm == {"utm_source": "x"}


# --- return-to-intent (REQ-5.4.2) ---

@pytest.mark.django_db
def test_register_routes_to_welcome_then_next_on_skip():
    """T-F-5.2.3-1: next survives register -> /welcome/ -> skip -> original target."""
    course = Course.objects.create(slug="comeback", title="C", is_published=True)
    Video.objects.create(course=course, lesson_order=1, title="L1")
    c = Client()
    resp = c.post("/register/?next=/courses/comeback/", {
        "username": "newbie2", "name": "ניב", "email": "newbie2@example.com",
        "password": "StrongPass123!",
    })
    assert resp.url == "/welcome/"
    resp = c.post("/welcome/skip/")
    assert resp.status_code == 302
    assert resp.url == "/courses/comeback/"


@pytest.mark.django_db
def test_new_user_routed_to_welcome_on_next_page_load():
    """T-F-5.5.1-1: after signup, the next GET is intercepted to /welcome/."""
    c = Client()
    c.post("/register/", {
        "username": "newbie3", "name": "ניב", "email": "newbie3@example.com",
        "password": "StrongPass123!",
    })
    resp = c.get("/courses/")
    assert resp.status_code == 302
    assert resp.url == "/welcome/"


@pytest.mark.django_db
def test_existing_sessions_never_intercepted():
    """force_login (no signup flag) browses freely - pre-EPIC-5 users unaffected."""
    from django.contrib.auth.models import User
    u = User.objects.create_user("oldtimer", password="pass12345")
    c = Client()
    c.force_login(u)
    assert c.get("/courses/").status_code == 200
