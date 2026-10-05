"""SPR-I.3.1 improv: the Setup screen with a keyboard attached, in a real browser.

The rules are proved under Node and the template against the script by the sibling file.
What neither can see is the page doing its job: asking for MIDI, listing the keyboards,
showing what is played, saving the preferences, and surviving a keyboard being pulled out
and plugged back in with a new port id. The keyboard is faked, because a test machine has no
piano; what is checked is that the page asks the browser for the right thing and keeps up
with what it is told.

Traces: spec ch. 4 and 8, feature 23, backlog SPR-I.3.1.
"""

import json
import os

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from improv.models import Player

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri31, pytest.mark.django_db]

PASSWORD = "spri31-browser-9043"

# A stand-in for Web MIDI. Ports stay in the map when they are unplugged, as real ones do,
# and a replug can bring the same keyboard back under a different id, which is the whole
# reason the app remembers the name instead.
FAKE_MIDI = """
(() => {
  const access = { inputs: new Map(), outputs: new Map(), onstatechange: null, sysexEnabled: false };
  const announce = (port) => { if (access.onstatechange) access.onstatechange({ port }); };
  window.__midi = {
    access,
    asked: 0,
    plug(id, name) {
      const port = access.inputs.get(id) || { id, name, type: "input", onmidimessage: null };
      port.name = name;
      port.state = "connected";
      access.inputs.set(id, port);
      announce(port);
    },
    unplug(id) {
      const port = access.inputs.get(id);
      if (!port) return;
      port.state = "disconnected";
      port.onmidimessage = null;
      announce(port);
    },
    forget(id) {
      const port = access.inputs.get(id);
      access.inputs.delete(id);
      if (port) announce(port);
    },
    press(id, note, velocity) {
      const port = access.inputs.get(id);
      if (port && port.onmidimessage) {
        port.onmidimessage({ data: new Uint8Array([velocity ? 0x90 : 0x80, note, velocity || 0]), timeStamp: 0 });
      }
    },
  };
  for (const [id, name] of __DEVICES__) window.__midi.plug(id, name);
  navigator.requestMIDIAccess = async (options) => {
    window.__midi.asked += 1;
    window.__midi.options = options;
    return access;
  };
})();
"""

NO_MIDI = "(() => { delete Navigator.prototype.requestMIDIAccess; })();"
REFUSED_MIDI = """
(() => { navigator.requestMIDIAccess = async () => { throw new DOMException("denied", "SecurityError"); }; })();
"""


def _fake(devices):
    return FAKE_MIDI.replace("__DEVICES__", json.dumps(devices))


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
def open_setup(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p31browser", password=PASSWORD)
    user.groups.add(group)

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value
    contexts = []
    errors = []

    def opener(init_script):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        contexts.append(context)
        context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
        context.add_init_script(init_script)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{live_server.url}/improv/setup/", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelectorAll('#note-names option').length > 0", timeout=15000)
        return page

    yield opener, errors, user
    for context in contexts:
        context.close()


def _profile(user):
    return Player.objects.get(user=user)


# ------------------------------------------------------------------- the keyboard


def test_the_page_lists_the_keyboards_and_listens_to_one_without_being_asked(open_setup):
    opener, errors, _ = open_setup
    page = opener(_fake([["a1", "Clavinova"], ["b2", "Minilab"]]))
    page.wait_for_selector("#midi-row:not([hidden])", timeout=10000)
    assert page.locator("#midi-input option").all_inner_texts() == ["Clavinova", "Minilab"]
    assert page.locator("#midi-state").inner_text() == "Listening to Clavinova."
    assert page.evaluate("window.__midi.options") == {"sysex": False}
    assert not errors, errors


