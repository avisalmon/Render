"""
EPIC-4 — Studio/local sync safety (REQ-4.6):
studio_edited_at marker, course-detail API, pull command, and the push guard.
"""
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import Client, override_settings
from django.urls import reverse

from app.models import Course, Video


def _author():
    u = User.objects.create_user("a2", password="pass12345", is_staff=True)
    return u


def _client():
    c = Client()
    c.force_login(_author())
    return c


# --- marker is set on Studio edits ---

@pytest.mark.django_db
def test_course_edit_marks_studio_edited():
    course = Course.objects.create(slug="mk", title="M")
    assert course.studio_edited_at is None
    _client().post(reverse("studio_course_edit", args=["mk"]),
                   {"title": "M2", "domain": "ai", "track": "ai-l1", "difficulty": "beginner"})
    course.refresh_from_db()
    assert course.studio_edited_at is not None


@pytest.mark.django_db
def test_lesson_save_marks_studio_edited():
    course = Course.objects.create(slug="mk2", title="M")
    _client().post(reverse("studio_lesson_new", args=["mk2"]),
                   {"title": "L1", "notes_markdown": "x", "duration_seconds": "0"})
    course.refresh_from_db()
    assert course.studio_edited_at is not None


# --- course-detail API ---

@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_course_detail_api_returns_full_course():
    course = Course.objects.create(slug="det", title="Detail", domain="ai", track="ai-l1")
    Video.objects.create(course=course, lesson_order=1, title="L1", notes_markdown="## hi",
                         reflection_prompt="q?")
    resp = Client().get(reverse("api_courses_detail", args=["det"]), HTTP_AUTHORIZATION="Bearer k")
    assert resp.status_code == 200
    data = resp.json()
    assert data["course"]["domain"] == "ai"
    assert len(data["videos"]) == 1
    assert data["videos"][0]["reflection_prompt"] == "q?"


@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_course_detail_api_requires_key():
    Course.objects.create(slug="det2", title="D")
    resp = Client().get(reverse("api_courses_detail", args=["det2"]))  # no Bearer header
    assert resp.status_code == 401


@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_list_api_includes_studio_edited_at():
    Course.objects.create(slug="li", title="L")
    resp = Client().get(reverse("api_courses_list"), HTTP_AUTHORIZATION="Bearer k")
    assert "studio_edited_at" in resp.json()["courses"][0]


# --- pull command (local <- prod), urllib mocked ---

@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_pull_command_rebuilds_local():
    payload = {
        "course": {"slug": "pulled", "title": "Pulled", "domain": "ai", "track": "ai-l1",
                   "difficulty": "beginner", "is_published": True, "studio_edited_at": None},
        "videos": [
            {"lesson_order": 1, "title": "One", "bunny_video_id": "b1", "notes_markdown": "n1"},
            {"lesson_order": 2, "title": "Two", "bunny_video_id": "b2", "notes_markdown": "n2"},
        ],
        "materials": [],
    }
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    with patch("app.management.commands.pull_course_from_production.urllib.request.urlopen",
               return_value=resp):
        call_command("pull_course_from_production", "pulled", "--target", "http://x")
    course = Course.objects.get(slug="pulled")
    assert course.title == "Pulled" and course.domain == "ai"
    assert course.videos.count() == 2


# --- push guard ---

@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_push_guard_blocks_when_remote_studio_edited():
    """If the remote course was edited in the Studio and local is older, push aborts."""
    Course.objects.create(slug="guarded", title="G")  # local studio_edited_at = None
    remote = {"course": {"studio_edited_at": "2099-01-01T00:00:00+00:00"}}
    resp = MagicMock()
    resp.read.return_value = json.dumps(remote).encode("utf-8")
    with patch("urllib.request.urlopen", return_value=resp):
        with pytest.raises(CommandError) as exc:
            call_command("push_course_to_production", "guarded", "--target", "https://x")
    assert "OVERWRITE" in str(exc.value) or "Studio" in str(exc.value)


@override_settings(COURSE_MGMT_API_KEY="k")
@pytest.mark.django_db
def test_push_force_overrides_guard():
    """--force skips the guard (the actual POST is mocked)."""
    Course.objects.create(slug="forced", title="F")
    Video.objects.create(course=Course.objects.get(slug="forced"), lesson_order=1, title="L")
    sent = {}

    def fake_post(self, target, api_key, path, data):
        sent["path"] = path
        return {"ok": True}

    with patch("app.management.commands.push_course_to_production.Command._post_json", fake_post):
        call_command("push_course_to_production", "forced", "--target", "https://x", "--force")
    assert "sync" in sent.get("path", "")
