"""
EPIC-4 — Course Authoring Studio.
Covers access control (REQ-4.1), manual CRUD + reorder + preview (REQ-4.2),
and the automated pipeline orchestration with mocked heavy steps (REQ-4.3).
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from app.models import AuthoringJob, Course, Video


def _author():
    u = User.objects.create_user("author1", password="pass12345")
    u.profile.is_author = True
    u.profile.save()
    return u


def _client_as(user):
    c = Client()
    c.force_login(user)
    return c


# --- REQ-4.1 access ---

@pytest.mark.django_db
def test_non_author_blocked():
    u = User.objects.create_user("plain", password="pass12345")
    resp = _client_as(u).get(reverse("studio_home"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_redirected_to_login():
    resp = Client().get(reverse("studio_home"))
    assert resp.status_code == 302
    assert "/login/" in resp.url


@pytest.mark.django_db
def test_author_can_open_studio():
    resp = _client_as(_author()).get(reverse("studio_home"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_is_implicit_author():
    staff = User.objects.create_user("staff1", password="pass12345", is_staff=True)
    assert _client_as(staff).get(reverse("studio_home")).status_code == 200


# --- REQ-4.2 manual CRUD ---

@pytest.mark.django_db
def test_create_course():
    c = _client_as(_author())
    resp = c.post(reverse("studio_course_create"), {
        "title": "My New Course", "description": "d", "domain": "ai",
        "track": "ai-l1", "difficulty": "beginner",
    })
    assert resp.status_code == 302
    course = Course.objects.get(title="My New Course")
    assert course.domain == "ai" and course.track == "ai-l1"
    assert course.is_published is False


@pytest.mark.django_db
def test_edit_course_metadata():
    _author_u = _author()
    course = Course.objects.create(slug="edit-me", title="Old", domain="matazim", track="software")
    c = _client_as(_author_u)
    c.post(reverse("studio_course_edit", args=["edit-me"]), {
        "title": "New Title", "description": "x", "domain": "ai",
        "track": "ai-l2", "difficulty": "advanced", "is_published": "on",
    })
    course.refresh_from_db()
    assert course.title == "New Title"
    assert course.domain == "ai" and course.track == "ai-l2"
    assert course.is_published is True


@pytest.mark.django_db
def test_delete_course():
    Course.objects.create(slug="del-me", title="Del")
    c = _client_as(_author())
    c.post(reverse("studio_course_delete", args=["del-me"]))
    assert not Course.objects.filter(slug="del-me").exists()


@pytest.mark.django_db
def test_publish_toggle():
    course = Course.objects.create(slug="pub-me", title="Pub", is_published=False)
    c = _client_as(_author())
    c.post(reverse("studio_course_publish", args=["pub-me"]))
    course.refresh_from_db()
    assert course.is_published is True


@pytest.mark.django_db
def test_add_and_edit_lesson():
    course = Course.objects.create(slug="lessons", title="L")
    c = _client_as(_author())
    # add
    c.post(reverse("studio_lesson_new", args=["lessons"]), {
        "title": "Lesson one", "notes_markdown": "## Hi", "bunny_video_id": "",
        "duration_seconds": "0",
    })
    v = Video.objects.get(course=course, lesson_order=1)
    assert v.title == "Lesson one"
    assert v.is_final_lesson is True  # only lesson => final
    # edit
    c.post(reverse("studio_lesson_edit", args=["lessons", 1]), {
        "title": "Lesson edited", "notes_markdown": "## Bye", "bunny_video_id": "abc",
        "reflection_prompt": "what did you try?", "duration_seconds": "120",
    })
    v.refresh_from_db()
    assert v.title == "Lesson edited"
    assert v.reflection_prompt == "what did you try?"


@pytest.mark.django_db
def test_delete_lesson():
    course = Course.objects.create(slug="dl", title="L")
    Video.objects.create(course=course, lesson_order=1, title="A")
    Video.objects.create(course=course, lesson_order=2, title="B")
    c = _client_as(_author())
    c.post(reverse("studio_lesson_delete", args=["dl", 1]))
    assert course.videos.count() == 1


@pytest.mark.django_db
def test_reorder_lessons():
    course = Course.objects.create(slug="ro", title="L")
    a = Video.objects.create(course=course, lesson_order=1, title="A")
    b = Video.objects.create(course=course, lesson_order=2, title="B")
    cc = Video.objects.create(course=course, lesson_order=3, title="C")
    c = _client_as(_author())
    resp = c.post(reverse("studio_lesson_reorder", args=["ro"]),
                  data=json.dumps({"order": [cc.id, a.id, b.id]}),
                  content_type="application/json")
    assert resp.status_code == 200
    cc.refresh_from_db(); a.refresh_from_db(); b.refresh_from_db()
    assert (cc.lesson_order, a.lesson_order, b.lesson_order) == (1, 2, 3)
    assert b.is_final_lesson is True  # last after reorder


@pytest.mark.django_db
def test_markdown_preview():
    c = _client_as(_author())
    resp = c.post(reverse("studio_markdown_preview"),
                  data=json.dumps({"markdown": "## Title\n- a\n- b"}),
                  content_type="application/json")
    assert resp.status_code == 200
    html = resp.json()["html"]
    assert "<h2" in html and "<ul" in html


# --- REQ-4.3 automated pipeline ---

@pytest.mark.django_db
def test_new_from_video_creates_job():
    c = _client_as(_author())
    with patch("app.authoring.pipeline.run_job_async") as mock_run:
        resp = c.post(reverse("studio_new_from_video"), {
            "title": "From Video", "domain": "ai", "track": "ai-l1",
            "source_type": "youtube", "source_url": "https://youtu.be/abc",
        })
    assert resp.status_code == 302
    job = AuthoringJob.objects.get(title="From Video")
    assert job.source_url == "https://youtu.be/abc"
    mock_run.assert_called_once_with(job.id)


@pytest.mark.django_db
def test_job_status_api():
    job = AuthoringJob.objects.create(title="J", status="running", progress=42, step="working")
    c = _client_as(_author())
    resp = c.get(reverse("studio_job_api", args=[job.id]))
    data = resp.json()
    assert data["status"] == "running" and data["progress"] == 42


@pytest.mark.django_db
def test_pipeline_orchestration_builds_course():
    """run_job builds a draft course with lessons (heavy steps mocked)."""
    job = AuthoringJob.objects.create(
        title="Pipeline Course", domain="ai", track="ai-l1",
        source_type="youtube", source_url="https://youtu.be/x",
    )
    segs = [{"start": 0, "end": 10, "text": "hello"},
            {"start": 300, "end": 310, "text": "world"}]
    sections = [{"title_he": "Part A", "start_sec": 0, "end_sec": 300},
                {"title_he": "Part B", "start_sec": 300, "end_sec": 600}]
    note = {"title_he": "T", "summary_he": "S", "notes_markdown": "## N"}
    p = "app.authoring.pipeline."
    with patch(p + "download_youtube", return_value="fake.mp4"), \
         patch(p + "probe_duration", return_value=600), \
         patch(p + "transcribe_with_timestamps", return_value=segs), \
         patch(p + "detect_topics", return_value=sections), \
         patch(p + "split_part", return_value=None), \
         patch(p + "bunny_create", return_value="guid-123"), \
         patch(p + "bunny_upload", return_value=None), \
         patch(p + "gen_notes", return_value=note):
        from app.authoring.pipeline import run_job
        run_job(job.id)
    job.refresh_from_db()
    assert job.status == "done"
    assert job.progress == 100
    assert job.course is not None
    assert job.course.videos.count() == 2
    assert job.course.is_published is False
    first = job.course.videos.order_by("lesson_order").first()
    assert first.bunny_video_id == "guid-123"
