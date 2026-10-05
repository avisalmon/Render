"""SPR-I.4.4 improv: the Takes screen in a real browser.

The rules are proved under Node. What those cannot see is the page listing a player's takes
in words, keeping and deleting one, and replaying one: the band starts from the take's own
snapshot, the chart lights bar by bar, and the notes go out either as a plain tone through
the synth or to the piano over MIDI with timestamps, according to the profile. The MIDI
output is faked and records what is sent; the band is the app's own.

Traces: spec ch. 6 and 8, feature 15, backlog SPR-I.4.4.
"""

import io
import os
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Player, PracticeSession, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri44, pytest.mark.django_db]

PASSWORD = "spri44-browser-6618"

FAKE_WORLD = """
(() => {
  const access = { inputs: new Map(), outputs: new Map(), onstatechange: null };
  window.__sent = [];
  access.outputs.set("out1", { id: "out1", name: "Clavinova", state: "connected", type: "output",
    send(bytes, at) { window.__sent.push([Array.from(bytes), at === undefined ? null : at]); } });
  navigator.requestMIDIAccess = async () => access;
  const C = window.AudioContext || window.webkitAudioContext;
  C.prototype.getOutputTimestamp = function () {
    return { contextTime: this.currentTime, performanceTime: performance.now() };
  };
  window.__made = { osc: 0 };
  const osc = C.prototype.createOscillator;
  C.prototype.createOscillator = function () { window.__made.osc += 1; return osc.apply(this, arguments); };
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


def _take(user, **changes):
    player, _ = Player.objects.get_or_create(user=user)
    session = PracticeSession.objects.filter(player=player).first() or PracticeSession.objects.create(player=player)
    preset = Progression.objects.get(slug="ii-v-i-major")
    fields = dict(
        player=player, session=session, progression=preset, style=preset.default_style,
        chart=preset.chart, home_key=preset.home_key, key="C", time_signature="4/4", tempo=200,
        swing_ratio="0.67", loop_from=0, loop_to=4, started_at=timezone.now(), duration_ms=2400, bars=4,
        events=[
            {"t_ms": 0, "type": "on", "note": 62, "velocity": 90},
            {"t_ms": 250, "type": "off", "note": 62, "velocity": 0},
            {"t_ms": 300, "type": "on", "note": 65, "velocity": 100},
            {"t_ms": 550, "type": "off", "note": 65, "velocity": 0},
        ],
        score=None, metrics={"notes": 2, "chordTonePct": 100, "outsidePct": 0, "meanOffsetMs": -12}, judge_version=1,
    )
    fields.update(changes)
    return Take.objects.create(**fields)


@pytest.fixture
def takes_page(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p44browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value
    contexts = []
    errors = []

    def opener():
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        contexts.append(context)
        context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
        context.add_init_script(FAKE_WORLD)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{live_server.url}/improv/takes/", wait_until="domcontentloaded")
        page.wait_for_function("!document.getElementById('takes-status').textContent.startsWith('Loading')", timeout=15000)
        return page

    yield opener, errors, user
    for context in contexts:
        context.close()


def test_the_takes_are_listed_in_words_newest_first(takes_page):
    opener, errors, user = takes_page
    old = _take(user, started_at=timezone.now() - timedelta(days=3), key="F")
    new = _take(user, is_kept=True)
    page = opener()
    rows = page.locator(".im-take")
    assert rows.count() == 2
    assert rows.nth(0).get_attribute("data-id") == str(new.pk)
    assert rows.nth(1).get_attribute("data-id") == str(old.pk)
    first = rows.nth(0).inner_text()
    assert "ii-V-I" in first and "C, 200 bpm, swing, 4 bars" in first
    assert "2 notes: 100% chord tones, rushing by 12 ms" in first
    assert "Today" in first
    assert rows.nth(0).locator('[data-action="keep"]').inner_text() == "Kept"
    assert rows.nth(1).locator('[data-action="keep"]').inner_text() == "Keep"
    assert "2 takes" in page.locator("#takes-count").inner_text()
    assert not errors, errors


def test_kept_only_narrows_the_list_and_keeping_is_one_click(takes_page):
    opener, errors, user = takes_page
    a = _take(user)
    _take(user, is_kept=True)
    page = opener()
    page.check("#f-kept")
    assert page.locator(".im-take").count() == 1
    page.uncheck("#f-kept")
    page.locator(f'.im-take[data-id="{a.pk}"] [data-action="keep"]').click()
    page.wait_for_function(f"document.querySelector('.im-take[data-id=\"{a.pk}\"] [data-action=\"keep\"]').textContent === 'Kept'")
    a.refresh_from_db()
    assert a.is_kept is True
    assert not errors, errors


def test_deleting_takes_two_clicks(takes_page):
    opener, errors, user = takes_page
    take = _take(user)
    page = opener()
    button = page.locator(f'.im-take[data-id="{take.pk}"] [data-action="delete"]')
    button.click()
    assert Take.objects.filter(pk=take.pk).exists(), "one click only asks"
    assert "again" in button.inner_text()
    button.click()
    page.wait_for_function("document.querySelectorAll('.im-take').length === 0")
    assert not Take.objects.filter(pk=take.pk).exists()
    assert page.locator("#takes-empty").is_visible()
    assert not errors, errors


def test_a_replay_plays_the_band_from_the_snapshot_and_the_notes_as_a_plain_tone(takes_page):
    opener, errors, user = takes_page
    take = _take(user)
    Player.objects.filter(user=user).update(demo_output="laptop")
    page = opener()
    page.locator(f'.im-take[data-id="{take.pk}"]').get_by_text("Replay", exact=True).click()
    page.wait_for_selector("#replay-panel:not([hidden])", timeout=5000)
    assert "ii-V-I" in page.locator("#replay-title").inner_text()
    assert "plain tone" in page.locator("#replay-output").inner_text()
    assert page.locator("#replay-chart .im-bar").count() == 4
    page.wait_for_selector("#replay-chart .im-bar-lit", timeout=8000)
    assert page.evaluate("window.__made.osc") > 2, "the band and the two demo notes are real oscillators"
    assert page.evaluate("window.__sent.length") == 0, "nothing went to MIDI"
    page.click("#replay-stop")
    assert page.locator("#replay-status").inner_text() == "Stopped."
    assert page.locator("#replay-chart .im-bar-lit").count() == 0
    assert not errors, errors


def test_a_replay_sends_the_notes_to_the_piano_over_midi_with_timestamps_when_asked(takes_page):
    opener, errors, user = takes_page
    take = _take(user)
    Player.objects.filter(user=user).update(demo_output="piano", midi_input_name="Clavinova")
    page = opener()
    page.locator(f'.im-take[data-id="{take.pk}"]').get_by_text("Replay", exact=True).click()
    page.wait_for_selector("#replay-panel:not([hidden])", timeout=5000)
    assert "Clavinova" in page.locator("#replay-output").inner_text()
    page.wait_for_function("window.__sent.length >= 4", timeout=8000)
    sent = page.evaluate("window.__sent")
    ons = [s for s in sent if s[0][0] == 0x90]
    offs = [s for s in sent if s[0][0] == 0x80]
    assert [s[0][1] for s in ons] == [62, 65]
    assert all(s[1] is not None and s[1] > 0 for s in ons), "every note is sent with a timestamp, not played now"
    assert ons[1][1] - ons[0][1] == pytest.approx(300, abs=40), "the two notes keep their 300 ms apart"
    assert len(offs) >= 2
    page.click("#replay-stop")
    assert not errors, errors


def test_a_take_whose_progression_was_deleted_still_replays(takes_page):
    opener, errors, user = takes_page
    take = _take(user)
    Progression.objects.filter(pk=take.progression_id).delete()
    take.refresh_from_db()
    assert take.progression_id is None and take.chart
    page = opener()
    assert "Free chart" in page.locator(".im-take").first.inner_text()
    page.locator(".im-take").first.get_by_text("Replay", exact=True).click()
    page.wait_for_selector("#replay-panel:not([hidden])", timeout=5000)
    assert page.locator("#replay-chart .im-bar").count() == 4
    assert page.locator("#replay-error").is_hidden()
    page.click("#replay-stop")
    assert not errors, errors
