"""SPR-I.10.2 improv: the curriculum. Twenty lessons in three levels, beginner to intermediate, and a seed
that keeps drafts up to date.

Avi, 2026-10-09: "build the lessons, not randomly, like real logic behind the progress. Maybe build 20
lessons." Each lesson is one idea with three exercises that get harder; the path interleaves the tracks so
no two lessons of one kind come in a row; every exercise is passed by a model player through the real judge
(tests/js/spri53.test.js). The seed adds what is missing and, with --refresh-drafts, brings every lesson
still drafted by AI up to date with the file; a lesson Avi has read or written is never touched, and
nothing is ever deleted.

Traces: spec ch. 6 "The path", data model section 6, backlog SPR-I.10.2.
"""

import io
import json
import re
from pathlib import Path

import pytest
from django.core.management import call_command

from improv import progress
from improv.models import Completion, Exercise, Lesson, Phrase, Player
from improv.teaching import TRACK_ORDER
from django.contrib.auth.models import User

pytestmark = [pytest.mark.spri102, pytest.mark.django_db]

SEED = Path("improv/seed_data/lessons.json")
ORIGINAL_SIX = (
    "chord-tones-on-the-beat", "guide-tones-thirds-and-sevenths", "scales-that-fit-the-chord",
    "approach-notes", "rhythm-motifs", "call-and-response",
)
ORIGINAL_EXERCISES = (
    "chord-tones-beat-one", "chord-tones-beats-one-and-three", "chord-tones-every-beat",
    "guide-tones-find-them", "guide-tones-connect-the-changes", "guide-tones-turnaround",
    "scales-stay-in-the-scale", "scales-dorian-groove", "scales-turnaround",
    "approach-notes-beat-one", "approach-notes-beats-one-and-three", "approach-notes-turnaround",
    "rhythm-half-notes", "rhythm-charleston", "rhythm-offbeats",
    "call-response-echo-the-rhythm", "call-response-answer-a-skip", "call-response-same-notes",
)


