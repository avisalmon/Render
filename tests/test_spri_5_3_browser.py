"""SPR-I.5.3 improv: the seeded lessons on the screen, in a real browser.

The sibling file proves the rows. What it cannot see is a new player opening the Lessons
screen to six real lessons with only the first one open, and a lesson page showing its text,
its honest authorship note and its three exercises.

Traces: spec ch. 6, backlog SPR-I.5.3.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client


os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri53, pytest.mark.django_db]

PASSWORD = "spri53-browser-7714"

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
def world(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p53browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons"):
        call_command(command, stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    context.add_init_script(FAKE_WORLD)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, live_server.url
    context.close()


def test_a_new_player_sees_twenty_lessons_in_three_levels_and_only_the_first_is_open(world):
    page, errors, base = world
    page.goto(f"{base}/improv/lessons/", wait_until="domcontentloaded")
    page.wait_for_selector('#lessons-tracks .im-take[data-slug="call-and-response-longer"]', timeout=10000)
    page.wait_for_function("document.getElementById('lessons-level').textContent !== ''", timeout=10000)
    cards = page.locator("#lessons-tracks .im-take")
    assert cards.count() == 20
    states = [cards.nth(i).get_attribute("data-state") for i in range(20)]
    assert states.count("open") == 1 and states.count("ahead") == 19
    assert page.locator('#lessons-tracks .im-take[data-slug="chord-tones-on-the-beat"]').get_attribute("data-state") == "open"
    assert page.locator("#lessons-done").inner_text() == "0 of 20 lessons done."
    assert [page.locator("#lessons-tracks section").nth(i).get_attribute("data-level") for i in range(3)] == ["1", "2", "3"]
    assert page.locator('#lessons-tracks section[data-level="1"] .im-take').count() == 7
    assert not errors, errors


def test_the_first_lesson_reads_hears_and_offers_its_three_exercises(world):
    page, errors, base = world
    page.goto(f"{base}/improv/lessons/chord-tones-on-the-beat/", wait_until="domcontentloaded")
    page.wait_for_selector("#lesson-body:not([hidden])", timeout=10000)
    assert "Chord tones on the beat" in page.inner_text("body")
    assert page.locator("#lesson-authorship").is_visible()
    assert page.locator("#lesson-exercises .im-take").count() == 3
    assert page.locator("#lesson-exercises a").count() == 3, "an open lesson links each exercise to Play"
    assert not page.locator("#lesson-ahead").is_visible()
    assert page.locator("#start-here").is_visible(), "the first lesson is open but not yet where the player is"
    assert not errors, errors


def test_a_seeded_exercise_opens_on_the_play_screen_with_its_goal(world):
    page, errors, base = world
    page.goto(f"{base}/improv/play/?exercise=rhythm-charleston", wait_until="domcontentloaded")
    page.wait_for_selector("#exercise-panel:not([hidden])", timeout=15000)
    goal = page.locator("#exercise-goal").inner_text()
    assert "4 bars, pass at 70, worth 15 XP." in goal or "builds on one you have not finished" in goal
    assert not errors, errors
