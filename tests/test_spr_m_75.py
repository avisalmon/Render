"""SPR-M.75 - A leader opens the file a student handed in.

Lital, by mail, 2026-10-28 18:37: "תלמידים מעלים תוצרים לאתר ומובילי התכנית לא
קוראים את הקובץ שמעלים".

What was found: the student's page told a leader where the screening test stood
(SPR-M.74) and had no way to open the file behind it, and a hand-in's file could
only be downloaded, which on a phone is a picture that goes nowhere. Now the test
file is on the student's page, a picture is shown on the page, and "פתיחת הקובץ"
opens a picture or a PDF in the browser (REQ-M.206). Who may open a file did not
widen, except that a student's leader now may open work the student handed to an
earlier leader.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

PNG = b"\x89PNG\r\n\x1a\n not really a picture"


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(
        username=f"{name}@example.com", email=f"{name}@example.com", password="sprm75-pass"
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": display or name})
    return user


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student

    pm = _user("pm")
    inst = Institution.objects.create(name="רשת עתיד")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("liron", "לירון"), institution=inst,
                                   approved_at=timezone.now())
    other = Leader.objects.create(user=_user("dov", "דב"), institution=inst,
                                  approved_at=timezone.now())
    student = Student.objects.create(user=_user("yuval", "יובל"), leader=leader,
                                     status=Student.IN_TRAINING)
    return {"pm": pm, "leader": leader, "other": other, "student": student}


def _attempt(user, name):
    from matazim.models import EntranceAttempt
    from matazim.views import member_profile

    return EntranceAttempt.objects.create(
        member=member_profile(user), target_id="t0000", number=1, passed=False,
        submitted_at=timezone.now(), model_file=SimpleUploadedFile(name, PNG),
    )


def _hand_in(student, name="keychain.png"):
    from matazim.models import Submission

    return Submission.objects.create(
        student=student, leader=student.leader, title="מחזיק מפתחות",
        work_file=SimpleUploadedFile(name, PNG),
    )


def _panel(html):
    part = html[html.index('id="mzStudentTest"'):]
    return part[:part.index("</section>")]


# ------------------------------------------------------- the screening test file


def test_the_student_page_opens_the_test_file(client, world):
    student = world["student"]
    attempt = _attempt(student.user, "photo.png")
    client.force_login(world["leader"].user)

    panel = _panel(client.get(reverse("matazim:student", args=[student.pk])).content.decode())

    url = reverse("matazim:attempt_file", args=[attempt.pk])
    assert 'id="mzStudentTestFile"' in panel
    assert f'{url}?view=1' in panel and "פתיחת הקובץ" in panel
    assert "<img" in panel, "a picture should be on the page"

    resp = client.get(url + "?view=1")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert "attachment" not in resp.get("Content-Disposition", "")
    assert b"".join(resp.streaming_content) == PNG


def test_an_stl_is_a_download_not_a_picture(client, world):
    student = world["student"]
    attempt = _attempt(student.user, "model.stl")
    client.force_login(world["leader"].user)

    panel = _panel(client.get(reverse("matazim:student", args=[student.pk])).content.decode())
    assert "<img" not in panel
    assert "הורדת הקובץ" in panel

    resp = client.get(reverse("matazim:attempt_file", args=[attempt.pk]) + "?view=1")
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment")


def test_the_programme_team_opens_the_test_file(client, world):
    attempt = _attempt(world["student"].user, "photo.jpg")
    client.force_login(world["pm"])
    resp = client.get(reverse("matazim:attempt_file", args=[attempt.pk]) + "?view=1")
    assert resp.status_code == 200 and resp["Content-Type"] == "image/jpeg"


def test_another_leader_still_cannot_open_it(client, world):
    attempt = _attempt(world["student"].user, "photo.png")
    client.force_login(world["other"].user)
    assert client.get(reverse("matazim:attempt_file", args=[attempt.pk])).status_code == 404


def test_no_file_no_panel(client, world):
    client.force_login(world["leader"].user)
    html = client.get(reverse("matazim:student", args=[world["student"].pk])).content.decode()
    assert 'id="mzStudentTestFile"' not in _panel(html)


# ------------------------------------------------------------ a hand-in's file


def test_the_review_page_shows_a_picture_and_opens_it(client, world):
    work = _hand_in(world["student"])
    client.force_login(world["leader"].user)

    html = client.get(reverse("matazim:review", args=[work.pk])).content.decode()
    url = reverse("matazim:work_file", args=[work.pk])
    assert 'id="mzWorkPicture"' in html
    assert f'{url}?view=1' in html and "פתיחת הקובץ" in html and "הורדת הקובץ" in html

    resp = client.get(url + "?view=1")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert "attachment" not in resp.get("Content-Disposition", "")

    download = client.get(url)
    assert download["Content-Disposition"].startswith("attachment")


def test_an_svg_is_never_shown_inline(client, world):
    work = _hand_in(world["student"], name="drawing.svg")
    client.force_login(world["leader"].user)
    resp = client.get(reverse("matazim:work_file", args=[work.pk]) + "?view=1")
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment")
    html = client.get(reverse("matazim:review", args=[work.pk])).content.decode()
    assert 'id="mzWorkPicture"' not in html


def test_the_new_leader_opens_work_handed_to_the_old_one(client, world):
    student = world["student"]
    work = _hand_in(student)
    student.leader = world["other"]
    student.save(update_fields=["leader"])

    client.force_login(world["other"].user)
    assert client.get(reverse("matazim:review", args=[work.pk])).status_code == 200
    assert client.get(reverse("matazim:work_file", args=[work.pk])).status_code == 200


def test_a_stranger_leader_still_gets_nothing(client, world):
    from matazim.models import Leader

    work = _hand_in(world["student"])
    stranger = Leader.objects.create(user=_user("ronit"), institution=world["leader"].institution,
                                     approved_at=timezone.now())
    client.force_login(stranger.user)
    assert client.get(reverse("matazim:work_file", args=[work.pk])).status_code == 404
    assert client.get(reverse("matazim:review", args=[work.pk])).status_code == 404
