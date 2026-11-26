"""Academia360 sprint C.1: asking to join (spec 4.5 "People, and requests to
join"; backlog C.1).

A signed-in person asks to be a program leader (institution, title) or a
committee member; anonymous visitors sign in first and come back; one open
request per kind; the admins are mailed through the one mail function;
/me/ shows the person's roles and requests; a stranger's request never
shows; the home page and the sign-in page point at the door.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail as dj_mail

from academia360.models import ChangeLog, Institution, Program, Role, RoleRequest

pytestmark = pytest.mark.django_db

PW = "join-4410-pw"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    Program.objects.create(slug="academia-360", name="אקדמיה 360")
    technion = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY)
    haifa = Institution.objects.create(slug="haifa", name_he="אוניברסיטת חיפה", kind=Institution.UNIVERSITY)
    avi = User.objects.create_user("avi@example.com", "avi@example.com", PW, is_superuser=True, is_staff=True, first_name="אבי")
    Role.objects.create(user=avi, kind=Role.ADMIN)
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PW, first_name="דנה")
    yoni = User.objects.create_user("yoni@example.com", "yoni@example.com", PW, first_name="יוני")
    return {"technion": technion, "haifa": haifa, "avi": avi, "dana": dana, "yoni": yoni}


def _in(client, who):
    assert client.login(username=who.email, password=PW)


def test_anonymous_is_sent_to_sign_in_and_comes_back_to_the_door(client, world):
    r = client.get("/academia360/join/?kind=leader")
    assert r.status_code == 302 and r.url.startswith("/academia360/login/?next=/academia360/join/")
    r = client.post("/academia360/join/", {"kind": "committee", "message": "x"})
    assert r.status_code == 302 and RoleRequest.objects.count() == 0


def test_a_leader_request_lands_once_mails_the_admin_and_shows_on_me(client, world):
    _in(client, world["dana"])
    html = client.get("/academia360/join/?kind=leader").content.decode()
    assert 'value="leader" checked' in html and 'name="institution"' in html and "הטכניון" in html
    r = client.post("/academia360/join/", {"kind": "leader", "institution": "technion", "title": "סגנית נשיא",
                                          "message": "אני אחראית על התכנית אצלנו <b>בולד</b>"})
    assert r.status_code == 302 and r.url == "/academia360/me/"
    row = RoleRequest.objects.get()
    assert row.user == world["dana"] and row.role_kind == "leader" and row.institution == world["technion"]
    assert row.title == "סגנית נשיא" and row.status == "open" and "<b>" not in row.message and "בולד" in row.message
    assert ChangeLog.objects.filter(model="academia360.RoleRequest", row_id=str(row.pk)).exists()
    assert len(dj_mail.outbox) == 1
    sent = dj_mail.outbox[0]
    assert sent.to == ["avi@example.com"] and "דנה" in sent.body and "הטכניון" in sent.body and "סגנית נשיא" in sent.body
    assert "/academia360/manage/people/" in sent.body and sent.subject.startswith("אקדמיה 360°")
    me = client.get("/academia360/me/").content.decode()
    role_box = me.split('id="role"', 1)[1].split("a360-two", 1)[0]
    assert "בקשה: מוביל/ת תכנית במוסד" in role_box and "הטכניון" in role_box and "ממתין" in role_box
    # a second open request of the same kind is refused; another kind is fine
    r = client.post("/academia360/join/", {"kind": "leader", "institution": "haifa"}, follow=True)
    assert RoleRequest.objects.count() == 1 and "כבר יש בקשה פתוחה" in r.content.decode()
    client.post("/academia360/join/", {"kind": "committee", "message": "גם בוועדה"})
    assert RoleRequest.objects.count() == 2 and len(dj_mail.outbox) == 2


def test_a_leader_needs_an_institution_and_a_holder_is_told_they_already_have_it(client, world):
    _in(client, world["dana"])
    r = client.post("/academia360/join/", {"kind": "leader", "institution": "", "message": "בלי מוסד"}, follow=True)
    assert RoleRequest.objects.count() == 0 and "איזה מוסד" in r.content.decode() and dj_mail.outbox == []
    Role.objects.create(user=world["dana"], kind=Role.COMMITTEE_MEMBER)
    r = client.post("/academia360/join/", {"kind": "committee"}, follow=True)
    assert RoleRequest.objects.count() == 0 and "כבר יש לכם תפקיד" in r.content.decode()
    r = client.post("/academia360/join/", {"kind": "king"}, follow=True)
    assert RoleRequest.objects.count() == 0


def test_me_shows_my_roles_and_never_a_strangers_request(client, world):
    RoleRequest.objects.create(user=world["dana"], role_kind="committee", message="סודי של דנה")
    _in(client, world["yoni"])
    me = client.get("/academia360/me/").content.decode()
    assert "סודי של דנה" not in me and "בקשה:" not in me
    assert 'href="/academia360/join/"' in me and "בלי תפקיד" in me
    Role.objects.create(user=world["yoni"], kind=Role.LEADER)
    from academia360.models import LeaderOf
    LeaderOf.objects.create(user=world["yoni"], institution=world["haifa"], title="דיקן")
    me = client.get("/academia360/me/").content.decode()
    assert "התפקיד שלכם:" in me and "מוביל/ת תכנית במוסד: אוניברסיטת חיפה" in me
    # the API shows a person only their own request, and the admin all
    r = client.get("/academia360/api/rolerequests/")
    assert r.status_code == 200 and r.json() == []
    client.logout()
    _in(client, world["avi"])
    assert len(client.get("/academia360/api/rolerequests/?status=open").json()) == 1
    assert client.get("/academia360/api/rolerequests/?status=approved").json() == []


def test_the_doors_point_at_the_request(client, world):
    home = client.get("/academia360/").content.decode()
    assert 'href="/academia360/join/?kind=leader"' in home and 'href="/academia360/join/?kind=committee"' in home
    login = client.get("/academia360/login/").content.decode()
    assert 'href="/academia360/join/"' in login
