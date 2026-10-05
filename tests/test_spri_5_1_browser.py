"""SPR-I.5.1 improv: a lesson is read, heard and played, in a real browser.

The API and the logic are proved by the sibling files. What they cannot see is the lesson page
drawing the explanation as text, offering the exercise, the Hear step sounding the demo, and
the Play screen opening on the exercise, scoring the take against it and saving it with the
exercise named.

Traces: spec ch. 6, backlog SPR-I.5.1.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Exercise, Lesson, Phrase, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri51, pytest.mark.django_db]

PASSWORD = "spri51-browser-3391"

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

NOTES = [
    {"midi": 62, "beat": 0, "length": 1, "velocity": 90},
    {"midi": 65, "beat": 1, "length": 1, "velocity": 88},
    {"midi": 69, "beat": 2, "length": 2, "velocity": 92},
]

EXPLANATION = "## Why\n\nOne scale per chord, **not** a <b>guess</b>.\n\n- Dm7: D dorian\n- G7: G mixolydian"


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
    user = User.objects.create_user("p51browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    iivi = Progression.objects.get(slug="ii-v-i-major")
    phrase = Phrase.objects.create(name="D F A", slug="d-f-a", kind="demo", notes=NOTES, length_beats=4, written_in_key="C", is_preset=True)
    lesson = Lesson.objects.create(
        track="scales_modes", order=1, title="A scale for each chord", slug="scale-each-chord", level=1,
        summary="Fit one scale to each chord.", explanation=EXPLANATION,
        demo_phrase=phrase, progression=iivi, style=iivi.default_style, status="published", authorship="ai_drafted",
    )
    Exercise.objects.create(
        lesson=lesson, order=1, slug="scale-every-chord", title="Stay in the scale", instructions="Play only notes of the chord's scale.",
        progression=iivi, key="C", tempo=100, style=iivi.default_style, bars=4, scoring_kind="scale_only", scoring_params={},
        pass_score=60, xp=15,
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


def _open_lesson(page, base):
    page.goto(f"{base}/improv/lessons/scale-each-chord/", wait_until="domcontentloaded")
    page.wait_for_selector("#lesson-body:not([hidden])", timeout=10000)


def test_the_lessons_screen_lists_the_lesson_and_opens_it(world):
    page, errors, user, base = world
    page.goto(f"{base}/improv/lessons/", wait_until="domcontentloaded")
    page.wait_for_selector('#lessons-tracks .im-take[data-slug="scale-each-chord"]', timeout=10000)
    assert "1 lesson" in page.locator("#lessons-status").inner_text()
    assert "A scale for each chord" in page.locator("#lessons-tracks").inner_text()
    page.click('#lessons-tracks .im-take[data-slug="scale-each-chord"] a')
    page.wait_for_selector("#lesson-body:not([hidden])", timeout=10000)
    assert page.locator("#lesson-title").inner_text() == "A scale for each chord"
    assert not errors, errors


def test_the_explanation_is_drawn_as_text_never_as_markup(world):
    page, errors, user, base = world
    _open_lesson(page, base)
    assert page.locator("#lesson-text b").count() == 0, "a tag in the text stays text"
    assert "<b>guess</b>" in page.locator("#lesson-text").inner_text()
    assert page.locator("#lesson-text strong").count() == 1
    assert page.locator("#lesson-text ul li").count() == 2
    assert page.locator("#lesson-exercises .im-take").count() == 1
    assert not errors, errors


def test_a_lesson_that_does_not_exist_says_so(world):
    page, errors, user, base = world
    page.goto(f"{base}/improv/lessons/nothing-here/", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('lesson-title').textContent === 'No such lesson'", timeout=10000)
    assert page.locator("#lesson-body").is_hidden()
    assert not errors, errors


def test_the_hear_step_plays_the_demo_over_the_band_and_stops(world):
    page, errors, user, base = world
    _open_lesson(page, base)
    page.click("#hear-toggle")
    page.wait_for_function("document.getElementById('hear-toggle').textContent === 'Stop'", timeout=8000)
    assert "phrase" in page.locator("#hear-status").inner_text()
    page.wait_for_selector("#hear-chart .im-bar-lit", timeout=8000)
    page.click("#hear-toggle")
    page.wait_for_function("document.getElementById('hear-toggle').textContent === 'Hear it'")
    assert page.locator("#hear-error").is_hidden()
    assert not errors, errors


def test_play_it_opens_the_exercise_and_the_take_is_saved_for_it(world):
    page, errors, user, base = world
    _open_lesson(page, base)
    page.click("#lesson-exercises a")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    page.wait_for_selector("#exercise-panel:not([hidden])", timeout=10000)
    assert page.locator("#exercise-title").inner_text() == "Stay in the scale"
    assert page.locator("#progression").input_value() == "ii-v-i-major"
    assert page.locator("#bpm").input_value() == "100"
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

    take = Take.objects.get(player__user=user)
    assert take.exercise is not None and take.exercise.slug == "scale-every-chord"
    assert take.score is not None
    result = page.locator("#exercise-result").inner_text()
    assert result.startswith("Score "), result
    assert not errors, errors


def test_changing_the_loop_makes_the_take_free_play(world):
    page, errors, user, base = world
    page.goto(f"{base}/improv/play/?exercise=scale-every-chord", wait_until="domcontentloaded")
    page.wait_for_selector("#exercise-panel:not([hidden])", timeout=15000)
    page.wait_for_function("document.getElementById('midi-state').textContent.startsWith('Listening to')", timeout=10000)
    page.fill("#last", "2")
    page.dispatch_event("#last", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_selector('.im-bar-lit[data-bar="0"]', timeout=8000)
    page.evaluate("window.__piano.press(62)")
    page.wait_for_function("document.getElementById('feedback').textContent.includes('1 note')", timeout=5000)
    page.evaluate("window.__piano.release(62)")
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('take-status').textContent.startsWith('Take ')", timeout=10000)
    take = Take.objects.get(player__user=user)
    assert take.exercise is None, "a shortened loop is not the exercise"
    assert not errors, errors
