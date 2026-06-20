"""
SPR-5.3 — First-visit exploration & welcome (REQ-5.3).
Welcome strip (entry-aware, dismissible, anonymous-only), no proactive
registration nudges (DEC-34), corporate "for your team" path (DEC-35).
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, Video


@pytest.mark.django_db
def test_welcome_strip_on_first_visit():
    """T-F-5.3.1-1: anonymous first visit shows the orientation strip."""
    resp = Client().get("/")
    assert "welcome-strip" in resp.content.decode()


@pytest.mark.django_db
def test_welcome_strip_acknowledges_entry_course():
    course = Course.objects.create(slug="camefor", title="הקורס שבגללו באתי", is_published=True)
    Video.objects.create(course=course, lesson_order=1, title="L1", is_free_preview=True)
    c = Client()
    resp = c.get("/courses/camefor/")
    assert "הקורס שבגללו באתי" in resp.content.decode()
    # strip keeps acknowledging on subsequent pages
    resp = c.get("/")
    body = resp.content.decode()
    assert "welcome-strip" in body and "camefor" in body


@pytest.mark.django_db
def test_welcome_strip_dismissed_by_cookie():
    c = Client()
    c.get("/")
    c.cookies["welcome_dismissed"] = "1"
    assert "welcome-strip" not in c.get("/").content.decode()


@pytest.mark.django_db
def test_no_strip_for_logged_in_users():
    u = User.objects.create_user("member1", password="pass12345")
    c = Client()
    c.force_login(u)
    assert "welcome-strip" not in c.get("/").content.decode()


@pytest.mark.django_db
def test_strip_has_no_register_ask():
    """T-F-5.3.2-1 (DEC-34): the strip orients - it never asks to register."""
    resp = Client().get("/")
    body = resp.content.decode()
    strip = body.split('id="welcome-strip"')[1].split("</div>\n  </div>")[0]
    assert "הרשמה" not in strip and "/register" not in strip and "/join" not in strip


