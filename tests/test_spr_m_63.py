"""SPR-M.63 - the year (REQ-M.186, REQ-M.187, REQ-M.180).

Atid's schedule for תשפ״ז is rows. What these tests protect: the ten rows are
the client's ten, seeding happens once and never overwrites an edit, only a
program manager of that institution writes them, a stranger can read them, and
the patrol is counted against ten without ever refusing an eleventh.
"""

import datetime
import importlib

import pytest
from django.apps import apps as real_apps
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm63

PASSWORD = "sprm63-pass-5521"
D = datetime.date


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst,
                                   approved_at=timezone.now())
    return {"inst": inst, "pm": pm, "leader": leader}


def _seed():
    migration = importlib.import_module("matazim.migrations.0040_seed_program_milestones")
    migration.seed(real_apps, None)


# ---------------------------------------------------------------- the seed


def test_the_seed_is_the_clients_ten_rows_in_her_order(world):
    from matazim.models import ProgramMilestone

    _seed()
    rows = list(ProgramMilestone.objects.filter(institution=world["inst"]))
    assert [r.title for r in rows] == [
        "זום חשיפה", "מבחן כניסה", "הכשרת מובילים", "גיוס תלמידים", "למידה עצמאית",
        "יום שיא 1", "למידה עצמאית", "יום שיא: הדרכה טובה", "פרקטיקום", "יום שיא מסכם",
    ]
    by_when = {r.when_text: r for r in rows}
    assert by_when["26.10.2026"].starts_on == D(2026, 10, 26)
    assert by_when["17.12.2026"].starts_on == D(2026, 12, 17)
    assert by_when["24.05.2027"].starts_on == D(2027, 5, 24)
    # Q24: the patrol deadline is built as 2026, not the mail's typo of 2027.
    assert by_when["עד אמצע נובמבר 2026"].ends_on == D(2026, 11, 15)
    assert [r.is_peak_day for r in rows].count(True) == 3


def test_seeding_twice_changes_nothing_and_never_overwrites_an_edit(world):
    """The one-time-import rule: the database is the source once it has rows."""
    from matazim.models import ProgramMilestone

    _seed()
    row = ProgramMilestone.objects.get(institution=world["inst"], when_text="17.12.2026")
    row.title = "יום שיא ראשון (עודכן)"
    row.save()
    ProgramMilestone.objects.filter(institution=world["inst"], when_text="24.05.2027").delete()

    _seed()

    assert ProgramMilestone.objects.filter(institution=world["inst"]).count() == 9
    edited = ProgramMilestone.objects.get(institution=world["inst"], when_text="17.12.2026")
    assert edited.title == "יום שיא ראשון (עודכן)"


# ------------------------------------------------------- now and next


def test_where_are_we_says_everything_under_way_and_the_next_one(world):
    from matazim.models import ProgramMilestone
    from matazim.year import where_are_we

    _seed()
    rows = list(ProgramMilestone.objects.filter(institution=world["inst"]))

    under, upcoming = where_are_we(rows, on=D(2026, 11, 3))
    # Early November: recruiting and independent learning are both live.
    assert {m.title for m in under} == {"גיוס תלמידים", "למידה עצמאית"}
    assert upcoming.title == "יום שיא 1"

    under, upcoming = where_are_we(rows, on=D(2026, 9, 1))
    assert under == [] and upcoming.title == "זום חשיפה"

    under, upcoming = where_are_we(rows, on=D(2027, 6, 1))
    assert under == [] and upcoming is None


# ------------------------------------------------------------ the screens


def test_a_stranger_reads_the_year_on_the_annual_path(client, world):
    _seed()
    html = client.get("/matazim/track/").content.decode()
    start = html.index('id="mzYear"')
    block = html[start:html.index("</section>", start)]
    assert block.count('class="mz-year-row') == 10
    assert "הכשרת מובילים" in block and "26.10.2026" in block


def test_the_banner_names_what_is_under_way_and_what_is_next(client, world, monkeypatch):
    import matazim.year as year

    _seed()
    monkeypatch.setattr(year, "today", lambda: D(2026, 11, 3))
    html = client.get("/matazim/track/").content.decode()
    start = html.index('class="mz-year-banner"')
    banner = html[start:html.index("</aside>", start)]
    assert "גיוס תלמידים" in banner and "יום שיא 1" in banner


def test_the_program_manager_edits_and_deletes_and_a_leader_cannot(client, world):
    from matazim.models import ProgramMilestone

    _seed()
    row = ProgramMilestone.objects.get(institution=world["inst"], when_text="17.12.2026")
    form = {"title": "יום שיא ראשון", "when_text": "17.12.2026", "starts_on": "2026-12-17",
            "ends_on": "", "stage": "peak", "activities": "x", "is_peak_day": "on", "order": "6"}

    client.force_login(world["leader"].user)
    assert client.post(f"/matazim/staff/milestones/{row.pk}/edit/", form).status_code == 403
    assert client.post(f"/matazim/staff/milestones/{row.pk}/delete/").status_code == 403
    assert ProgramMilestone.objects.filter(pk=row.pk, title="יום שיא 1").exists()

    client.force_login(world["pm"])
    assert client.post(f"/matazim/staff/milestones/{row.pk}/edit/", form).status_code == 302
    assert ProgramMilestone.objects.get(pk=row.pk).title == "יום שיא ראשון"
    assert client.post(f"/matazim/staff/milestones/{row.pk}/delete/").status_code == 302
    assert not ProgramMilestone.objects.filter(pk=row.pk).exists()


