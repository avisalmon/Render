"""SPR-M.76 - A program manager sees the site as one of her leaders.

Naomi, by mail, 2026-10-29: "אני רוצה בבקשה שבאתר יהיה אפשרות של 'לראות את
האתר כמוביל' כמו שיש את האפשרות 'לראות את האתר כתלמיד'. ... אני רוצה שתהיה לי
ולליטל לראות את האתר מכל הזוויות."

A leader's screens are about that leader's students, so she picks one of her own
leaders and sees their area, students and classes as they do. Read only, and
never wider than what she already sees.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm76-pass-2910"


def _user(name, display=None):
    from app.models import UserProfile

    person = User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                      password=PASSWORD)
    if display:
        UserProfile.objects.update_or_create(user=person, defaults={"display_name": display})
    return person


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student, StudyClass

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm", "נעמי")
    inst.managers.add(pm)
    dana = Leader.objects.create(user=_user("dana", "דנה המובילה"), institution=inst,
                                 approved_at=timezone.now())
    yossi = Leader.objects.create(user=_user("yossi", "יוסי המוביל"), institution=inst,
                                  approved_at=timezone.now())
    other = Institution.objects.create(name="רשת אחרת")
    far = Leader.objects.create(user=_user("far", "מוביל רחוק"), institution=other,
                                approved_at=timezone.now())
    hers = Student.objects.create(user=_user("kid1", "תלמידה של דנה"), leader=dana)
    his = Student.objects.create(user=_user("kid2", "תלמיד של יוסי"), leader=yossi)
    StudyClass.objects.create(leader=dana, name="כיתה ט1 של דנה")
    return {"pm": pm, "dana": dana, "yossi": yossi, "far": far, "hers": hers, "his": his}


def _look(client, world, who="dana"):
    client.force_login(world["pm"])
    return client.get(f"/matazim/as-leader/?leader={world[who].pk}")


def test_the_staff_home_offers_her_own_leaders_only(client, world):
    client.force_login(world["pm"])
    page = client.get("/matazim/staff/").content.decode()
    assert "לראות את האתר כמוביל" in page
    assert "דנה המובילה" in page and "יוסי המוביל" in page
    assert "מוביל רחוק" not in page


def test_the_home_page_offers_it_beside_the_student_view(client, world):
    client.force_login(world["pm"])
    page = client.get("/matazim/").content.decode()
    assert "לראות את האתר כתלמיד" in page and "לראות את האתר כמוביל" in page


def test_the_leader_page_has_the_button(client, world):
    client.force_login(world["pm"])
    page = client.get(f"/matazim/staff/leaders/{world['dana'].pk}/").content.decode()
    assert f"/matazim/as-leader/?leader={world['dana'].pk}" in page


def test_looking_opens_the_leaders_area_with_a_bar(client, world):
    resp = _look(client, world)
    assert resp.status_code == 302 and resp["Location"] == "/matazim/leader/"
    page = client.get("/matazim/leader/")
    assert page.status_code == 200
    html = page.content.decode()
    assert "אתם רואים את האתר כמוביל/ה: דנה המובילה" in html
    assert "חזרה לתצוגה שלי" in html
    assert world["dana"].join_code in html
    # The leader's menu, not the manager's.
    assert "המטצים שלי" in html
    assert 'href="/matazim/staff/"' not in html


def test_the_roster_shows_that_leaders_students_only(client, world):
    _look(client, world)
    html = client.get("/matazim/leader/students/").content.decode()
    assert "תלמידה של דנה" in html
    assert "תלמיד של יוסי" not in html
    assert client.get(f"/matazim/leader/students/{world['hers'].pk}/").status_code == 200
    assert client.get(f"/matazim/leader/students/{world['his'].pk}/").status_code == 404


def test_the_classes_are_that_leaders(client, world):
    _look(client, world)
    html = client.get("/matazim/leader/classes/").content.decode()
    assert "כיתה ט1 של דנה" in html


def test_nothing_is_written_while_looking(client, world):
    from matazim.models import StudyClass

    _look(client, world)
    hers = world["hers"]
    assert client.post(f"/matazim/leader/students/{hers.pk}/", {"action": "remove"}).status_code == 403
    assert client.post("/matazim/leader/classes/", {"action": "add", "name": "חדשה"}).status_code == 403
    assert client.post("/matazim/leader/courses/", {"slug": "x"}).status_code == 403
    status_before = hers.status
    hers.refresh_from_db()
    assert hers.leader_id == world["dana"].pk and hers.status == status_before
    assert not StudyClass.objects.filter(name="חדשה").exists()


def test_another_programmes_leader_is_refused(client, world):
    client.force_login(world["pm"])
    assert client.get(f"/matazim/as-leader/?leader={world['far'].pk}").status_code == 403
    assert "mz_as_leader" not in client.session


def test_a_leader_or_a_student_cannot_look(client, world):
    client.force_login(world["yossi"].user)
    assert client.get(f"/matazim/as-leader/?leader={world['dana'].pk}").status_code == 403
    client.force_login(world["hers"].user)
    assert client.get(f"/matazim/as-leader/?leader={world['dana'].pk}").status_code == 403


def test_stopping_returns_to_that_leaders_page(client, world):
    _look(client, world)
    resp = client.get("/matazim/as-leader/?leader=off")
    assert resp["Location"] == f"/matazim/staff/leaders/{world['dana'].pk}/"
    assert "mz_as_leader" not in client.session
    # Back to herself: no leader area of her own.
    assert client.get("/matazim/leader/").status_code == 403


def test_a_leader_taken_out_of_use_stops_the_view(client, world):
    _look(client, world)
    world["dana"].is_active = False
    world["dana"].save(update_fields=["is_active"])
    assert client.get("/matazim/leader/").status_code == 403


def test_one_way_of_looking_at_a_time(client, world):
    _look(client, world)
    client.get("/matazim/preview/member/")
    assert "mz_as_leader" not in client.session
    _look(client, world)
    assert "mz_preview_stage" not in client.session
