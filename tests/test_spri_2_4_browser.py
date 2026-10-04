"""SPR-I.2.4 improv: the Play screen in a real browser.

The logic is proved under Node and the template against the script by the sibling
file. What neither can see is the page doing its job: the library loads over the API,
the chart is drawn, a key change redraws it, Play makes real Web Audio nodes and lights
the bars, Stop puts everything back. Sound quality is not judged here (nobody is
listening); that the band is *scheduling sound* is.

Traces: spec ch. 8 (nothing on Play needs a click during playing), backlog SPR-I.2.4.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

# Playwright's sync API keeps an event loop alive in this thread, and Django refuses
# ordinary database calls while one is running (same flag as tests/test_exo_*browser*).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri24, pytest.mark.django_db]

PASSWORD = "spri24-browser-7712"

COUNT_NODES = """
(() => {
  window.__made = { osc: 0, source: 0 };
  const C = window.AudioContext || window.webkitAudioContext;
  const osc = C.prototype.createOscillator;
  C.prototype.createOscillator = function () { window.__made.osc += 1; return osc.apply(this, arguments); };
  const src = C.prototype.createBufferSource;
  C.prototype.createBufferSource = function () { window.__made.source += 1; return src.apply(this, arguments); };
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
def player_page(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p24browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    context.add_init_script(COUNT_NODES)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{live_server.url}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    yield page, errors
    context.close()


def _bar_text(page, n):
    return page.locator(f'.im-bar[data-bar="{n}"] .im-bar-chords').inner_text().split()


def test_the_page_loads_the_library_and_draws_the_chart(player_page):
    page, errors = player_page
    page.select_option("#progression", "ii-v-i-major")
    page.wait_for_selector(".im-bar")
    assert page.locator("#play-status").inner_text().startswith("Ready")
    assert page.locator("#play-toggle").is_enabled()
    assert page.locator(".im-bar").count() == 4
    assert _bar_text(page, 0) == ["Dm7"]
    assert page.locator("#style").input_value() != ""
    assert page.locator("#bpm").input_value().isdigit()
    assert not errors, errors


def test_choosing_a_key_redraws_the_chart_in_that_key(player_page):
    page, errors = player_page
    page.select_option("#progression", "ii-v-i-major")
    assert _bar_text(page, 0) == ["Dm7"]
    page.select_option("#key", "Eb")
    assert _bar_text(page, 0) == ["Fm7"]
    assert "Eb" in page.locator("#chart-title").inner_text()
    assert not errors, errors


def test_a_loop_that_makes_no_sense_is_explained_and_cannot_be_played(player_page):
    page, errors = player_page
    page.select_option("#progression", "twelve-bar-blues")
    page.fill("#first", "9")
    page.fill("#last", "2")
    page.dispatch_event("#last", "change")
    assert page.locator("#play-error").is_visible()
    assert "before" in page.locator("#play-error").inner_text()
    assert page.locator("#play-toggle").is_disabled()
    page.fill("#first", "5")
    page.fill("#last", "8")
    page.dispatch_event("#last", "change")
    assert not page.locator("#play-error").is_visible()
    assert page.locator("#play-toggle").is_enabled()
    assert page.locator(".im-bar-out").count() == 8, "the bars outside the loop are dimmed"
    assert not errors, errors


def test_play_counts_in_lights_the_bars_makes_sound_and_stop_puts_it_back(player_page):
    page, errors = player_page
    page.select_option("#progression", "ii-v-i-major")
    page.fill("#bpm", "200")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "1")

    page.click("#play-toggle")
    page.wait_for_selector("#count-in:not([hidden])", timeout=5000)
    assert "Count-in" in page.locator("#count-in").inner_text()
    assert page.locator("#play-toggle").inner_text() == "Stop"
    assert page.locator("#progression").is_disabled(), "the shape of the take is locked while it plays"
    assert page.locator("#bpm").is_enabled(), "the tempo can move while it plays (SPR-I.2.6)"
    assert page.locator("#mix input[type=range]").first.is_enabled(), "the mix stays live"

    page.wait_for_selector(".im-bar-lit", timeout=8000)
    lit = int(page.locator(".im-bar-lit").first.get_attribute("data-bar"))
    assert 0 <= lit <= 3
    page.wait_for_function("document.querySelectorAll('.im-bar-lit').length === 1")

    made = page.evaluate("window.__made")
    assert made["osc"] > 5 and made["source"] > 5, f"the band is not making sound: {made}"

    page.locator("#mix input[type=checkbox]").nth(2).check()
    page.locator("#mix input[type=range]").nth(1).fill("40")

    page.click("#play-toggle")
    assert page.locator("#play-toggle").inner_text() == "Play"
    assert page.locator("#bpm").is_enabled()
    page.wait_for_function("document.querySelectorAll('.im-bar-lit').length === 0")
    assert page.locator("#count-in").is_hidden()
    assert not errors, errors


def test_the_loop_goes_round_and_never_repeats_the_count_in(player_page):
    page, errors = player_page
    page.select_option("#progression", "ii-v-i-major")
    page.fill("#bpm", "300")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "1")
    page.click("#play-toggle")
    page.wait_for_selector("#count-in:not([hidden])", timeout=5000)
    seen = page.evaluate(
        """() => new Promise((resolve) => {
            const order = [];
            const start = performance.now();
            const tick = () => {
              const lit = document.querySelector('.im-bar-lit');
              const counting = !document.getElementById('count-in').hidden;
              const label = counting ? 'c' : lit ? lit.dataset.bar : null;
              if (label !== null && order[order.length - 1] !== label) order.push(label);
              if (performance.now() - start > 6500) resolve(order); else requestAnimationFrame(tick);
            };
            tick();
        })"""
    )
    page.click("#play-toggle")
    assert seen[0] == "c"
    assert seen.count("c") == 1, f"the count-in came back: {seen}"
    assert seen[1:5] == ["0", "1", "2", "3"], seen
    assert seen.count("0") >= 2, f"it did not loop: {seen}"
    assert not errors, errors
