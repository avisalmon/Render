"""Manual-review certificate gate for the YouTube-proof courses (requires_review).

The learner finishes the lessons + uploads a video, then submits for review. The
certificate is NOT auto-issued: a reviewer (admin or the learner's class teacher)
gets an email + in-app notification, watches the video, and approves or rejects it
with a message. The project stays hidden from public/cross-user views until the
review is approved.
"""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client

from app.models import (
    ClassMembership,
    Course,
    CourseCertificate,
    CourseCompletionReview,
    LessonModelSubmission,
    Notification,
    TeacherClass,
    UserVideoProgress,
    Video,
)
from app.review import visible_submissions

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_yt_embeddable(monkeypatch):
    monkeypatch.setattr("app.views.youtube_is_embeddable", lambda vid: True)


def _review_course(slug="rev-test", min_pct=80, min_count=1):
    c = Course.objects.create(
        title="Arduino", slug=slug, is_published=True,
        requires_project=True, project_upload_type=Course.PROJECT_YOUTUBE,
        project_min_count=min_count, cert_min_pct=min_pct, requires_review=True,
    )
    vids = []
    for i in range(1, 6):
        v = Video.objects.create(course=c, lesson_order=i, title=f"L{i}",
                                 accepts_model=(i == 4))
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
        {"youtube_url": url, **extra})


def _ready_learner(course, vids, username="learner"):
    """A learner who has met the gate (80% + a video) but isn't certified yet."""
    user = User.objects.create_user(username, email=f"{username}@x.com", password="pass12345")
    c = Client()
    c.force_login(user)
    _complete(user, vids, 4)  # 4/5 = 80%
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ", caption="my robot")
    return user, c


# --- Finish submits for review instead of issuing the certificate -------------

def test_finish_creates_pending_review_and_notifies():
    course, vids = _review_course()
    staff = User.objects.create_user("admin1", email="admin@x.com", password="x", is_staff=True)
    learner, c = _ready_learner(course, vids)
    mail.outbox.clear()

    resp = c.post(f"/courses/{course.slug}/finish/")

    # No certificate yet; a pending review exists.
    assert not CourseCertificate.objects.filter(user=learner, course=course).exists()
    review = CourseCompletionReview.objects.get(user=learner, course=course)
    assert review.is_pending
    # Redirect back to the summary lesson with the pending flag.
    assert resp.status_code == 302 and "review_pending" in resp["Location"]
    # Reviewer (staff) got an in-app notification...
    assert Notification.objects.filter(user=staff, verb="review_request").exists()
    # ...and an email went out (to the staff reviewer and/or the admin address).
    assert len(mail.outbox) >= 1
    assert any("admin@x.com" in m.to or "avi.salmon@gmail.com" in m.to for m in mail.outbox)


def test_pending_video_hidden_until_approved():
    course, vids = _review_course()
    learner, c = _ready_learner(course, vids)
    c.post(f"/courses/{course.slug}/finish/")

    subs = list(LessonModelSubmission.objects.filter(user=learner, video__course=course)
                .select_related("video"))
    # Pending -> filtered out of any public/cross-user display.
    assert subs and visible_submissions(subs) == []

    review = CourseCompletionReview.objects.get(user=learner, course=course)
    review.status = CourseCompletionReview.APPROVED
    review.save(update_fields=["status"])
    # Approved -> shown.
    assert visible_submissions(subs) == subs


def test_non_review_course_submissions_always_visible():
    c = Course.objects.create(
        title="Scratch", slug="vis-plain", is_published=True, requires_project=True,
        project_upload_type=Course.PROJECT_SCRATCH)
    v = Video.objects.create(course=c, lesson_order=1, title="L1", accepts_model=True)
    user = User.objects.create_user("plain1", password="x")
    sub = LessonModelSubmission.objects.create(user=user, video=v, scratch_id="123")
    assert visible_submissions([sub]) == [sub]


# --- Reviewer permissions -----------------------------------------------------

