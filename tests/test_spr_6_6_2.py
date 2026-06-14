"""
EPIC-6.6 — SPR-6.6.2 Groups, presence & collaborators: per-course channel,
"learning now" presence, directory filters, and the DM-control toggle.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _member(username="m1", student=False, **lp):
    u = User.objects.create_user(username, password="pass12345")
    u.profile.display_name = username
    u.profile.is_public = True
    u.profile.guidelines_accepted_at = timezone.now()
    u.profile.save()
    if student or lp:
        from app.models import LearnerProfile
        LearnerProfile.objects.create(
            user=u, role_type="student" if student else lp.get("role_type", "other"),
            experience_level=lp.get("level", ""), interests=lp.get("interests", []))
    return u


def _client(user):
    c = Client(); c.force_login(user); return c


def _course_with_video(slug="micro"):
    from app.models import Course, Video
    course = Course.objects.create(slug=slug, title="MicroPython", is_published=True)
    v = Video.objects.create(course=course, bunny_video_id="vid1", title="שיעור 1",
                             title_en="", notes_markdown="", summary_he="", lesson_order=1)
    return course, v


# --- F-6.6.2.1: per-course channel ---

@pytest.mark.django_db
def test_course_channel_created_and_linked():
    from app.models import Channel
    course, _ = _course_with_video()
    resp = Client().get(f"/community/chat/course/{course.slug}/")
    assert resp.status_code == 302 and "/community/chat/" in resp.url
    ch = Channel.objects.get(kind="course", course=course)
    assert ch.slug in resp.url
    # course page links to its group
    body = Client().get(f"/courses/{course.slug}/").content.decode()
    assert f"/community/chat/course/{course.slug}/" in body


# --- F-6.6.2.2: learning-now presence ---

@pytest.mark.django_db
def test_learning_now_presence_window():
    from app.chat import learners_now
    from app.models import UserVideoProgress
    course, video = _course_with_video()
    active = _member("active_learner")
    stale = _member("stale_learner")
    UserVideoProgress.objects.create(user=active, video=video)  # updated_at = now
    old = UserVideoProgress.objects.create(user=stale, video=video)
    UserVideoProgress.objects.filter(pk=old.pk).update(
        updated_at=timezone.now() - timezone.timedelta(minutes=30))
    now_learners = set(learners_now(course))
    assert active in now_learners and stale not in now_learners


# --- F-6.6.2.3: directory filters ---

@pytest.mark.django_db
def test_directory_filters():
    _member("teacher1", role_type="teacher", level="advanced", interests=["ai"])
    _member("student1", student=True)
    collab = _member("collabber", role_type="other")
    collab.profile.open_to_collab = True; collab.profile.save()
    # role filter
    body = Client().get("/community/members/?role=teacher").content.decode()
    assert "teacher1" in body and "student1" not in body
    # collaboration filter
    body = Client().get("/community/members/?collab=1").content.decode()
    assert "collabber" in body and "teacher1" not in body
    # domain (interest) filter
    body = Client().get("/community/members/?domain=ai").content.decode()
    assert "teacher1" in body


# --- F-6.6.2.4: DM control toggle ---

@pytest.mark.django_db
def test_dm_toggle_respected_by_can_message():
    from app.community import can_message
    sender = _member("sender", role_type="other")
    recipient = _member("recipient", role_type="other")
    # default ON for adults
    ok, _ = can_message(sender, recipient)
    assert ok is True
    # recipient turns DMs off
    recipient.profile.dms_enabled = False
    recipient.profile.save()
    ok, reason = can_message(sender, recipient)
    assert ok is False
