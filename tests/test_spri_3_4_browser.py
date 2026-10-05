"""SPR-I.3.4 improv: calibration end to end in a real browser.

The click really plays, the taps really arrive over MIDI, and the offset really reaches the
database. The keyboard is faked and the audio clock's output timestamp is stood in for, since
a headless browser makes no sound and reports no speaker; everything between them is the
app's own.

The taps here are on a perfect grid of the click's own period, so whatever phase they happen
to land on, every tap is the same distance from its click: the spread is near zero and the run
is storable. That is what makes this a test and not a measurement. **The measurement itself
is Avi at his piano**, which is why SPR-I.3.4 is an at-the-piano sprint.

Traces: spec ch. 4 and 9, feature 14, backlog SPR-I.3.4.
"""

import os

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from improv.models import Player

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri34, pytest.mark.django_db]

PASSWORD = "spri34-browser-6680"
GAP_MS = 750  # the click's own period at 80 bpm

# A keyboard that can tap on a grid, and an audio clock that will say when its sound comes
# out. A headless browser's getOutputTimestamp stays empty, so it is stood in for here with
# what a real one reports: the audio time and the performance time of the same moment.
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
    // Taps on a steady grid, starting `firstIn` ms from now, `gap` ms apart.
    tapGrid(count, gap, firstIn) {
      const start = performance.now() + firstIn;
      for (let i = 0; i < count; i++) {
        const at = start + i * gap;
        port.onmidimessage({ data: new Uint8Array([0x90, 60, 90]), timeStamp: at });
        port.onmidimessage({ data: new Uint8Array([0x80, 60, 0]), timeStamp: at });
      }
    },
    // Taps scattered about: the player lost the pulse.
    tapScattered(count, gap, firstIn) {
      const start = performance.now() + firstIn;
      const wobble = [0, 180, -160, 90, -200, 140, -60, 210, -120, 40, 170, -190, 60, -80, 200, -140];
      for (let i = 0; i < count; i++) {
        const at = start + i * gap + wobble[i % wobble.length];
        port.onmidimessage({ data: new Uint8Array([0x90, 60, 90]), timeStamp: at });
        port.onmidimessage({ data: new Uint8Array([0x80, 60, 0]), timeStamp: at });
      }
    },
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
def setup_page(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p34browser", password=PASSWORD)
    user.groups.add(group)

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
    page.goto(f"{live_server.url}/improv/setup/", wait_until="domcontentloaded")
    page.wait_for_selector("#midi-row:not([hidden])", timeout=15000)
    yield page, errors, user
    context.close()


def test_sixteen_taps_on_the_click_are_counted_measured_and_stored(setup_page):
    page, errors, user = setup_page
    assert page.locator("#latency").inner_text() == "Not calibrated yet."

    page.click("#calibrate")
    assert page.locator("#calibrate").is_disabled(), "one run at a time"
    assert "0 of 16 taps" in page.locator("#cal-count").inner_text()
    assert "Listen" in page.locator("#cal-result").inner_text()

    # The four count-in clicks first, then sixteen taps on the click's own period.
    page.evaluate("([gap]) => window.__piano.tapGrid(16, gap, 4 * gap + 400)", [GAP_MS])
    page.wait_for_function("document.getElementById('cal-count').textContent.startsWith('16 of 16')", timeout=25000)

    page.wait_for_selector("#cal-save:not([hidden])", timeout=25000)
    said = page.locator("#cal-result").inner_text()
    assert "give or take" in said, said
    assert any(word in said for word in ("early", "late", "right on the click")), said
    assert page.locator("#calibrate").is_enabled(), "a run can be done again"

    page.click("#cal-save")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=10000)
    stored = Player.objects.get(user=user).latency_offset_ms
    assert abs(stored) <= GAP_MS / 2, f"an offset of {stored} ms is not a tap on this click"
    assert page.locator("#latency").inner_text() == (
        f"Calibrated: your notes are shifted by {stored} ms before they are judged."
    )
    assert page.locator("#cal-save").is_hidden(), "there is nothing left to save"
    assert not errors, errors


def test_a_run_all_over_the_place_is_not_stored_and_says_why(setup_page):
    page, errors, user = setup_page
    page.click("#calibrate")
    page.evaluate("([gap]) => window.__piano.tapScattered(16, gap, 4 * gap + 400)", [GAP_MS])
    page.wait_for_function("document.getElementById('cal-count').textContent.startsWith('16 of 16')", timeout=25000)
    page.wait_for_function("document.getElementById('calibrate').disabled === false", timeout=25000)

    said = page.locator("#cal-result").inner_text()
    assert "uneven" in said or "spread" in said, said
    assert page.locator("#cal-save").is_hidden(), "a bad run offers nothing to save"
    assert Player.objects.get(user=user).latency_offset_ms == 0, "nothing was stored"
    assert page.locator("#latency").inner_text() == "Not calibrated yet."
    assert not errors, errors


def test_tapping_nothing_at_all_is_said_plainly(setup_page):
    page, errors, user = setup_page
    page.click("#calibrate")
    page.wait_for_function("document.getElementById('calibrate').disabled === false", timeout=25000)
    said = page.locator("#cal-result").inner_text()
    assert "Not enough taps" in said, said
    assert "0 of 16" in said, said
    assert page.locator("#cal-save").is_hidden()
    assert Player.objects.get(user=user).latency_offset_ms == 0
    assert not errors, errors
