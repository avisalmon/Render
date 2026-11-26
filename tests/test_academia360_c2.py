"""Academia360 sprint C.2: people, one function per act (spec 2.4, 2.6, 4.5,
4.8; backlog C.2; methodology 53 and 55).

Every path that gives access runs through `academia360/people.py`, which
writes, logs and mails. A mail per path, counted on the test backend; the
backend refusing reads "not sent"; approving a request grants the role and
mails the person; declining mails the word; the API's decide endpoint does
the same for the chat; the generic API refuses to decide a request or to
make an invitation behind the function's back; the CLI builds the calls.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.core import mail as dj_mail

from academia360 import people
from academia360.models import (
    ChangeLog,
    CommitteeAttribute,
    Institution,
    Invitation,
    LeaderOf,
    Program,
    Role,
    RoleRequest,
)

pytestmark = pytest.mark.django_db

PW = "people-4410-pw"
TOKEN = "test-token-a360-c2-not-a-real-secret"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN
    settings.ACADEMIA360_AGENT_USER = ""


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    technion = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY)
    avi = User.objects.create_user("avi", "avi@example.com", PW, is_superuser=True, is_staff=True, first_name="אבי")
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PW, first_name="דנה")
    return {"program": program, "technion": technion, "avi": avi, "dana": dana}


def bearer():
    return {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


def post(client, url, data, **headers):
    return client.post(url, json.dumps(data), content_type="application/json", **headers)


# ------------------------------------------------------------ the functions

def test_each_grant_path_mails_the_person_once_and_logs(world):
    avi, dana, inst = world["avi"], world["dana"], world["technion"]
    done = people.grant_role(avi, dana, Role.LEADER, institution=inst, title="דיקנית")
    assert done.ok and done.mailed == 1 and LeaderOf.objects.get(user=dana, institution=inst).title == "דיקנית"
    assert dj_mail.outbox[-1].to == ["dana@example.com"] and "הטכניון" in dj_mail.outbox[-1].body
    assert ChangeLog.objects.filter(model="academia360.Role", actor_kind="person", by=avi).exists()
    # granting again changes nothing and sends nothing
    again = people.grant_role(avi, dana, Role.LEADER, institution=inst)
    assert again.ok and again.mailed is None and len(dj_mail.outbox) == 1 and "כבר" in again.what
    # committee, then chair and reviewer: a mail each
    assert people.grant_role(avi, dana, Role.COMMITTEE_MEMBER).mailed == 1
    assert people.set_attribute(avi, dana, CommitteeAttribute.CHAIR).mailed == 1
    assert people.set_attribute(avi, dana, CommitteeAttribute.REVIEWER, institution=inst).mailed == 1
    assert len(dj_mail.outbox) == 4
    assert "סוקר/ת של הטכניון" in people.role_sentence(dana) and "יו״ר" in people.role_sentence(dana)
    # revoking the committee role drops its marks and mails
    assert people.revoke_role(avi, dana, Role.COMMITTEE_MEMBER).mailed == 1
    assert not CommitteeAttribute.objects.filter(user=dana).exists()
    # a chair mark needs the committee role; a reviewer needs an institution
    assert people.set_attribute(avi, dana, CommitteeAttribute.CHAIR).status == 400
    people.grant_role(avi, dana, Role.COMMITTEE_MEMBER)
    assert people.set_attribute(avi, dana, CommitteeAttribute.REVIEWER).status == 400
    assert people.grant_role(avi, dana, Role.LEADER).status == 400  # no institution


def test_when_the_backend_refuses_the_answer_says_not_sent(world, monkeypatch):
    from academia360 import mail as a_mail

    def refuse(*args, **kwargs):
        raise OSError("smtp down")

    monkeypatch.setattr(a_mail, "send_mail", refuse)
    done = people.grant_role(world["avi"], world["dana"], Role.COMMITTEE_MEMBER)
    assert done.ok and done.mailed == 0 and done.mail_word == "המייל לא נשלח"
    assert Role.objects.filter(user=world["dana"], kind=Role.COMMITTEE_MEMBER, active=True).exists()


def test_approving_a_request_grants_and_mails_declining_mails_the_word(world):
    avi, dana, inst = world["avi"], world["dana"], world["technion"]
    req = RoleRequest.objects.create(user=dana, role_kind="leader", institution=inst, title="רקטורית", message="x")
    done = people.decide_request(avi, req, approve=True)
    req.refresh_from_db()
    assert done.ok and req.status == "approved" and req.decided_by == avi and req.decided_at is not None
    assert LeaderOf.objects.filter(user=dana, institution=inst, title="רקטורית", active=True).exists()
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["dana@example.com"] and "קיבלתם תפקיד" in dj_mail.outbox[0].subject
    # deciding twice is refused
    assert people.decide_request(avi, req, approve=False).status == 409
    other = RoleRequest.objects.create(user=dana, role_kind="committee", message="y")
    done = people.decide_request(avi, other, approve=False, note="הוועדה מלאה השנה")
    other.refresh_from_db()
    assert done.ok and other.status == "declined" and other.decision_note == "הוועדה מלאה השנה"
    assert len(dj_mail.outbox) == 2 and "הוועדה מלאה השנה" in dj_mail.outbox[1].body
    assert not Role.objects.filter(user=dana, kind=Role.COMMITTEE_MEMBER).exists()


# ------------------------------------------------------------------- the API

def test_the_decide_endpoint_works_the_queue_for_the_chat_and_is_closed_to_others(client, world):
    dana, inst = world["dana"], world["technion"]
    req = RoleRequest.objects.create(user=dana, role_kind="leader", institution=inst, message="x")
    client.force_login(dana)
    assert post(client, f"/academia360/api/admin/requests/{req.pk}/decide/", {"decision": "approve"}).status_code == 403
    client.logout()
    r = post(client, f"/academia360/api/admin/requests/{req.pk}/decide/", {"decision": "maybe"}, **bearer())
    assert r.status_code == 400
    r = post(client, f"/academia360/api/admin/requests/{req.pk}/decide/", {"decision": "approve"}, **bearer())
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["mailed"] == 1
    assert Role.objects.filter(user=dana, kind=Role.LEADER, active=True).exists()
    assert ChangeLog.objects.filter(model="academia360.Role", actor_kind=ChangeLog.AGENT).exists()
    r = post(client, f"/academia360/api/admin/requests/{req.pk}/decide/", {"decision": "decline"}, **bearer())
    assert r.status_code == 409
    assert post(client, "/academia360/api/admin/requests/9999/decide/", {"decision": "approve"}, **bearer()).status_code == 404


def test_the_generic_api_never_decides_or_invites_behind_the_functions_back(client, world):
    dana = world["dana"]
    req = RoleRequest.objects.create(user=dana, role_kind="committee", message="x")
    r = client.patch(f"/academia360/api/rolerequests/{req.pk}/", json.dumps({"status": "approved"}),
                     content_type="application/json", **bearer())
    assert r.status_code == 403 and "decide" in r.json()["detail"]
    req.refresh_from_db()
    assert req.status == "open" and not Role.objects.filter(user=dana).exists()
    r = post(client, "/academia360/api/invitations/", {"email": "x@example.com", "role_kind": "committee", "token": "t"}, **bearer())
    assert r.status_code == 403 and not Invitation.objects.exists()
    # a request made through the generic API still reaches the admin's inbox
    client.force_login(dana)
    r = post(client, "/academia360/api/rolerequests/", {"user": dana.pk, "role_kind": "leader",
                                                        "institution": world["technion"].pk, "message": "דרך ה-API"})
    assert r.status_code == 201 and len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["avi@example.com"]


def test_the_role_endpoint_reports_the_mail_and_still_refuses_as_before(client, world):
    dana, inst = world["dana"], world["technion"]
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "leader", "email": dana.email,
                                                       "institution": inst.pk, "title": "דיקנית"}, **bearer())
    assert r.status_code == 200 and r.json()["mailed"] == 1 and "roles" in r.json()
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == [dana.email]
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "chair", "email": dana.email}, **bearer())
    assert r.status_code == 400  # not on the committee yet
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "leader", "email": "ghost@example.com"}, **bearer())
    assert r.status_code == 404


def test_the_invite_endpoint_makes_an_invitation_or_grants_an_existing_account(client, world):
    inst = world["technion"]
    r = post(client, "/academia360/api/admin/invitations/", {"email": "new@example.com", "kind": "leader",
                                                             "institution": inst.pk, "title": "סגן נשיא"}, **bearer())
    assert r.status_code == 201 and r.json()["mailed"] == 1 and "/academia360/invite/" in r.json()["link"]
    inv = Invitation.objects.get()
    assert inv.email == "new@example.com" and inv.role_kind == "leader" and inv.institution == inst and inv.title == "סגן נשיא"
    assert inv.sent_at is not None and inv.accepted_at is None and len(inv.token) >= 40
    assert dj_mail.outbox[-1].to == ["new@example.com"] and inv.token in dj_mail.outbox[-1].body
    assert not User.objects.filter(email="new@example.com").exists()  # no account until they come
    r = post(client, "/academia360/api/admin/invitations/", {"email": world["dana"].email, "kind": "committee"}, **bearer())
    assert r.status_code == 201 and r.json().get("existing_account") is True
    assert Role.objects.filter(user=world["dana"], kind=Role.COMMITTEE_MEMBER, active=True).exists() and Invitation.objects.count() == 1
    r = post(client, "/academia360/api/admin/invitations/", {"email": "nobody", "kind": "committee"}, **bearer())
    assert r.status_code == 400


def test_the_cli_builds_the_people_calls(monkeypatch, capsys):
    import sys
    sys.path.insert(0, "scripts")
    import a360 as cli

    sent = []

    def fake_call(self, method, path, data=None, params=None):
        sent.append((method, path, data, params))
        return 200, {"ok": True, "count": 0, "results": []}

    monkeypatch.setattr(cli.Client, "call", fake_call)
    cli.main(["--dev", "--token", TOKEN, "requests"])
    cli.main(["--dev", "--token", TOKEN, "decide", "12", "approve", "--note", "ברוכה הבאה"])
    cli.main(["--dev", "--token", TOKEN, "invite", "leader", "p@example.com", "--institution", "4", "--title", "דיקן"])
    assert sent[0][:2] == ("GET", "rolerequests/") and sent[0][3] == {"status": "open"}
    assert sent[1][:2] == ("POST", "admin/requests/12/decide/") and sent[1][2] == {"decision": "approve", "note": "ברוכה הבאה"}
    assert sent[2][:2] == ("POST", "admin/invitations/") and sent[2][2]["institution"] == 4 and sent[2][2]["kind"] == "leader"
    assert "ok" in capsys.readouterr().out
