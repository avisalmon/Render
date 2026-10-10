"""SPR-I.12.1 improv: the reading trainer: the ladder, the generator, the judge and the ReadingTake record.

Avi, 2026-10-10: "The user will get a sheet note 2 hands and the system will practice him. It will include a
show me, play, score"; then: "Right hand first, after success left hand and then after success both. Start
with C but progress to the rest. Also hint what scale we are near the left indication."

The rules are proved under Node (tests/js/spri121.test.js). Here: the Node run is part of the suite, the page
is behind the gate and carries the three piano keys, a take is saved to its player and nobody else's, it is
checked for shape, the pass line and the Flow-only rule are the server's, and the ladder read moves on a pass.

Traces: spec ch. 11, data model section 6c, backlog SPR-I.12.1.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player, ReadingTake
from improv.reading import STAGES, stage_index, stage_of, zone_of

pytestmark = pytest.mark.spri121

API = "/improv/api/"
PASSWORD = "spri121-pass-3318"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user("p121one", password=PASSWORD)
    two = User.objects.create_user("p121two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    return {"one": one, "two": two}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def _note(**over):
    note = {"hand": "R", "step": 32, "acc": 0, "midi": 67, "beat": 0, "dur": 1}
    note.update(over)
    return note


def _take(**over):
    notes = [_note(), _note(beat=1, step=33, midi=69), _note(beat=2, step=34, midi=71), _note(beat=3, step=35, midi=72, dur=1)]
    body = {
        "key": "C", "hands": "R", "difficulty": 1, "tempo_bpm": 72, "mode": "flow", "curtain": False, "seed": 4242,
        "notes": notes,
        "events": [{"t_ms": 0, "type": "on", "note": 67, "velocity": 80}, {"t_ms": 833, "type": "on", "note": 69, "velocity": 80}],
        "results": [
            {"state": "right", "timing": "ontime", "offset_ms": 0, "played": None},
            {"state": "right", "timing": "late", "offset_ms": 200, "played": None},
            {"state": "wrong", "timing": None, "offset_ms": 10, "played": 72},
            {"state": "missed", "timing": None, "offset_ms": None, "played": None},
        ],
        "score": 85, "pitch_accuracy": 0.5, "timing_accuracy": 0.5, "judge_version": 1,
    }
    body.update(over)
    return body


def test_the_rules_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri121.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


# ------------------------------------------------------------------ the page and the gate


def test_the_page_is_behind_the_gate_and_carries_the_three_keys(people):
    visitor = Client().get("/improv/reading/")
    assert visitor.status_code == 302
    assert visitor.headers["Location"].startswith("/improv/?next=")
    response = _client(people["one"]).get("/improv/reading/")
    assert response.status_code == 200
    text = response.content.decode()
    screen = text[text.index('<div id="reading"'):text.index("</main>")]
    assert 'data-api-takes="/improv/api/reading-takes/"' in screen
    assert 'data-api-reading="/improv/api/reading/"' in screen
    assert 'data-api-player="/improv/api/player/"' in screen
    assert re.search(r'id="rd-start"[^>]*data-key-action="primary"', screen)
    assert re.search(r'id="rd-show"[^>]*data-key-action="secondary"', screen)
    assert re.search(r'id="rd-next"[^>]*data-key-action="tertiary"', screen)
    assert '<svg id="rd-staff"' in screen
    nav = text[text.index('<nav class="im-nav"'):text.index("</nav>")]
    assert 'href="/improv/reading/"' in nav, "Reading is in the main menu"


def test_the_scripts_are_the_pure_module_the_staff_and_the_page(people):
    text = _client(people["one"]).get("/improv/reading/").content.decode()
    order = [m for m in re.findall(r"improv/([a-z-]+)\.js", text)]
    assert order.index("reading") < order.index("staff-view") < order.index("reading-page")
    assert "keyboard-view" in order and "midi" in order and "synth" in order


# ------------------------------------------------------------------ saving a take


def test_a_take_is_saved_to_its_player_and_listed_newest_first(people):
    client = _client(people["one"])
    response = _json(client, "post", f"{API}reading-takes/", _take())
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["key"] == "C" and data["hands"] == "R" and data["seed"] == 4242 and data["mode"] == "flow"
    assert data["passed"] is True and data["created_at"]
    assert len(data["notes"]) == 4 and len(data["results"]) == 4 and len(data["events"]) == 2
    row = ReadingTake.objects.get(pk=data["id"])
    assert row.player == Player.objects.get(user=people["one"])
    second = _json(client, "post", f"{API}reading-takes/", _take(score=40)).json()
    listed = client.get(f"{API}reading-takes/").json()
    assert [t["id"] for t in listed] == [second["id"], data["id"]]
    assert _client(people["two"]).get(f"{API}reading-takes/").json() == []
    assert _client(people["two"]).get(f"{API}reading-takes/{data['id']}/").status_code == 404
    assert client.get(f"{API}reading-takes/?mode=flow&key=C&hands=R").json()[0]["id"] == second["id"]
    assert client.get(f"{API}reading-takes/?hands=L").json() == []


def test_the_pass_line_is_the_servers_and_step_mode_never_passes(people):
    client = _client(people["one"])
    low = _json(client, "post", f"{API}reading-takes/", _take(score=79, passed=True)).json()
    assert low["passed"] is False, "79 is under the line whatever the client says"
    line = _json(client, "post", f"{API}reading-takes/", _take(score=80)).json()
    assert line["passed"] is True
    step = _json(client, "post", f"{API}reading-takes/", _take(score=100, mode="step")).json()
    assert step["passed"] is False, "step mode waits for the right note, so it cannot pass"
    assert _json(client, "patch", f"{API}reading-takes/{step['id']}/", {"passed": True}).json()["passed"] is False


@pytest.mark.parametrize(
    "bad, field",
    [
        ({"key": "H"}, "key"),
        ({"key": "Gb"}, "key"),
        ({"hands": "X"}, "hands"),
        ({"difficulty": 4}, "difficulty"),
        ({"tempo_bpm": 20}, "tempo_bpm"),
        ({"mode": "wait"}, "mode"),
        ({"score": 101}, "score"),
        ({"pitch_accuracy": 1.5}, "pitch_accuracy"),
        ({"notes": []}, "notes"),
        ({"notes": [_note(hand="M")]}, "notes"),
        ({"notes": [_note(midi=128)]}, "notes"),
        ({"notes": [_note(acc=2)]}, "notes"),
        ({"events": [{"t_ms": 0, "type": "on", "note": 60}]}, "events"),
        ({"results": [{"state": "maybe"}] * 4}, "results"),
        ({"results": [{"state": "right", "played": 200}] * 4}, "results"),
        ({"results": [{"state": "right"}] * 3}, "results"),
    ],
)
def test_a_take_is_checked_for_shape_and_range(people, bad, field):
    response = _json(_client(people["one"]), "post", f"{API}reading-takes/", _take(**bad))
    assert response.status_code == 400, response.content
    assert field in response.json(), response.json()


# ------------------------------------------------------------------ the ladder read


def test_the_ladder_moves_on_a_pass_and_counts_a_pass_ahead(people):
    client = _client(people["one"])
    first = client.get(f"{API}reading/").json()
    assert first["stage"] == {"index": 0, "key": "C", "hands": "R", "difficulty": 1, "total": STAGES, "done": False}
    assert first["passed"] == [] and first["focus"] == [] and first["totals"] == {"takes": 0, "passes": 0}
    _json(client, "post", f"{API}reading-takes/", _take(score=60))
    assert client.get(f"{API}reading/").json()["stage"]["index"] == 0, "a fail stays"
    _json(client, "post", f"{API}reading-takes/", _take(score=90))
    after = client.get(f"{API}reading/").json()
    assert after["stage"]["index"] == 1 and after["stage"]["hands"] == "L" and after["stage"]["key"] == "C"
    assert after["passed"] == [0]
    _json(client, "post", f"{API}reading-takes/", _take(score=95, key="G", hands="B"))
    ahead = client.get(f"{API}reading/").json()
    assert ahead["stage"]["index"] == 6 and ahead["stage"]["key"] == "F", "a pass ahead moves the path past it"
    assert ahead["passed"] == [0, 5]
    assert [b["index"] for b in ahead["bests"]] == [0, 5]
    assert ahead["bests"][0]["score"] == 90 and ahead["bests"][0]["takes"] == 2
    _json(client, "post", f"{API}reading-takes/", _take(score=100, mode="step", key="F", hands="R"))
    assert client.get(f"{API}reading/").json()["stage"]["index"] == 6, "a step take moves nothing"
    assert client.get(f"{API}reading/").json()["totals"] == {"takes": 4, "passes": 2}
    assert _client(people["two"]).get(f"{API}reading/").json()["stage"]["index"] == 0
    assert _json(client, "post", f"{API}reading/", {}).status_code == 405


def test_the_weak_spots_come_from_the_last_month_and_lean_the_focus(people):
    client = _client(people["one"])
    notes = [_note(step=27 + (i % 3), midi=60, beat=i) for i in range(8)]
    results = [{"state": "wrong" if i % 2 else "right", "timing": None, "offset_ms": 0, "played": 62 if i % 2 else None} for i in range(8)]
    _json(client, "post", f"{API}reading-takes/", _take(notes=notes, results=results, score=50))
    read = client.get(f"{API}reading/").json()
    assert read["zones"] == [{"zone": "treble-below", "seen": 8, "missed": 4, "share": 0.5}]
    assert read["focus"] == ["treble-below"]
    old = ReadingTake.objects.get()
    ReadingTake.objects.filter(pk=old.pk).update(created_at=old.created_at.replace(year=old.created_at.year - 1))
    assert client.get(f"{API}reading/").json()["zones"] == [], "older than thirty days is forgotten"


def test_the_python_ladder_agrees_with_the_javascript_one():
    assert STAGES == 36
    assert stage_index("C", "R") == 0 and stage_index("C", "B") == 2 and stage_index("Bb", "B") == 14 and stage_index("F#", "B") == 35
    assert stage_index("Gb", "B") is None
    assert stage_of(12) == {"index": 12, "key": "Bb", "hands": "R", "difficulty": 2, "total": 36}
    assert zone_of("R", 28) == "treble-below" and zone_of("R", 34) == "treble-on" and zone_of("L", 27) == "bass-above"
    js = Path("static/improv/reading.js").read_text(encoding="utf-8")
    for key in ("C", "G", "F", "D", "Bb", "A", "Eb", "E", "Ab", "B", "Db", "F#"):
        assert f'name: "{key}"' in js


# ------------------------------------------------------------------ the tempo, the admin and the docs


def test_the_reading_tempo_is_the_players_and_is_remembered(people):
    client = _client(people["one"])
    assert client.get(f"{API}player/").json()["reading_tempo"] == 72
    assert _json(client, "patch", f"{API}player/", {"reading_tempo": 96}).status_code == 200
    assert client.get(f"{API}player/").json()["reading_tempo"] == 96
    assert _json(client, "patch", f"{API}player/", {"reading_tempo": 10}).status_code == 400


def test_the_admin_lists_reading_takes():
    assert ReadingTake in admin.site._registry


def test_the_docs_describe_the_reading_trainer_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "## Chapter 11. The reading trainer" in spec
    assert "right hand first" in spec.lower() and "curtain" in spec.lower()
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "### `ReadingTake`" in model and "reading_tempo" in model
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/reading-takes/" in api and "/improv/api/reading/" in api
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"\| SPR-I\.12\.1 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)
