"""SPR-I.8.6 improv: the trainer read, shown on both screens, and the menu.

`GET /improv/api/trainer/` is a read over a player's scale runs and chord attempts and is stored
nowhere: the best run per key and octave count, the slowest chords, the weakest keys and the totals.
Here: what it computes, whose data it reads, the gate, and the screens and menu that carry it.

Traces: spec ch. 10, api "Trainer", backlog SPR-I.8.6.
"""

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import DrillAttempt, Player, Scale, ScaleRun

pytestmark = [pytest.mark.spri86, pytest.mark.django_db]

URL = "/improv/api/trainer/"
PASSWORD = "spri86-pass-5520"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user("p86one", password=PASSWORD)
    two = User.objects.create_user("p86two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    return {
        "one": one, "two": two, "stranger": User.objects.create_user("p86stranger", password=PASSWORD),
        "p1": Player.objects.get_or_create(user=one)[0], "p2": Player.objects.get_or_create(user=two)[0],
    }


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _run(player, root_pc=7, octaves=2, score=70, tempo=60):
    return ScaleRun.objects.create(
        player=player, scale=Scale.objects.get(slug="major"), root_pc=root_pc, octaves=octaves, notes_per_beat=octaves,
        tempo_bpm=tempo, score=score, pitch_accuracy=0.9, timing_accuracy=0.8, mean_offset_ms=10, judge_version=1,
    )


def _attempt(player, key_pc=7, chord="Gmaj7", position=1, ms=2000, correct=True, skipped=False, wrong=0):
    return DrillAttempt.objects.create(
        player=player, kind="chord_position", key_pc=key_pc, level=2,
        prompt={"title": f"{chord}, position {position}", "name": chord, "rootPc": key_pc, "symbol": "maj7", "position": position},
        answer={}, is_correct=correct and not skipped and wrong == 0, wrong_tries=wrong, skipped=skipped,
        response_ms=None if skipped else ms,
    )


def test_the_work_words_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri86.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_new_player_gets_an_empty_but_complete_read(people):
    data = _client(people["one"]).get(URL).json()
    assert data == {"scales": [], "slowest_chords": [], "weakest_keys": [], "totals": {"runs": 0, "passes": 0, "attempts": 0, "clean": 0}}


def test_the_best_run_of_each_key_and_octave_count_is_kept(people):
    p = people["p1"]
    _run(p, 7, 2, 60)
    _run(p, 7, 2, 85, tempo=70)
    _run(p, 7, 2, 40)
    _run(p, 7, 3, 55)
    _run(p, 2, 2, 90)
    rows = _client(people["one"]).get(URL).json()["scales"]
    assert [(r["root_pc"], r["octaves"], r["score"], r["tempo_bpm"], r["passed"], r["runs"]) for r in rows] == [
        (2, 2, 90, 60, True, 1), (7, 2, 85, 70, True, 3), (7, 3, 55, 60, False, 1),
    ]


def test_the_totals_count_runs_passes_attempts_and_clean_answers(people):
    p = people["p1"]
    _run(p, score=90)
    _run(p, score=50)
    _attempt(p)
    _attempt(p, wrong=2)
    _attempt(p, skipped=True)
    hinted = _attempt(p)
    DrillAttempt.objects.filter(pk=hinted.pk).update(hint_used=True)
    assert _client(people["one"]).get(URL).json()["totals"] == {"runs": 2, "passes": 1, "attempts": 4, "clean": 1}


def test_the_slowest_chords_need_three_answers_and_use_the_median(people):
    p = people["p1"]
    for ms in (1000, 9000, 2000):
        _attempt(p, chord="Cmaj7", key_pc=0, position=2, ms=ms)
    for ms in (5000, 6000, 7000):
        _attempt(p, chord="Am7", key_pc=9, position=1, ms=ms)
    _attempt(p, chord="Dm7", key_pc=2, position=1, ms=60000)
    _attempt(p, chord="Dm7", key_pc=2, position=1, ms=60000)
    rows = _client(people["one"]).get(URL).json()["slowest_chords"]
    assert [(r["title"], r["median_ms"], r["attempts"]) for r in rows] == [("Am7, position 1", 6000, 3), ("Cmaj7, position 2", 2000, 3)]


def test_skipped_prompts_have_no_time_and_do_not_slow_a_chord(people):
    p = people["p1"]
    for ms in (1000, 1000, 1000):
        _attempt(p, ms=ms)
    for _ in range(4):
        _attempt(p, skipped=True)
    rows = _client(people["one"]).get(URL).json()["slowest_chords"]
    assert [(r["median_ms"], r["attempts"]) for r in rows] == [(1000, 3)]


def test_only_the_five_slowest_chords_are_listed(people):
    p = people["p1"]
    for position in range(1, 8):
        for _ in range(3):
            _attempt(p, position=position, ms=1000 * position)
    rows = _client(people["one"]).get(URL).json()["slowest_chords"]
    assert [r["median_ms"] for r in rows] == [7000, 6000, 5000, 4000, 3000]


def test_the_weakest_keys_are_by_share_missed_and_need_five_prompts(people):
    p = people["p1"]
    for i in range(5):
        _attempt(p, key_pc=7, correct=i < 4)
    for i in range(5):
        _attempt(p, key_pc=2, correct=i < 2)
    for i in range(4):
        _attempt(p, key_pc=0, correct=False)
    rows = _client(people["one"]).get(URL).json()["weakest_keys"]
    assert [(r["key_pc"], r["attempts"], r["missed"]) for r in rows] == [(2, 5, 3), (7, 5, 1)]
    assert rows[0]["miss_share"] == 0.6


def test_a_skip_and_a_wrong_try_both_count_as_missed(people):
    p = people["p1"]
    for _ in range(3):
        _attempt(p, key_pc=4)
    _attempt(p, key_pc=4, wrong=1)
    _attempt(p, key_pc=4, skipped=True)
    row = _client(people["one"]).get(URL).json()["weakest_keys"][0]
    assert (row["attempts"], row["missed"]) == (5, 2)


def test_an_attempt_without_a_shape_the_page_would_write_is_ignored_not_fatal(people):
    p = people["p1"]
    DrillAttempt.objects.create(player=p, kind="chord_position", key_pc=1, level=1, prompt={}, answer={}, is_correct=True, response_ms=800)
    response = _client(people["one"]).get(URL)
    assert response.status_code == 200 and response.json()["slowest_chords"] == []


def test_one_players_read_is_not_anothers(people):
    _run(people["p1"], score=95)
    _attempt(people["p1"])
    data = _client(people["two"]).get(URL).json()
    assert data["scales"] == [] and data["totals"]["attempts"] == 0 and data["totals"]["runs"] == 0


def test_the_read_is_behind_the_gate_and_read_only(people):
    assert _client(None).get(URL).status_code == 404
    assert _client(people["stranger"]).get(URL).status_code == 404
    assert _client(people["one"]).post(URL, {}, content_type="application/json").status_code == 405


def test_the_read_is_in_the_api_docs():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/trainer/" in api


# ------------------------------------------------------------------ the screens and the menu


@pytest.mark.parametrize("path", ["/improv/scales/", "/improv/chords/"])
def test_both_trainer_screens_carry_the_read(people, path):
    text = _client(people["one"]).get(path).content.decode()
    assert "/improv/api/trainer/" in text and 'id="tr-work"' in text


def test_the_menu_links_both_screens(people):
    text = _client(people["one"]).get("/improv/").content.decode()
    assert 'href="/improv/scales/"' in text and 'href="/improv/chords/"' in text
