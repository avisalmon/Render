"""SPR-I.4.3 improv: PracticeSession and Take, recorded by the page and kept by the server.

A take carries its own chart, key, tempo and feel (snapshots), the events as the MIDI
arrived, and the score the page computed with the judge version that computed it. The
server checks shape and ranges and keeps it; it does not re-judge (data model, section
11). Sessions and takes are the player's own: another player's do not exist for them.

Traces: spec ch. 5 and 6, feature 15, backlog SPR-I.4.3.
"""

import io
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Player, PracticeSession, Progression, Take

pytestmark = pytest.mark.spri43

SESSIONS = "/improv/api/sessions/"
TAKES = "/improv/api/takes/"
PASSWORD = "spri43-pass-7731"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p43member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p43other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p43stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "other": other, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _session(client):
    made = client.post(SESSIONS, {}, content_type="application/json")
    assert made.status_code == 201, made.content
    return made.json()


def _take_body(session_id, **changes):
    preset = Progression.objects.get(slug="ii-v-i-major")
    body = {
        "session": session_id,
        "progression": preset.pk,
        "style": preset.default_style_id,
        "chart": preset.chart,
        "home_key": preset.home_key,
        "key": "C",
        "time_signature": "4/4",
        "tempo": 120,
        "swing_ratio": "0.67",
        "loop_from": 0,
        "loop_to": 4,
        "started_at": timezone.now().isoformat(),
        "duration_ms": 16000,
        "bars": 4,
        "events": [
            {"t_ms": 0, "type": "on", "note": 62, "velocity": 90},
            {"t_ms": 400, "type": "off", "note": 62, "velocity": 0},
            {"t_ms": 500, "type": "on", "note": 65, "velocity": 88},
            {"t_ms": 900, "type": "off", "note": 65, "velocity": 0},
        ],
        "score": None,
        "metrics": {"notes": 2, "chordTonePct": 100, "meanOffsetMs": 0},
        "judge_version": 1,
    }
    body.update(changes)
    return body


# ----------------------------------------------------------------------- sessions


def test_a_session_is_mine_from_the_moment_it_is_made(people):
    client = _client(people["member"])
    session = _session(client)
    row = PracticeSession.objects.get(pk=session["id"])
    assert row.player.user == people["member"]
    assert row.active_seconds == 0 and row.ended_at is None
    assert client.get(SESSIONS).json()[0]["id"] == session["id"]


def test_a_session_is_closed_with_its_active_time(people):
    client = _client(people["member"])
    session = _session(client)
    ended = timezone.now().isoformat()
    reply = client.patch(f"{SESSIONS}{session['id']}/", {"active_seconds": 600, "ended_at": ended}, content_type="application/json")
    assert reply.status_code == 200, reply.content
    row = PracticeSession.objects.get(pk=session["id"])
    assert row.active_seconds == 600 and row.ended_at is not None


def test_another_players_session_does_not_exist_for_me(people):
    mine = _session(_client(people["member"]))
    other = _client(people["other"])
    assert other.get(f"{SESSIONS}{mine['id']}/").status_code == 404
    assert other.patch(f"{SESSIONS}{mine['id']}/", {"active_seconds": 1}, content_type="application/json").status_code == 404
    assert other.get(SESSIONS).json() == []


def test_a_visitor_gets_near_neither_sessions_nor_takes(people):
    visitor = _client(None)
    assert visitor.get(SESSIONS).status_code in (401, 403)
    assert visitor.post(SESSIONS, {}, content_type="application/json").status_code in (401, 403)
    assert visitor.post(TAKES, {}, content_type="application/json").status_code in (401, 403)
    assert PracticeSession.objects.count() == 0 and Take.objects.count() == 0


def test_a_signed_in_person_without_a_group_is_a_normal_player_with_their_own_sessions(people):
    stranger = _client(people["stranger"])
    assert stranger.get(SESSIONS).status_code == 200
    assert stranger.get(SESSIONS).json() == []
    made = _session(stranger)
    assert PracticeSession.objects.get(pk=made["id"]).player.user == people["stranger"]
    assert _client(people["member"]).get(SESSIONS).json() == [], "the new person's sitting is theirs alone"
    # A take needs a body; an empty one is a plain 400 for anyone signed in, not a 404.
    assert stranger.post(TAKES, {}, content_type="application/json").status_code == 400


# -------------------------------------------------------------------------- takes


def test_a_take_is_kept_whole_with_its_snapshots_and_its_events(people):
    client = _client(people["member"])
    session = _session(client)
    made = client.post(TAKES, _take_body(session["id"]), content_type="application/json")
    assert made.status_code == 201, made.content
    take = Take.objects.get(pk=made.json()["id"])
    assert take.player.user == people["member"]
    assert take.session_id == session["id"]
    assert take.chart == Progression.objects.get(slug="ii-v-i-major").chart
    assert take.key == "C" and take.tempo == 120 and str(take.swing_ratio) == "0.67"
    assert take.loop_from == 0 and take.loop_to == 4 and take.bars == 4
    assert len(take.events) == 4 and take.events[2] == {"t_ms": 500, "type": "on", "note": 65, "velocity": 88}
    assert take.score is None and take.metrics["chordTonePct"] == 100
    assert take.judge_version == 1 and take.is_kept is False


