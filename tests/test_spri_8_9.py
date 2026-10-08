"""SPR-I.8.9 improv: "Show me" on the Play screen's exercise.

Avi, on the bossa challenge: "add a button show me so you can demonstrate to me what you expect."
The demonstration is built by static/improv/demo.js from the same chart and chord table the judge
reads, and tests/js/spri89.test.js runs it through the real judge. Here the Node run is part of the
suite and the button is driven in a real browser: it sounds the exercise over the band, lights the
keys, stops by itself, and records nothing.

Traces: spec ch. 10, backlog SPR-I.8.9.
"""

import io
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import Client

from improv.models import Exercise, PracticeSession, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri89, pytest.mark.django_db]

PASSWORD = "spri89-pass-5521"
TEMPLATE = Path("templates/improv/play.html")
PAGE_JS = Path("static/improv/play-page.js")
DEMO_JS = Path("static/improv/demo.js")

FAKE_PIANO = """
(() => {
  const input = {
    id: "fake-1", name: "Fake piano", manufacturer: "", type: "input", state: "connected", connection: "open",
    onmidimessage: null, listeners: [],
    addEventListener(type, fn) { if (type === "midimessage") this.listeners.push(fn); },
    removeEventListener() {},
    open() { return Promise.resolve(this); },
  };
  window.__sent = [];
  const output = {
    id: "fake-out", name: "Fake piano", manufacturer: "", type: "output", state: "connected", connection: "open",
    send(bytes, at) { window.__sent.push({ bytes: Array.from(bytes), at }); },
    open() { return Promise.resolve(this); },
  };
  const access = {
    inputs: new Map([["fake-1", input]]),
    outputs: window.__withOutput ? new Map([["fake-out", output]]) : new Map(),
    onstatechange: null, addEventListener() {},
  };
  navigator.requestMIDIAccess = () => Promise.resolve(access);
  window.__press = (note, velocity = 100) => {
    const event = { data: Uint8Array.from([0x90, note, velocity]), timeStamp: performance.now() };
    if (input.onmidimessage) input.onmidimessage(event);
    input.listeners.forEach((fn) => fn(event));
  };
})();
"""

SPY_ON_THE_SYNTH = """
() => {
  window.__plays = [];
  const original = window.ImprovSynth.createSynth;
  window.ImprovSynth.createSynth = (ctx) => {
    const synth = original(ctx);
    const play = synth.play.bind(synth);
    synth.play = (event, when, seconds) => {
      if (event.voice === "demo") window.__plays.push({ midi: event.midi, when, seconds, now: ctx.currentTime });
      return play(event, when, seconds);
    };
    return synth;
  };
}
"""

# Dm7 is D F A C and G7 is G B D F: the first two bars of the bossa chart.
DM7 = {2, 5, 9, 0}
G7 = {7, 11, 2, 5}


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


def _make_world(browser, live_server, with_output):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p89browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_fingerings", "seed_improv_library"):
        call_command(command, stdout=io.StringIO())
    bossa = Progression.objects.get(slug="bossa-ii-v-i-loop")
    common = {"progression": bossa, "key": "C", "tempo": 150, "style": bossa.default_style, "pass_score": 70, "xp": 30}
    Exercise.objects.create(slug="show-rhythm", title="A short bossa rhythm", instructions="Play the rhythm.", bars=2, scoring_kind="rhythm_motif", scoring_params={"pattern": [0, 1.5, 2, 3.5]}, **common)
    Exercise.objects.create(slug="show-free", title="Just play", instructions="Play anything.", bars=2, scoring_kind="free_play", scoring_params={}, **common)
    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    if with_output:
        context.add_init_script("window.__withOutput = true;")
    context.add_init_script(FAKE_PIANO)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    return context, page, errors, live_server.url


@pytest.fixture
def world(browser, live_server, db, one_request_at_a_time):
    context, page, errors, base = _make_world(browser, live_server, with_output=False)
    yield page, errors, base
    context.close()


