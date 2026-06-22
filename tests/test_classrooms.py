"""Chapter 9 - Teachers & Classes. Full flow + privacy boundary + opt-out."""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client

from app.classroom_models import (
    ClassInvite,
    ClassJoinRequest,
    ClassMembership,
    ClassMessage,
    TeacherClass,
)
from app.models import Course, LessonModelSubmission, Notification, Video

pytestmark = pytest.mark.django_db


def _teacher(username="teacher"):
    u = User.objects.create_user(username, password="pass12345", email=f"{username}@ex.com")
    u.profile.is_teacher = True
    u.profile.save()
    return u


def _student(username):
    return User.objects.create_user(username, password="pass12345", email=f"{username}@ex.com")


def _class(owner, name="Class A"):
    return TeacherClass.objects.create(owner=owner, name=name)


# --- become a teacher --------------------------------------------------------

def test_become_teacher_one_click():
    u = _student("u1")
    assert u.profile.is_teacher is False
    c = Client(); c.force_login(u)
    r = c.post("/classes/become-teacher/")
    assert r.status_code == 302
    u.profile.refresh_from_db()
    assert u.profile.is_teacher is True


def test_non_teacher_cannot_reach_create():
    u = _student("u2")
    c = Client(); c.force_login(u)
    r = c.get("/classes/new/")
    assert r.status_code == 302  # bounced to my_classes


# --- create + join via link --------------------------------------------------

def test_create_class_and_join_link_logged_in():
    teacher = _teacher()
    c = Client(); c.force_login(teacher)
    r = c.post("/classes/new/", {"name": "Robotics", "description": "fun"})
    assert r.status_code == 302
    klass = TeacherClass.objects.get(name="Robotics")

    student = _student("s1")
    sc = Client(); sc.force_login(student)
    r = sc.get(f"/class/join/{klass.join_code}/")
    assert r.status_code == 302
    assert r.url == f"/class/{klass.id}/"
    assert ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()


