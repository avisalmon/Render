"""SPR-I.5.2 improv: passing an exercise earns XP and opens the next lesson, in a real browser.

The server's rules are proved by the sibling file. What it cannot see is the Lessons screen
showing a locked lesson and the level line, the Play screen reporting the XP the server gave,
and the lessons opening up on the next visit.

Traces: spec ch. 6, backlog SPR-I.5.2.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Completion, Exercise, Lesson, Progression

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri52, pytest.mark.django_db]

PASSWORD = "spri52-browser-7714"

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
    user = User.objects.create_user("p52browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    iivi = Progression.objects.get(slug="ii-v-i-major")
    first = Lesson.objects.create(
        track="chord_tones", order=1, title="First idea", slug="first-idea", summary="One.", explanation="Read.",
        progression=iivi, style=iivi.default_style, status="published",
    )
    Lesson.objects.create(
        track="guide_tones", order=1, title="Second idea", slug="second-idea", summary="Two.", explanation="Read.",
        progression=iivi, style=iivi.default_style, status="published", prerequisite=first,
    )
    Exercise.objects.create(
        lesson=first, order=1, slug="first-exercise", title="Stay in the scale", instructions="Play.",
        progression=iivi, key="C", tempo=100, style=iivi.default_style, bars=4, scoring_kind="scale_only", scoring_params={},
        pass_score=0, xp=15,
    )

    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    context.add_init_script(FAKE_WORLD)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, user, live_server.url
    context.close()


def _lessons(page, base):
    page.goto(f"{base}/improv/lessons/", wait_until="domcontentloaded")
    page.wait_for_selector('#lessons-tracks .im-take[data-slug="second-idea"]', timeout=10000)
    page.wait_for_function("document.getElementById('lessons-level').textContent !== ''", timeout=10000)


def test_a_new_player_sees_level_one_and_the_second_lesson_locked(world):
    page, errors, user, base = world
    _lessons(page, base)
    assert page.locator("#lessons-level").inner_text() == "Level 1, 0 XP. 50 XP to level 2."
    assert page.locator("#lessons-done").inner_text() == "0 of 2 lessons done."
    first = page.locator('#lessons-tracks .im-take[data-slug="first-idea"]')
    second = page.locator('#lessons-tracks .im-take[data-slug="second-idea"]')
    assert second.get_attribute("data-state") == "locked"
    assert "Locked" in second.inner_text()
    assert "Pass every exercise in First idea to open this." in second.inner_text()
    assert "0 of 1 passed" in first.inner_text()
    assert not errors, errors


def test_a_locked_lesson_can_be_read_but_offers_no_play(world):
    page, errors, user, base = world
    Exercise.objects.create(
        lesson=Lesson.objects.get(slug="second-idea"), order=1, slug="second-exercise", title="Second task", instructions="Play.",
        progression=Progression.objects.get(slug="ii-v-i-major"), key="C", tempo=100, bars=4, scoring_kind="scale_only", scoring_params={},
        pass_score=0, xp=10,
    )
    page.goto(f"{base}/improv/lessons/second-idea/", wait_until="domcontentloaded")
    page.wait_for_selector("#lesson-body:not([hidden])", timeout=10000)
    assert page.locator("#lesson-lock").is_visible()
    assert "Pass every exercise in First idea" in page.locator("#lesson-lock").inner_text()
    assert page.locator("#lesson-exercises .im-take").count() == 1
    assert page.locator("#lesson-exercises a").count() == 0, "no Play link while the lesson is locked"
    assert "Locked" in page.locator("#lesson-exercises").inner_text()
    assert not errors, errors


def test_passing_the_exercise_reports_the_xp_and_opens_the_next_lesson(world):
    page, errors, user, base = world
    page.goto(f"{base}/improv/play/?exercise=first-exercise", wait_until="domcontentloaded")
    page.wait_for_selector("#exercise-panel:not([hidden])", timeout=15000)
    assert "worth 15 XP" in page.locator("#exercise-goal").inner_text()
    page.wait_for_function("document.getElementById('midi-state').textContent.startsWith('Listening to')", timeout=10000)
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_selector('.im-bar-lit[data-bar="0"]', timeout=8000)
    for note in (62, 65, 69):
        page.evaluate(f"window.__piano.press({note})")
    page.wait_for_function("document.getElementById('feedback').textContent.includes('3 notes')", timeout=5000)
    for note in (62, 65, 69):
        page.evaluate(f"window.__piano.release({note})")
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('take-status').textContent.startsWith('Take ')", timeout=10000)
    assert "Passed. +15 XP." in page.locator("#take-status").inner_text()
    assert "passed this one already" in page.locator("#exercise-goal").inner_text()
    assert Completion.objects.get().xp_awarded == 15

    _lessons(page, base)
    assert page.locator("#lessons-level").inner_text() == "Level 1, 15 XP. 35 XP to level 2."
    assert page.locator("#lessons-done").inner_text() == "1 of 2 lessons done."
    assert page.locator('#lessons-tracks .im-take[data-slug="first-idea"] .im-state-done').inner_text() == "Done"
    assert page.locator('#lessons-tracks .im-take[data-slug="second-idea"]').get_attribute("data-state") == "open"
    assert not errors, errors