@pytest.fixture
def world_with_piano_out(browser, live_server, db, one_request_at_a_time):
    context, page, errors, base = _make_world(browser, live_server, with_output=True)
    yield page, errors, base
    context.close()


def _open(page, base, slug="show-rhythm"):
    page.goto(f"{base}/improv/play/?exercise={slug}", wait_until="domcontentloaded")
    page.wait_for_function("!document.getElementById('exercise-panel').hidden", timeout=15000)
    page.wait_for_function("document.getElementById('play-toggle').disabled === false", timeout=15000)


def _spy(page):
    page.evaluate(SPY_ON_THE_SYNTH)


# ------------------------------------------------------------------ the rules and the page


def test_the_demonstration_rules_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri89.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_page_loads_the_demo_module_before_its_own_script():
    html = TEMPLATE.read_text(encoding="utf-8")
    names = [Path(src).name for src in re.findall(r"improv/([\w-]+\.js)", html)]
    assert names.index("demo.js") < names.index("play-page.js")
    assert finders.find("improv/demo.js")


def test_show_me_is_a_piano_key_button_and_does_not_take_over_c8():
    html = TEMPLATE.read_text(encoding="utf-8")
    button = re.search(r'<button[^>]*id="show-me"[^>]*>', html)
    assert button, "the exercise panel has a Show me button"
    assert 'data-key-action="tertiary"' in button.group(0)
    assert html.count('data-key-action="primary"') == 1, "C8 stays Play"


def test_the_demo_module_builds_markup_nowhere():
    text = re.sub(r"//[^\n]*", "", DEMO_JS.read_text(encoding="utf-8"))
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert forbidden not in text
    script = re.sub(r"//[^\n]*", "", PAGE_JS.read_text(encoding="utf-8"))
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert forbidden not in script


# ----------------------------------------------------------------------------- the button


def test_the_button_is_there_for_an_exercise_that_can_be_shown_and_not_for_free_play(world):
    page, errors, base = world
    _open(page, base)
    assert page.locator("#show-me").is_visible()
    assert page.locator("#show-me").is_enabled()
    assert page.locator("#show-me").inner_text() == "Show me"
    _open(page, base, "show-free")
    assert page.locator("#show-me").is_hidden()
    assert not errors, errors


def test_show_me_plays_the_rhythm_in_chord_tones_over_the_band_and_stops_by_itself(world):
    page, errors, base = world
    _open(page, base)
    _spy(page)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    assert "chord tone" in page.locator("#feedback").inner_text()
    assert "the and of 2" in page.locator("#feedback").inner_text()
    page.wait_for_selector("#chart .im-bar-lit", timeout=10000)
    assert page.locator("#show-me").is_enabled()
    page.wait_for_selector("#keys .im-key-on", timeout=15000)
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=30000)
    plays = page.evaluate("window.__plays")
    assert len(plays) == 8, "four notes in each of two bars"
    first, second = plays[:4], plays[4:]
    assert {p["midi"] % 12 for p in first} <= DM7
    assert {p["midi"] % 12 for p in second} <= G7
    beat = 60 / 150
    gaps = [round((b["when"] - a["when"]) / beat, 3) for a, b in zip(plays, plays[1:4])]
    assert gaps == [1.5, 0.5, 1.5]
    assert round((plays[4]["when"] - plays[0]["when"]) / beat, 3) == 4.0
    assert "Done" in page.locator("#play-status").inner_text()
    assert page.locator("#play-toggle").inner_text() == "Play"
    assert page.locator("#keys .im-key-on").count() == 0
    assert page.locator("#chart .im-bar-lit").count() == 0
    assert not errors, errors


