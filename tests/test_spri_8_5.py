"""SPR-I.8.5 improv: the Chords screen.

The chords and the matching are proved under Node (tests/js/spri84.test.js). Here: the page is behind the
gate, and in a real browser with a faked piano a prompt is shown with a running clock, a right chord is
marked, saved to its player and followed by the next, a wrong chord keeps the prompt and is counted
once, Hint (B7) lights the keys, Skip (A#7) saves a miss, C8 starts and stops, Circle walks the keys and
Learn lists the chords of the key without scoring anything.

Traces: spec ch. 10, backlog SPR-I.8.5.
"""

import io
import json
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import DrillAttempt, Player

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri85, pytest.mark.django_db]

PASSWORD = "spri85-pass-4471"

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
  const send = (status, note, velocity) => {
    const event = { data: Uint8Array.from([status, note, velocity]), timeStamp: performance.now() };
    if (input.onmidimessage) input.onmidimessage(event);
    input.listeners.forEach((fn) => fn(event));
  };
  window.__press = (note, velocity = 100) => send(0x90, note, velocity);
  window.__release = (note) => send(0x80, note, 0);
  window.__tap = (note) => { send(0x90, note, 100); send(0x80, note, 0); };
})();
"""

# Holds a chord down for a moment, then lets go.
PLAY_CHORD = """
async (notes) => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  notes.forEach((n) => window.__press(n));
  await wait(300);
  notes.forEach((n) => window.__release(n));
  await wait(200);
}
"""

# The chord the page is asking for, as notes in the middle of the piano with the right bass lowest.
RIGHT_NOTES = """
() => {
  const p = JSON.parse(document.getElementById('chords').dataset.promptJson);
  const order = [];
  for (let i = 0; i < p.intervals.length; i++) order.push((p.rootPc + p.intervals[(p.position - 1 + i) % p.intervals.length]) % 12);
  const notes = [48 + (((order[0] - 48) % 12) + 12) % 12];
  for (let i = 1; i < order.length; i++) { const prev = notes[i - 1]; notes.push(prev + (((order[i] - prev) % 12) + 12) % 12); }
  return notes;
}
"""

# A note that is not in the chord at all.
WRONG_NOTES = """
() => {
  const p = JSON.parse(document.getElementById('chords').dataset.promptJson);
  let extra = 0;
  while (p.pcs.includes(extra)) extra++;
  return [60, 60 + ((extra - 60) % 12 + 12) % 12];
}
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
    user = User.objects.create_user("p85browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
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


def _open(page, base, query=""):
    page.goto(f"{base}/improv/chords/{query}", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#ch-key option').length > 5", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def _prompt(page):
    return json.loads(page.locator("#chords").get_attribute("data-prompt-json"))


def _saved(page, count):
    page.wait_for_function(f"document.getElementById('chords').dataset.saved === '{count}'", timeout=8000)


# ------------------------------------------------------------------ the gate


def test_the_page_is_behind_the_gate(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p85member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p85stranger", password=PASSWORD)
    assert Client().get("/improv/chords/").status_code == 404
    other = Client()
    other.force_login(stranger)
    assert other.get("/improv/chords/").status_code == 404
    mine = Client()
    mine.force_login(member)
    response = mine.get("/improv/chords/")
    assert response.status_code == 200
    text = response.content.decode()
    assert "/improv/api/drill-attempts/" in text and "/improv/api/chord-qualities/" in text and "/improv/api/player/" in text
    for action in ("primary", "secondary", "tertiary"):
        assert f'data-key-action="{action}"' in text


# ------------------------------------------------------------------ in a browser


def test_it_opens_in_drill_on_g_with_start_ready_and_no_errors(world):
    page, errors, _, base = world
    _open(page, base)
    assert page.locator("#ch-mode option").all_inner_texts()[0].lower().startswith("drill")
    assert page.locator("#ch-key option").all_inner_texts() == ["G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F", "C"]
    assert page.locator("#ch-key").input_value() == "7"
    assert page.locator("#ch-level option").count() == 3
    assert page.locator("#ch-hint").is_disabled() and page.locator("#ch-skip").is_disabled()
    assert page.locator("#chords").get_attribute("data-running") == "no"
    assert not errors, errors


def test_start_shows_a_prompt_with_a_running_clock(world):
    page, errors, _, base = world
    _open(page, base, "?level=2")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    prompt = _prompt(page)
    assert prompt["key_pc"] == 7 and prompt["level"] == 2
    assert prompt["title"] in page.locator("#ch-prompt").inner_text()
    assert page.locator("#ch-hint").is_enabled() and page.locator("#ch-skip").is_enabled()
    first = page.locator("#ch-timer").inner_text()
    page.wait_for_timeout(700)
    assert page.locator("#ch-timer").inner_text() != first
    assert not errors, errors


def test_the_right_chord_is_marked_saved_and_the_next_one_shown(world):
    page, errors, player, base = world
    _open(page, base, "?level=2")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    first = _prompt(page)
    page.evaluate(PLAY_CHORD, page.evaluate(RIGHT_NOTES))
    _saved(page, 1)
    assert page.locator("#chords").get_attribute("data-last-result") == "right"
    page.wait_for_function(
        f"JSON.parse(document.getElementById('chords').dataset.promptJson).id !== {json.dumps(first['id'])}", timeout=5000,
    )
    row = DrillAttempt.objects.get()
    assert row.player == player and row.is_correct and row.wrong_tries == 0 and not row.hint_used and not row.skipped
    assert row.response_ms is not None and row.prompt["id"] == first["id"] and row.key_pc == 7 and row.level == 2
    assert not errors, errors


def test_a_wrong_chord_keeps_the_prompt_and_is_counted_once(world):
    page, errors, _, base = world
    _open(page, base, "?level=2")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    first = _prompt(page)
    page.evaluate(PLAY_CHORD, page.evaluate(WRONG_NOTES))
    page.wait_for_function("document.getElementById('chords').dataset.wrongTries === '1'", timeout=5000)
    assert _prompt(page)["id"] == first["id"]
    assert page.locator("#ch-feedback").inner_text().strip() != ""
    assert page.locator("#ch-feedback").get_attribute("data-state") == "wrong"
    assert DrillAttempt.objects.count() == 0
    page.evaluate(PLAY_CHORD, page.evaluate(RIGHT_NOTES))
    _saved(page, 1)
    row = DrillAttempt.objects.get()
    assert row.wrong_tries == 1 and row.is_correct is False and row.skipped is False and row.response_ms is not None
    assert not errors, errors


def test_the_hint_is_b7_and_shows_the_chord_on_the_keyboard(world):
    page, errors, _, base = world
    _open(page, base, "?level=2")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    prompt = _prompt(page)
    page.wait_for_selector('#ch-hint[data-key-hint="B7"]')
    page.evaluate("window.__tap(107)")
    page.wait_for_function("document.getElementById('chords').dataset.hint === 'yes'", timeout=5000)
    assert prompt["bassName"] in page.locator("#ch-detail").inner_text()
    assert page.locator("#ch-keyboard .im-key-pending").count() == len(prompt["pcs"])
    page.evaluate(PLAY_CHORD, page.evaluate(RIGHT_NOTES))
    _saved(page, 1)
    row = DrillAttempt.objects.get()
    assert row.hint_used is True
    assert not errors, errors


def test_the_skip_is_a_tertiary_key_and_saves_a_miss(world):
    page, errors, _, base = world
    _open(page, base, "?level=1")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    first = _prompt(page)
    page.wait_for_selector('#ch-skip[data-key-hint="A#7"]')
    page.evaluate("window.__tap(106)")
    _saved(page, 1)
    assert page.locator("#chords").get_attribute("data-last-result") == "skipped"
    page.wait_for_function(
        f"JSON.parse(document.getElementById('chords').dataset.promptJson).id !== {json.dumps(first['id'])}", timeout=5000,
    )
    row = DrillAttempt.objects.get()
    assert row.skipped and not row.is_correct and row.response_ms is None
    assert not errors, errors


def test_c8_starts_and_stops_and_a_stopped_drill_saves_nothing_more(world):
    page, errors, _, base = world
    _open(page, base)
    page.wait_for_selector('#ch-start[data-key-hint="C8"]')
    page.evaluate("window.__tap(108)")
    page.wait_for_selector('#chords[data-running="yes"]', timeout=5000)
    page.wait_for_timeout(400)
    page.evaluate("window.__tap(108)")
    page.wait_for_selector('#chords[data-running="no"]', timeout=5000)
    assert page.locator("#ch-start").inner_text() == "Start"
    assert DrillAttempt.objects.count() == 0
    assert not errors, errors


def test_circle_walks_the_keys_from_g(world):
    page, errors, _, base = world
    _open(page, base, "?mode=circle&level=1")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    assert _prompt(page)["key_pc"] == 7
    assert "1" in page.locator("#ch-progress").inner_text() and "84" in page.locator("#ch-progress").inner_text()
    for _ in range(7):
        page.evaluate(PLAY_CHORD, page.evaluate(RIGHT_NOTES))
        page.wait_for_timeout(900)
    assert _prompt(page)["key_pc"] == 2
    assert not errors, errors


def test_learn_lists_the_chords_and_shows_a_position_without_scoring(world):
    page, errors, _, base = world
    _open(page, base, "?mode=learn&level=3")
    assert page.locator("#ch-start").is_disabled()
    assert page.locator("#ch-learn .im-learn-row").count() == 9
    assert page.locator("#ch-results-box").is_hidden() and page.locator("#ch-learn-box").is_visible()
    page.locator("#ch-learn .im-learn-row").nth(4).locator("button").nth(1).click()
    page.wait_for_function("document.querySelectorAll('#ch-keyboard .im-key-chord').length === 4", timeout=5000)
    assert "second position" in page.locator("#ch-prompt").inner_text()
    assert DrillAttempt.objects.count() == 0
    assert not errors, errors


def test_a_running_drill_with_hint_and_feedback_still_fits_the_window(world):
    page, errors, _, base = world
    _open(page, base, "?level=3")
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    page.evaluate(PLAY_CHORD, page.evaluate(WRONG_NOTES))
    page.evaluate("window.__tap(107)")
    page.wait_for_function("document.getElementById('chords').dataset.hint === 'yes'", timeout=5000)
    for _ in range(12):
        page.evaluate("window.__tap(106)")
        page.wait_for_timeout(1700)
    measured = page.evaluate("() => ({tall: document.documentElement.scrollHeight - innerHeight, wide: document.documentElement.scrollWidth - innerWidth})")
    assert measured["tall"] <= 0 and measured["wide"] <= 0, measured
    assert not errors, errors


def test_the_work_on_this_line_follows_the_answers(world):
    page, errors, _, base = world
    _open(page, base, "?level=2")
    page.wait_for_function("document.getElementById('chords').dataset.work !== undefined", timeout=5000)
    assert "No chord answers yet" in page.locator("#tr-work").inner_text()
    page.click("#ch-start")
    page.wait_for_selector('#chords[data-running="yes"]')
    page.evaluate(PLAY_CHORD, page.evaluate(RIGHT_NOTES))
    _saved(page, 1)
    page.wait_for_function("document.getElementById('chords').dataset.work.indexOf('Not enough answers') === 0", timeout=5000)
    assert not errors, errors
