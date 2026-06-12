"""
EPIC-3 — Training Platform & Course Library.
Covers: taxonomy + drill-down catalog (REQ-3.1/3.2), intros + cross-listing
(REQ-3.3/3.4), reflection lessons (REQ-3.5), sync deletion (REQ-3.6), and the
profile courses view (REQ-3.5.3).
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse

from app.models import (
    Course,
    Enrollment,
    LessonReflection,
    UserVideoProgress,
    Video,
)
from app.taxonomy import build_catalog


def _course(slug, domain="matazim", track="software", published=True, title=None):
    return Course.objects.create(
        slug=slug, title=title or slug, domain=domain, track=track,
        is_published=published,
    )


# --- REQ-3.1.3 build_catalog grouping ---

@pytest.mark.django_db
def test_build_catalog_groups_by_domain_and_track():
    """T-F-3.1.3-1: a course lands in its (domain, track) bucket."""
    c = _course("py-basics", "matazim", "software")
    domains, uncategorized = build_catalog(Course.objects.filter(is_published=True))
    matazim = next(d for d in domains if d["key"] == "matazim")
    software = next(t for t in matazim["tracks"] if t["key"] == "software")
    assert c in software["courses"]
    assert uncategorized == []


@pytest.mark.django_db
def test_build_catalog_uncategorized_bucket():
    """T-F-3.1.3-2: a course with an unknown track is surfaced as uncategorized."""
    c = _course("orphan", "matazim", "")  # empty track is not a real track
    _domains, uncategorized = build_catalog(Course.objects.filter(is_published=True))
    assert c in uncategorized


# --- REQ-3.4.1 cross-listing ---

@pytest.mark.django_db
def test_cross_listing_extra_slugs():
    """T-F-3.2.2-1: Python (primary matazim/software) also appears in ai-l3 via extra_slugs."""
    py = _course("python", "matazim", "software")
    domains, _ = build_catalog(Course.objects.filter(is_published=True))
    ai = next(d for d in domains if d["key"] == "ai")
    l3 = next(t for t in ai["tracks"] if t["key"] == "ai-l3")
    assert py in l3["courses"]  # cross-listed
    matazim = next(d for d in domains if d["key"] == "matazim")
    software = next(t for t in matazim["tracks"] if t["key"] == "software")
    assert py in software["courses"]  # still primary


@pytest.mark.django_db
def test_cross_listed_course_keeps_primary_placement():
    """T-F-3.2.2-2: MicroPython (no primary track) shows in matazim/hardware AND uncategorized."""
    mp = _course("micropython-thonny", "matazim", "")
    domains, uncategorized = build_catalog(Course.objects.filter(is_published=True))
    matazim = next(d for d in domains if d["key"] == "matazim")
    hardware = next(t for t in matazim["tracks"] if t["key"] == "hardware")
    assert mp in hardware["courses"]
    assert mp in uncategorized


# --- REQ-3.3.1 intros ---

@pytest.mark.django_db
def test_intro_course_featured_first():
    """T-F-3.2.1-1: ai-l3's intro_slug course is marked as the track intro."""
    intro = _course("ai-fundamentals", "ai", "ai-l3")
    domains, _ = build_catalog(Course.objects.filter(is_published=True))
    ai = next(d for d in domains if d["key"] == "ai")
    l3 = next(t for t in ai["tracks"] if t["key"] == "ai-l3")
    assert l3["intro"] == intro
    assert l3["courses"][0] == intro


# --- REQ-3.2.1/3.2.2/3.2.3 drill-down views ---

@pytest.mark.django_db
def test_catalog_drilldown_views_return_200():
    """T-F-3.1.4/5/6-1: all three catalog levels render."""
    _course("py-basics", "matazim", "software")
    client = Client()
    assert client.get(reverse("courses_catalog")).status_code == 200
    assert client.get(reverse("courses_domain", args=["matazim"])).status_code == 200
    assert client.get(reverse("courses_track", args=["matazim", "software"])).status_code == 200


@pytest.mark.django_db
def test_unknown_domain_404():
    """T-F-3.1.5-2: an unknown domain is a 404, not a crash."""
    client = Client()
    assert client.get(reverse("courses_domain", args=["nope"])).status_code == 404


# --- REQ-3.5 reflection lessons ---

