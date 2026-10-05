"""SPR-I.5.6 improv: the weakness report, standalone challenges and personal bests.

The weakness report is a read over the last thirty days of takes. It says nothing about a bucket
until there are twenty notes behind it, names at most three things, and gives each an exercise
that works on it. Personal bests are a read too: the best take per exercise. Challenges are
exercises with no lesson, seeded by their own command.

Traces: spec ch. 6 (the weakness report, challenges and takes), features 17 and 19, backlog SPR-I.5.6.
"""

import datetime as dt
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv import bests, weakness, workout
from improv.models import Completion, Exercise, Lesson, Player, PracticeSession, Progression, Take
from improv.teaching import check_scoring

pytestmark = pytest.mark.spri56

PASSWORD = "spri56-pass-3318"
API = "/improv/api/"
ZONE = ZoneInfo("Asia/Jerusalem")
NOW = dt.datetime(2026, 10, 5, 12, 0, tzinfo=ZONE)
TODAY = NOW.date()
SEED = Path("improv/seed_data/challenges.json")


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p56member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p56other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p56stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "other": other, "stranger": stranger}


@pytest.fixture
def path(people):
    iivi = Progression.objects.get(slug="ii-v-i-major")

    def lesson(track, slug, **more):
        return Lesson.objects.create(
            track=track, order=1, title=slug.title(), slug=slug, summary="s", explanation="e", progression=iivi,
            status=more.pop("status", "published"), **more,
        )

    def exercise(les, order, slug, kind, **more):
        return Exercise.objects.create(
            lesson=les, order=order, slug=slug, title=slug.title(), instructions="i", progression=iivi, key="C", tempo=90,
            bars=4, scoring_kind=kind, scoring_params={}, pass_score=70, xp=20, daily_eligible=more.pop("eligible", True), **more,
        )

    a = lesson("chord_tones", "lesson-a")
    c = lesson("scales_modes", "lesson-c", prerequisite=a)
    draft = lesson("rhythm_motifs", "lesson-draft", status="draft")
    return dict(
        iivi=iivi, a=a, c=c,
        a1=exercise(a, 1, "a-one", "chord_tones_on_beats"),
        a2=exercise(a, 2, "a-two", "guide_tones"),
        c1=exercise(c, 1, "c-one", "scale_only"),
        draft1=exercise(draft, 1, "draft-one", "rhythm_motif"),
        challenge=exercise(None, 1, "a-challenge", "rhythm_motif"),
    )


def _client(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _player(user, **fields):
    player, _ = Player.objects.get_or_create(user=user)
    for name, value in fields.items():
        setattr(player, name, value)
    player.save()
    return player


def _finish_lesson_a(player):
    for e in Exercise.objects.filter(lesson__slug="lesson-a"):
        row = Completion.objects.create(player=player, exercise=e, xp_awarded=e.xp)
        Completion.objects.filter(pk=row.pk).update(completed_at=NOW - dt.timedelta(days=9))


def _played(player, days_ago=1, exercise=None, score=None, bars=None, **metrics):
    """A take with the given metrics, played `days_ago` days before NOW."""
    when = NOW - dt.timedelta(days=days_ago)
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    iivi = Progression.objects.get(slug="ii-v-i-major")
    row = Take.objects.create(
        player=player, session=session, progression=iivi, exercise=exercise, chart=iivi.chart, home_key="C", key="C", tempo=90,
        loop_from=0, loop_to=4, started_at=when, duration_ms=10000, bars=bars or (exercise.bars if exercise else 4),
        score=score, metrics=metrics, judge_version=1,
    )
    return row


def _good(notes=40, **over):
    metrics = {"notes": notes, "chordTonePct": 60, "scalePct": 30, "approachPct": 5, "outsidePct": 5, "withinPct": 90}
    metrics.update(over)
    return metrics


def _claims(player, **kw):
    return weakness.report(player, now=NOW, **kw)["claims"]


def _areas(player, **kw):
    return [c["area"] for c in _claims(player, **kw)]


# ------------------------------------------------------------------ the weakness report: the floor


def test_with_no_takes_it_says_nothing_and_says_how_many_notes_it_needs(people, path):
    report = weakness.report(_player(people["member"]), now=NOW)
    assert report["claims"] == [] and report["notes"] == 0 and report["enough"] is False
    assert report["floor"] == 20 and report["notes_needed"] == 20 and report["days"] == 30


def test_nineteen_notes_say_nothing_and_twenty_can(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=19, withinPct=10))
    report = weakness.report(player, now=NOW)
    assert report["claims"] == [] and report["enough"] is False and report["notes_needed"] == 1
    _played(player, **_good(notes=1, withinPct=10))
    report = weakness.report(player, now=NOW)
    assert report["enough"] is True and report["notes_needed"] == 0
    assert [c["area"] for c in report["claims"]] == ["timing"]


