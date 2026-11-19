"""SPR-M.91 - Naomi, 2026-11-19: a leader brings students into their class without the test.

"אני רוצה שלכל מוביל כיתה תהיה האפשרות לצרף תלמידים לכיתה שלו גם ללא מבחן הכניסה.
תוסיף בכל עמוד של מוביל את האפשרות לשלוח לתלמיד להצטרף פעם ראשונה כתלמיד כיתה ט'
ופעם שנייה כתלמיד כיתה י'."
"""

import base64

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm91-pass-1119"
PNG = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 80
).decode()


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


def _adult(user):
    from matazim.models import MemberProfile

    MemberProfile.objects.update_or_create(user=user, defaults={"birth_year": 1990})
    return user


@pytest.fixture
def leader(db):
    from matazim.models import Institution, Leader

    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(name="רשת עתיד")
    return Leader.objects.create(user=_user("leader91"), institution=inst, approved_at=timezone.now())


def test_every_leader_has_two_distinct_codes(leader):
    codes = {leader.join_code, leader.direct_code, leader.graduate_code}
    assert len(codes) == 3


def test_the_leader_page_shows_both_links(client, leader):
    client.force_login(leader.user)
    html = client.get("/matazim/leader/").content.decode()
    panel = html[html.index('id="mzDirectLinks"'):html.index("</section>", html.index('id="mzDirectLinks"'))]
    assert "בלי מבחן כניסה" in panel
    assert "כיתה ט" in panel and "כיתה י" in panel
    assert f"/matazim/class-link/{leader.direct_code}/" in panel
    assert f"/matazim/graduates/link/{leader.graduate_code}/" in panel


def test_the_programme_team_sees_both_links_on_a_leaders_page(client, leader):
    from matazim.roles import grant_program_manager

    pm = _user("pm91")
    grant_program_manager(pm)
    client.force_login(pm)
    html = client.get(f"/matazim/staff/leaders/{leader.pk}/").content.decode()
    assert f"/matazim/class-link/{leader.direct_code}/" in html
    assert f"/matazim/graduates/link/{leader.graduate_code}/" in html


def test_grade9_link_signed_out_names_the_leader_and_offers_an_account(client, leader):
    resp = client.get(f"/matazim/class-link/{leader.direct_code}/")
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "הזמנה לכיתה ט" in html and "פתיחת חשבון" in html
    assert "אין צורך במבחן הכניסה" in html


def test_grade9_link_joins_the_class_without_the_test(client, leader):
    from matazim.gate import MEMBER, learner_stage
    from matazim.models import MemberProfile, Student

    kid = _adult(_user("kid91"))
    client.force_login(kid)
    assert learner_stage(kid) == "test"
    resp = client.post(f"/matazim/class-link/{leader.direct_code}/", {"action": "join"})
    assert resp.status_code == 302 and resp["Location"].endswith("/matazim/joined/")
    student = Student.objects.get(user=kid)
    assert student.leader == leader and student.status == Student.IN_TRAINING
    profile = MemberProfile.objects.get(user=kid)
    # A waiver, written as one: never a pass.
    assert profile.entrance_test_passed_at is None
    assert profile.entrance_waived_at is not None and profile.entrance_waived_by == leader.user
    assert learner_stage(kid) == MEMBER
    assert client.get("/matazim/my-path/").status_code == 200


def test_the_path_says_let_in_without_the_test(client, leader):
    kid = _adult(_user("kid91p"))
    client.force_login(kid)
    client.post(f"/matazim/class-link/{leader.direct_code}/", {"action": "join"})
    from types import SimpleNamespace

    from matazim.models import MemberProfile, Student
    from matazim.track import milestones

    state = SimpleNamespace(entrance_test_required=False, certified_courses=set(), is_eligible=False)
    nodes = milestones(kid, MemberProfile.objects.get(user=kid), Student.objects.get(user=kid), state, {})
    test = [n for n in nodes if n["key"] == "test"]
    assert test and test[0]["status"] == "done" and test[0]["word"] == "צורף/ה בלי מבחן"


def test_a_minor_still_needs_a_parent_first_and_then_lands_with_the_leader(client, leader, settings):
    from matazim.consent import record_guardian_consent

    settings.MATAZIM_REQUIRE_GUARDIAN_CONSENT = True
    from matazim.models import MemberProfile, Student

    kid = _user("minor91")
    MemberProfile.objects.update_or_create(user=kid, defaults={"birth_year": timezone.now().year - 14})
    client.force_login(kid)
    resp = client.post(f"/matazim/class-link/{leader.direct_code}/", {"action": "join"})
    assert resp.status_code == 302 and "/matazim/profile" in resp["Location"]
    assert not Student.objects.filter(user=kid, leader=leader).exists()
    profile = MemberProfile.objects.get(user=kid)
    assert profile.entrance_waived_at is not None
    record_guardian_consent(profile, name="הורה", email="parent91@example.com")
    # The ordinary link is carried on, and the test no longer stands in the way.
    resp = client.get("/matazim/join-leader/")
    assert resp.status_code == 302 and resp["Location"].endswith(f"/matazim/join/{leader.join_code}/")
    client.post(f"/matazim/join/{leader.join_code}/", {"action": "join"})
    assert Student.objects.get(user=kid).leader == leader


