"""SPR-I.7.1 improv: the top piano keys press buttons, in a real browser with a faked piano.

A fake MIDI input stands in for the keyboard: the test sends the bytes a piano would, through both
the `onmidimessage` property (what the Play and Setup screens use) and `addEventListener` (what the
control layer uses), so the two coexist exactly as they do on the real instrument.

Traces: spec ch. 8 "Two standing rules for every screen", backlog SPR-I.7.1 and SPR-I.7.2.
"""

import datetime as dt
import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Player, PracticeSession, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri71, pytest.mark.django_db]

PASSWORD = "spri71-browser-3318"
EVENTS = [{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 400, "type": "off", "note": 62, "velocity": 0}]

FAKE_PIANO = """
(() => {
  const input = {
    id: "fake-1", name: "Fake piano", manufacturer: "", type: "input", state: "connected", connection: "open",
    onmidimessage: null, listeners: [],
    addEventListener(type, fn) { if (type === "midimessage") this.listeners.push(fn); },
    removeEventListener() {},
    open() { return Promise.resolve(this); },
  };
  const access = { inputs: new Map([["fake-1", input]]), outputs: new Map(), onstatechange: null, addEventListener() {} };
  navigator.requestMIDIAccess = () => Promise.resolve(access);
  window.__press = (note, velocity = 100) => {
    const event = { data: Uint8Array.from([0x90, note, velocity]), timeStamp: performance.now() };
    if (input.onmidimessage) input.onmidimessage(event);
    input.listeners.forEach((fn) => fn(event));
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
    user = User.objects.create_user("p71browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(command, stdout=io.StringIO())
    player, _ = Player.objects.get_or_create(user=user)
    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    context.add_init_script(FAKE_PIANO)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, player, live_server.url
    context.close()


def _take(player, events=EVENTS):
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    chart = Progression.objects.get(slug="ii-v-i-major")
    return Take.objects.create(
        player=player, session=session, progression=chart, chart=chart.chart, home_key=chart.home_key, key="C", tempo=90,
        loop_from=0, loop_to=4, started_at=timezone.now() - dt.timedelta(days=1), duration_ms=10000, bars=4,
        events=events, score=64, metrics={"notes": 25, "chordTonePct": 60}, judge_version=1,
    )


def _open(page, base, path, ready):
    page.goto(f"{base}{path}", wait_until="domcontentloaded")
    page.wait_for_selector(ready, timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def test_c8_starts_and_stops_the_band_and_the_button_wears_the_key(world):
    page, errors, _, base = world
    _open(page, base, "/improv/play/", "#play-toggle:not([disabled])")
    page.wait_for_selector('#play-toggle[data-key-hint="C8"]')
    assert page.locator("#play-toggle").inner_text() == "Play"
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Stop'", timeout=5000)
    page.wait_for_selector('#play-toggle[data-key-hint="C8"]')
    page.wait_for_timeout(450)
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Play'", timeout=5000)
    assert not errors, errors


def test_a_second_c8_inside_the_debounce_does_not_undo_the_first(world):
    page, errors, _, base = world
    _open(page, base, "/improv/play/", "#play-toggle:not([disabled])")
    page.evaluate("window.__press(108); window.__press(108)")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Stop'", timeout=5000)
    page.wait_for_timeout(200)
    assert page.locator("#play-toggle").inner_text() == "Stop"
    page.click("#play-toggle")
    assert not errors, errors


def test_the_control_keys_are_not_notes_on_the_play_screen(world):
    page, errors, _, base = world
    _open(page, base, "/improv/play/", "#play-toggle:not([disabled])")
    page.evaluate("window.__press(60)")
    page.wait_for_function("document.getElementById('heard').textContent.trim() !== ''", timeout=3000)
    before = page.locator("#heard").inner_text()
    page.evaluate("window.__press(107); window.__press(106)")
    page.wait_for_timeout(300)
    assert page.locator("#heard").inner_text() == before, "B7 and A#7 are not played notes"
    assert not errors, errors


def test_setup_c8_saves_and_then_the_spent_button_wears_no_key(world):
    page, errors, _, base = world
    _open(page, base, "/improv/setup/", "#calibrate")
    page.wait_for_function("document.getElementById('setup-status').textContent.startsWith('Choose')", timeout=10000)
    page.wait_for_selector('#save[data-key-hint="C8"]')
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=5000)
    page.wait_for_selector("#save:disabled")
    assert page.locator("#save").get_attribute("data-key-hint") is None, "nothing to save, so no key promised"
    page.wait_for_timeout(450)
    page.evaluate("window.__press(108)")
    page.wait_for_timeout(300)
    assert page.locator("#setup-status").inner_text() == "Saved.", "a disabled button is skipped, nothing else fires"
    assert page.locator("#calibrate").get_attribute("data-key-hint") == "B7"
    page.evaluate("window.__press(107)")
    page.wait_for_function("document.getElementById('calibrate').disabled", timeout=5000)
    assert page.locator("#calibrate").get_attribute("data-key-hint") is None
    assert not errors, errors


def test_today_c8_opens_the_lesson_in_progress(world):
    page, errors, _, base = world
    _open(page, base, "/improv/", "#continue-link:not([hidden])")
    assert page.locator("#continue-link").get_attribute("data-key-hint") == "C8"
    assert page.locator('a:has-text("Open Play")').get_attribute("data-key-hint") is None, "only the button that fires wears the key"
    href = page.locator("#continue-link").get_attribute("href")
    page.evaluate("window.__press(108)")
    page.wait_for_url(f"**{href}", timeout=10000)
    assert not errors, errors


def test_takes_c8_replays_the_first_take_and_then_stops_it(world):
    page, errors, player, base = world
    _take(player)
    _open(page, base, "/improv/takes/", "#takes-list .im-take")
    page.wait_for_selector('#takes-list [data-key-item][data-key-hint="C8"]')
    page.evaluate("window.__press(108)")
    page.wait_for_selector("#replay-panel:not([hidden])", timeout=5000)
    page.wait_for_selector('#replay-stop[data-key-hint="C8"]')
    page.wait_for_timeout(450)
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('replay-panel').hidden || document.getElementById('replay-status').textContent.length > 0", timeout=5000)
    assert not errors, errors


def test_lessons_c8_opens_the_first_lesson_not_yet_done(world):
    page, errors, _, base = world
    _open(page, base, "/improv/lessons/", "#lessons-tracks a")
    page.wait_for_selector('#lessons-tracks [data-key-hint="C8"]')
    href = page.locator('#lessons-tracks [data-key-hint="C8"]').get_attribute("href")
    page.evaluate("window.__press(108)")
    page.wait_for_url(f"**{href}", timeout=10000)
    assert not errors, errors


def test_challenges_c8_opens_the_first_challenge_in_play(world):
    page, errors, _, base = world
    _open(page, base, "/improv/challenges/", "#challenges-list a")
    href = page.locator('#challenges-list [data-key-hint="C8"]').get_attribute("href")
    page.evaluate("window.__press(108)")
    page.wait_for_url(f"**{href}", timeout=10000)
    assert not errors, errors


def test_the_library_c8_plays_the_first_card_and_b7_makes_a_new_one(world):
    page, errors, _, base = world
    _open(page, base, "/improv/library/", "#lib-list .im-card")
    href = page.locator('#lib-list [data-key-hint="C8"]').get_attribute("href")
    assert page.locator('a:has-text("New progression")').get_attribute("data-key-hint") == "B7"
    page.evaluate("window.__press(108)")
    page.wait_for_url(f"**{href}", timeout=10000)
    assert not errors, errors
