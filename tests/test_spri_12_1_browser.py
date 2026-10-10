"""SPR-I.12.1 improv: the Reading screen in a real browser with a faked piano.

A stage opens at the path's own place with the key written next to the staff, Flow counts in and judges
against the clock and saves the take, a pass moves the stage on, Step waits for the right note, the curtain
hides what is behind the cursor, Show me plays it, and the three piano keys press the three buttons.

Traces: spec ch. 11, backlog SPR-I.12.1.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player, ReadingTake

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri121, pytest.mark.django_db]

PASSWORD = "spri121-browser-7781"

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

# Reads the exercise on the page's own clock. `wrongEvery` makes one note in so many a step too high.
READ_IT = """
async ({ tempo, wrongEvery }) => {
  const host = document.getElementById('reading');
  const notes = window.ImprovReadingPage.active();
  const beat = 60000 / tempo;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  for (const [i, n] of notes.entries()) {
    const due = Number(host.dataset.runStart) + n.beat * beat;
    const gap = due - performance.now();
    if (gap > 0) await wait(gap);
    window.__press(wrongEvery && i % wrongEvery === 1 ? n.midi + 2 : n.midi);
  }
}
"""

MEASURE = "[document.documentElement.scrollHeight - window.innerHeight, document.documentElement.scrollWidth - window.innerWidth]"


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
    user = User.objects.create_user("p121browser", password=PASSWORD)
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
    page.goto(f"{base}/improv/reading/{query}", wait_until="domcontentloaded")
    page.wait_for_selector("#rd-start:not([disabled])", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def _tempo(page, bpm):
    page.fill("#rd-tempo", str(bpm))
    page.dispatch_event("#rd-tempo", "change")


def _run(page, errors, tempo=160, wrong_every=0):
    _tempo(page, tempo)
    page.click("#rd-start")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    page.evaluate(READ_IT, {"tempo": tempo, "wrongEvery": wrong_every})
    try:
        page.wait_for_function("document.getElementById('reading').dataset.saved === 'yes'", timeout=30000)
    except Exception as exc:  # pragma: no cover - a failing run says why
        raise AssertionError(f"the take was not saved: {page.inner_text('#rd-status')!r} {errors}") from exc


def _texts(page, selector):
    return page.locator(selector).evaluate_all("els => els.map((e) => e.textContent)")


def test_the_stage_opens_where_the_path_is_with_the_key_beside_the_staff(world):
    page, errors, player, base = world
    _open(page, base)
    assert page.input_value("#rd-key") == "C" and page.input_value("#rd-hands") == "R"
    assert page.inner_text("#rd-stage-line").startswith("Stage 1 of 36: C major, right hand.")
    assert _texts(page, "#rd-staff .im-st-hand") == ["right hand", "left hand"]
    assert _texts(page, "#rd-staff .im-st-key") == ["C major", "no sharps or flats"]
    assert page.locator("#rd-staff .im-st-note").count() >= 8
    assert page.locator("#rd-staff .im-st-note.im-st-other").count() >= 4, "the left hand is shown in grey"
    assert page.locator("#rd-staff .im-st-note:not(.im-st-other)").count() >= 8
    seed = page.get_attribute("#reading", "data-seed")
    assert page.inner_text("#rd-midi") == "Listening to Fake piano."
    page.select_option("#rd-key", "D")
    page.select_option("#rd-hands", "B")
    assert _texts(page, "#rd-staff .im-st-key") == ["D major", "2 sharps (F#, C#)"]
    assert page.locator("#rd-staff .im-st-note.im-st-other").count() == 0, "both hands are asked for"
    assert page.get_attribute("#reading", "data-seed") == seed, "the piece stays through a change of key and hands"
    page.click("#rd-next")
    assert page.get_attribute("#reading", "data-seed") != seed, "Next is a new piece"
    assert page.locator("#rd-staff .im-st-acc").count() == 4, "two sharps on each staff"
    assert page.evaluate(MEASURE) == [0, 0]
    assert errors == []


def test_a_clean_flow_read_is_saved_passes_and_moves_the_stage_on(world):
    page, errors, player, base = world
    _open(page, base)
    _run(page, errors, tempo=160)
    assert page.locator("#rd-staff .im-st-note.im-st-right").count() == page.locator("#rd-staff .im-st-note:not(.im-st-other)").count()
    seed = page.get_attribute("#reading", "data-seed")
    assert page.inner_text("#rd-verdict").startswith("Passed: 100.")
    assert page.inner_text("#m-score") == "100"
    row = ReadingTake.objects.get(player=player)
    assert row.passed and row.mode == "flow" and row.key == "C" and row.hands == "R" and row.tempo_bpm == 160
    assert len(row.notes) == len(row.results) and row.events
    assert page.input_value("#rd-hands") == "L", "the next stage is the left hand"
    assert page.inner_text("#rd-status").startswith("Passed. Next: C major, left hand.")
    assert page.inner_text("#rd-stage-line").startswith("Stage 1 of 36: C major, right hand. Passed already; the path is at stage 2.")
    assert page.locator("#rd-takes li").count() == 1
    assert page.locator("#rd-staff .im-st-note.im-st-right").count() > 0, "the result stays on the staff to be looked at"
    page.click("#rd-start")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    assert page.inner_text("#rd-stage-line").startswith("Stage 2 of 36: C major, left hand. Pass it in Flow to move on.")
    assert _texts(page, "#rd-staff .im-st-key") == ["C major", "no sharps or flats"]
    assert page.get_attribute("#reading", "data-seed") == seed, "the left hand reads the piece the right hand just passed"
    assert page.locator("#rd-staff .im-st-note.im-st-other").count() >= 4, "now the right hand is the grey one"
    assert page.locator("#rd-staff .im-st-note.im-st-right").count() == 0, "a fresh take"
    page.click("#rd-start")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'no'", timeout=5000)
    assert page.evaluate(MEASURE) == [0, 0]
    assert errors == []


def test_slips_are_coloured_named_and_offered_as_a_bar_to_drill(world):
    page, errors, player, base = world
    _open(page, base, "?key=C&hands=R&seed=5")
    _run(page, errors, tempo=160, wrong_every=3)
    wrong = page.locator("#rd-staff .im-st-note.im-st-wrong").count()
    assert wrong >= 2
    assert page.locator("#rd-staff .im-st-ghost").count() == wrong, "a dotted head where the wrong note was played"
    assert page.inner_text("#rd-verdict").startswith("Not yet:")
    spots = page.locator("#rd-spots li").all_inner_texts()
    assert any("missed or misread" in s for s in spots), spots
    assert page.locator("#rd-fix button").count() >= 1
    assert page.input_value("#rd-hands") == "R", "a fail stays"
    page.locator("#rd-fix button").first.click()
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    assert page.input_value("#rd-mode") == "step"
    assert page.locator("#rd-staff .im-st-note.im-st-out").count() > 0, "the other bars are out"
    page.click("#rd-start")
    assert page.inner_text("#rd-status") == "Stopped. Nothing was saved."
    assert errors == []


def test_step_mode_waits_for_the_right_note_and_cannot_pass(world):
    page, errors, player, base = world
    _open(page, base, "?key=C&hands=R&seed=9&mode=step")
    notes = page.evaluate("window.ImprovReadingPage.active().map((n) => n.midi)")
    page.click("#rd-start")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    assert page.get_attribute("#reading", "data-target") == "0"
    page.evaluate(f"window.__press({notes[0] + 1})")
    assert page.get_attribute("#reading", "data-target") == "0", "a wrong note does not move on"
    assert page.inner_text("#rd-status") == "Not that one. Look again."
    page.evaluate(f"window.__press({notes[0]})")
    page.wait_for_function("document.getElementById('reading').dataset.target !== '0'", timeout=3000)
    for midi in notes[1:]:
        page.evaluate(f"window.__press({midi})")
    page.wait_for_function("document.getElementById('reading').dataset.saved === 'yes'", timeout=10000)
    row = ReadingTake.objects.get(player=player)
    assert row.mode == "step" and not row.passed
    assert page.inner_text("#rd-verdict").startswith("Step mode:")
    assert page.input_value("#rd-hands") == "R"
    assert errors == []


def test_the_curtain_covers_what_is_behind_the_cursor(world):
    page, errors, player, base = world
    _open(page, base, "?key=C&hands=R&seed=3")
    page.check("#rd-curtain")
    _tempo(page, 60)
    page.click("#rd-start")
    page.wait_for_function("document.querySelector('#rd-staff .im-st-curtain').getAttribute('visibility') === 'visible'", timeout=8000)
    page.wait_for_function("Number(document.querySelector('#rd-staff .im-st-curtain').getAttribute('width')) > 40", timeout=10000)
    page.click("#rd-start")
    assert page.evaluate("document.querySelector('#rd-staff .im-st-curtain').getAttribute('visibility')") == "hidden"
    assert errors == []


def test_show_me_plays_it_and_the_piano_keys_press_the_buttons(world):
    page, errors, player, base = world
    _open(page, base, "?key=G&hands=L&seed=4")
    seed = page.get_attribute("#reading", "data-seed")
    page.evaluate("window.__press(106)")
    page.wait_for_function("(was) => document.getElementById('reading').dataset.seed !== was", arg=seed, timeout=3000)
    page.evaluate("window.__press(107)")
    try:
        page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    except Exception as exc:  # pragma: no cover - a failing run says why
        raise AssertionError(f"Show me did not start: {page.inner_text('#rd-status')!r} {errors}") from exc
    assert page.inner_text("#rd-start") == "Stop"
    page.wait_for_function("document.querySelectorAll('#rd-staff .im-st-note.im-st-now').length > 0", timeout=8000)
    page.wait_for_function("document.getElementById('reading').dataset.running === 'no'", timeout=30000)
    assert page.inner_text("#rd-status") == "That was it. Now you."
    assert ReadingTake.objects.filter(player=player).count() == 0, "a demonstration is not a take"
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    assert page.get_attribute("#reading", "data-mode") == "flow"
    page.wait_for_timeout(500)  # the same control key twice within 400 ms counts once
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'no'", timeout=5000)
    assert errors == []
