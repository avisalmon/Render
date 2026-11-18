"""SPR-M.89 - Lital, 2026-11-18 (mails of 12:29 and 12:32).

12:29: "אני נכנסת ללינק של התלמידים של כיתה ט ולא רואה שבמסלול השנתי מופיע מפגש 1".
Read with her 11:45 mail: מפגש 1, היכרות עם התכנית, comes first on the grade 9
students' year path too, and the leader confirms that everybody took part.

12:32, about the letter to the grade 10 leaders: "חשוב שיהיה לבוגרי המטצים הסבר על
התהליך השנתי שלהם ומה אנחנו מצפים מהם לאורך השנה ... ותוסיף להם לינק לכניסה להסבר
אודות התהליך". A page open to anybody, linked from the graduates' door.
"""

import importlib
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm89-pass-1118"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student, StudentMeeting
    from tests.matazim_helpers import attach

    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(name="רשת עתיד")
    leader = Leader.objects.create(user=_user("leader89"), institution=inst, approved_at=timezone.now())
    other = Leader.objects.create(user=_user("other89"), institution=inst, approved_at=timezone.now())
    kid = attach(_user("kid89"), leader=leader)
    kid2 = attach(_user("kid89b"), leader=leader)
    stranger = attach(_user("kid89c"), leader=other)
    meeting = StudentMeeting.objects.order_by("number").first()
    return {
        "leader": leader, "other": other, "kid": kid, "meeting": meeting,
        "student": Student.objects.get(user=kid), "student2": Student.objects.get(user=kid2),
        "stranger": Student.objects.get(user=stranger),
    }


def _section(html, anchor):
    start = html.index(f'id="{anchor}"')
    return html[start:html.index("</section>", start)]


# ------------------------------------------------------------------ the seed


def test_meeting_one_is_seeded_once_and_never_again(db):
    from django.apps import apps

    from matazim.models import StudentMeeting

    first = StudentMeeting.objects.order_by("number").first()
    assert first is not None and first.number == 1 and first.title == "היכרות עם התכנית"
    first.title = "שם שהצוות בחר"
    first.save()
    importlib.import_module("matazim.migrations.0054_seed_student_meeting").seed(apps, None)
    assert StudentMeeting.objects.count() == 1
    assert StudentMeeting.objects.get().title == "שם שהצוות בחר"


# ------------------------------------------------------------------ the student's path


def test_meeting_one_comes_first_on_the_students_path(world):
    from matazim.track import path_steps

    steps = path_steps(world["kid"], world["student"], {}, [], today=date(2026, 11, 20))
    assert steps[0]["title"] == "מפגש 1: היכרות עם התכנית"
    assert steps[0]["word"] == "מחכה לאישור המוביל/ה" and steps[0]["status"] == "todo"
    assert steps[0]["month"] == "פתיחת התכנית"
    assert steps[1]["key"] == "scratch"


def test_the_student_sees_it_on_my_path_and_then_confirmed(client, world):
    from matazim.models import StudentAttendance

    client.force_login(world["kid"])
    html = client.get("/matazim/my-path/").content.decode()
    assert "מפגש 1: היכרות עם התכנית" in html and "מחכה לאישור המוביל/ה" in html
    StudentAttendance.objects.create(meeting=world["meeting"], student=world["student"],
                                     confirmed_by=world["leader"].user)
    html = client.get("/matazim/my-path/").content.decode()
    assert "ההשתתפות אושרה" in html


# ------------------------------------------------------------------ the leader


def test_the_leader_confirms_the_whole_group_at_once(client, world):
    from matazim.models import StudentAttendance

    m, a, b = world["meeting"], world["student"], world["student2"]
    client.force_login(world["leader"].user)
    html = _section(client.get("/matazim/leader/students/").content.decode(), "mzStudentMeetings")
    assert "מפגש 1: היכרות עם התכנית" in html
    assert f'name="student" value="{a.pk}" checked' in html and f'name="student" value="{b.pk}" checked' in html
    assert f'value="{world["stranger"].pk}"' not in html

    resp = client.post(f"/matazim/leader/meeting/{m.pk}/confirm/", {"student": [a.pk, b.pk]})
    assert resp.status_code == 302 and resp["Location"].startswith("/matazim/leader/students/")
    assert StudentAttendance.objects.filter(meeting=m).count() == 2
    html = _section(client.get("/matazim/leader/students/").content.decode(), "mzStudentMeetings")
    assert "2 מתוך 2 אושרו" in html and "כל המטצים השתתפו" in html

    client.post(f"/matazim/leader/meeting/{m.pk}/confirm/", {"undo": b.pk})
    assert list(StudentAttendance.objects.values_list("student_id", flat=True)) == [a.pk]


