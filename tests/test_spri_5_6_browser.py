"""SPR-I.5.6 improv: where to work and the Challenges screen, in a real browser.

The report and the bests are proved by the sibling file and the words by the Node tests. What they
cannot see is the screens drawing them: the panel that says how many notes it still needs, the
claim with a working Play link, and the Challenges list with its bests.

Traces: spec ch. 6 (the weakness report, challenges), backlog SPR-I.5.6.
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

pytestmark = [pytest.mark.spri56, pytest.mark.django_db]

PASSWORD = "spri56-browser-9120"


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
    user = User.objects.create_user("p56browser", password=PASSWORD)
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


def _take(player, exercise=None, score=None, **metrics):
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    chart = exercise.progression if exercise else __import__("improv.models", fromlist=["Progression"]).Progression.objects.get(slug="ii-v-i-major")
    return Take.objects.create(
        player=player, session=session, progression=chart, exercise=exercise, chart=chart.chart, home_key=chart.home_key,
        key=exercise.key if exercise else "C", tempo=exercise.tempo if exercise else 90, loop_from=0,
        loop_to=exercise.bars if exercise else 4, started_at=timezone.now(), duration_ms=10000,
        bars=exercise.bars if exercise else 4, score=score, metrics=metrics, judge_version=1,
    )


def _progress(page, base):
    page.goto(f"{base}/improv/progress/", wait_until="domcontentloaded")
    page.wait_for_function("!document.getElementById('weakness-status').textContent.startsWith('Reading')", timeout=10000)


def _challenges(page, base):
    page.goto(f"{base}/improv/challenges/", wait_until="domcontentloaded")
    page.wait_for_selector("#challenges-list .im-take", timeout=10000)


def test_a_new_player_is_told_how_many_notes_it_needs_and_nothing_else(world):
    page, errors, player, base = world
    _progress(page, base)
    assert page.locator("#weakness-status").inner_text() == (
        "No notes in the last 30 days yet. Play 20 over the band and it will say where to work."
    )
    assert page.locator("#weakness-list .im-take").count() == 0
    assert not errors, errors


def test_some_notes_but_not_enough_says_how_many_more(world):
    page, errors, player, base = world
    _take(player, notes=12, withinPct=10, chordTonePct=5, outsidePct=90)
    _progress(page, base)
    assert page.locator("#weakness-status").inner_text() == (
        "So far 12 of the 20 notes it needs from the last 30 days. Play 8 more and it will say where to work."
    )
    assert page.locator("#weakness-list .im-take").count() == 0
    assert not errors, errors


def test_a_weak_area_is_named_with_a_play_link_that_opens_the_exercise(world):
    page, errors, player, base = world
    _take(player, notes=40, withinPct=30, chordTonePct=60, outsidePct=5)
    _progress(page, base)
    assert page.locator("#weakness-status").inner_text() == "Where to work, from the last 30 days:"
    claims = page.locator("#weakness-list .im-take")
    assert claims.count() == 1
    claim = claims.nth(0)
    assert claim.get_attribute("data-area") == "timing"
    assert "Timing: 30% of your notes were close to the beat." in claim.inner_text()
    assert "From 40 notes." in claim.inner_text()
    link = claim.locator("a")
    assert link.inner_text() == "Work on it: A bossa rhythm over the two five one"
    assert link.get_attribute("href") == "/improv/play/?exercise=challenge-bossa-rhythm"
    link.click()
    page.wait_for_url("**/improv/play/?exercise=challenge-bossa-rhythm", timeout=10000)
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    assert not errors, errors


def test_the_challenges_screen_lists_every_challenge_unplayed(world):
    page, errors, player, base = world
    _challenges(page, base)
    items = page.locator("#challenges-list .im-take")
    assert items.count() == Exercise.objects.filter(lesson__isnull=True).count() == 5
    assert page.locator("#challenges-status").inner_text() == "0 of 5 challenges passed."
    first = items.nth(0)
    assert "Not played yet. Pass mark" in first.inner_text()
    assert first.locator("a").inner_text() == "Play"
    assert first.locator("a").get_attribute("href") == f"/improv/play/?exercise={first.get_attribute('data-exercise')}"
    assert page.locator("#lessons-bests .im-take").count() == 0
    assert page.locator("#lessons-bests-empty").is_visible()
    assert page.locator("#challenges-empty").is_hidden()
    assert not errors, errors


def test_a_pass_shows_the_best_the_tries_and_a_replay_link(world):
    page, errors, player, base = world
    challenge = Exercise.objects.get(slug="challenge-turnaround-scale")
    _take(player, exercise=challenge, score=60)
    _take(player, exercise=challenge, score=88)
    _take(player, exercise=challenge, score=71)
    _challenges(page, base)
    row = page.locator("#challenges-list .im-take[data-exercise='challenge-turnaround-scale']")
    assert row.get_attribute("data-passed") == "yes"
    assert "Best 88, past the 75 mark. 3 tries" in row.inner_text()
    assert "Passed" in row.inner_text()
    assert row.locator("a").inner_text() == "Play again"
    assert page.locator("#challenges-status").inner_text() == "1 of 5 challenges passed."
    assert not errors, errors


def test_a_lesson_exercise_that_was_played_shows_among_the_bests(world):
    page, errors, player, base = world
    exercise = Exercise.objects.filter(lesson__isnull=False).order_by("id").first()
    _take(player, exercise=exercise, score=55)
    _challenges(page, base)
    page.wait_for_selector("#lessons-bests .im-take", timeout=10000)
    row = page.locator("#lessons-bests .im-take").nth(0)
    assert row.get_attribute("data-exercise") == exercise.slug
    assert "Best 55. Pass mark" in row.inner_text()
    assert page.locator("#lessons-bests-empty").is_hidden()
    assert not errors, errors


def test_the_menu_reaches_the_challenges_screen(world):
    page, errors, player, base = world
    page.goto(f"{base}/improv/practice/", wait_until="domcontentloaded")
    page.locator("a.im-nav-link", has_text="Challenges").click()
    page.wait_for_url("**/improv/challenges/", timeout=10000)
    page.wait_for_selector("#challenges-list .im-take", timeout=10000)
    assert not errors, errors
