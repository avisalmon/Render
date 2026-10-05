"""SPR-I.3.3 improv: scale hints while a run is played, in a real browser.

The rule has its own tests under Node. What those cannot see is the Setup screen holding
back until it has enough notes to mean something, then naming the scales the run fits.

Traces: spec ch. 4, feature 2, backlog SPR-I.3.3.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri33, pytest.mark.django_db]

PASSWORD = "spri33-browser-3361"

FAKE_MIDI = """
(() => {
  const access = { inputs: new Map(), outputs: new Map(), onstatechange: null };
  window.__midi = {
    plug(id, name) {
      access.inputs.set(id, { id, name, state: "connected", type: "input", onmidimessage: null });
      if (access.onstatechange) access.onstatechange({ port: access.inputs.get(id) });
    },
    // A run: each note pressed and let go before the next, the way single notes are played.
    run(notes) {
      const port = access.inputs.get("piano");
      for (const note of notes) {
        port.onmidimessage({ data: new Uint8Array([0x90, note, 90]), timeStamp: 0 });
        port.onmidimessage({ data: new Uint8Array([0x80, note, 0]), timeStamp: 0 });
      }
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
    user = User.objects.create_user("p33browser", password=PASSWORD)
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


def _run(page, notes):
    page.evaluate("(notes) => window.__midi.run(notes)", notes)


def _fits(page):
    return page.locator("#scale-fits").inner_text().strip()


def test_a_run_of_five_notes_is_named_and_fewer_is_not(piano):
    page, errors = piano
    assert "Play a run of single notes" in _fits(page)

    _run(page, [60, 62, 64])
    page.wait_for_function("document.getElementById('scale-fits').textContent.includes('more notes')")
    assert _fits(page) == "2 more notes and the scales they fit are named here."

    _run(page, [65])
    page.wait_for_function("document.getElementById('scale-fits').textContent.includes('1 more note ')")
    assert _fits(page) == "1 more note and the scales they fit are named here."

    _run(page, [67])
    page.wait_for_function("document.getElementById('scale-fits').textContent.startsWith('Fits ')")
    assert _fits(page).startswith("Fits C Major (Ionian)")
    assert not errors, errors


def test_a_pentatonic_run_is_named_as_the_pentatonic(piano):
    page, errors = piano
    _run(page, [60, 63, 65, 67, 70])
    page.wait_for_function("document.getElementById('scale-fits').textContent.startsWith('Fits ')")
    assert _fits(page).startswith("Fits C Minor pentatonic")
    assert not errors, errors


def test_the_hint_follows_the_spelling_the_player_asked_for(piano):
    page, errors = piano
    _run(page, [61, 63, 65, 66, 68])
    page.wait_for_function("document.getElementById('scale-fits').textContent.startsWith('Fits ')")
    assert "C#" in _fits(page)
    page.select_option("#note-names", "flats")
    page.wait_for_function("document.getElementById('scale-fits').textContent.includes('Db')")
    assert "C#" not in _fits(page)
    assert not errors, errors


def test_a_run_that_fits_nothing_in_the_table_says_so(piano):
    page, errors = piano
    _run(page, [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71])
    page.wait_for_function("document.getElementById('scale-fits').textContent.includes('no scale')")
    assert _fits(page) == "That run fits no scale in the table."
    assert not errors, errors


def test_chords_and_runs_are_shown_at_the_same_time_without_getting_in_each_others_way(piano):
    page, errors = piano
    _run(page, [60, 62, 64, 65, 67])
    page.wait_for_function("document.getElementById('scale-fits').textContent.startsWith('Fits ')")
    assert page.locator("#heard").inner_text().strip() == "Nothing yet.", "nothing is being held now"

    page.evaluate("window.__midi.plug('piano', 'Clavinova')")
    _run(page, [])
    assert _fits(page).startswith("Fits "), "the run is not thrown away by a device event"
    assert not errors, errors
