"""SPR-M.71 - A leader who registers sees what the students see.

Lital, by mail, 2026-10-25: "אבקש לקבל לינק לשלוח למובילים להירשם ולקבל הרשאה,
חשוב שבהרשמה שלהם הם יוכלו לראות את הכניסה של התלמידים את המבחן מיון את המסלול."

The link is the open invite (REQ-M.92) and the permission is still a person's
approval (REQ-M.93). What is new: while waiting, and after approval, the leader
has three links into the student preview: the entrance, the screening test and
the path. A candidate sees the two stages that show nobody's data; the whole
site waits for approval.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm71-pass-2510"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, LeaderInvite

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst, approved_at=timezone.now())
    invite = LeaderInvite.objects.create(institution=inst, kind=LeaderInvite.OPEN)
    return {"pm": pm, "leader": leader, "invite": invite, "inst": inst}


def _candidate(client, world, name="teacher"):
    person = _user(name)
    client.force_login(person)
    client.get(f"/matazim/leaders/join/{world['invite'].token}/")
    return person


def test_the_open_link_makes_a_candidate_who_sees_the_three_links(client, world):
    from matazim.models import Leader

    person = _user("teacher")
    client.force_login(person)
    page = client.get(f"/matazim/leaders/join/{world['invite'].token}/").content.decode()
    assert Leader.objects.get(user=person).approved_at is None             # still a person's yes
    assert "מה התלמידים רואים" in page
    for word in ("הכניסה של התלמידים", "מבחן המיון", "המסלול"):
        assert word in page
    entrance = client.get("/matazim/leaders/").content.decode()
    assert "מה התלמידים רואים" in entrance


def test_a_candidate_can_look_at_the_entrance_the_test_and_the_path(client, world):
    from matazim.models import EntranceAttempt, Student

    person = _candidate(client, world)
    resp = client.get("/matazim/preview/test/?next=/matazim/")
    assert resp["Location"] == "/matazim/"
    home = client.get("/matazim/").content.decode()
    assert "אתם רואים את האתר כתלמיד" in home and "מבחן הכניסה" in home

    resp = client.get("/matazim/preview/test/?next=/matazim/test/")
    assert resp["Location"] == "/matazim/test/"
    assert client.get("/matazim/test/").status_code == 200

    resp = client.get("/matazim/preview/test/?next=/matazim/my-path/")
    assert resp["Location"] == "/matazim/my-path/"
    path = client.get("/matazim/my-path/")
    assert path.status_code == 200 and "אתם רואים את האתר כתלמיד" in path.content.decode()

    assert not EntranceAttempt.objects.exists()
    assert not Student.objects.filter(user=person).exists()


def test_a_candidate_does_not_see_the_whole_site_before_approval(client, world):
    _candidate(client, world)
    assert client.get("/matazim/preview/member/").status_code == 403
    client.get("/matazim/preview/test/")
    html = client.get("/matazim/").content.decode()
    assert 'href="/matazim/preview/member/"' not in html
    # A member stage left in the session from somewhere else is not honoured.
    session = client.session
    session["mz_preview_stage"] = "member"
    session.save()
    assert "אתם רואים את האתר כתלמיד" not in client.get("/matazim/leaders/").content.decode()


def test_stopping_takes_a_candidate_back_to_their_waiting_page(client, world):
    _candidate(client, world)
    client.get("/matazim/preview/test/")
    html = client.get("/matazim/").content.decode()
    assert 'href="/matazim/preview/off/?next=/matazim/leaders/"' in html
    assert client.get("/matazim/preview/off/?next=/matazim/leaders/")["Location"] == "/matazim/leaders/"


def test_next_never_leaves_the_walls(client, world):
    client.force_login(world["pm"])
    assert client.get("/matazim/preview/test/?next=https://evil.example/")["Location"] == "/matazim/"
    assert client.get("/matazim/preview/test/?next=//evil.example/")["Location"] == "/matazim/"
    assert client.get("/matazim/preview/test/?next=/courses/")["Location"] == "/matazim/"


def test_an_approved_leader_has_the_three_links_on_their_page(client, world):
    client.force_login(world["leader"].user)
    page = client.get("/matazim/leader/").content.decode()
    assert "מה התלמידים רואים" in page
    assert client.get("/matazim/preview/member/").status_code == 302


def test_a_student_still_cannot_look(client, world):
    client.force_login(_user("kid"))
    assert client.get("/matazim/preview/test/").status_code == 403