def test_join_link_anonymous_shows_landing_with_og_and_wall_cta():
    klass = _class(_teacher(), "Sailing")
    r = Client().get(f"/class/join/{klass.join_code}/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Sailing" in body
    # CTA leads to the join wall, preserving the return-to-class intent.
    assert f"/join/?next=/class/join/{klass.join_code}/" in body
    # The page carries an Open Graph card so WhatsApp shows a preview.
    assert 'property="og:title"' in body
    assert 'property="og:image"' in body


def test_join_blocked_when_class_closed():
    klass = _class(_teacher())
    klass.is_open = False
    klass.save()
    student = _student("s2")
    sc = Client(); sc.force_login(student)
    r = sc.get(f"/class/join/{klass.join_code}/")
    assert r.status_code == 302
    assert not ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()


# --- in-system invite --------------------------------------------------------

def test_invite_existing_member_and_accept():
    teacher = _teacher()
    klass = _class(teacher)
    invitee = _student("s3")

    tc = Client(); tc.force_login(teacher)
    r = tc.post(f"/class/{klass.id}/invite/", {"user_id": invitee.id})
    assert r.status_code == 302
    assert ClassInvite.objects.filter(klass=klass, invitee=invitee, status="pending").exists()
    # The invitee got an in-system notification.
    assert Notification.objects.filter(user=invitee, verb="class_invite").exists()

    ic = Client(); ic.force_login(invitee)
    invite = ClassInvite.objects.get(klass=klass, invitee=invitee)
    r = ic.post(f"/class/invite/{invite.id}/respond/", {"action": "accept"})
    assert r.status_code == 302
    assert ClassMembership.objects.filter(klass=klass, student=invitee, status="active").exists()
    invite.refresh_from_db()
    assert invite.status == "accepted"


def test_invite_decline():
    teacher = _teacher()
    klass = _class(teacher)
    invitee = _student("s4")
    ClassInvite.objects.create(klass=klass, inviter=teacher, invitee=invitee)
    ic = Client(); ic.force_login(invitee)
    invite = ClassInvite.objects.get(klass=klass, invitee=invitee)
    ic.post(f"/class/invite/{invite.id}/respond/", {"action": "decline"})
    invite.refresh_from_db()
    assert invite.status == "declined"
    assert not ClassMembership.objects.filter(klass=klass, student=invitee, status="active").exists()


# --- privacy boundary --------------------------------------------------------

def test_classmate_cannot_see_another_students_progress():
    teacher = _teacher()
    klass = _class(teacher)
    s1 = _student("s5"); s2 = _student("s6")
    ClassMembership.objects.create(klass=klass, student=s1, status="active")
    ClassMembership.objects.create(klass=klass, student=s2, status="active")

    # A classmate cannot open the teacher-only per-student progress page.
    cc = Client(); cc.force_login(s2)
    r = cc.get(f"/class/{klass.id}/student/{s1.id}/")
    assert r.status_code == 404

    # The teacher can.
    tc = Client(); tc.force_login(teacher)
    r = tc.get(f"/class/{klass.id}/student/{s1.id}/")
    assert r.status_code == 200


def test_manage_page_is_owner_only():
    teacher = _teacher()
    klass = _class(teacher)
    other = _student("s7")
    oc = Client(); oc.force_login(other)
    assert oc.get(f"/class/{klass.id}/manage/").status_code == 404


# --- project gallery opt-out -------------------------------------------------

def _scratch_project(user):
    course = Course.objects.create(title="Scratch", slug="scratch-x", is_published=True,
                                   project_upload_type="scratch")
    video = Video.objects.create(course=course, lesson_order=1, title="L1")
    return LessonModelSubmission.objects.create(user=user, video=video, scratch_id="123456789")


def test_shared_project_visible_then_hidden_on_optout():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("s8")
    membership = ClassMembership.objects.create(klass=klass, student=student, status="active")
    _scratch_project(student)

    sc = Client(); sc.force_login(student)
    body = sc.get(f"/class/{klass.id}/").content.decode()
    assert "123456789" in body  # the shared scratch project shows in the class gallery

    # Opt out -> hidden from classmates.
    sc.post(f"/class/{klass.id}/toggle-share/")
    membership.refresh_from_db()
    assert membership.share_projects is False
    body = sc.get(f"/class/{klass.id}/").content.decode()
    assert "123456789" not in body


# --- classroom discussion ----------------------------------------------------

def test_post_message_teacher_is_announcement():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("s9")
    ClassMembership.objects.create(klass=klass, student=student, status="active")

    tc = Client(); tc.force_login(teacher)
    tc.post(f"/class/{klass.id}/post/", {"body": "Welcome class"})
    msg = ClassMessage.objects.get(klass=klass, author=teacher)
    assert msg.is_announcement is True

    sc = Client(); sc.force_login(student)
    sc.post(f"/class/{klass.id}/post/", {"body": "Hi teacher"})
    smsg = ClassMessage.objects.get(klass=klass, author=student)
    assert smsg.is_announcement is False


def test_non_member_cannot_enter_classroom():
    klass = _class(_teacher())
    other = _student("s10")
    oc = Client(); oc.force_login(other)
    r = oc.get(f"/class/{klass.id}/")
    assert r.status_code == 302  # bounced to my_classes


# --- QR ----------------------------------------------------------------------

def test_owner_pages_render():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("s12")
    ClassMembership.objects.create(klass=klass, student=student, status="active")
    tc = Client(); tc.force_login(teacher)
    assert tc.get("/classes/").status_code == 200
    assert tc.get("/classes/new/").status_code == 200
    assert tc.get(f"/class/{klass.id}/manage/").status_code == 200
    assert tc.get(f"/class/{klass.id}/").status_code == 200


def test_user_search_matches_from_first_letter():
    teacher = _teacher()
    klass = _class(teacher)
    User.objects.create_user("zoebravo", password="pass12345", first_name="Zoe")
    tc = Client(); tc.force_login(teacher)
    # A single letter already returns matches.
    data = tc.get(f"/class/{klass.id}/search-users/?q=z").json()
    assert any(u["username"] == "zoebravo" for u in data["results"])
    # Empty query returns nothing; search is owner-only.
    assert tc.get(f"/class/{klass.id}/search-users/?q=").json()["results"] == []
    other = _student("srch1")
    oc = Client(); oc.force_login(other)
    assert oc.get(f"/class/{klass.id}/search-users/?q=z").status_code == 404


def test_manage_whatsapp_message_and_qr_actions():
    teacher = _teacher()
    klass = _class(teacher, "Robotics")
    tc = Client(); tc.force_login(teacher)
    body = tc.get(f"/class/{klass.id}/manage/").content.decode()
    # WhatsApp share carries a friendly invitation, not a bare URL.
    assert "wa.me/?text=" in body
    assert "babook" in body  # invitation text mentions the platform
    assert klass.join_code in body  # and the (clickable) join link
    # QR has both copy and download affordances.
    assert 'download="class-qr.png"' in body
    assert 'id="copyQr"' in body


def test_qr_owner_only():
    teacher = _teacher()
    klass = _class(teacher)
    tc = Client(); tc.force_login(teacher)
    r = tc.get(f"/class/{klass.id}/qr.png")
    assert r.status_code == 200
    assert r["Content-Type"] == "image/png"

    other = _student("s11")
    oc = Client(); oc.force_login(other)
    assert oc.get(f"/class/{klass.id}/qr.png").status_code == 404


# --- public directory + request-to-join + approval ---------------------------

def test_directory_public_and_hides_student_data():
    teacher = _teacher()
    klass = _class(teacher, "Astronomy")
    student = _student("d1")
    ClassMembership.objects.create(klass=klass, student=student, status="active")
    # Anonymous can browse the directory.
    body = Client().get("/classes/all/").content.decode()
    assert "Astronomy" in body
    assert teacher.profile.public_name in body
    # No student identity / progress leaks into the public directory.
    assert student.username not in body
    assert "cls-bar" not in body  # the progress-bar element never appears here


def test_anonymous_request_button_points_to_wall():
    klass = _class(_teacher())
    body = Client().get("/classes/all/").content.decode()
    assert "/join/?next=/classes/all/" in body


def test_request_to_join_notifies_teacher_in_system_and_email():
    teacher = _teacher()
    klass = _class(teacher, "Chess")
    student = _student("d2")
    mail.outbox.clear()
    sc = Client(); sc.force_login(student)
    r = sc.post(f"/class/{klass.id}/request-join/")
    assert r.status_code == 302
    assert ClassJoinRequest.objects.filter(klass=klass, student=student, status="pending").exists()
    assert Notification.objects.filter(user=teacher, verb="class_join_request").exists()
    assert len(mail.outbox) == 1
    assert teacher.email in mail.outbox[0].to
    # The teacher's email carries the approval link.
    req = ClassJoinRequest.objects.get(klass=klass, student=student)
    assert f"/class/request/{req.id}/approve/" in mail.outbox[0].body


def test_directory_shows_request_sent_state():
    teacher = _teacher()
    klass = _class(teacher, "Biology")
    student = _student("d3")
    ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    sc = Client(); sc.force_login(student)
    body = sc.get("/classes/all/").content.decode()
    assert "הבקשה נשלחה" in body


def test_approve_is_owner_only():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("d4")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    intruder = _student("d5")
    ic = Client(); ic.force_login(intruder)
    assert ic.get(f"/class/request/{req.id}/approve/").status_code == 404
    assert ic.post(f"/class/request/{req.id}/approve/").status_code == 404
    # The intruder did not get added.
    assert not ClassMembership.objects.filter(klass=klass, student=intruder).exists()
    req.refresh_from_db()
    assert req.status == "pending"


def test_approve_get_is_confirm_page_no_mutation():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("d6")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    tc = Client(); tc.force_login(teacher)
    r = tc.get(f"/class/request/{req.id}/approve/")
    assert r.status_code == 200  # confirm page
    # GET must NOT change anything.
    req.refresh_from_db()
    assert req.status == "pending"
    assert not ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()


def test_approve_post_adds_member_and_notifies_student():
    teacher = _teacher()
    klass = _class(teacher, "Drama")
    student = _student("d7")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    mail.outbox.clear()
    tc = Client(); tc.force_login(teacher)
    r = tc.post(f"/class/request/{req.id}/approve/")
    assert r.status_code == 302
    assert ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()
    req.refresh_from_db()
    assert req.status == "approved"
    assert Notification.objects.filter(user=student, verb="class_request_approved").exists()
    assert len(mail.outbox) == 1
    assert student.email in mail.outbox[0].to
    assert f"/class/{klass.id}/" in mail.outbox[0].body


def test_decline_request():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("d8")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    tc = Client(); tc.force_login(teacher)
    r = tc.post(f"/class/request/{req.id}/decline/")
    assert r.status_code == 302
    req.refresh_from_db()
    assert req.status == "declined"
    assert not ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()
    assert Notification.objects.filter(user=student, verb="class_request_declined").exists()


def test_request_join_requires_login():
    klass = _class(_teacher())
    r = Client().post(f"/class/{klass.id}/request-join/")
    assert r.status_code == 302
    assert "/login" in r.url or "/join" in r.url


def test_owner_requesting_own_class_is_redirected():
    teacher = _teacher()
    klass = _class(teacher)
    tc = Client(); tc.force_login(teacher)
    tc.post(f"/class/{klass.id}/request-join/")
    assert not ClassJoinRequest.objects.filter(klass=klass, student=teacher).exists()


# --- review fixes: closed class, idempotency, reconciliation -----------------

def test_request_join_blocked_when_class_closed():
    teacher = _teacher()
    klass = _class(teacher)
    klass.is_open = False
    klass.save()
    student = _student("f1")
    mail.outbox.clear()
    sc = Client(); sc.force_login(student)
    r = sc.post(f"/class/{klass.id}/request-join/")
    assert r.status_code == 302
    assert not ClassJoinRequest.objects.filter(klass=klass, student=student).exists()
    assert len(mail.outbox) == 0


def test_directory_shows_closed_state():
    teacher = _teacher()
    klass = _class(teacher, "ClosedClub")
    klass.is_open = False
    klass.save()
    student = _student("f2")
    sc = Client(); sc.force_login(student)
    body = sc.get("/classes/all/").content.decode()
    assert "סגורה להצטרפות" in body


def test_repeated_request_does_not_respam_teacher():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("f3")
    mail.outbox.clear()
    sc = Client(); sc.force_login(student)
    sc.post(f"/class/{klass.id}/request-join/")
    sc.post(f"/class/{klass.id}/request-join/")
    sc.post(f"/class/{klass.id}/request-join/")
    assert ClassJoinRequest.objects.filter(klass=klass, student=student).count() == 1
    assert Notification.objects.filter(user=teacher, verb="class_join_request").count() == 1
    assert len(mail.outbox) == 1


def test_rerequest_after_decline_reopens_and_notifies_again():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("f4")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="declined")
    mail.outbox.clear()
    sc = Client(); sc.force_login(student)
    sc.post(f"/class/{klass.id}/request-join/")
    req.refresh_from_db()
    assert req.status == "pending"
    assert req.decided_at is None
    assert Notification.objects.filter(user=teacher, verb="class_join_request").count() == 1
    assert len(mail.outbox) == 1