def test_the_ordinary_code_does_not_open_the_direct_link(client, leader):
    assert client.get(f"/matazim/class-link/{leader.join_code}/").status_code == 404
    assert client.get(f"/matazim/graduates/link/{leader.direct_code}/").status_code == 404


def test_an_inactive_or_unapproved_leader_has_no_live_link(client, leader):
    leader.is_active = False
    leader.save()
    assert client.get(f"/matazim/class-link/{leader.direct_code}/").status_code == 404
    assert client.get(f"/matazim/graduates/link/{leader.graduate_code}/").status_code == 404


def test_a_leader_cannot_use_the_link_on_themselves(client, leader):
    from matazim.models import Student

    client.force_login(leader.user)
    resp = client.post(f"/matazim/class-link/{leader.direct_code}/", {"action": "join"})
    assert resp.status_code == 200 and "מיועד לתלמידים" in resp.content.decode()
    assert not Student.objects.filter(user=leader.user).exists()


def test_rotating_replaces_the_direct_links_too(client, leader):
    from matazim.roles import grant_program_manager

    old = (leader.direct_code, leader.graduate_code)
    pm = _user("pm91r")
    grant_program_manager(pm)
    client.force_login(pm)
    client.post(f"/matazim/staff/leaders/{leader.pk}/", {"action": "rotate"})
    leader.refresh_from_db()
    assert leader.direct_code != old[0] and leader.graduate_code != old[1]
    client.logout()
    assert client.get(f"/matazim/class-link/{old[0]}/").status_code == 404


def test_grade10_link_signed_out_names_the_leader(client, leader):
    html = client.get(f"/matazim/graduates/link/{leader.graduate_code}/").content.decode()
    assert "לבוגרי מטצים" in html and "פתיחת חשבון" in html and "חתימה של הורה" in html


def test_grade10_link_fixes_the_leader_and_approves_on_sending(client, leader):
    from matazim.models import Graduate
    from tests.matazim_helpers import school_pk

    other = _user("other91")
    from matazim.models import Leader

    Leader.objects.create(user=other, institution=leader.institution, approved_at=timezone.now())
    grad = _user("grad91")
    client.force_login(grad)
    resp = client.get(f"/matazim/graduates/link/{leader.graduate_code}/")
    assert resp.status_code == 302 and resp["Location"].endswith("/matazim/graduates/join/")
    form = client.get("/matazim/graduates/join/").content.decode()
    assert 'id="mzGradInvited"' in form and "בלי לחכות לאישור" in form
    assert "other91" not in form
    resp = client.post("/matazim/graduates/join/", {
        "full_name": "בוגרת ניסיון", "school": school_pk(),
        "leader": Leader.objects.get(user=other).pk,  # ignored: the link chose
        "guardian_name": "הורה", "guardian_email": "p91@example.com",
        "guardian_consent": "on", "signature": PNG,
    })
    assert resp.status_code == 302
    g = Graduate.objects.get(user=grad)
    assert g.leader == leader and g.is_approved and g.approved_by == leader.user
    space = client.get("/matazim/graduates/").content.decode()
    assert "ברוכים הבאים לנבחרת בוגרי מטצים" in space


def test_grade10_without_the_link_still_waits_for_the_leader(client, leader):
    from matazim.models import Graduate
    from tests.matazim_helpers import school_pk

    grad = _user("grad91w")
    client.force_login(grad)
    client.post("/matazim/graduates/join/", {
        "full_name": "בוגר", "school": school_pk(), "leader": leader.pk,
        "guardian_name": "הורה", "guardian_email": "p91w@example.com",
        "guardian_consent": "on", "signature": PNG,
    })
    assert not Graduate.objects.get(user=grad).is_approved


def test_grade10_link_still_needs_the_parents_signature(client, leader):
    from matazim.models import Graduate
    from tests.matazim_helpers import school_pk

    grad = _user("grad91s")
    client.force_login(grad)
    client.get(f"/matazim/graduates/link/{leader.graduate_code}/")
    client.post("/matazim/graduates/join/", {
        "full_name": "בוגר", "school": school_pk(),
        "guardian_name": "הורה", "guardian_email": "p91s@example.com", "guardian_consent": "on",
    })
    assert not Graduate.objects.filter(user=grad).exists()


def test_the_api_does_not_hand_out_the_codes(leader):
    from rest_framework.test import APIClient

    api = APIClient()
    api.force_authenticate(leader.user)
    body = api.get("/matazim/api/leaders/").content.decode()
    assert leader.direct_code not in body and leader.graduate_code not in body


def test_the_new_words_are_plain():
    from pathlib import Path

    for name in ("_direct_links.html", "direct_link.html"):
        text = Path(f"templates/matazim/{name}").read_text(encoding="utf-8")
        assert "—" not in text and "מט\"צ" not in text and "קורס" not in text
