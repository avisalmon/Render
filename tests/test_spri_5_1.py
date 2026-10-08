"""SPR-I.5.1 improv: Phrase, Lesson and Exercise, their API, and the pages that teach from them.

A lesson is Read, Hear, Play. The rows are content written during development and seeded once
(SPR-I.5.3), so the API is read-only for lessons and exercises, and a player's own phrases are
the only content row a player may write. A lesson is hidden until it is published, except from
a superuser, who is the one who reads it before it is. The scoring parameters of an exercise are
checked when the row is saved, because a typo in them would otherwise surface as a take that
can never pass.

Traces: spec ch. 6 (the cycle of a lesson), data model section 4, backlog SPR-I.5.1.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from improv import teaching
from improv.models import Exercise, Lesson, Phrase, Progression, Take

pytestmark = pytest.mark.spri51

API = "/improv/api/"
PASSWORD = "spri51-pass-4417"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p51member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p51other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p51stranger", password=PASSWORD)
    admin = User.objects.create_user("p51admin", password=PASSWORD, is_staff=True, is_superuser=True)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "other": other, "stranger": stranger, "admin": admin}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


NOTES = [
    {"midi": 62, "beat": 0, "length": 1, "velocity": 90},
    {"midi": 65, "beat": 1, "length": 1, "velocity": 88},
    {"midi": 69, "beat": 2, "length": 2, "velocity": 92},
]


@pytest.fixture
def content(people):
    iivi = Progression.objects.get(slug="ii-v-i-major")
    phrase = Phrase.objects.create(name="D F A", slug="d-f-a", kind="demo", notes=NOTES, length_beats=4, written_in_key="C", is_preset=True)
    first = Lesson.objects.create(
        track="chord_tones", order=1, title="Chord tones over a ii-V-I", slug="chord-tones-ii-v-i", level=1,
        summary="Land on chord tones.", explanation="## Why\n\nChord tones **are** the sound.",
        demo_phrase=phrase, progression=iivi, style=iivi.default_style, status="published", authorship="ai_drafted",
    )
    second = Lesson.objects.create(
        track="guide_tones", order=1, title="Guide tones", slug="guide-tones", level=1, summary="Thirds and sevenths.",
        explanation="Text.", progression=iivi, prerequisite=first, status="published", authorship="ai_drafted",
    )
    draft = Lesson.objects.create(
        track="scales_modes", order=1, title="Draft lesson", slug="draft-lesson", level=2, summary="Not yet.",
        explanation="Text.", progression=iivi, status="draft", authorship="ai_drafted",
    )
    ex1 = Exercise.objects.create(
        lesson=first, order=1, slug="chord-tones-beats-1-3", title="Chord tones on 1 and 3", instructions="Play chord tones on beats 1 and 3.",
        progression=iivi, key="C", tempo=90, style=iivi.default_style, bars=4, scoring_kind="chord_tones_on_beats",
        scoring_params={"beats": [1, 3]}, pass_score=80, xp=20,
    )
    ex2 = Exercise.objects.create(
        lesson=first, order=2, slug="chord-tones-every-beat", title="Chord tones on every beat", instructions="Every beat.",
        progression=iivi, key="C", tempo=80, bars=4, scoring_kind="chord_tones_on_beats", scoring_params={}, pass_score=70, xp=25,
    )
    hidden = Exercise.objects.create(
        lesson=draft, order=1, slug="draft-exercise", title="Hidden", instructions="x", progression=iivi, key="C", tempo=90,
        bars=4, scoring_kind="scale_only", scoring_params={}, pass_score=70, xp=10,
    )
    challenge = Exercise.objects.create(
        lesson=None, order=1, slug="approach-challenge", title="Approach challenge", instructions="Approach every downbeat.",
        progression=iivi, key="C", tempo=90, bars=4, scoring_kind="approach_notes", scoring_params={"beats": [1]},
        pass_score=60, xp=30, daily_eligible=True,
    )
    return dict(iivi=iivi, phrase=phrase, first=first, second=second, draft=draft, ex1=ex1, ex2=ex2, hidden=hidden, challenge=challenge)


# ------------------------------------------------------------ the checks, on their own


def test_a_phrase_of_notes_on_beats_is_accepted():
    assert teaching.check_notes(NOTES, 4) is None


@pytest.mark.parametrize(
    "notes, length, why",
    [
        ("not a list", 4, "list"),
        ([], 4, "at least one"),
        ([{"midi": 62, "beat": 0, "length": 1}], 4, "velocity"),
        ([{"midi": 128, "beat": 0, "length": 1, "velocity": 90}], 4, "midi"),
        ([{"midi": 62, "beat": -1, "length": 1, "velocity": 90}], 4, "beat"),
        ([{"midi": 62, "beat": 0, "length": 0, "velocity": 90}], 4, "length"),
        ([{"midi": 62, "beat": 4, "length": 1, "velocity": 90}], 4, "inside"),
        ([{"midi": 62, "beat": 0, "length": 1, "velocity": 0}], 4, "velocity"),
        ([{"midi": True, "beat": 0, "length": 1, "velocity": 90}], 4, "midi"),
        ([{"midi": 62, "beat": 0, "length": 1, "velocity": 90}] * 201, 400, "most"),
    ],
)
def test_a_phrase_that_is_not_notes_on_beats_is_refused_with_a_reason(notes, length, why):
    problem = teaching.check_notes(notes, length)
    assert problem and why in problem.lower(), problem


@pytest.mark.parametrize(
    "kind, params",
    [
        ("free_play", {}),
        ("scale_only", {}),
        ("chord_tones_on_beats", {}),
        ("chord_tones_on_beats", {"beats": [1, 3]}),
        ("guide_tones", {"step": 2}),
        ("approach_notes", {"beats": [1]}),
        ("rhythm_motif", {"pattern": [0, 1.5, 2, 3.5]}),
        ("call_and_response", {"phrase": [[0, 62], [1, 64]], "answerBar": 1}),
        ("call_and_response", {"phrase": [[0, 62]], "answerBar": 3, "exact": True}),
    ],
)
def test_scoring_parameters_in_the_judges_own_shape_are_accepted(kind, params):
    assert teaching.check_scoring(kind, params, beats_per_bar=4, bars=4) is None


@pytest.mark.parametrize(
    "kind, params, why",
    [
        ("scale_only", {"beats": [1]}, "beats"),
        ("chord_tones_on_beats", {"beats": [0]}, "beat"),
        ("chord_tones_on_beats", {"beats": [5]}, "beat"),
        ("chord_tones_on_beats", {"beats": "1"}, "beat"),
        ("chord_tones_on_beats", {"beat": [1]}, "beat"),
        ("guide_tones", {"step": -1}, "step"),
        ("approach_notes", {"beats": []}, "beat"),
        ("rhythm_motif", {}, "pattern"),
        ("rhythm_motif", {"pattern": [4]}, "pattern"),
        ("rhythm_motif", {"pattern": ["x"]}, "pattern"),
        ("call_and_response", {}, "phrase"),
        ("call_and_response", {"phrase": [[0]]}, "phrase"),
        ("call_and_response", {"phrase": [[0, 62]], "answerBar": 4}, "answerbar"),
        ("call_and_response", {"phrase": [[0, 62]], "answerBar": 0}, "answerbar"),
        ("call_and_response", {"phrase": [[0, 62]], "answerBar": 1, "exact": "yes"}, "exact"),
        ("comping_voicings", {}, "version"),
        ("telepathy", {}, "kind"),
        ("free_play", "x", "object"),
    ],
)
def test_scoring_parameters_the_judge_would_throw_on_are_refused_when_saved(kind, params, why):
    problem = teaching.check_scoring(kind, params, beats_per_bar=4, bars=4)
    assert problem and why in problem.lower(), problem


def test_the_scoring_kinds_the_python_knows_are_the_ones_the_judge_scores():
    judge = Path("static/improv/judge.js").read_text(encoding="utf-8")
    scored = re.findall(r'"([a-z_]+)"', judge.split("SCORING_KINDS = [")[1].split("]")[0])
    assert sorted(teaching.SCORED_KINDS) == sorted(scored)
    assert set(Exercise.ScoringKind.values) == set(scored) | {"comping_voicings"}


# --------------------------------------------------------------------------- the models


def test_a_track_position_holds_one_lesson(content):
    iivi = content["iivi"]
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesson.objects.create(track="chord_tones", order=1, title="Again", slug="again", level=1, summary="x", explanation="x", progression=iivi)


def test_a_lesson_slug_is_unique(content):
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesson.objects.create(track="chord_tones", order=9, title="Dup", slug="guide-tones", level=1, summary="x", explanation="x")


def test_a_new_lesson_is_a_draft_that_nobody_has_read():
    assert Lesson._meta.get_field("status").default == "draft"
    assert Lesson._meta.get_field("authorship").default == "ai_drafted"


def test_an_exercise_saved_with_a_bad_scoring_shape_is_refused(content):
    ex = content["ex1"]
    ex.scoring_params = {"beats": [9]}
    with pytest.raises(ValidationError) as caught:
        ex.full_clean()
    assert "scoring_params" in caught.value.message_dict


def test_an_exercise_cannot_ask_for_more_bars_than_it_has_pass_score_or_xp_outside_range(content):
    ex = content["ex1"]
    for field, value in (("pass_score", 101), ("pass_score", -1), ("xp", -5), ("bars", 0), ("tempo", 10)):
        before = getattr(ex, field)
        setattr(ex, field, value)
        with pytest.raises(ValidationError) as caught:
            ex.full_clean()
        assert field in caught.value.message_dict, field
        setattr(ex, field, before)
    ex.full_clean()


def test_a_phrase_row_with_notes_off_the_beat_grid_is_refused(content):
    phrase = content["phrase"]
    phrase.notes = [{"midi": 62, "beat": 0, "length": 1}]
    with pytest.raises(ValidationError) as caught:
        phrase.full_clean()
    assert "notes" in caught.value.message_dict


def test_a_take_may_name_the_exercise_it_was_played_for(content):
    assert Take._meta.get_field("exercise").null is True
    assert Take._meta.get_field("exercise").remote_field.model is Exercise


# ----------------------------------------------------------------- lessons over the API


def test_a_member_sees_published_lessons_in_track_order_and_not_the_draft(people, content):
    body = _client(people["member"]).get(f"{API}lessons/").json()
    assert [row["slug"] for row in body] == ["chord-tones-ii-v-i", "guide-tones"]


def test_the_superuser_who_reads_the_lessons_before_they_are_published_sees_the_draft_too(people, content):
    body = _client(people["admin"]).get(f"{API}lessons/").json()
    assert "draft-lesson" in [row["slug"] for row in body]


def test_a_draft_lesson_does_not_exist_for_a_member_by_id_either(people, content):
    assert _client(people["member"]).get(f"{API}lessons/{content['draft'].pk}/").status_code == 404
    assert _client(people["admin"]).get(f"{API}lessons/{content['draft'].pk}/").status_code == 200


def test_a_lesson_carries_what_the_page_needs_to_teach_it(people, content):
    row = next(r for r in _client(people["member"]).get(f"{API}lessons/").json() if r["slug"] == "chord-tones-ii-v-i")
    assert row["track"] == "chord_tones" and row["order"] == 1 and row["level"] == 1
    assert row["explanation"].startswith("## Why")
    assert row["demo_phrase"] == content["phrase"].pk
    assert row["progression"] == content["iivi"].pk
    assert row["prerequisite"] is None
    assert row["exercises"] == ["chord-tones-beats-1-3", "chord-tones-every-beat"]
    assert row["authorship"] == "ai_drafted" and row["status"] == "published"
    second = next(r for r in _client(people["member"]).get(f"{API}lessons/").json() if r["slug"] == "guide-tones")
    assert second["prerequisite"] == "chord-tones-ii-v-i"


def test_lessons_filter_by_track(people, content):
    body = _client(people["member"]).get(f"{API}lessons/", {"track": "guide_tones"}).json()
    assert [row["slug"] for row in body] == ["guide-tones"]
    assert _client(people["member"]).get(f"{API}lessons/", {"track": "nonsense"}).json() == []


@pytest.mark.parametrize("who", ["member", "admin"])
def test_lessons_exercises_and_presets_cannot_be_written_through_the_api(people, content, who):
    client = _client(people[who])
    for path in ("lessons", "exercises"):
        assert _json(client, "post", f"{API}{path}/", {"title": "x"}).status_code == 405, path
        for method in ("put", "patch", "delete"):
            url = f"{API}{path}/{content['first'].pk if path == 'lessons' else content['ex1'].pk}/"
            assert _json(client, method, url, {"title": "x"}).status_code == 405, f"{method} {url}"
    assert Lesson.objects.get(pk=content["first"].pk).title == "Chord tones over a ii-V-I"


# --------------------------------------------------------------- exercises over the API


def test_an_exercise_carries_the_whole_task(people, content):
    rows = _client(people["member"]).get(f"{API}exercises/", {"lesson": "chord-tones-ii-v-i"}).json()
    assert [r["slug"] for r in rows] == ["chord-tones-beats-1-3", "chord-tones-every-beat"]
    first = rows[0]
    assert first["lesson"] == "chord-tones-ii-v-i"
    assert first["progression"] == content["iivi"].pk and first["progression_slug"] == "ii-v-i-major"
    assert first["key"] == "C" and first["tempo"] == 90 and first["bars"] == 4
    assert first["scoring_kind"] == "chord_tones_on_beats" and first["scoring_params"] == {"beats": [1, 3]}
    assert first["pass_score"] == 80 and first["xp"] == 20 and first["daily_eligible"] is False


def test_the_exercises_of_a_draft_lesson_are_hidden_from_a_member(people, content):
    slugs = [r["slug"] for r in _client(people["member"]).get(f"{API}exercises/").json()]
    assert "draft-exercise" not in slugs
    assert {"chord-tones-beats-1-3", "chord-tones-every-beat", "approach-challenge"} <= set(slugs)
    admin_slugs = [r["slug"] for r in _client(people["admin"]).get(f"{API}exercises/").json()]
    assert "draft-exercise" in admin_slugs


def test_a_challenge_is_an_exercise_with_no_lesson(people, content):
    rows = _client(people["member"]).get(f"{API}exercises/", {"challenge": "1"}).json()
    assert [r["slug"] for r in rows] == ["approach-challenge"]
    assert rows[0]["lesson"] is None


def test_exercises_filter_to_the_ones_the_daily_workout_may_pick(people, content):
    rows = _client(people["member"]).get(f"{API}exercises/", {"daily": "1"}).json()
    assert [r["slug"] for r in rows] == ["approach-challenge"]


def test_an_unknown_lesson_filter_is_an_empty_list(people, content):
    assert _client(people["member"]).get(f"{API}exercises/", {"lesson": "no-such"}).json() == []


# ----------------------------------------------------------------------------- phrases


def _phrase_body(**changes):
    body = {"name": "My lick", "kind": "lick", "notes": NOTES, "length_beats": 4, "chart_context": "", "written_in_key": "C"}
    body.update(changes)
    return body


def test_a_player_can_make_change_and_delete_their_own_phrase(people, content):
    client = _client(people["member"])
    made = _json(client, "post", f"{API}phrases/", _phrase_body())
    assert made.status_code == 201, made.content
    row = made.json()
    assert row["is_preset"] is False and row["is_mine"] is True and row["slug"] == "my-lick"
    assert Phrase.objects.get(pk=row["id"]).owner == people["member"]
    changed = _json(client, "patch", f"{API}phrases/{row['id']}/", {"name": "My lick, again"})
    assert changed.status_code == 200 and changed.json()["name"] == "My lick, again"
    assert _json(client, "delete", f"{API}phrases/{row['id']}/").status_code == 204


def test_a_preset_phrase_is_read_only_and_another_players_phrase_does_not_exist(people, content):
    client = _client(people["member"])
    preset = content["phrase"]
    assert _json(client, "patch", f"{API}phrases/{preset.pk}/", {"name": "x"}).status_code == 403
    mine = _json(client, "post", f"{API}phrases/", _phrase_body()).json()
    other = _client(people["other"])
    assert other.get(f"{API}phrases/{mine['id']}/").status_code == 404
    assert mine["id"] not in [r["id"] for r in other.get(f"{API}phrases/").json()]
    assert preset.pk in [r["id"] for r in other.get(f"{API}phrases/").json()]


def test_a_phrase_with_bad_notes_is_refused_by_the_api(people, content):
    client = _client(people["member"])
    reply = _json(client, "post", f"{API}phrases/", _phrase_body(notes=[{"midi": 999, "beat": 0, "length": 1, "velocity": 90}]))
    assert reply.status_code == 400 and "notes" in reply.json()
    assert _json(client, "post", f"{API}phrases/", _phrase_body(length_beats=0)).status_code == 400


def test_phrases_filter_by_kind(people, content):
    client = _client(people["member"])
    _json(client, "post", f"{API}phrases/", _phrase_body())
    kinds = {r["kind"] for r in client.get(f"{API}phrases/", {"kind": "lick"}).json()}
    assert kinds == {"lick"}


# -------------------------------------------------------------- a take for an exercise


def _take_body(session_id, content, **changes):
    iivi = content["iivi"]
    body = {
        "session": session_id, "progression": iivi.pk, "style": iivi.default_style_id, "chart": iivi.chart,
        "home_key": iivi.home_key, "key": "C", "time_signature": "4/4", "tempo": 90, "swing_ratio": "0.67",
        "loop_from": 0, "loop_to": 4, "started_at": timezone.now().isoformat(), "duration_ms": 10000, "bars": 4,
        "events": [{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 300, "type": "off", "note": 62, "velocity": 0}],
        "score": 90, "metrics": {"notes": 1}, "judge_version": 1,
    }
    body.update(changes)
    return body


def test_a_take_names_the_exercise_by_slug_and_gives_it_back_that_way(people, content):
    client = _client(people["member"])
    session = _json(client, "post", f"{API}sessions/").json()
    made = _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="chord-tones-beats-1-3"))
    assert made.status_code == 201, made.content
    assert made.json()["exercise"] == "chord-tones-beats-1-3"
    assert Take.objects.get(pk=made.json()["id"]).exercise == content["ex1"]
    plain = _json(client, "post", f"{API}takes/", _take_body(session["id"], content))
    assert plain.json()["exercise"] is None


def test_a_take_cannot_name_a_draft_lessons_exercise_or_one_that_does_not_exist(people, content):
    client = _client(people["member"])
    session = _json(client, "post", f"{API}sessions/").json()
    assert _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="draft-exercise")).status_code == 400
    assert _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="nope")).status_code == 400
    admin = _client(people["admin"])
    admin_session = _json(admin, "post", f"{API}sessions/").json()
    assert _json(admin, "post", f"{API}takes/", _take_body(admin_session["id"], content, exercise="draft-exercise")).status_code == 201


def test_a_take_cannot_be_moved_to_another_exercise_after_it_is_posted(people, content):
    client = _client(people["member"])
    session = _json(client, "post", f"{API}sessions/").json()
    take = _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="chord-tones-beats-1-3")).json()
    assert _json(client, "patch", f"{API}takes/{take['id']}/", {"exercise": "chord-tones-every-beat"}).status_code == 403


def test_takes_filter_by_exercise(people, content):
    client = _client(people["member"])
    session = _json(client, "post", f"{API}sessions/").json()
    _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="chord-tones-beats-1-3"))
    _json(client, "post", f"{API}takes/", _take_body(session["id"], content))
    rows = client.get(f"{API}takes/", {"exercise": "chord-tones-beats-1-3"}).json()
    assert len(rows) == 1 and rows[0]["exercise"] == "chord-tones-beats-1-3"


def test_deleting_an_exercise_keeps_the_takes_played_for_it(people, content):
    client = _client(people["member"])
    session = _json(client, "post", f"{API}sessions/").json()
    take = _json(client, "post", f"{API}takes/", _take_body(session["id"], content, exercise="chord-tones-beats-1-3")).json()
    content["ex1"].delete()
    assert Take.objects.get(pk=take["id"]).exercise is None


# ------------------------------------------------------------------------------- pages


def test_the_lessons_page_and_a_lesson_page_open_for_anyone_signed_in_and_send_a_visitor_to_the_front_door(people, content):
    for url in ("/improv/lessons/", "/improv/lessons/chord-tones-ii-v-i/"):
        assert _client(people["member"]).get(url).status_code == 200, url
        assert _client(people["stranger"]).get(url).status_code == 200, url
        visitor = _client(None).get(url)
        assert visitor.status_code == 302, url
        assert visitor.headers["Location"].startswith("/improv/?next="), url


def test_the_menu_leads_to_the_lessons(people):
    html = _client(people["member"]).get("/improv/lessons/").content.decode()
    nav = re.search(r'<nav class="im-nav".*?</nav>', html, re.S).group(0)
    assert 'href="/improv/lessons/"' in nav


def test_the_lesson_page_says_where_its_data_comes_from_and_the_three_steps(people, content):
    html = _client(people["member"]).get("/improv/lessons/chord-tones-ii-v-i/").content.decode()
    for needle in ('data-lesson="chord-tones-ii-v-i"', 'data-api-lessons="/improv/api/lessons/"', 'data-api-exercises="/improv/api/exercises/"', 'data-api-phrases="/improv/api/phrases/"'):
        assert needle in html, needle
    for step in ("Read", "Hear", "Play"):
        assert f". {step}<" in html, step


def test_the_play_page_knows_the_exercises_endpoint(people):
    html = _client(people["member"]).get("/improv/play/").content.decode()
    assert 'data-api-exercises="/improv/api/exercises/"' in html


# ------------------------------------------------------------------ the logic and the discipline

STATIC = Path("static/improv")
LESSONS_JS = STATIC / "lessons.js"
PAGE_SCRIPTS = (STATIC / "lessons.js", STATIC / "lessons-page.js", STATIC / "lesson-page.js")


def test_the_lessons_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri51.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


def test_the_lesson_pages_build_their_screens_without_html_injection():
    for path in PAGE_SCRIPTS:
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_lessons_logic_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LESSONS_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"lessons.js reaches for {forbidden}"


def _scripts(html):
    return [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html) if Path(src).name not in ("control.js", "control-page.js")]


def test_each_lesson_page_loads_its_scripts_in_dependency_order(people, content):
    lessons = _scripts(_client(people["member"]).get("/improv/lessons/").content.decode())
    assert lessons == ["chart.js", "band.js", "lessons.js", "lessons-page.js"]
    one = _scripts(_client(people["member"]).get("/improv/lessons/chord-tones-ii-v-i/").content.decode())
    assert one == ["chart.js", "band.js", "scheduler.js", "synth.js", "chart-view.js", "play.js", "midi.js", "setup.js", "timing.js", "lessons.js", "lesson-page.js"]


def test_the_lesson_pages_link_nowhere_outside_the_app(people, content):
    for url in ("/improv/lessons/", "/improv/lessons/chord-tones-ii-v-i/"):
        html = _client(people["member"]).get(url).content.decode("utf-8")
        for href in re.findall(r'(?:href|src)="([^"]+)"', html):
            assert href.startswith(("/improv/", "/static/")), f"{url} points at {href}"
        assert "http://" not in html and "https://" not in html


def test_the_lesson_page_hear_step_sends_the_demo_by_the_players_chosen_output():
    page = (STATIC / "lesson-page.js").read_text(encoding="utf-8")
    assert 'demo_output !== "piano"' in page
    assert "Timing.heardAt(anchor, n.when)" in page
    assert 'voice: "demo"' in page
    stop = page.split("function stopHear()")[1].split("\n  }\n")[0]
    assert "noteOffBytes" in stop, "a stopped demo must not leave a key held on the piano"


def test_play_page_counts_a_take_for_an_exercise_only_while_the_loop_matches():
    page = (STATIC / "play-page.js").read_text(encoding="utf-8")
    assert "P.exerciseApplies(" in page and "P.exerciseVerdict(" in page and "P.exerciseScoring(" in page
    assert "?exercise=" in page or '"exercise"' in page


# ------------------------------------------------------------------------------- docs


def test_the_api_doc_and_the_data_model_say_what_was_built():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    for path in ("/improv/api/lessons/", "/improv/api/exercises/", "/improv/api/phrases/"):
        assert path in api, path
    data_model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "Added after approval, SPR-I.5.1" in data_model
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.5\.1 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)
