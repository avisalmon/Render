"""Per-lesson Scratch project sharing + exhibition certificate (Scratch course).

Each build lesson optionally accepts a link to a shared Scratch project; we parse
the id from any link form and embed it. Cert needs >=80% lessons + >=1 shared
project. All shared projects form an exhibition (sidebar / course page / cert).
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import (
    Course,
    CourseCertificate,
    LessonModelSubmission,
    UserVideoProgress,
    Video,
)
from app.views import parse_scratch_id

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_scratch_shared(monkeypatch):
    """Don't hit the real Scratch API in tests - assume projects are shared."""
    monkeypatch.setattr("app.views.scratch_project_is_shared", lambda pid: True)


@pytest.mark.parametrize("text,expected", [
    ("https://scratch.mit.edu/projects/123456789/", "123456789"),
    ("https://scratch.mit.edu/projects/123456789/editor", "123456789"),
    ("http://scratch.mit.edu/projects/987654321/fullscreen/", "987654321"),
    ("scratch.mit.edu/projects/555/embed", "555"),
    ("  123456789  ", "123456789"),
    ("https://scratch.mit.edu/projects/42/?x=1", "42"),
    ("not a link", None),
    ("", None),
])
def test_parse_scratch_id(text, expected):
    assert parse_scratch_id(text) == expected


def _scratch_course(slug="scratch-test"):
    c = Course.objects.create(
        title="Scratch", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_SCRATCH,
    )
    vids = [Video.objects.create(course=c, lesson_order=i, title=f"L{i}") for i in range(1, 6)]
    vids[-1].is_final_lesson = True
    vids[-1].save(update_fields=["is_final_lesson"])
    return c, vids


def _complete(user, vids, n):
    for v in vids[:n]:
        UserVideoProgress.objects.create(user=user, video=v, percent_watched=100)


def _share(client, course, lesson_order, url, **extra):
    return client.post(
        f"/courses/{course.slug}/lesson/{lesson_order}/submit-scratch/",
        {"scratch_url": url, **extra},
    )


def test_share_parses_link_and_stores_id():
    course, vids = _scratch_course()
    user = User.objects.create_user("kid", password="pass12345")
    c = Client()
    c.force_login(user)

    # Garbage link -> nothing stored.
    _share(c, course, 1, "just some text")
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[0]).exists()

    # Real links (different forms) on two lessons.
    _share(c, course, 1, "https://scratch.mit.edu/projects/111222333/editor", caption="my cat")
    _share(c, course, 2, "444555666")
    subs = LessonModelSubmission.objects.filter(user=user, video__course=course)
    assert subs.count() == 2
    s1 = subs.get(video=vids[0])
    assert s1.scratch_id == "111222333" and s1.caption == "my cat" and not s1.model_file
    assert s1.scratch_embed_url == "https://scratch.mit.edu/projects/111222333/embed"

    # Re-share replaces.
    _share(c, course, 1, "https://scratch.mit.edu/projects/999/")
    assert LessonModelSubmission.objects.get(user=user, video=vids[0]).scratch_id == "999"


def test_finish_requires_80pct_and_one_shared_project():
    course, vids = _scratch_course()
    user = User.objects.create_user("k2", password="pass12345")
    c = Client()
    c.force_login(user)

    _complete(user, vids, 4)  # 80% but no project
    c.post(f"/courses/{course.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course).exists()

    _share(c, course, 1, "https://scratch.mit.edu/projects/123456/")
    resp = c.post(f"/courses/{course.slug}/finish/")
    assert resp.status_code == 302
    assert CourseCertificate.objects.filter(user=user, course=course).exists()


def test_requires_min_count_projects():
    """A course with project_min_count=2 needs two shared projects, not one."""
    course, vids = _scratch_course(slug="scratch-min2")
    course.project_min_count = 2
    course.save(update_fields=["project_min_count"])
    user = User.objects.create_user("k4", password="pass12345")
    c = Client()
    c.force_login(user)
    _complete(user, vids, 5)

    _share(c, course, 1, "https://scratch.mit.edu/projects/111/")
    c.post(f"/courses/{course.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course).exists()  # only 1

    _share(c, course, 2, "https://scratch.mit.edu/projects/222/")
    c.post(f"/courses/{course.slug}/finish/")
    assert CourseCertificate.objects.filter(user=user, course=course).exists()  # 2 -> ok


def test_resubmit_same_link_updates_title_without_reverify(monkeypatch):
    """Re-publishing the same link (e.g. to add a title) always updates the same
    row and is never blocked - even if sharing-verification would now say no."""
    course, vids = _scratch_course(slug="scratch-retitle")
    user = User.objects.create_user("k6", password="pass12345")
    c = Client()
    c.force_login(user)
    _share(c, course, 1, "https://scratch.mit.edu/projects/592640441/", caption="first")
    sub = LessonModelSubmission.objects.get(user=user, video=vids[0])
    assert sub.scratch_id == "592640441" and sub.caption == "first"

    # Same link again, with a new title, while the API would reject a *new* link.
    monkeypatch.setattr("app.views.scratch_project_is_shared", lambda pid: False)
    _share(c, course, 1, "https://scratch.mit.edu/projects/592640441/", caption="my title")
    sub.refresh_from_db()
    assert sub.caption == "my title"
    assert LessonModelSubmission.objects.filter(user=user, video=vids[0]).count() == 1


def test_unshared_project_is_rejected(monkeypatch):
    """If the Scratch API says a project is not shared, the submission is refused."""
    course, vids = _scratch_course(slug="scratch-unshared")
    user = User.objects.create_user("k5", password="pass12345")
    c = Client()
    c.force_login(user)
    monkeypatch.setattr("app.views.scratch_project_is_shared", lambda pid: False)
    _share(c, course, 1, "https://scratch.mit.edu/projects/111/")
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[0]).exists()


def test_lesson_embeds_and_exhibition_everywhere():
    course, vids = _scratch_course()
    user = User.objects.create_user("k3", password="pass12345")
    c = Client()
    c.force_login(user)
    _complete(user, vids, 5)
    _share(c, course, 1, "https://scratch.mit.edu/projects/111/")
    _share(c, course, 2, "https://scratch.mit.edu/projects/222/")

    # Lesson page: the share box + the inline embed of THIS lesson's project,
    # plus the sidebar exhibition with Scratch tiles.
    body = c.get(f"/courses/{course.slug}/lesson/1/").content.decode()
    assert "submit-scratch" in body
    assert "scratch.mit.edu/projects/111/embed" in body   # inline embed
    assert 'data-scratch="222"' in body                    # sidebar tile for the other one

    # Course page exhibition.
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert 'data-scratch="111"' in course_body

    # Certificate exhibition.
    c.post(f"/courses/{course.slug}/finish/")
    cert = CourseCertificate.objects.get(user=user, course=course)
    cert_body = c.get(f"/certificate/{cert.certificate_id}/").content.decode()
    assert cert_body.count("stl-tile") >= 2
    assert 'data-scratch="111"' in cert_body and 'data-scratch="222"' in cert_body