def test_removed_member_rerequest_then_approve_reactivates():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("f5")
    ClassMembership.objects.create(klass=klass, student=student, status="removed")
    sc = Client(); sc.force_login(student)
    sc.post(f"/class/{klass.id}/request-join/")
    req = ClassJoinRequest.objects.get(klass=klass, student=student)
    tc = Client(); tc.force_login(teacher)
    # The confirm page warns that the student was removed before.
    body = tc.get(f"/class/request/{req.id}/approve/").content.decode()
    assert "הוסר מהכיתה בעבר" in body
    tc.post(f"/class/request/{req.id}/approve/")
    assert ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()


def test_request_and_approve_survive_empty_emails():
    teacher = _teacher("noemailteach")
    teacher.email = ""; teacher.save()
    klass = _class(teacher)
    student = _student("f6")
    student.email = ""; student.save()
    mail.outbox.clear()
    sc = Client(); sc.force_login(student)
    sc.post(f"/class/{klass.id}/request-join/")  # no crash, no email
    req = ClassJoinRequest.objects.get(klass=klass, student=student)
    tc = Client(); tc.force_login(teacher)
    r = tc.post(f"/class/request/{req.id}/approve/")
    assert r.status_code == 302
    assert ClassMembership.objects.filter(klass=klass, student=student, status="active").exists()
    assert len(mail.outbox) == 0


def test_joining_by_link_resolves_pending_request():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("f7")
    ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    sc = Client(); sc.force_login(student)
    sc.get(f"/class/join/{klass.join_code}/")
    req = ClassJoinRequest.objects.get(klass=klass, student=student)
    assert req.status == "approved"  # no longer lingering as pending
    # And it no longer clutters the teacher's pending list.
    tc = Client(); tc.force_login(teacher)
    body = tc.get(f"/class/{klass.id}/manage/").content.decode()
    assert "בקשות הצטרפות" not in body


def test_approve_is_idempotent():
    teacher = _teacher()
    klass = _class(teacher)
    student = _student("f8")
    req = ClassJoinRequest.objects.create(klass=klass, student=student, status="pending")
    tc = Client(); tc.force_login(teacher)
    tc.post(f"/class/request/{req.id}/approve/")
    mail.outbox.clear()
    tc.post(f"/class/request/{req.id}/approve/")  # second time = no-op
    assert ClassMembership.objects.filter(klass=klass, student=student, status="active").count() == 1
    assert Notification.objects.filter(user=student, verb="class_request_approved").count() == 1
    assert len(mail.outbox) == 0