def _seed(*flags):
    out = io.StringIO()
    call_command("seed_improv_lessons", *flags, stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(db):
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    _seed()


def _path():
    return sorted(Lesson.objects.all(), key=progress.path_key)


# ------------------------------------------------------------------ the shape of the course


def test_twenty_lessons_in_three_levels_with_three_exercises_each(seeded):
    assert Lesson.objects.count() == 20
    assert Exercise.objects.filter(lesson__isnull=False).count() == 60
    for lesson in Lesson.objects.all():
        assert lesson.exercises.count() == 3, lesson.slug
        assert lesson.status == "published" and lesson.authorship == "ai_drafted", lesson.slug
    by_level = {level: Lesson.objects.filter(level=level).count() for level in (1, 2, 3)}
    assert by_level == {1: 7, 2: 7, 3: 6}


def test_every_scored_track_has_at_least_three_lessons(seeded):
    for track in TRACK_ORDER[:-1]:
        assert Lesson.objects.filter(track=track).count() >= 3, track


def test_the_path_is_numbered_one_to_twenty_and_climbs_through_the_levels(seeded):
    path = _path()
    assert [lesson.path_order for lesson in path] == list(range(1, 21))
    levels = [lesson.level for lesson in path]
    assert levels == sorted(levels), "level 1 before level 2 before level 3"


def test_no_two_lessons_of_one_track_come_in_a_row(seeded):
    tracks = [lesson.track for lesson in _path()]
    assert all(a != b for a, b in zip(tracks, tracks[1:])), tracks


def test_every_prerequisite_comes_earlier_in_the_path_and_the_path_has_one_start(seeded):
    path = _path()
    position = {lesson.pk: i for i, lesson in enumerate(path)}
    roots = [lesson for lesson in path if lesson.prerequisite_id is None]
    assert [lesson.slug for lesson in roots] == ["chord-tones-on-the-beat"]
    for lesson in path:
        if lesson.prerequisite_id:
            assert position[lesson.prerequisite_id] < position[lesson.pk], lesson.slug


def test_a_new_player_sees_one_open_lesson_and_the_rest_ahead_until_they_choose(seeded):
    player = Player.objects.create(user=User.objects.create_user("p102fresh"))
    states = progress.lesson_states(player)
    slugs = dict(Lesson.objects.values_list("id", "slug"))
    assert [slugs[pk] for pk, row in states.items() if row["state"] == "open"] == ["chord-tones-on-the-beat"]
    assert {row["state"] for row in states.values()} == {"open", "ahead"}
    progress.move_to(player, Lesson.objects.get(slug="scales-minor-two-five-one"))
    states = progress.lesson_states(player)
    assert sum(1 for row in states.values() if row["state"] == "open") == 16, "the pointer at lesson 16 opens all sixteen"


# ------------------------------------------------------------------ the exercises make sense


def test_within_a_lesson_the_exercises_get_harder(seeded):
    for lesson in Lesson.objects.prefetch_related("exercises"):
        rows = sorted(lesson.exercises.all(), key=lambda e: e.order)
        tempos = [e.tempo for e in rows]
        xps = [e.xp for e in rows]
        assert tempos == sorted(tempos) or lesson.track == "call_and_response", f"{lesson.slug}: {tempos}"
        assert xps == sorted(xps) and xps[0] < xps[-1], f"{lesson.slug}: {xps}"
        assert [e.daily_eligible for e in rows] == [True, True, False], f"{lesson.slug}: the hardest is never a workout pick"


def test_the_levels_climb_in_tempo_and_reward(seeded):
    def tempos(level):
        return [e.tempo for e in Exercise.objects.filter(lesson__level=level)]

    def xps(level):
        return [e.xp for e in Exercise.objects.filter(lesson__level=level)]

    assert max(tempos(1)) <= 90 and min(tempos(3)) >= 80
    assert max(xps(1)) < min(xps(3))
    assert sum(xps(1)) < sum(xps(2)) < sum(xps(3))


def test_every_exercise_is_in_its_charts_own_key_and_within_its_chart(seeded):
    for ex in Exercise.objects.select_related("progression"):
        assert ex.key == ex.progression.home_key, ex.slug
        bars = len([c for c in ex.progression.chart.split("|") if c.strip()])
        assert ex.bars <= bars, f"{ex.slug} asks for {ex.bars} bars of a {bars}-bar chart"
        ex.full_clean()


def test_the_whole_course_is_worth_a_handful_of_levels(seeded):
    total = sum(Exercise.objects.values_list("xp", flat=True))
    assert 6 <= progress.level_for(total) <= 10, total


def test_every_lesson_has_its_own_demo_inside_its_own_chart(seeded):
    seen = set()
    for lesson in Lesson.objects.select_related("demo_phrase", "progression"):
        phrase = lesson.demo_phrase
        assert phrase is not None and phrase.slug not in seen, lesson.slug
        seen.add(phrase.slug)
        chord_names = set(re.findall(r"[A-G][#b]?[A-Za-z0-9#]*", phrase.chart_context))
        chart_names = set(re.findall(r"[A-G][#b]?[A-Za-z0-9#]*", lesson.progression.chart))
        assert chord_names <= chart_names, f"{lesson.slug}: the demo names chords that are not in its chart"


def test_the_words_are_plain_and_every_lesson_reads_hears_and_plays(seeded):
    data = json.loads(SEED.read_text(encoding="utf-8"))
    for lesson in data["lessons"]:
        for heading in ("## Read", "## Hear", "## Play"):
            assert heading in lesson["explanation"], lesson["slug"]
        texts = [lesson["title"], lesson["summary"], lesson["explanation"]] + [t for ex in lesson["exercises"] for t in (ex["title"], ex["instructions"])]
        for text in texts:
            assert chr(0x2014) not in text and chr(0x2013) not in text, lesson["slug"]
            assert not re.search(r"[\U0001F300-\U0001FAFF]", text), lesson["slug"]
        assert 500 <= len(lesson["explanation"]) <= 1400, f"{lesson['slug']}: a screen or less, and not a tweet"


# ------------------------------------------------------------------ the seed and its refresh


def test_the_original_six_keep_their_slugs_so_nobody_loses_what_they_passed(seeded):
    for slug in ORIGINAL_SIX:
        assert Lesson.objects.filter(slug=slug).exists(), slug
    for slug in ORIGINAL_EXERCISES:
        assert Exercise.objects.filter(slug=slug).exists(), slug


def test_the_command_reports_what_it_added_then_nothing(db):
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    first = _seed()
    assert "improv lessons: added 100 (20 phrases, 20 lessons, 60 exercises)." in first, first
    assert "improv lessons: added 0" in _seed()
    assert (Phrase.objects.count(), Lesson.objects.count(), Exercise.objects.count()) == (20, 20, 60)


def test_refresh_brings_a_draft_back_to_the_file_and_leaves_a_read_lesson_alone(seeded):
    draft = Lesson.objects.get(slug="rhythm-motifs")
    Lesson.objects.filter(pk=draft.pk).update(explanation="An older draft.", summary="old")
    Exercise.objects.filter(slug="rhythm-charleston").update(tempo=55, pass_score=99)
    Phrase.objects.filter(slug="demo-rhythm-motif").update(name="old name")

    read = Lesson.objects.get(slug="call-and-response")
    Lesson.objects.filter(pk=read.pk).update(explanation="Avi rewrote this.", authorship="reviewed")
    Exercise.objects.filter(slug="call-response-same-notes").update(xp=99)

    out = _seed("--refresh-drafts")
    assert "Refreshed 3 (1 phrases, 1 lessons, 1 exercises)." in out, out
    draft.refresh_from_db()
    assert "## Read" in draft.explanation and draft.summary != "old"
    charleston = Exercise.objects.get(slug="rhythm-charleston")
    assert (charleston.tempo, charleston.pass_score) == (80, 70)
    assert Phrase.objects.get(slug="demo-rhythm-motif").name == "One rhythm, every bar"
    read.refresh_from_db()
    assert (read.explanation, read.authorship) == ("Avi rewrote this.", "reviewed")
    assert Exercise.objects.get(slug="call-response-same-notes").xp == 99


def test_without_the_flag_nothing_that_exists_is_touched(seeded):
    Lesson.objects.filter(slug="rhythm-motifs").update(explanation="An older draft.")
    _seed()
    assert Lesson.objects.get(slug="rhythm-motifs").explanation == "An older draft."


def test_refresh_never_deletes_an_exercise_or_a_completion(seeded):
    lesson = Lesson.objects.get(slug="rhythm-motifs")
    extra = Exercise.objects.create(
        lesson=lesson, order=4, slug="rhythm-extra", title="Extra", instructions="i", progression=lesson.progression, key="C",
        tempo=80, bars=4, scoring_kind="rhythm_motif", scoring_params={"pattern": [0]}, pass_score=70, xp=5,
    )
    player = Player.objects.create(user=User.objects.create_user("p102keeps"))
    Completion.objects.create(player=player, exercise=extra, xp_awarded=5)
    Completion.objects.create(player=player, exercise=Exercise.objects.get(slug="rhythm-charleston"), xp_awarded=15)
    _seed("--refresh-drafts")
    assert Exercise.objects.filter(slug="rhythm-extra").exists()
    assert Completion.objects.filter(player=player).count() == 2
    assert progress.total_xp(player) == 20


def test_the_path_position_is_kept_right_even_for_a_lesson_avi_has_read(seeded):
    Lesson.objects.filter(slug="call-and-response").update(authorship="avi_written", path_order=None)
    _seed()
    assert Lesson.objects.get(slug="call-and-response").path_order == 6


def test_a_lesson_someone_deleted_comes_back_in_its_place(seeded):
    Lesson.objects.get(slug="rhythm-motifs-funk").delete()
    out = _seed()
    assert "added 4 (0 phrases, 1 lessons, 3 exercises)" in out, out
    assert Lesson.objects.get(slug="rhythm-motifs-funk").path_order == 18


def test_the_deploy_refreshes_drafts():
    assert "seed_improv_lessons --refresh-drafts" in Path("render.yaml").read_text(encoding="utf-8")


def test_the_docs_describe_the_course_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "twenty lessons" in spec.lower() or "20 lessons" in spec
    assert "--refresh-drafts" in spec or "--refresh-drafts" in Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.10\.2 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)