@pytest.mark.django_db
def test_reflection_endpoint_saves_and_completes():
    """T-F-3.3.2-1: posting a reflection saves it, returns an AI reply, and completes the lesson."""
    user = User.objects.create_user("refuser", password="pass12345")
    course = _course("journey", "ai", "ai-l1")
    video = Video.objects.create(
        course=course, lesson_order=1, title="L1", bunny_video_id="",
        is_free_preview=True, reflection_prompt="What did you try?",
    )
    client = Client()
    client.force_login(user)
    with patch("app.views._generate_reflection_reply", return_value="Great job, keep going."):
        resp = client.post(
            reverse("lesson_reflect", args=[video.id]),
            data=json.dumps({"text": "I tried Suno and made a song"}),
            content_type="application/json",
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["ai_reply"] == "Great job, keep going."
    assert LessonReflection.objects.filter(user=user, video=video).count() == 1
    prog = UserVideoProgress.objects.get(user=user, video=video)
    assert prog.quiz_passed is True


@pytest.mark.django_db
def test_reflection_endpoint_rejects_empty():
    """T-F-3.3.2-2: empty reflection text is rejected."""
    user = User.objects.create_user("refuser2", password="pass12345")
    course = _course("journey2", "ai", "ai-l1")
    video = Video.objects.create(
        course=course, lesson_order=1, title="L1", bunny_video_id="",
        is_free_preview=True, reflection_prompt="What did you try?",
    )
    client = Client()
    client.force_login(user)
    resp = client.post(reverse("lesson_reflect", args=[video.id]),
                       data=json.dumps({"text": "  "}), content_type="application/json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_text_only_lesson_has_no_player():
    """T-F-3.3.4-1: a lesson without a bunny video renders text-only (no player)."""
    course = _course("textonly", "ai", "ai-l1")
    Video.objects.create(course=course, lesson_order=1, title="Text lesson",
                         bunny_video_id="", is_free_preview=True,
                         notes_markdown="## Hello\nsome content")
    client = Client()
    resp = client.get(reverse("courses_lesson", args=["textonly", 1]))
    assert resp.status_code == 200
    assert "lesson-player" not in resp.content.decode("utf-8", "ignore")


# --- REQ-3.5.3 profile ---

@pytest.mark.django_db
def test_profile_shows_courses_not_reflections():
    """T-F-3.3.3-1: the profile shows enrolled courses, never the user's reflections."""
    user = User.objects.create_user("profuser", password="pass12345")
    course = _course("mycourse", "ai", "ai-l1", title="My Course")
    Enrollment.objects.create(user=user, course=course)
    video = Video.objects.create(course=course, lesson_order=1, title="L1",
                                 bunny_video_id="", reflection_prompt="Q?")
    LessonReflection.objects.create(user=user, video=video, prompt="Q?",
                                    user_text="SECRET_REFLECTION_TEXT", ai_reply="ok")
    client = Client()
    client.force_login(user)
    resp = client.get(reverse("profile"))
    html = resp.content.decode("utf-8", "ignore")
    assert resp.status_code == 200
    assert "My Course" in html
    assert "SECRET_REFLECTION_TEXT" not in html


# --- REQ-3.6.1 sync deletes removed lessons ---

@override_settings(COURSE_MGMT_API_KEY="testkey-123")
@pytest.mark.django_db
def test_sync_deletes_removed_lessons():
    """T-F-3.4.1-1: pushing a course with fewer lessons deletes the extras on the target."""
    course = _course("synced", "matazim", "software")
    for i in range(1, 4):
        Video.objects.create(course=course, lesson_order=i, title=f"L{i}", bunny_video_id="x")
    assert course.videos.count() == 3
    payload = {
        "course": {"slug": "synced", "title": "Synced", "is_published": True,
                   "domain": "matazim", "track": "software"},
        "videos": [
            {"lesson_order": 1, "title": "L1", "bunny_video_id": "x"},
            {"lesson_order": 2, "title": "L2", "bunny_video_id": "x"},
        ],
    }
    client = Client()
    resp = client.post(
        reverse("api_courses_sync"),
        data=json.dumps(payload), content_type="application/json",
        HTTP_AUTHORIZATION="Bearer testkey-123",
    )
    assert resp.status_code == 200
    course.refresh_from_db()
    assert course.videos.count() == 2  # lesson 3 deleted
    assert not course.videos.filter(lesson_order=3).exists()
