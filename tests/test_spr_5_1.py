"""
SPR-5.1 — Access model & context-aware wall (REQ-5.1, REQ-5.4.1).
Anonymous users hitting a gated action get the /join/ wall (never a bare
403/login), free exploration stays open, and the wall names the course.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, Video


def _course(slug="walled", published=True, free_first=True):
    c = Course.objects.create(slug=slug, title=f"Course {slug}", is_published=published,
                              domain="ai", track="ai-l1")
    Video.objects.create(course=c, lesson_order=1, title="L1", is_free_preview=free_first)
    Video.objects.create(course=c, lesson_order=2, title="L2", is_free_preview=False)
    return c


# --- the wall page ---

@pytest.mark.django_db
def test_wall_names_the_course_and_preserves_next():
    """T-F-5.1.2-1: the wall shows the course title, signup options, next."""
    _course("target")
    resp = Client().get("/join/?next=/courses/target/lesson/2/&course=target")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Course target" in body
    assert "/courses/target/lesson/2/" in body
    assert "google" in body.lower()


@pytest.mark.django_db
def test_wall_generic_without_course():
    resp = Client().get("/join/")
    assert resp.status_code == 200
    assert "כניסה להמשך" in resp.content.decode()


@pytest.mark.django_db
def test_wall_redirects_logged_in_users_to_next():
    u = User.objects.create_user("walled1", password="pass12345")
    c = Client()
    c.force_login(u)
    resp = c.get("/join/?next=/courses/")
    assert resp.status_code == 302
    assert resp.url == "/courses/"


# --- gated actions route to the wall (REQ-5.1.2: no bare 403/login) ---

@pytest.mark.django_db
def test_anonymous_locked_lesson_routes_to_wall():
    """T-F-5.1.2-2: non-preview lesson -> /join/ with next + course."""
    _course("gated")
    resp = Client().get("/courses/gated/lesson/2/")
    assert resp.status_code == 302
    assert resp.url.startswith("/join/")
    assert "next=/courses/gated/lesson/2/" in resp.url
    assert "course=gated" in resp.url


@pytest.mark.django_db
def test_anonymous_enroll_routes_to_wall():
    _course("enrollgate")
    resp = Client().get("/courses/enrollgate/enroll/")
    assert resp.status_code == 302
    assert resp.url.startswith("/join/")
    assert "course=enrollgate" in resp.url


# --- login is the only gate: every lesson routes anonymous users to the wall ---

@pytest.mark.django_db
def test_anonymous_first_lesson_routes_to_wall():
    """Open-access model with mandatory login: even lesson 1 sends anonymous users
    to the wall (no preview tier anymore)."""
    _course("freely")
    resp = Client().get("/courses/freely/lesson/1/")
    assert resp.status_code == 302
    assert resp.url.startswith("/join/")


@pytest.mark.django_db
def test_anonymous_catalog_and_detail_open():
    _course("browse")
    c = Client()
    assert c.get("/courses/").status_code == 200
    assert c.get("/courses/browse/").status_code == 200
