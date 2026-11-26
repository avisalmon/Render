"""SPR-M.90 - Lital, 2026-11-18 13:27, about the students' year path.

"תוריד את מחכה לאישור מוביל בפגישה ה 1 חשוב שלאחר שלקח חלק הוא ירשום שהוא היה נוכח".
No more waiting for the leader on מפגש 1: the student records being there.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm90-pass-1118"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student, StudentMeeting
    from tests.matazim_helpers import attach

    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(name="רשת עתיד")
    leader = Leader.objects.create(user=_user("leader90"), institution=inst, approved_at=timezone.now())
    kid = attach(_user("kid90"), leader=leader)
    kid2 = attach(_user("kid90b"), leader=leader)
    return {
        "leader": leader, "kid": kid, "kid2": kid2,
        "meeting": StudentMeeting.objects.order_by("number").first(),
        "student": Student.objects.get(user=kid), "student2": Student.objects.get(user=kid2),
    }


def _path(client):
    html = client.get("/matazim/my-path/").content.decode()
    return html[html.index('class="mz-path"'):html.index("</ol>", html.index('class="mz-path"'))]


def test_no_more_waiting_for_the_leader_and_a_button_to_record(client, world):
    client.force_login(world["kid"])
    path = _path(client)
    assert "מפגש 1: היכרות עם התכנית" in path
    assert "מחכה לאישור" not in path
    assert "עוד לא נרשמה נוכחות" in path
    assert f'action="/matazim/my-path/meeting/{world["meeting"].pk}/present/"' in path
    assert "הייתי במפגש" in path


def test_the_student_records_being_there_and_can_take_it_back(client, world):
    from matazim.models import StudentAttendance

    m = world["meeting"]
    client.force_login(world["kid"])
    resp = client.post(f"/matazim/my-path/meeting/{m.pk}/present/")
    assert resp.status_code == 302 and resp["Location"] == "/matazim/my-path/"
    row = StudentAttendance.objects.get(meeting=m)
    assert row.student == world["student"] and row.confirmed_by == world["kid"]
    path = _path(client)
    assert "הנוכחות נרשמה" in path and "ביטול הרישום" in path and "הייתי במפגש" not in path

    client.post(f"/matazim/my-path/meeting/{m.pk}/present/", {"undo": "1"})
    assert not StudentAttendance.objects.exists()


def test_recording_twice_keeps_one_row(client, world):
    from matazim.models import StudentAttendance

    client.force_login(world["kid"])
    for _ in range(2):
        client.post(f"/matazim/my-path/meeting/{world['meeting'].pk}/present/")
    assert StudentAttendance.objects.count() == 1


def test_it_only_ever_records_the_person_themselves(client, world):
    from matazim.models import StudentAttendance

    client.force_login(world["kid"])
    client.post(f"/matazim/my-path/meeting/{world['meeting'].pk}/present/",
                {"student": world["student2"].pk})
    assert list(StudentAttendance.objects.values_list("student_id", flat=True)) == [world["student"].pk]


def test_a_meeting_in_the_future_cannot_be_recorded(client, world):
    from matazim.models import StudentAttendance

    m = world["meeting"]
    m.on = timezone.localdate() + timedelta(days=5)
    m.save()
    client.force_login(world["kid"])
    assert "הייתי במפגש" not in _path(client)
    assert client.post(f"/matazim/my-path/meeting/{m.pk}/present/").status_code == 404
    assert not StudentAttendance.objects.exists()


def test_somebody_with_no_student_row_gets_no_button(client, db):
    client.force_login(_user("nobody90"))
    html = client.get("/matazim/my-path/").content.decode()
    assert "הייתי במפגש" not in html


def test_signed_out_and_get_are_refused(client, world):
    url = f"/matazim/my-path/meeting/{world['meeting'].pk}/present/"
    assert client.post(url).status_code == 302
    client.force_login(world["kid"])
    assert client.get(url).status_code == 405


def test_the_leader_sees_who_recorded_without_a_button_on_the_students_page(client, world):
    client.force_login(world["kid"])
    client.post(f"/matazim/my-path/meeting/{world['meeting'].pk}/present/")
    client.force_login(world["leader"].user)
    html = client.get("/matazim/leader/students/").content.decode()
    panel = html[html.index('id="mzStudentMeetings"'):html.index("</section>", html.index('id="mzStudentMeetings"'))]
    assert "נוכחות במפגשים" in panel and "1 מתוך 2 נרשמו כנוכחים" in panel
    assert "אישור השתתפות" not in panel
    page = client.get(f"/matazim/leader/students/{world['student'].pk}/").content.decode()
    assert "הנוכחות נרשמה" in page and "הייתי במפגש" not in page


def test_the_path_step_word_for_a_recorded_meeting(world):
    from matazim.models import StudentAttendance
    from matazim.track import path_steps

    StudentAttendance.objects.create(meeting=world["meeting"], student=world["student"],
                                     confirmed_by=world["kid"])
    steps = path_steps(world["kid"], world["student"], {}, [], today=date(2026, 11, 20))
    assert steps[0]["status"] == "done" and steps[0]["word"] == "הנוכחות נרשמה"


def test_the_api_lets_a_student_write_only_their_own_row(world):
    from rest_framework.test import APIClient

    from matazim.models import StudentAttendance

    api = APIClient()
    api.force_authenticate(world["kid"])
    mine = api.post("/matazim/api/student-attendance/",
                    {"meeting": world["meeting"].pk, "student": world["student"].pk}, format="json")
    assert mine.status_code == 201
    other = api.post("/matazim/api/student-attendance/",
                     {"meeting": world["meeting"].pk, "student": world["student2"].pk}, format="json")
    assert other.status_code in (400, 403)
    assert list(StudentAttendance.objects.values_list("student_id", flat=True)) == [world["student"].pk]
    assert api.delete(f"/matazim/api/student-attendance/{mine.data['id']}/").status_code == 204


def test_the_new_words_are_plain(world):
    from pathlib import Path

    roster = Path("templates/matazim/roster.html").read_text(encoding="utf-8")
    start = roster.index('id="mzStudentMeetings"')
    for text in (Path("templates/matazim/_year_path.html").read_text(encoding="utf-8"),
                 roster[start:roster.index("</section>", start)]):
        assert "—" not in text and "מט\"צ" not in text
