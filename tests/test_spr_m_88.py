"""SPR-M.88 - the graduates' yearly track. Lital, 2026-11-18 (mail, 11:45).

"אני צריכים שתוסיף במסלול השנתי מפגש 1 – היכרות עם התכנית – חשוב שהמוביל יאשר
שכלל התלמידים לקחו חלק המוביל תמדי צריך לאשר לאורך כל הדרך וגם בהדרכות".

Read as: the graduates' yearly track gets meetings, starting with מפגש 1, היכרות
עם התכנית; the leader confirms who took part (all of them at once by default);
and a הדרכה a graduate finished waits for the leader's approval too.
"""

import importlib

import pytest
from django.utils import timezone

from tests.test_spr_m_84 import _graduate, _section, _user, world  # noqa: F401


@pytest.fixture
def meeting(world):  # noqa: F811
    from matazim.models import GraduateMeeting

    return GraduateMeeting.objects.create(institution=world["inst"], number=1, title="היכרות עם התכנית")


def _second(world):  # noqa: F811
    from matazim.models import Graduate

    return Graduate.objects.create(
        user=_user("grad2", "יואב"), full_name="יואב לוי", school=world["school"], leader=world["leader"],
        guardian_name="אמא", guardian_email="mom@example.com", guardian_signature="x",
        guardian_signed_at=timezone.now(), approved_at=timezone.now(),
    )


# ------------------------------------------------------------------ the seed


def test_meeting_one_is_seeded_once_and_never_again(db):
    from matazim.models import GraduateMeeting

    seed = importlib.import_module("matazim.migrations.0052_seed_graduate_meeting").seed
    from django.apps import apps

    first = GraduateMeeting.objects.order_by("number").first()
    assert first is not None and first.number == 1 and first.title == "היכרות עם התכנית"
    first.title = "שם שהצוות בחר"
    first.save()
    seed(apps, None)
    assert GraduateMeeting.objects.count() == 1
    assert GraduateMeeting.objects.get().title == "שם שהצוות בחר"


# ------------------------------------------------------------------ the graduate


