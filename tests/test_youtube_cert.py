"""Per-lesson YouTube video sharing + certificate.

The learner uploads their project video to their own YouTube and pastes the link;
we parse the id, verify it's embeddable, and embed it. Cert = cert_min_pct% of
lessons + project_min_count videos. Re-pasting the same link is never blocked.
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
from app.views import parse_youtube_id

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_yt_embeddable(monkeypatch):
    """Don't hit YouTube's oembed in tests - assume the video embeds."""
    monkeypatch.setattr("app.views.youtube_is_embeddable", lambda vid: True)


@pytest.mark.parametrize("text,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
    ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("nope", None),
    ("", None),
])
def test_parse_youtube_id(text, expected):
    assert parse_youtube_id(text) == expected


def _yt_course(slug="yt-test", min_pct=80, min_count=1):
    c = Course.objects.create(
        title="Arduino", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_YOUTUBE,
        project_min_count=min_count, cert_min_pct=min_pct,
    )
    vids = []
    for i in range(1, 6):
        v = Video.objects.create(course=c, lesson_order=i, title=f"L{i}",
                                 accepts_model=(i == 4))   # upload only on lesson 4
        vids.append(v)
    vids[-1].is_final_lesson = True
    vids[-1].save(update_fields=["is_final_lesson"])
    return c, vids


def _complete(user, vids, n):
    for v in vids[:n]:
        UserVideoProgress.objects.create(user=user, video=v, percent_watched=100)


def _share(client, course, lesson_order, url, **extra):
    return client.post(
        f"/courses/{course.slug}/lesson/{lesson_order}/submit-youtube/",
        {"youtube_url": url, **extra},
    )


def test_share_parses_and_stores_youtube_id():
    course, vids = _yt_course()
    user = User.objects.create_user("yt1", password="pass12345")
    c = Client()
    c.force_login(user)

    _share(c, course, 4, "not a link")
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[3]).exists()

    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ?si=x", caption="my robot")
    sub = LessonModelSubmission.objects.get(user=user, video=vids[3])
    assert sub.youtube_id == "dQw4w9WgXcQ" and sub.caption == "my robot"
    assert sub.youtube_embed_url == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


def test_unavailable_video_is_rejected(monkeypatch):
    course, vids = _yt_course()
    user = User.objects.create_user("yt2", password="pass12345")
    c = Client()
    c.force_login(user)
    monkeypatch.setattr("app.views.youtube_is_embeddable", lambda vid: False)
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ")
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[3]).exists()


def test_resubmit_same_link_not_blocked(monkeypatch):
    course, vids = _yt_course()
    user = User.objects.create_user("yt3", password="pass12345")
    c = Client()
    c.force_login(user)
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ", caption="first")
    # Even if it would now be deemed unavailable, re-saving the same link to edit
    # the title is allowed.
    monkeypatch.setattr("app.views.youtube_is_embeddable", lambda vid: False)
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ", caption="final title")
    sub = LessonModelSubmission.objects.get(user=user, video=vids[3])
    assert sub.caption == "final title"
    assert LessonModelSubmission.objects.filter(user=user, video=vids[3]).count() == 1


def test_cert_needs_pct_and_one_video():
    course, vids = _yt_course(min_pct=80, min_count=1)
    user = User.objects.create_user("yt4", password="pass12345")
    c = Client()
    c.force_login(user)
    _complete(user, vids, 4)   # 80%
    c.post(f"/courses/{course.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course).exists()  # no video
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ")
    resp = c.post(f"/courses/{course.slug}/finish/")
    assert resp.status_code == 302
    assert CourseCertificate.objects.filter(user=user, course=course).exists()


def test_lesson_embeds_and_exhibition():
    course, vids = _yt_course()
    user = User.objects.create_user("yt5", password="pass12345")
    c = Client()
    c.force_login(user)
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ")
    body = c.get(f"/courses/{course.slug}/lesson/4/").content.decode()
    assert "submit-youtube" in body
    assert "/embed/dQw4w9WgXcQ" in body
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert "/embed/dQw4w9WgXcQ" in course_body
