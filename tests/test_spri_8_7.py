"""SPR-I.8.7 improv: Avi's live check of the trainer.

What he asked for after playing it: the keys start at C, a passed scale goes straight on to the next
length (2, 3, then 4 octaves, 2, 3, 4 notes a beat) without pressing anything, the scale can start
lower or where he wants, the top piano keys show that they were heard, and the band on the Play
screen is quiet enough to hear himself. The rules are proved under Node (tests/js/spri87.test.js);
here the Node run is part of the suite and the screens are driven in a real browser with a faked piano.

Traces: spec ch. 10, backlog SPR-I.8.7.
"""

import io
import os
import shutil
import subprocess

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player, ScaleRun

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri87, pytest.mark.django_db]

PASSWORD = "spri87-pass-6143"

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

PLAY_IT_RIGHT = """
async ({ pc, octaves, tempo, startOctave }) => {
  const host = document.getElementById('scales');
  const steps = window.ImprovScale.buildSteps(pc, octaves, startOctave);
  const step = 60000 / (tempo * octaves);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < steps.length; i++) {
    const due = Number(host.dataset.runStart) + i * step;
    const gap = due - performance.now();
    if (gap > 0) await wait(gap);
    window.__press(steps[i].left);
    window.__press(steps[i].right);
  }
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
    user = User.objects.create_user("p87browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_fingerings", "seed_improv_library"):
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


def _open_scales(page, base, query=""):
    page.goto(f"{base}/improv/scales/{query}", wait_until="domcontentloaded")
    page.wait_for_selector("#sc-start:not([disabled])", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def _fast(page):
    page.locator("#sc-tempo").fill("160")
    page.keyboard.press("Tab")
    page.wait_for_function("document.getElementById('sc-line').textContent.includes('160 bpm')")


def test_the_rules_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri87.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ keep going


def test_a_pass_goes_straight_on_to_the_next_length_in_the_same_key(world):
    page, errors, player, base = world
    _open_scales(page, base)
    _fast(page)
    assert page.locator("#sc-auto").is_checked()
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 2, "tempo": 160})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    assert "Next: 3 octaves, 3 notes a beat" in page.locator("#sc-status").inner_text()
    page.wait_for_function("document.getElementById('sc-level').value === '2'", timeout=5000)
    page.wait_for_selector('#scales[data-running="yes"]', timeout=8000)
    assert page.locator("#sc-key").input_value() == "0"
    assert len(page.locator("#sc-strip .im-sc-cell").all()) == 43
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 3, "tempo": 160})
    page.wait_for_function("document.getElementById('sc-level').value === '3'", timeout=15000)
    page.wait_for_selector('#scales[data-running="yes"]', timeout=8000)
    assert [(r.root_pc, r.octaves, r.passed) for r in ScaleRun.objects.order_by("id")] == [(0, 2, True), (0, 3, True)]
    page.evaluate("window.__press(108)")
    page.wait_for_selector('#scales[data-running="no"]', timeout=5000)
    assert not errors, errors


def test_a_pass_at_four_octaves_moves_to_the_next_key_and_waits(world):
    page, errors, player, base = world
    _open_scales(page, base, "?level=3&key=0")
    _fast(page)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 4, "tempo": 160})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    page.wait_for_function("document.getElementById('sc-key').value === '7'", timeout=5000)
    assert page.locator("#sc-level").input_value() == "1"
    assert "Next key: G" in page.locator("#sc-status").inner_text()
    page.wait_for_timeout(3500)
    assert page.locator("#scales").get_attribute("data-running") == "no", "a new key waits for the player"
    assert not errors, errors


def test_a_run_that_did_not_pass_does_not_start_another(world):
    page, errors, player, base = world
    _open_scales(page, base)
    _fast(page)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=15000)
    assert page.locator("#sc-verdict").inner_text().startswith("Not yet")
    page.wait_for_timeout(3500)
    assert page.locator("#scales").get_attribute("data-running") == "no"
    assert page.locator("#sc-level").input_value() == "1"
    assert ScaleRun.objects.count() == 1
    assert not errors, errors


def test_keep_going_can_be_turned_off_and_is_remembered(world):
    page, errors, player, base = world
    _open_scales(page, base)
    page.uncheck("#sc-auto")
    _fast(page)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 2, "tempo": 160})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    page.wait_for_timeout(3500)
    assert page.locator("#scales").get_attribute("data-running") == "no"
    assert page.locator("#sc-level").input_value() == "1"
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#sc-start:not([disabled])")
    assert not page.locator("#sc-auto").is_checked()
    assert not errors, errors


def test_start_during_the_pause_goes_now(world):
    page, errors, player, base = world
    _open_scales(page, base)
    _fast(page)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 2, "tempo": 160})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('sc-level').value === '2'", timeout=3000)
    page.wait_for_selector('#scales[data-running="yes"]', timeout=3000)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="no"]', timeout=5000)
    assert not errors, errors


# ------------------------------------------------------------------ where it starts


def test_the_scale_opens_on_c_two_octaves_below_middle_c_and_the_start_can_be_chosen(world):
    page, errors, player, base = world
    _open_scales(page, base)
    assert page.locator("#sc-key").input_value() == "0"
    assert page.locator("#sc-octave").input_value() == "2"
    assert page.locator("#sc-octave option").all_inner_texts()[:4] == ["C1", "C2", "C3", "C4"]
    assert page.evaluate("window.ImprovScale.buildSteps(0, 2)[0].left") == 36
    page.select_option("#sc-octave", "3")
    assert "C3" in page.locator("#sc-name").inner_text()
    assert page.locator("#scales").get_attribute("data-start-note") == "48"
    page.select_option("#sc-key", "7")
    assert page.locator("#sc-octave").input_value() == "3", "the chosen octave is kept when the key changes"
    assert page.locator("#scales").get_attribute("data-start-note") == "55"
    assert not errors, errors


def test_the_chosen_start_is_remembered_and_is_what_the_run_is_judged_against(world):
    page, errors, player, base = world
    _open_scales(page, base)
    page.select_option("#sc-octave", "3")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#sc-start:not([disabled])")
    assert page.locator("#sc-octave").input_value() == "3"
    _fast(page)
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 2, "tempo": 160, "startOctave": 3})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    assert page.locator("#sc-verdict").inner_text().startswith("Passed")
    assert not errors, errors


def test_a_start_the_scale_cannot_fit_is_pulled_to_one_it_can(world):
    page, errors, player, base = world
    _open_scales(page, base)
    page.select_option("#sc-octave", "4")
    page.select_option("#sc-level", "3")
    top = int(page.locator("#sc-octave option").last.get_attribute("value"))
    assert top < 4
    assert page.locator("#sc-octave").input_value() == str(top)
    assert not errors, errors


# ------------------------------------------------------------------ the top keys, heard


def test_the_header_shows_the_last_key_the_browser_heard(world):
    page, errors, _, base = world
    _open_scales(page, base)
    assert page.locator("#im-heard").inner_text().strip() == ""
    page.evaluate("window.__press(60)")
    page.wait_for_function("document.getElementById('im-heard').textContent.includes('C4')", timeout=3000)
    assert "60" in page.locator("#im-heard").inner_text()
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('im-heard').textContent.includes('C8')", timeout=3000)
    assert "108" in page.locator("#im-heard").inner_text()
    page.wait_for_selector('#scales[data-running="yes"]', timeout=5000)
    assert not errors, errors


def test_the_control_layer_keeps_hold_of_the_midi_access(world):
    page, errors, _, base = world
    _open_scales(page, base)
    assert page.evaluate("Boolean(window.__improvMidiAccess)"), "a MIDI access nobody holds can be collected, and then no key is heard"
    assert not errors, errors


def test_c8_still_starts_on_the_chords_screen(world):
    page, errors, _, base = world
    page.goto(f"{base}/improv/chords/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#ch-key option').length > 5", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)
    page.wait_for_selector('#ch-start[data-key-hint="C8"]')
    page.evaluate("window.__press(108)")
    page.wait_for_selector('#chords[data-running="yes"]', timeout=5000)
    page.wait_for_function("document.getElementById('im-heard').textContent.includes('C8')")
    assert not errors, errors


# ------------------------------------------------------------------ the band is quiet


def _play_sliders(page, base):
    page.goto(f"{base}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#mix input[type=range]').length === 4", timeout=15000)
    return page.evaluate("Array.from(document.querySelectorAll('#mix input[type=range]')).map((s) => Number(s.value))")


def test_the_band_starts_quiet_enough_to_hear_yourself(world):
    page, errors, _, base = world
    levels = _play_sliders(page, base)
    assert max(levels) <= 45, levels
    assert min(levels) > 0
    assert not errors, errors


def test_a_mix_you_set_is_remembered(world):
    page, errors, _, base = world
    _play_sliders(page, base)
    page.locator("#mix input[type=range]").nth(1).fill("12")
    page.locator("#mix input[type=checkbox]").nth(2).check()
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#mix input[type=range]').length === 4", timeout=15000)
    assert page.locator("#mix input[type=range]").nth(1).input_value() == "12"
    assert page.locator("#mix input[type=checkbox]").nth(2).is_checked()
    assert not errors, errors
