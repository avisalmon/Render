"""SPR-I.5.2 improv: Completion, XP, level and the unlock of the next lesson.

A completion is a fact the server records as the consequence of a take: the player passed an
exercise for the first time. The page cannot write one, and the XP comes from the exercise row,
not from anything the page said, because a completion a client could write would be a counter
the client could set. XP, level and what is unlocked are reads over the completions, never
stored.

Traces: spec ch. 5 (what the server does with the result), ch. 6 (the cycle of a lesson, XP and
level), data model section 6 and 8, backlog SPR-I.5.2.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from improv import progress
from improv.models import Completion, Exercise, Lesson, Take

pytestmark = pytest.mark.spri52

API = "/improv/api/"
PASSWORD = "spri52-pass-5528"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p52member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p52other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p52stranger", password=PASSWORD)
    admin = User.objects.create_user("p52admin", password=PASSWORD, is_staff=True, is_superuser=True)
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


@pytest.fixture
def path(people):
    """Lesson A (two exercises), B after A (one), C after A (none to play), a draft, and a challenge."""
    from improv.models import Progression

    iivi = Progression.objects.get(slug="ii-v-i-major")
    blues = Progression.objects.exclude(pk=iivi.pk).first()

    def lesson(track, order, slug, **more):
        return Lesson.objects.create(
            track=track, order=order, title=slug.title(), slug=slug, summary="s", explanation="e", progression=iivi,
            status=more.pop("status", "published"), **more,
        )

    def exercise(les, order, slug, **more):
        values = dict(
            lesson=les, order=order, slug=slug, title=slug.title(), instructions="i", progression=iivi, key="C", tempo=90,
            bars=4, scoring_kind="scale_only", scoring_params={}, pass_score=70, xp=20,
        )
        values.update(more)
        return Exercise.objects.create(**values)

    a = lesson("chord_tones", 1, "lesson-a")
    b = lesson("guide_tones", 1, "lesson-b", prerequisite=a)
    c = lesson("scales_modes", 1, "lesson-c", prerequisite=a)
    d = lesson("approach_notes", 1, "lesson-d", prerequisite=c)
    draft = lesson("rhythm_motifs", 1, "lesson-draft", status="draft")
    return dict(
        iivi=iivi, blues=blues, a=a, b=b, c=c, d=d, draft=draft,
        a1=exercise(a, 1, "a-one", pass_score=70, xp=20),
        a2=exercise(a, 2, "a-two", pass_score=80, xp=30),
        b1=exercise(b, 1, "b-one", xp=40),
        draft1=exercise(draft, 1, "draft-one", xp=99),
        challenge=exercise(None, 1, "a-challenge", xp=15, pass_score=60),
    )


def _session(client):
    return _json(client, "post", f"{API}sessions/").json()["id"]


def _take(client, session, path, exercise=None, score=90, **changes):
    iivi = path["iivi"]
    body = {
        "session": session, "progression": iivi.pk, "style": iivi.default_style_id, "exercise": exercise,
        "chart": iivi.chart, "home_key": iivi.home_key, "key": "C", "time_signature": "4/4", "tempo": 90,
        "swing_ratio": "0.67", "loop_from": 0, "loop_to": 4, "started_at": timezone.now().isoformat(),
        "duration_ms": 10000, "bars": 4,
        "events": [{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 300, "type": "off", "note": 62, "velocity": 0}],
        "score": score, "metrics": {"notes": 1}, "judge_version": 1,
    }
    body.update(changes)
    return _json(client, "post", f"{API}takes/", body)


# --------------------------------------------------------------- level, on its own


def test_the_level_thresholds_are_one_gentle_curve_in_one_place():
    assert progress.level_floor(1) == 0
    assert [progress.level_floor(n) for n in (2, 3, 4, 5)] == [50, 150, 300, 500]
    floors = [progress.level_floor(n) for n in range(1, progress.MAX_LEVEL + 1)]
    assert floors == sorted(set(floors)), "each level asks for more than the one before"
    gaps = [b - a for a, b in zip(floors, floors[1:])]
    assert gaps == sorted(gaps), "the curve only ever steepens, never lurches"


@pytest.mark.parametrize(
    "xp,level",
    [(0, 1), (49, 1), (50, 2), (149, 2), (150, 3), (299, 3), (300, 4), (10**9, progress.MAX_LEVEL)],
)
def test_level_is_a_function_of_total_xp(xp, level):
    assert progress.level_for(xp) == level


def test_the_next_level_is_named_until_the_top():
    assert progress.next_level_at(1) == 50
    assert progress.next_level_at(progress.MAX_LEVEL) is None


# ------------------------------------------------------ the server makes the completion


def test_a_passing_take_makes_the_completion_and_the_xp_comes_from_the_exercise_row(people, path):
    client = _client(people["member"])
    made = _take(client, _session(client), path, exercise="a-one", score=75, metrics={"notes": 1, "xp_awarded": 9999})
    assert made.status_code == 201, made.content
    completion = Completion.objects.get()
    assert completion.player.user == people["member"]
    assert completion.exercise == path["a1"]
    assert completion.take_id == made.json()["id"]
    assert completion.xp_awarded == 20, "the row says 20; whatever the page sent is ignored"
    assert made.json()["completion"] == {"id": completion.pk, "xp_awarded": 20}


def test_the_score_has_to_reach_the_pass_score_exactly(people, path):
    client = _client(people["member"])
    session = _session(client)
    below = _take(client, session, path, exercise="a-one", score=69)
    assert below.json()["completion"] is None
    assert not Completion.objects.exists()
    on_the_mark = _take(client, session, path, exercise="a-one", score=70)
    assert on_the_mark.json()["completion"]["xp_awarded"] == 20
    assert Completion.objects.get().take_id == on_the_mark.json()["id"], "the take that passed"


def test_free_play_and_an_unscored_take_complete_nothing(people, path):
    client = _client(people["member"])
    session = _session(client)
    assert _take(client, session, path, exercise="a-one", score=None).json()["completion"] is None
    assert _take(client, session, path, exercise=None, score=100).json()["completion"] is None
    assert not Completion.objects.exists()


def test_passing_again_earns_nothing(people, path):
    client = _client(people["member"])
    session = _session(client)
    first = _take(client, session, path, exercise="a-one", score=90).json()
    again = _take(client, session, path, exercise="a-one", score=100).json()
    assert first["completion"] and again["completion"] is None
    assert Completion.objects.count() == 1
    assert Completion.objects.get().take_id == first["id"]
    assert _client(people["member"]).get(f"{API}summary/").json()["xp"] == 20


@pytest.mark.parametrize(
    "changes",
    [
        {"loop_from": 1, "loop_to": 5},
        {"loop_to": 3, "bars": 3},
        {"loop_to": 8, "bars": 8},
    ],
)
def test_a_take_over_other_bars_than_the_exercise_asks_for_does_not_count(people, path, changes):
    client = _client(people["member"])
    made = _take(client, _session(client), path, exercise="a-one", score=100, **changes)
    assert made.status_code == 201
    assert made.json()["completion"] is None
    assert not Completion.objects.exists()


def test_a_take_over_another_progression_does_not_count(people, path):
    client = _client(people["member"])
    blues = path["blues"]
    made = _take(client, _session(client), path, exercise="a-one", score=100, progression=blues.pk, style=None)
    assert made.status_code == 201
    assert made.json()["completion"] is None


def test_an_exercise_of_a_lesson_ahead_counts_all_the_same(people, path):
    # Since SPR-I.10.1 nothing is locked: a person may start where they like, and the pass counts.
    client = _client(people["member"])
    early = _take(client, _session(client), path, exercise="b-one", score=100)
    assert early.status_code == 201
    assert early.json()["completion"]["xp_awarded"] == 40


def test_a_challenge_is_never_locked(people, path):
    client = _client(people["member"])
    made = _take(client, _session(client), path, exercise="a-challenge", score=60)
    assert made.json()["completion"]["xp_awarded"] == 15


def test_a_client_cannot_name_a_completion_in_a_take(people, path):
    client = _client(people["member"])
    made = _take(client, _session(client), path, exercise="a-one", score=10, completion={"id": 1, "xp_awarded": 500})
    assert made.status_code == 201
    assert made.json()["completion"] is None
    assert not Completion.objects.exists()


def test_the_completion_belongs_to_the_player_who_played_not_to_anyone_named_in_the_body(people, path):
    client = _client(people["member"])
    made = _take(client, _session(client), path, exercise="a-one", score=100, player=people["other"].pk)
    assert made.status_code == 201
    assert Completion.objects.get().player.user == people["member"]


def test_the_admin_reading_a_draft_lesson_earns_its_xp_like_anyone(people, path):
    client = _client(people["admin"])
    made = _take(client, _session(client), path, exercise="draft-one", score=100)
    assert made.status_code == 201
    assert made.json()["completion"]["xp_awarded"] == 99


# --------------------------------------------------- a completion is a fact, kept


def test_a_player_has_one_completion_per_exercise_in_the_database_too(people, path):
    client = _client(people["member"])
    _take(client, _session(client), path, exercise="a-one", score=100)
    first = Completion.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        Completion.objects.create(player=first.player, exercise=first.exercise, take=None, xp_awarded=5)


def test_deleting_the_take_keeps_the_completion_and_its_xp(people, path):
    client = _client(people["member"])
    take = _take(client, _session(client), path, exercise="a-one", score=100).json()
    assert client.delete(f"{API}takes/{take['id']}/").status_code == 204
    completion = Completion.objects.get()
    assert completion.take is None and completion.xp_awarded == 20
    assert client.get(f"{API}summary/").json()["xp"] == 20


def test_deleting_the_exercise_takes_its_completion_with_it(people, path):
    client = _client(people["member"])
    _take(client, _session(client), path, exercise="a-one", score=100)
    path["a1"].delete()
    assert not Completion.objects.exists()


def test_the_xp_is_frozen_when_the_exercise_is_later_changed(people, path):
    client = _client(people["member"])
    _take(client, _session(client), path, exercise="a-one", score=100)
    Exercise.objects.filter(pk=path["a1"].pk).update(xp=500)
    assert Completion.objects.get().xp_awarded == 20
    assert client.get(f"{API}summary/").json()["xp"] == 20


# ------------------------------------------------------------- the completions API


def test_completions_are_read_only_through_the_api(people, path):
    client = _client(people["member"])
    _take(client, _session(client), path, exercise="a-one", score=100)
    pk = Completion.objects.get().pk
    assert client.post(f"{API}completions/", {"exercise": "a-two", "xp_awarded": 500}, content_type="application/json").status_code == 405
    for method in ("put", "patch", "delete"):
        response = getattr(client, method)(f"{API}completions/{pk}/", {"xp_awarded": 500}, content_type="application/json")
        assert response.status_code == 405, method
    assert Completion.objects.get().xp_awarded == 20


def test_a_player_reads_their_own_completions_and_nobody_elses(people, path):
    mine, theirs = _client(people["member"]), _client(people["other"])
    _take(mine, _session(mine), path, exercise="a-one", score=100)
    _take(theirs, _session(theirs), path, exercise="a-two", score=100)
    rows = mine.get(f"{API}completions/").json()
    assert [r["exercise"] for r in rows] == ["a-one"]
    other_pk = Completion.objects.get(exercise=path["a2"]).pk
    assert mine.get(f"{API}completions/{other_pk}/").status_code == 404


def test_a_completion_says_what_was_passed_with_which_take_and_for_how_much(people, path):
    client = _client(people["member"])
    take = _take(client, _session(client), path, exercise="a-one", score=88).json()
    row = client.get(f"{API}completions/").json()[0]
    assert set(row) == {"id", "exercise", "exercise_title", "lesson", "take", "xp_awarded", "completed_at"}
    assert row["exercise"] == "a-one" and row["lesson"] == "lesson-a" and row["take"] == take["id"] and row["xp_awarded"] == 20


def test_completions_filter_by_exercise_and_by_lesson(people, path):
    client = _client(people["member"])
    session = _session(client)
    _take(client, session, path, exercise="a-one", score=100)
    _take(client, session, path, exercise="a-challenge", score=100)
    assert [r["exercise"] for r in client.get(f"{API}completions/", {"exercise": "a-challenge"}).json()] == ["a-challenge"]
    assert [r["exercise"] for r in client.get(f"{API}completions/", {"lesson": "lesson-a"}).json()] == ["a-one"]
    assert client.get(f"{API}completions/", {"lesson": "nope"}).json() == []


# ------------------------------------------------------------------- the summary read


def test_the_summary_is_a_read_over_the_completions(people, path):
    client = _client(people["member"])
    empty = client.get(f"{API}summary/").json()
    assert empty["xp"] == 0 and empty["level"] == 1 and empty["level_floor"] == 0 and empty["next_level_at"] == 50
    assert empty["exercises_done"] == 0 and empty["lessons_done"] == 0

    session = _session(client)
    for slug, score in (("a-one", 100), ("a-two", 100), ("a-challenge", 100)):
        _take(client, session, path, exercise=slug, score=score)
    summary = client.get(f"{API}summary/").json()
    assert summary["xp"] == 20 + 30 + 15
    assert summary["level"] == 2 and summary["level_floor"] == 50 and summary["next_level_at"] == 150
    assert summary["exercises_done"] == 3
    assert summary["lessons_done"] == 1
    assert summary["lessons_total"] == 4, "the published lessons, not the draft"


def test_the_summary_counts_only_the_signed_in_players_work(people, path):
    other = _client(people["other"])
    _take(other, _session(other), path, exercise="a-one", score=100)
    assert _client(people["member"]).get(f"{API}summary/").json()["xp"] == 0


def test_the_summary_is_not_writable_and_is_behind_the_gate(people):
    member = _client(people["member"])
    assert member.post(f"{API}summary/", {"xp": 1000}, content_type="application/json").status_code == 405
    assert _client(people["stranger"]).get(f"{API}summary/").status_code == 200, "anyone signed in has a summary of their own"
    assert _client(people["stranger"]).post(f"{API}summary/", {"xp": 1000}, content_type="application/json").status_code == 405
    assert _client(None).get(f"{API}summary/").status_code in (401, 403)


def test_every_derived_read_uses_the_player_permission():
    from improv import api
    from improv.permissions import IsPlayer

    assert api.DERIVED, "the summary is a derived read"
    for name, view in api.DERIVED.items():
        assert list(view.permission_classes) == [IsPlayer], name


# ------------------------------------------------------- unlocks, as reads on the API


def _states(client):
    return {row["slug"]: row for row in client.get(f"{API}lessons/").json()}


def test_a_lesson_is_open_ahead_or_done_for_this_player(people, path):
    client = _client(people["member"])
    states = _states(client)
    assert states["lesson-a"]["state"] == "open"
    assert states["lesson-b"]["state"] == "ahead"
    assert states["lesson-c"]["state"] == "ahead"
    assert states["lesson-d"]["state"] == "ahead"
    assert states["lesson-a"]["exercises_done"] == 0 and states["lesson-a"]["exercises_total"] == 2

    session = _session(client)
    _take(client, session, path, exercise="a-one", score=100)
    states = _states(client)
    assert states["lesson-a"]["state"] == "open" and states["lesson-a"]["exercises_done"] == 1
    assert states["lesson-b"]["state"] == "ahead"

    _take(client, session, path, exercise="a-two", score=100)
    states = _states(client)
    assert states["lesson-a"]["state"] == "done"
    assert states["lesson-b"]["state"] == "open"
    assert states["lesson-c"]["state"] == "open"


def test_a_lesson_with_nothing_to_play_does_not_hold_up_the_next(people, path):
    client = _client(people["member"])
    session = _session(client)
    _take(client, session, path, exercise="a-one", score=100)
    _take(client, session, path, exercise="a-two", score=100)
    states = _states(client)
    assert states["lesson-c"]["exercises_total"] == 0
    assert states["lesson-c"]["state"] == "open", "nothing to play is never 'done', so it is read, not ticked off"
    assert states["lesson-d"]["state"] == "open", "and it does not lock the lesson that follows it"


def test_one_player_finishing_a_lesson_unlocks_nothing_for_another(people, path):
    other = _client(people["other"])
    session = _session(other)
    _take(other, session, path, exercise="a-one", score=100)
    _take(other, session, path, exercise="a-two", score=100)
    assert _states(_client(people["member"]))["lesson-b"]["state"] == "ahead"
    assert _states(other)["lesson-b"]["state"] == "open"


def test_an_exercise_says_whether_it_is_done_and_whether_it_is_ahead(people, path):
    client = _client(people["member"])
    _take(client, _session(client), path, exercise="a-one", score=100)
    rows = {row["slug"]: row for row in client.get(f"{API}exercises/").json()}
    assert rows["a-one"]["completed"] is True and rows["a-one"]["ahead"] is False
    assert rows["a-two"]["completed"] is False and rows["a-two"]["ahead"] is False
    assert rows["b-one"]["ahead"] is True
    assert rows["a-challenge"]["ahead"] is False and rows["a-challenge"]["completed"] is False


def test_the_detail_reads_say_it_too(people, path):
    client = _client(people["member"])
    assert client.get(f"{API}lessons/{path['b'].pk}/").json()["state"] == "ahead"
    assert client.get(f"{API}exercises/{path['b1'].pk}/").json()["ahead"] is True


# ----------------------------------------------------------------- admin, pages, docs


def test_completions_are_in_the_admin_for_reading_not_for_making():
    from django.contrib import admin

    model_admin = admin.site._registry[Completion]
    assert model_admin.has_add_permission(None) is False


def test_the_lesson_pages_know_the_summary_endpoint(people, path):
    for url in ("/improv/lessons/", "/improv/lessons/lesson-a/"):
        html = _client(people["member"]).get(url).content.decode()
        assert 'data-api-summary="/improv/api/summary/"' in html, url


def test_the_docs_say_what_was_built():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/completions/" in api and "/improv/api/summary/" in api
    assert "xp_awarded" in api and "level_floor" in api
    data_model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "Added after approval, SPR-I.5.2" in data_model
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.5\.2 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)


def test_the_progress_words_pass_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri52.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


def test_the_pages_show_progress_from_what_the_server_says_and_award_nothing_themselves():
    play = Path("static/improv/play-page.js").read_text(encoding="utf-8")
    assert "P.completionNote(saved)" in play and "P.exerciseGoalLine(" in play
    lessons = Path("static/improv/lessons-page.js").read_text(encoding="utf-8")
    assert "L.stateLabel(lesson)" in lessons and "L.levelLine(summary)" in lessons
    lesson = Path("static/improv/lesson-page.js").read_text(encoding="utf-8")
    assert "L.exerciseMark(ex)" in lesson
    for text in (play, lessons, lesson):
        code = re.sub(r"//[^\n]*", "", text)
        assert "xp_awarded:" not in code, "a page must not write a completion"
        assert "api-completions" not in code and "apiCompletions" not in code
