"""SPR-I.1.2 improv: the spike page that proves MIDI in, a click out and a timing readout.

The numbers the page produces can only be judged on Avi's piano and laptop. What
can be tested without them is: the pure maths (under Node), that the page exists
behind the gate, that it carries every control the spike needs, and that it is
built on the files the later sprints will reuse rather than on one throwaway
script.

Acceptance of the sprint itself is Avi at his piano, not this file.

Traces: spec ch. 3, 4, 9; backlog SPR-I.1.2.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

pytestmark = pytest.mark.spri12

STATIC = Path("static/improv")


def test_the_timing_and_midi_maths_pass_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run(
        [node, "--test", "tests/js/spri12.test.js"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


@pytest.fixture
def member(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user(username="spike-member", password="spri12-pass-3317")
    user.groups.add(group)
    client = Client()
    client.force_login(user)
    return client


def test_the_spike_page_loads_for_a_player(member):
    response = member.get("/improv/spike/")
    assert response.status_code == 200
    assert "improv/spike.html" in [t.name for t in response.templates]


def test_the_spike_page_is_gated_like_everything_else(db):
    assert Client().get("/improv/spike/").status_code == 404


def test_the_page_has_every_control_the_spike_needs(member):
    html = member.get("/improv/spike/").content.decode("utf-8")
    for element_id in (
        "start-audio",
        "midi-status",
        "midi-input",
        "bpm",
        "click-toggle",
        "keyboard",
        "readout",
        "summary",
        "copy-result",
        "environment",
    ):
        assert f'id="{element_id}"' in html, f"the spike page has no #{element_id}"


def test_the_page_uses_the_shared_files_not_one_inline_script(member):
    html = member.get("/improv/spike/").content.decode("utf-8")
    for name in ("midi.js", "timing.js", "spike.js"):
        assert f"improv/{name}" in html, f"{name} is not loaded"
        assert (STATIC / name).exists()
    inline = re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, flags=re.S)
    assert all(len(block.strip()) < 400 for block in inline), "logic belongs in static files, where Node can test it"


def test_the_pure_files_touch_no_browser_api():
    """timing.js and midi.js must run under Node, so they may not reach for the
    browser. That is what keeps them testable."""
    for name in ("timing.js", "midi.js"):
        text = re.sub(r"//[^\n]*", "", (STATIC / name).read_text(encoding="utf-8"))
        for forbidden in ("document.", "window.", "navigator.", "performance.now", "AudioContext"):
            assert forbidden not in text, f"{name} reaches for {forbidden}"


def test_the_page_says_what_browsers_it_needs_and_what_to_do_without_midi(member):
    html = member.get("/improv/spike/").content.decode("utf-8").lower()
    assert "chrome" in html and "edge" in html
    assert "on-screen keyboard" in html
