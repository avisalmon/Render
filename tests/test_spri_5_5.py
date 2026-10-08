"""SPR-I.5.5 improv: the daily workout, three picks that stay put for the day.

The workout is a read, never stored: a function of the player, the date and what the player had
done before that day began. So a reload does not shuffle it, finishing one of the three during the
day does not change the other two, and tomorrow is a different set. It never offers an exercise
that is locked, a draft, or not marked for the workout.

Traces: spec ch. 6 (the daily workout), data model section 8, backlog SPR-I.5.5.
"""

import datetime as dt
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

from improv import workout
from improv.models import Completion, Exercise, Lesson, Player, PracticeSession, Progression, Take

import io

pytestmark = pytest.mark.spri55

PASSWORD = "spri55-pass-9917"
WORKOUT = "/improv/api/workout/"
ZONE = ZoneInfo("Asia/Jerusalem")
TODAY = dt.date(2026, 10, 5)
START = dt.datetime(2026, 10, 5, 0, 0, tzinfo=ZONE)


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p55member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p55other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p55stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "other": other, "stranger": stranger}


@pytest.fixture
def path(people):
    """A (two for the workout and one not), B and C after A, D after C, a draft, and a challenge."""
    iivi = Progression.objects.get(slug="ii-v-i-major")

    def lesson(track, slug, **more):
        return Lesson.objects.create(
            track=track, order=1, title=slug.title(), slug=slug, summary="s", explanation="e", progression=iivi,
            status=more.pop("status", "published"), **more,
        )

    def exercise(les, order, slug, kind, eligible=True, **more):
        return Exercise.objects.create(
            lesson=les, order=order, slug=slug, title=slug.title(), instructions="i", progression=iivi, key="C", tempo=90,
            bars=4, scoring_kind=kind, scoring_params={}, pass_score=70, xp=20, daily_eligible=eligible, **more,
        )

    a = lesson("chord_tones", "lesson-a")
    b = lesson("guide_tones", "lesson-b", prerequisite=a)
    c = lesson("scales_modes", "lesson-c", prerequisite=a)
    d = lesson("approach_notes", "lesson-d", prerequisite=c)
    draft = lesson("rhythm_motifs", "lesson-draft", status="draft")
    return dict(
        iivi=iivi, a=a, b=b, c=c, d=d,
        a1=exercise(a, 1, "a-one", "chord_tones_on_beats"),
        a2=exercise(a, 2, "a-two", "chord_tones_on_beats"),
        a3=exercise(a, 3, "a-three", "chord_tones_on_beats", eligible=False),
        b1=exercise(b, 1, "b-one", "guide_tones"),
        c1=exercise(c, 1, "c-one", "scale_only"),
        d1=exercise(d, 1, "d-one", "approach_notes"),
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


def _complete(player, exercise, when):
    row = Completion.objects.create(player=player, exercise=exercise, xp_awarded=exercise.xp)
    Completion.objects.filter(pk=row.pk).update(completed_at=when)
    return row


def _finish_lesson_a(player):
    for e in Exercise.objects.filter(lesson__slug="lesson-a"):
        _complete(player, e, START - dt.timedelta(days=2))


def _take(player, exercise, when, score=90, **more):
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    iivi = exercise.progression
    row = Take.objects.create(
        player=player, session=session, progression=iivi, exercise=exercise, chart=iivi.chart, home_key=iivi.home_key,
        key="C", tempo=90, loop_from=0, loop_to=exercise.bars, started_at=when, duration_ms=10000, bars=more.pop("bars", exercise.bars),
        score=score, judge_version=1, **more,
    )
    Take.objects.filter(pk=row.pk).update(created_at=when)
    return row


def _slugs(picks):
    return [item["exercise"].slug for item in picks]


# ------------------------------------------------------------------ what is picked


def test_a_new_player_gets_the_first_exercise_as_next_and_fresh_ones_beside_it(people, path):
    player = _player(people["member"])
    picks = workout.pick(player, TODAY)
    assert [item["slot"] for item in picks] == ["next", "fresh", "fresh"]
    assert picks[0]["exercise"] == path["a1"]
    assert set(_slugs(picks)) == {"a-one", "a-two", "a-challenge"}


def test_the_same_player_and_date_always_get_the_same_picks(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    first = workout.pick(player, TODAY)
    for _ in range(3):
        assert _slugs(workout.pick(player, TODAY)) == _slugs(first)


def test_a_review_is_one_the_player_has_passed_and_next_is_the_first_they_have_not(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    picks = workout.pick(player, TODAY)
    assert [item["slot"] for item in picks] == ["review", "next", "fresh"]
    review, nxt, fresh = picks
    assert review["exercise"] in (path["a1"], path["a2"])
    assert nxt["exercise"] == path["b1"], "guide tones come before scales in the order of the tracks"
    assert fresh["exercise"] in (path["c1"], path["challenge"])


def test_a_weak_spot_picks_an_exercise_of_that_kind_first(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    picks = workout.pick(player, TODAY, weak_kinds=["scale_only"])
    assert [item["slot"] for item in picks] == ["weak", "review", "next"]
    assert picks[0]["exercise"] == path["c1"]


def test_the_first_weak_kind_that_has_something_to_play_wins(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    picks = workout.pick(player, TODAY, weak_kinds=["approach_notes", "guide_tones"])
    assert picks[0]["slot"] == "weak" and picks[0]["exercise"] == path["b1"], "approach notes are locked, so the next kind"


def test_a_weak_kind_with_nothing_unlocked_is_not_forced(people, path):
    player = _player(people["member"])
    picks = workout.pick(player, TODAY, weak_kinds=["guide_tones"])
    assert "weak" not in [item["slot"] for item in picks]
    assert path["b1"] not in [item["exercise"] for item in picks]


def test_a_locked_draft_or_unmarked_exercise_is_never_offered(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    for n in range(40):
        day = TODAY + dt.timedelta(days=n)
        offered = set(_slugs(workout.pick(player, day, weak_kinds=["approach_notes", "rhythm_motif"])))
        assert "d-one" not in offered, "lesson D is locked until C is done"
        assert "draft-one" not in offered
        assert "a-three" not in offered, "not marked daily_eligible"


def test_no_exercise_is_picked_twice_and_there_are_never_more_than_three(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    _complete(player, path["b1"], START - dt.timedelta(days=1))
    for n in range(30):
        picks = workout.pick(player, TODAY + dt.timedelta(days=n), weak_kinds=["chord_tones_on_beats"])
        slugs = _slugs(picks)
        assert len(slugs) == len(set(slugs)) <= 3


def test_a_challenge_is_always_open_and_can_be_picked(people, path):
    player = _player(people["member"])
    assert path["challenge"] in [item["exercise"] for item in workout.pick(player, TODAY)]


def test_the_picks_change_from_one_day_to_the_next_over_a_month(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    reviews = {workout.pick(player, TODAY + dt.timedelta(days=n))[0]["exercise"].slug for n in range(30)}
    assert reviews == {"a-one", "a-two"}, "the review rotates through what has been passed"


def test_with_nothing_to_play_there_is_nothing_to_pick(people):
    assert workout.pick(_player(people["member"]), TODAY) == []


def test_another_players_progress_does_not_change_my_picks(people, path):
    mine = _player(people["member"])
    theirs = _player(people["other"])
    before = _slugs(workout.pick(mine, TODAY))
    _finish_lesson_a(theirs)
    assert _slugs(workout.pick(mine, TODAY)) == before


# ------------------------------------------------------------------ staying put through the day


def test_finishing_one_during_the_day_does_not_change_the_three(people, path):
    player = _player(people["member"])
    before = workout.pick(player, TODAY)
    first = before[0]["exercise"]
    _complete(player, first, START + dt.timedelta(hours=9))
    _take(player, first, START + dt.timedelta(hours=9))
    after = workout.pick(player, TODAY)
    assert _slugs(after) == _slugs(before)
    assert [item["done_today"] for item in after] == [True, False, False]


def test_a_take_below_the_bar_or_over_other_bars_is_not_done(people, path):
    player = _player(people["member"])
    first = workout.pick(player, TODAY)[0]["exercise"]
    _take(player, first, START + dt.timedelta(hours=9), score=40)
    assert workout.pick(player, TODAY)[0]["done_today"] is False
    _take(player, first, START + dt.timedelta(hours=10), score=95, bars=2)
    assert workout.pick(player, TODAY)[0]["done_today"] is False
    _take(player, first, START + dt.timedelta(hours=11), score=95)
    assert workout.pick(player, TODAY)[0]["done_today"] is True


def test_a_pass_from_yesterday_does_not_make_today_done(people, path):
    player = _player(people["member"])
    first = workout.pick(player, TODAY)[0]["exercise"]
    _take(player, first, START - dt.timedelta(hours=2))
    assert workout.pick(player, TODAY)[0]["done_today"] is False


def test_the_next_day_moves_on_once_it_has_been_passed(people, path):
    player = _player(people["member"])
    first = workout.pick(player, TODAY)[0]["exercise"]
    _complete(player, first, START + dt.timedelta(hours=9))
    tomorrow = workout.pick(player, TODAY + dt.timedelta(days=1))
    assert first not in [item["exercise"] for item in tomorrow if item["slot"] == "next"]


def test_a_review_passed_again_today_is_done_but_earns_nothing(people, path):
    player = _player(people["member"])
    _finish_lesson_a(player)
    review = workout.pick(player, TODAY)[0]
    assert review["slot"] == "review" and review["xp_available"] == 0
    _take(player, review["exercise"], START + dt.timedelta(hours=9))
    assert workout.pick(player, TODAY)[0]["done_today"] is True


def test_an_item_says_what_it_would_earn(people, path):
    player = _player(people["member"])
    picks = workout.pick(player, TODAY)
    assert all(item["xp_available"] == 20 for item in picks)


# ------------------------------------------------------------------ the day is the player's


def test_the_day_comes_from_the_players_own_timezone(people, path):
    player = _player(people["member"], timezone="Pacific/Auckland")
    now = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.timezone.utc)
    assert workout.report(player, now=now)["date"] == "2026-10-06"
    player.timezone = "America/Los_Angeles"
    player.save()
    assert workout.report(player, now=now)["date"] == "2026-10-05"


def test_a_completion_just_after_local_midnight_counts_for_the_new_day(people, path):
    player = _player(people["member"])
    first = workout.pick(player, TODAY)[0]["exercise"]
    _complete(player, first, START + dt.timedelta(minutes=5))
    _take(player, first, START + dt.timedelta(minutes=5))
    assert workout.pick(player, TODAY)[0]["done_today"] is True
    assert workout.pick(player, TODAY - dt.timedelta(days=1))[0]["done_today"] is False


# ------------------------------------------------------------------ the API


def test_the_workout_read_is_behind_the_gate_and_read_only(people, path):
    assert _client().get(WORKOUT).status_code in (401, 403)
    for who in ("member", "stranger"):
        client = _client(people[who])
        assert client.get(WORKOUT).status_code == 200, who
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(WORKOUT).status_code == 405, (who, method)
    visitor = _client()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(visitor, method)(WORKOUT).status_code in (401, 403, 405), method


def test_the_workout_read_carries_what_the_page_needs(people, path):
    data = _client(people["member"]).get(WORKOUT).json()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["date"])
    assert data["timezone"] == "Asia/Jerusalem"
    assert data["total"] == 3 and data["done_today"] == 0 and data["complete"] is False
    first = data["items"][0]
    assert set(first) == {
        "slot", "exercise", "title", "lesson", "lesson_title", "scoring_kind", "xp", "xp_available", "pass_score", "done_today",
    }
    assert first["slot"] == "next" and first["exercise"] == "a-one" and first["lesson"] == "lesson-a"
    challenge = next(item for item in data["items"] if item["exercise"] == "a-challenge")
    assert challenge["lesson"] is None and challenge["lesson_title"] == ""


def test_a_whole_workout_done_is_complete(people, path):
    client = _client(people["member"])
    player = _player(people["member"])
    for item in client.get(WORKOUT).json()["items"]:
        _take(player, Exercise.objects.get(slug=item["exercise"]), timezone.now())
    data = client.get(WORKOUT).json()
    assert data["done_today"] == 3 and data["complete"] is True


def test_the_workout_for_a_player_with_no_lessons_is_empty_not_an_error(people):
    data = _client(people["member"]).get(WORKOUT).json()
    assert data["items"] == [] and data["total"] == 0 and data["complete"] is False


def test_the_read_makes_the_profile_on_a_first_visit(people, path):
    assert not Player.objects.filter(user=people["member"]).exists()
    assert _client(people["member"]).get(WORKOUT).status_code == 200


def test_another_player_cannot_see_my_progress_through_the_workout(people, path):
    mine = _player(people["member"])
    _finish_lesson_a(mine)
    data = _client(people["other"]).get(WORKOUT).json()
    assert [item["slot"] for item in data["items"]] == ["next", "fresh", "fresh"]


# ------------------------------------------------------------------ the page and the docs


def test_the_practice_page_has_the_workout_panel(people):
    html = _client(people["member"]).get("/improv/practice/").content.decode("utf-8")
    assert 'data-api-workout="/improv/api/workout/"' in html
    for element_id in ("workout-status", "workout-list", "workout-empty"):
        assert f'id="{element_id}"' in html


def test_the_docs_describe_the_workout_and_the_backlog_is_done():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/workout/" in api
    assert "SPR-I.5.5" in Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "SPR-I.5.5" in Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    row = next(line for line in backlog.splitlines() if line.startswith("| SPR-I.5.5 "))
    assert re.search(r"DONE \d{4}-\d{2}-\d{2}", row), row


def test_the_page_script_holds_no_unsafe_dom_use():
    source = Path("static/improv/workout.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "eval(" not in source


def test_the_words_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri55.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