def test_what_is_played_on_the_chosen_keyboard_shows_up(open_setup):
    opener, errors, _ = open_setup
    page = opener(_fake([["a1", "Clavinova"], ["b2", "Minilab"]]))
    page.wait_for_selector("#midi-row:not([hidden])", timeout=10000)
    assert page.locator("#heard").inner_text() == "Nothing yet."

    # What the notes are *called* is SPR-I.3.2's business; what matters here is that the
    # notes of the chosen keyboard arrive and the other keyboard's do not.
    page.evaluate("window.__midi.press('a1', 60, 90)")
    page.evaluate("window.__midi.press('a1', 64, 90)")
    page.wait_for_function("document.getElementById('heard').textContent.startsWith('C4 E4')")

    page.evaluate("window.__midi.press('a1', 60, 0)")
    page.wait_for_function("document.getElementById('heard').textContent === 'E4'")

    page.evaluate("window.__midi.press('b2', 72, 90)")
    assert page.locator("#heard").inner_text() == "E4", "only the chosen keyboard is listened to"

    page.select_option("#midi-input", "b2")
    assert page.locator("#midi-state").inner_text() == "Listening to Minilab."
    assert page.locator("#heard").inner_text() == "Nothing yet."
    page.evaluate("window.__midi.press('b2', 72, 90)")
    page.wait_for_function("document.getElementById('heard').textContent === 'C5'")
    assert not errors, errors


def test_pulling_the_keyboard_out_and_plugging_it_back_in_is_handled_without_a_reload(open_setup):
    opener, errors, _ = open_setup
    page = opener(_fake([["a1", "Clavinova"]]))
    page.wait_for_selector("#midi-row:not([hidden])", timeout=10000)

    page.evaluate("window.__midi.unplug('a1')")
    page.wait_for_function(
        "document.getElementById('midi-state').textContent.includes('No keyboard is connected')", timeout=5000
    )
    assert "Clavinova was unplugged" in page.locator("#midi-state").inner_text()
    assert page.locator("#midi-row").is_hidden()
    assert page.locator("#heard").inner_text() == "Nothing yet."

    # The same piano, back on a different port id, which is why the name is what is remembered.
    page.evaluate("window.__midi.plug('a9', 'Clavinova')")
    page.wait_for_function(
        "document.getElementById('midi-state').textContent.startsWith('Listening to Clavinova')", timeout=5000
    )
    assert "is connected" in page.locator("#midi-state").inner_text()
    page.evaluate("window.__midi.press('a9', 67, 90)")
    page.wait_for_function("document.getElementById('heard').textContent === 'G4'")
    assert not errors, errors


def test_losing_the_keyboard_being_played_says_so_while_another_one_takes_over(open_setup):
    opener, errors, _ = open_setup
    page = opener(_fake([["a1", "Clavinova"], ["b2", "Minilab"]]))
    page.wait_for_selector("#midi-row:not([hidden])", timeout=10000)
    page.evaluate("window.__midi.unplug('a1')")
    page.wait_for_function(
        "document.getElementById('midi-state').textContent.startsWith('Listening to Minilab')", timeout=5000
    )
    state = page.locator("#midi-state").inner_text()
    assert "Clavinova was unplugged" in state
    assert "Plug it back in" in state
    assert page.locator("#midi-input option").all_inner_texts() == ["Minilab", "Clavinova (unplugged)"]
    assert not errors, errors


def test_the_keyboard_used_last_time_is_chosen_again_by_its_name(open_setup):
    opener, errors, user = open_setup
    page = opener(_fake([["a1", "Clavinova"]]))
    page.wait_for_selector("#midi-row:not([hidden])", timeout=10000)
    page.click("#save")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=10000)
    assert _profile(user).midi_input_name == "Clavinova"

    # Next session: a different port id, and another keyboard that would otherwise be first.
    again = opener(_fake([["zz", "Alpha Keys"], ["new-id-7", "Clavinova"]]))
    again.wait_for_selector("#midi-row:not([hidden])", timeout=10000)
    assert again.locator("#midi-state").inner_text() == "Listening to Clavinova."
    assert again.locator("#midi-input").input_value() == "new-id-7"
    assert again.locator("#save").is_disabled(), "nothing changed, so there is nothing to save"
    assert not errors, errors


# ----------------------------------------------------------------- the preferences


