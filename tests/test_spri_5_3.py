"""SPR-I.5.3 improv: the first lessons, seeded.

Six lessons, one per scored track, with their demo phrases and eighteen exercises, drafted by AI
and honestly labelled so. The seed is a one-time import (Rule 1): it adds what is missing by slug
and never touches a row that exists, so running it on every deploy cannot undo an edit. The node
file proves the exercises can be passed with the real judge; this file proves the rows are sound.

Traces: spec ch. 6 (the first curriculum), data model section 6, backlog SPR-I.5.3.
"""

import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv import progress
from improv.models import Exercise, Lesson, Phrase, Player, Progression
from improv.teaching import TRACK_ORDER, check_notes, check_scoring

pytestmark = pytest.mark.spri53

SEED = Path("improv/seed_data/lessons.json")
API = "/improv/api/"
PASSWORD = "spri53-pass-9930"


def _seed():
    out = io.StringIO()
    call_command("seed_improv_lessons", stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(db):
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    _seed()


@pytest.fixture
def player(seeded):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p53player", password=PASSWORD)
    user.groups.add(group)
    client = Client()
    client.force_login(user)
    return user, client


# ------------------------------------------------------------------- what the seed holds


def test_the_seed_adds_six_lessons_one_for_each_scored_track(seeded):
    tracks = list(Lesson.objects.order_by("track").values_list("track", flat=True))
    assert Lesson.objects.count() == 6
    assert sorted(tracks) == sorted(set(tracks)), "one lesson to a track"
    assert set(tracks) <= set(TRACK_ORDER)
    assert "voicings_comping" not in tracks, "that kind is not scored in version 1, so there is nothing to teach it with yet"


def test_every_lesson_is_published_and_says_it_has_not_been_read(seeded):
    for lesson in Lesson.objects.all():
        assert lesson.status == "published", lesson.slug
        assert lesson.authorship == "ai_drafted", f"{lesson.slug} must not claim a person wrote or read it"


def test_every_lesson_reads_hears_and_plays(seeded):
    for lesson in Lesson.objects.all():
        for heading in ("## Read", "## Hear", "## Play"):
            assert heading in lesson.explanation, f"{lesson.slug} has no {heading}"
        assert lesson.demo_phrase_id, f"{lesson.slug} has nothing to Hear"
        assert lesson.progression_id and lesson.style_id, f"{lesson.slug} has no band to Hear it over"
        assert lesson.exercises.count() >= 2, f"{lesson.slug} has little to Play"
        lesson.full_clean()


def test_the_exercises_number_between_ten_and_twenty(seeded):
    assert 10 <= Exercise.objects.count() <= 20


def test_every_exercise_passes_the_same_check_as_a_saved_one(seeded):
    for ex in Exercise.objects.select_related("progression"):
        ex.full_clean()
        assert ex.lesson_id, "a seeded exercise belongs to a lesson"
        assert 1 <= ex.xp <= 100 and 40 <= ex.pass_score <= 100, ex.slug
        assert ex.key == ex.progression.home_key, f"{ex.slug}: the exercise is set in the chart's own key"


def test_an_exercise_asks_for_no_more_than_its_chart_has(seeded):
    for ex in Exercise.objects.select_related("progression"):
        bars = len([c for c in ex.progression.chart.split("|") if c.strip()])
        assert ex.bars <= bars, f"{ex.slug} asks for {ex.bars} bars of a {bars}-bar chart"
        params = ex.scoring_params
        if ex.scoring_kind == "call_and_response":
            assert params["answerBar"] < ex.bars
        assert check_scoring(ex.scoring_kind, params, beats_per_bar=4, bars=ex.bars) is None


def test_a_rhythm_motif_is_taught_on_a_straight_groove(seeded):
    for ex in Exercise.objects.filter(scoring_kind="rhythm_motif").select_related("style", "progression__default_style"):
        style = ex.style or ex.progression.default_style
        assert float(style.swing_ratio) == 0.5, f"{ex.slug}: the judge expects straight beats for a rhythm motif"


def test_every_demo_phrase_is_a_valid_phrase_inside_its_lesson_chart(seeded):
    for lesson in Lesson.objects.select_related("demo_phrase", "progression"):
        phrase = lesson.demo_phrase
        assert phrase.is_preset and phrase.owner_id is None and phrase.kind == "demo"
        assert check_notes(phrase.notes, phrase.length_beats) is None
        phrase.full_clean()
        bars = len([c for c in lesson.progression.chart.split("|") if c.strip()])
        assert float(phrase.length_beats) <= bars * 4, f"{lesson.slug}: the phrase outlasts the chart"
        assert phrase.chart_context.strip(), f"{lesson.slug}: say what chords the phrase goes over"
        assert {n["velocity"] for n in phrase.notes}, "the seed gives every note a velocity"


def test_the_prerequisites_form_a_path_with_a_start_and_no_loop(seeded):
    by_slug = {lesson.slug: lesson for lesson in Lesson.objects.all()}
    roots = [lesson for lesson in by_slug.values() if lesson.prerequisite_id is None]
    assert len(roots) == 1, "the player starts in one place"
    for lesson in by_slug.values():
        seen, here = set(), lesson
        while here.prerequisite_id:
            assert here.pk not in seen, f"{lesson.slug} loops"
            seen.add(here.pk)
            here = by_slug[here.prerequisite.slug]
        assert here.pk == roots[0].pk, f"{lesson.slug} does not lead back to the first lesson"


def test_a_new_player_can_start_one_lesson_and_the_rest_wait(seeded):
    user = Player.objects.create(user=User.objects.create_user("p53fresh"))
    slugs = dict(Lesson.objects.values_list("id", "slug"))
    states = {slugs[pk]: row["state"] for pk, row in progress.lesson_states(user).items()}
    assert [slug for slug, state in states.items() if state == "open"] == ["chord-tones-on-the-beat"]
    assert set(states.values()) == {"open", "locked"}


def test_the_level_and_the_xp_of_the_whole_course_are_reachable(seeded):
    total = sum(Exercise.objects.values_list("xp", flat=True))
    assert progress.level_for(total) >= 3, "finishing everything should be worth a few levels"
    assert progress.level_for(total) < 10, "and not a hundred"


def test_every_authored_text_is_plain(seeded):
    texts = [seed for seed in _seed_texts()]
    for text in texts:
        assert chr(0x2014) not in text and chr(0x2013) not in text, "no em or en dashes in teaching text"
        assert not re.search(r"[\U0001F300-\U0001FAFF]", text), "no emojis"


def _seed_texts():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    for lesson in data["lessons"]:
        yield lesson["title"]
        yield lesson["summary"]
        yield lesson["explanation"]
        for ex in lesson["exercises"]:
            yield ex["title"]
            yield ex["instructions"]
    for phrase in data["phrases"]:
        yield phrase["name"]


# ------------------------------------------------------------------- the command


def test_the_command_reports_what_it_added_then_nothing(db):
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    first = _seed()
    assert re.search(r"improv lessons: added 30 \(6 phrases, 6 lessons, 18 exercises\)\.", first), first
    second = _seed()
    assert "improv lessons: added 0" in second
    assert (Phrase.objects.count(), Lesson.objects.count(), Exercise.objects.count()) == (6, 6, 18)


def test_running_it_again_never_undoes_an_edit(seeded):
    lesson = Lesson.objects.get(slug="rhythm-motifs")
    lesson.explanation = "Avi rewrote this."
    lesson.authorship = "avi_written"
    lesson.save()
    ex = Exercise.objects.get(slug="rhythm-charleston")
    ex.xp = 99
    ex.save()
    phrase = Phrase.objects.get(slug="demo-rhythm-motif")
    phrase.name = "My own name"
    phrase.save()
    _seed()
    lesson.refresh_from_db()
    assert (lesson.explanation, lesson.authorship) == ("Avi rewrote this.", "avi_written")
    assert Exercise.objects.get(slug="rhythm-charleston").xp == 99
    assert Phrase.objects.get(slug="demo-rhythm-motif").name == "My own name"


def test_it_fills_in_what_was_deleted_and_leaves_the_rest(seeded):
    Exercise.objects.get(slug="rhythm-offbeats").delete()
    out = _seed()
    assert "added 1 (0 phrases, 0 lessons, 1 exercises)" in out, out
    assert Exercise.objects.count() == 18


def test_it_is_all_or_nothing(db):
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    Progression.objects.get(slug="fifties-changes").delete()
    with pytest.raises(Exception):
        _seed()
    assert (Phrase.objects.count(), Lesson.objects.count(), Exercise.objects.count()) == (0, 0, 0), "a half-seeded course is worse than none"


def test_the_command_needs_the_library_and_says_so(db):
    with pytest.raises(Exception, match="seed_improv_library"):
        _seed()


# ------------------------------------------------------------------- through the API


def test_the_seeded_lessons_arrive_through_the_api_in_the_order_a_player_meets_them(player):
    user, client = player
    got = client.get(f"{API}lessons/")
    assert got.status_code == 200
    body = got.json()
    rows = body["lessons"] if isinstance(body, dict) else body
    tracks = [row["track"] for row in rows]
    assert tracks == [t for t in TRACK_ORDER if t in tracks], "tracks come in the order a player meets them"
    assert {row["slug"]: row["state"] for row in rows}["chord-tones-on-the-beat"] == "open"
    assert {row["slug"]: row["state"] for row in rows}["call-and-response"] == "locked"


def test_the_exercises_and_phrases_are_in_the_api(player):
    _, client = player
    exercises = client.get(f"{API}exercises/").json()
    phrases = client.get(f"{API}phrases/").json()
    assert len(exercises) == 18 and len(phrases) == 6
    assert all(e["lesson"] for e in exercises)
    assert {e["scoring_kind"] for e in exercises} == {
        "chord_tones_on_beats", "guide_tones", "scale_only", "approach_notes", "rhythm_motif", "call_and_response",
    }  # fmt: skip


def test_an_outsider_sees_none_of_it(seeded):
    stranger = User.objects.create_user("p53stranger", password=PASSWORD)
    client = Client()
    client.force_login(stranger)
    for path in ("lessons/", "exercises/", "phrases/"):
        assert client.get(f"{API}{path}").status_code == 404, path
    assert client.get("/improv/lessons/chord-tones-on-the-beat/").status_code == 404


def test_the_first_lesson_page_opens_for_a_player(player):
    _, client = player
    page = client.get("/improv/lessons/chord-tones-on-the-beat/")
    assert page.status_code == 200
    assert b"Chord tones on the beat" in page.content or b"lesson-title" in page.content


# ------------------------------------------------------------------- docs, backlog, node


def test_the_docs_say_the_lessons_are_ai_drafted_and_how_to_seed_them():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "seed_improv_lessons" in api and "seed_improv_lessons" in model
    assert "ai_drafted" in model
    assert "lessons.json" in spec or "lessons.json" in model
    assert re.search(r"read the .*lessons|read each lesson|before .*taught", model + api + spec, re.IGNORECASE)


def test_the_backlog_marks_the_sprint_done():
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.5\.3 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)


def test_the_seeded_exercises_can_be_passed_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri53.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]
