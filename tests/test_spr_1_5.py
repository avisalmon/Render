"""
SPR-1.5 — Billing (Mock Mode)
Tests for Entitlement model, tier selection, and video access gating.
Run: pytest tests/test_spr_1_5.py -v
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, Entitlement, Video

pytestmark = pytest.mark.django_db


# --- Entitlement model ---


class TestEntitlementModel:
    def test_entitlement_created_with_default_free(self):
        user = User.objects.create_user("u1", password="pass123")
        ent = Entitlement.objects.create(user=user)
        assert ent.tier == "free"

    def test_has_video_access_free(self):
        user = User.objects.create_user("u2", password="pass123")
        ent = Entitlement.objects.create(user=user, tier="free")
        assert ent.has_video_access is False

    def test_has_video_access_base(self):
        user = User.objects.create_user("u3", password="pass123")
        ent = Entitlement.objects.create(user=user, tier="base")
        assert ent.has_video_access is True

    def test_has_video_access_master(self):
        user = User.objects.create_user("u4", password="pass123")
        ent = Entitlement.objects.create(user=user, tier="master")
        assert ent.has_video_access is True

    def test_has_copilot_access_only_master(self):
        user = User.objects.create_user("u5", password="pass123")
        ent = Entitlement.objects.create(user=user, tier="base")
        assert ent.has_copilot_access is False
        ent.tier = "master"
        assert ent.has_copilot_access is True


# --- Pricing page ---


class TestPricingPage:
    def test_pricing_page_returns_200(self):
        client = Client()
        response = client.get("/pricing/")
        assert response.status_code == 200

    def test_pricing_page_shows_three_tiers(self):
        client = Client()
        response = client.get("/pricing/")
        content = response.content.decode()
        assert "Free" in content
        assert "Base" in content
        assert "Master" in content


# --- Choose tier (mock billing) ---


class TestChooseTier:
    def test_choose_tier_requires_login(self):
        client = Client()
        response = client.post("/pricing/choose/", {"tier": "base"})
        assert response.status_code == 302
        assert "/accounts/login/" in response.url or "/login/" in response.url

    def test_choose_tier_sets_entitlement(self):
        user = User.objects.create_user("buyer1", password="pass123")
        client = Client()
        client.login(username="buyer1", password="pass123")
        response = client.post("/pricing/choose/", {"tier": "master"})
        assert response.status_code == 302
        ent = Entitlement.objects.get(user=user)
        assert ent.tier == "master"

    def test_choose_tier_updates_existing(self):
        user = User.objects.create_user("buyer2", password="pass123")
        Entitlement.objects.create(user=user, tier="base")
        client = Client()
        client.login(username="buyer2", password="pass123")
        client.post("/pricing/choose/", {"tier": "free"})
        ent = Entitlement.objects.get(user=user)
        assert ent.tier == "free"

    def test_choose_invalid_tier_defaults_to_free(self):
        user = User.objects.create_user("buyer3", password="pass123")
        client = Client()
        client.login(username="buyer3", password="pass123")
        client.post("/pricing/choose/", {"tier": "hacker_tier"})
        ent = Entitlement.objects.get(user=user)
        assert ent.tier == "free"


# --- Video access gating ---


class TestVideoGating:
    @pytest.fixture(autouse=True)
    def setup_course(self):
        self.course = Course.objects.create(title="Test Course", slug="test-course")
        self.free_video = Video.objects.create(
            course=self.course, bunny_video_id="v1", title="Free Lesson",
            lesson_order=1, is_free_preview=True,
        )
        self.paid_video = Video.objects.create(
            course=self.course, bunny_video_id="v2", title="Paid Lesson",
            lesson_order=2, is_free_preview=False,
        )

    def test_free_preview_accessible_to_anonymous(self):
        client = Client()
        response = client.get("/course/test-course/lesson/1/")
        assert response.status_code == 200

    def test_paid_video_redirects_anonymous_to_login(self):
        client = Client()
        response = client.get("/course/test-course/lesson/2/")
        assert response.status_code == 302

    def test_paid_video_denied_for_free_tier(self):
        user = User.objects.create_user("freeuser", password="pass123")
        Entitlement.objects.create(user=user, tier="free")
        client = Client()
        client.login(username="freeuser", password="pass123")
        response = client.get("/course/test-course/lesson/2/")
        assert response.status_code == 403

    def test_paid_video_allowed_for_base_tier(self):
        user = User.objects.create_user("baseuser", password="pass123")
        Entitlement.objects.create(user=user, tier="base")
        client = Client()
        client.login(username="baseuser", password="pass123")
        response = client.get("/course/test-course/lesson/2/")
        assert response.status_code == 200

    def test_paid_video_allowed_for_master_tier(self):
        user = User.objects.create_user("masteruser", password="pass123")
        Entitlement.objects.create(user=user, tier="master")
        client = Client()
        client.login(username="masteruser", password="pass123")
        response = client.get("/course/test-course/lesson/2/")
        assert response.status_code == 200

    def test_paid_video_denied_for_no_entitlement(self):
        User.objects.create_user("noent", password="pass123")
        client = Client()
        client.login(username="noent", password="pass123")
        response = client.get("/course/test-course/lesson/2/")
        assert response.status_code == 403
