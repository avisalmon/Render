"""SPR-I.4.3 improv: a take recorded while playing reaches the database, in a real browser.

The API is proved by the sibling file. What it cannot see is the Play screen opening a
session when the band starts, recording the notes on the take's clock while they are played,
and posting the whole take with its snapshots and verdict at Stop, then closing the session
with the time the band ran when the page is left.

Traces: spec ch. 5 and 6, feature 15, backlog SPR-I.4.3.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import PracticeSession, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri43, pytest.mark.django_db]

PASSWORD = "spri43-browser-2284"

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
    user = User.objects.create_user("p43browser", password=PASSWORD)
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
    yield page, errors, user
    context.close()


def _start(page):
    page.select_option("#progression", "ii-v-i-major")
    page.fill("#bpm", "120")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_selector('.im-bar-lit[data-bar="0"]', timeout=8000)


def test_a_take_played_over_the_band_is_posted_whole_at_stop(play):
    page, errors, user = play
    assert not PracticeSession.objects.exists()
    _start(page)
    page.wait_for_function("document.getElementById('take-status').textContent === ''")
    session = PracticeSession.objects.get(player__user=user)
    assert session.ended_at is None, "the session is opened when the band starts"

    for note in (62, 65, 69):
        page.evaluate(f"window.__piano.press({note})")
    page.wait_for_function("document.getElementById('feedback').textContent.includes('3 notes')", timeout=5000)
    for note in (62, 65, 69):
        page.evaluate(f"window.__piano.release({note})")
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('take-status').textContent.startsWith('Take ')", timeout=10000)

    take = Take.objects.get(player__user=user)
    assert take.session_id == session.pk
    assert take.progression.slug == "ii-v-i-major"
    assert take.chart == take.progression.chart and take.key == "C" and take.tempo == 120
    assert take.loop_from == 0 and take.loop_to == 4 and take.bars == 4
    assert take.judge_version == 2 and take.score is None, "free play has no score"
    ons = [e for e in take.events if e["type"] == "on"]
    assert [e["note"] for e in ons] == [62, 65, 69]
    assert all(e["t_ms"] >= 0 for e in ons), "played after the first downbeat"
    assert sum(1 for e in take.events if e["type"] == "off") == 3
    assert take.metrics["notes"] == 3 and take.metrics["chordTonePct"] == 100
    assert take.duration_ms >= ons[-1]["t_ms"]
    assert "3 notes" in page.locator("#take-status").inner_text()
    assert not errors, errors


def test_a_run_with_nothing_played_is_not_a_take(play):
    page, errors, user = play
    _start(page)
    page.wait_for_function("document.querySelectorAll('.im-bar-lit').length === 1")
    page.click("#play-toggle")
    assert page.locator("#take-status").inner_text() == ""
    assert Take.objects.count() == 0
    assert PracticeSession.objects.filter(player__user=user).count() == 1, "the sitting still counts"
    assert not errors, errors


def test_two_takes_in_one_sitting_share_the_session_and_leaving_closes_it(play):
    page, errors, user = play
    for i in range(2):
        _start(page)
        if i == 0:
            page.wait_for_selector('.im-bar-lit[data-bar="1"]', timeout=8000)
        page.evaluate("window.__piano.press(62)")
        page.wait_for_function("document.getElementById('feedback').textContent.includes('1 note')", timeout=5000)
        page.evaluate("window.__piano.release(62)")
        page.click("#play-toggle")
        page.wait_for_function("document.getElementById('take-status').textContent.startsWith('Take ')", timeout=10000)
    takes = Take.objects.filter(player__user=user)
    assert takes.count() == 2
    assert len({t.session_id for t in takes}) == 1
    session = PracticeSession.objects.get(player__user=user)
    assert session.ended_at is None

    page.goto("about:blank")
    import time

    deadline = time.time() + 5
    while time.time() < deadline:
        session.refresh_from_db()
        if session.ended_at is not None:
            break
        time.sleep(0.2)
    assert session.ended_at is not None, "leaving the page closes the sitting"
    assert session.active_seconds >= 1, "the band ran for a few seconds across the two takes"
    assert not errors, errors
