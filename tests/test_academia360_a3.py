"""Academia360 sprint A.3: the agent's door (spec chapter 3; building_an_app.md
"giving an agent a key, without giving it the house").

Refusals first, about two to one:
- no token set in the environment means closed, whatever is presented;
- a wrong token is refused; an empty header never matches an empty setting;
- the token reaches only this app's API: it cannot touch the site's User
  table, and it cannot create an account through the role endpoint;
- the role endpoint grants and revokes for accounts that already exist and
  ignores any escalation field; a request for a missing account is refused;
- the token's writes land in the ChangeLog as the agent's, with the run and
  the reason it sent; the CLI builds exactly those requests.
"""

import json

import pytest
from django.contrib.auth.models import User

from academia360.models import AgentRun, ChangeLog, Institution, LeaderOf, Role

pytestmark = pytest.mark.django_db
TOKEN = "test-token-a360-4410-not-a-real-secret"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN
    settings.ACADEMIA360_AGENT_USER = ""


@pytest.fixture
def avi(db):
    return User.objects.create_user("avi", "avi@example.com", "pw-a360-4410", is_superuser=True, is_staff=True)


@pytest.fixture
def someone(db):
    return User.objects.create_user("someone", "someone@example.com", "pw-a360-4410")


def bearer(token=TOKEN):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def post(client, url, data, **headers):
    return client.post(url, json.dumps(data), content_type="application/json", **headers)


# ---------------------------------------------------------------- refusals

def test_an_unset_token_means_closed(client, avi, settings):
    settings.ACADEMIA360_AGENT_TOKEN = ""
    r = post(client, "/academia360/api/institutions/", {"slug": "x", "name_he": "x", "kind": "university"}, **bearer(""))
    assert r.status_code in (401, 403) and not Institution.objects.filter(slug="x").exists()
    r = post(client, "/academia360/api/institutions/", {"slug": "x", "name_he": "x", "kind": "university"}, **bearer())
    assert r.status_code in (401, 403) and not Institution.objects.filter(slug="x").exists()


def test_a_wrong_token_is_refused(client, avi):
    r = post(client, "/academia360/api/institutions/", {"slug": "x", "name_he": "x", "kind": "university"},
             **bearer("wrong"))
    assert r.status_code == 401 and not Institution.objects.exists()
    r = client.get("/academia360/api/roles/", **bearer("wrong"))
    assert r.status_code == 401


def test_the_token_needs_an_account_to_act_as(client, settings):
    """No superuser and no named account: the door stays shut."""
    r = client.get("/academia360/api/roles/", **bearer())
    assert r.status_code == 401


def test_the_token_cannot_reach_the_site_outside_this_app(client, avi):
    """Outside /academia360/ the token is just an unknown header: the admin
    site still asks for a login, and another app's API treats the request as
    anonymous (a write there is refused)."""
    r = client.get("/admin/auth/user/", **bearer())
    assert r.status_code == 302 and "/login/" in r.url
    r = client.post("/gallery/api/topics/", {"slug": "x", "name_he": "x", "name_en": "x"}, **bearer())
    assert r.status_code in (401, 403)
    r = client.get("/gallery/api/persons/me/", **bearer())
    assert r.status_code in (401, 403, 404)


def test_the_role_endpoint_never_creates_an_account(client, avi):
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "committee",
                                                       "email": "nobody@example.com"}, **bearer())
    assert r.status_code == 404 and not User.objects.filter(email="nobody@example.com").exists()


def test_the_role_endpoint_ignores_escalation_fields(client, avi, someone):
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "committee", "email": someone.email,
                                                       "is_superuser": True, "is_staff": True, "password": "x"},
             **bearer())
    assert r.status_code == 200
    someone.refresh_from_db()
    assert not someone.is_superuser and not someone.is_staff and someone.check_password("pw-a360-4410")
    assert Role.objects.filter(user=someone, kind=Role.COMMITTEE_MEMBER, active=True).exists()


def test_a_leader_grant_needs_an_institution(client, avi, someone):
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "leader", "email": someone.email},
             **bearer())
    assert r.status_code == 400 and not Role.objects.filter(user=someone).exists()


def test_the_role_endpoint_is_closed_to_everyone_but_admin_and_token(client, avi, someone):
    client.force_login(someone)
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "committee", "email": someone.email})
    assert r.status_code == 403 and not Role.objects.filter(user=someone).exists()
    Role.objects.create(user=someone, kind=Role.COMMITTEE_MEMBER)
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "admin", "email": someone.email})
    assert r.status_code == 403 and not Role.objects.filter(user=someone, kind=Role.ADMIN).exists()


