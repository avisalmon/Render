"""SPR-I.5.5 improv: the daily workout on the Practice screen, in a real browser.

The picks are proved by the sibling file and the words by the Node tests. What they cannot see is
the screen drawing the three with a reason and a working Play link, marking one done after a pass,
and keeping the same three after a reload.

Traces: spec ch. 6 (the daily workout), backlog SPR-I.5.5.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Exercise, Player, PracticeSession, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri55, pytest.mark.django_db]

PASSWORD = "spri55-browser-4471"


@pytest.fixture(scope="module")
def browser(django_db_setup):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch()
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def world(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p55browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons"):
        call_command(command, stdout=io.StringIO())
    player, _ = Player.objects.get_or_create(user=user)

    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, player, live_server.url
    context.close()


def _open(page, base):
    page.goto(f"{base}/improv/practice/", wait_until="domcontentloaded")
    page.wait_for_selector("#workout-list .im-take", timeout=10000)


def test_a_new_player_sees_the_workout_with_a_reason_and_a_play_link_for_each(world):
    page, errors, player, base = world
    _open(page, base)
    items = page.locator("#workout-list .im-take")
    assert items.count() == 2, "a new player has two seeded exercises that are open and marked for the workout"
    assert page.locator("#workout-status").inner_text() == "Today's workout: 0 of 2 done."
    first = items.nth(0)
    assert first.get_attribute("data-slot") == "next"
    assert "Next in your lessons. Worth" in first.inner_text()
    link = first.locator("a")
    assert link.inner_text() == "Play"
    assert link.get_attribute("href") == f"/improv/play/?exercise={first.get_attribute('data-exercise')}"
    assert page.locator("#workout-empty").is_hidden()
    assert not errors, errors


def test_the_same_picks_show_after_a_reload(world):
    page, errors, player, base = world
    _open(page, base)
    before = page.locator("#workout-list .im-take").evaluate_all("els => els.map(e => e.dataset.exercise)")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#workout-list .im-take", timeout=10000)
    after = page.locator("#workout-list .im-take").evaluate_all("els => els.map(e => e.dataset.exercise)")
    assert before == after
    assert not errors, errors


def test_a_pass_today_marks_it_done_and_changes_nothing_else(world):
    page, errors, player, base = world
    _open(page, base)
    before = page.locator("#workout-list .im-take").evaluate_all("els => els.map(e => e.dataset.exercise)")

    exercise = Exercise.objects.get(slug=before[0])
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    Take.objects.create(
        player=player, session=session, progression=exercise.progression, exercise=exercise, chart=exercise.progression.chart,
        home_key=exercise.progression.home_key, key=exercise.key, tempo=exercise.tempo, loop_from=0, loop_to=exercise.bars,
        started_at=timezone.now(), duration_ms=10000, bars=exercise.bars, score=95, judge_version=1,
    )

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#workout-list .im-take", timeout=10000)
    after = page.locator("#workout-list .im-take").evaluate_all("els => els.map(e => e.dataset.exercise)")
    assert after == before
    assert page.locator("#workout-list .im-take").nth(0).get_attribute("data-done") == "yes"
    assert page.locator("#workout-list .im-take").nth(0).locator("a").inner_text() == "Play again"
    assert page.locator("#workout-status").inner_text() == "Today's workout: 1 of 2 done."
    assert not errors, errors


def test_the_play_link_opens_the_exercise_on_the_play_screen(world):
    page, errors, player, base = world
    _open(page, base)
    slug = page.locator("#workout-list .im-take").nth(0).get_attribute("data-exercise")
    page.locator("#workout-list .im-take").nth(0).locator("a").click()
    page.wait_for_url(f"**/improv/play/?exercise={slug}", timeout=10000)
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    assert not errors, errors


def test_a_player_with_nothing_unlocked_sees_the_empty_note(world):
    page, errors, player, base = world
    Exercise.objects.update(daily_eligible=False)
    page.goto(f"{base}/improv/practice/", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('workout-status').textContent.startsWith('Nothing to pick')", timeout=10000)
    assert page.locator("#workout-empty").is_visible()
    assert page.locator("#workout-list .im-take").count() == 0
    assert not errors, errors
