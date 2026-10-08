"""SPR-I.8.2 improv: the scale judge and the ScaleRun record.

The judging rules are proved under Node (tests/js/spri82.test.js). Here: the Node run is part of the
suite, a run is saved to its player and nobody else's, it is checked for shape and range, and the
pass line is the server's own say.

Traces: spec ch. 10, data model section 6a, backlog SPR-I.8.2.
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

from improv.models import Player, Scale, ScaleRun

pytestmark = pytest.mark.spri82

API = "/improv/api/"
PASSWORD = "spri82-pass-7713"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user("p82one", password=PASSWORD)
    two = User.objects.create_user("p82two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    stranger = User.objects.create_user("p82stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    return {"one": one, "two": two, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def _run(**over):
    body = {
        "root_pc": 3, "octaves": 2, "notes_per_beat": 2, "tempo_bpm": 60, "score": 91,
        "pitch_accuracy": 0.95, "timing_accuracy": 0.82, "mean_offset_ms": -14, "missed_steps": [4, 19], "judge_version": 1,
    }
    body.update(over)
    return body


def test_the_judge_passes_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri82.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ saving a run


def test_a_run_is_saved_to_its_player_and_the_scale_defaults_to_major(people):
    client = _client(people["one"])
    response = _json(client, "post", f"{API}scale-runs/", _run())
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["scale"] == "major"
    assert data["root_pc"] == 3 and data["octaves"] == 2 and data["tempo_bpm"] == 60
    assert data["missed_steps"] == [4, 19]
    assert data["created_at"]
    row = ScaleRun.objects.get(pk=data["id"])
    assert row.player == Player.objects.get(user=people["one"])
    assert row.scale == Scale.objects.get(slug="major")


def test_the_pass_line_is_the_servers_to_draw(people):
    client = _client(people["one"])
    low = _json(client, "post", f"{API}scale-runs/", _run(score=79, passed=True)).json()
    high = _json(client, "post", f"{API}scale-runs/", _run(score=80, passed=False)).json()
    assert low["passed"] is False
    assert high["passed"] is True
    changed = _json(client, "patch", f"{API}scale-runs/{low['id']}/", {"score": 95}).json()
    assert changed["passed"] is True


def test_a_run_may_name_the_scale_it_was_played_in(people):
    client = _client(people["one"])
    assert _json(client, "post", f"{API}scale-runs/", _run(scale="major")).status_code == 201
    assert _json(client, "post", f"{API}scale-runs/", _run(scale="no-such-scale")).status_code == 400


@pytest.mark.parametrize(
    "bad",
    [
        {"root_pc": 12}, {"root_pc": -1},
        {"octaves": 1}, {"octaves": 5},
        {"notes_per_beat": 1}, {"notes_per_beat": 5},
        {"tempo_bpm": 29}, {"tempo_bpm": 161},
        {"score": 101}, {"score": -1},
        {"pitch_accuracy": 1.5}, {"pitch_accuracy": -0.1},
        {"timing_accuracy": 2},
        {"mean_offset_ms": 99999},
        {"missed_steps": "4"}, {"missed_steps": [-1]}, {"missed_steps": [57]}, {"missed_steps": [1.5]}, {"missed_steps": [True]},
        {"missed_steps": list(range(58))},
        {"judge_version": 0},
    ],
)
def test_a_run_that_makes_no_sense_is_refused(people, bad):
    response = _json(_client(people["one"]), "post", f"{API}scale-runs/", _run(**bad))
    assert response.status_code == 400, bad
    assert ScaleRun.objects.count() == 0


def test_a_run_missing_a_required_field_is_refused(people):
    body = _run()
    del body["score"]
    assert _json(_client(people["one"]), "post", f"{API}scale-runs/", body).status_code == 400


# ------------------------------------------------------------------ whose they are


def test_a_player_sees_only_their_own_runs_newest_first(people):
    one, two = _client(people["one"]), _client(people["two"])
    first = _json(one, "post", f"{API}scale-runs/", _run(score=70)).json()
    second = _json(one, "post", f"{API}scale-runs/", _run(score=90)).json()
    _json(two, "post", f"{API}scale-runs/", _run(score=50))
    mine = one.get(f"{API}scale-runs/").json()
    assert [r["id"] for r in mine] == [second["id"], first["id"]]
    assert len(two.get(f"{API}scale-runs/").json()) == 1


def test_another_players_run_does_not_exist_for_you(people):
    one, two = _client(people["one"]), _client(people["two"])
    mine = _json(one, "post", f"{API}scale-runs/", _run()).json()
    url = f"{API}scale-runs/{mine['id']}/"
    assert two.get(url).status_code == 404
    assert _json(two, "patch", url, {"score": 1}).status_code == 404
    assert two.delete(url).status_code == 404
    assert ScaleRun.objects.get(pk=mine["id"]).score == 91


def test_you_can_read_change_and_delete_your_own(people):
    client = _client(people["one"])
    run = _json(client, "post", f"{API}scale-runs/", _run()).json()
    url = f"{API}scale-runs/{run['id']}/"
    assert client.get(url).json()["score"] == 91
    assert _json(client, "patch", url, {"tempo_bpm": 72}).json()["tempo_bpm"] == 72
    assert _json(client, "put", url, _run(score=60)).json()["score"] == 60
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_a_client_cannot_name_the_player(people):
    other = Player.objects.get_or_create(user=people["two"])[0]
    client = _client(people["one"])
    run = _json(client, "post", f"{API}scale-runs/", _run(player=other.pk)).json()
    assert ScaleRun.objects.get(pk=run["id"]).player.user == people["one"]


def test_runs_are_filtered_by_key_and_octaves(people):
    client = _client(people["one"])
    _json(client, "post", f"{API}scale-runs/", _run(root_pc=3, octaves=2))
    _json(client, "post", f"{API}scale-runs/", _run(root_pc=3, octaves=3, notes_per_beat=3))
    _json(client, "post", f"{API}scale-runs/", _run(root_pc=7, octaves=2))
    assert len(client.get(f"{API}scale-runs/?root_pc=3").json()) == 2
    assert len(client.get(f"{API}scale-runs/?octaves=2").json()) == 2
    assert len(client.get(f"{API}scale-runs/?root_pc=3&octaves=3").json()) == 1
    assert client.get(f"{API}scale-runs/?root_pc=abc").json() == []


def test_runs_are_behind_the_gate(people):
    assert _client(None).get(f"{API}scale-runs/").status_code in (401, 403)
    assert _json(_client(None), "post", f"{API}scale-runs/", _run()).status_code in (401, 403)
    assert ScaleRun.objects.count() == 0


def test_a_person_without_a_group_keeps_runs_of_their_own(people):
    stranger = _client(people["stranger"])
    assert stranger.get(f"{API}scale-runs/").status_code == 200
    assert _json(stranger, "post", f"{API}scale-runs/", _run()).status_code == 201
    assert ScaleRun.objects.get().player.user == people["stranger"]
    assert _client(people["one"]).get(f"{API}scale-runs/").json() == [], "another player never sees it"


def test_a_players_runs_go_when_the_player_goes(people):
    client = _client(people["one"])
    _json(client, "post", f"{API}scale-runs/", _run())
    people["one"].delete()
    assert ScaleRun.objects.count() == 0


# ------------------------------------------------------------------ the rest


def test_the_run_is_in_the_admin(db):
    assert ScaleRun in admin.site._registry


def test_the_migration_matches_the_model(db):
    out = io.StringIO()
    call_command("makemigrations", "improv", check=True, dry_run=True, stdout=out)


def test_the_docs_describe_the_run():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "/improv/api/scale-runs/" in api and "`ScaleRun`" in model