def test_the_graduate_sees_the_track_and_whether_the_leader_confirmed(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    graduate = _graduate(world)
    client.force_login(world["grad_user"])
    html = _section(client.get("/matazim/graduates/practicum/").content.decode(), "mzGradTrack")
    assert "המסלול השנתי" in html and "מפגש 1: היכרות עם התכנית" in html
    assert "מחכה לאישור המוביל/ה" in html and "ההשתתפות אושרה" not in html

    GraduateAttendance.objects.create(meeting=meeting, graduate=graduate, confirmed_by=world["leader"].user)
    html = _section(client.get("/matazim/graduates/practicum/").content.decode(), "mzGradTrack")
    assert "ההשתתפות אושרה" in html


# ------------------------------------------------------------------ the leader


def test_the_leader_confirms_everybody_at_once(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    a = _graduate(world)
    b = _second(world)
    client.force_login(world["leader"].user)
    html = _section(client.get("/matazim/leader/graduates/").content.decode(), "mzGradMeetings")
    assert "מפגש 1: היכרות עם התכנית" in html
    assert f'name="graduate" value="{a.pk}" checked' in html and f'name="graduate" value="{b.pk}" checked' in html

    resp = client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/",
                       {"graduate": [a.pk, b.pk], "next": "/matazim/leader/graduates/"})
    assert resp.status_code == 302 and resp["Location"] == "/matazim/leader/graduates/"
    assert GraduateAttendance.objects.filter(meeting=meeting).count() == 2
    html = _section(client.get("/matazim/leader/graduates/").content.decode(), "mzGradMeetings")
    assert "2 מתוך 2 אושרו" in html and "כל הבוגרים השתתפו" in html

    client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/", {"undo": b.pk})
    assert list(GraduateAttendance.objects.values_list("graduate_id", flat=True)) == [a.pk]


def test_another_leader_cannot_confirm_my_graduates(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    a = _graduate(world)
    client.force_login(world["other"].user)
    client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/", {"graduate": [a.pk]})
    assert not GraduateAttendance.objects.exists()
    resp = client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/", {"undo": a.pk})
    assert resp.status_code == 403


def test_a_graduate_not_yet_approved_is_not_confirmed(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    a = _graduate(world, approved=False)
    client.force_login(world["leader"].user)
    client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/", {"graduate": [a.pk]})
    assert not GraduateAttendance.objects.exists()


def test_a_graduate_cannot_confirm_themselves(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    a = _graduate(world)
    client.force_login(world["grad_user"])
    client.post(f"/matazim/graduates/meeting/{meeting.pk}/confirm/", {"graduate": [a.pk]})
    assert not GraduateAttendance.objects.exists()


# ------------------------------------------------------------------ the הדרכות


@pytest.fixture
def finished(world, monkeypatch):  # noqa: F811
    """One הדרכה of the programme the graduate finished."""
    from app.models import Course

    from matazim import graduate_views
    from matazim.content import REQUIRED_COURSE_SLUGS

    slug = REQUIRED_COURSE_SLUGS[0]
    Course.objects.update_or_create(slug=slug, defaults={"title": "סקראץ׳ למתחילים"})
    grad_id = world["grad_user"].id

    def fake(graduates):
        return {g.user_id: ({slug: {"pct": 100, "done": 4, "total": 4}} if g.user_id == grad_id else {})
                for g in graduates}

    monkeypatch.setattr(graduate_views, "_per_course", fake)
    return slug


def test_a_finished_course_waits_for_the_leader_and_then_is_approved(client, world, finished):  # noqa: F811
    from matazim.models import GraduateCourseApproval

    graduate = _graduate(world)
    client.force_login(world["leader"].user)
    html = _section(client.get("/matazim/leader/graduates/").content.decode(), "mzGradMine")
    assert "השלים/ה את ההדרכה" in html and "סקראץ׳ למתחילים" in html and "אישור ההדרכה" in html

    resp = client.post(f"/matazim/graduates/{graduate.pk}/course-approve/",
                       {"slug": finished, "next": "/matazim/leader/graduates/"})
    assert resp.status_code == 302
    assert GraduateCourseApproval.objects.filter(graduate=graduate, course_slug=finished).exists()
    html = _section(client.get("/matazim/leader/graduates/").content.decode(), "mzGradMine")
    assert "אישור ההדרכה" not in html and "1 הדרכות אושרו" in html


def test_an_unfinished_course_cannot_be_approved(client, world, finished):  # noqa: F811
    from matazim.models import GraduateCourseApproval

    graduate = _graduate(world)
    client.force_login(world["leader"].user)
    resp = client.post(f"/matazim/graduates/{graduate.pk}/course-approve/", {"slug": "not-finished"})
    assert resp.status_code == 403
    assert not GraduateCourseApproval.objects.exists()


def test_the_graduate_card_says_waiting_then_approved(client, world, finished, monkeypatch):  # noqa: F811
    from matazim import access
    from matazim.models import GraduateCourseApproval

    graduate = _graduate(world)
    monkeypatch.setattr(access, "visible_course_slugs", lambda user: {finished})
    monkeypatch.setattr("matazim.progress.cohort_progress",
                        lambda people, slugs: {p.user_id: {finished: {"pct": 100}} for p in people})
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/courses/").content.decode()
    assert "הושלמה, מחכה לאישור המוביל/ה" in html
    GraduateCourseApproval.objects.create(graduate=graduate, course_slug=finished)
    html = client.get("/matazim/graduates/courses/").content.decode()
    assert "הושלמה ואושרה" in html


# ------------------------------------------------------------------ the team


def test_the_team_adds_and_deletes_meetings_and_sees_the_count(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateMeeting

    client.force_login(world["pm"])
    html = _section(client.get("/matazim/staff/graduates/").content.decode(), "mzGradMeetingsEdit")
    assert "מפגש 1: היכרות עם התכנית" in html and 'value="2"' in html
    client.post("/matazim/staff/graduates/", {"do": "add_meeting", "number": "2", "title": "תכנון הדרכה"})
    assert GraduateMeeting.objects.filter(number=2, title="תכנון הדרכה", institution=world["inst"]).exists()
    resp = client.post("/matazim/staff/graduates/", {"do": "add_meeting", "number": "", "title": "x"})
    assert "למפגש צריך מספר ונושא" in resp.content.decode()
    m2 = GraduateMeeting.objects.get(number=2)
    client.post("/matazim/staff/graduates/", {"do": "delete_meeting", "id": m2.pk})
    assert not GraduateMeeting.objects.filter(pk=m2.pk).exists()


def test_a_leader_cannot_edit_the_meetings(client, world, meeting):  # noqa: F811
    client.force_login(world["leader"].user)
    resp = client.post("/matazim/staff/graduates/", {"do": "add_meeting", "number": "2", "title": "x"})
    assert resp.status_code == 403


# ------------------------------------------------------------------ the API


def test_the_api_lets_the_leader_confirm_and_nobody_else(client, world, meeting):  # noqa: F811
    from matazim.models import GraduateAttendance

    a = _graduate(world)
    client.force_login(world["other"].user)
    resp = client.post("/matazim/api/graduate-attendance/", {"meeting": meeting.pk, "graduate": a.pk})
    assert resp.status_code == 403
    client.force_login(world["leader"].user)
    resp = client.post("/matazim/api/graduate-attendance/", {"meeting": meeting.pk, "graduate": a.pk})
    assert resp.status_code == 201
    assert GraduateAttendance.objects.get().confirmed_by == world["leader"].user
    client.force_login(world["grad_user"])
    assert client.get("/matazim/api/graduate-attendance/").json()
    assert client.get("/matazim/api/graduate-meetings/").status_code == 200
    resp = client.post("/matazim/api/graduate-meetings/", {"number": 3, "title": "x"})
    assert resp.status_code == 403
