"""SPR-I.10.1 improv: start anywhere. Nothing is locked, and the player carries a pointer in the path.

Avi, 2026-10-09: "give the opportunity to unlock any lesson that the user would like to start from and
just continue from the spot that he chose. If he decides to go back or jump ahead, you will let him,
but the progress will keep on going from the new point."

A lesson whose prerequisite is unfinished is "ahead", not shut: a take there counts like any other and
moves the pointer there. Start here on a lesson page moves it too. Today and Continue follow the
pointer, then the path after it, then whatever is left. Everything up to the pointer is open.

Traces: spec ch. 6 "The path" and "Start anywhere", data model (Player.current_lesson, Lesson.path_order),
api.md "Start here", backlog SPR-I.10.1.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv import progress
from improv.models import Completion, Exercise, Lesson, Player, Progression

pytestmark = [pytest.mark.spri101, pytest.mark.django_db]

API = "/improv/api/"
PASSWORD = "spri101-pass-7731"


@pytest.fixture
def path(db):
    """Four lessons in path order: a, then b (after a), c (after a), d (after c). Plus a draft and a challenge."""
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    iivi = Progression.objects.get(slug="ii-v-i-major")

    def lesson(track, order, slug, position, **more):
        return Lesson.objects.create(
            track=track, order=order, title=slug.title(), slug=slug, summary="s", explanation="e", progression=iivi,
            style=iivi.default_style, path_order=position, status=more.pop("status", "published"), **more,
        )

    def exercise(les, order, slug, **more):
        values = dict(
            lesson=les, order=order, slug=slug, title=slug.title(), instructions="i", progression=iivi, key="C", tempo=90,
            bars=4, scoring_kind="scale_only", scoring_params={}, pass_score=70, xp=20, daily_eligible=True,
        )
        values.update(more)
        return Exercise.objects.create(**values)

    a = lesson("chord_tones", 1, "lesson-a", 1)
    b = lesson("guide_tones", 1, "lesson-b", 2, prerequisite=a)
    c = lesson("scales_modes", 1, "lesson-c", 3, prerequisite=a)
    d = lesson("approach_notes", 1, "lesson-d", 4, prerequisite=c)
    draft = lesson("rhythm_motifs", 1, "lesson-draft", 5, status="draft")
    return dict(
        iivi=iivi, a=a, b=b, c=c, d=d, draft=draft,
        a1=exercise(a, 1, "a-one"), a2=exercise(a, 2, "a-two"),
        b1=exercise(b, 1, "b-one", xp=40), c1=exercise(c, 1, "c-one"), d1=exercise(d, 1, "d-one"),
        challenge=exercise(None, 1, "a-challenge", xp=15),
    )


@pytest.fixture
def me(path):
    user = User.objects.create_user("p101", email="p101@example.com", password=PASSWORD)
    client = Client()
    client.force_login(user)
    return user, client


def _player(user):
    return Player.objects.get_or_create(user=user)[0]


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def _session(client):
    return _json(client, "post", f"{API}sessions/").json()["id"]


def _take(client, session, path, exercise, score=90):
    iivi = path["iivi"]
    body = {
        "session": session, "progression": iivi.pk, "style": iivi.default_style_id, "exercise": exercise,
        "chart": iivi.chart, "home_key": iivi.home_key, "key": "C", "time_signature": "4/4", "tempo": 90,
        "swing_ratio": "0.67", "loop_from": 0, "loop_to": 4, "started_at": timezone.now().isoformat(),
        "duration_ms": 10000, "bars": 4,
        "events": [{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 300, "type": "off", "note": 62, "velocity": 0}],
        "score": score, "metrics": {"notes": 1}, "judge_version": 1,
    }
    return _json(client, "post", f"{API}takes/", body)


def _states(client):
    return {row["slug"]: row for row in client.get(f"{API}lessons/").json()}


def _start_here(client, slug):
    return _json(client, "post", f"{API}start-here/", {"lesson": slug})


# ------------------------------------------------------------------ nothing is locked


def test_a_player_starts_with_no_pointer(me):
    user, _ = me
    assert _player(user).current_lesson is None


def test_a_lesson_whose_prerequisite_is_unfinished_is_ahead_not_locked(me):
    _, client = me
    states = _states(client)
    assert states["lesson-a"]["state"] == "open"
    assert {states[s]["state"] for s in ("lesson-b", "lesson-c", "lesson-d")} == {"ahead"}
    assert "locked" not in {row["state"] for row in states.values()}


def test_a_take_in_a_lesson_ahead_counts_all_the_same(me, path):
    _, client = me
    made = _take(client, _session(client), path, "b-one", score=100)
    assert made.status_code == 201
    assert made.json()["completion"]["xp_awarded"] == 40
    assert Completion.objects.get().exercise == path["b1"]


def test_an_exercise_row_says_ahead_and_never_locked(me):
    _, client = me
    rows = {row["slug"]: row for row in client.get(f"{API}exercises/").json()}
    assert rows["a-one"]["ahead"] is False
    assert rows["b-one"]["ahead"] is True
    assert rows["a-challenge"]["ahead"] is False
    assert "locked" not in rows["b-one"]


# -------------------------------------------------------------------- the pointer


def test_playing_an_exercise_moves_the_pointer_to_its_lesson(me, path):
    user, client = me
    _take(client, _session(client), path, "c-one", score=10)
    assert _player(user).current_lesson == path["c"]
    assert client.get(f"{API}continue/").json()["lesson"] == "lesson-c"


def test_a_free_take_or_a_challenge_moves_nothing(me, path):
    user, client = me
    session = _session(client)
    _take(client, session, path, None)
    _take(client, session, path, "a-challenge", score=100)
    assert _player(user).current_lesson is None


def test_start_here_points_the_player_at_a_lesson_and_answers_with_where_to_continue(me, path):
    user, client = me
    reply = _start_here(client, "lesson-d")
    assert reply.status_code == 200, reply.content
    assert reply.json()["lesson"] == "lesson-d" and reply.json()["state"] == "start"
    assert _player(user).current_lesson == path["d"]
    assert client.get(f"{API}continue/").json()["lesson"] == "lesson-d"


def test_the_pointer_opens_everything_before_it(me):
    _, client = me
    _start_here(client, "lesson-d")
    states = _states(client)
    assert {states[s]["state"] for s in ("lesson-a", "lesson-b", "lesson-c", "lesson-d")} == {"open"}
    assert states["lesson-d"]["current"] is True
    assert [s for s, row in states.items() if row["current"]] == ["lesson-d"]


def test_going_back_moves_the_pointer_back_and_the_later_lesson_is_ahead_again(me):
    _, client = me
    _start_here(client, "lesson-d")
    _start_here(client, "lesson-a")
    states = _states(client)
    assert states["lesson-a"]["current"] is True
    assert states["lesson-d"]["state"] == "ahead"


def test_start_here_refuses_what_it_should(me, path):
    _, client = me
    assert _start_here(client, "no-such-lesson").status_code == 404
    assert _start_here(client, "lesson-draft").status_code == 404, "a draft is not there for anyone but the superuser"
    assert _json(client, "post", f"{API}start-here/", {}).status_code == 404
    assert client.get(f"{API}start-here/").status_code == 405
    assert Client().post(f"{API}start-here/", {"lesson": "lesson-a"}, content_type="application/json").status_code in (401, 403)


def test_the_superuser_may_start_at_a_draft(path):
    boss = User.objects.create_user("boss101", password=PASSWORD, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(boss)
    assert _start_here(client, "lesson-draft").status_code == 200


def test_the_pointer_is_the_players_own(me, path):
    _, client = me
    other = User.objects.create_user("p101other", password=PASSWORD)
    _start_here(client, "lesson-d")
    assert _player(other).current_lesson is None
    theirs = Client()
    theirs.force_login(other)
    assert _states(theirs)["lesson-d"]["state"] == "ahead"


# --------------------------------------------------------------------- continue


def test_continue_stays_on_the_pointer_while_it_has_exercises_to_pass(me, path):
    _, client = me
    _start_here(client, "lesson-c")
    assert client.get(f"{API}continue/").json() == {
        "state": "start", "lesson": "lesson-c", "title": "Lesson-C", "track": "scales_modes", "exercises_done": 0, "exercises_total": 1,
    }


def test_continue_moves_on_to_the_next_unfinished_lesson_after_the_pointer(me, path):
    _, client = me
    _start_here(client, "lesson-c")
    _take(client, _session(client), path, "c-one", score=100)
    got = client.get(f"{API}continue/").json()
    assert got["lesson"] == "lesson-d" and got["state"] == "start"


def test_after_the_end_of_the_path_what_is_left_before_the_pointer_comes_round(me, path):
    _, client = me
    session = _session(client)
    _start_here(client, "lesson-d")
    _take(client, session, path, "d-one", score=100)
    got = client.get(f"{API}continue/").json()
    assert got["lesson"] == "lesson-a", "nothing after d is left, so the earliest unfinished lesson"
    for slug in ("a-one", "a-two", "b-one", "c-one"):
        _take(client, session, path, slug, score=100)
    assert client.get(f"{API}continue/").json()["state"] == "finished"


def test_without_a_pointer_a_lesson_ahead_is_never_offered(me, path):
    _, client = me
    assert client.get(f"{API}continue/").json()["lesson"] == "lesson-a"


def test_a_begun_lesson_moves_the_pointer_so_continue_says_continue(me, path):
    _, client = me
    _take(client, _session(client), path, "a-one", score=100)
    got = client.get(f"{API}continue/").json()
    assert got["lesson"] == "lesson-a" and got["state"] == "continue" and got["exercises_done"] == 1


# -------------------------------------------------------------------- the path


def test_the_path_is_the_path_order_then_level_track_and_position(path):
    a, b, c, d = path["a"], path["b"], path["c"], path["d"]
    assert [l.slug for l in sorted([d, c, b, a], key=progress.path_key)] == ["lesson-a", "lesson-b", "lesson-c", "lesson-d"]
    Lesson.objects.filter(slug="lesson-d").update(path_order=None)
    Lesson.objects.filter(slug="lesson-a").update(path_order=None, level=2)
    rows = {l.slug: l for l in Lesson.objects.all()}
    ordered = [l.slug for l in sorted(rows.values(), key=progress.path_key)]
    assert ordered.index("lesson-b") < ordered.index("lesson-c") < ordered.index("lesson-draft")
    assert ordered.index("lesson-draft") < ordered.index("lesson-d") < ordered.index("lesson-a"), "unnumbered: level 1 before level 2"


def test_the_lessons_api_comes_in_path_order(me):
    _, client = me
    rows = client.get(f"{API}lessons/").json()
    assert [row["slug"] for row in rows] == ["lesson-a", "lesson-b", "lesson-c", "lesson-d"]
    assert [row["path_order"] for row in rows] == [1, 2, 3, 4]


def test_the_workout_pool_reaches_the_pointer_and_not_past_it(me, path):
    user, client = me
    player = _player(user)
    assert {e.slug for e in progress.open_exercises(player)} == {"a-one", "a-two", "a-challenge"}
    _start_here(client, "lesson-c")
    player.refresh_from_db()
    assert {e.slug for e in progress.open_exercises(player)} == {"a-one", "a-two", "b-one", "c-one", "a-challenge"}
    assert [e.slug for e in progress.open_exercises(player)][:4] == ["a-one", "a-two", "b-one", "c-one"], "in the order of the path"


def test_the_summary_counts_lessons_done_the_same_whatever_the_pointer(me, path):
    _, client = me
    _start_here(client, "lesson-d")
    _take(client, _session(client), path, "d-one", score=100)
    assert client.get(f"{API}summary/").json()["lessons_done"] == 1


# ---------------------------------------------------------------------- the pages


def test_the_lesson_page_offers_start_here_and_the_ahead_note(me):
    _, client = me
    html = client.get("/improv/lessons/lesson-d/").content.decode("utf-8")
    assert 'id="start-here"' in html and 'id="lesson-ahead"' in html and 'id="lesson-here"' in html
    assert 'data-api-start-here="/improv/api/start-here/"' in html
    assert re.search(r'data-csrf="[^"]+"', html)
    assert "lesson-lock" not in html


def test_the_lessons_page_tells_people_they_may_start_anywhere(me):
    _, client = me
    html = client.get("/improv/lessons/").content.decode("utf-8")
    assert "Start here" in html and "Today follows you" in html


def test_the_scripts_and_words_never_say_locked():
    for name in ("lessons.js", "lessons-page.js", "lesson-page.js"):
        source = Path("static/improv", name).read_text(encoding="utf-8")
        assert "locked" not in source.lower(), name
    play = Path("static/improv/play.js").read_text(encoding="utf-8")
    assert "exercise.ahead" in play and "exercise.locked" not in play
    assert "innerHTML" not in Path("static/improv/lesson-page.js").read_text(encoding="utf-8")


def test_start_here_posts_with_the_csrf_token_and_never_writes_markup():
    source = Path("static/improv/lesson-page.js").read_text(encoding="utf-8")
    assert "X-CSRFToken" in source and "apiStartHere" in source
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source


# ----------------------------------------------------------------------- the docs


def test_the_docs_and_the_backlog_say_so():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "Start here" in spec and "current_lesson" in spec and "ahead" in spec
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/start-here/" in api and '"ahead"' in api or "`ahead`" in api
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "current_lesson" in model and "path_order" in model
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.10\.1 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)


def test_the_path_words_pass_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri101.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]
