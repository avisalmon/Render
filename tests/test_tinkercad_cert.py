"""Per-lesson Tinkercad project sharing + certificate (Arduino-with-Tinkercad).

Upload box only on the lessons whose video.accepts_model is on; cert = all
lessons done (cert_min_pct) + project_min_count projects. Tinkercad links of any
form parse to the thing id and embed as a live player.
"""
import struct

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
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


@pytest.fixture(autouse=True)
def _mock_tinkercad_shared(monkeypatch):
    """Don't hit the real Tinkercad site in tests - assume projects are shared."""
    monkeypatch.setattr("app.views.tinkercad_is_shared", lambda tid: True)


def _make_stl(n_tris=1):
    """A minimal but valid binary STL (passes app.safety.validate_stl)."""
    body = b"\x00" * 80 + struct.pack("<I", n_tris)
    tri = struct.pack("<12fH", *([0.0] * 12), 0)  # 50 bytes/triangle
    return body + tri * n_tris


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


def _tk_course(slug="tk-test", min_pct=100, min_count=1, track="3d"):
    c = Course.objects.create(
        title="Arduino+TK", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_TINKERCAD,
        project_min_count=min_count, cert_min_pct=min_pct, track=track,
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


def test_unshared_project_is_rejected(monkeypatch):
    """A private/nonexistent Tinkercad link (share check says no) is refused."""
    course, vids = _tk_course(slug="tk-unshared")
    user = User.objects.create_user("tk5", password="pass12345")
    c = Client()
    c.force_login(user)
    monkeypatch.setattr("app.views.tinkercad_is_shared", lambda tid: False)
    resp = _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5")
    assert "tcnotshared" in resp["Location"]
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[2]).exists()


def test_resubmit_same_link_not_blocked(monkeypatch):
    """Re-saving the same link (e.g. to edit the caption) is never re-verified,
    even if the share check would now say no."""
    course, vids = _tk_course(slug="tk-retitle")
    user = User.objects.create_user("tk6", password="pass12345")
    c = Client()
    c.force_login(user)
    _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5", caption="first")
    sub = LessonModelSubmission.objects.get(user=user, video=vids[2])
    assert sub.tinkercad_id == "6dV0w3uENk5" and sub.caption == "first"

    monkeypatch.setattr("app.views.tinkercad_is_shared", lambda tid: False)
    _share(c, course, 3, "https://www.tinkercad.com/things/6dV0w3uENk5", caption="second")
    sub.refresh_from_db()
    assert sub.caption == "second"
    assert LessonModelSubmission.objects.filter(user=user, video=vids[2]).count() == 1


def test_summary_lesson_accepts_both_tinkercad_and_stl():
    """The final (summary) lesson offers an optional STL alongside the required
    shared-project link; both land on one submission row without clobbering each
    other, and both render in the exhibition gallery."""
    course, vids = _tk_course(slug="tk-summary")
    final = vids[-1]  # lesson 4, is_final_lesson
    user = User.objects.create_user("tk7", password="pass12345")
    c = Client()
    c.force_login(user)

    # The summary lesson shows BOTH the tinkercad share form and the STL upload box.
    body = c.get(f"/courses/{course.slug}/lesson/{final.lesson_order}/").content.decode()
    assert 'id="tinkercad-form"' in body
    assert 'id="stl-form"' in body
    assert 'id="lesson-model-stl"' in body          # STL box gets a distinct id
    assert body.count('id="lesson-model"') == 1     # no duplicate ids

    # Share the project, then upload an STL on the same lesson.
    _share(c, course, final.lesson_order, "https://www.tinkercad.com/things/6dV0w3uENk5")
    c.post(
        f"/courses/{course.slug}/lesson/{final.lesson_order}/submit-model/",
        {"model": SimpleUploadedFile("design.stl", _make_stl(), content_type="model/stl")},
    )
    sub = LessonModelSubmission.objects.get(user=user, video=final)
    assert sub.tinkercad_id == "6dV0w3uENk5"          # link kept
    assert bool(sub.model_file)                       # STL kept on the same row

    # Re-saving the link must NOT wipe the STL.
    _share(c, course, final.lesson_order, "https://www.tinkercad.com/things/6dV0w3uENk5", caption="x")
    sub.refresh_from_db()
    assert sub.tinkercad_id == "6dV0w3uENk5" and bool(sub.model_file)

    # The course exhibition shows both an embed tile and an STL tile from one row.
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert "tinkercad.com/embed/6dV0w3uENk5" in course_body
    assert sub.model_file.url in course_body

    sub.model_file.delete(save=False)


def test_circuit_course_summary_has_no_stl_box():
    """A non-3D Tinkercad course (e.g. arduino-tinkercad, track='hardware') is for
    circuits, which have no STL to export - its summary lesson shows the shared-
    project link ONLY, never the STL upload box."""
    course, vids = _tk_course(slug="tk-hardware", track="hardware")
    final = vids[-1]
    user = User.objects.create_user("tk8", password="pass12345")
    c = Client()
    c.force_login(user)
    body = c.get(f"/courses/{course.slug}/lesson/{final.lesson_order}/").content.decode()
    assert 'id="tinkercad-form"' in body      # project sharing present
    assert 'id="stl-form"' not in body        # STL box NOT present
    assert 'id="lesson-model-stl"' not in body