def test_enough_notes_and_nothing_wrong_says_nothing(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=60))
    report = weakness.report(player, now=NOW)
    assert report["enough"] is True and report["claims"] == []


def test_the_notes_of_many_takes_add_up_to_the_floor(people, path):
    player = _player(people["member"])
    for _ in range(4):
        _played(player, **_good(notes=5, withinPct=20))
    assert _areas(player) == ["timing"]


# ------------------------------------------------------------------ the buckets


def test_timing_is_weak_when_few_notes_are_close_to_the_beat(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=40, withinPct=40))
    claim = _claims(player)[0]
    assert claim["area"] == "timing" and claim["percent"] == 40 and claim["notes"] == 40
    assert claim["kinds"] == ["rhythm_motif"] and claim["family"] == ""


def test_timing_at_the_bar_is_not_a_claim(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=40, withinPct=60))
    assert _areas(player) == []


def test_chord_tones_are_weak_when_few_notes_land_on_them(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=40, chordTonePct=10, scalePct=80))
    claim = _claims(player)[0]
    assert claim["area"] == "chord_tones" and claim["percent"] == 10
    assert claim["kinds"] == ["chord_tones_on_beats", "guide_tones"]
    assert claim["exercise"] == "a-one"


def test_too_many_outside_notes_is_a_claim_that_wants_a_scale_exercise(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=40, outsidePct=45, scalePct=0, chordTonePct=55))
    claim = _claims(player)[0]
    assert claim["area"] == "outside" and claim["percent"] == 45
    assert claim["kinds"] == ["scale_only", "chord_tones_on_beats"]
    assert claim["exercise"] == "a-one", "the scale lesson is locked, so the next kind that is open"
    _finish_lesson_a(player)
    assert _claims(player)[0]["exercise"] == "c-one"


def test_numbers_are_weighted_by_the_notes_behind_them(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=90, withinPct=100))
    _played(player, **_good(notes=10, withinPct=0))
    assert _areas(player) == [], "ninety percent close to the beat overall"
    _played(player, **_good(notes=100, withinPct=0))
    assert _areas(player) == ["timing"]


def test_a_chord_family_is_weak_when_the_notes_over_it_go_outside(people, path):
    player = _player(people["member"])
    by_quality = {
        "m7": {"notes": 30, "chord": 10, "scale": 5, "approach": 0, "outside": 15},
        "maj7": {"notes": 10, "chord": 10, "scale": 0, "approach": 0, "outside": 0},
    }
    _played(player, **_good(notes=40, byQuality=by_quality))
    claims = _claims(player)
    assert [c["area"] for c in claims] == ["family"]
    assert claims[0]["family"] == "minor" and claims[0]["family_label"] == "minor"
    assert claims[0]["percent"] == 50 and claims[0]["notes"] == 30


def test_a_family_with_fewer_than_twenty_notes_is_not_named(people, path):
    player = _player(people["member"])
    by_quality = {"m7b5": {"notes": 19, "chord": 0, "scale": 0, "approach": 0, "outside": 19}}
    _played(player, **_good(notes=40, byQuality=by_quality))
    assert _areas(player) == []


def test_qualities_of_one_family_pool_their_notes(people, path):
    player = _player(people["member"])
    by_quality = {
        "m7": {"notes": 12, "chord": 2, "scale": 2, "approach": 0, "outside": 8},
        "m9": {"notes": 12, "chord": 2, "scale": 2, "approach": 0, "outside": 8},
    }
    _played(player, **_good(notes=40, byQuality=by_quality))
    claims = _claims(player)
    assert [(c["family"], c["notes"], c["percent"]) for c in claims] == [("minor", 24, 67)]