# --------------------------------------------------------------- the happy path

def test_the_token_reads_and_writes_as_the_admin_and_is_logged(client, avi):
    assert client.get("/academia360/api/roles/", **bearer()).status_code == 200
    run = post(client, "/academia360/api/agentruns/", {"purpose": "test run", "sources": "x"}, **bearer())
    assert run.status_code == 201
    run_id = run.json()["id"]
    r = post(client, "/academia360/api/institutions/", {"slug": "haifa", "name_he": "אוניברסיטת חיפה", "kind": "university"},
             **bearer(), HTTP_X_A360_RUN=str(run_id), HTTP_X_A360_REASON="haifa.ac.il/about")
    assert r.status_code == 201
    log = ChangeLog.objects.get(model="academia360.Institution", row_id=str(r.json()["id"]))
    assert log.actor_kind == ChangeLog.AGENT and log.by == avi and log.run_id == run_id and log.reason == "haifa.ac.il/about"
    assert AgentRun.objects.get(pk=run_id).rows_touched == 1
    # A session write by the same person is a person's write.
    client.force_login(avi)
    r = post(client, "/academia360/api/institutions/", {"slug": "tau", "name_he": "תל אביב", "kind": "university"})
    assert ChangeLog.objects.get(model="academia360.Institution", row_id=str(r.json()["id"])).actor_kind == ChangeLog.PERSON


def test_grant_and_revoke_leader_and_attributes(client, avi, someone):
    from academia360.models import Program
    Program.objects.create(slug="academia-360", name="אקדמיה 360")
    inst = Institution.objects.create(slug="technion", name_he="הטכניון", kind="university")
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "leader", "email": someone.email,
                                                       "institution": inst.pk, "title": "סגנית נשיא"}, **bearer())
    assert r.status_code == 200
    assert LeaderOf.objects.filter(user=someone, institution=inst, active=True, title="סגנית נשיא").exists()
    assert Role.objects.filter(user=someone, kind=Role.LEADER, active=True).exists()
    r = post(client, "/academia360/api/roles/grant/", {"action": "revoke", "kind": "leader", "email": someone.email,
                                                       "institution": inst.pk}, **bearer())
    assert r.status_code == 200
    assert not LeaderOf.objects.filter(user=someone, active=True).exists()
    assert not Role.objects.filter(user=someone, kind=Role.LEADER, active=True).exists()
    # Chair and reviewer are attributes on a committee member.
    post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "committee", "email": someone.email}, **bearer())
    r = post(client, "/academia360/api/roles/grant/", {"action": "grant", "kind": "chair", "email": someone.email}, **bearer())
    assert r.status_code == 200
    from academia360 import access
    someone = User.objects.get(pk=someone.pk)
    assert access.is_chair(someone)
    assert ChangeLog.objects.filter(model="academia360.Role", actor_kind=ChangeLog.AGENT).exists()


def test_the_cli_builds_the_same_requests(monkeypatch, capsys):
    import sys
    sys.path.insert(0, "scripts")
    import a360 as cli

    sent = []

    def fake_call(self, method, path, data=None, params=None):
        sent.append((method, path, data, params, self.token, self.run, self.reason))
        return 201, {"id": 7}

    monkeypatch.setattr(cli.Client, "call", fake_call)
    cli.main(["--dev", "--token", TOKEN, "--run", "3", "--reason", "src", "create", "researchers",
              "--data", '{"name_he": "x", "institution": 1, "slug": "x"}'])
    cli.main(["--prod", "--token", TOKEN, "grant", "leader", "p@example.com", "--institution", "4"])
    cli.main(["--dev", "--token", TOKEN, "list", "institutions", "--q", "kind=university"])
    assert sent[0][:2] == ("POST", "researchers/") and sent[0][2]["slug"] == "x" and sent[0][5] == 3 and sent[0][6] == "src"
    assert sent[1][:2] == ("POST", "roles/grant/") and sent[1][2]["institution"] == 4 and sent[1][2]["action"] == "grant"
    assert sent[2][:2] == ("GET", "institutions/") and sent[2][3] == {"kind": "university"}
    assert '"id": 7' in capsys.readouterr().out