def test_the_profile_is_shown_with_its_defaults_and_saves_what_is_changed(open_setup):
    opener, errors, user = open_setup
    page = opener(_fake([["a1", "Clavinova"]]))
    assert page.locator("#note-names").input_value() == "sharps"
    assert page.locator("#demo-output").input_value() == "piano"
    assert page.locator("#daily-goal").input_value() == "15"
    assert page.locator("#timezone").input_value() == "Asia/Jerusalem"
    assert page.locator("#latency").inner_text() == "Not calibrated yet."

    page.select_option("#note-names", "flats")
    page.select_option("#demo-output", "laptop")
    page.fill("#daily-goal", "40")
    page.fill("#timezone", "Europe/Berlin")
    assert page.locator("#save").is_enabled()
    page.click("#save")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=10000)

    profile = _profile(user)
    assert profile.note_names == "flats"
    assert profile.demo_output == "laptop"
    assert profile.daily_goal_minutes == 40
    assert profile.timezone == "Europe/Berlin"
    assert profile.midi_input_name == "Clavinova"
    assert page.locator("#save").is_disabled(), "nothing has changed since it was saved"
    assert not errors, errors


def test_a_goal_nobody_could_practise_is_refused_before_the_server_sees_it(open_setup):
    opener, errors, user = open_setup
    page = opener(_fake([["a1", "Clavinova"]]))
    page.fill("#daily-goal", "999")
    assert page.locator("#setup-problems").is_visible()
    assert "between 5 and 240" in page.locator("#setup-problems").inner_text()
    assert page.locator("#save").is_disabled()

    page.fill("#timezone", "")
    assert "timezone" in page.locator("#setup-problems").inner_text()

    page.fill("#daily-goal", "30")
    page.fill("#timezone", "Asia/Jerusalem")
    assert page.locator("#setup-problems").is_hidden()
    assert page.locator("#save").is_enabled()
    page.click("#save")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=10000)
    assert _profile(user).daily_goal_minutes == 30
    assert not errors, errors


def test_a_calibrated_player_is_told_what_their_offset_is(open_setup):
    opener, errors, user = open_setup
    Player.objects.create(user=user, latency_offset_ms=-48)
    page = opener(_fake([["a1", "Clavinova"]]))
    assert page.locator("#latency").inner_text() == "Calibrated: your notes are shifted by -48 ms before they are judged."
    assert not errors, errors


# ------------------------------------------------------------ when MIDI is missing


def test_a_browser_without_web_midi_says_so_and_the_rest_of_the_page_still_works(open_setup):
    opener, errors, user = open_setup
    page = opener(NO_MIDI)
    page.wait_for_function(
        "document.getElementById('midi-state').textContent.includes('no Web MIDI')", timeout=10000
    )
    assert page.locator("#midi-row").is_hidden()
    assert "Chrome or Edge" in page.locator("#midi-state").inner_text()

    page.fill("#daily-goal", "25")
    page.click("#save")
    page.wait_for_function("document.getElementById('setup-status').textContent === 'Saved.'", timeout=10000)
    assert _profile(user).daily_goal_minutes == 25
    assert not errors, errors


def test_midi_refused_is_explained_and_can_be_asked_for_again(open_setup):
    opener, errors, _ = open_setup
    page = opener(REFUSED_MIDI)
    page.wait_for_selector("#midi-allow:not([hidden])", timeout=10000)
    assert "refused" in page.locator("#midi-state").inner_text()
    assert "address bar" in page.locator("#midi-help").inner_text()
    page.click("#midi-allow")
    assert page.locator("#midi-allow").is_visible(), "still refused, so the offer stays"
    assert not errors, errors


def test_midi_allowed_but_nothing_plugged_in_asks_for_the_cable(open_setup):
    opener, errors, _ = open_setup
    page = opener(_fake([]))
    page.wait_for_function(
        "document.getElementById('midi-state').textContent.includes('No keyboard is connected')", timeout=10000
    )
    assert page.locator("#midi-row").is_hidden()
    assert "USB" in page.locator("#midi-state").inner_text()
    assert not errors, errors
