"""SPR-I.6.1 improv: the Today and Progress screens in a real browser.

The reads are proved by the sibling file and the words by the Node tests. What they cannot see is
the screens drawing them: the ring, the three workout Play links, the button into the lesson, the
level bar, the calendar cells and the best takes.

Traces: spec ch. 8 (Today, Progress), backlog SPR-I.6.1.
"""

import datetime as dt
import io
import os
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv import progress
from improv.models import Completion, Exercise, Player, PracticeSession, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri61, pytest.mark.django_db]

PASSWORD = "spri61-browser-5530"
UTC = dt_timezone.utc


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
    user = User.objects.create_user("p61browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
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


def _sit(player, seconds, days_ago=0):
    row = PracticeSession.objects.create(player=player, active_seconds=seconds)
    if days_ago:
        day = timezone.now().astimezone(UTC).date() - dt.timedelta(days=days_ago)
        PracticeSession.objects.filter(pk=row.pk).update(started_at=dt.datetime(day.year, day.month, day.day, 12, tzinfo=UTC))
    return row


def _take(player, exercise, score):
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    chart = exercise.progression
    return Take.objects.create(
        player=player, session=session, progression=chart, exercise=exercise, chart=chart.chart, home_key=chart.home_key,
        key=exercise.key, tempo=exercise.tempo, loop_from=0, loop_to=exercise.bars, started_at=timezone.now(),
        duration_ms=10000, bars=exercise.bars, score=score, metrics={"notes": 30}, judge_version=1,
    )


def _today(page, base):
    page.goto(f"{base}/improv/", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('continue-line').textContent !== ''", timeout=10000)
    page.wait_for_function("document.getElementById('today-level').textContent !== ''", timeout=10000)


def _progress(page, base):
    page.goto(f"{base}/improv/progress/", wait_until="domcontentloaded")
    page.wait_for_function("!document.getElementById('bests-status').textContent.startsWith('Reading')", timeout=10000)
    page.wait_for_selector("#progress-calendar .im-cal-day", timeout=10000)


def test_a_new_player_sees_an_empty_ring_the_workout_and_the_first_lesson(world):
    page, errors, player, base = world
    _today(page, base)
    assert page.locator("#today-ring-label").inner_text() == "0 of 15 min"
    assert page.locator("#today-ring").get_attribute("data-met") == "no"
    assert page.locator("#today-ring").evaluate("e => e.style.getPropertyValue('--pct')") == "0"
    assert page.locator("#today-goal").inner_text() == "Today: 0 of 15 minutes."
    assert page.locator("#today-streak").inner_text().startswith("No streak yet")
    assert page.locator("#today-level").inner_text().startswith("Level 1, 0 XP")
    assert page.locator("#workout-list .im-take").count() == 3, "the workout is three exercises"
    assert page.locator("#workout-empty").is_hidden()
    first = page.locator("#continue-line").inner_text()
    assert first.startswith("Next up: ")
    link = page.locator("#continue-link")
    assert link.is_visible() and link.inner_text() == "Start"
    assert link.get_attribute("href").startswith("/improv/lessons/")
    assert not errors, errors


def test_the_workout_play_links_open_the_play_screen_on_that_exercise(world):
    page, errors, player, base = world
    _today(page, base)
    item = page.locator("#workout-list .im-take").nth(0)
    slug = item.get_attribute("data-exercise")
    href = item.locator("a.im-btn").get_attribute("href")
    assert href.startswith("/improv/play/") and slug in href
    item.locator("a.im-btn").click()
    page.wait_for_url(f"**{href}", timeout=10000)
    assert not errors, errors


def test_minutes_played_fill_the_ring_and_meeting_the_goal_says_so(world):
    page, errors, player, base = world
    _sit(player, 450)
    _today(page, base)
    assert page.locator("#today-ring-label").inner_text() == "7 of 15 min"
    assert page.locator("#today-ring").evaluate("e => e.style.getPropertyValue('--pct')") == "50"
    _sit(player, 600)
    _today(page, base)
    assert page.locator("#today-ring-label").inner_text() == "Goal met"
    assert page.locator("#today-ring").get_attribute("data-met") == "yes"
    assert page.locator("#today-ring").evaluate("e => e.style.getPropertyValue('--pct')") == "100"
    assert not errors, errors


def test_a_lesson_begun_offers_continue_and_the_button_opens_it(world):
    page, errors, player, base = world
    slug = progress.continue_lesson(player)["lesson"]
    exercise = Exercise.objects.filter(lesson__slug=slug).order_by("order").first()
    assert Exercise.objects.filter(lesson__slug=slug).count() > 1
    Completion.objects.create(player=player, exercise=exercise, xp_awarded=exercise.xp)
    _today(page, base)
    link = page.locator("#continue-link")
    assert link.inner_text() == "Continue"
    assert "passed." in page.locator("#continue-line").inner_text()
    assert page.locator("#today-level").inner_text().startswith(f"Level ")
    link.click()
    page.wait_for_url("**/improv/lessons/**", timeout=10000)
    assert not errors, errors


def test_progress_draws_the_level_the_calendar_and_the_empty_lists(world):
    page, errors, player, base = world
    _progress(page, base)
    assert page.locator("#progress-level").inner_text().startswith("Level 1, 0 XP")
    assert page.locator("#progress-xp").is_visible()
    assert page.locator("#progress-calendar .im-cal-head").count() == 7
    assert page.locator("#progress-calendar .im-cal-day").count() == 35
    assert page.locator('#progress-calendar .im-cal-day[data-today="yes"]').count() == 1
    assert page.locator("#progress-calendar-line").inner_text().endswith("met the goal.")
    assert page.locator("#bests-empty").is_visible()
    assert page.locator("#bests-list .im-take").count() == 0
    assert "No notes in the last 30 days yet" in page.locator("#weakness-status").inner_text()
    assert not errors, errors


def test_the_calendar_marks_the_days_met_practised_and_resting(world):
    page, errors, player, base = world
    _sit(player, 20 * 60, days_ago=1)
    _sit(player, 5 * 60, days_ago=2)
    _progress(page, base)
    state = lambda ago: page.locator(  # noqa: E731
        f'#progress-calendar .im-cal-day[data-date="{(timezone.now().astimezone(UTC).date() - dt.timedelta(days=ago)).isoformat()}"]'
    ).get_attribute("data-state")
    assert state(1) == "met"
    assert state(2) == "practised"
    assert state(3) == "rest"
    today = page.locator('#progress-calendar .im-cal-day[data-today="yes"]')
    assert today.get_attribute("aria-label")
    assert "1 of the last" in page.locator("#progress-calendar-line").inner_text()
    assert not errors, errors


def test_the_best_takes_are_listed_highest_first_with_a_cap_of_five(world):
    page, errors, player, base = world
    exercises = list(Exercise.objects.order_by("pk")[:7])
    assert len(exercises) == 7
    for n, exercise in enumerate(exercises):
        _take(player, exercise, 50 + n * 5)
    _progress(page, base)
    cards = page.locator("#bests-list .im-take")
    assert cards.count() == 5
    assert cards.nth(0).get_attribute("data-exercise") == exercises[6].slug
    assert page.locator("#bests-empty").is_hidden()
    assert not errors, errors
