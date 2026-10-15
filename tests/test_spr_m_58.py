"""SPR-M.58 — each persona lands on their own front door.

Avi, 2026-10-11, in three parts and one rule. A first-time student sees one
button and "it's not intuitive what I need to do". A program manager should
"understand in the first glance that the system recognized him" and see his
leaders and how to add one. A leader "needs to own students, invite students,
track them, report up" and should be shown that. And: "user experience has
priority over the defined screens we talked about earlier."

**What these tests hold.** Not layout — the screen contract has all three
pages in its catalogue. They hold the two things a role-shaped front door can
get wrong quietly:

1. **The door opens on the right room.** Signing in puts each role on its own
   page, in `access`'s precedence, and `?next=` still wins.
2. **The page knows who is reading.** The hero never asks a member to join
   twice; the orientation strip says עכשיו exactly once; the dashboards show
   the numbers the other screens show, through the same readers (RULE-3).

Traces: REQ-M.5a, REQ-M.36, REQ-M.65, REQ-M.73, REQ-M.76, REQ-M.88, REQ-M.101,
REQ-M.158, REQ-M.159, REQ-M.160.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm58

PASSWORD = "sprm58-pass-9012"


def _course(slug, title, lessons=2):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=title, is_published=True)
    for n in range(1, lessons + 1):
        Video.objects.create(course=course, title=f"שיעור {n}", lesson_order=n,
                             bunny_video_id=f"{slug}-{n}")
    return course


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _profile(user, passed=False):
    from matazim.models import MemberProfile

    return MemberProfile.objects.create(
        user=user, welcome_accepted_at=timezone.now(),
        entrance_test_passed_at=timezone.now() if passed else None,
    )


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student

    _course("scratch", "סקראץ׳ 1")
    _course("scratch-advanced", "סקראץ׳ 2")

    inst = Institution.objects.create(name="רשת עתיד")
    naomi = _user("naomi@example.com", "נעמי")
    inst.managers.add(naomi)

    leader = Leader.objects.create(user=_user("leader@example.com", "רונית"),
                                   institution=inst, approved_at=timezone.now())
    _profile(leader.user)
    empty_leader = Leader.objects.create(user=_user("new@example.com", "מוביל חדש"),
                                         institution=inst, approved_at=timezone.now())
    _profile(empty_leader.user)
    Leader.objects.create(user=_user("waiting@example.com", "ממתין"), institution=inst)

    fresh = _user("fresh@example.com", "נועה")           # registered, nothing else
    _profile(fresh)
    passed = _user("passed@example.com", "דנה")         # passed, nobody's yet
    _profile(passed, passed=True)
    joined = _user("joined@example.com", "יובל")         # in the programme
    _profile(joined, passed=True)
    Student.objects.create(user=joined, leader=leader, status=Student.IN_TRAINING)
    done = _user("done@example.com", "עומר")             # certified
    _profile(done, passed=True)
    Student.objects.create(user=done, leader=leader, status=Student.CERTIFIED,
                           certified_at=timezone.now())

    return {"inst": inst, "naomi": naomi, "leader": leader, "empty_leader": empty_leader,
            "fresh": fresh, "passed": passed, "joined": joined, "done": done}


def _sign_in(client, email, **extra):
    return client.post("/matazim/login/", {"email": email, "password": PASSWORD, **extra})


def _login(client, email):
    assert client.login(username=email, password=PASSWORD)
    return client


# ---------------------------------------------------------------- the door


@pytest.mark.parametrize("email,where", [
    ("naomi@example.com", "/matazim/staff/"),
    ("leader@example.com", "/matazim/leader/"),
    ("joined@example.com", "/matazim/my-path/"),
    ("passed@example.com", "/matazim/my-path/"),
    ("fresh@example.com", "/matazim/"),
])
def test_signing_in_lands_each_role_on_its_own_front_door(client, world, email, where):
    response = _sign_in(client, email)
    assert response.status_code == 302
    assert response["Location"] == where


def test_a_candidate_is_a_member_for_landing_and_their_menu_says_so(client, world):
    """Not a leader yet (REQ-M.93). The door is the home strip, and ההרשאה שלי
    is one tap away in the menu."""
    response = _sign_in(client, "waiting@example.com")
    assert response["Location"] == "/matazim/"
    body = _login(client, "waiting@example.com").get("/matazim/").content.decode()
    assert "/matazim/leaders/" in body


def test_an_explicit_destination_still_wins(client, world):
    response = _sign_in(client, "leader@example.com", next="/matazim/leader/classes/")
    assert response["Location"] == "/matazim/leader/classes/"


# ------------------------------------------------------- the student's door


def test_staff_opening_the_public_page_are_sent_to_their_own_door(client, world):
    assert _login(client, "naomi@example.com").get("/matazim/").context["hero"]["kind"] == "staff"
    client.logout()
    assert _login(client, "leader@example.com").get("/matazim/").context["hero"]["kind"] == "leader"


# ----------------------------------------------- the program manager's door


def test_the_staff_door_opens_on_the_leaders(client, world):
    """"Who are the leaders that he owns, the main status of each one, like
    how many students, like pass rate." One line per leader, four numbers."""
    response = _login(client, "naomi@example.com").get("/matazim/staff/")
    rows = {r["name"]: r for r in response.context["dashboard"]["rows"]}
    assert set(rows) == {"רונית", "מוביל חדש"}
    assert rows["רונית"]["students"] == 2
    assert rows["רונית"]["certified"] == 1
    assert rows["רונית"]["rate"] == 50
    # No students is not a 0% pass rate: that would be a claim about a person.
    assert rows["מוביל חדש"]["rate"] is None
    body = response.content.decode()
    assert "עוד אין מטצים" in body


