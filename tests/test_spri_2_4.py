"""SPR-I.2.4 improv: the Play screen v0.

The logic (settings to a plan, the count-in, the loop range, the lit bar) is tested
under Node in tests/js/spri24.test.js, because it has to run in the browser. This file
runs that suite, proves the page is served to a player and to nobody else, and checks
that the page script and the template agree: every control the script reads exists,
every script the page loads is served, and nothing reaches outside the app.

Traces: spec ch. 3 and 8, backlog SPR-I.2.4.
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

pytestmark = pytest.mark.spri24

TEMPLATE = Path("templates/improv/play.html")
PAGE_JS = Path("static/improv/play-page.js")
LOGIC_JS = Path("static/improv/play.js")
VIEW_JS = Path("static/improv/chart-view.js")
PASSWORD = "spri24-pass-8841"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p24member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p24stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _get(user, url="/improv/play/"):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client.get(url)


def test_the_play_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri24.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_a_player_gets_the_page(people):
    response = _get(people["member"])
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'id="play"' in html
    assert "Play" in html


def test_a_visitor_is_sent_to_the_front_door(people):
    response = _get(None)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/improv/?next=")


def test_a_signed_in_person_without_a_group_gets_the_page(people):
    assert _get(people["stranger"]).status_code == 200


def test_the_page_says_where_the_api_is_and_the_api_answers(people):
    html = _get(people["member"]).content.decode("utf-8")
    urls = {
        "data-api-progressions": "/improv/api/progressions/",
        "data-api-styles": "/improv/api/styles/",
        "data-api-qualities": "/improv/api/chord-qualities/",
    }
    client = Client()
    client.force_login(people["member"])
    for attribute, url in urls.items():
        assert f'{attribute}="{url}"' in html
        reply = client.get(url)
        assert reply.status_code == 200
        assert len(reply.json()) > 0, f"{url} is empty, so the page would have nothing to play"


def test_the_menu_has_the_play_link(people):
    html = _get(people["member"]).content.decode("utf-8")
    assert 'href="/improv/play/"' in html


def test_every_script_the_page_loads_is_served_and_in_the_right_order(people):
    html = _get(people["member"]).content.decode("utf-8")
    loaded = re.findall(r'<script src="([^"]+)"', html)
    names = [Path(src).name for src in loaded]
    # Later sprints add scripts to this page and the newest sprint's test pins the whole list.
    # What this one owns is that its own scripts are there, in their own order, and last the page.
    own = ["chart.js", "band.js", "scheduler.js", "synth.js", "chart-view.js", "play.js"]
    assert [n for n in names if n in own] == own
    assert names[-1] == "play-page.js"
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_every_control_the_script_reads_exists_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([a-z-]+)"\)', script))
    for ids in re.findall(r"for \(const id of \[([^\]]+)\]", script):
        wanted |= set(re.findall(r'"([a-z-]+)"', ids))
    assert len(wanted) >= 15, "the check found too few controls to mean anything"
    present = set(re.findall(r'\bid="([^"]+)"', html))
    # The mix rows are built by the script into the empty #mix container.
    missing = wanted - present
    assert not missing, f"the script reads controls the template does not have: {sorted(missing)}"


def test_every_dataset_attribute_the_script_reads_is_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    for camel in re.findall(r"host\.dataset\.(\w+)", script):
        kebab = "data-" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), camel)
        assert kebab in html, f"the script reads {camel} but the template has no {kebab}"


def test_the_page_builds_its_screen_without_html_injection():
    """Chord names and titles come from the database, so they only ever go in as text."""
    for path in (PAGE_JS, LOGIC_JS, VIEW_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_logic_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LOGIC_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "new AudioContext", "fetch(", "Math.random", "setTimeout"):
        assert forbidden not in text, f"play.js reaches for {forbidden}"


def test_the_page_links_nowhere_outside_the_app(people):
    html = _get(people["member"]).content.decode("utf-8")
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert href.startswith(("/improv/", "/static/")), f"the page points at {href}"
    assert "http://" not in html and "https://" not in html
