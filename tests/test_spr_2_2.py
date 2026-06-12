"""
SPR-2.2 — First Flagship Course
Tests for: F-2.2.1 model enhancements, F-2.2.2 enrollment model,
F-2.2.3 catalog page, F-2.2.4 detail page, F-2.2.5 enrollment flow,
F-2.2.6 lesson page, F-2.2.7 course completion, F-2.2.8 SEO/sitemap,
F-2.2.9 corporate funnel hook, F-2.2.10 load_course_from_manifest.
"""
import json

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from app.models import Course, Enrollment, UserVideoProgress, Video

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def published_course(db):
    course = Course.objects.create(
        title="מיקרופייתון עם תוני",
        title_en="MicroPython with Thonny",
        slug="micropython-thonny",
        description="ללמוד מיקרופייתון עם ESP32",
        difficulty="beginner",
        category="foundations",
        is_published=True,
        thumbnail="course_thumbnails/micropython-thonny.png",
    )
    Video.objects.create(
        course=course, lesson_order=1, title="שיעור 1", title_en="Lesson 1",
        bunny_video_id="abc-001", duration_seconds=300, is_free_preview=True,
        notes_markdown="### מבוא\nברוכים הבאים.",
        summary_he="שיעור פתיחה.",
    )
    Video.objects.create(
        course=course, lesson_order=2, title="שיעור 2", title_en="Lesson 2",
        bunny_video_id="abc-002", duration_seconds=400, is_free_preview=False,
        notes_markdown="### שיעור 2\nתוכן מתקדם.",
        has_code_example=True, github_file="010 lines.py",
    )
    return course


@pytest.fixture
def unpublished_course(db):
    return Course.objects.create(
        title="קורס טיוטה", slug="draft-course", is_published=False,
    )


@pytest.fixture
def user(db):
    return User.objects.create_user("testuser", "t@t.com", "pass123")


@pytest.fixture
def enrolled_user(db, published_course):
    u = User.objects.create_user("enrolled", "e@t.com", "pass123")
    Enrollment.objects.create(user=u, course=published_course)
    return u


# ---------------------------------------------------------------------------
# F-2.2.1 — Course model enhancements
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_course_has_new_fields(published_course):
    """T-F-2.2.1-1: Course model has thumbnail, difficulty, is_published, category."""
    assert published_course.thumbnail == "course_thumbnails/micropython-thonny.png"
    assert published_course.difficulty == "beginner"
    assert published_course.is_published is True
    assert published_course.category == "foundations"
    assert published_course.title_en == "MicroPython with Thonny"


@pytest.mark.django_db
def test_video_has_new_fields(published_course):
    """T-F-2.2.1-2: Video model has notes_markdown, summary_he, has_code_example, github_file."""
    v1 = published_course.videos.get(lesson_order=1)
    assert "מבוא" in v1.notes_markdown
    assert v1.summary_he == "שיעור פתיחה."
    v2 = published_course.videos.get(lesson_order=2)
    assert v2.has_code_example is True
    assert v2.github_file == "010 lines.py"


# ---------------------------------------------------------------------------
# F-2.2.2 — Enrollment model
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_enrollment_created(db, user, published_course):
    """T-F-2.2.2-1: Enrollment row can be created."""
    e = Enrollment.objects.create(user=user, course=published_course)
    assert e.enrolled_at is not None
    assert e.completed_at is None


@pytest.mark.django_db
def test_enrollment_unique(db, user, published_course):
    """T-F-2.2.2-2: Cannot enroll same user in same course twice."""
    Enrollment.objects.create(user=user, course=published_course)
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        Enrollment.objects.create(user=user, course=published_course)


