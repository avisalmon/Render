"""
SPR-1.4 — Video Infrastructure (Bunny Stream)
TDD tests written BEFORE implementation. All should fail (RED) until features are built.
"""
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client

# ---------------------------------------------------------------------------
# F-1.4.1 — Bunny Stream env keys wired into settings
# ---------------------------------------------------------------------------

@pytest.mark.spr14
def test_bunny_settings_exist():
    """T-F-1.4.1-1: All 4 Bunny settings are defined in Django settings."""
    assert hasattr(settings, "BUNNY_API_KEY"), "Missing BUNNY_API_KEY"
    assert hasattr(settings, "BUNNY_STREAM_LIBRARY_ID"), "Missing BUNNY_STREAM_LIBRARY_ID"
    assert hasattr(settings, "BUNNY_STREAM_CDN_HOSTNAME"), "Missing BUNNY_STREAM_CDN_HOSTNAME"
    assert hasattr(settings, "BUNNY_STREAM_TOKEN_KEY"), "Missing BUNNY_STREAM_TOKEN_KEY"


@pytest.mark.spr14
def test_bunny_settings_from_env(monkeypatch):
    """T-F-1.4.1-2: Bunny settings use os.environ.get() pattern (verified by code inspection)."""
    # Verify that settings.py contains the os.environ.get pattern for all 4 keys
    import inspect

    import mysite.settings as s
    source = inspect.getsource(s)
    for key in ["BUNNY_API_KEY", "BUNNY_STREAM_LIBRARY_ID", "BUNNY_STREAM_CDN_HOSTNAME", "BUNNY_STREAM_TOKEN_KEY"]:
        assert f'os.environ.get("{key}"' in source or f"os.environ.get('{key}'" in source, \
            f"{key} should use os.environ.get() in settings.py"


# ---------------------------------------------------------------------------
# F-1.4.2 — Video model + Course model + admin registration
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_course_model_fields():
    """T-F-1.4.2-1: Course model has title, slug, description."""
    from app.models import Course
    fields = {f.name for f in Course._meta.get_fields()}
    assert "title" in fields
    assert "slug" in fields
    assert "description" in fields


@pytest.mark.spr14
@pytest.mark.django_db
def test_video_model_fields():
    """T-F-1.4.2-2: Video model has all required fields."""
    from app.models import Video
    fields = {f.name for f in Video._meta.get_fields()}
    for field in ["bunny_video_id", "title", "duration_seconds", "course", "lesson_order", "is_free_preview"]:
        assert field in fields, f"Missing field: {field}"


@pytest.mark.spr14
def test_video_registered_in_admin():
    """T-F-1.4.2-3: Video model is registered in Django admin."""
    from django.contrib import admin

    from app.models import Video
    assert Video in admin.site._registry, "Video not registered in admin"


@pytest.mark.spr14
def test_course_registered_in_admin():
    """T-F-1.4.2-4: Course model is registered in Django admin."""
    from django.contrib import admin

    from app.models import Course
    assert Course in admin.site._registry, "Course not registered in admin"