def test_the_leader_sees_it_on_the_students_page(client, world):
    from matazim.models import StudentAttendance

    StudentAttendance.objects.create(meeting=world["meeting"], student=world["student"])
    client.force_login(world["leader"].user)
    html = client.get(f"/matazim/leader/students/{world['student'].pk}/").content.decode()
    panel = _section(html, "mzStudentPath")
    assert "מפגש 1: היכרות עם התכנית" in panel and "ההשתתפות אושרה" in panel


def test_another_leader_cannot_confirm_my_students(client, world):
    from matazim.models import StudentAttendance

    m = world["meeting"]
    client.force_login(world["other"].user)
    client.post(f"/matazim/leader/meeting/{m.pk}/confirm/", {"student": [world["student"].pk]})
    assert not StudentAttendance.objects.filter(student=world["student"]).exists()
    StudentAttendance.objects.create(meeting=m, student=world["student"])
    resp = client.post(f"/matazim/leader/meeting/{m.pk}/confirm/", {"undo": world["student"].pk})
    assert resp.status_code == 404
    assert StudentAttendance.objects.filter(student=world["student"]).exists()


def test_a_student_cannot_confirm_themselves(client, world):
    from matazim.models import StudentAttendance

    client.force_login(world["kid"])
    resp = client.post(f"/matazim/leader/meeting/{world['meeting'].pk}/confirm/",
                       {"student": [world["student"].pk]})
    assert resp.status_code == 403
    assert not StudentAttendance.objects.exists()


# ------------------------------------------------------------------ the API


def test_the_api_lets_the_leader_confirm_and_refuses_the_student(world):
    from rest_framework.test import APIClient

    from matazim.models import StudentAttendance

    api = APIClient()
    api.force_authenticate(world["kid"])
    assert api.get("/matazim/api/student-meetings/").status_code == 200
    resp = api.post("/matazim/api/student-attendance/",
                    {"meeting": world["meeting"].pk, "student": world["student"].pk}, format="json")
    assert resp.status_code == 403
    assert api.post("/matazim/api/student-meetings/", {"number": 2, "title": "x"}, format="json").status_code == 403

    api.force_authenticate(world["other"].user)
    resp = api.post("/matazim/api/student-attendance/",
                    {"meeting": world["meeting"].pk, "student": world["student"].pk}, format="json")
    assert resp.status_code in (400, 403)
    assert not StudentAttendance.objects.exists()

    api.force_authenticate(world["leader"].user)
    resp = api.post("/matazim/api/student-attendance/",
                    {"meeting": world["meeting"].pk, "student": world["student"].pk}, format="json")
    assert resp.status_code == 201
    row = StudentAttendance.objects.get()
    assert row.confirmed_by == world["leader"].user
    assert api.delete(f"/matazim/api/student-attendance/{row.pk}/").status_code == 204


# ------------------------------------------------------------------ the graduates' process


def test_the_process_page_is_open_to_anybody_and_says_her_letter(client, db):
    resp = client.get("/matazim/graduates/process/")
    assert resp.status_code == 200
    html = resp.content.decode()
    for words in ("התהליך השנתי של בוגרי מטצים", "120 שעות מעורבות אישית", "מפגש 1: היכרות עם התכנית",
                  "ז׳, ח׳ וט׳", "4 עד 5 מפגשים", "יום השיא בחברת Intel", "רכז/ת המעורבות",
                  "מה אנחנו מצפים מכם", "נרשמים כאן"):
        assert words in html, words
    page = html[html.index('id="mzGradProcess"'):]
    assert "—" not in page and "מט\"צ" not in page and "קורס" not in page


def test_the_graduates_door_and_the_leader_link_to_the_process(client, world):
    html = client.get("/matazim/graduates/").content.decode()
    assert 'href="/matazim/graduates/process/"' in html
    client.force_login(world["leader"].user)
    html = client.get("/matazim/leader/graduates/").content.decode()
    assert 'href="/matazim/graduates/process/"' in html
