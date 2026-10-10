"""SPR-I.13.1 improv: the Pieces screen in a real browser with a faked piano.

A piece opens at the path's own rung, the staff shows both hands and the page turns at the bar line, a clean Flow
take is saved and moves the path on, a slip is named and offered as a one-bar drill that never passes, Step mode
waits, and the three piano keys press the three buttons.

Traces: spec ch. 12, backlog SPR-I.13.1.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player, PieceTake

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri131, pytest.mark.django_db]

PASSWORD = "spri131-browser-5530"

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

# Plays the stretch on the screen on the page's own clock. `wrongEvery` makes one note in so many a step too high.
PLAY_IT = """
async ({ tempo, wrongEvery }) => {
  const host = document.getElementById('repertoire');
  const notes = window.ImprovRepertoirePage.active();
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
    user = User.objects.create_user("p131browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_pieces", stdout=io.StringIO())
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
    page.goto(f"{base}/improv/repertoire/{query}", wait_until="domcontentloaded")
    page.wait_for_selector("#rp-start:not([disabled])", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def _tempo(page, bpm):
    page.fill("#rp-tempo", str(bpm))
    page.dispatch_event("#rp-tempo", "change")


def _run(page, errors, tempo=160, wrong_every=0):
    _tempo(page, tempo)
    page.click("#rp-start")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    page.evaluate(PLAY_IT, {"tempo": tempo, "wrongEvery": wrong_every})
    try:
        page.wait_for_function("document.getElementById('repertoire').dataset.saved === 'yes'", timeout=30000)
    except Exception as exc:  # pragma: no cover - a failing run says why
        raise AssertionError(f"the take was not saved: {page.inner_text('#rp-status')!r} {errors}") from exc


def _texts(page, selector):
    return page.locator(selector).evaluate_all("els => els.map((e) => e.textContent)")


def test_a_piece_opens_at_the_path_with_both_hands_on_the_staff(world):
    page, errors, player, base = world
    _open(page, base)
    assert page.get_attribute("#repertoire", "data-piece") == "ode-to-joy"
    assert page.get_attribute("#repertoire", "data-rung") == "p1-R-slow"
    assert page.locator("#rp-piece option").count() == 4
    assert page.inner_text("#rp-path").startswith("Step 1 of 22. This is the next step on the path.")
    assert page.inner_text("#rp-rung-line").startswith("Bars 1 to 4: right hand, slowly.")
    assert page.input_value("#rp-tempo") == "60"
    assert _texts(page, "#rp-staff .im-st-hand") == ["right hand", "left hand"]
    assert _texts(page, "#rp-staff .im-st-key") == ["C major", "no sharps or flats"]
    assert page.locator("#rp-staff .im-st-note:not(.im-st-other)").count() == 15
    assert page.locator("#rp-staff .im-st-note.im-st-other").count() == 4, "the left hand is shown in grey"
    assert page.inner_text("#rp-midi") == "Listening to Fake piano."
    page.select_option("#rp-piece", "minuet-in-g")
    assert page.get_attribute("#repertoire", "data-piece") == "minuet-in-g"
    assert _texts(page, "#rp-staff .im-st-key") == ["G major", "1 sharp (F#)"]
    assert page.evaluate(MEASURE) == [0, 0]
    assert errors == []


def test_the_prelude_draws_rests_and_ties_and_turns_the_page_at_the_bar_line(world):
    page, errors, player, base = world
    _open(page, base, "?piece=prelude-in-c&rung=whole-B-slow")
    assert page.get_attribute("#repertoire", "data-rung") == "whole-B-slow"
    assert page.locator("#rp-staff .im-st-tie").count() > 0, "the held bass notes are tied"
    assert page.locator("#rp-staff .im-st-rest").count() > 0, "the right hand rests on the first beat of each bar"
    assert page.locator("#rp-staff .im-st-note").count() == 549
    assert page.get_attribute("#rp-staff", "viewBox").startswith("0 ")
    _tempo(page, 160)
    page.click("#rp-start")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    page.wait_for_function("document.getElementById('rp-staff').getAttribute('viewBox').startsWith('960 ')", timeout=20000)
    page.click("#rp-start")
    assert page.inner_text("#rp-status") == "Stopped. Nothing was saved."
    assert PieceTake.objects.filter(player=player).count() == 0
    assert page.evaluate(MEASURE) == [0, 0]
    assert errors == []


def test_a_clean_flow_take_is_saved_passes_and_moves_the_path_on(world):
    page, errors, player, base = world
    _open(page, base)
    _run(page, errors, tempo=160)
    assert page.inner_text("#rp-verdict").startswith("Passed: 100.")
    assert page.inner_text("#m-score") == "100"
    row = PieceTake.objects.get(player=player)
    assert row.passed and row.mode == "flow" and row.rung == "p1-R-slow" and row.hands == "R"
    assert (row.first_bar, row.last_bar) == (1, 4)
    assert len(row.notes) == len(row.results) and row.events
    assert page.input_value("#rp-rung") == "p1-L-slow", "the next step is the left hand"
    assert page.inner_text("#rp-status").startswith("Passed. Next: Bars 1 to 4: left hand, slowly.")
    assert page.locator("#rp-takes li").count() == 1
    assert page.locator("#rp-staff .im-st-note.im-st-right").count() > 0, "the result stays on the staff to be looked at"
    page.click("#rp-start")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    assert page.inner_text("#rp-path").startswith("Step 2 of 22. This is the next step on the path.")
    assert page.locator("#rp-staff .im-st-note.im-st-right").count() == 0, "a fresh take"
    assert page.locator("#rp-staff .im-st-note.im-st-other").count() == 15, "now the right hand is the grey one"
    page.click("#rp-start")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'no'", timeout=5000)
    assert page.evaluate(MEASURE) == [0, 0]
    assert errors == []


def test_slips_are_named_and_a_one_bar_drill_never_passes(world):
    page, errors, player, base = world
    _open(page, base)
    _run(page, errors, tempo=160, wrong_every=3)
    assert page.locator("#rp-staff .im-st-note.im-st-wrong").count() >= 2
    assert page.locator("#rp-staff .im-st-ghost").count() >= 2, "a dotted head where the wrong note was played"
    assert page.inner_text("#rp-verdict").startswith("Not yet:")
    assert page.input_value("#rp-rung") == "p1-R-slow", "a fail stays"
    assert not PieceTake.objects.get(player=player).passed
    assert page.locator("#rp-fix button").count() >= 1
    page.locator("#rp-fix button").first.click()
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    assert page.input_value("#rp-rung") == "drill"
    assert page.input_value("#rp-mode") == "step"
    assert page.get_attribute("#repertoire", "data-rung") == "drill"
    notes = page.evaluate("window.ImprovRepertoirePage.active().map((n) => n.midi)")
    assert 1 <= len(notes) <= 8, "one bar"
    for midi in notes:
        page.evaluate(f"window.__press({midi})")
    page.wait_for_function("document.getElementById('repertoire').dataset.saved === 'yes'", timeout=10000)
    drill = PieceTake.objects.filter(player=player).order_by("-id").first()
    assert drill.rung == "drill" and drill.mode == "step" and not drill.passed
    assert drill.first_bar == drill.last_bar
    assert page.inner_text("#rp-status").startswith("Saved.")
    assert errors == []


def test_step_mode_waits_for_the_right_note_and_cannot_pass(world):
    page, errors, player, base = world
    _open(page, base, "?mode=step")
    notes = page.evaluate("window.ImprovRepertoirePage.exercise().notes.filter((n) => n.hand === 'R').map((n) => n.midi)")
    page.click("#rp-start")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    assert page.get_attribute("#repertoire", "data-target") == "0"
    page.evaluate(f"window.__press({notes[0] + 1})")
    assert page.get_attribute("#repertoire", "data-target") == "0", "a wrong note does not move on"
    for midi in notes:
        page.evaluate(f"window.__press({midi})")
    page.wait_for_function("document.getElementById('repertoire').dataset.saved === 'yes'", timeout=10000)
    row = PieceTake.objects.get(player=player)
    assert row.mode == "step" and not row.passed
    assert page.inner_text("#rp-verdict").startswith("Step mode:")
    assert page.input_value("#rp-rung") == "p1-R-slow"
    assert errors == []


def test_the_three_piano_keys_press_the_three_buttons(world):
    page, errors, player, base = world
    _open(page, base)
    assert page.input_value("#rp-rung") == "p1-R-slow"
    page.evaluate("window.__press(106)")
    page.wait_for_function("document.getElementById('rp-rung').value === 'p1-L-slow'", timeout=3000)
    page.evaluate("window.__press(107)")
    try:
        page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    except Exception as exc:  # pragma: no cover - a failing run says why
        raise AssertionError(f"Show me did not start: {page.inner_text('#rp-status')!r} {errors}") from exc
    assert page.inner_text("#rp-start") == "Stop"
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'no'", timeout=40000)
    assert page.inner_text("#rp-status") == "That was it. Now you."
    assert PieceTake.objects.filter(player=player).count() == 0, "a demonstration is not a take"
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'yes'", timeout=5000)
    page.wait_for_timeout(500)  # the same control key twice within 400 ms counts once
    page.evaluate("window.__press(108)")
    page.wait_for_function("document.getElementById('repertoire').dataset.running === 'no'", timeout=5000)
    assert errors == []
