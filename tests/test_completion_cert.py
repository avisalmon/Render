"""Completion-gated certificate (no project upload): a course with
requires_completion=True issues the cert when cert_min_pct% of lessons are done.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, CourseCertificate, Enrollment, UserVideoProgress, Video

pytestmark = pytest.mark.django_db


def _course(slug="ai-test", pct=100):
    c = Course.objects.create(
        title="AI basics", slug=slug, is_published=True,
        requires_project=False, requires_completion=True, cert_min_pct=pct,
    )
    vids = [Video.objects.create(course=c, lesson_order=i, title=f"L{i}") for i in range(1, 5)]
    vids[-1].is_final_lesson = True
    vids[-1].save(update_fields=["is_final_lesson"])
    return c, vids


def test_cert_requires_all_lessons_no_upload():
    c, vids = _course(pct=100)
    u = User.objects.create_user("ai1", password="pass12345")
    Enrollment.objects.create(user=u, course=c)
    cl = Client()
    cl.force_login(u)

    # 3/4 lessons -> not enough for a 100% gate.
    for v in vids[:3]:
        UserVideoProgress.objects.create(user=u, video=v, percent_watched=100)
    cl.post(f"/courses/{c.slug}/finish/")
    assert not CourseCertificate.objects.filter(user=u, course=c).exists()

    # All 4 -> certificate issues (no project upload involved).
    UserVideoProgress.objects.create(user=u, video=vids[3], percent_watched=100)
    resp = cl.post(f"/courses/{c.slug}/finish/")
    assert resp.status_code == 302
    assert CourseCertificate.objects.filter(user=u, course=c).exists()


def test_final_lesson_shows_completion_gate_not_upload():
    c, vids = _course()
    u = User.objects.create_user("ai2", password="pass12345")
    cl = Client()
    cl.force_login(u)
    body = cl.get(f"/courses/{c.slug}/lesson/4/").content.decode()
    assert "קבלת תעודת סיום" in body            # the gate card renders
    assert "submit-youtube" not in body          # but no upload widgets
    assert "submit-model" not in body
    assert "submit-scratch" not in body
