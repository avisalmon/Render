"""SPR-M.69 - Lital's second round, 2026-10-15 (mail to Avi, 18:11 and 18:13).

Her words: the name is מטצים; a new opening text; one prominent registration box
and a form with a full name and a school from a list; a menu of "about" on the
right and registration only; "המסלול שלי" shows the training path and the
certificate only at the end; "תהליך ההכשרה" instead of "טרום מטצ"; and a way for
the managers to see how the site looks to the student.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm69

PASSWORD = "sprm69-pass-2208"
SCHOOLS = ["עתיד חנה סנש", "עתיד סאג'ור", "עתיד יוצר צור ים", "עתיד אריאל",
           "עתיד יצחק שמיר", "עתיד יגאל אלון", "עתיד עמנואל מורנו"]


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst, approved_at=timezone.now())
    return {"pm": pm, "leader": leader}


def _nav(html):
    return html[html.index('id="mzNav"'):html.index("</nav>", html.index('id="mzNav"'))]


def _attached_kid(name="kid"):
    from matazim.models import MemberProfile
    from tests.matazim_helpers import attach

    kid = _user(name)
    MemberProfile.objects.update_or_create(user=kid, defaults={
        "entrance_test_passed_at": timezone.now(), "welcome_accepted_at": timezone.now(),
        "birth_year": timezone.now().year - 14, "guardian_consent_at": timezone.now()})
    return attach(kid)


# ------------------------------------------------------------- the schools


def test_the_seven_schools_are_seeded_and_are_rows(db):
    from matazim.models import School

    assert sorted(School.objects.values_list("name", flat=True)) == sorted(SCHOOLS)


def test_the_seed_never_puts_back_what_the_team_changed(db):
    import importlib

    from django.apps import apps

    from matazim.models import School

    School.objects.filter(name="עתיד אריאל").update(is_active=False, name="עתיד אריאל (ישן)")
    importlib.import_module("matazim.migrations.0045_seed_schools").seed(apps, None)
    assert School.objects.count() == 7 and not School.objects.filter(name="עתיד אריאל").exists()


def test_registration_asks_for_a_name_and_a_school_from_the_list(client, db):
    html = client.get("/matazim/register/").content.decode()
    select = html[html.index('name="school"'):]
    select = select[:select.index("</select>")]
    for name in SCHOOLS:
        assert name.replace("'", "&#x27;") in select or name in select


def _register(client, **over):
    from tests.matazim_helpers import school_pk

    data = {"name": "רותם", "email": "rotem@example.com", "password": PASSWORD,
            "school": school_pk(), "birth_year": "2012", "guardian_name": "רונית",
            "guardian_email": "p@example.com", "guardian_consent": "on", **over}
    return client.post("/matazim/register/", data)


def test_registration_saves_the_school_and_refuses_without_one(client, db):
    from matazim.models import MemberProfile, School

    resp = _register(client, school="")
    assert resp.status_code == 200 and "בית ספר מהרשימה" in resp.content.decode()
    assert not User.objects.filter(email="rotem@example.com").exists()

    chosen = School.objects.get(name="עתיד יגאל אלון")
    assert _register(client, school=chosen.pk).status_code == 302
    assert MemberProfile.objects.get(user__email="rotem@example.com").school == chosen


def test_a_retired_or_made_up_school_is_not_accepted(client, db):
    from matazim.models import School

    old = School.objects.get(name="עתיד אריאל")
    School.objects.filter(pk=old.pk).update(is_active=False)
    assert _register(client, school=old.pk).status_code == 200
    assert _register(client, school=99999).status_code == 200
    assert not User.objects.filter(email="rotem@example.com").exists()


def test_somebody_who_signed_up_with_google_is_asked_once_on_the_first_screen(client, db):
    from matazim.models import MemberProfile, School

    kid = _user("google-kid")
    client.force_login(kid)
    home = client.get("/matazim/").content.decode()
    assert 'action="/matazim/school/"' in home
    assert "ברוכים הבאים לתכנית מטצים, מצורף מבחן המיון." in home

    school = School.objects.first()
    client.post("/matazim/school/", {"school": school.pk})
    assert MemberProfile.objects.get(user=kid).school == school
    assert 'action="/matazim/school/"' not in client.get("/matazim/").content.decode()


# ------------------------------------------------------------------ the menu


def test_a_visitors_menu_is_about_on_the_right_and_registration_only(client, db):
    nav = _nav(client.get("/matazim/").content.decode())
    links = re.findall(r'<a href="([^"]+)"', nav)
    assert len(links) == 2
    assert links[0] == "/matazim/about/"          # first in the document is the right in RTL
    assert links[1].startswith("/matazim/register/") and "הרשמה לתכנית" in nav


# ---------------------------------------------------------------- the path


def test_the_path_is_her_list_by_months_and_the_certificate_comes_after(client, world):
    """Lital, 2026-10-15 (mail): remove all of the old training, and put in: a Scratch
    הדרכה, arriving at a peak day, a Python הדרכה, the good-instruction day, two
    elective הדרכות from what is left, two practicums, the closing peak day. By months."""
    from tests.test_spr_m_63 import _seed

    _seed()
    client.force_login(_attached_kid())
    html = client.get("/matazim/my-path/").content.decode()
    start = html.index('id="mzTrainingPath"')
    panel = html[start:html.index("</section>", start)]

    order = ["הדרכה על סקראץ", "הגעה ליום שיא", "הדרכה על פייתון", "הדרכה טובה",
             "2 הדרכות לבחירה", "2 פרקטיקומים", "הגעה ליום שיא מסכם", "ובסוף: תעודת מטצ"]
    positions = [panel.index(item) for item in order]
    assert positions == sorted(positions)
    for month in ("נובמבר–דצמבר 2026", "17.12.2026", "דצמבר–פברואר", "פברואר 2027",
                  "פברואר–מאי 2027", "24.05.2027"):
        assert month in panel
    # none of what she asked to take out
    for gone in ("הצטרפות למוביל", "סקראץ' 1", "סקראץ' 2", "סיום ההדרכה", "מטצ מוסמך"):
        assert gone not in panel
    assert panel.count('class="mz-path-node') == 7


def test_the_steps_know_how_far_the_member_is(db):
    from datetime import date

    from matazim.models import Student, TeachingSession
    from matazim.track import path_steps
    from tests.matazim_helpers import attach

    kid = attach(_user("steps"))
    student = Student.objects.get(user=kid)
    steps = {s["key"]: s for s in path_steps(kid, student, {}, [], today=date(2026, 11, 20))}
    assert steps["scratch"]["status"] == "todo" and steps["practicum"]["word"] == "0 מתוך 2"
    assert steps["peak1"]["word"] == "בהמשך"                      # no schedule row, never invented

    TeachingSession.objects.create(student=student, title="מפגש", happened_on=date(2027, 3, 1))
    steps = {s["key"]: s for s in path_steps(kid, student, {}, [], today=date(2027, 3, 2))}
    assert steps["practicum"]["status"] == "doing" and steps["practicum"]["word"] == "1 מתוך 2"


def test_a_peak_day_is_ahead_on_now_or_held_from_the_schedule_rows(world):
    from datetime import date

    from matazim.models import Institution, ProgramMilestone
    from matazim.track import path_steps
    from tests.matazim_helpers import attach

    inst = Institution.objects.order_by("created_at").first()
    rows = [ProgramMilestone(institution=inst, order=i, when_text="x", starts_on=d, stage="peak",
                             title="יום שיא", is_peak_day=True)
            for i, d in enumerate((date(2026, 12, 17), date(2027, 2, 10), date(2027, 5, 24)))]
    kid = attach(_user("peaks"))
    words = lambda today: [s["word"] for s in path_steps(kid, None, {}, rows, today=today)
                           if s["key"] in ("peak1", "good", "final")]
    assert words(date(2026, 12, 1)) == ["בהמשך", "בהמשך", "בהמשך"]
    assert words(date(2026, 12, 17)) == ["עכשיו", "בהמשך", "בהמשך"]
    assert words(date(2027, 3, 1)) == ["התקיים", "התקיים", "בהמשך"]


def test_the_winter_row_says_python_unless_the_team_changed_it(db):
    import importlib

    from django.apps import apps

    from matazim.models import Institution, ProgramMilestone

    inst = Institution.objects.create(name="רשת בדיקה")
    from datetime import date

    kept = ProgramMilestone.objects.create(
        institution=inst, order=1, when_text="x", starts_on=date(2026, 12, 18), title="למידה",
        activities="הצוות כתב משהו אחר")
    old = ProgramMilestone.objects.create(
        institution=inst, order=2, when_text="x", starts_on=date(2026, 12, 18), title="למידה",
        activities="שתי הדרכות תלת־ממד והכנת תוצר.")
    importlib.import_module("matazim.migrations.0046_python_in_the_winter_row").change(apps, None)
    kept.refresh_from_db(); old.refresh_from_db()
    assert kept.activities == "הצוות כתב משהו אחר"
    assert old.activities == "הדרכה על פייתון והכנת תוצר."


def test_finishing_a_course_is_called_finishing_the_course():
    import pathlib

    source = pathlib.Path("matazim/track.py").read_text(encoding="utf-8")
    assert "סיום ההדרכה:" in source and 'f"תעודה: {title}"' not in source


def test_the_state_before_certification_is_the_training_process(client, world):
    client.force_login(_attached_kid())
    home = client.get("/matazim/").content.decode()
    assert "תהליך ההכשרה" in home and "טרום מטצ" not in home


# --------------------------------------------------------------- the preview


def test_a_manager_can_look_at_the_site_at_each_stage_and_nothing_is_made(client, world):
    from matazim.models import EntranceAttempt, Student

    client.force_login(world["pm"])
    assert 'href="/matazim/preview/test/"' in client.get("/matazim/").content.decode()

    client.get("/matazim/preview/test/")
    html = client.get("/matazim/").content.decode()
    assert "אתם רואים את האתר כתלמיד" in html and "מבחן הכניסה" in html
    assert "ניהול" not in _nav(html)                                    # the student's menu only

    client.get("/matazim/preview/join/")
    assert client.get("/matazim/")["Location"] == "/matazim/join-leader/"
    page = client.get("/matazim/join-leader/").content.decode()
    assert "אתם רואים את האתר כתלמיד" in page
    resp = client.post("/matazim/join-leader/", {"leader": world["leader"].pk})
    assert "תצוגה בלבד" in resp.content.decode()
    assert not Student.objects.filter(user=world["pm"]).exists()

    client.get("/matazim/preview/member/")
    home = client.get("/matazim/").content.decode()
    assert home.count('class="mz-tile"') == 8 and 'class="mz-tile mz-tile-role"' not in home

    assert not EntranceAttempt.objects.exists()


def test_the_manager_can_stop_looking_and_is_themselves_again(client, world):
    client.force_login(world["pm"])
    client.get("/matazim/preview/test/")
    client.get("/matazim/preview/off/")
    html = client.get("/matazim/").content.decode()
    assert "אתם רואים את האתר כתלמיד" not in html
    assert 'class="mz-tile mz-tile-role"' in html


def test_the_gate_follows_the_stage_being_looked_at(client, world):
    client.force_login(world["pm"])
    assert client.get("/matazim/my-work/").status_code == 200
    client.get("/matazim/preview/test/")
    assert client.get("/matazim/my-work/")["Location"] == "/matazim/test/?gate=1"
    client.get("/matazim/preview/join/")
    assert client.get("/matazim/my-work/")["Location"] == "/matazim/join-leader/"


def test_only_root_managers_and_leaders_can_look(client, world):
    client.force_login(_user("kid"))
    assert client.get("/matazim/preview/test/").status_code == 403
    client.logout()
    assert client.get("/matazim/preview/test/").status_code in (302, 403)

    client.force_login(world["leader"].user)
    assert client.get("/matazim/preview/member/").status_code == 302
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    client.force_login(root)
    assert client.get("/matazim/preview/test/").status_code == 302
    assert client.get("/matazim/preview/nowhere/").status_code == 404