def test_half_diminished_reads_in_plain_words(people, path):
    player = _player(people["member"])
    by_quality = {"m7b5": {"notes": 25, "chord": 5, "scale": 0, "approach": 0, "outside": 20}}
    _played(player, **_good(notes=40, byQuality=by_quality))
    claim = _claims(player)[0]
    assert claim["family"] == "half_diminished" and claim["family_label"] == "half-diminished"


# ------------------------------------------------------------------ at most three, worst first


def test_it_names_the_worst_first_and_never_more_than_three(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=60, withinPct=20, chordTonePct=10, outsidePct=55))
    assert _areas(player) == ["timing", "outside", "chord_tones"]
    by_quality = {"m7": {"notes": 30, "chord": 0, "scale": 0, "approach": 0, "outside": 27}}
    _played(player, **_good(notes=30, withinPct=20, chordTonePct=10, outsidePct=55, byQuality=by_quality))
    claims = _claims(player)
    assert len(claims) == 3
    assert claims[0]["area"] == "family", "ninety percent outside is the furthest from fine"


# ------------------------------------------------------------------ the exercise each one names


def test_a_claim_names_an_exercise_that_is_open_and_published(people, path):
    player = _player(people["member"])
    _played(player, **_good(notes=40, withinPct=10))
    claim = _claims(player)[0]
    assert claim["exercise"] == "a-challenge", "the only open rhythm exercise: the draft lesson's is not offered"
    assert claim["exercise_title"] == "A-Challenge" and claim["lesson_title"] == ""


def test_with_nothing_open_to_work_on_it_the_claim_still_stands(people, path):
    player = _player(people["member"])
    Exercise.objects.filter(slug="a-challenge").delete()
    _played(player, **_good(notes=40, withinPct=10))
    claim = _claims(player)[0]
    assert claim["area"] == "timing" and claim["exercise"] is None and claim["exercise_title"] == ""


