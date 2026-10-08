"""SPR-I.3.5 improv: the Reference screen, any chord or scale in any key.

The layout rules are a pure function tested under Node in tests/js/spri35.test.js against
the app's own theory table. This file runs that suite, proves the page is served to a player
and nobody else, and checks that the page and its script agree.

Traces: spec ch. 8, feature 11, backlog SPR-I.3.5.
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

pytestmark = pytest.mark.spri35

URL = "/improv/reference/"
TEMPLATE = Path("templates/improv/reference.html")
PAGE_JS = Path("static/improv/reference-page.js")
LOGIC_JS = Path("static/improv/reference.js")
VIEW_JS = Path("static/improv/keyboard-view.js")
PASSWORD = "spri35-pass-6117"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p35member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p35stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_fingerings", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _html(user):
    response = _client(user).get(URL)
    assert response.status_code == 200
    return response.content.decode("utf-8")


def test_the_reference_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri35.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_anyone_signed_in_gets_the_page_and_a_visitor_is_sent_to_the_front_door(people):
    assert 'id="reference"' in _html(people["member"])
    assert 'id="reference"' in _html(people["stranger"])
    visitor = _client(None).get(URL)
    assert visitor.status_code == 302
    assert visitor.headers["Location"].startswith("/improv/?next=")


def test_the_page_says_where_every_table_it_needs_is_and_they_all_answer(people):
    html = _html(people["member"])
    client = _client(people["member"])
    urls = re.findall(r'data-api-[a-z-]+="([^"]+)"', html)
    assert len(urls) == 5, "the player's spelling, the chords, the scales, the pairings and the fingerings"
    for url in urls:
        reply = client.get(url)
        assert reply.status_code == 200, url
        body = reply.json()
        assert body, f"{url} is empty"


def test_the_menu_leads_to_the_reference(people):
    for url in ("/improv/", URL, "/improv/play/"):
        html = _client(people["member"]).get(url).content.decode("utf-8")
        assert f'href="{URL}"' in html, url


def test_every_script_the_page_loads_is_served_and_in_the_right_order(people):
    html = _html(people["member"])
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html) if Path(src).name not in ("control.js", "control-page.js")]
    assert names == ["chart.js", "reference.js", "scale.js", "keyboard-view.js", "reference-page.js"]
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_every_control_the_script_reads_exists_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([a-z-]+)"\)', script))
    for ids in re.findall(r"for \(const id of \[([^\]]+)\]", script):
        wanted |= set(re.findall(r'"([a-z-]+)"', ids))
    assert len(wanted) >= 8, "the check found too few controls to mean anything"
    missing = wanted - set(re.findall(r'\bid="([^"]+)"', html))
    assert not missing, f"the script reads controls the template does not have: {sorted(missing)}"


def test_every_dataset_attribute_the_script_reads_is_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    camels = set(re.findall(r"host\.dataset\.(\w+)", script))
    assert len(camels) == 5
    for camel in camels:
        kebab = "data-" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), camel)
        assert kebab in html, f"the script reads {camel} but the template has no {kebab}"


def test_the_page_draws_the_keys_without_html_injection():
    """Chord and scale names come from the database, so they only ever go in as text."""
    for path in (PAGE_JS, LOGIC_JS, VIEW_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_logic_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LOGIC_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"reference.js reaches for {forbidden}"


def test_the_screen_invents_no_theory_of_its_own():
    """Every note shown has to come from the table, so the admin can add a chord and have it
    appear here without a code change."""
    for path in (PAGE_JS, LOGIC_JS):
        body = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for invented in ("dorian", "maj7", "pentatonic", "[0, 4, 7]"):
            assert invented not in body, f"{path.name} spells out {invented} instead of reading the table"


def test_the_page_links_nowhere_outside_the_app(people):
    html = _html(people["member"])
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert href.startswith(("/improv/", "/static/")), f"the page points at {href}"
    assert "http://" not in html and "https://" not in html
