"""SPR-I.8.4 improv: the chord pool, positions and matcher, and the DrillAttempt record.

The chords and the matching are proved under Node (tests/js/spri84.test.js). Here: the Node run is part
of the suite, an attempt is saved to its player and nobody else's, it is checked for shape and
consistency, and the filters work.

Traces: spec ch. 10, data model section 7, backlog SPR-I.8.4.
"""

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import DrillAttempt, Player

pytestmark = pytest.mark.spri84

API = "/improv/api/"
PASSWORD = "spri84-pass-3318"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user("p84one", password=PASSWORD)
    two = User.objects.create_user("p84two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    stranger = User.objects.create_user("p84stranger", password=PASSWORD)
    return {"one": one, "two": two, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def _attempt(**over):
    body = {
        "kind": "chord_position", "key_pc": 0, "level": 2,
        "prompt": {"name": "Cmaj7", "position": 2, "bassPc": 4},
        "answer": {"notes": [64, 67, 71, 72], "called": "Cmaj7/E"},
        "is_correct": True, "wrong_tries": 0, "hint_used": False, "skipped": False, "response_ms": 2412,
    }
    body.update(over)
    return body


def test_the_chords_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri84.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ saving an attempt


def test_an_attempt_is_saved_to_its_player(people):
    response = _json(_client(people["one"]), "post", f"{API}drill-attempts/", _attempt())
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["kind"] == "chord_position" and data["key_pc"] == 0 and data["level"] == 2
    assert data["prompt"]["name"] == "Cmaj7" and data["answer"]["called"] == "Cmaj7/E"
    assert data["response_ms"] == 2412 and data["answered_at"]
    assert DrillAttempt.objects.get(pk=data["id"]).player == Player.objects.get(user=people["one"])


def test_a_skipped_prompt_is_stored_as_a_miss_without_a_time(people):
    client = _client(people["one"])
    ok = _json(client, "post", f"{API}drill-attempts/", _attempt(skipped=True, is_correct=False, response_ms=None))
    assert ok.status_code == 201 and ok.json()["response_ms"] is None
    assert _json(client, "post", f"{API}drill-attempts/", _attempt(skipped=True, is_correct=False, response_ms=900)).status_code == 400
    assert _json(client, "post", f"{API}drill-attempts/", _attempt(skipped=True, is_correct=True, response_ms=None)).status_code == 400


def test_a_prompt_with_wrong_tries_is_not_correct(people):
    client = _client(people["one"])
    assert _json(client, "post", f"{API}drill-attempts/", _attempt(wrong_tries=2, is_correct=True)).status_code == 400
    assert _json(client, "post", f"{API}drill-attempts/", _attempt(wrong_tries=2, is_correct=False)).status_code == 201


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "ear_game"},
        {"key_pc": 12}, {"key_pc": -1},
        {"level": 0}, {"level": 4},
        {"prompt": "Cmaj7"}, {"prompt": [1]},
        {"answer": "x"},
        {"wrong_tries": -1}, {"wrong_tries": 201},
        {"response_ms": -5}, {"response_ms": 4_000_000},
    ],
)
def test_an_attempt_that_makes_no_sense_is_refused(people, bad):
    response = _json(_client(people["one"]), "post", f"{API}drill-attempts/", _attempt(**bad))
    assert response.status_code == 400, bad
    assert DrillAttempt.objects.count() == 0


# ------------------------------------------------------------------ whose they are


def test_a_player_sees_only_their_own_attempts_newest_first(people):
    one, two = _client(people["one"]), _client(people["two"])
    first = _json(one, "post", f"{API}drill-attempts/", _attempt(response_ms=1000)).json()
    second = _json(one, "post", f"{API}drill-attempts/", _attempt(response_ms=2000)).json()
    _json(two, "post", f"{API}drill-attempts/", _attempt())
    assert [r["id"] for r in one.get(f"{API}drill-attempts/").json()] == [second["id"], first["id"]]
    assert len(two.get(f"{API}drill-attempts/").json()) == 1


def test_another_players_attempt_does_not_exist_for_you(people):
    one, two = _client(people["one"]), _client(people["two"])
    mine = _json(one, "post", f"{API}drill-attempts/", _attempt()).json()
    url = f"{API}drill-attempts/{mine['id']}/"
    assert two.get(url).status_code == 404
    assert _json(two, "patch", url, {"level": 1}).status_code == 404
    assert two.delete(url).status_code == 404


def test_you_can_read_change_and_delete_your_own(people):
    client = _client(people["one"])
    row = _json(client, "post", f"{API}drill-attempts/", _attempt()).json()
    url = f"{API}drill-attempts/{row['id']}/"
    assert client.get(url).json()["response_ms"] == 2412
    assert _json(client, "patch", url, {"hint_used": True}).json()["hint_used"] is True
    assert _json(client, "put", url, _attempt(level=3)).json()["level"] == 3
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_a_client_cannot_name_the_player(people):
    other = Player.objects.get_or_create(user=people["two"])[0]
    row = _json(_client(people["one"]), "post", f"{API}drill-attempts/", _attempt(player=other.pk)).json()
    assert DrillAttempt.objects.get(pk=row["id"]).player.user == people["one"]


def test_attempts_are_filtered_by_key_and_kind(people):
    client = _client(people["one"])
    _json(client, "post", f"{API}drill-attempts/", _attempt(key_pc=0))
    _json(client, "post", f"{API}drill-attempts/", _attempt(key_pc=0))
    _json(client, "post", f"{API}drill-attempts/", _attempt(key_pc=7))
    assert len(client.get(f"{API}drill-attempts/?key_pc=0").json()) == 2
    assert len(client.get(f"{API}drill-attempts/?key_pc=7").json()) == 1
    assert client.get(f"{API}drill-attempts/?key_pc=abc").json() == []
    assert len(client.get(f"{API}drill-attempts/?kind=chord_position").json()) == 3
    assert client.get(f"{API}drill-attempts/?kind=other").json() == []


def test_attempts_are_behind_the_gate(people):
    assert _client(None).get(f"{API}drill-attempts/").status_code == 404
    assert _client(people["stranger"]).get(f"{API}drill-attempts/").status_code == 404
    assert _json(_client(people["stranger"]), "post", f"{API}drill-attempts/", _attempt()).status_code == 404
    assert DrillAttempt.objects.count() == 0


def test_a_players_attempts_go_when_the_player_goes(people):
    _json(_client(people["one"]), "post", f"{API}drill-attempts/", _attempt())
    people["one"].delete()
    assert DrillAttempt.objects.count() == 0


# ------------------------------------------------------------------ the rest


def test_the_attempt_is_in_the_admin(db):
    assert DrillAttempt in admin.site._registry


def test_the_migration_matches_the_model(db):
    call_command("makemigrations", "improv", check=True, dry_run=True, stdout=io.StringIO())


def test_the_docs_describe_the_attempt():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "/improv/api/drill-attempts/" in api and "`DrillAttempt`" in model
