"""Courses catalog: thin 'continue learning' rows + 'my achievements' (certificates)."""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, CourseCertificate, Enrollment, UserVideoProgress, Video

pytestmark = pytest.mark.django_db


def test_catalog_shows_resume_and_trophy_rows():
    # An in-progress course (50%) -> "continue learning".
    c1 = Course.objects.create(title="In progress", slug="cat-c1", is_published=True)
    v1 = Video.objects.create(course=c1, lesson_order=1, title="L1")
    Video.objects.create(course=c1, lesson_order=2, title="L2")
    # A finished course -> certificate -> "my achievements".
    c2 = Course.objects.create(title="Finished course", slug="cat-c2", is_published=True)
    Video.objects.create(course=c2, lesson_order=1, title="L1")

    u = User.objects.create_user("learner", password="pass12345")
    Enrollment.objects.create(user=u, course=c1)
    UserVideoProgress.objects.create(user=u, video=v1, percent_watched=100)
    cert = CourseCertificate.objects.create(user=u, course=c2)

    c = Client()
    c.force_login(u)
    body = c.get("/courses/").content.decode()

    # Continue-learning one-line card for the in-progress course.
    assert "המשך ללמוד" in body
    assert "hcard" in body
    assert "In progress" in body
    # Achievements thin row linking to the certificate.
    assert "ההישגים שלי" in body
    assert f"/certificate/{cert.certificate_id}/" in body
    assert "Finished course" in body


def test_catalog_anonymous_has_no_resume_or_trophies():
    Course.objects.create(title="Open", slug="cat-open", is_published=True)
    body = Client().get("/courses/").content.decode()
    assert "המשך ללמוד" not in body
    assert "ההישגים שלי" not in body
