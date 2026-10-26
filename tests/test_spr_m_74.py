"""SPR-M.74 - Taking a student out, what a leader sees on the row, any file for the test.

Lital, by mail, 2026-10-26 11:33: "מבקשת לוודא שכל מוביל יכול וגם ליטל ונעמי שיש להן
הרשאה יכולות להוציא תלמידים שנרשמו ולהסיר אותן".

Naomi, by mail, 2026-10-26 12:18: leaders should be able to "לאשר או למחוק תלמיד,
יכולת לראות את ההתקדמות של התלמידים והאם בצעו את המשימות ואת מבחן הכניסה".

Naomi, 12:19: "אפשר להעלות כל קובץ כהגשה, גם אם ירצו לעלות תמונה".

Removing deletes nothing (REQ-M.203); the row shows the test and the tasks
(REQ-M.204); any file may be handed in for the test, and a file that is not an STL
goes straight to a person (REQ-M.205).
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(
        username=f"{name}@example.com", email=f"{name}@example.com", password="sprm74-pass"
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": display or name})
    return user


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student, StudyClass

    pm = _user("pm")
    inst = Institution.objects.create(name="רשת עתיד")
    inst.managers.add(pm)
    liron = _user("liron", "לירון")
    leader = Leader.objects.create(user=liron, institution=inst, approved_at=timezone.now())
    other = Leader.objects.create(
        user=_user("dov", "דב"), institution=inst, approved_at=timezone.now()
    )
    kid = _user("yuval", "יובל")
    student = Student.objects.create(user=kid, leader=leader, status=Student.IN_TRAINING)
    group = StudyClass.objects.create(leader=leader, name="ז1")
    student.classes.add(group)
    theirs = Student.objects.create(
        user=_user("noa", "נועה"), leader=other, status=Student.IN_TRAINING
    )
    return {
        "pm": pm, "liron": liron, "leader": leader, "other": other,
        "student": student, "theirs": theirs, "group": group,
    }


# ------------------------------------------------------------------ REQ-M.203


def test_a_leader_takes_their_student_out_and_nothing_is_deleted(client, world):
    from matazim.models import StatusLog, Student

    student = world["student"]
    client.force_login(world["liron"])

    resp = client.post(
        reverse("matazim:student", args=[student.pk]),
        {"action": "remove", "note": "נרשם בטעות"},
    )

    assert resp.status_code == 302 and "removed=1" in resp["Location"]
    student.refresh_from_db()
    assert Student.objects.filter(pk=student.pk).exists()
    assert User.objects.filter(pk=student.user_id).exists()
    assert student.status == Student.REVOKED
    assert student.leader is None
    assert list(student.classes.all()) == []
    line = StatusLog.objects.filter(student=student).order_by("-pk").first()
    assert line.to_status == Student.REVOKED
    assert line.from_status == Student.IN_TRAINING
    assert line.from_leader == world["leader"]
    assert line.changed_by == world["liron"]
    assert line.note == "נרשם בטעות"

    # Off the leader's list, and the list says what happened.
    roster = client.get(reverse("matazim:roster") + "?removed=1").content.decode()
    assert 'id="mzRemoved"' in roster
    assert reverse("matazim:student", args=[student.pk]) not in roster
    assert client.get(reverse("matazim:student", args=[student.pk])).status_code == 404


def test_a_leader_cannot_take_out_another_leaders_student(client, world):
    from matazim.models import Student

    theirs = world["theirs"]
    client.force_login(world["liron"])

    resp = client.post(reverse("matazim:student", args=[theirs.pk]), {"action": "remove"})

    assert resp.status_code == 404
    theirs.refresh_from_db()
    assert theirs.status == Student.IN_TRAINING and theirs.leader == world["other"]


def test_a_leader_cannot_bring_back(client, world):
    from matazim.models import Student
    from matazim.removal import remove_student

    student = world["student"]
    remove_student(student, by=world["pm"])
    # Put them back with the leader by hand, so the page is reachable for the leader
    # and only the role decides.
    Student.objects.filter(pk=student.pk).update(leader=world["leader"])
    client.force_login(world["liron"])

    resp = client.post(reverse("matazim:student", args=[student.pk]), {"action": "restore"})

    assert resp.status_code == 403
    student.refresh_from_db()
    assert student.status == Student.REVOKED


def test_the_programme_team_takes_out_and_brings_back_to_the_same_leader(client, world):
    from matazim.models import Student

    student = world["student"]
    client.force_login(world["pm"])
    page = reverse("matazim:student", args=[student.pk])

    client.post(page, {"action": "remove"})
    student.refresh_from_db()
    assert student.status == Student.REVOKED and student.leader is None

    html = client.get(page).content.decode()
    assert "החזרה לתוכנית" in html

    client.post(page, {"action": "restore"})
    student.refresh_from_db()
    assert student.status == Student.IN_TRAINING
    assert student.leader == world["leader"]


def test_the_api_still_refuses_to_delete(client, world):
    client.force_login(world["pm"])
    resp = client.delete(f"/matazim/api/students/{world['student'].pk}/")
    assert resp.status_code in (403, 405)
    from matazim.models import Student

    assert Student.objects.filter(pk=world["student"].pk).exists()


def test_a_removed_student_leaves_the_school_counts(world):
    """`schools.py` already leaves out "revoked"; removing is what sets it."""
    from matazim.models import Student
    from matazim.removal import remove_student

    remove_student(world["student"], by=world["pm"])
    counted = Student.objects.exclude(status__in=(Student.REJECTED, Student.REVOKED))
    assert world["student"].pk not in set(counted.values_list("pk", flat=True))


# ------------------------------------------------------------------ REQ-M.204


def _attempt(user, *, passed, decision="", name="m.stl"):
    from matazim.models import EntranceAttempt
    from matazim.views import member_profile

    return EntranceAttempt.objects.create(
        member=member_profile(user), target_id="t0000", number=1, passed=passed,
        decision=decision, submitted_at=timezone.now(),
        model_file=SimpleUploadedFile(name, b"x"),
    )


def _row(html, student):
    """The one roster row for this student, not the page."""
    href = f'href="{reverse("matazim:student", args=[student.pk])}"'
    start = html.index(href)
    return html[start:html.index("</li>", start)]


def test_the_roster_row_shows_the_test_and_the_tasks(client, world):
    from matazim.models import EntranceAttempt, Submission

    student = world["student"]
    _attempt(student.user, passed=True, decision=EntranceAttempt.APPROVED)
    for status in (Submission.APPROVED, Submission.APPROVED, Submission.WAITING):
        Submission.objects.create(student=student, leader=world["leader"], title="x",
                                  status=status)
    client.force_login(world["liron"])

    row = _row(client.get(reverse("matazim:roster")).content.decode(), student)

    assert 'data-test="approved"' in row
    assert "2 אושרו" in row
    assert "1 מחכות לכם" in row


def test_a_student_with_nothing_handed_in_says_so(client, world):
    client.force_login(world["liron"])
    row = _row(client.get(reverse("matazim:roster")).content.decode(), world["student"])
    assert 'data-test="none"' in row
    assert "לא הוגש" in row
    assert "עוד לא הוגשו" in row


def test_the_student_page_shows_the_test_waiting(client, world):
    student = world["student"]
    _attempt(student.user, passed=True)
    client.force_login(world["liron"])

    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()
    panel = html[html.index('id="mzStudentTest"'):]
    panel = panel[:panel.index("</section>")]
    assert "מחכה לצוות" in panel


# ------------------------------------------------------------------ REQ-M.205


def test_a_file_that_is_not_an_stl_is_waiting_for_a_person(db):
    from matazim import entrance_review

    kid = _user("photo")
    attempt = _attempt(kid, passed=False, name="photo.jpg")
    assert entrance_review.attempt_state(attempt) == "waiting"

    stl = _attempt(_user("stl"), passed=False, name="m.stl")
    assert entrance_review.attempt_state(stl) == entrance_review.RETRY


def test_the_test_page_takes_any_file_and_sends_a_picture_to_the_team(client, db):
    from matazim import entrance_review
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    kid = _user("dana")
    client.force_login(kid)
    form = client.get(reverse("matazim:test_task")).content.decode()
    field = form[form.index('name="model_file"'):]
    field = field[:field.index(">")]
    assert "accept=" not in field

    resp = client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("keychain.png", b"\x89PNG not measured")},
    )

    html = resp.content.decode()
    assert 'id="mzFileOnly"' in html
    attempt = EntranceAttempt.objects.get(member__user=kid)
    assert attempt.submitted_at is not None and attempt.model_file
    assert attempt.model_file.name.endswith(".png")
    assert attempt.issues == []
    assert entrance_review.attempt_state(attempt) == "waiting"

    # Coming back, they are waiting for the team, not handed a new object.
    again = client.get(reverse("matazim:test_task")).content.decode()
    assert 'id="mzWaitingTeam"' in again


def test_the_team_can_approve_a_picture(client, db):
    from matazim.models import EntranceAttempt, Institution
    from matazim.views import member_profile

    pm = _user("pm2")
    Institution.objects.create(name="רשת").managers.add(pm)
    kid = _user("pic")
    attempt = _attempt(kid, passed=False, name="photo.jpg")
    client.force_login(pm)

    listing = client.get(reverse("matazim:staff_entrance") + "?state=waiting")
    assert listing.status_code == 200
    assert reverse("matazim:decide_attempt", args=[attempt.pk]) in listing.content.decode()
    client.post(reverse("matazim:decide_attempt", args=[attempt.pk]), {"action": "approve"})

    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED
    assert member_profile(kid).entrance_test_passed_at is not None
