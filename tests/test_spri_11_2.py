"""SPR-I.11.2 improv: pause on the Play screen, and a click to hold a chord.

Avi, 2026-10-10: a Pause next to Play and Stop, on a piano key or the left pedal, so he can stop on a chord and
look at it; and when the band is stopped, a click on any chord in the progression shows its details.

Pause freezes the audio clock, so the band and the lit bar stand still and carry on from the same place. B7 is
Pause and Resume, and so is the left pedal (controller 67). A click on a bar holds that chord in the guide while
stopped or paused; the same chord again lets it go.

Traces: spec ch. 8 "The chord guide" and "Pause", backlog SPR-I.11.2.
"""

import io
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri112]

PASSWORD = "spri112-browser-5521"

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
    leftPedal(down) { port.onmidimessage({ data: new Uint8Array([0xb0, 67, down ? 127 : 0]), timeStamp: performance.now() }); },
  };
})();
"""

LIT_BAR = "(document.querySelector('.im-bar-lit') || {dataset: {}}).dataset.bar"


def test_the_pedal_logic_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri112.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


def test_the_page_has_a_pause_button_on_the_second_key_and_says_so():
    html = Path("templates/improv/play.html").read_text(encoding="utf-8")
    assert re.search(r'id="pause-toggle" data-key-action="secondary"', html)
    assert "left pedal pauses" in html


def test_the_docs_describe_pause_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "Pause (SPR-I.11.2" in spec and "left pedal" in spec
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.11\.2 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)


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
def play(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p112browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 720})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    context.add_init_script(FAKE_WORLD)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{live_server.url}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    page.wait_for_function("document.getElementById('midi-state').textContent.startsWith('Listening to')", timeout=10000)
    page.select_option("#progression", "ii-v-i-major")
    page.wait_for_selector("#chart .im-bar", timeout=8000)
    yield page, errors
    context.close()


def _said(page, start):
    page.wait_for_function("(start) => document.getElementById('guide-chord').textContent.startsWith(start)", arg=start, timeout=8000)


def _start(page):
    page.fill("#bpm", "160")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    _said(page, "Now playing")


def test_pause_is_hidden_until_the_band_plays(play):
    page, errors = play
    assert page.is_hidden("#pause-toggle")
    _start(page)
    assert page.is_visible("#pause-toggle")
    assert page.inner_text("#pause-toggle") == "Pause"
    assert page.inner_text("#play-toggle") == "Stop"
    page.click("#play-toggle")
    assert page.is_hidden("#pause-toggle")
    assert page.inner_text("#play-toggle") == "Play"
    assert errors == []


def test_pause_freezes_the_band_and_resume_carries_on(play):
    page, errors = play
    _start(page)
    page.click("#pause-toggle")
    _said(page, "Paused on")
    assert page.inner_text("#pause-toggle") == "Resume"
    held_bar = page.evaluate(LIT_BAR)
    page.wait_for_timeout(1500)
    assert page.evaluate(LIT_BAR) == held_bar
    page.click("#pause-toggle")
    _said(page, "Now playing")
    assert page.inner_text("#pause-toggle") == "Pause"
    page.wait_for_function(f"(was) => {LIT_BAR} !== was", arg=held_bar, timeout=8000)
    assert errors == []


def test_the_left_pedal_pauses_and_resumes(play):
    page, errors = play
    _start(page)
    page.evaluate("window.__piano.leftPedal(true)")
    page.wait_for_function("document.getElementById('pause-toggle').textContent === 'Resume'", timeout=3000)
    page.evaluate("window.__piano.leftPedal(false)")
    page.wait_for_timeout(600)
    page.evaluate("window.__piano.leftPedal(true)")
    page.wait_for_function("document.getElementById('pause-toggle').textContent === 'Pause'", timeout=3000)
    assert errors == []


def test_the_left_pedal_does_nothing_while_stopped(play):
    page, errors = play
    page.evaluate("window.__piano.leftPedal(true)")
    page.wait_for_timeout(500)
    assert page.is_hidden("#pause-toggle")
    assert page.inner_text("#play-toggle") == "Play"
    assert errors == []


def _click_bar(page, index, at=0.2):
    box = page.locator(f'#chart .im-bar[data-bar="{index}"]').bounding_box()
    page.mouse.move(box["x"] + box["width"] * at, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.up()
    page.mouse.move(2, 2)


def test_stopped_a_click_holds_a_chord_and_the_same_click_lets_it_go(play):
    page, errors = play
    _click_bar(page, 1)
    _said(page, "Holding")
    assert page.get_attribute('#chart .im-bar[data-bar="1"]', "data-held") == "yes"
    _click_bar(page, 1)
    _said(page, "First chord")
    assert page.get_attribute('#chart .im-bar[data-bar="1"]', "data-held") is None
    assert errors == []


def test_paused_a_click_holds_a_chord_and_resume_goes_back_to_the_band(play):
    page, errors = play
    _start(page)
    page.click("#pause-toggle")
    _said(page, "Paused on")
    _click_bar(page, 3)
    _said(page, "Holding")
    page.click("#pause-toggle")
    _said(page, "Now playing")
    assert page.get_attribute('#chart .im-bar[data-bar="3"]', "data-held") is None
    assert errors == []


def test_a_click_while_the_band_plays_holds_nothing(play):
    page, errors = play
    _start(page)
    _click_bar(page, 3)
    page.wait_for_timeout(500)
    assert page.inner_text("#guide-chord").startswith("Now playing")
    assert page.get_attribute('#chart .im-bar[data-bar="3"]', "data-held") is None
    assert errors == []


def test_stop_while_paused_stops_and_play_works_again(play):
    page, errors = play
    _start(page)
    page.click("#pause-toggle")
    page.wait_for_function("document.getElementById('pause-toggle').textContent === 'Resume'", timeout=3000)
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('play-toggle').textContent === 'Play'", timeout=3000)
    assert page.is_hidden("#pause-toggle")
    page.click("#play-toggle")
    _said(page, "Now playing")
    assert page.inner_text("#pause-toggle") == "Pause"
    assert errors == []


def test_playing_and_paused_still_fit_one_screen(play):
    page, errors = play
    fits = "document.documentElement.scrollHeight <= window.innerHeight && document.documentElement.scrollWidth <= window.innerWidth"
    assert page.evaluate(fits)
    _start(page)
    assert page.evaluate(fits)
    page.click("#pause-toggle")
    _said(page, "Paused on")
    _click_bar(page, 2)
    _said(page, "Holding")
    assert page.evaluate(fits)
    assert errors == []
