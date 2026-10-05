"""SPR-I.3.2 improv: the chord the player holds, named on the screen, in a real browser.

The recognizer has golden cases under Node. What those cannot see is the Setup screen
putting a name on what comes in over MIDI, in the spelling the player asked for. The
keyboard is faked; the chords are real.

Traces: spec ch. 4, feature 2, backlog SPR-I.3.2.
"""

import io
import json
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri32, pytest.mark.django_db]

PASSWORD = "spri32-browser-5529"

FAKE_MIDI = """
(() => {
  const access = { inputs: new Map(), outputs: new Map(), onstatechange: null };
  window.__midi = {
    plug(id, name) {
      access.inputs.set(id, { id, name, state: "connected", type: "input", onmidimessage: null });
      if (access.onstatechange) access.onstatechange({ port: access.inputs.get(id) });
    },
    play(notes) {
      const port = access.inputs.get("piano");
      for (const note of notes) port.onmidimessage({ data: new Uint8Array([0x90, note, 90]), timeStamp: 0 });
    },
    release(notes) {
      const port = access.inputs.get("piano");
      for (const note of notes) port.onmidimessage({ data: new Uint8Array([0x80, note, 0]), timeStamp: 0 });
    },
  };
  window.__midi.plug("piano", "Clavinova");
  navigator.requestMIDIAccess = async () => access;
})();
"""


@pytest.fixture(scope="module")
def browser(django_db_setup):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch()
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def piano(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p32browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    context.add_init_script(FAKE_MIDI)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{live_server.url}/improv/setup/", wait_until="domcontentloaded")
    page.wait_for_selector("#midi-row:not([hidden])", timeout=15000)
    yield page, errors
    context.close()


def _play(page, notes):
    page.evaluate("(notes) => window.__midi.play(notes)", notes)


def _release(page, notes):
    page.evaluate("(notes) => window.__midi.release(notes)", notes)


def _heard(page):
    return page.locator("#heard").inner_text().strip()


def test_a_chord_played_on_the_piano_is_named_on_the_screen(piano):
    page, errors = piano
    assert _heard(page) == "Nothing yet."

    _play(page, [60, 64, 67])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'C'")
    assert "C4 E4 G4" in page.locator("#heard-notes").inner_text()

    _play(page, [71])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'Cmaj7'")

    _release(page, [60, 64, 67, 71])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'Nothing yet.'")
    assert page.locator("#heard-notes").inner_text() == ""
    assert not errors, errors


def test_an_inversion_is_named_as_a_slash_chord_not_a_different_chord(piano):
    page, errors = piano
    _play(page, [52, 55, 60])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'C/E'")
    assert not errors, errors


def test_a_rootless_shell_offers_both_chords_it_could_be(piano):
    page, errors = piano
    _play(page, [59, 65])
    page.wait_for_function("document.getElementById('heard').textContent.includes(' or ')")
    assert _heard(page) == "C#7 or G7"
    assert "B3 F4, a tritone" in page.locator("#heard-notes").inner_text()
    assert not errors, errors


def test_the_name_follows_the_spelling_the_player_asked_for(piano):
    page, errors = piano
    _play(page, [61, 65, 68])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'C#'")
    page.select_option("#note-names", "flats")
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'Db'")
    assert "Db4 F4 Ab4" in page.locator("#heard-notes").inner_text()
    assert not errors, errors


def test_a_chord_with_a_note_missing_is_shown_as_a_guess(piano):
    page, errors = piano
    _play(page, [59, 65, 69])
    page.wait_for_function("document.getElementById('heard').textContent.trim() === 'Bm7b5?'")
    assert "or Dm6/B" in page.locator("#heard-notes").inner_text()
    assert not errors, errors


def test_two_notes_are_shown_as_notes_and_an_interval(piano):
    page, errors = piano
    _play(page, [60, 67])
    page.wait_for_function("document.getElementById('heard').textContent.includes('a fifth')")
    assert _heard(page) == "C4 G4, a fifth"
    assert page.locator("#heard-notes").inner_text() == "", "there is nothing to add to two notes"
    assert not errors, errors
