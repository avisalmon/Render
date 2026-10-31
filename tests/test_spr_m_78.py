"""SPR-M.78 - A leader takes an approved student into the patrol and their own group.

Lital, by mail, 2026-10-31: "מרגע שיש מבחן כניסה והתלמיד העלה את הקובץ אנחנו
רוצות שלמוביל יהיה אופציה לאשר ולהכניס אותו לסיירת ... שיישלח לתלמיד הודעה
שעבר את מבחני המיון לתכנית מטצים ונכנס לסיירת ... שלמוביל תהיה אופציה לשליחת
הודעה ... להכניס את התלמיד לקבוצה של המוביל" (REQ-M.209).
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

PNG = b"\x89PNG\r\n\x1a\n not really a picture"
PATROL = "עברת את מבחני המיון לתכנית מטצים ונכנסת לסיירת"


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(
        username=f"{name}@example.com", email=f"{name}@example.com", password="sprm78-pass"
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": display or name})
    return user


def _profile(user, school=None):
    from matazim.views import member_profile

    profile = member_profile(user)
    if school is not None:
        profile.school = school
        profile.save(update_fields=["school"])
    return profile


def _attempt(user):
    from matazim.models import EntranceAttempt

    return EntranceAttempt.objects.create(
        member=_profile(user), target_id="t0000", number=1, passed=False,
        submitted_at=timezone.now(), model_file=SimpleUploadedFile("keychain.png", PNG),
    )


@pytest.fixture
def world(db, monkeypatch):
    from matazim import consent
    from matazim.models import Institution, Leader, School

    monkeypatch.setattr(consent, "needs_guardian_consent", lambda profile: False)
    north = School.objects.create(name="עתיד צפון")
    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm", "נעמי")
    inst.managers.add(pm)
    liron = Leader.objects.create(user=_user("liron", "לירון"), institution=inst,
                                  approved_at=timezone.now())
    _profile(liron.user, north)
    noa = _user("noa", "נועה")
    _profile(noa, north)
    return {"pm": pm, "liron": liron, "noa": noa, "north": north, "inst": inst}


def _decide(client, attempt, **data):
    return client.post(reverse("matazim:leader_decide", args=[attempt.pk]), data)


def test_the_form_offers_the_group_and_the_message_ticked(client, world):
    _attempt(world["noa"])
    client.force_login(world["liron"].user)
    html = client.get(reverse("matazim:leader_tests")).content.decode()
    assert "אישור והכנסה לסיירת" in html
    assert 'name="group" value="1" checked' in html and "להכניס לקבוצה שלי" in html
    assert 'name="tell" value="1" checked' in html
    assert "הודעה שעבר/ה את מבחני המיון ונכנס/ה לסיירת" in html


def test_approve_take_into_group_and_tell(client, world):
    from matazim.models import Notification, Student

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    mail.outbox.clear()

    resp = _decide(client, attempt, action="approve", group="1", tell="1")
    assert resp.status_code == 302 and "group=in" in resp["Location"] and "told=1" in resp["Location"]

    attempt.refresh_from_db()
    assert attempt.member.has_passed_entrance_test()
    student = Student.objects.get(user=world["noa"])
    assert student.leader == world["liron"] and student.status == Student.IN_TRAINING
    note = Notification.objects.get(user=world["noa"], kind=Notification.ENTRANCE_APPROVED)
    assert PATROL in note.text
    assert [m.to for m in mail.outbox] == [["noa@example.com"]]
    assert PATROL in mail.outbox[0].body

    html = client.get(resp["Location"]).content.decode()
    assert "נועה בקבוצה שלכם עכשיו" in html
    assert "נשלחה לנועה הודעה" in html


def test_approve_without_the_options_does_neither(client, world):
    from matazim.models import Notification, Student

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    mail.outbox.clear()

    _decide(client, attempt, action="approve")
    attempt.refresh_from_db()
    assert attempt.member.has_passed_entrance_test()
    assert not Student.objects.filter(user=world["noa"]).exists()
    assert not Notification.objects.filter(user=world["noa"]).exists()
    assert mail.outbox == []


def test_after_approving_the_group_and_the_message_each_on_their_own(client, world):
    from matazim.models import Notification, Student

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="approve")

    html = client.get(reverse("matazim:leader_tests")).content.decode()
    assert "הכנסה לקבוצה שלי" in html and "שליחת הודעה על מעבר לסיירת" in html

    _decide(client, attempt, action="tell")
    assert Notification.objects.filter(user=world["noa"], text__contains=PATROL).count() == 1
    assert not Student.objects.filter(user=world["noa"]).exists()

    _decide(client, attempt, action="group")
    assert Student.objects.get(user=world["noa"]).leader == world["liron"]
    html = client.get(reverse("matazim:leader_tests")).content.decode()
    assert "בקבוצה שלכם." in html and "הכנסה לקבוצה שלי" not in html


def test_group_and_tell_need_an_approved_test(client, world):
    from matazim.models import Notification, Student

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="group")
    _decide(client, attempt, action="tell")
    assert not Student.objects.filter(user=world["noa"]).exists()
    assert not Notification.objects.filter(user=world["noa"]).exists()


def test_a_student_without_a_parents_consent_is_approved_but_not_taken_in(client, world, monkeypatch):
    from matazim import consent
    from matazim.models import Student

    monkeypatch.setattr(consent, "needs_guardian_consent", lambda profile: True)
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)

    html = client.get(reverse("matazim:leader_tests")).content.decode()
    assert 'name="group"' not in html and "אחרי שההורים יאשרו" in html

    resp = _decide(client, attempt, action="approve", group="1", tell="1")
    assert "group=consent" in resp["Location"]
    attempt.refresh_from_db()
    assert attempt.member.has_passed_entrance_test()
    assert not Student.objects.filter(user=world["noa"]).exists()
    assert "עוד אין אישור הורים" in client.get(resp["Location"]).content.decode()


def test_a_student_taken_out_is_not_taken_back_in_by_a_leader(client, world):
    from matazim.models import Student

    Student.objects.create(user=world["noa"], status=Student.REVOKED)
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    resp = _decide(client, attempt, action="approve", group="1")
    assert "group=out" in resp["Location"]
    student = Student.objects.get(user=world["noa"])
    assert student.leader is None and student.status == Student.REVOKED


def test_a_student_who_asked_for_nobody_yet_is_taken_in(client, world):
    from matazim.models import Student, StatusLog

    Student.objects.create(user=world["noa"], status=Student.APPLIED)
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="approve", group="1")
    student = Student.objects.get(user=world["noa"])
    assert student.leader == world["liron"] and student.status == Student.IN_TRAINING
    assert StatusLog.objects.filter(student=student).exists()


def test_looking_as_the_leader_cannot_take_anyone_in(client, world):
    from matazim.models import Student

    attempt = _attempt(world["noa"])
    client.force_login(world["pm"])
    client.get(f"/matazim/as-leader/?leader={world['liron'].pk}")
    assert _decide(client, attempt, action="approve", group="1", tell="1").status_code == 403
    assert not Student.objects.filter(user=world["noa"]).exists()


def test_the_patrol_counts_the_student_taken_in(client, world):
    from matazim.models import Student
    from matazim.year import patrol_by_school

    from matazim.models import StudyClass

    StudyClass.objects.create(leader=world["liron"], name="ט1", school_name="עתיד צפון")
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="approve", group="1")
    rows = patrol_by_school(Student.objects.filter(leader=world["liron"]))
    assert rows[0]["school"] == "עתיד צפון" and rows[0]["count"] == 1