def test_an_exercise_not_yet_passed_is_preferred_to_one_already_passed(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    Completion.objects.filter(player=player, exercise__slug="a-one").delete()
    _played(player, **_good(notes=40, chordTonePct=5))
    assert _claims(player)[0]["exercise"] == "a-one", "not passed yet"
    Completion.objects.create(player=player, exercise=Exercise.objects.get(slug="a-one"), xp_awarded=20)
    Completion.objects.filter(player=player, exercise__slug="a-two").delete()
    assert _claims(player)[0]["exercise"] == "a-two", "a-one is passed, a-two is the next kind and is not"
    Completion.objects.create(player=player, exercise=Exercise.objects.get(slug="a-two"), xp_awarded=20)
    assert _claims(player)[0]["exercise"] == "a-one", "all passed: the first again"


# ------------------------------------------------------------------ the window


def test_takes_older_than_thirty_days_are_not_read(people, path):
    player = _player(people["member"])
    _played(player, days_ago=31, **_good(notes=40, withinPct=0))
    assert weakness.report(player, now=NOW)["notes"] == 0
    _played(player, days_ago=29, **_good(notes=40, withinPct=0))
    assert weakness.report(player, now=NOW)["notes"] == 40
    assert _areas(player) == ["timing"]


def test_another_players_takes_are_not_mine(people, path):
    other = _player(people["other"])
    _played(other, **_good(notes=60, withinPct=0))
    assert weakness.report(_player(people["member"]), now=NOW)["notes"] == 0


def test_a_report_can_be_read_as_it_stood_before_a_moment(people, path):
    player = _player(people["member"])
    _played(player, days_ago=3, **_good(notes=40, withinPct=0))
    _played(player, days_ago=0, **_good(notes=40, withinPct=100))
    before = NOW - dt.timedelta(days=1)
    assert weakness.report(player, now=NOW, before=before)["notes"] == 40
    assert weakness.report(player, now=NOW)["notes"] == 80


def test_metrics_that_are_garbage_count_as_nothing_and_never_crash(people, path):
    player = _player(people["member"])
    for metrics in (
        {}, {"notes": "lots"}, {"notes": -5, "withinPct": 10}, {"notes": 30, "withinPct": "bad"},
        {"notes": 30, "byQuality": "oops"}, {"notes": 30, "byQuality": {"m7": [1, 2]}}, {"notes": 30, "byQuality": {"nope": {"notes": 30, "outside": 30}}},
        {"notes": 30, "withinPct": 5000, "chordTonePct": -300}, {"notes": True},
    ):
        _played(player, **metrics)
    report = weakness.report(player, now=NOW)
    assert isinstance(report["claims"], list) and len(report["claims"]) <= 3


# ------------------------------------------------------------------ the workout hears it


def test_the_weak_kinds_are_the_kinds_the_claims_name_in_order(people, path):
    claims = [{"kinds": ["rhythm_motif"]}, {"kinds": ["scale_only", "chord_tones_on_beats"]}, {"kinds": ["rhythm_motif", "guide_tones"]}]
    assert weakness.weak_kinds(claims) == ["rhythm_motif", "scale_only", "chord_tones_on_beats", "guide_tones"]


def test_a_weak_spot_from_before_today_fills_the_weak_slot(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    _played(player, days_ago=2, **_good(notes=40, withinPct=10))
    picks = workout.pick(player, TODAY)
    assert picks[0]["slot"] == "weak" and picks[0]["exercise"].slug == "a-challenge"
    assert [p["slot"] for p in picks] == ["weak", "review", "next"]


def test_playing_badly_today_does_not_change_todays_workout(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    before = [(p["slot"], p["exercise"].slug) for p in workout.pick(player, TODAY)]
    assert "weak" not in [slot for slot, _ in before]
    _played(player, days_ago=0, **_good(notes=60, withinPct=0))
    assert [(p["slot"], p["exercise"].slug) for p in workout.pick(player, TODAY)] == before
    tomorrow = workout.pick(player, TODAY + dt.timedelta(days=1))
    assert tomorrow[0]["slot"] == "weak", "tomorrow it counts"


def test_the_workout_read_uses_the_report_as_it_stood_before_the_day(people, path):
    user = people["member"]
    player = _player(user)
    _finish_lesson_a(player)
    _played(player, days_ago=2, **_good(notes=40, withinPct=10))
    first = workout.report(player, now=NOW)
    assert first["items"][0]["slot"] == "weak"
    assert first["items"][0]["scoring_kind"] == "rhythm_motif"


# ------------------------------------------------------------------ personal bests


def _best_of(player, slug):
    return next((b for b in bests.report(player)["items"] if b["exercise"] == slug), None)


def test_every_challenge_is_listed_even_before_it_is_played(people, path):
    item = _best_of(_player(people["member"]), "a-challenge")
    assert item["is_challenge"] is True and item["lesson"] is None
    assert item["best_score"] is None and item["best_take"] is None and item["attempts"] == 0 and item["passed"] is False


def test_a_lesson_exercise_appears_once_it_has_been_played(people, path):
    player = _player(people["member"])
    assert _best_of(player, "a-one") is None
    _played(player, exercise=path["a1"], score=55)
    item = _best_of(player, "a-one")
    assert item["is_challenge"] is False and item["lesson"] == "lesson-a" and item["best_score"] == 55


def test_the_best_is_the_highest_score_and_it_names_the_take(people, path):
    player = _player(people["member"])
    _played(player, days_ago=5, exercise=path["a1"], score=60)
    best = _played(player, days_ago=3, exercise=path["a1"], score=88)
    _played(player, days_ago=1, exercise=path["a1"], score=71)
    item = _best_of(player, "a-one")
    assert item["best_score"] == 88 and item["best_take"] == best.pk and item["attempts"] == 3 and item["passed"] is True
    assert item["best_at"].startswith(str((NOW - dt.timedelta(days=3)).astimezone(dt.timezone.utc).date()))


def test_a_tie_goes_to_the_take_that_got_there_first(people, path):
    player = _player(people["member"])
    first = _played(player, days_ago=5, exercise=path["a1"], score=90)
    _played(player, days_ago=1, exercise=path["a1"], score=90)
    assert _best_of(player, "a-one")["best_take"] == first.pk


def test_a_take_over_other_bars_or_without_a_score_is_not_a_best(people, path):
    player = _player(people["member"])
    _played(player, exercise=path["a1"], score=100, bars=2)
    _played(player, exercise=path["a1"], score=None)
    assert _best_of(player, "a-one") is None
    _played(player, exercise=path["a1"], score=64)
    item = _best_of(player, "a-one")
    assert item["best_score"] == 64 and item["attempts"] == 1 and item["passed"] is False


def test_the_bar_is_the_exercises_own_pass_mark(people, path):
    player = _player(people["member"])
    _played(player, exercise=path["a1"], score=70)
    assert _best_of(player, "a-one")["passed"] is True
    assert _best_of(player, "a-one")["pass_score"] == 70


def test_one_players_bests_are_not_anothers(people, path):
    _played(_player(people["other"]), exercise=path["a1"], score=99)
    assert _best_of(_player(people["member"]), "a-one") is None


def test_a_draft_lessons_exercise_is_never_listed(people, path):
    player = _player(people["member"])
    _played(player, exercise=path["draft1"], score=80)
    assert _best_of(player, "draft-one") is None


def test_the_bests_come_challenges_last_after_the_lessons_in_order(people, path):
    player = _player(people["member"])
    _played(player, exercise=path["c1"], score=70)
    _played(player, exercise=path["a2"], score=70)
    _played(player, exercise=path["a1"], score=70)
    assert [b["exercise"] for b in bests.report(player)["items"]] == ["a-one", "a-two", "c-one", "a-challenge"]


# ------------------------------------------------------------------ the API


@pytest.mark.parametrize("name", ["weakness", "bests"])
def test_the_new_reads_are_behind_the_gate_and_read_only(people, path, name):
    url = f"{API}{name}/"
    assert _client().get(url).status_code == 404
    assert _client(people["stranger"]).get(url).status_code == 404
    client = _client(people["member"])
    assert client.get(url).status_code == 200
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(url).status_code == 405


def test_the_weakness_read_carries_the_claims(people, path):
    player = _player(people["member"])
    _played(player, days_ago=0, **_good(notes=40, withinPct=10))
    data = _client(people["member"]).get(f"{API}weakness/").json()
    assert set(data) == {"days", "floor", "notes", "enough", "notes_needed", "claims"}
    assert data["enough"] is True and data["claims"][0]["area"] == "timing"
    assert set(data["claims"][0]) == {
        "area", "family", "family_label", "percent", "notes", "kinds", "exercise", "exercise_title", "lesson_title",
    }


def test_the_bests_read_carries_what_the_page_needs(people, path):
    player = _player(people["member"])
    _played(player, exercise=path["a1"], score=80)
    data = _client(people["member"]).get(f"{API}bests/").json()
    item = next(i for i in data["items"] if i["exercise"] == "a-one")
    assert set(item) == {
        "exercise", "title", "lesson", "lesson_title", "scoring_kind", "pass_score", "xp", "is_challenge",
        "best_score", "best_take", "best_at", "attempts", "passed",
    }


def test_another_player_cannot_see_my_weakness(people, path):
    _played(_player(people["member"]), days_ago=0, **_good(notes=60, withinPct=0))
    data = _client(people["other"]).get(f"{API}weakness/").json()
    assert data["notes"] == 0 and data["claims"] == []


# ------------------------------------------------------------------ the judge says it per quality (python side of the shape)


def test_the_judge_script_keeps_a_note_count_per_chord_quality():
    source = Path("static/improv/judge.js").read_text(encoding="utf-8")
    assert "byQuality" in source


# ------------------------------------------------------------------ challenges: the seed


@pytest.fixture
def seeded(people):
    call_command("seed_improv_challenges", stdout=io.StringIO())


def _seed():
    out = io.StringIO()
    call_command("seed_improv_challenges", stdout=out)
    return out.getvalue()


def test_the_seed_adds_a_handful_of_challenges_with_no_lesson(seeded):
    rows = Exercise.objects.all()
    assert 4 <= rows.count() <= 8
    assert all(e.lesson_id is None for e in rows)
    assert all(e.daily_eligible for e in rows)


def test_every_challenge_passes_the_check_of_a_saved_one(seeded):
    for e in Exercise.objects.select_related("progression"):
        e.full_clean()
        bars = len([c for c in e.progression.chart.split("|") if c.strip()])
        assert e.bars <= bars, f"{e.slug} asks for {e.bars} bars of a {bars}-bar chart"
        assert check_scoring(e.scoring_kind, e.scoring_params, beats_per_bar=4, bars=e.bars) is None
        assert e.key == e.progression.home_key and 1 <= e.xp <= 100 and 40 <= e.pass_score <= 100


def test_challenges_cover_more_than_one_kind_so_each_weakness_has_one(seeded):
    kinds = set(Exercise.objects.values_list("scoring_kind", flat=True))
    assert {"chord_tones_on_beats", "scale_only", "rhythm_motif"} <= kinds


def test_the_seed_text_is_plain():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    for row in data["challenges"]:
        for text in (row["title"], row["instructions"]):
            assert chr(0x2014) not in text and chr(0x2013) not in text
            assert not re.search(r"[\U0001F300-\U0001FAFF]", text)


def test_the_command_reports_what_it_added_then_nothing(people):
    first = _seed()
    count = Exercise.objects.count()
    assert re.search(rf"improv challenges: added {count}\.", first), first
    assert "improv challenges: added 0" in _seed()
    assert Exercise.objects.count() == count


def test_running_it_again_never_undoes_an_edit_and_fills_in_what_was_deleted(seeded):
    slug = Exercise.objects.order_by("id").first().slug
    Exercise.objects.filter(slug=slug).update(xp=77)
    other = Exercise.objects.order_by("-id").first()
    other_slug = other.slug
    other.delete()
    out = _seed()
    assert "added 1" in out, out
    assert Exercise.objects.get(slug=slug).xp == 77
    assert Exercise.objects.filter(slug=other_slug).exists()


def test_the_command_needs_the_library_and_says_so(db):
    with pytest.raises(Exception, match="seed_improv_library"):
        _seed()


def test_a_new_player_sees_the_challenges_in_the_bests_and_the_workout(people, seeded):
    player = _player(people["member"])
    items = bests.report(player)["items"]
    assert len(items) == Exercise.objects.count() and all(i["is_challenge"] for i in items)
    assert len(workout.pick(player, TODAY)) == 3


# ------------------------------------------------------------------ the page and the docs


def test_the_challenges_page_is_in_the_menu_and_has_its_places(people):
    client = _client(people["member"])
    html = client.get("/improv/challenges/").content.decode("utf-8")
    assert 'data-api-bests="/improv/api/bests/"' in html
    for element_id in ("challenges-status", "challenges-list", "challenges-empty", "lessons-bests"):
        assert f'id="{element_id}"' in html
    assert 'href="/improv/challenges/"' in client.get("/improv/practice/").content.decode("utf-8")


def test_the_progress_page_has_the_weakness_panel(people):
    html = _client(people["member"]).get("/improv/progress/").content.decode("utf-8")
    assert 'data-api-weakness="/improv/api/weakness/"' in html
    for element_id in ("weakness-status", "weakness-list"):
        assert f'id="{element_id}"' in html


def test_the_challenges_page_is_behind_the_gate(people):
    assert _client().get("/improv/challenges/").status_code == 404
    assert _client(people["stranger"]).get("/improv/challenges/").status_code == 404


def test_the_docs_describe_the_new_reads_and_the_backlog_is_done():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    for needle in ("/improv/api/weakness/", "/improv/api/bests/", "/improv/challenges/"):
        assert needle in api, needle
    assert "SPR-I.5.6" in Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "SPR-I.5.6" in Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    row = next(line for line in backlog.splitlines() if line.startswith("| SPR-I.5.6 "))
    assert re.search(r"DONE \d{4}-\d{2}-\d{2}", row), row
    epic = next(line for line in backlog.splitlines() if "EPIC-I.5" in line and "DONE" in line)
    assert epic


def test_the_page_scripts_hold_no_unsafe_dom_use():
    for name in ("weakness.js", "bests.js", "challenges-page.js"):
        source = Path(f"static/improv/{name}").read_text(encoding="utf-8")
        assert "innerHTML" not in source and "eval(" not in source, name


def test_the_judge_counts_and_the_words_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri56.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
