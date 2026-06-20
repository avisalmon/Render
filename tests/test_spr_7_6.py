"""
SPR-7.6 — Contact reliability. The corporate lead form/page was removed; the
team-training contact is now a direct mailto, and privacy/terms point at email.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
def test_team_training_hook_is_email():
    """A logged-in lesson page offers the team-training contact as a mailto to Avi."""
    from django.contrib.auth.models import User

    from app.models import Course, Video
    course = Course.objects.create(title="C", slug="c7", is_published=True)
    Video.objects.create(course=course, lesson_order=1, title="L1")
    u = User.objects.create_user("u76", password="pass12345")
    c = Client()
    c.force_login(u)
    body = c.get("/courses/c7/lesson/1/").content.decode()
    assert "mailto:avi.salmon@gmail.com" in body


@pytest.mark.django_db
def test_privacy_terms_offer_email_contact():
    pbody = Client().get("/privacy/").content.decode()
    tbody = Client().get("/terms/").content.decode()
    assert "privacy@babook.co.il" in pbody
    assert "support@babook.co.il" in tbody
