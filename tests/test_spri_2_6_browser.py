"""SPR-I.2.6 improv: changing things while it plays, and the output picker, in a real browser.

The rules are proved under Node and the template against the scripts by the sibling file.
What neither can see is the page doing its job: the key, tempo, feel and band controls stay
live while it plays and a change shows on the chart at a bar line, the shape controls stay
locked, and the output picker lists the sound outputs, sends the sound to the one chosen and
stays out of the way where the browser cannot do it. The devices are faked, because a test
machine has no choice of speakers; what is checked is that the page asks the browser for the
right thing.

Traces: spec ch. 3 and 8, backlog SPR-I.2.6.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri26, pytest.mark.django_db]

PASSWORD = "spri26-browser-4417"

FAKE_OUTPUTS = """
(() => {
  window.__sinks = [];
  const devices = [
    { kind: "audioinput", deviceId: "mic1", label: "Microphone" },
    { kind: "audiooutput", deviceId: "default", label: "Default - Speakers" },
    { kind: "audiooutput", deviceId: "spk1", label: "Speakers" },
    { kind: "audiooutput", deviceId: "usb1", label: "USB Audio" },
  ];
  window.__devices = devices;
  navigator.mediaDevices.enumerateDevices = async () => window.__devices.slice();
  const C = window.AudioContext || window.webkitAudioContext;
  C.prototype.setSinkId = async function (id) { window.__sinks.push(id); };
})();
"""

NO_SINK = """
(() => {
  const C = window.AudioContext || window.webkitAudioContext;
  delete C.prototype.setSinkId;
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
def open_play(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p26browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value
    contexts = []
    errors = []

    def opener(init_script):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        contexts.append(context)
        context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
        context.add_init_script(init_script)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{live_server.url}/improv/play/", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
        return page

    yield opener, errors
    for context in contexts:
        context.close()


def _bar0(page):
    return page.locator('.im-bar[data-bar="0"] .im-bar-chords').inner_text().split()


def _play_blues_fast(page, progression="ii-v-i-major", bpm="200"):
    page.select_option("#progression", progression)
    page.fill("#bpm", bpm)
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_selector(".im-bar-lit", timeout=8000)


# -------------------------------------------------------------- changes while it plays


def test_the_shape_of_the_take_is_locked_and_the_rest_moves_while_it_plays(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    _play_blues_fast(page)
    for locked in ("progression", "countin", "first", "last", "metronome"):
        assert page.locator(f"#{locked}").is_disabled(), f"{locked} should be locked while it plays"
    for live in ("style", "key", "bpm", "swing"):
        assert page.locator(f"#{live}").is_enabled(), f"{live} should stay live while it plays"
    page.click("#play-toggle")
    for locked in ("progression", "countin", "first", "last", "metronome"):
        assert page.locator(f"#{locked}").is_enabled(), f"{locked} should be free again after Stop"
    assert not errors, errors


def test_a_key_change_while_it_plays_shows_on_the_chart_at_a_bar_line(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    _play_blues_fast(page)
    assert _bar0(page) == ["Dm7"]
    page.select_option("#key", "Eb")
    assert "next bar" in page.locator("#play-status").inner_text()
    page.wait_for_function(
        "document.querySelector('.im-bar[data-bar=\"0\"] .im-bar-chords').textContent.trim() === 'Fm7'",
        timeout=10000,
    )
    assert "Eb" in page.locator("#chart-title").inner_text()
    assert page.locator("#play-toggle").inner_text() == "Stop", "it kept playing"
    assert page.locator("#play-error").is_hidden()
    page.click("#play-toggle")
    assert not errors, errors


def test_a_tempo_change_while_it_plays_is_accepted_and_clamped(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    _play_blues_fast(page)
    page.fill("#bpm", "240")
    page.dispatch_event("#bpm", "change")
    assert page.locator("#play-status").inner_text() == "240 bpm from the next bar."
    page.fill("#bpm", "9999")
    page.dispatch_event("#bpm", "change")
    assert int(page.locator("#bpm").input_value()) < 9999
    assert page.locator("#play-toggle").inner_text() == "Stop"
    page.click("#play-toggle")
    assert not errors, errors


def test_a_change_of_feel_and_of_band_while_it_plays_is_accepted(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    _play_blues_fast(page)
    other = page.evaluate(
        "(() => { const s = document.getElementById('style'); return [...s.options].map(o => o.value).find(v => v !== s.value); })()"
    )
    assert other, "there should be a second band for a 4/4 progression"
    page.select_option("#style", other)
    assert "from the next bar" in page.locator("#play-status").inner_text()
    assert page.locator("#play-error").is_hidden()

    current = page.locator("#swing").input_value()
    flipped = page.evaluate(
        "(cur) => [...document.getElementById('swing').options].map(o => o.value).find(v => v !== cur)", current
    )
    if flipped:
        page.select_option("#swing", flipped)
        assert "from the next bar" in page.locator("#play-status").inner_text()
    assert page.locator("#play-toggle").inner_text() == "Stop"
    page.click("#play-toggle")
    assert not errors, errors


def test_stopping_drops_a_change_that_was_waiting_for_its_bar_line(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    _play_blues_fast(page, bpm="40")
    page.select_option("#key", "Eb")
    page.click("#play-toggle")
    assert page.locator("#play-toggle").inner_text() == "Play"
    assert _bar0(page) == ["Fm7"], "the chart shows the key that was chosen, once it has stopped"
    assert page.locator("#bpm").is_enabled()
    assert not errors, errors


# ----------------------------------------------------------------------- output picker


def test_the_output_picker_lists_the_outputs_and_not_the_browsers_duplicates(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    page.wait_for_selector("#output-row:not([hidden])", timeout=10000)
    labels = page.locator("#output option").all_inner_texts()
    assert labels == ["System default: Speakers", "Speakers", "USB Audio"], labels
    assert page.locator("#output").input_value() == ""
    assert page.locator("#output-note").is_hidden(), "names are available, so there is nothing to explain"
    assert not errors, errors


def test_choosing_an_output_sends_the_sound_there_and_it_survives_play(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    page.wait_for_selector("#output-row:not([hidden])", timeout=10000)
    page.select_option("#output", "usb1")
    assert "Sound will start there" in page.locator("#play-status").inner_text()
    assert page.evaluate("window.__sinks") == [], "no audio context yet, so nothing to redirect"

    _play_blues_fast(page)
    assert page.evaluate("window.__sinks")[-1] == "usb1", "the band started on the chosen output"

    page.select_option("#output", "spk1")
    page.wait_for_function("window.__sinks[window.__sinks.length - 1] === 'spk1'")
    assert "Sound moved" in page.locator("#play-status").inner_text()
    page.select_option("#output", "")
    page.wait_for_function("window.__sinks[window.__sinks.length - 1] === ''")
    page.click("#play-toggle")
    assert not errors, errors


def test_an_output_that_is_unplugged_while_chosen_falls_back_to_the_default(open_play):
    opener, errors = open_play
    page = opener(FAKE_OUTPUTS)
    page.wait_for_selector("#output-row:not([hidden])", timeout=10000)
    page.select_option("#output", "usb1")
    page.evaluate(
        "(() => { window.__devices = window.__devices.filter(d => d.deviceId !== 'usb1');"
        " navigator.mediaDevices.dispatchEvent(new Event('devicechange')); })()"
    )
    page.wait_for_function("document.querySelectorAll('#output option').length === 2")
    assert page.locator("#output").input_value() == ""
    assert "back on the system default" in page.locator("#play-status").inner_text()
    assert not errors, errors


def test_a_failing_output_is_reported_and_the_sound_stays_on_the_default(open_play):
    opener, errors = open_play
    failing = FAKE_OUTPUTS.replace(
        "window.__sinks.push(id); };",
        "if (id === 'usb1') throw new Error('Device not available'); window.__sinks.push(id); };",
    )
    page = opener(failing)
    page.wait_for_selector("#output-row:not([hidden])", timeout=10000)
    _play_blues_fast(page)
    page.select_option("#output", "usb1")
    page.wait_for_selector("#play-error:not([hidden])", timeout=5000)
    assert "system default" in page.locator("#play-error").inner_text()
    assert page.locator("#output").input_value() == ""
    assert page.locator("#play-toggle").inner_text() == "Stop", "the band keeps playing"
    page.click("#play-toggle")
    assert not errors, errors


def test_where_the_browser_cannot_choose_an_output_the_picker_is_hidden_and_says_why(open_play):
    opener, errors = open_play
    page = opener(NO_SINK)
    page.wait_for_selector("#output-note:not([hidden])", timeout=10000)
    assert page.locator("#output-row").is_hidden()
    assert "system" in page.locator("#output-note").inner_text().lower()
    _play_blues_fast(page)
    assert page.locator("#play-toggle").inner_text() == "Stop", "Play works without the picker"
    page.click("#play-toggle")
    assert not errors, errors
