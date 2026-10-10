"""SPR-I.11.1 improv: the chord guide on the Play screen.

Avi, 2026-10-10: a player who does not know what is in "Cmaj7" should see the keys without the flow being
disturbed: the scale in one colour, the chord in root position dark, its inversions in lighter shades.

The pure logic (tones, scale, positions, keyboard roles) runs under Node in tests/js/spri111.test.js; this file
runs it, checks the docs, and drives the real Play screen: the guide follows the chord the band is on, a bar
pointed at is looked ahead at, and leaving it goes back.

Traces: spec ch. 8 "The chord guide", backlog SPR-I.11.1.
"""

import io
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri111]

PASSWORD = "spri111-browser-4417"


def test_the_guide_logic_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri111.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


def test_the_play_page_has_the_guide_panel_and_loads_its_scripts():
    html = Path("templates/improv/play.html").read_text(encoding="utf-8")
    assert 'aria-label="Chord guide"' in html
    for needle in ("guide-chord", "guide-scale", "guide-legend", "guide-keys", "chord-guide.js", "chord-guide-view.js"):
        assert needle in html, needle
    for swatch in ("im-swatch-gscale", "im-swatch-gp1", "im-swatch-gp2", "im-swatch-gp3"):
        assert swatch in html, swatch


def test_the_guide_shades_are_defined_in_the_stylesheet():
    css = Path("static/improv/improv.css").read_text(encoding="utf-8")
    for cls in (".im-g-scale", ".im-g-p1", ".im-g-p2", ".im-g-p3"):
        assert cls in css, cls


def test_the_docs_describe_the_guide_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "The chord guide" in spec and "Looking ahead" in spec
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.11\.1 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)


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
def play(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p111browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 720})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "MIDI" not in m.text else None)
    page.goto(f"{live_server.url}/improv/play/", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('#progression option').length > 5", timeout=15000)
    page.select_option("#progression", "ii-v-i-major")
    page.wait_for_selector("#chart .im-bar", timeout=8000)
    yield page, errors
    context.close()


def _classes(page):
    return page.evaluate(
        """() => {
          const out = {};
          for (const role of ["scale", "p1", "p2", "p3"]) out[role] = document.querySelectorAll("#guide-keys .im-g-" + role).length;
          return out;
        }"""
    )


def test_stopped_the_guide_shows_the_first_chord_with_all_three_positions(play):
    page, errors = play
    text = page.inner_text("#guide-chord")
    assert text.startswith("First chord:"), text
    assert "Dm7" in text
    counts = _classes(page)
    assert counts["p1"] == 4 and counts["p2"] == 4 and counts["p3"] == 4, counts
    assert counts["scale"] > 10
    assert "Scale:" in page.inner_text("#guide-scale")
    assert errors == []


def test_pointing_at_a_bar_looks_ahead_and_leaving_goes_back(play):
    page, errors = play
    bar = page.locator('#chart .im-bar[data-bar="1"]')
    box = bar.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] / 2)
    page.wait_for_function("document.getElementById('guide-chord').textContent.startsWith('Looking ahead')", timeout=3000)
    assert page.get_attribute('#chart .im-bar[data-bar="1"]', "data-previewing") == "yes"
    page.mouse.move(box["x"] + box["width"] * 0.8, box["y"] + box["height"] / 2)
    assert page.inner_text("#guide-chord").startswith("Looking ahead")
    page.mouse.move(2, 2)
    page.wait_for_function("document.getElementById('guide-chord').textContent.startsWith('First chord')", timeout=3000)
    assert page.get_attribute('#chart .im-bar[data-bar="1"]', "data-previewing") is None
    assert errors == []


def test_tabbing_to_a_bar_looks_ahead_too(play):
    page, errors = play
    page.focus('#chart .im-bar[data-bar="2"]')
    page.wait_for_function("document.getElementById('guide-chord').textContent.startsWith('Looking ahead')", timeout=3000)
    assert errors == []


def test_while_the_band_plays_the_guide_follows_it(play):
    page, errors = play
    page.fill("#bpm", "120")
    page.dispatch_event("#bpm", "change")
    page.select_option("#countin", "0")
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('guide-chord').textContent.startsWith('Now playing')", timeout=8000)
    page.click("#play-toggle")
    page.wait_for_function("document.getElementById('guide-chord').textContent.startsWith('First chord')", timeout=8000)
    assert errors == []
