"""SPR-I.2.6 improv: changes while it plays (key, tempo, feel, band) and the output picker.

The rules (swapping the plan at the next bar line, which changes may go live, which
outputs are listed) are tested under Node in tests/js/spri26.test.js, because they run in
the browser. This file runs that suite and checks that the page, its script and the
template still agree: the output picker exists, the script that lists outputs is loaded
before the page script, the lock list the page uses is the one the logic module exports,
and the on-screen hint tells the truth about what moves while it plays.

Traces: spec ch. 3 and 8, backlog SPR-I.2.6.
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

pytestmark = pytest.mark.spri26

TEMPLATE = Path("templates/improv/play.html")
PAGE_JS = Path("static/improv/play-page.js")
PLAY_JS = Path("static/improv/play.js")
OUTPUT_JS = Path("static/improv/output.js")
SCHEDULER_JS = Path("static/improv/scheduler.js")
PASSWORD = "spri26-pass-3917"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p26member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p26stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _html(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    response = client.get("/improv/play/")
    return response


def test_the_live_change_and_output_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri26.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_anyone_signed_in_gets_the_page_and_a_visitor_is_sent_to_the_front_door(people):
    assert _html(people["member"]).status_code == 200
    assert _html(people["stranger"]).status_code == 200
    visitor = _html(None)
    assert visitor.status_code == 302
    assert visitor.headers["Location"].startswith("/improv/?next=")


def test_the_output_picker_is_on_the_page_and_starts_hidden(people):
    html = _html(people["member"]).content.decode("utf-8")
    assert re.search(r'<div id="output-row"[^>]*\bhidden\b', html), "the picker should stay hidden until the browser supports it"
    assert re.search(r'<select id="output"', html)
    assert re.search(r'<label for="output">', html)
    assert re.search(r'<p id="output-note"[^>]*\bhidden\b', html)


def test_the_output_script_is_served_and_loads_before_the_page_script(people):
    html = _html(people["member"]).content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html)]
    assert names.index("output.js") < names.index("play-page.js")
    assert finders.find("improv/output.js")


def test_the_page_locks_what_the_logic_module_says_and_nothing_else():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "P.LOCKED_CONTROLS" in page, "the page must lock exactly the list play.js exports"
    logic = PLAY_JS.read_text(encoding="utf-8")
    locked = re.search(r"LOCKED_CONTROLS\s*=\s*\[([^\]]+)\]", logic)
    live = re.search(r"LIVE_CONTROLS\s*=\s*\[([^\]]+)\]", logic)
    assert locked and live
    template = TEMPLATE.read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', template))
    for found in (locked, live):
        for control in re.findall(r'"([a-z-]+)"', found.group(1)):
            assert control in ids, f"{control} is named by play.js but is not on the page"


def test_the_live_controls_apply_a_change_at_the_next_bar_line_and_say_so():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "setPlan(" in page and "canGoLive(" in page and "setBpm(" in page
    assert "from the next bar" in page
    hint = TEMPLATE.read_text(encoding="utf-8")
    assert "next bar line" in hint
    for word in ("key", "tempo", "feel", "band"):
        assert word in hint.split("next bar line")[0].split("While it plays")[-1], f"the hint does not mention {word}"


def test_the_output_choice_is_only_text_and_never_asks_for_the_microphone():
    for path in (OUTPUT_JS, PAGE_JS, SCHEDULER_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"
        assert "getUserMedia" not in text, f"{path.name} would ask for the microphone"


def test_the_output_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", OUTPUT_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"output.js reaches for {forbidden}"