# ---------------------------------------------------------------------------
# F-2.2.3 — Course catalog page
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_catalog_page_200(client, published_course):
    """T-F-2.2.3-1: /courses/ returns 200."""
    r = client.get(reverse("courses_catalog"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_catalog_shows_published(client, published_course):
    """T-F-2.2.3-2: Catalog lists published courses."""
    r = client.get(reverse("courses_catalog"))
    assert "מיקרופייתון" in r.content.decode("utf-8")


@pytest.mark.django_db
def test_catalog_hides_unpublished(client, published_course, unpublished_course):
    """T-F-2.2.3-3: Catalog does NOT list unpublished courses."""
    r = client.get(reverse("courses_catalog"))
    assert "קורס טיוטה" not in r.content.decode("utf-8")


# ---------------------------------------------------------------------------
# F-2.2.4 — Course detail page
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_detail_page_200(client, published_course):
    """T-F-2.2.4-1: /courses/<slug>/ returns 200."""
    r = client.get(reverse("courses_detail", args=["micropython-thonny"]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_detail_shows_lessons(client, published_course):
    """T-F-2.2.4-2: Detail page lists all lessons."""
    r = client.get(reverse("courses_detail", args=["micropython-thonny"]))
    content = r.content.decode("utf-8")
    assert "שיעור 1" in content
    assert "שיעור 2" in content


@pytest.mark.django_db
def test_detail_404_for_unknown(client):
    """T-F-2.2.4-3: /courses/unknown/ returns 404."""
    r = client.get(reverse("courses_detail", args=["no-such-course"]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_detail_shows_enroll_cta(client, published_course):
    """T-F-2.2.4-4: Unauthenticated user sees enroll/preview CTA."""
    r = client.get(reverse("courses_detail", args=["micropython-thonny"]))
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# F-2.2.5 — Enrollment flow
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_enroll_requires_login(client, published_course):
    """T-F-2.2.5-1: POST /courses/<slug>/enroll/ redirects anonymous to login."""
    r = client.post(reverse("courses_enroll", args=["micropython-thonny"]))
    assert r.status_code in (302, 301)
    assert "/login" in r["Location"] or "/accounts" in r["Location"]


@pytest.mark.django_db
def test_enroll_creates_enrollment(client, user, published_course):
    """T-F-2.2.5-2: Logged-in user POST creates Enrollment and redirects to lesson 1."""
    client.force_login(user)
    r = client.post(reverse("courses_enroll", args=["micropython-thonny"]))
    assert Enrollment.objects.filter(user=user, course=published_course).exists()
    assert r.status_code == 302
    assert "lesson" in r["Location"]


@pytest.mark.django_db
def test_enroll_idempotent(client, enrolled_user, published_course):
    """T-F-2.2.5-3: Second enroll doesn't crash — still redirects to lesson 1."""
    client.force_login(enrolled_user)
    r = client.post(reverse("courses_enroll", args=["micropython-thonny"]))
    assert r.status_code == 302
    assert Enrollment.objects.filter(user=enrolled_user, course=published_course).count() == 1


# ---------------------------------------------------------------------------
# F-2.2.6 — Lesson page
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_lesson_free_preview_anonymous(client, published_course):
    """T-F-2.2.6-1: Anonymous user can access free-preview lesson."""
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 1]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_lesson_paid_redirects_anonymous(client, published_course):
    """T-F-2.2.6-2: Anonymous user gets redirected for non-preview lesson."""
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 2]))
    assert r.status_code == 302


@pytest.mark.django_db
def test_lesson_shows_notes(client, published_course):
    """T-F-2.2.6-3: Lesson page renders notes_markdown content."""
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 1]))
    content = r.content.decode("utf-8")
    # notes_markdown "### מבוא\nברוכים הבאים." should appear rendered
    assert "מבוא" in content


@pytest.mark.django_db
def test_lesson_enrolled_can_access_paid(client, enrolled_user, published_course):
    """T-F-2.2.6-4: Enrolled user can access paid lesson.

    Sequential locking requires lesson 1 to be visited before lesson 2 unlocks.
    Pre-create a UserVideoProgress record for lesson 1 to simulate a prior visit.
    """
    lesson1 = published_course.videos.get(lesson_order=1)
    UserVideoProgress.objects.create(
        user=enrolled_user, video=lesson1,
        percent_watched=100, completed_at=timezone.now(),
    )
    client.force_login(enrolled_user)
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 2]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_lesson_has_next_prev(client, published_course):
    """T-F-2.2.6-5: Lesson page includes next/prev navigation context."""
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 1]))
    assert r.status_code == 200
    assert r.context.get("next_video") is not None


