"""SPR-I.8.3 improv: the Scales screen.

The words and the clock are proved under Node (tests/js/spri83.test.js). Here: the Node run is part of
the suite, the page is behind the gate, and in a real browser with a faked piano a run is counted in,
judged against the clock, saved to its player, and the tempo is remembered. C8 starts and stops,
B7 moves to the next key.

Traces: spec ch. 10, backlog SPR-I.8.3.
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

pytestmark = [pytest.mark.spri83, pytest.mark.django_db]

PASSWORD = "spri83-pass-9027"

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

# Plays the whole scale, both hands, on the page's own clock.
PLAY_IT_RIGHT = """
async ({ pc, octaves, tempo }) => {
  const host = document.getElementById('scales');
  const steps = window.ImprovScale.buildSteps(pc, octaves);
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
    user = User.objects.create_user("p83browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_fingerings"):
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


def _open(page, base):
    page.goto(f"{base}/improv/scales/", wait_until="domcontentloaded")
    page.wait_for_selector("#sc-start:not([disabled])", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)


def test_the_words_and_the_clock_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri83.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ the page and the gate


def test_the_page_is_behind_the_gate(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p83member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p83stranger", password=PASSWORD)
    visitor = Client().get("/improv/scales/")
    assert visitor.status_code == 302
    assert visitor.headers["Location"].startswith("/improv/?next=")
    other = Client()
    other.force_login(stranger)
    assert other.get("/improv/scales/").status_code == 200, "anyone signed in may open it"
    mine = Client()
    mine.force_login(member)
    response = mine.get("/improv/scales/")
    assert response.status_code == 200
    text = response.content.decode()
    assert "/improv/api/scale-fingerings/" in text and "/improv/api/scale-runs/" in text and "/improv/api/player/" in text
    assert "data-key-action=\"primary\"" in text and "data-key-action=\"secondary\"" in text


# ------------------------------------------------------------------ in a browser


def test_it_opens_on_c_at_sixty_with_the_fingering_and_no_errors(world):
    page, errors, _, base = world
    _open(page, base)
    assert page.locator("#sc-key option").all_inner_texts() == ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
    assert page.locator("#sc-key").input_value() == "0"
    assert page.locator("#sc-tempo").input_value() == "60"
    assert page.locator("#sc-strip .im-sc-cell").count() == 29
    assert page.locator("#sc-keyboard .im-key").count() > 24
    assert "left finger" in page.locator("#sc-line").inner_text()
    page.select_option("#sc-level", "3")
    assert page.locator("#sc-strip .im-sc-cell").count() == 57
    assert "88-key" in page.locator("#sc-line").inner_text()
    assert not errors, errors


def test_the_tempo_is_remembered_for_next_time(world):
    page, errors, player, base = world
    _open(page, base)
    page.locator("#sc-tempo").fill("84")
    page.keyboard.press("Tab")
    page.wait_for_function("document.getElementById('sc-line').textContent.includes('84 bpm')")
    page.wait_for_timeout(300)
    player.refresh_from_db()
    assert player.trainer_tempo == 84
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#sc-start:not([disabled])")
    assert page.locator("#sc-tempo").input_value() == "84"
    assert not errors, errors


def test_a_tempo_out_of_range_is_pulled_back_before_it_is_saved(world):
    page, errors, player, base = world
    _open(page, base)
    page.locator("#sc-tempo").fill("500")
    page.keyboard.press("Tab")
    page.wait_for_function("document.getElementById('sc-tempo').value === '160'")
    page.wait_for_timeout(300)
    player.refresh_from_db()
    assert player.trainer_tempo == 160
    assert not errors, errors


def test_a_scale_played_right_in_tempo_is_judged_and_saved(world):
    page, errors, player, base = world
    _open(page, base)
    page.locator("#sc-tempo").fill("160")
    page.keyboard.press("Tab")
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-running="yes"]')
    assert page.locator("#sc-start").inner_text() == "Stop"
    assert page.locator("#sc-key").is_disabled()
    page.evaluate(PLAY_IT_RIGHT, {"pc": 0, "octaves": 2, "tempo": 160})
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=10000)
    assert page.locator("#sc-verdict").inner_text().startswith("Passed")
    assert page.locator("#sc-misses").inner_text() == "No note was missed."
    assert page.locator("#sc-start").inner_text() == "Start"
    run = ScaleRun.objects.get(player=player)
    assert run.root_pc == 0 and run.octaves == 2 and run.notes_per_beat == 2 and run.tempo_bpm == 160
    assert run.passed and run.score >= 90 and run.missed_steps == []
    assert page.locator("#sc-runs li").count() == 1
    assert page.locator("#sc-level").input_value() == "2"
    page.select_option("#sc-level", "1")
    assert "Your best here" in page.locator("#sc-best").inner_text()
    assert not errors, errors


def test_a_silent_run_is_a_miss_and_still_saved(world):
    page, errors, player, base = world
    _open(page, base)
    page.locator("#sc-tempo").fill("160")
    page.keyboard.press("Tab")
    page.click("#sc-start")
    page.wait_for_selector('#scales[data-saved="yes"]', timeout=15000)
    assert page.locator("#sc-verdict").inner_text().startswith("Not yet")
    assert page.locator("#sc-misses").inner_text().startswith("Missed:")
    run = ScaleRun.objects.get(player=player)
    assert not run.passed and run.score == 0 and len(run.missed_steps) == 29
    assert not errors, errors


def test_c8_starts_and_stops_and_a_stopped_run_is_not_saved(world):
    page, errors, player, base = world
    _open(page, base)
    page.wait_for_selector('#sc-start[data-key-hint="C8"]')
    page.evaluate("window.__press(108)")
    page.wait_for_selector('#scales[data-running="yes"]', timeout=5000)
    page.wait_for_selector('#sc-start[data-key-hint="C8"]')
    page.wait_for_timeout(500)
    page.evaluate("window.__press(108)")
    page.wait_for_selector('#scales[data-running="no"]', timeout=5000)
    assert page.locator("#sc-start").inner_text() == "Start"
    assert "Nothing was saved" in page.locator("#sc-status").inner_text()
    assert ScaleRun.objects.count() == 0
    assert not errors, errors


def test_b7_moves_round_the_circle_of_fifths(world):
    page, errors, _, base = world
    _open(page, base)
    page.wait_for_selector('#sc-next[data-key-hint="B7"]')
    page.evaluate("window.__press(107)")
    page.wait_for_function("document.getElementById('sc-key').value === '7'", timeout=5000)
    assert "G major" in page.locator("#sc-name").inner_text()
    assert not errors, errors


def test_the_work_on_this_line_starts_with_where_to_begin(world):
    page, errors, _, base = world
    _open(page, base)
    page.wait_for_function("document.getElementById('scales').dataset.work !== undefined", timeout=5000)
    assert "No scale run yet" in page.locator("#tr-work").inner_text()
    assert not errors, errors
