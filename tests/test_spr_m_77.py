"""SPR-M.77 - A leader sees who took the entrance test, and approves them or not.

Naomi, by mail, 2026-10-29: "אני רוצה שלמובילים יהיה כפתור בולט בעמוד הראשי ובו
הם יוכלו לראות את כל מי שביצע את מבחן הכניסה כולל את הקובץ הסופי שהתלמיד העלאה.
לייד כל תלמיד כזה תהיה האפשרות האם לאשר את התלמיד להצטרפות לאתר או האם לא לאשר
אותו ... התלמידים כמובן יקבלו הודעה על כך שהם מאושרים באתר".

The test comes before joining a leader, so a test-taker is nobody's student yet.
A leader sees their own students' hand-ins and those of test-takers who chose the
leader's school when they signed up (REQ-M.208). Nobody else's.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

PNG = b"\x89PNG\r\n\x1a\n not really a picture"


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(
        username=f"{name}@example.com", email=f"{name}@example.com", password="sprm77-pass"
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


def _attempt(user, name="keychain.png"):
    from matazim.models import EntranceAttempt

    return EntranceAttempt.objects.create(
        member=_profile(user), target_id="t0000", number=1, passed=False,
        submitted_at=timezone.now(), model_file=SimpleUploadedFile(name, PNG),
    )


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, School, Student

    north = School.objects.create(name="עתיד צפון")
    south = School.objects.create(name="עתיד דרום")
    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm", "נעמי")
    inst.managers.add(pm)
    liron = Leader.objects.create(user=_user("liron", "לירון"), institution=inst,
                                  approved_at=timezone.now())
    _profile(liron.user, north)
    dov = Leader.objects.create(user=_user("dov", "דב"), institution=inst,
                                approved_at=timezone.now())
    _profile(dov.user, south)

    noa = _user("noa", "נועה מהצפון")
    _profile(noa, north)
    gal = _user("gal", "גל מהדרום")
    _profile(gal, south)
    # Took the test at Liron's school, and is already Dov's student.
    tom = _user("tom", "תום של דב")
    _profile(tom, north)
    Student.objects.create(user=tom, leader=dov)
    return {"pm": pm, "liron": liron, "dov": dov, "noa": noa, "gal": gal, "tom": tom,
            "north": north}


def test_the_home_page_has_the_prominent_button(client, world):
    _attempt(world["noa"])
    client.force_login(world["liron"].user)
    html = client.get("/matazim/").content.decode()
    assert 'id="mzLeaderTestsButton"' in html
    assert reverse("matazim:leader_tests") in html
    assert "מבחני הכניסה של התלמידים" in html and "1 מחכים לאישור" in html


def test_the_leaders_area_has_the_button_too(client, world):
    _attempt(world["noa"])
    client.force_login(world["liron"].user)
    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert 'id="mzLeaderTestsButton"' in html


def test_a_student_sees_no_button(client, world):
    client.force_login(world["gal"])
    assert 'id="mzLeaderTestsButton"' not in client.get("/matazim/").content.decode()


def test_the_list_is_the_leaders_school_with_the_file(client, world):
    noa_try = _attempt(world["noa"])
    _attempt(world["gal"])
    _attempt(world["tom"])
    client.force_login(world["liron"].user)

    resp = client.get(reverse("matazim:leader_tests"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "נועה מהצפון" in html
    assert "גל מהדרום" not in html, "another school's test-taker"
    assert "תום של דב" not in html, "another leader's student"
    file_url = reverse("matazim:attempt_file", args=[noa_try.pk])
    assert f"{file_url}?view=1" in html and "<img" in html
    assert "פתיחת הקובץ" in html
    assert reverse("matazim:leader_decide", args=[noa_try.pk]) in html
    # SPR-M.78 renamed the button: approving is entering the patrol (Lital, 2026-10-31).
    assert "אישור והכנסה לסיירת" in html and "לא לאשר" in html


def test_the_leader_opens_the_file(client, world):
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    resp = client.get(reverse("matazim:attempt_file", args=[attempt.pk]) + "?view=1")
    assert resp.status_code == 200 and resp["Content-Type"] == "image/png"

    client.force_login(world["dov"].user)
    assert client.get(reverse("matazim:attempt_file", args=[attempt.pk])).status_code == 404


def test_a_class_at_the_school_counts_as_the_leaders_school(client, world):
    from matazim.models import Leader, StudyClass

    ronit = Leader.objects.create(user=_user("ronit", "רונית"), institution=world["liron"].institution,
                                  approved_at=timezone.now())
    StudyClass.objects.create(leader=ronit, name="ט1", school_name="עתיד צפון")
    _attempt(world["noa"])
    client.force_login(ronit.user)
    assert "נועה מהצפון" in client.get(reverse("matazim:leader_tests")).content.decode()


def test_approving_lets_the_student_in_and_tells_them(client, world):
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    mail.outbox.clear()

    # SPR-M.78: telling is the leader's option, ticked by default on the form.
    resp = client.post(reverse("matazim:leader_decide", args=[attempt.pk]),
                       {"action": "approve", "tell": "1"})
    assert resp.status_code == 302

    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED
    assert attempt.decided_by == world["liron"].user
    assert attempt.member.has_passed_entrance_test()
    assert Notification.objects.filter(user=world["noa"], kind=Notification.ENTRANCE_APPROVED).exists()
    assert [m.to for m in mail.outbox] == [["noa@example.com"]]
    assert "עברת את מבחני המיון לתכנית מטצים ונכנסת לסיירת" in mail.outbox[0].body


def test_not_approving_needs_words_and_tells_them(client, world):
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    url = reverse("matazim:leader_decide", args=[attempt.pk])

    resp = client.post(url, {"action": "return", "note": "  "})
    assert "error=note" in resp["Location"]
    attempt.refresh_from_db()
    assert attempt.decision != EntranceAttempt.RETURNED

    mail.outbox.clear()
    client.post(url, {"action": "return", "note": "חסר החור למחזיק"})
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.RETURNED
    assert attempt.decision_note == "חסר החור למחזיק"
    assert not attempt.member.has_passed_entrance_test()
    assert Notification.objects.filter(user=world["noa"], kind=Notification.ENTRANCE_RETURNED).exists()
    assert [m.to for m in mail.outbox] == [["noa@example.com"]]


def test_a_leader_cannot_decide_another_schools_test(client, world):
    attempt = _attempt(world["gal"])
    client.force_login(world["liron"].user)
    resp = client.post(reverse("matazim:leader_decide", args=[attempt.pk]), {"action": "approve"})
    assert resp.status_code == 404
    attempt.refresh_from_db()
    assert attempt.decision == "waiting" and attempt.decided_by is None


def test_a_student_cannot_open_the_list_or_decide(client, world):
    attempt = _attempt(world["noa"])
    client.force_login(world["gal"])
    assert client.get(reverse("matazim:leader_tests")).status_code == 403
    assert client.post(reverse("matazim:leader_decide", args=[attempt.pk]),
                       {"action": "approve"}).status_code == 403


def test_looking_as_the_leader_reads_and_cannot_decide(client, world):
    attempt = _attempt(world["noa"])
    client.force_login(world["pm"])
    client.get(f"/matazim/as-leader/?leader={world['liron'].pk}")

    html = client.get(reverse("matazim:leader_tests")).content.decode()
    assert "נועה מהצפון" in html
    assert reverse("matazim:leader_decide", args=[attempt.pk]) not in html
    assert client.post(reverse("matazim:leader_decide", args=[attempt.pk]),
                       {"action": "approve"}).status_code == 403
    attempt.refresh_from_db()
    assert attempt.decision == "waiting" and attempt.decided_by is None


def test_the_programme_team_screen_still_decides(client, world):
    from matazim.models import EntranceAttempt

    attempt = _attempt(world["gal"])
    client.force_login(world["pm"])
    client.post(reverse("matazim:decide_attempt", args=[attempt.pk]), {"action": "approve"})
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED
