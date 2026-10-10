"""SPR-I.14.2 improv: where the notes come from, in a real browser.

MIDI stays the default and works as before; the picker is on every practice screen; touch keys play and let go, slide
and hold two notes, and move up and down the piano; the choice is remembered on the device; and a generated recording
of a piano note, fed to the page as the microphone, comes out as the same note on the same keyboard.

Traces: spec ch. 13, backlog SPR-I.14.1 and SPR-I.14.2.
"""

import io
import math
import os
import struct
import wave

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri141, pytest.mark.django_db]

PASSWORD = "spri141-browser-7712"

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
  window.__release = (note) => {
    const event = { data: Uint8Array.from([0x80, note, 0]), timeStamp: performance.now() };
    if (input.onmidimessage) input.onmidimessage(event);
    input.listeners.forEach((fn) => fn(event));
  };
})();
"""

SCREENS = [
    ("/improv/play/", "#midi-state"),
    ("/improv/reading/", "#rd-midi"),
    ("/improv/repertoire/", "#rp-midi"),
    ("/improv/scales/", "#sc-midi"),
    ("/improv/chords/", "#ch-midi"),
]


def _piano_wav(path, midi=60, silence=0.5, held=1.4, tail=0.6, rate=44100):
    """A piano-like note (overtones falling away) between two silences."""
    hz = 440.0 * 2 ** ((midi - 69) / 12)
    total = silence + held + tail
    frames = bytearray()
    for i in range(int(total * rate)):
        t = i / rate
        value = 0.0
        if silence <= t < silence + held:
            u = t - silence
            attack = min(1.0, u / 0.004)
            for h in range(1, 9):
                f = hz * h * math.sqrt(1 + 0.0001 * h * h)
                value += 0.22 / h**1.1 * math.exp(-u / (2.5 / (1 + 0.5 * h))) * math.sin(2 * math.pi * f * u + h) * attack
        frames += struct.pack("<h", int(max(-1, min(1, value)) * 32000))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(frames))


@pytest.fixture(scope="module")
def wav_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("mic") / "c4.wav"
    _piano_wav(path)
    return path


@pytest.fixture(scope="module")
def browser(django_db_setup, wav_path):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch(
                args=[
                    "--autoplay-policy=no-user-gesture-required",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    f"--use-file-for-fake-audio-capture={wav_path}",
                ]
            )
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def make_page(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p141browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_pieces", "seed_improv_fingerings", "seed_improv_library", "seed_improv_lessons"):
        call_command(command, stdout=io.StringIO())
    Player.objects.get_or_create(user=user)
    client = Client()
    client.force_login(user)
    contexts = []

    def make(width=1280, height=720, mode=None, mic=False):
        context = browser.new_context(viewport={"width": width, "height": height}, permissions=["microphone"] if mic else [])
        context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
        context.add_init_script(FAKE_PIANO)
        if mode:
            context.add_init_script(f"try {{ if (!sessionStorage.getItem('__seeded')) {{ localStorage.setItem('improv.input.mode', '{mode}'); sessionStorage.setItem('__seeded', '1'); }} }} catch (e) {{}}")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        contexts.append(context)
        return page, errors

    yield make, live_server.url
    for context in contexts:
        context.close()


def _open_reading(page, base):
    page.goto(f"{base}/improv/reading/", wait_until="domcontentloaded")
    page.wait_for_selector("#rd-start:not([disabled])", timeout=15000)
    page.wait_for_function("document.documentElement.dataset.input !== undefined", timeout=5000)


def _lit(page, note):
    return page.evaluate(f"(() => {{ const k = document.querySelector('#rd-keyboard .im-key[data-note=\"{note}\"]'); return !!k && k.classList.contains('im-key-on'); }})()")


def _centre(page, note):
    """The point on a white dock key, low on it, clear of the black keys."""
    return page.evaluate(
        f"""(() => {{ const r = document.querySelector('#im-dock-keys .im-key[data-note="{note}"]').getBoundingClientRect();
        return {{ x: r.left + r.width / 2, y: r.top + r.height * 0.85 }}; }})()"""
    )


def test_midi_is_the_default_on_every_screen_and_the_piano_still_plays(make_page):
    make, base = make_page
    page, errors = make()
    for path, status in SCREENS:
        page.goto(f"{base}{path}", wait_until="domcontentloaded")
        try:
            page.wait_for_function("document.documentElement.dataset.input !== undefined", timeout=15000)
        except Exception:
            pytest.fail(f"{path} never started its input: {errors}")
        assert page.input_value("#im-input-mode") == "midi", path
        assert page.evaluate("document.documentElement.dataset.input") == "midi"
        assert page.is_hidden("#im-dock") if page.query_selector("#im-dock") else True
        page.wait_for_function(f"document.querySelector('{status}').textContent.includes('Fake piano')", timeout=5000)
    _open_reading(page, base)
    page.wait_for_function("document.documentElement.dataset.keys === 'on'", timeout=5000)
    page.evaluate("window.__press(60)")
    assert _lit(page, 60)
    page.evaluate("window.__release(60)")
    assert not _lit(page, 60)
    assert errors == []


def test_touch_keys_play_and_let_go_and_hold_two_notes(make_page):
    make, base = make_page
    page, errors = make(width=500, height=800)
    _open_reading(page, base)
    page.select_option("#im-input-mode", "touch")
    page.wait_for_selector("#im-dock:not([hidden])")
    assert page.inner_text("#reading-status, #rd-midi").strip() != ""
    assert page.evaluate("document.querySelectorAll('#im-dock-keys .im-key').length") == 25  # two octaves, C to C

    spot = _centre(page, 60)
    page.mouse.move(spot["x"], spot["y"])
    page.mouse.down()
    assert _lit(page, 60)
    assert page.evaluate("document.querySelector('#im-dock-keys .im-key[data-note=\"60\"]').classList.contains('im-key-on')")
    page.mouse.up()
    assert not _lit(page, 60)

    for pointer, note in ((7, 60), (8, 64)):
        spot = _centre(page, note)
        page.evaluate(
            """([id, x, y]) => document.getElementById('im-dock-keys').dispatchEvent(
                new PointerEvent('pointerdown', { pointerId: id, clientX: x, clientY: y, bubbles: true }))""",
            [pointer, spot["x"], spot["y"]],
        )
    assert _lit(page, 60) and _lit(page, 64)
    page.evaluate(
        "() => document.getElementById('im-dock-keys').dispatchEvent(new PointerEvent('pointerup', { pointerId: 7, bubbles: true }))"
    )
    assert not _lit(page, 60) and _lit(page, 64)
    page.evaluate(
        "() => document.getElementById('im-dock-keys').dispatchEvent(new PointerEvent('pointercancel', { pointerId: 8, bubbles: true }))"
    )
    assert not _lit(page, 64)
    assert errors == []


def test_sliding_a_finger_moves_from_key_to_key(make_page):
    make, base = make_page
    page, errors = make(width=500, height=800)
    _open_reading(page, base)
    page.select_option("#im-input-mode", "touch")
    page.wait_for_selector("#im-dock:not([hidden])")
    a, b = _centre(page, 60), _centre(page, 62)
    page.mouse.move(a["x"], a["y"])
    page.mouse.down()
    assert _lit(page, 60)
    page.mouse.move(b["x"], b["y"], steps=4)
    assert _lit(page, 62) and not _lit(page, 60)
    page.mouse.up()
    assert not _lit(page, 62)
    assert errors == []


def test_lower_and_higher_move_the_keyboard_and_never_reach_the_control_keys(make_page):
    make, base = make_page
    page, errors = make(width=500, height=800)
    _open_reading(page, base)
    page.select_option("#im-input-mode", "touch")
    page.wait_for_selector("#im-dock:not([hidden])")
    first = lambda: int(page.evaluate("document.querySelector('#im-dock-keys .im-key').dataset.note"))
    last = lambda: int(page.evaluate("[...document.querySelectorAll('#im-dock-keys .im-key')].pop().dataset.note"))
    assert (first(), last()) == (48, 72)
    page.click("#im-dock-higher")
    assert (first(), last()) == (60, 84)
    for _ in range(10):
        if page.is_enabled("#im-dock-higher"):
            page.click("#im-dock-higher")
    assert last() <= 105
    assert page.is_disabled("#im-dock-higher")
    for _ in range(10):
        if page.is_enabled("#im-dock-lower"):
            page.click("#im-dock-lower")
    assert first() == 24
    assert page.is_disabled("#im-dock-lower")
    assert errors == []


def test_the_choice_is_remembered_and_switching_back_gives_the_piano_again(make_page):
    make, base = make_page
    page, errors = make(width=500, height=800)
    _open_reading(page, base)
    page.select_option("#im-input-mode", "touch")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#rd-start:not([disabled])", timeout=15000)
    page.wait_for_selector("#im-dock:not([hidden])")
    assert page.input_value("#im-input-mode") == "touch"
    page.select_option("#im-input-mode", "midi")
    page.wait_for_selector("#im-dock", state="hidden")
    page.wait_for_function("document.querySelector('#rd-midi').textContent.includes('Fake piano')", timeout=5000)
    page.evaluate("window.__press(62)")
    assert _lit(page, 62)
    assert errors == []


def test_a_recorded_piano_note_through_the_microphone_lights_the_same_key(make_page):
    make, base = make_page
    page, errors = make(mode="mic", mic=True)
    _open_reading(page, base)
    assert page.input_value("#im-input-mode") == "mic"
    page.wait_for_function(
        "document.querySelector('#rd-keyboard .im-key[data-note=\"60\"]').classList.contains('im-key-on')", timeout=20000
    )
    page.wait_for_function("document.querySelector('#rd-midi').textContent.includes('C4')", timeout=5000)
    page.wait_for_function(
        "!document.querySelector('#rd-keyboard .im-key[data-note=\"60\"]').classList.contains('im-key-on')", timeout=20000
    )
    others = page.evaluate("[...document.querySelectorAll('#rd-keyboard .im-key-on')].map((k) => k.dataset.note)")
    assert others == []
    page.select_option("#im-input-mode", "midi")
    page.wait_for_function("document.querySelector('#rd-midi').textContent.includes('Fake piano')", timeout=5000)
    assert errors == []


def test_a_refused_microphone_says_so(make_page):
    make, base = make_page
    page, errors = make(mode="mic", mic=False)
    page.add_init_script(
        "navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('no', 'NotAllowedError'));"
    )
    _open_reading(page, base)
    page.wait_for_function("document.querySelector('#rd-midi').textContent.includes('refused')", timeout=5000)
    assert errors == []
