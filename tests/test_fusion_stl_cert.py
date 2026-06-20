"""Per-lesson STL models + exhibition certificate (e.g. Fusion 360).

Each "build" lesson optionally accepts an STL the learner designed. The cert
needs >=80% of lessons AND at least one model uploaded. All the learner's models
form an exhibition shown in the lesson sidebar, the course page and the cert.
"""
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

pytestmark = pytest.mark.django_db

ASCII_STL = b"solid cube\nfacet normal 0 0 0\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid cube\n"


def _stl_course(slug="fusion-test"):
    c = Course.objects.create(
        title="Fusion", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_STL,
    )
    vids = [Video.objects.create(course=c, lesson_order=i, title=f"L{i}") for i in range(1, 6)]
    vids[-1].is_final_lesson = True
    vids[-1].save(update_fields=["is_final_lesson"])
    return c, vids


def _complete(user, vids, n):
    for v in vids[:n]:
        UserVideoProgress.objects.create(user=user, video=v, percent_watched=100)


def _stl(name="cube.stl"):
    return SimpleUploadedFile(name, ASCII_STL, content_type="application/octet-stream")


def _upload(client, course, lesson_order, **extra):
    return client.post(
        f"/courses/{course.slug}/lesson/{lesson_order}/submit-model/",
        {"model": _stl(), **extra},
    )


def test_per_lesson_upload_creates_one_submission_each_and_validates_ext():
    course, vids = _stl_course()
    user = User.objects.create_user("designer", password="pass12345")
    c = Client()
    c.force_login(user)

    # Non-.stl is rejected.
    c.post(f"/courses/{course.slug}/lesson/1/submit-model/",
           {"model": SimpleUploadedFile("notes.txt", b"x", content_type="text/plain")})
    assert not LessonModelSubmission.objects.filter(user=user, video=vids[0]).exists()

    # Upload models on two different lessons -> two submissions.
    _upload(c, course, 1, caption="bracket")
    _upload(c, course, 3)
    subs = LessonModelSubmission.objects.filter(user=user, video__course=course)
    assert subs.count() == 2
    assert subs.get(video=vids[0]).caption == "bracket"

    # Re-uploading the same lesson replaces (still one for that lesson).
    _upload(c, course, 1)
    assert LessonModelSubmission.objects.filter(user=user, video=vids[0]).count() == 1


def test_finish_requires_80pct_and_at_least_one_model():
    course, vids = _stl_course()
    user = User.objects.create_user("d2", password="pass12345")
    c = Client()
    c.force_login(user)

    # 80% done but no model -> blocked.
    _complete(user, vids, 4)
    c.post(f"/courses/{course.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course).exists()

    # One model but only 40% done -> still blocked.
    course2, vids2 = _stl_course(slug="fusion-test-2")
    _upload(c, course2, 1)
    _complete(user, vids2, 2)
    c.post(f"/courses/{course2.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=user, course=course2).exists()

    # First course: add a model on top of the 80% -> issues.
    _upload(c, course, 2)
    resp = c.post(f"/courses/{course.slug}/finish/")
    assert resp.status_code == 302
    assert CourseCertificate.objects.filter(user=user, course=course).exists()


def test_certificate_exhibition_and_owner_only_download():
    course, vids = _stl_course()
    owner = User.objects.create_user("owner", password="pass12345")
    c = Client()
    c.force_login(owner)
    _complete(owner, vids, 5)
    _upload(c, course, 1)
    _upload(c, course, 2)
    c.post(f"/courses/{course.slug}/finish/")
    cert = CourseCertificate.objects.get(user=owner, course=course)
    sub = LessonModelSubmission.objects.filter(user=owner, video__course=course).first()

    # Owner cert page: exhibition tiles + download links present.
    body = c.get(f"/certificate/{cert.certificate_id}/").content.decode()
    assert body.count("stl-tile") >= 2          # two models exhibited
    assert "/model-submission/" in body         # owner download links

    # Owner can download a model; another user cannot.
    assert c.get(f"/model-submission/{sub.pk}/download").status_code == 200
    other = User.objects.create_user("other", password="pass12345")
    c2 = Client()
    c2.force_login(other)
    assert c2.get(f"/model-submission/{sub.pk}/download").status_code == 404
    body2 = c2.get(f"/certificate/{cert.certificate_id}/").content.decode()
    assert body2.count("stl-tile") >= 2         # public still sees the exhibition
    assert "/model-submission/" not in body2    # but no download links


def test_certified_user_sees_trophy_on_lesson_and_course():
    course, vids = _stl_course()
    user = User.objects.create_user("champ", password="pass12345")
    c = Client()
    c.force_login(user)
    _complete(user, vids, 5)
    _upload(c, course, 1)
    c.post(f"/courses/{course.slug}/finish/")
    cert = CourseCertificate.objects.get(user=user, course=course)
    link = f"/certificate/{cert.certificate_id}/"

    # Trophy on a non-final lesson and on the course page, linking to the cert.
    lesson_body = c.get(f"/courses/{course.slug}/lesson/2/").content.decode()
    assert "cert-trophy" in lesson_body and link in lesson_body
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert "cert-trophy" in course_body and link in course_body

    # A non-certified user sees no trophy.
    other = User.objects.create_user("nocert", password="pass12345")
    c2 = Client()
    c2.force_login(other)
    assert "cert-trophy" not in c2.get(f"/courses/{course.slug}/lesson/2/").content.decode()


def test_lesson_sidebar_and_course_page_show_my_models():
    course, vids = _stl_course()
    user = User.objects.create_user("viewer", password="pass12345")
    c = Client()
    c.force_login(user)
    _upload(c, course, 1)

    # Lesson page sidebar shows the gallery tile.
    lesson_body = c.get(f"/courses/{course.slug}/lesson/2/").content.decode()
    assert "stl-tile" in lesson_body and "הפרויקטים שלי" in lesson_body

    # Course main page shows the exhibition too.
    course_body = c.get(f"/courses/{course.slug}/").content.decode()
    assert "stl-tile" in course_body
