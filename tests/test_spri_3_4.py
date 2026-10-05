"""SPR-I.3.4 improv: calibration, the one number that makes timing mean anything.

The rules are a pure function tested under Node in tests/js/spri34.test.js, on top of the
spike's timing.js. This file runs that suite and checks the screen: the Setup page has the
calibration, it stores the offset through the profile endpoint, and the stored number is
within what the model will hold.

**This sprint is only truly accepted at the piano.** The numbers a real Clavinova and a real
laptop output produce are the point of it, and no test here can stand in for Avi tapping
sixteen times. What is tested is everything around that: the maths, the screen, the storing.

Traces: spec ch. 4 and 9, feature 14, backlog SPR-I.3.4.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import Client

from improv.models import Player

pytestmark = pytest.mark.spri34

LOGIC_JS = Path("static/improv/calibrate.js")
TIMING_JS = Path("static/improv/timing.js")
PAGE_JS = Path("static/improv/setup-page.js")
TEMPLATE = Path("templates/improv/setup.html")
API = "/improv/api/player/"
PASSWORD = "spri34-pass-2290"


@pytest.fixture
def player(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p34member", password=PASSWORD)
    user.groups.add(group)
    client = Client()
    client.force_login(user)
    return client, user


def test_the_calibration_rules_pass_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri34.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_the_calibration_uses_the_spikes_own_timing_maths_rather_than_its_own():
    """The spike measured a real piano with timing.js. Calibration must not re-do that
    arithmetic differently, or the two would drift apart."""
    text = LOGIC_JS.read_text(encoding="utf-8")
    assert 'require("./timing.js")' in text
    assert "Timing.nearestClick(" in text and "Timing.stats(" in text
    body = re.sub(r"//[^\n]*", "", text)
    assert "Math.sqrt" not in body, "the spread is timing.js's job"
    assert "performanceTime" not in body, "mapping the clocks is timing.js's job"


def test_the_offset_the_calibration_can_produce_always_fits_the_profile(player):
    client, user = player
    client.get(API)
    limit = int(re.search(r"OFFSET_LIMIT_MS = (\d+)", LOGIC_JS.read_text(encoding="utf-8")).group(1))
    model_limit = [
        v.limit_value
        for v in Player._meta.get_field("latency_offset_ms").validators
        if hasattr(v, "limit_value")
    ]
    assert limit in [abs(v) for v in model_limit], "the screen's limit and the model's must be one number"
    assert client.patch(API, {"latency_offset_ms": limit}, content_type="application/json").status_code == 200
    assert client.patch(API, {"latency_offset_ms": limit + 1}, content_type="application/json").status_code == 400


def test_the_screen_has_the_calibration_and_says_what_to_do(player):
    client, _ = player
    html = client.get("/improv/setup/").content.decode("utf-8")
    for control in ("calibrate", "cal-count", "cal-result", "cal-save", "cal-warning", "latency"):
        assert f'id="{control}"' in html, control
    help_text = re.search(r'id="cal-help"[^>]*>([^<]+)<', html).group(1)
    assert "sixteen" in help_text, "the player is told how many taps before they start"
    assert "tap" in help_text.lower()


def test_the_page_loads_the_click_and_the_maths_it_needs_in_order(player):
    client, _ = player
    html = client.get("/improv/setup/").content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html)]
    assert names == [
        "midi.js", "chart.js", "recognize.js", "timing.js", "synth.js", "calibrate.js",
        "setup.js", "setup-page.js",
    ]  # fmt: skip
    assert names.index("timing.js") < names.index("calibrate.js"), "calibrate.js is built on timing.js"
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_the_page_measures_with_the_clock_the_sound_actually_comes_out_on():
    """A click's scheduled time is not when it is heard. Using the wrong one would store the
    output latency as if it were the player's own lead, which is the whole trap the spike found."""
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "getOutputTimestamp()" in page
    assert "Timing.makeAnchor(" in page
    assert "Timing.heardAt(" in page
    assert "Cal.collect(" in page and "Cal.result(" in page


def test_the_count_in_clicks_are_not_measured_against():
    """The first clicks are there to find the pulse. Measuring against them would count
    the taps the player has not started making yet."""
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "slice(run.plan.countIn)" in page


def test_the_logic_module_touches_no_browser_api():
    for path in (LOGIC_JS, TIMING_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout"):
            assert forbidden not in text, f"{path.name} reaches for {forbidden}"


def test_a_slow_output_is_warned_about_rather_than_calibrated_away():
    text = LOGIC_JS.read_text(encoding="utf-8")
    assert "latencyNote" in text
    assert "outputLatency" in PAGE_JS.read_text(encoding="utf-8"), "the page has to ask the output how slow it is"
