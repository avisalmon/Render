"""
Open-access course model (paywall removed).

The site is fully free: there is no pricing page, no tier selection, and no
entitlement-based video gating. A login is the only gate — the moment a
logged-in user opens a lesson they are auto-enrolled and every lesson is open.
Run: pytest tests/test_spr_1_5.py -v
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, Enrollment, Video

pytestmark = pytest.mark.django_db


# --- No pricing surface anymore ---


class TestNoPricing:
    def test_pricing_page_gone(self):
        client = Client()
        assert client.get("/pricing/").status_code == 404

    def test_choose_tier_gone(self):
        client = Client()
        assert client.post("/pricing/choose/", {"tier": "base"}).status_code == 404


# --- Open access: login required, then everything is open ---


class TestOpenAccess:
    @pytest.fixture(autouse=True)
    def setup_course(self):
        self.course = Course.objects.create(title="Test Course", slug="test-course", is_published=True)
        self.lesson1 = Video.objects.create(
            course=self.course, bunny_video_id="v1", title="Lesson 1",
            lesson_order=1, is_free_preview=True,
        )
        # A formerly "paid" lesson — now open like any other.
        self.lesson2 = Video.objects.create(
            course=self.course, bunny_video_id="v2", title="Lesson 2",
            lesson_order=2, is_free_preview=False,
        )

    def test_anonymous_is_sent_to_login(self):
        client = Client()
        resp = client.get("/course/test-course/lesson/2/")
        assert resp.status_code == 302  # login is a must

    def test_any_logged_in_user_can_watch_any_lesson(self):
        User.objects.create_user("learner", password="pass123")
        client = Client()
        client.login(username="learner", password="pass123")
        # No tier, no enrollment step — still gets in.
        assert client.get("/course/test-course/lesson/1/").status_code == 200
        assert client.get("/course/test-course/lesson/2/").status_code == 200

    def test_opening_a_lesson_auto_enrolls(self):
        user = User.objects.create_user("auto", password="pass123")
        client = Client()
        client.login(username="auto", password="pass123")
        assert not Enrollment.objects.filter(user=user, course=self.course).exists()
        client.get("/courses/test-course/lesson/1/")
        assert Enrollment.objects.filter(user=user, course=self.course).exists()