def test_a_program_manager_cannot_touch_another_institutions_schedule(client, world):
    from matazim.models import Institution, ProgramMilestone

    _seed()
    other = Institution.objects.create(name="רשת אחרת")
    other_pm = _user("otherpm")
    other.managers.add(other_pm)
    row = ProgramMilestone.objects.get(institution=world["inst"], when_text="17.12.2026")

    client.force_login(other_pm)
    assert client.post(f"/matazim/staff/milestones/{row.pk}/delete/").status_code == 404
    assert ProgramMilestone.objects.filter(pk=row.pk).exists()


def test_a_bad_row_is_refused_whole(client, world):
    from matazim.models import ProgramMilestone

    client.force_login(world["pm"])
    resp = client.post("/matazim/staff/milestones/", {
        "title": "x", "when_text": "x", "starts_on": "2026-12-17", "ends_on": "2026-12-01",
        "stage": "peak"})
    assert resp.status_code == 200
    assert "לא יכולה להסתיים לפני שהתחילה" in resp.content.decode()
    assert not ProgramMilestone.objects.filter(institution=world["inst"]).exists()


# ------------------------------------------------------------------ the API


def test_the_api_is_for_signed_in_people_to_read_and_the_managers_to_write(client, world):
    from matazim.models import ProgramMilestone

    _seed()
    assert client.get("/matazim/api/milestones/").status_code in (401, 403)  # a stranger
    client.force_login(world["leader"].user)
    body = client.get("/matazim/api/milestones/").json()
    assert len(body["results"] if isinstance(body, dict) else body) == 10
    client.logout()

    payload = {"title": "חדש", "when_text": "מאי", "starts_on": "2027-05-01", "stage": "peak"}
    assert client.post("/matazim/api/milestones/", payload).status_code in (401, 403)

    client.force_login(world["leader"].user)
    assert client.post("/matazim/api/milestones/", payload).status_code == 403

    client.force_login(world["pm"])
    resp = client.post("/matazim/api/milestones/", {**payload, "institution": 999})
    assert resp.status_code == 201, resp.content
    assert ProgramMilestone.objects.get(title="חדש").institution_id == world["inst"].pk

    resp = client.post("/matazim/api/milestones/", {**payload, "ends_on": "2027-04-01"})
    assert resp.status_code == 400


# --------------------------------------------------------------- the patrol


def _students(world, count, school="עתיד רמלה", status="in_training"):
    from matazim.models import Student, StudyClass

    klass = StudyClass.objects.create(leader=world["leader"], name="ט1", school_name=school)
    made = []
    for i in range(count):
        user = _user(f"{school}-{status}-{i}".replace(" ", ""))
        student = Student.objects.create(user=user, leader=world["leader"], status=status)
        student.classes.add(klass)
        made.append(student)
    return made


def test_the_patrol_counts_against_ten_and_never_refuses_an_eleventh(world):
    from matazim.models import Student
    from matazim.year import patrol_by_school

    _students(world, 11)
    rows = patrol_by_school(Student.objects.all())
    assert rows == [{"school": "עתיד רמלה", "count": 11, "target": 10, "missing": 0}]


def test_the_patrol_leaves_out_rejected_and_revoked_and_counts_each_school(world):
    from matazim.models import Student
    from matazim.year import patrol_by_school

    _students(world, 6, "עתיד רמלה")
    _students(world, 3, "עתיד חיפה")
    _students(world, 4, "עתיד רמלה", status="rejected")
    _students(world, 2, "עתיד רמלה", status="revoked")
    rows = {r["school"]: r for r in patrol_by_school(Student.objects.all())}
    assert rows["עתיד רמלה"]["count"] == 6 and rows["עתיד רמלה"]["missing"] == 4
    assert rows["עתיד חיפה"]["count"] == 3
    # Most-short first, so the school that needs somebody leads.
    assert [r["school"] for r in patrol_by_school(Student.objects.all())][0] == "עתיד חיפה"


def test_the_leader_sees_their_count_and_the_deadline_beside_it(client, world):
    _seed()
    _students(world, 4)
    client.force_login(world["leader"].user)
    html = client.get("/matazim/leader/").content.decode()
    start = html.index('class="mz-panel mz-patrol"')
    block = html[start:html.index("</section>", start)]
    assert "4 מתוך כ-10" in block and "חסרים 6" in block
    assert "15.11.2026" in block


def test_the_program_manager_sees_every_school(client, world):
    _seed()
    _students(world, 4, "עתיד רמלה")
    _students(world, 10, "עתיד חיפה")
    client.force_login(world["pm"])
    html = client.get("/matazim/staff/").content.decode()
    start = html.index('class="mz-panel mz-patrol"')
    block = html[start:html.index("</section>", start)]
    assert "עתיד רמלה" in block and "4 מתוך כ-10" in block
    assert "עתיד חיפה" in block and "הסיירת מלאה" in block