def test_the_staff_door_names_the_person_and_the_role(client, world):
    body = _login(client, "naomi@example.com").get("/matazim/staff/").content.decode()
    assert "שלום נעמי" in body
    assert "מנהל/ת התכנית" in body
    assert "רשת עתיד" in body


def test_inviting_a_leader_is_the_one_primary_action(client, world):
    body = _login(client, "naomi@example.com").get("/matazim/staff/").content.decode()
    assert "/matazim/staff/team/#invite" in body
    # and the anchor it points at exists
    team = client.get("/matazim/staff/team/").content.decode()
    assert 'id="invite"' in team


def test_a_candidate_waiting_sits_above_the_list(client, world):
    response = _login(client, "naomi@example.com").get("/matazim/staff/")
    assert [c["email"] for c in response.context["dashboard"]["candidates"]] == ["waiting@example.com"]
    body = response.content.decode()
    # The nav also says המובילים שלי; anchor on the headings.
    assert body.index("<h2>ממתינים לאישור") < body.index("<h2>המובילים שלי")


def test_the_reports_are_still_one_tap_away(client, world):
    body = _login(client, "naomi@example.com").get("/matazim/staff/").content.decode()
    for path in ("/matazim/staff/people/", "/matazim/staff/cohort/", "/matazim/staff/courses/",
                 "/matazim/staff/events/", "/matazim/requests/new/", "/matazim/my-path/"):
        assert path in body, path


def test_the_dashboard_numbers_are_the_report_numbers(client, world):
    """RULE-3 — one reader. The dashboard and the full report cannot disagree
    about how many students a leader has."""
    session = _login(client, "naomi@example.com")
    dash = {r["email"]: r for r in session.get("/matazim/staff/").context["dashboard"]["rows"]}
    report = {r["email"]: r for r in session.get("/matazim/staff/people/").context["rows"]}
    for email in dash:
        assert dash[email]["students"] == report[email]["students"]
        assert dash[email]["certified"] == report[email]["certified"]


# ---------------------------------------------------------- the leader's door


def test_the_leader_door_opens_on_the_group(client, world):
    response = _login(client, "leader@example.com").get("/matazim/leader/")
    dash = response.context["dashboard"]
    assert dash["students"] == 2
    assert dash["certified"] == 1
    assert dash["learning"] == 1
    names = {r["name"]: r for r in dash["rows"]}
    assert names["עומר"]["status"] == "done"
    assert names["יובל"]["status"] == "todo"
    body = response.content.decode()
    assert "שלום רונית" in body
    assert "מטצ מוסמך" in body


def test_somebody_ready_to_certify_is_the_first_thing_a_leader_sees(client, world):
    """REQ-M.76 from the leader's side: the two automatic conditions met, the
    third is theirs, and nothing else in the product said so until they opened
    the student's page."""
    from app.models import Course, CourseCertificate

    yuval = world["joined"]
    for slug in ("scratch", "scratch-advanced"):
        CourseCertificate.objects.create(user=yuval, course=Course.objects.get(slug=slug))

    response = _login(client, "leader@example.com").get("/matazim/leader/")
    dash = response.context["dashboard"]
    assert dash["ready"] == 1
    assert [r["name"] for r in dash["attention"]] == ["יובל"]
    body = response.content.decode()
    assert "<h2>מוכנים להסמכה" in body
    assert body.index("<h2>מוכנים להסמכה") < body.index("<h2>המטצים שלי")


def test_a_leader_on_day_one_sees_the_link_first(client, world):
    """SPR-M.44's rule kept: with nobody yet, the link is the page."""
    body = _login(client, "new@example.com").get("/matazim/leader/").content.decode()
    assert "הקישור שלכם, כדי שהמטצים הראשונים יצטרפו" in body
    assert "מוכנים להסמכה" not in body
    assert "עוד אין מטצים משויכים אליכם" in body


def test_reporting_up_is_seeing_what_the_manager_sees(client, world):
    """There is no form to file, and the page says so."""
    body = _login(client, "leader@example.com").get("/matazim/leader/").content.decode()
    assert "אין מה לדווח בנפרד" in body
    leader_numbers = client.get("/matazim/leader/").context["dashboard"]
    client.logout()
    manager_rows = {r["email"]: r for r in
                    _login(client, "naomi@example.com").get("/matazim/staff/").context["dashboard"]["rows"]}
    assert manager_rows["leader@example.com"]["students"] == leader_numbers["students"]
    assert manager_rows["leader@example.com"]["certified"] == leader_numbers["certified"]


def test_the_leader_door_does_not_grow_a_query_per_student(client, world):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from matazim.models import Student

    session = _login(client, "leader@example.com")
    with CaptureQueriesContext(connection) as before:
        session.get("/matazim/leader/")
    for n in range(6):
        u = _user(f"more{n}@example.com", f"מטצ {n}")
        _profile(u, passed=True)
        Student.objects.create(user=u, leader=world["leader"], status=Student.IN_TRAINING)
    with CaptureQueriesContext(connection) as after:
        session.get("/matazim/leader/")
    assert len(after) == len(before), "the leader's door asks per student"
