"""SPR-I.4.2 improv: live feedback on the Play screen, from the same judge as the score.

The judge is tested in SPR-I.4.1; the glue with rules in it (the take's clock, the colours,
the running summary) is tested under Node in tests/js/spri42.test.js. This file runs that
suite and checks the page: it has the keys and the feedback, it loads the judge and what the
judge needs in order, every colour the judge can give is a colour the stylesheet knows, and
the page records a take in the shape SPR-I.4.3 will post.

Traces: spec ch. 5 and 8, features 13 and 14, backlog SPR-I.4.2.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.spri42

TEMPLATE = Path("templates/improv/play.html")
PAGE_JS = Path("static/improv/play-page.js")
PLAY_JS = Path("static/improv/play.js")
CSS = Path("static/improv/improv.css")
PASSWORD = "spri42-pass-1180"


@pytest.fixture
def player(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p42member", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    client = Client()
    client.force_login(user)
    return client


def test_the_live_feedback_glue_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri42.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_the_page_has_the_keys_the_chord_and_the_feedback(player):
    html = player.get("/improv/play/").content.decode("utf-8")
    for control in ("keys", "heard", "feedback", "midi-state"):
        assert f'id="{control}"' in html, control
    assert 'data-api-player="/improv/api/player/"' in html, "the profile carries the keyboard's name and the offset"
    legend = re.search(r'<p class="im-legend".*?</p>', html, re.S).group(0)
    for meaning in ("chord tone", "in the scale", "approach", "outside"):
        assert meaning in legend


def test_the_page_loads_the_judge_and_what_it_needs_in_order(player):
    html = player.get("/improv/play/").content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html) if Path(src).name not in ("control.js", "control-page.js")]
    assert names == [
        "chart.js", "band.js", "scheduler.js", "synth.js", "chart-view.js", "play.js", "output.js",
        "midi.js", "setup.js", "recognize.js", "timing.js", "judge.js", "practice.js", "keyboard-view.js", "play-page.js",
    ]  # fmt: skip
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_every_colour_the_judge_can_give_is_in_the_stylesheet():
    classes = re.findall(r'"(im-key-[a-z]+)"', PLAY_JS.read_text(encoding="utf-8"))
    assert set(classes) >= {"im-key-chord", "im-key-guide", "im-key-scale", "im-key-approach", "im-key-pending", "im-key-outside"}
    css = CSS.read_text(encoding="utf-8")
    for cls in set(classes):
        assert re.search(rf"\.im-key-(white|black)\.{cls}\b", css), f"{cls} has no colour on the keys"


def test_the_live_display_and_the_final_score_come_from_the_one_judge():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert page.count("J.judge(") == 1, "one call, run with now while it plays and without it at the end"
    assert "now: now === null ? undefined : now" in page
    assert "judgeLive(true)" in page and "judgeLive(false)" in page


def test_a_note_is_put_on_the_takes_clock_through_the_anchor_not_the_wall_clock():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "Timing.makeAnchor(state.ctx.getOutputTimestamp())" in page
    assert "Timing.audioAt(" in page and "P.takeTimeMs(" in page
    body = re.sub(r"//[^\n]*", "", page)
    assert "performance.now()" not in body.split("function takeTimeOf")[1].split("function anchorTake")[0]


def test_the_take_is_recorded_in_the_shape_the_server_will_take():
    """SPR-I.4.3 posts these events as they are: t_ms, type, note, velocity (data model, Take)."""
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "t_ms: Math.round(t), type: message.type, note: message.note, velocity: message.velocity || 0" in page


def test_the_page_judges_free_play_and_leaves_scoring_kinds_to_the_exercises():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "scoring: P.exerciseScoring(" in page
    assert 'return { kind: "free_play", params: {} }' in PLAY_JS.read_text(encoding="utf-8")


def test_the_page_builds_its_screen_without_html_injection():
    text = re.sub(r"//[^\n]*", "", PAGE_JS.read_text(encoding="utf-8"))
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert forbidden not in text, f"play-page.js uses {forbidden}"


def test_play_js_is_still_pure_after_growing():
    text = re.sub(r"//[^\n]*", "", PLAY_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "new AudioContext", "fetch(", "Math.random", "setTimeout"):
        assert forbidden not in text, f"play.js reaches for {forbidden}"
