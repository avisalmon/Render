"""SPR-I.4.2 improv: playing over the band and being told, live, in a real browser.

The judge has its golden takes. What those cannot see is the Play screen hearing the piano
while the band plays, putting each note on the take's clock, colouring the key with the
judge's class, naming the chord held, and summing it up in words; then, at Stop, settling
everything with the same judge. The keyboard is faked and the audio clock's output timestamp
is stood in for; the band, the scheduler and the judge are the app's own.

Traces: spec ch. 5 and 8, features 13 and 14, backlog SPR-I.4.2.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri42, pytest.mark.django_db]

PASSWORD = "spri42-browser-9910"

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
def play(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p42browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    context.add_init_script(FAKE_WORLD)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{live_server.url}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    page.wait_for_function("document.getElementById('midi-state').textContent.startsWith('Listening to')", timeout=10000)
    yield page, errors
    context.close()


def _start(page):
    page.select_option("#progression", "ii-v-i-major")
    page.fill("#bpm", "60")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_selector('.im-bar-lit[data-bar="0"]', timeout=8000)


def _key_class(page, note):
    return page.eval_on_selector(f'.im-key[data-note="{note}"]', "k => k.className")


def test_the_keys_are_drawn_and_the_piano_is_heard_before_playing(play):
    page, errors = play
    assert page.locator("#keys .im-key").count() >= 60
    assert "Clavinova" in page.locator("#midi-state").inner_text()
    page.evaluate("window.__piano.press(62)")
    page.evaluate("window.__piano.press(65)")
    page.evaluate("window.__piano.press(69)")
    page.wait_for_function("document.getElementById('heard').textContent === 'Dm'")
    assert "im-key-on" in _key_class(page, 62), "before the band plays a key is only lit, not judged"
    for n in (62, 65, 69):
        page.evaluate(f"window.__piano.release({n})")
    page.wait_for_function("document.getElementById('heard').textContent === ''")
    assert not errors, errors


def test_a_chord_tone_over_the_band_goes_green_and_a_guide_tone_brighter(play):
    page, errors = play
    _start(page)
    # Bar 1 is Dm7 for four slow seconds: F is the third, D the root.
    page.evaluate("window.__piano.press(65)")
    page.wait_for_function("document.querySelector('.im-key[data-note=\"65\"]').classList.contains('im-key-guide')", timeout=4000)
    page.evaluate("window.__piano.press(62)")
    page.wait_for_function("document.querySelector('.im-key[data-note=\"62\"]').classList.contains('im-key-chord')", timeout=4000)
    assert "chord tones" in page.locator("#feedback").inner_text()
    assert page.locator("#heard").inner_text() in ("D4 F4, a minor third", "Dm7?", "Dm", "D4 F4, a minor third")
    page.click("#play-toggle")
    assert not errors, errors


def test_an_outside_note_is_amber_while_undecided_and_settles(play):
    page, errors = play
    _start(page)
    page.evaluate("window.__piano.press(63)")
    page.wait_for_function("document.querySelector('.im-key[data-note=\"63\"]').classList.contains('im-key-pending')", timeout=4000)
    # A beat at 60 bpm is a second; with nothing after it, the Eb settles as outside.
    page.wait_for_function("document.querySelector('.im-key[data-note=\"63\"]').classList.contains('im-key-outside')", timeout=4000)
    assert "outside" in page.locator("#feedback").inner_text()
    page.click("#play-toggle")
    assert not errors, errors


def test_stopping_settles_the_take_and_keeps_the_summary(play):
    page, errors = play
    _start(page)
    page.evaluate("window.__piano.press(62)")
    page.wait_for_function("document.getElementById('feedback').textContent.includes('1 note')", timeout=4000)
    page.evaluate("window.__piano.release(62)")
    page.click("#play-toggle")
    summary = page.locator("#feedback").inner_text()
    assert "1 note" in summary and "100% chord tones" in summary, summary
    assert page.locator("#keys .im-key-chord").count() == 0, "nothing is held after Stop"
    assert not errors, errors


def test_a_new_take_starts_clean(play):
    page, errors = play
    _start(page)
    page.evaluate("window.__piano.press(62)")
    page.wait_for_function("document.getElementById('feedback').textContent.includes('1 note')", timeout=4000)
    page.evaluate("window.__piano.release(62)")
    page.click("#play-toggle")
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('feedback').textContent === 'Play something.'", timeout=4000)
    page.click("#play-toggle")
    assert not errors, errors