def test_the_chart_in_the_take_is_a_snapshot_that_survives_an_edit(people):
    client = _client(people["member"])
    session = _session(client)
    preset = Progression.objects.get(slug="ii-v-i-major")
    client.post(TAKES, _take_body(session["id"]), content_type="application/json")
    before = preset.chart
    preset.chart = "| C | C | C | C |"
    preset.save()
    take = Take.objects.get(player__user=people["member"])
    assert take.chart == before, "the take says what it was played over, whatever the progression says now"


def test_a_take_cannot_be_posted_into_someone_elses_session(people):
    theirs = _session(_client(people["other"]))
    reply = _client(people["member"]).post(TAKES, _take_body(theirs["id"]), content_type="application/json")
    assert reply.status_code == 400
    assert "session" in reply.json()


def test_a_take_may_point_at_a_preset_or_my_own_progression_and_not_another_players(people):
    client = _client(people["member"])
    session = _session(client)
    preset = Progression.objects.get(slug="ii-v-i-major")
    theirs = Progression.objects.create(
        owner=people["other"], title="Theirs", slug="theirs", genre="jazz", chart=preset.chart,
        home_key="C", time_signature="4/4", default_tempo=100, default_style=preset.default_style, difficulty=1,
    )
    assert client.post(TAKES, _take_body(session["id"], progression=theirs.pk), content_type="application/json").status_code == 400
    assert client.post(TAKES, _take_body(session["id"], progression=None, style=None), content_type="application/json").status_code == 201


@pytest.mark.parametrize(
    "field,value",
    [
        ("score", 101),
        ("score", -1),
        ("tempo", 10),
        ("tempo", 400),
        ("judge_version", 0),
        ("bars", 0),
        ("chart", "   "),
        ("key", "H"),
        ("home_key", "Hb"),
        ("time_signature", "13/4"),
        ("swing_ratio", "0.90"),
        ("duration_ms", -5),
        ("loop_to", 0),
        ("metrics", [1, 2]),
        ("events", {"t_ms": 0}),
        ("events", [{"t_ms": 0, "type": "on", "note": 200, "velocity": 90}]),
        ("events", [{"t_ms": 0, "type": "bang", "note": 60, "velocity": 90}]),
        ("events", [{"t_ms": 0.5, "type": "on", "note": 60, "velocity": 90}]),
        ("events", [{"t_ms": 0, "type": "on", "note": 60, "velocity": 300}]),
        ("events", [{"t_ms": 0, "type": "on", "note": 60}]),
        ("events", [None]),
    ],
)
def test_the_server_refuses_a_take_whose_shape_or_range_is_wrong(people, field, value):
    client = _client(people["member"])
    session = _session(client)
    reply = client.post(TAKES, _take_body(session["id"], **{field: value}), content_type="application/json")
    assert reply.status_code == 400, f"{field}={value!r} was accepted: {reply.content}"
    assert Take.objects.count() == 0


def test_bars_has_to_agree_with_the_loop(people):
    client = _client(people["member"])
    session = _session(client)
    reply = client.post(TAKES, _take_body(session["id"], bars=3), content_type="application/json")
    assert reply.status_code == 400 and "bars" in reply.json()


def test_a_take_with_no_notes_at_all_is_still_a_take(people):
    client = _client(people["member"])
    session = _session(client)
    reply = client.post(TAKES, _take_body(session["id"], events=[], metrics={"notes": 0}), content_type="application/json")
    assert reply.status_code == 201, reply.content


def test_a_take_can_be_kept_and_that_is_all_that_can_change(people):
    client = _client(people["member"])
    session = _session(client)
    take = client.post(TAKES, _take_body(session["id"]), content_type="application/json").json()
    assert client.patch(f"{TAKES}{take['id']}/", {"is_kept": True}, content_type="application/json").status_code == 200
    assert Take.objects.get(pk=take["id"]).is_kept is True
    assert client.patch(f"{TAKES}{take['id']}/", {"score": 100}, content_type="application/json").status_code == 403
    assert Take.objects.get(pk=take["id"]).score is None
    assert client.patch(f"{TAKES}{take['id']}/", {"events": []}, content_type="application/json").status_code == 403


def test_a_take_can_be_deleted_by_its_player_only(people):
    client = _client(people["member"])
    session = _session(client)
    take = client.post(TAKES, _take_body(session["id"]), content_type="application/json").json()
    assert _client(people["other"]).delete(f"{TAKES}{take['id']}/").status_code == 404
    assert _client(people["other"]).get(f"{TAKES}{take['id']}/").status_code == 404
    assert client.delete(f"{TAKES}{take['id']}/").status_code == 204
    assert not Take.objects.filter(pk=take["id"]).exists()


def test_takes_can_be_listed_by_what_is_kept_and_by_progression(people):
    client = _client(people["member"])
    session = _session(client)
    first = client.post(TAKES, _take_body(session["id"]), content_type="application/json").json()
    client.post(TAKES, _take_body(session["id"], progression=None), content_type="application/json")
    client.patch(f"{TAKES}{first['id']}/", {"is_kept": True}, content_type="application/json")
    assert len(client.get(TAKES).json()) == 2
    assert [t["id"] for t in client.get(TAKES + "?kept=1").json()] == [first["id"]]
    assert [t["id"] for t in client.get(TAKES + "?progression=ii-v-i-major").json()] == [first["id"]]
    assert client.get(TAKES + "?progression=no-such").json() == []


def test_the_api_is_documented(people):
    docs = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/sessions/" in docs and "/improv/api/takes/" in docs
    assert "judge_version" in docs and "is_kept" in docs
    assert re.search(r"does not re-judge|not re-judge|believes", docs), "the accepted browser-judging limit is written down"
