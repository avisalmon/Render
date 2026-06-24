"""Profile redesign: per-user course visibility + teacher public recognition."""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.classroom_models import ClassMembership, TeacherClass
from app.models import Course, CourseCertificate, Enrollment, UserVideoProgress, Video

pytestmark = pytest.mark.django_db


def _user(name, public=True):
    u = User.objects.create_user(name, password="pass12345")
    u.profile.is_public = public
    u.profile.display_name = name
    u.profile.save()
    return u


def _enrolled_course(user, slug, title, cert=False):
    c = Course.objects.create(title=title, slug=slug, is_published=True)
    v = Video.objects.create(course=c, lesson_order=1, title="L1")
    UserVideoProgress.objects.create(
        user=user, video=v, percent_watched=100, completed_at=timezone.now())
    Enrollment.objects.create(user=user, course=c)
    if cert:
        CourseCertificate.objects.create(user=user, course=c)
    return c


def test_public_profile_default_shows_certs_not_progress():
    owner = _user("alpha")  # default visibility = certs
    _enrolled_course(owner, "c-done", "DoneCourse", cert=True)
    _enrolled_course(owner, "c-prog", "ProgCourse")  # no cert
    body = Client().get(f"/c/{owner.username}/").content.decode()
    assert "DoneCourse" in body          # certified course shows
    assert "ProgCourse" not in body      # in-progress (no cert) hidden by default


def test_public_profile_all_shows_courses_and_progress():
    owner = _user("beta")
    owner.profile.courses_visibility = "all"; owner.profile.save()
    _enrolled_course(owner, "c-prog2", "ProgBeta")
    body = Client().get(f"/c/{owner.username}/").content.decode()
    assert "ProgBeta" in body            # full learning shown
    assert "hcard-bar" in body           # with a progress bar


def test_public_profile_none_hides_all_learning():
    owner = _user("gamma")
    owner.profile.courses_visibility = "none"; owner.profile.save()
    _enrolled_course(owner, "c-g", "GammaCourse", cert=True)
    body = Client().get(f"/c/{owner.username}/").content.decode()
    assert "GammaCourse" not in body     # even certificates are hidden
    assert "profile-cert" not in body


def test_teacher_recognized_only_with_active_students():
    teacher = _user("teach1")
    klass = TeacherClass.objects.create(owner=teacher, name="K")
    body = Client().get(f"/c/{teacher.username}/").content.decode()
    assert "profile-chip-teacher" not in body   # no students yet -> not a public teacher
    student = _user("stud1", public=False)
    ClassMembership.objects.create(klass=klass, student=student, status="active")
    body2 = Client().get(f"/c/{teacher.username}/").content.decode()
    assert "profile-chip-teacher" in body2      # now recognized


def test_settings_save_persists_courses_visibility():
    u = _user("settervis")
    c = Client(); c.force_login(u)
    c.post(reverse("community_settings"), {"courses_visibility": "all"})
    u.profile.refresh_from_db()
    assert u.profile.courses_visibility == "all"


def test_own_profile_shows_visibility_control_and_all_courses():
    u = _user("ownerx")
    u.profile.courses_visibility = "none"; u.profile.save()  # even if hidden publicly...
    _enrolled_course(u, "ox", "OwnerCourse")
    c = Client(); c.force_login(u)
    body = c.get("/profile/").content.decode()
    assert 'name="courses_visibility"' in body   # the setting control
    assert "OwnerCourse" in body                 # ...the owner always sees their own courses
