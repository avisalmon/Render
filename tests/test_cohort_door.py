"""cohort, SPR-C.1: the frame, the disclaimer and the door.

The sharpest test here is `test_nothing_of_the_course_is_visible_before_approval`:
the whole point of the app is that it is closed, so every page and every API
route is swept for every kind of outsider, rather than spot-checked.

Traces: REQ-C.1 to C.6, C.42, C.45.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command

from cohort.models import Exhibit, Material, Member, Track

pytestmark = pytest.mark.cohort

PASSWORD = "cohort-pass-8823"
DISCLAIMER = "אינו אתר רשמי של משרד החינוך, של אינטל או של כל גורם אחר"


@pytest.fixture(autouse=True)
def private_dir(settings, tmp_path):
    settings.COHORT_PRIVATE_DIR = tmp_path
    settings.COHORT_SHOTS_ENABLED = False


def _user(email, superuser=False, name="מורה"):
    first, _, last = name.partition(" ")
    if superuser:
        return User.objects.create_superuser(email, email, PASSWORD, first_name=first, last_name=last)
    return User.objects.create_user(email, email, PASSWORD, first_name=first, last_name=last)


def _member(email, status=Member.APPROVED, admin=False, name="מורה"):
    user = _user(email, name=name)
    return Member.objects.create(user=user, display_name=name, status=status, is_admin=admin)


@pytest.fixture
def world(db):
    call_command("seed_cohort")
    avi = _user("avi@example.com", superuser=True, name="אבי סלמון")
    inside = _member("in@example.com", name="רונית לוי")
    exhibit = Exhibit.objects.create(owner=inside, title="מעבדת פוטוסינתזה", url="https://example.com/")
    material = Material.objects.create(kind=Material.COURSE, title="הדרכה", line="שורה", url="https://babook.co.il/courses/x/")
    return {"avi": avi, "inside": inside, "exhibit": exhibit, "material": material}


INSIDE_PAGES = [
    "/cohort/exhibition/", "/cohort/exhibition/new/", "/cohort/tracks/", "/cohort/tracks/computer-science/",
    "/cohort/materials/",
]


def _inside_urls(world):
    e, m = world["exhibit"], world["material"]
    return INSIDE_PAGES + [f"/cohort/exhibition/{e.pk}/", f"/cohort/exhibition/{e.pk}/edit/",
                           "/cohort/tracks/computer-science/edit/", f"/cohort/materials/{m.pk}/edit/",
                           "/cohort/materials/new/", "/cohort/requests/"]


API = ["members", "exhibits", "likes", "stars", "comments", "tracks", "materials"]


# ------------------------------------------------------------ the disclaimer


@pytest.mark.parametrize("path", ["/cohort/", "/cohort/login/", "/cohort/signup/", "/cohort/no-such-page/"])
def test_the_disclaimer_is_on_the_pages_before_signing_in(client, db, path):
    """REQ-C.1"""
    html = client.get(path).content.decode()
    assert 'id="cb-disclaimer"' in html
    assert DISCLAIMER in html and "אבי סלמון" in html and "משתתפי הקורס שאושרו" in html


def test_the_disclaimer_is_on_every_page_inside(client, world):
    """REQ-C.1"""
    client.force_login(world["avi"])
    for path in _inside_urls(world):
        response = client.get(path)
        assert response.status_code == 200, path
        assert DISCLAIMER in response.content.decode(), path


def test_the_disclaimer_stays_put(client, db):
    """REQ-C.1: it lives inside the sticky top block, not in the page body."""
    html = client.get("/cohort/").content.decode()
    top = html.split('<div class="cb-top">', 1)[1].split('<main', 1)[0]
    assert 'id="cb-disclaimer"' in top
    import pathlib

    css = pathlib.Path("static/cohort/cohort.css").read_text(encoding="utf-8")
    assert ".cb-top { position: sticky; top: 0;" in css


# ------------------------------------------------------------ closed by default


def test_nothing_of_the_course_is_visible_before_approval(client, world):
    """REQ-C.2, C.42: every page and every API route, for every outsider."""
    outsiders = {
        "signed out": None,
        "no request": _user("new@example.com"),
        "pending": _member("wait@example.com", Member.PENDING).user,
        "declined": _member("no@example.com", Member.DECLINED).user,
    }
    for who, user in outsiders.items():
        client.logout()
        if user:
            client.force_login(user)
        for path in _inside_urls(world):
            response = client.get(path)
            assert response.status_code in (302, 404), (who, path, response.status_code)
            if response.status_code == 302:
                assert response["Location"] == "/cohort/", (who, path)
        shot = f"/cohort/files/shots/x.jpg"
        assert client.get(shot).status_code in (302, 404), (who, "files")
        for route in API:
            assert client.get(f"/cohort/api/{route}/").status_code in (401, 403), (who, route)
        html = client.get("/cohort/").content.decode()
        assert "מעבדת פוטוסינתזה" not in html and "רונית לוי" not in html


def test_the_door_says_where_you_stand(client, db):
    """REQ-C.2 to C.5"""
    html = client.get("/cohort/").content.decode()
    assert 'href="/cohort/login/"' in html and 'id="cb-ask"' not in html

    user = _user("t@example.com")
    client.force_login(user)
    assert 'id="cb-ask"' in client.get("/cohort/").content.decode()

    assert client.post("/cohort/").status_code == 302
    assert client.post("/cohort/").status_code == 302
    assert Member.objects.filter(user=user).count() == 1, "asking twice made two requests"
    html = client.get("/cohort/").content.decode()
    assert 'id="cb-pending"' in html and "ממתינה לאישור של אבי" in html

    Member.objects.filter(user=user).update(status=Member.DECLINED)
    assert 'id="cb-declined"' in client.get("/cohort/").content.decode()

    Member.objects.filter(user=user).update(status=Member.APPROVED)
    response = client.get("/cohort/")
    assert response.status_code == 302 and response["Location"] == "/cohort/exhibition/"


# ------------------------------------------------------------ Avi's screen


def test_avi_sees_requests_approves_and_the_person_gets_one_email(client, world):
    """REQ-C.4, C.5"""
    person = _member("teacher@example.com", Member.PENDING, name="מיכל אברהם")
    client.force_login(world["avi"])
    html = client.get("/cohort/requests/").content.decode()
    pending = html.split('id="pending"', 1)[1].split("</section>", 1)[0]
    assert "מיכל אברהם" in pending and "teacher@example.com" in pending
    assert 'cb-badge' in html.split('<nav class="cb-nav"', 1)[1].split("</nav>", 1)[0]

    mail.outbox.clear()
    client.post("/cohort/requests/", {"member": person.pk, "action": "approve"})
    person.refresh_from_db()
    assert person.status == Member.APPROVED and person.decided_by == world["avi"]
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["teacher@example.com"]
    assert "/cohort/" in mail.outbox[0].body

    client.post("/cohort/requests/", {"member": person.pk, "action": "withdraw"})
    client.post("/cohort/requests/", {"member": person.pk, "action": "approve"})
    assert len(mail.outbox) == 1, "approving again sent a second welcome"

    client.force_login(person.user)
    assert client.get("/cohort/exhibition/").status_code == 200


def test_withdrawing_closes_the_door(client, world):
    """REQ-C.4"""
    person = world["inside"]
    client.force_login(world["avi"])
    client.post("/cohort/requests/", {"member": person.pk, "action": "withdraw"})
    client.force_login(person.user)
    assert client.get("/cohort/exhibition/").status_code == 302


def test_only_an_admin_reaches_the_requests_screen(client, world):
    """REQ-C.4: a participant gets the same answer as a page that is not there."""
    client.force_login(world["inside"].user)
    assert client.get("/cohort/requests/").status_code == 404
    other = _member("p@example.com", Member.PENDING)
    client.post("/cohort/requests/", {"member": other.pk, "action": "approve"})
    other.refresh_from_db()
    assert other.status == Member.PENDING
    assert 'href="/cohort/requests/"' not in client.get("/cohort/exhibition/").content.decode()


def test_a_member_marked_admin_by_avi_can_decide(client, world):
    """Spec Chapter 7: admins Avi names through the chat."""
    helper = _member("helper@example.com", admin=True)
    person = _member("x@example.com", Member.PENDING)
    client.force_login(helper.user)
    client.post("/cohort/requests/", {"member": person.pk, "action": "approve"})
    person.refresh_from_db()
    assert person.status == Member.APPROVED


def test_avi_never_has_to_ask_himself(client, world):
    """Spec Chapter 7: the superuser bypass is deliberate."""
    client.force_login(world["avi"])
    assert client.get("/cohort/").status_code == 302
    assert client.get("/cohort/exhibition/").status_code == 200
    member = Member.objects.get(user=world["avi"])
    assert member.is_admin and member.status == Member.APPROVED


def test_asking_and_deciding_through_the_api(client, world):
    """REQ-C.44"""
    user = _user("api@example.com")
    client.force_login(user)
    assert client.post("/cohort/api/members/").status_code == 201
    assert client.post("/cohort/api/members/").status_code == 200
    member = Member.objects.get(user=user)
    assert member.status == Member.PENDING
    assert client.post(f"/cohort/api/members/{member.pk}/approve/").status_code in (403, 404)

    client.force_login(world["inside"].user)
    assert client.post(f"/cohort/api/members/{member.pk}/approve/").status_code in (403, 404)
    names = [m["display_name"] for m in client.get("/cohort/api/members/").json()]
    assert "רונית לוי" in names and all("email" not in m for m in client.get("/cohort/api/members/").json())

    client.force_login(world["avi"])
    mail.outbox.clear()
    assert client.post(f"/cohort/api/members/{member.pk}/approve/").status_code == 200
    member.refresh_from_db()
    assert member.status == Member.APPROVED and len(mail.outbox) == 1


# ------------------------------------------------------------ sign in, in the app's look


def test_signing_up_and_in_stays_inside_the_app(client, db):
    """REQ-C.6"""
    response = client.post("/cohort/signup/", {
        "name": "דנה כהן", "email": "Dana@Example.com", "password1": "a-long-pass-7781", "password2": "a-long-pass-7781",
    })
    assert response.status_code == 302 and response["Location"] == "/cohort/"
    user = User.objects.get(email="dana@example.com")
    assert user.first_name == "דנה"
    client.logout()
    response = client.post("/cohort/login/", {"username": "dana@example.com", "password": "a-long-pass-7781"})
    assert response.status_code == 302 and response["Location"] == "/cohort/"
    client.logout()
    response = client.post("/cohort/login/?next=https://evil.example/", {"username": "dana@example.com", "password": "a-long-pass-7781"})
    assert response["Location"] == "/cohort/"


def test_the_pages_do_not_link_back_to_the_main_site(client, world):
    """Rule 3: no babook menu, no link out, except the courses Avi links (REQ-C.34)."""
    import re

    client.force_login(world["avi"])
    for path in _inside_urls(world):
        html = client.get(path).content.decode()
        for href in re.findall(r'href="(/[^"]*)"', html):
            assert href.startswith(("/cohort/", "/static/", "/accounts/google/")), (path, href)