def test_a_demonstration_is_not_a_take_and_is_not_practice(world):
    page, errors, base = world
    _open(page, base)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=30000)
    page.wait_for_timeout(500)
    assert Take.objects.count() == 0
    assert PracticeSession.objects.count() == 0
    assert "Take" not in page.locator("#take-status").inner_text()
    assert not errors, errors


def test_the_settings_hold_still_while_it_is_shown_and_come_back_after(world):
    page, errors, base = world
    _open(page, base)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    for control in ("bpm", "key", "swing", "style", "progression", "first", "last", "countin"):
        assert page.locator(f"#{control}").is_disabled(), control
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=5000)
    for control in ("bpm", "key", "swing", "style", "progression", "first", "last", "countin"):
        assert page.locator(f"#{control}").is_enabled(), control
    assert "Stopped" in page.locator("#play-status").inner_text()
    assert page.locator("#keys .im-key-on").count() == 0
    assert not errors, errors


def test_the_third_piano_key_starts_and_stops_it(world):
    page, errors, base = world
    _open(page, base)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)
    page.evaluate("window.__press(106)")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    page.wait_for_timeout(600)
    page.evaluate("window.__press(106)")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=5000)
    assert not errors, errors


def test_play_while_it_is_shown_ends_the_demonstration_and_starts_the_take(world):
    page, errors, base = world
    _open(page, base)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Stop'", timeout=8000)
    assert page.locator("#show-me").inner_text() == "Show me"
    assert page.locator("#show-me").is_disabled(), "no demonstration over a take"
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Play'", timeout=5000)
    assert page.locator("#show-me").is_enabled()
    assert not errors, errors


def test_changing_the_loop_turns_it_into_free_play_and_nothing_is_shown(world):
    page, errors, base = world
    _open(page, base)
    page.locator("#last").fill("1")
    page.locator("#last").dispatch_event("change")
    page.wait_for_function("document.getElementById('exercise-goal').textContent.includes('free play')", timeout=5000)
    assert page.locator("#show-me").is_disabled()
    assert not errors, errors


def test_with_a_piano_connected_the_notes_go_out_over_midi_and_the_laptop_stays_silent(world_with_piano_out):
    page, errors, base = world_with_piano_out
    _open(page, base)
    _spy(page)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    page.wait_for_function("window.__sent.length >= 16", timeout=10000)
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=30000)
    sent = page.evaluate("window.__sent")
    ons = [m for m in sent if m["bytes"][0] == 0x90]
    offs = [m for m in sent if m["bytes"][0] == 0x80]
    assert len(ons) == 8 and len(offs) >= 8
    assert {m["bytes"][1] % 12 for m in ons[:4]} <= DM7
    assert page.evaluate("window.__plays.length") == 0, "the band plays on the laptop, the notes on the piano"
    assert not errors, errors


def test_stopping_early_lifts_every_note_off_the_piano(world_with_piano_out):
    page, errors, base = world_with_piano_out
    _open(page, base)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Stop'", timeout=8000)
    page.wait_for_function("window.__sent.length >= 6", timeout=10000)
    page.click("#show-me")
    page.wait_for_function("document.getElementById('show-me').textContent === 'Show me'", timeout=5000)
    sent = page.evaluate("window.__sent")
    sounded = {m["bytes"][1] for m in sent if m["bytes"][0] == 0x90}
    lifted = {m["bytes"][1] for m in sent if m["bytes"][0] == 0x80}
    assert sounded <= lifted
    assert not errors, errors


def test_the_screen_still_fits_with_the_button_at_both_sizes(world):
    page, errors, base = world
    for width, height in ((1280, 720), (1920, 1080)):
        page.set_viewport_size({"width": width, "height": height})
        _open(page, base)
        over = page.evaluate("() => ({ tall: document.documentElement.scrollHeight - window.innerHeight, wide: document.documentElement.scrollWidth - window.innerWidth })")
        assert over["tall"] <= 0 and over["wide"] <= 0, (width, height, over)
        assert page.locator("#show-me").is_visible()
    assert not errors, errors
