"""SPR-I.6.1 improv: the Today and Progress screens and the lesson to go on with.

Today is the landing page: the goal as a ring, the streak, the three workout exercises, and a way
back into the lesson in progress. Progress is level and XP, the practice calendar, where to work
and the best takes. Both read derived endpoints, and the one new read is `continue`, the lesson in
progress. The words and shapes are tested under Node (tests/js/spri61.test.js).

Traces: spec ch. 8 (Today, Progress), backlog SPR-I.6.1.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv import progress
from improv.models import Completion, Exercise, Lesson, Player, Progression

pytestmark = pytest.mark.spri61

PASSWORD = "spri61-pass-4410"
API = "/improv/api/"
KEYS = {"state", "lesson", "title", "track", "exercises_done", "exercises_total"}


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p61member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p61stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _player(user):
    return Player.objects.get_or_create(user=user)[0]


def _lesson(track, slug, order=1, exercises=2, **more):
    iivi = Progression.objects.get(slug="ii-v-i-major")
    lesson = Lesson.objects.create(
        track=track, order=order, title=slug.title(), slug=slug, summary="s", explanation="e", progression=iivi,
        status=more.pop("status", "published"), **more,
    )
    for n in range(1, exercises + 1):
        Exercise.objects.create(
            lesson=lesson, order=n, slug=f"{slug}-{n}", title=f"{slug} {n}", instructions="i", progression=iivi, key="C",
            tempo=90, bars=4, scoring_kind="scale_only", scoring_params={}, pass_score=70, xp=20,
        )
    return lesson


def _pass(player, lesson, count=None):
    for e in Exercise.objects.filter(lesson=lesson).order_by("order")[:count]:
        Completion.objects.create(player=player, exercise=e, xp_awarded=e.xp)


# ------------------------------------------------------------------ the lesson to go on with


def test_with_no_lessons_there_is_nothing_to_go_on_with(people):
    got = progress.continue_lesson(_player(people["member"]))
    assert got == {"state": "none", "lesson": None, "title": "", "track": "", "exercises_done": 0, "exercises_total": 0}


def test_a_new_player_starts_at_the_first_lesson_of_the_path(people):
    _lesson("guide_tones", "second-track", order=1)
    _lesson("chord_tones", "first-track", order=1)
    got = progress.continue_lesson(_player(people["member"]))
    assert got["state"] == "start" and got["lesson"] == "first-track"
    assert got["exercises_done"] == 0 and got["exercises_total"] == 2


def test_a_lesson_begun_is_continued(people):
    first = _lesson("chord_tones", "first", order=1)
    _lesson("chord_tones", "second", order=2, prerequisite=first)
    player = _player(people["member"])
    _pass(player, first, count=1)
    got = progress.continue_lesson(player)
    assert got["state"] == "continue" and got["lesson"] == "first"
    assert (got["exercises_done"], got["exercises_total"]) == (1, 2)
    assert set(got) == KEYS


def test_a_finished_lesson_moves_on_to_the_next_that_it_opens(people):
    first = _lesson("chord_tones", "first", order=1)
    _lesson("chord_tones", "second", order=2, prerequisite=first)
    player = _player(people["member"])
    _pass(player, first)
    got = progress.continue_lesson(player)
    assert got["state"] == "start" and got["lesson"] == "second"


def test_a_lesson_ahead_is_never_offered_before_the_player_goes_there(people):
    first = _lesson("chord_tones", "first", order=1)
    _lesson("chord_tones", "second", order=2, prerequisite=first)
    got = progress.continue_lesson(_player(people["member"]))
    assert got["lesson"] == "first"


def test_a_lesson_begun_comes_before_one_not_yet_started_even_when_later(people):
    a = _lesson("chord_tones", "a", order=1)
    b = _lesson("guide_tones", "b", order=1)
    player = _player(people["member"])
    _pass(player, b, count=1)
    got = progress.continue_lesson(player)
    assert got["state"] == "continue" and got["lesson"] == "b"
    assert a.slug == "a"


def test_a_draft_is_never_offered(people):
    _lesson("chord_tones", "draft", order=1, status="draft")
    _lesson("guide_tones", "real", order=1)
    assert progress.continue_lesson(_player(people["member"]))["lesson"] == "real"
    Lesson.objects.filter(slug="real").update(status="draft")
    assert progress.continue_lesson(_player(people["member"]))["state"] == "none"


def test_a_lesson_with_nothing_to_play_is_never_the_one_to_go_on_with(people):
    _lesson("chord_tones", "read-only", order=1, exercises=0)
    assert progress.continue_lesson(_player(people["member"]))["state"] == "none"
    _lesson("guide_tones", "playable", order=1)
    assert progress.continue_lesson(_player(people["member"]))["lesson"] == "playable"


def test_when_every_lesson_is_done_it_says_so(people):
    first = _lesson("chord_tones", "first", order=1)
    second = _lesson("chord_tones", "second", order=2, prerequisite=first)
    player = _player(people["member"])
    _pass(player, first)
    _pass(player, second)
    got = progress.continue_lesson(player)
    assert got["state"] == "finished" and got["lesson"] is None


def test_another_players_passes_do_not_move_mine(people):
    first = _lesson("chord_tones", "first", order=1)
    other = User.objects.create_user("p61other", password=PASSWORD)
    _pass(_player(other), first, count=1)
    got = progress.continue_lesson(_player(people["member"]))
    assert got["state"] == "start" and got["exercises_done"] == 0


def test_the_lessons_follow_the_tracks_in_their_order_not_the_alphabet(people):
    _lesson("approach_notes", "a-approach", order=1)
    _lesson("scales_modes", "z-scales", order=1)
    assert progress.continue_lesson(_player(people["member"]))["lesson"] == "z-scales"


# ------------------------------------------------------------------ the read


def test_the_continue_read_is_behind_the_gate_and_read_only(people):
    assert _client().get(API + "continue/").status_code in (401, 403)
    for who in ("member", "stranger"):
        client = _client(people[who])
        reply = client.get(API + "continue/")
        assert reply.status_code == 200 and set(reply.json()) == KEYS, who
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(API + "continue/").status_code == 405, (who, method)


def test_the_read_follows_the_player_over_the_api(people):
    first = _lesson("chord_tones", "first", order=1)
    member = _client(people["member"])
    assert member.get(API + "continue/").json()["state"] == "start"
    _pass(_player(people["member"]), first, count=1)
    body = member.get(API + "continue/").json()
    assert body["state"] == "continue" and body["exercises_done"] == 1


def test_the_read_makes_a_profile_for_a_first_visit(people):
    assert not Player.objects.filter(user=people["member"]).exists()
    assert _client(people["member"]).get(API + "continue/").status_code == 200


# ------------------------------------------------------------------ the pages


def test_today_is_the_landing_page_and_has_what_it_shows(people):
    html = _client(people["member"]).get("/improv/").content.decode("utf-8")
    for attribute in ("data-api-practice", "data-api-workout", "data-api-summary", "data-api-continue"):
        assert attribute in html, attribute
    assert 'data-api-continue="/improv/api/continue/"' in html
    for element_id in (
        "today-ring", "today-ring-label", "today-goal", "today-streak", "today-level",
        "workout-list", "workout-empty", "continue-line", "continue-link",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert "<h1 class=\"im-title\">Today</h1>" in html


def test_progress_has_what_it_shows(people):
    html = _client(people["member"]).get("/improv/progress/").content.decode("utf-8")
    for attribute in ("data-api-summary", "data-api-practice", "data-api-weakness", "data-api-bests"):
        assert attribute in html, attribute
    for element_id in (
        "progress-level", "progress-xp", "progress-lessons", "progress-streak", "progress-calendar", "progress-calendar-line",
        "weakness-status", "weakness-list", "bests-status", "bests-list", "bests-empty",
    ):
        assert f'id="{element_id}"' in html, element_id


def test_progress_is_for_anyone_signed_in_and_sends_a_visitor_to_the_front_door(people):
    visitor = _client().get("/improv/progress/")
    assert visitor.status_code == 302
    assert visitor.headers["Location"].startswith("/improv/?next=")
    assert _client(people["stranger"]).get("/improv/progress/").status_code == 200
    assert _client(people["member"]).get("/improv/progress/").status_code == 200


def test_the_menu_names_today_and_progress(people):
    html = _client(people["member"]).get("/improv/practice/").content.decode("utf-8")
    assert re.search(r'<a class="im-nav-link" href="/improv/">Today</a>', html)
    assert re.search(r'<a href="/improv/progress/">Progress</a>', html), "Progress is in the account menu"
    assert ">Home<" not in html


def test_the_practice_page_no_longer_carries_the_weakness_panel(people):
    html = _client(people["member"]).get("/improv/practice/").content.decode("utf-8")
    assert "weakness-status" not in html and "data-api-weakness" not in html


def test_the_page_scripts_hold_no_unsafe_dom_use():
    for name in ("today.js", "today-page.js", "progress-page.js", "bests.js"):
        source = Path("static/improv", name).read_text(encoding="utf-8")
        assert "innerHTML" not in source and "eval(" not in source, name


def test_the_words_live_in_a_file_that_touches_no_browser():
    source = Path("static/improv/today.js").read_text(encoding="utf-8")
    for api in ("document.", "window.", "fetch(", "localStorage"):
        assert api not in source, api


# ------------------------------------------------------------------ the docs


def test_the_docs_describe_the_read_and_the_screens_and_the_backlog_row_is_done():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    for needle in ("/improv/api/continue/", "/improv/progress/"):
        assert needle in api, needle
    assert "SPR-I.6.1" in Path("docs/improv/spec.md").read_text(encoding="utf-8")
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    row = next(line for line in backlog.splitlines() if line.startswith("| SPR-I.6.1 "))
    assert re.search(r"DONE \d{4}-\d{2}-\d{2}", row), row


def test_the_words_and_shapes_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri61.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
