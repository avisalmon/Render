"""SPR-I.5.4 improv: the practice timer and the practice log, in a real browser.

The server's reading of the log is proved by the sibling file and the clock's arithmetic by the Node
tests. What they cannot see is the page really counting while the band runs or a note is played,
reporting it to the open sitting, saying where today stands on the Play screen, and the Practice
screen drawing the streak and the days from what the server read.

Traces: spec ch. 6 (the practice timer, streak, daily goal), backlog SPR-I.5.4.
"""

import datetime as dt
import io
import os
import time

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Player, PracticeSession

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri54, pytest.mark.django_db]

PASSWORD = "spri54-browser-6620"
UTC = dt.timezone.utc

FAKE_WORLD = """
(() => {
  const access = { inputs: new Map(), outputs: new Map(), onstatechange: null };
  const port = { id: "piano", name: "Clavinova", state: "connected", type: "input", onmidimessage: null };
  access.inputs.set("piano", port);
  navigator.requestMIDIAccess = async () => access;
  const C = window.AudioContext || window.webkitAudioContext;
  C.prototype.getOutputTimestamp = function () {
    return { contextTime: this.currentTime, performanceTime: performance.now() };
  };
  window.__piano = {
    press(note) { port.onmidimessage({ data: new Uint8Array([0x90, note, 90]), timeStamp: performance.now() }); },
    release(note) { port.onmidimessage({ data: new Uint8Array([0x80, note, 0]), timeStamp: performance.now() }); },
  };
})();
"""


@pytest.fixture(scope="module")
def browser(django_db_setup):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def world(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p54browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    player, _ = Player.objects.get_or_create(user=user)
    player.timezone = "UTC"
    player.save()

    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    context.add_init_script(FAKE_WORLD)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, user, player, live_server.url
    context.close()


def _play(page, base):
    page.goto(f"{base}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    page.wait_for_function("document.getElementById('midi-state').textContent.startsWith('Listening to')", timeout=10000)
    page.select_option("#progression", "ii-v-i-major")
    page.select_option("#countin", "0")


def _wait_for(condition, seconds=8):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return False


def test_the_band_running_counts_and_stopping_reports_it_at_once(world):
    page, errors, user, player, base = world
    _play(page, base)
    page.click("#play-toggle")
    page.wait_for_selector('.im-bar-lit[data-bar="0"]', timeout=8000)
    page.wait_for_timeout(2500)
    page.click("#play-toggle")
    assert _wait_for(lambda: PracticeSession.objects.filter(player=player, active_seconds__gte=2).exists()), (
        "stopping reports the seconds the band ran without waiting for the thirty-second beat"
    )
    page.wait_for_function("document.getElementById('practice-line').textContent.startsWith('Today: ')", timeout=8000)
    assert "of 15 minutes" in page.locator("#practice-line").inner_text()
    assert not errors, errors


def test_a_note_played_with_the_band_stopped_opens_a_sitting_and_counts_a_few_seconds(world):
    page, errors, user, player, base = world
    _play(page, base)
    assert not PracticeSession.objects.exists()
    page.evaluate("window.__piano.press(60)")
    assert _wait_for(lambda: PracticeSession.objects.filter(player=player).exists()), "a note opens the sitting"
    page.wait_for_timeout(1600)
    page.goto("about:blank")
    sitting = PracticeSession.objects.get(player=player)
    assert _wait_for(lambda: PracticeSession.objects.get(pk=sitting.pk).ended_at is not None), "leaving closes it"
    sitting.refresh_from_db()
    assert 1 <= sitting.active_seconds <= 10, "a note counts for its own ten seconds at most"
    assert not errors, errors


def test_a_tab_left_open_with_nothing_happening_counts_nothing(world):
    page, errors, user, player, base = world
    _play(page, base)
    page.wait_for_timeout(1500)
    assert not PracticeSession.objects.exists(), "opening the page is not practice"
    assert not errors, errors


def test_the_practice_screen_shows_today_the_streak_and_the_days(world):
    page, errors, user, player, base = world
    today = timezone.now().astimezone(UTC).date()
    for ago, minutes in ((1, 16), (2, 15), (3, 20), (6, 5)):
        day = today - dt.timedelta(days=ago)
        row = PracticeSession.objects.create(player=player, active_seconds=minutes * 60)
        PracticeSession.objects.filter(pk=row.pk).update(started_at=dt.datetime(day.year, day.month, day.day, 12, tzinfo=UTC))
    row = PracticeSession.objects.create(player=player, active_seconds=5 * 60)
    PracticeSession.objects.filter(pk=row.pk).update(started_at=dt.datetime(today.year, today.month, today.day, 0, 1, tzinfo=UTC))

    page.goto(f"{base}/improv/practice/", wait_until="domcontentloaded")
    page.wait_for_selector("#practice-log .im-take", timeout=10000)
    assert page.locator("#practice-goal").inner_text() == "Today: 5 of 15 minutes."
    assert page.locator("#practice-streak").inner_text() == "Streak: 3 days. Meet the goal today to keep it."
    assert "UTC" in page.locator("#practice-zone").inner_text()
    assert page.locator("#practice-log .im-take").count() == 5
    assert page.locator('#practice-log .im-take[data-met="yes"]').count() == 3
    assert page.locator("#practice-empty").is_hidden()
    assert not errors, errors


def test_a_new_player_sees_an_empty_log_and_no_streak(world):
    page, errors, user, player, base = world
    page.goto(f"{base}/improv/practice/", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('practice-goal').textContent !== ''", timeout=10000)
    assert page.locator("#practice-goal").inner_text() == "Today: 0 of 15 minutes."
    assert page.locator("#practice-streak").inner_text().startswith("No streak yet")
    assert page.locator("#practice-empty").is_visible()
    assert not errors, errors
