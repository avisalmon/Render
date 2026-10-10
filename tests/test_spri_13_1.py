"""SPR-I.13.1 improv: the repertoire library: level 1 pieces taught phrase by phrase, hand by hand.

Avi, 2026-10-10: "I want the note practice to have also a library of classical pieces. Bach etc. You can serve
them in multiple levels, from beginners to advanced. The teaching method should be bar by bar, hand by hand,
conquering the piece. Make sense? Like a piano teacher." Then: "Do the beginners you identified."

Here: the ladder, the models, the one-time seed, the API, the pass rules that are the server's. The page and the
staff rules are proved under Node (tests/js/spri131.test.js) and in the browser (test_spri_13_1_browser.py).

Traces: spec ch. 12, data model section 6d, backlog SPR-I.13.1.
"""

import io
import json
from pathlib import Path

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client

from improv import ladder
from improv.models import Piece, PiecePhrase, PieceTake, Player

pytestmark = pytest.mark.spri131

API = "/improv/api/"
PASSWORD = "spri131-pass-4417"
SEED = json.loads(Path("improv/seed_data/pieces.json").read_text(encoding="utf-8"))
SLUGS = ["ode-to-joy", "minuet-in-g", "musette-in-d", "prelude-in-c"]


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user("p131one", password=PASSWORD)
    two = User.objects.create_user("p131two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    call_command("seed_improv_pieces", stdout=io.StringIO())
    return {"one": one, "two": two}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def _rung(slug, key):
    piece = Piece.objects.get(slug=slug)
    return ladder.find([(p.first_bar, p.last_bar) for p in piece.phrases.all()], key)


def _take(slug="ode-to-joy", rung="p1-R-slow", **over):
    r = _rung(slug, rung) or {"hands": over.get("hands", "R"), "first_bar": over.get("first_bar", 1), "last_bar": over.get("last_bar", 1), "tempo": "slow"}
    piece = Piece.objects.get(slug=slug)
    notes = [n for n in piece.notes if n["hand"] == r["hands"] or r["hands"] == "B"][:4]
    notes = [{k: n[k] for k in ("hand", "step", "acc", "midi", "beat", "dur")} for n in notes]
    body = {
        "piece": slug, "rung": rung, "first_bar": r["first_bar"], "last_bar": r["last_bar"], "hands": r["hands"],
        "mode": "flow", "tempo_bpm": piece.slow_bpm if r["tempo"] == "slow" else piece.tempo_bpm, "curtain": False,
        "notes": notes,
        "events": [{"t_ms": 0, "type": "on", "note": notes[0]["midi"], "velocity": 80}],
        "results": [{"state": "right", "timing": "ontime", "offset_ms": 0, "played": None} for _ in notes],
        "score": 85, "pitch_accuracy": 0.9, "timing_accuracy": 0.8, "judge_version": 1,
    }
    body.update(over)
    return body


# ------------------------------------------------------------------ the ladder


def test_the_ladder_has_four_rungs_a_phrase_a_join_between_and_three_for_the_whole():
    for n in (1, 2, 4, 9):
        phrases = [(1 + 4 * i, 4 + 4 * i) for i in range(n)]
        rungs = ladder.rungs(phrases)
        assert len(rungs) == 4 * n + (n - 1) + 3
        assert len({r["key"] for r in rungs}) == len(rungs)
    r = ladder.rungs([(1, 4), (5, 8), (9, 12)])
    keys = [x["key"] for x in r]
    assert keys[:4] == ["p1-R-slow", "p1-L-slow", "p1-B-slow", "p1-B-tempo"]
    assert keys[4:9] == ["p2-R-slow", "p2-L-slow", "p2-B-slow", "p2-B-tempo", "j1-2"], "a join follows the phrase it extends"
    assert keys[-3:] == ["whole-B-slow", "whole-B-tempo", "perform"]
    join = next(x for x in r if x["key"] == "j1-2")
    assert (join["hands"], join["first_bar"], join["last_bar"], join["tempo"]) == ("B", 1, 8, "tempo")
    whole = next(x for x in r if x["key"] == "whole-B-slow")
    assert (whole["first_bar"], whole["last_bar"]) == (1, 12)
    assert next(x for x in r if x["key"] == "perform")["line"] == ladder.PERFORM_SCORE
    assert ladder.rungs([]) == []


def test_find_and_next_rung():
    phrases = [(1, 4), (5, 8)]
    assert ladder.find(phrases, "p2-L-slow")["hands"] == "L"
    assert ladder.find(phrases, "p3-L-slow") is None
    assert ladder.find(phrases, "drill") is None
    rungs = ladder.rungs(phrases)
    assert ladder.next_rung(rungs, set())["key"] == "p1-R-slow"
    assert ladder.next_rung(rungs, {"p1-R-slow", "p1-B-tempo"})["key"] == "p1-L-slow", "the first gap, not the highest pass"
    assert ladder.next_rung(rungs, {r["key"] for r in rungs}) is None


# ------------------------------------------------------------------ the seed


def test_the_seed_adds_the_four_beginner_pieces_and_is_idempotent(db):
    call_command("seed_improv_pieces", stdout=io.StringIO())
    assert set(Piece.objects.values_list("slug", flat=True)) == set(SLUGS)
    before = {p.slug: (p.pk, p.updated_at, p.phrases.count()) for p in Piece.objects.all()}
    phrase_ids = set(PiecePhrase.objects.values_list("pk", flat=True))
    call_command("seed_improv_pieces", stdout=io.StringIO())
    call_command("seed_improv_pieces", "--refresh-drafts", stdout=io.StringIO())
    assert Piece.objects.count() == 4
    assert {p.slug: (p.pk, p.updated_at, p.phrases.count()) for p in Piece.objects.all()} == before, "nothing changed, so nothing was written"
    assert set(PiecePhrase.objects.values_list("pk", flat=True)) == phrase_ids


def test_each_seeded_piece_is_whole_and_matches_the_file(people):
    assert [p["slug"] for p in SEED] == SLUGS
    for row in SEED:
        piece = Piece.objects.get(slug=row["slug"])
        assert piece.level == 1 and piece.authorship == "ai_drafted" and piece.status == "published"
        assert piece.notes == row["notes"] and piece.bars == row["bars"]
        assert piece.slow_bpm < piece.tempo_bpm
        phrases = list(piece.phrases.all())
        assert phrases[0].first_bar == 1 and phrases[-1].last_bar == piece.bars
        for a, b in zip(phrases, phrases[1:]):
            assert b.first_bar == a.last_bar + 1, "the phrases cover every bar once"
        assert {n["bar"] for n in piece.notes} <= set(range(1, piece.bars + 1))
        for n in piece.notes:
            assert n["hand"] in ("R", "L") and 0 <= n["beat"] < piece.bars * piece.beats_per_bar
            assert n["bar"] == int(n["beat"] // piece.beats_per_bar) + 1
        piece.full_clean()


def test_a_refresh_brings_a_draft_up_to_date_and_leaves_a_checked_piece_alone(people):
    ode = Piece.objects.get(slug="ode-to-joy")
    Piece.objects.filter(pk=ode.pk).update(blurb="old words")
    checked = Piece.objects.get(slug="minuet-in-g")
    Piece.objects.filter(pk=checked.pk).update(blurb="Avi's own words", authorship="reviewed")
    call_command("seed_improv_pieces", stdout=io.StringIO())
    assert Piece.objects.get(pk=ode.pk).blurb == "old words", "without the flag nothing is touched"
    call_command("seed_improv_pieces", "--refresh-drafts", stdout=io.StringIO())
    assert Piece.objects.get(pk=ode.pk).blurb != "old words"
    assert Piece.objects.get(pk=checked.pk).blurb == "Avi's own words", "a checked piece stays as it is"


# ------------------------------------------------------------------ the reference API


def test_the_pieces_are_listed_to_a_player_and_only_to_a_player(people):
    assert Client().get(f"{API}pieces/").status_code in (302, 401, 403, 404)
    listed = _client(people["one"]).get(f"{API}pieces/").json()
    assert [p["slug"] for p in listed] == SLUGS
    ode = listed[0]
    assert ode["authorship"] == "ai_drafted" and len(ode["phrases"]) == 4 and len(ode["notes"]) == 81
    assert _client(people["one"]).get(f"{API}pieces/?level=2").json() == []
    assert _client(people["one"]).get(f"{API}pieces/{ode['id']}/").json()["title"] == "Ode to Joy"
    assert _json(_client(people["one"]), "post", f"{API}pieces/", {}).status_code == 405
    assert _json(_client(people["one"]), "delete", f"{API}pieces/{ode['id']}/").status_code == 405
    phrases = _client(people["one"]).get(f"{API}piece-phrases/?piece=minuet-in-g").json()
    assert [p["order"] for p in phrases] == [1, 2, 3, 4] and phrases[0]["title"] == "Bars 1 to 4"


def test_a_draft_piece_is_hidden_from_players_and_shown_to_the_owner(people):
    Piece.objects.filter(slug="musette-in-d").update(status="draft")
    names = [p["slug"] for p in _client(people["one"]).get(f"{API}pieces/").json()]
    assert "musette-in-d" not in names
    assert _client(people["one"]).get(f"{API}piece-phrases/?piece=musette-in-d").json() == []
    owner = User.objects.create_superuser("p131owner", password=PASSWORD)
    assert "musette-in-d" in [p["slug"] for p in _client(owner).get(f"{API}pieces/").json()]
    assert _json(_client(people["one"]), "post", f"{API}piece-takes/", _take("musette-in-d")).status_code == 400


# ------------------------------------------------------------------ takes


def test_a_take_is_saved_to_its_player_and_nobody_elses(people):
    client = _client(people["one"])
    response = _json(client, "post", f"{API}piece-takes/", _take())
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["piece"] == "ode-to-joy" and data["rung"] == "p1-R-slow" and data["passed"] is True
    assert PieceTake.objects.get(pk=data["id"]).player == Player.objects.get(user=people["one"])
    assert _client(people["two"]).get(f"{API}piece-takes/").json() == []
    assert _client(people["two"]).get(f"{API}piece-takes/{data['id']}/").status_code == 404
    assert [t["id"] for t in client.get(f"{API}piece-takes/?piece=ode-to-joy&rung=p1-R-slow").json()] == [data["id"]]
    assert client.get(f"{API}piece-takes/?piece=minuet-in-g").json() == []


def test_the_pass_line_the_tempo_and_the_mode_are_the_servers(people):
    client = _client(people["one"])

    def post(**over):
        return _json(client, "post", f"{API}piece-takes/", _take(**over)).json()

    ode = Piece.objects.get(slug="ode-to-joy")
    assert post(score=79, passed=True)["passed"] is False, "79 is under the line whatever the client says"
    assert post(score=80)["passed"] is True
    assert post(score=100, mode="step")["passed"] is False, "step waits for the right note, so it cannot pass"
    assert post(score=95, tempo_bpm=ode.slow_bpm - 1)["passed"] is False, "under the slow tempo is not a slow pass"
    assert post(score=95, tempo_bpm=ode.slow_bpm + 20)["passed"] is True, "faster than the slow tempo counts"
    tempo = {"rung": "p1-B-tempo", "hands": "B"}
    assert post(**tempo, tempo_bpm=ode.tempo_bpm - 1, score=95)["passed"] is False, "an at-tempo rung needs the tempo"
    assert post(**tempo, tempo_bpm=ode.tempo_bpm, score=95)["passed"] is True
    perform = {"rung": "perform", "hands": "B", "first_bar": 1, "last_bar": 16, "tempo_bpm": ode.tempo_bpm}
    assert post(**perform, score=89)["passed"] is False, "a performance run has a higher line"
    assert post(**perform, score=90)["passed"] is True


def test_a_drill_is_kept_and_never_passes(people):
    client = _client(people["one"])
    body = _take(rung="drill", first_bar=3, last_bar=3, hands="R", score=100)
    response = _json(client, "post", f"{API}piece-takes/", body)
    assert response.status_code == 201, response.content
    assert response.json()["passed"] is False
    assert _json(client, "post", f"{API}piece-takes/", {**body, "last_bar": 99}).status_code == 400, "the piece has no bar 99"
    assert _json(client, "post", f"{API}piece-takes/", {**body, "first_bar": 5, "last_bar": 4}).status_code == 400


@pytest.mark.parametrize(
    "bad, field",
    [
        ({"rung": "p9-R-slow"}, "rung"),
        ({"rung": "p1-L-slow", "hands": "R"}, "rung"),
        ({"first_bar": 2}, "rung"),
        ({"piece": "nope"}, "piece"),
        ({"hands": "X"}, "hands"),
        ({"tempo_bpm": 20}, "tempo_bpm"),
        ({"mode": "wait"}, "mode"),
        ({"score": 101}, "score"),
        ({"pitch_accuracy": 1.5}, "pitch_accuracy"),
        ({"notes": []}, "notes"),
        ({"notes": [{"hand": "M", "step": 30, "acc": 0, "midi": 60, "beat": 0, "dur": 1}] * 4}, "notes"),
        ({"events": [{"t_ms": 0, "type": "on", "note": 60}]}, "events"),
        ({"results": [{"state": "maybe"}] * 4}, "results"),
        ({"results": [{"state": "right"}] * 3}, "results"),
    ],
)
def test_a_take_is_checked_for_shape_and_range(people, bad, field):
    response = _json(_client(people["one"]), "post", f"{API}piece-takes/", _take(**bad))
    assert response.status_code == 400, response.content
    assert field in response.json(), response.json()


def test_a_take_that_is_too_big_is_refused(people):
    note = {"hand": "R", "step": 30, "acc": 0, "midi": 64, "beat": 0, "dur": 1}
    big = _take(notes=[note] * 801, results=[{"state": "right"}] * 801)
    assert _json(_client(people["one"]), "post", f"{API}piece-takes/", big).status_code == 400


def test_a_player_may_delete_their_own_take_and_not_another_s(people):
    client = _client(people["one"])
    made = _json(client, "post", f"{API}piece-takes/", _take()).json()
    assert _client(people["two"]).delete(f"{API}piece-takes/{made['id']}/").status_code == 404
    assert client.delete(f"{API}piece-takes/{made['id']}/").status_code == 204


# ------------------------------------------------------------------ the repertoire read


def test_the_repertoire_read_names_the_next_rung_and_counts_a_pass_ahead(people):
    client = _client(people["one"])
    first = client.get(f"{API}repertoire/").json()
    ode = next(p for p in first["pieces"] if p["slug"] == "ode-to-joy")
    assert ode["total"] == 4 * 4 + 3 + 3 and ode["next"] == "p1-R-slow" and ode["passed_count"] == 0 and ode["done"] is False
    assert ode["rungs"][0]["tempo"] == "slow" and ode["rungs"][0]["best"] is None
    assert first["totals"] == {"takes": 0, "passes": 0, "pieces_done": 0}
    _json(client, "post", f"{API}piece-takes/", _take(score=60))
    assert client.get(f"{API}repertoire/").json()["pieces"][0]["next"] == "p1-R-slow", "a fail stays"
    _json(client, "post", f"{API}piece-takes/", _take(score=90))
    _json(client, "post", f"{API}piece-takes/", _take(rung="p2-L-slow", score=88))
    after = next(p for p in client.get(f"{API}repertoire/").json()["pieces"] if p["slug"] == "ode-to-joy")
    assert after["next"] == "p1-L-slow", "the first gap, not the highest pass"
    assert after["passed_count"] == 2
    first_rung = after["rungs"][0]
    assert first_rung["passed"] is True and first_rung["best"] == 90 and first_rung["takes"] == 2
    _json(client, "post", f"{API}piece-takes/", _take(rung="drill", first_bar=1, last_bar=1, score=100))
    assert client.get(f"{API}repertoire/").json()["totals"]["takes"] == 4
    other = _client(people["two"]).get(f"{API}repertoire/").json()
    assert other["pieces"][0]["next"] == "p1-R-slow" and other["totals"]["takes"] == 0
    assert _json(client, "post", f"{API}repertoire/", {}).status_code == 405


def test_climbing_every_rung_finishes_a_piece(people):
    client = _client(people["one"])
    piece = Piece.objects.get(slug="musette-in-d")
    rungs = next(p for p in client.get(f"{API}repertoire/").json()["pieces"] if p["slug"] == "musette-in-d")["rungs"]
    for row in rungs:
        tempo = piece.slow_bpm if row["tempo"] == "slow" else piece.tempo_bpm
        body = _take("musette-in-d", row["key"], score=95, tempo_bpm=tempo)
        assert _json(client, "post", f"{API}piece-takes/", body).status_code == 201
    done = client.get(f"{API}repertoire/").json()
    musette = next(p for p in done["pieces"] if p["slug"] == "musette-in-d")
    assert musette["done"] is True and musette["next"] is None
    assert done["totals"]["pieces_done"] == 1


# ------------------------------------------------------------------ the page, the admin and the model


def test_the_page_is_behind_the_gate_and_in_the_menu(people):
    assert Client().get("/improv/repertoire/").status_code == 302
    response = _client(people["one"]).get("/improv/repertoire/")
    assert response.status_code == 200
    text = response.content.decode()
    assert 'data-api-pieces="/improv/api/pieces/"' in text and 'data-api-takes="/improv/api/piece-takes/"' in text
    assert 'data-api-repertoire="/improv/api/repertoire/"' in text
    nav = text[text.index('<nav class="im-nav"'):text.index("</nav>")]
    assert 'href="/improv/repertoire/"' in nav


def test_the_admin_lists_the_pieces_and_their_takes():
    for model in (Piece, PieceTake):
        assert model in admin.site._registry


def test_a_slow_tempo_over_the_tempo_is_refused(db):
    row = SEED[0]
    keep = ("slug", "title", "composer", "level", "order", "key", "beats_per_bar", "bars", "tempo_bpm", "notes")
    piece = Piece(**{k: row[k] for k in keep}, slow_bpm=200)
    with pytest.raises(ValidationError):
        piece.full_clean()


def test_the_rules_pass_under_node():
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri131.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]
