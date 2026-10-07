"""SPR-I.7.1 improv: the piano as a remote control, the parts that need no browser.

The rules are proved under Node (tests/js/spri71.test.js). Here: the Node run is part of the suite,
every screen loads the control layer, the legend in the menu names the same keys as control.js, and
a screen that reads the piano leaves the control zone out.

Traces: spec ch. 8 "Two standing rules for every screen", backlog SPR-I.7.1.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.spri71

PASSWORD = "spri71-pass-5530"
STATIC = Path("static/improv")
SCREENS = (
    "/improv/",
    "/improv/play/",
    "/improv/lessons/",
    "/improv/challenges/",
    "/improv/library/",
    "/improv/takes/",
    "/improv/practice/",
    "/improv/progress/",
    "/improv/reference/",
    "/improv/setup/",
    "/improv/spike/",
)


@pytest.fixture
def member(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p71member", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    client = Client()
    client.force_login(user)
    return client


def test_the_control_rules_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri71.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("path", SCREENS)
def test_every_screen_loads_the_control_layer_before_its_own_scripts(member, path):
    html = member.get(path).content.decode("utf-8")
    order = [html.find(name) for name in ("improv/control.js", "improv/control-page.js")]
    assert all(i >= 0 for i in order), path
    assert order == sorted(order), path


def test_the_menu_legend_names_the_keys_control_js_defines(member):
    html = member.get("/improv/").content.decode("utf-8")
    legend = re.search(r'class="im-keys"[^>]*>(.*?)</span>', html, re.S).group(1)
    for name in ("C8", "B7", "A#7"):
        assert f"<b>{name}</b>" in legend
    source = (STATIC / "control.js").read_text(encoding="utf-8")
    assert '108: "primary"' in source and '107: "secondary"' in source and '106: "tertiary"' in source


def test_the_screens_that_read_the_piano_leave_the_control_zone_out():
    for name in ("play-page.js", "setup-page.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        assert "Ctl.isControlNote(message.note)" in source, name


def test_the_hint_is_drawn_from_an_attribute_so_a_changed_label_keeps_it():
    css = (STATIC / "improv.css").read_text(encoding="utf-8")
    assert "[data-key-hint]::after" in css and "attr(data-key-hint)" in css