# ---------------------------------------------------------------------------
# F-1.4.3 — Embedded responsive Bunny player
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
@pytest.mark.django_db
def test_lesson_page_renders_iframe():
    """T-F-1.4.3-1: Lesson page contains Bunny iframe."""
    from django.test import override_settings

    from app.models import Course, Video
    course = Course.objects.create(title="Test Course", slug="test-course", description="Test")
    Video.objects.create(
        course=course, bunny_video_id="test-vid-123", title="Lesson 1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    client = Client()
    with override_settings(BUNNY_STREAM_LIBRARY_ID="test-lib-999"):
        resp = client.get("/course/test-course/lesson/1/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "<iframe" in content
    assert "iframe.mediadelivery.net" in content or settings.BUNNY_STREAM_CDN_HOSTNAME in content


@pytest.mark.spr14
@pytest.mark.django_db
def test_player_responsive_aspect_ratio():
    """T-F-1.4.3-2: Player wrapper uses 16:9 aspect ratio."""
    from django.test import override_settings

    from app.models import Course, Video
    course = Course.objects.create(title="Test Course 2", slug="test-course-2", description="Test")
    Video.objects.create(
        course=course, bunny_video_id="test-vid-456", title="Lesson 1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    client = Client()
    with override_settings(BUNNY_STREAM_LIBRARY_ID="test-lib-999"):
        resp = client.get("/course/test-course-2/lesson/1/")
    content = resp.content.decode()
    # 16:9 responsiveness is provided by the .lesson-player wrapper
    # (padding-bottom: 56.25% defined in static/style.css). Assert the wrapper
    # renders rather than the CSS value, which lives in the external stylesheet.
    assert 'class="lesson-player' in content


# ---------------------------------------------------------------------------
# F-1.4.4 — Signed playback URLs
# ---------------------------------------------------------------------------

@pytest.mark.spr14
def test_generate_signed_url():
    """T-F-1.4.4-1: generate_signed_url() produces URL with token and expiry."""
    from app.bunny import generate_signed_url
    url = generate_signed_url("test-video-id-abc")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "token" in params, "Signed URL must contain 'token' param"
    assert "expires" in params, "Signed URL must contain 'expires' param"
    # Expiry should be within 24h from now
    expires = int(params["expires"][0])
    now = int(time.time())
    assert expires > now, "Expiry must be in the future"
    assert expires <= now + 86400 + 60, "Expiry must be within 24h"


@pytest.mark.spr14
@pytest.mark.django_db
def test_paid_video_without_entitlement_returns_403():
    """T-F-1.4.4-2: Paid video (is_free_preview=False) returns 403 for user without entitlement."""
    from app.models import Course, Video
    course = Course.objects.create(title="Paid Course", slug="paid-course", description="Paid")
    Video.objects.create(
        course=course, bunny_video_id="paid-vid-789", title="Paid Lesson",
        duration_seconds=600, lesson_order=1, is_free_preview=False,
    )
    user = User.objects.create_user(username="testuser", password="testpass123")
    client = Client()
    client.login(username="testuser", password="testpass123")
    resp = client.get("/course/paid-course/lesson/1/")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# F-1.4.5 — UserVideoProgress model + heartbeat endpoint
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_user_video_progress_model_fields():
    """T-F-1.4.5-1: UserVideoProgress has all required fields."""
    from app.models import UserVideoProgress
    fields = {f.name for f in UserVideoProgress._meta.get_fields()}
    for field in ["user", "video", "last_position_seconds", "percent_watched", "completed_at"]:
        assert field in fields, f"Missing field: {field}"


@pytest.mark.spr14
@pytest.mark.django_db
def test_heartbeat_endpoint_accepts_post():
    """T-F-1.4.5-2: POST /api/video-progress/ with valid data returns 200."""
    from app.models import Course, Video
    course = Course.objects.create(title="HB Course", slug="hb-course", description="HB")
    video = Video.objects.create(
        course=course, bunny_video_id="hb-vid-1", title="HB Lesson",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    user = User.objects.create_user(username="hbuser", password="testpass123")
    client = Client()
    client.login(username="hbuser", password="testpass123")
    resp = client.post(
        "/api/video-progress/",
        data=json.dumps({"video_id": video.id, "position": 120, "percent": 40.0}),
        content_type="application/json",
    )
    assert resp.status_code == 200


@pytest.mark.spr14
@pytest.mark.django_db
def test_heartbeat_updates_existing_progress():
    """T-F-1.4.5-3: Second heartbeat updates existing record, no duplicate."""
    from app.models import Course, UserVideoProgress, Video
    course = Course.objects.create(title="HB2 Course", slug="hb2-course", description="HB2")
    video = Video.objects.create(
        course=course, bunny_video_id="hb2-vid-1", title="HB2 Lesson",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    user = User.objects.create_user(username="hb2user", password="testpass123")
    client = Client()
    client.login(username="hb2user", password="testpass123")
    # First heartbeat
    client.post(
        "/api/video-progress/",
        data=json.dumps({"video_id": video.id, "position": 60, "percent": 20.0}),
        content_type="application/json",
    )
    # Second heartbeat
    client.post(
        "/api/video-progress/",
        data=json.dumps({"video_id": video.id, "position": 120, "percent": 40.0}),
        content_type="application/json",
    )
    assert UserVideoProgress.objects.filter(user=user, video=video).count() == 1
    progress = UserVideoProgress.objects.get(user=user, video=video)
    assert progress.last_position_seconds == 120
    assert progress.percent_watched == pytest.approx(40.0, abs=0.1)


# ---------------------------------------------------------------------------
# F-1.4.6 — Resume playback from last_position
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_lesson_page_includes_last_position():
    """T-F-1.4.6-1: Lesson page context includes last_position_seconds for user with progress."""
    from app.models import Course, UserVideoProgress, Video
    course = Course.objects.create(title="Resume Course", slug="resume-course", description="R")
    video = Video.objects.create(
        course=course, bunny_video_id="resume-vid-1", title="Resume Lesson",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    user = User.objects.create_user(username="resumeuser", password="testpass123")
    UserVideoProgress.objects.create(
        user=user, video=video, last_position_seconds=150, percent_watched=50.0,
    )
    client = Client()
    client.login(username="resumeuser", password="testpass123")
    resp = client.get("/course/resume-course/lesson/1/")
    assert resp.status_code == 200
    # Check that the page contains the last position for JS to pick up
    content = resp.content.decode()
    assert "150" in content  # last_position_seconds should appear in page


# ---------------------------------------------------------------------------
# F-1.4.7 — Course progress aggregation
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_course_detail_shows_progress():
    """T-F-1.4.7-1: Course page shows correct progress % for logged-in user."""
    from app.models import Course, UserVideoProgress, Video
    course = Course.objects.create(title="Prog Course", slug="prog-course", description="P")
    v1 = Video.objects.create(
        course=course, bunny_video_id="prog-v1", title="L1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    v2 = Video.objects.create(
        course=course, bunny_video_id="prog-v2", title="L2",
        duration_seconds=300, lesson_order=2, is_free_preview=True,
    )
    user = User.objects.create_user(username="proguser", password="testpass123")
    # User watched 100% of v1, 0% of v2 → 50% course progress
    UserVideoProgress.objects.create(user=user, video=v1, last_position_seconds=300, percent_watched=100.0)
    client = Client()
    client.login(username="proguser", password="testpass123")
    resp = client.get("/course/prog-course/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "50" in content  # 50% progress


@pytest.mark.spr14
@pytest.mark.django_db
def test_course_complete_at_95_percent():
    """T-F-1.4.7-2: Course marked complete when all videos >= 95% watched."""
    from app.models import Course, UserVideoProgress, Video
    course = Course.objects.create(title="Complete Course", slug="complete-course", description="C")
    v1 = Video.objects.create(
        course=course, bunny_video_id="comp-v1", title="L1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    v2 = Video.objects.create(
        course=course, bunny_video_id="comp-v2", title="L2",
        duration_seconds=300, lesson_order=2, is_free_preview=True,
    )
    user = User.objects.create_user(username="compuser", password="testpass123")
    UserVideoProgress.objects.create(user=user, video=v1, last_position_seconds=290, percent_watched=96.0)
    UserVideoProgress.objects.create(user=user, video=v2, last_position_seconds=285, percent_watched=95.0)
    client = Client()
    client.login(username="compuser", password="testpass123")
    resp = client.get("/course/complete-course/")
    content = resp.content.decode()
    assert resp.status_code == 200
    # Should indicate 100% or "complete"
    assert "100" in content or "complete" in content.lower()


# ---------------------------------------------------------------------------
# F-1.4.8 — Free preview gating
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_free_preview_accessible_to_anonymous():
    """T-F-1.4.8-1: Free preview video returns 200 for anonymous user."""
    from app.models import Course, Video
    course = Course.objects.create(title="Free Course", slug="free-course", description="Free")
    Video.objects.create(
        course=course, bunny_video_id="free-vid-1", title="Free Lesson",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    client = Client()
    resp = client.get("/course/free-course/lesson/1/")
    assert resp.status_code == 200


@pytest.mark.spr14
@pytest.mark.django_db
def test_non_preview_redirects_anonymous_to_login():
    """T-F-1.4.8-2: Non-preview video redirects anonymous users to the
    context-aware wall, preserving next (updated by REQ-5.1.2/5.4.1)."""
    from app.models import Course, Video
    course = Course.objects.create(title="Paid Course 2", slug="paid-course-2", description="Paid")
    Video.objects.create(
        course=course, bunny_video_id="paid-vid-2", title="Paid Lesson",
        duration_seconds=300, lesson_order=1, is_free_preview=False,
    )
    client = Client()
    resp = client.get("/course/paid-course-2/lesson/1/")
    assert resp.status_code == 302
    assert resp.url.startswith("/join/")
    assert "next=/course/paid-course-2/lesson/1/" in resp.url


# ---------------------------------------------------------------------------
# F-1.4.13 — Home auto-redirect to last watched lesson (REQ-1.3.16)
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_home_shows_continue_watching_card():
    """T-F-1.4.13-1: Logged-in user with UserVideoProgress sees a 'Continue watching' card on home page."""
    from app.models import Course, UserVideoProgress, Video
    course = Course.objects.create(
        title="Resume Course", slug="resume-course", description="Test", is_published=True
    )
    video = Video.objects.create(
        course=course, bunny_video_id="res-vid-1", title="Lesson 1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    user = User.objects.create_user(username="resumeuser", password="testpass123")
    UserVideoProgress.objects.create(user=user, video=video, percent_watched=50)
    client = Client()
    client.login(username="resumeuser", password="testpass123")
    resp = client.get("/")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "resume-course" in content or "Lesson 1" in content or "Resume Course" in content


@pytest.mark.spr14
@pytest.mark.django_db
def test_home_no_redirect_without_progress():
    """T-F-1.4.13-2: Logged-in user with no UserVideoProgress sees normal home page (200)."""
    user = User.objects.create_user(username="freshuser", password="testpass123")
    client = Client()
    client.login(username="freshuser", password="testpass123")
    resp = client.get("/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# F-1.4.14 — Volume persistence: localStorage key in lesson template (REQ-1.3.15)
# ---------------------------------------------------------------------------

@pytest.mark.spr14
@pytest.mark.django_db
def test_lesson_template_has_volume_localStorage_key():
    """T-F-1.4.14-1: Lesson page HTML contains the babook_volume localStorage key (auth required)."""
    from app.models import Course, Video
    course = Course.objects.create(title="Vol Course", slug="vol-course", description="Vol", is_published=True)
    Video.objects.create(
        course=course, bunny_video_id="vol-vid-1", title="Lesson 1",
        duration_seconds=300, lesson_order=1, is_free_preview=True,
    )
    user = User.objects.create_user(username="voluser", password="testpass123")
    client = Client()
    client.login(username="voluser", password="testpass123")
    resp = client.get("/courses/vol-course/lesson/1/")
    assert resp.status_code == 200
    assert "babook_volume" in resp.content.decode("utf-8")