def test_review_page_permissions():
    course, vids = _review_course()
    learner, c = _ready_learner(course, vids)
    c.post(f"/courses/{course.slug}/finish/")
    url = f"/courses/{course.slug}/review/{learner.id}/"

    # A random member cannot see the review page.
    rando = User.objects.create_user("rando", password="x")
    rc = Client(); rc.force_login(rando)
    assert rc.get(url).status_code == 404

    # Staff can.
    staff = User.objects.create_user("admin2", password="x", is_staff=True)
    sc = Client(); sc.force_login(staff)
    assert sc.get(url).status_code == 200

    # The teacher of a class the learner is an active member of can.
    teacher = User.objects.create_user("teacher", password="x")
    klass = TeacherClass.objects.create(owner=teacher, name="C")
    ClassMembership.objects.create(klass=klass, student=learner, status="active")
    tc = Client(); tc.force_login(teacher)
    assert tc.get(url).status_code == 200

    # The same teacher cannot review a learner who is NOT in their class.
    other, _ = _ready_learner(course, vids, username="other")
    c2 = Client(); c2.force_login(other)
    c2.post(f"/courses/{course.slug}/finish/")
    assert tc.get(f"/courses/{course.slug}/review/{other.id}/").status_code == 404


# --- Approve / reject ---------------------------------------------------------

def test_approve_issues_certificate_and_notifies_learner():
    course, vids = _review_course()
    staff = User.objects.create_user("admin3", password="x", is_staff=True)
    learner, c = _ready_learner(course, vids)
    c.post(f"/courses/{course.slug}/finish/")
    mail.outbox.clear()

    sc = Client(); sc.force_login(staff)
    sc.post(f"/courses/{course.slug}/review/{learner.id}/", {"action": "approve"})

    review = CourseCompletionReview.objects.get(user=learner, course=course)
    assert review.is_approved and review.reviewer_id == staff.id
    assert CourseCertificate.objects.filter(user=learner, course=course).exists()
    assert Notification.objects.filter(user=learner, verb="cert_approved").exists()
    assert any("learner@x.com" in m.to for m in mail.outbox)


def test_reject_sends_message_and_blocks_cert_then_resubmit():
    course, vids = _review_course()
    staff = User.objects.create_user("admin4", password="x", is_staff=True)
    learner, c = _ready_learner(course, vids)
    c.post(f"/courses/{course.slug}/finish/")

    sc = Client(); sc.force_login(staff)
    # Reject with a message about what to fix.
    sc.post(f"/courses/{course.slug}/review/{learner.id}/",
            {"action": "reject", "message": "האודיו לא נשמע, צלמו שוב"})
    review = CourseCompletionReview.objects.get(user=learner, course=course)
    assert review.is_rejected and "האודיו" in review.note
    assert not CourseCertificate.objects.filter(user=learner, course=course).exists()
    assert Notification.objects.filter(user=learner, verb="cert_rejected").exists()

    # An empty reject message is refused (status unchanged).
    sc.post(f"/courses/{course.slug}/review/{learner.id}/", {"action": "reject", "message": "  "})
    review.refresh_from_db()
    assert review.is_rejected

    # The learner fixes the video and resubmits -> back to pending.
    c.post(f"/courses/{course.slug}/finish/")
    review.refresh_from_db()
    assert review.is_pending


def test_swapping_an_approved_video_reopens_review():
    course, vids = _review_course()
    User.objects.create_user("admin5", password="x", is_staff=True)
    learner, c = _ready_learner(course, vids)
    c.post(f"/courses/{course.slug}/finish/")
    review = CourseCompletionReview.objects.get(user=learner, course=course)
    review.status = CourseCompletionReview.APPROVED
    review.save(update_fields=["status"])

    # Editing only the caption keeps it approved.
    _share(c, course, 4, "https://youtu.be/dQw4w9WgXcQ", caption="new caption")
    review.refresh_from_db()
    assert review.is_approved

    # Swapping in a different video re-opens the review (no unreviewed video can
    # stay attached to the certificate).
    _share(c, course, 4, "https://youtu.be/abcdefghijk")
    review.refresh_from_db()
    assert review.is_pending