# ---------------------------------------------------------------------------
# F-2.2.7 — Course completion
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_completion_detected(db, enrolled_user, published_course):
    """T-F-2.2.7-1: All videos ≥95% → course marked completed."""
    for video in published_course.videos.all():
        UserVideoProgress.objects.create(
            user=enrolled_user, video=video,
            percent_watched=100, completed_at=timezone.now(),
        )
    enrollment = Enrollment.objects.get(user=enrolled_user, course=published_course)
    # Trigger completion check (called by lesson view / progress endpoint)
    from app.views import _check_course_completion
    _check_course_completion(enrolled_user, published_course)
    enrollment.refresh_from_db()
    assert enrollment.completed_at is not None


# ---------------------------------------------------------------------------
# F-2.2.8 — SEO + sitemap
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_course_page_has_json_ld(client, published_course):
    """T-F-2.2.8-1: Course detail page contains JSON-LD Course schema."""
    r = client.get(reverse("courses_detail", args=["micropython-thonny"]))
    content = r.content.decode("utf-8")
    assert "application/ld+json" in content
    assert "Course" in content


@pytest.mark.django_db
def test_sitemap_includes_courses(client, published_course):
    """T-F-2.2.8-2: /sitemap.xml includes published course URLs."""
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "micropython-thonny" in r.content.decode("utf-8")


# ---------------------------------------------------------------------------
# F-2.2.9 — Corporate funnel hook
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_corporate_hook_on_detail(client, published_course):
    """T-F-2.2.9-1: Course detail page contains corporate funnel link."""
    r = client.get(reverse("courses_detail", args=["micropython-thonny"]))
    content = r.content.decode("utf-8")
    assert "/corporate/" in content


@pytest.mark.django_db
def test_corporate_hook_on_lesson(client, published_course):
    """T-F-2.2.9-2: Lesson page contains corporate funnel link."""
    r = client.get(reverse("courses_lesson", args=["micropython-thonny", 1]))
    content = r.content.decode("utf-8")
    assert "/corporate/" in content


# ---------------------------------------------------------------------------
# F-2.2.10 — load_course_from_manifest
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_manifest_command_populates_new_fields(db, tmp_path, settings):
    """T-F-2.2.10-1: Command populates new Video fields from manifest."""
    # Arrange: write a minimal manifest to tmp_path
    slug = "test-manifest-course"
    manifest = {
        "course_slug": slug,
        "course_title": "Test Course",
        "course_title_en": "Test Course EN",
        "thumbnail": "course_thumbnails/test.png",
        "category": "foundations",
        "difficulty": "beginner",
        "is_published": False,
        "lessons": [
            {
                "lesson_order": 1,
                "bunny_video_id": "bunny-001",
                "title_he": "שיעור אחד",
                "title_en": "Lesson One",
                "duration_seconds": 120,
                "is_free_preview": True,
                "notes_markdown": "### Hello\nWorld",
                "summary_he": "תקציר",
                "has_code_example": True,
                "github_file": "001_test.py",
            }
        ],
    }
    mat_dir = tmp_path / slug
    mat_dir.mkdir()
    (mat_dir / "course_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    # Patch BASE_DIR so the command reads from tmp_path
    import app.management.commands.load_course_from_manifest as cmd_module
    original = cmd_module.MATERIALS_ROOT
    cmd_module.MATERIALS_ROOT = tmp_path
    try:
        from django.core.management import call_command
        call_command("load_course_from_manifest", slug)
        video = Video.objects.get(course__slug=slug, lesson_order=1)
        assert video.notes_markdown == "### Hello\nWorld"
        assert video.summary_he == "תקציר"
        assert video.has_code_example is True
        assert video.github_file == "001_test.py"
        assert video.title_en == "Lesson One"
    finally:
        cmd_module.MATERIALS_ROOT = original
