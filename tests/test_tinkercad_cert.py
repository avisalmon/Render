"""Per-lesson Tinkercad project sharing + certificate (Arduino-with-Tinkercad).

Upload box only on the lessons whose video.accepts_model is on; cert = all
lessons done (cert_min_pct) + project_min_count projects. Tinkercad links of any
form parse to the thing id and embed as a live player.
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
from app.views import parse_tinkercad_id

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("text,expected", [
    ("https://www.tinkercad.com/things/6dV0w3uENk5", "6dV0w3uENk5"),
    ("https://www.tinkercad.com/things/6dV0w3uENk5-funky-curcan", "6dV0w3uENk5"),
    ("https://www.tinkercad.com/things/6dV0w3uENk5/edit", "6dV0w3uENk5"),
    ("https://www.tinkercad.com/embed/6dV0w3uENk5?editbtn=1", "6dV0w3uENk5"),
    ("6dV0w3uENk5", "6dV0w3uENk5"),
    ("not a link", None),
    ("", None),
])
def test_parse_tinkercad_id(text, expected):
    assert parse_tinkercad_id(text) == expected


def _tk_course(slug="tk-test", min_pct=100, min_count=1):
    c = Course.objects.create(
        title="Arduino+TK", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_TINKERCAD,
        project_min_count=min_count, cert_min_pct=min_pct,
    )
    vids = []
    for i in range(1, 5):
        v = Video.objects.create(course=c, lesson_order=i, title=f"L{i}",
                                 accepts_model=(i >= 3))  # upload only on lessons 3,4
        vids.append(v)
    vids[-1].is_final_lesson = True
    vids[-1].save(update_fields=["is_final_lesson"])
    return c, vids


def _complete(user, vids, n):
    for v in vids[:n]:
        UserVideoProgress.objects.create(user=user, video=v, percent_watched=100)


def _share(client, course, lesson_order, url, **extra):
    return client.post(
        f"/courses/{course.slug}/lesson/{lesson_order}/submit-tinkercad/",
        {"tinkercad_url": url, **extra},
    )


def test_share_parses_and_stores_tinkercad_id():
    course, vids = _tk_course()
    user = User.objects.create_user("tk1", password="pass12345")
    c = Client()
    c.force_login(user)

    _share(c, course, 3, "garbage")
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[2]).exists()

    _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5-funky", caption="my circuit")
    sub = LessonModelSubmission.objects.get(user=user, video=vids[2])
    assert sub.tinkercad_id == "6dV0w3uENk5" and not sub.scratch_id and not sub.model_file
    assert sub.tinkercad_embed_url == "https://www.tinkercad.com/embed/6dV0w3uENk5?editbtn=1"


def test_cert_needs_all_lessons_done_and_one_project():
    course, vids = _tk_course(min_pct=100, min_count=1)  # all lessons + 1 project
    user = User.objects.create_user("tk2", password="pass12345")
    c = Client()
    c.force_login(user)

    # 3/4 lessons + a project -> not enough (needs 100%).
    _complete(user, vids, 3)
    _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5")
    c.post(f"/courses/{course.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course).exists()

    # All 4 lessons done -> certificate issues.
    _complete(user, vids[3:], 1)
    resp = c.post(f"/courses/{course.slug}/finish/")
    assert resp.status_code == 302
    assert CourseCertificate.objects.filter(user=user, course=course).exists()


def test_lesson_embeds_and_exhibition():
    course, vids = _tk_course()
    user = User.objects.create_user("tk3", password="pass12345")
    c = Client()
    c.force_login(user)
    _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5")

    body = c.get(f"/courses/{course.slug}/lesson/3/").content.decode()
    assert "submit-tinkercad" in body
    assert "tinkercad.com/embed/6dV0w3uENk5" in body          # inline embed
    # Gallery tile carries the embed url for the modal.
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert "tinkercad.com/embed/6dV0w3uENk5" in course_body


def test_upload_box_only_on_accepts_model_lessons():
    course, vids = _tk_course()
    user = User.objects.create_user("tk4", password="pass12345")
    c = Client()
    c.force_login(user)
    # Lesson 1 has accepts_model=False -> no upload box.
    assert "submit-tinkercad" not in c.get(f"/courses/{course.slug}/lesson/1/").content.decode()
    # Lesson 3 has accepts_model=True -> box present.
    assert "submit-tinkercad" in c.get(f"/courses/{course.slug}/lesson/3/").content.decode()
