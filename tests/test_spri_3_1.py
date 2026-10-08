"""SPR-I.3.1 improv: the Player profile, the Setup screen, and remembering the keyboard.

The rules (which input to listen to, what a hot-plug means, the field checks) are tested
under Node in tests/js/spri31.test.js, because they run in the browser. This file runs that
suite, proves the profile is made on a first visit and belongs to one person only, proves
the profile endpoint is a singleton that cannot be asked for somebody else's row, and checks
that the page and its script agree.

Traces: spec ch. 4 and 8, feature 23, backlog SPR-I.3.1.
"""

import re
from pathlib import Path

import pytest
import shutil
import subprocess
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import Client

from improv.models import Player

pytestmark = pytest.mark.spri31

TEMPLATE = Path("templates/improv/setup.html")
PAGE_JS = Path("static/improv/setup-page.js")
LOGIC_JS = Path("static/improv/setup.js")
URL = "/improv/setup/"
API = "/improv/api/player/"
PASSWORD = "spri31-pass-7206"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p31member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p31other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p31stranger", password=PASSWORD)
    return {"member": member, "other": other, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def test_the_setup_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri31.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


# --------------------------------------------------------------- the profile row


def test_a_first_visit_makes_the_profile_and_a_second_one_does_not_make_another(people):
    assert not Player.objects.exists()
    client = _client(people["member"])
    assert client.get(URL).status_code == 200
    profile = Player.objects.get(user=people["member"])
    assert client.get(URL).status_code == 200
    assert Player.objects.count() == 1
    assert Player.objects.get(user=people["member"]).pk == profile.pk


def test_the_profile_starts_with_the_defaults_the_spec_asks_for(people):
    _client(people["member"]).get(URL)
    profile = Player.objects.get(user=people["member"])
    assert profile.daily_goal_minutes == 15
    assert profile.latency_offset_ms == 0, "nothing is calibrated until the player calibrates it"
    assert profile.midi_input_name == ""
    assert profile.note_names == "sharps"
    assert profile.demo_output == "piano", "the piano is the default whenever an output is found"
    assert profile.timezone == "Asia/Jerusalem"


def test_each_player_gets_their_own_profile(people):
    _client(people["member"]).get(API)
    _client(people["other"]).get(API)
    assert Player.objects.count() == 2
    assert Player.objects.filter(user=people["member"]).count() == 1


def test_nobody_else_gets_the_page_or_the_profile(people):
    for user in (None, people["stranger"]):
        assert _client(user).get(URL).status_code == 404
        assert _client(user).get(API).status_code == 404
    assert not Player.objects.exists(), "an outsider does not get a profile made for them"


# -------------------------------------------------------------------- the API


def test_the_profile_endpoint_answers_with_this_players_own_row(people):
    reply = _client(people["member"]).get(API)
    assert reply.status_code == 200
    data = reply.json()
    assert data["username"] == "p31member"
    assert data["id"] == Player.objects.get(user=people["member"]).pk
    assert set(data) == {
        "id", "username", "daily_goal_minutes", "latency_offset_ms", "midi_input_name",
        "note_names", "demo_output", "timezone", "trainer_tempo", "created_at",
    }  # fmt: skip


def test_the_profile_is_a_singleton_with_no_id_in_the_route_to_ask_for(people):
    client = _client(people["member"])
    mine = Player.objects.create(user=people["other"]).pk
    assert client.get(f"{API}{mine}/").status_code == 404, "there is no route for another player's row"
    assert client.post(API, {}, content_type="application/json").status_code == 405
    assert client.delete(API).status_code == 405


def test_a_player_can_change_their_own_profile(people):
    client = _client(people["member"])
    client.get(API)
    changed = client.patch(
        API,
        {"daily_goal_minutes": 45, "note_names": "flats", "demo_output": "laptop", "midi_input_name": "Clavinova"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    profile = Player.objects.get(user=people["member"])
    assert profile.daily_goal_minutes == 45
    assert profile.note_names == "flats"
    assert profile.demo_output == "laptop"
    assert profile.midi_input_name == "Clavinova"


def test_whose_profile_it_is_cannot_be_changed_through_the_api(people):
    client = _client(people["member"])
    client.patch(API, {"username": "p31other", "id": 999}, content_type="application/json")
    profile = Player.objects.get(user=people["member"])
    assert profile.user == people["member"]
    assert profile.pk != 999


@pytest.mark.parametrize(
    "field,value",
    [
        ("daily_goal_minutes", 0),
        ("daily_goal_minutes", 500),
        ("latency_offset_ms", 5000),
        ("latency_offset_ms", -5000),
        ("note_names", "squiggles"),
        ("demo_output", "trumpet"),
        ("midi_input_name", "x" * 200),
    ],
)
def test_the_server_refuses_a_value_it_could_not_act_on(people, field, value):
    client = _client(people["member"])
    client.get(API)
    assert client.patch(API, {field: value}, content_type="application/json").status_code == 400


def test_the_calibration_number_is_stored_as_the_calibration_screen_will_write_it(people):
    client = _client(people["member"])
    client.get(API)
    assert client.patch(API, {"latency_offset_ms": -48}, content_type="application/json").status_code == 200
    assert Player.objects.get(user=people["member"]).latency_offset_ms == -48


# ------------------------------------------------------- the page and its script


def test_a_player_gets_the_page_and_it_says_where_the_profile_is(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    assert 'id="setup"' in html
    assert f'data-api-player="{API}"' in html
    token = re.search(r'data-csrf="([^"]+)"', html)
    assert token and len(token.group(1)) >= 32, "saving needs the CSRF token, because the API uses session auth"


def test_the_menu_leads_to_setup(people):
    for url in ("/improv/", URL, "/improv/play/"):
        html = _client(people["member"]).get(url).content.decode("utf-8")
        assert f'href="{URL}"' in html, url


def test_every_script_the_page_loads_is_served_and_this_sprints_are_in_order(people):
    """Later sprints add more scripts to this page, and the newest sprint's test pins the
    whole list. What this one owns is that its own three are there, in their own order."""
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html) if Path(src).name not in ("control.js", "control-page.js")]
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"
    assert names[-1] == "setup-page.js", "the page script runs after everything it uses"
    assert names.index("midi.js") < names.index("setup-page.js")
    assert names.index("setup.js") < names.index("setup-page.js")


def test_every_control_the_script_reads_exists_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([a-z-]+)"\)', script))
    for ids in re.findall(r"for \(const id of \[([^\]]+)\]", script):
        wanted |= set(re.findall(r'"([a-z-]+)"', ids))
    assert len(wanted) >= 10, "the check found too few controls to mean anything"
    missing = wanted - set(re.findall(r'\bid="([^"]+)"', html))
    assert not missing, f"the script reads controls the template does not have: {sorted(missing)}"


def test_every_dataset_attribute_the_script_reads_is_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    camels = set(re.findall(r"host\.dataset\.(\w+)", script))
    assert camels
    for camel in camels:
        kebab = "data-" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), camel)
        assert kebab in html, f"the script reads {camel} but the template has no {kebab}"


def test_the_page_builds_its_screen_without_html_injection():
    """A keyboard's name comes from the person's hardware, so it only ever goes in as text."""
    for path in (PAGE_JS, LOGIC_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_logic_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LOGIC_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"setup.js reaches for {forbidden}"


def test_the_page_never_asks_for_more_than_it_needs_from_the_browser():
    """MIDI is asked for without sysex, and the microphone is never asked for at all."""
    text = PAGE_JS.read_text(encoding="utf-8")
    assert "requestMIDIAccess({ sysex: false })" in text
    assert "getUserMedia" not in text


def test_the_page_links_nowhere_outside_the_app(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert href.startswith(("/improv/", "/static/")), f"the page points at {href}"
    assert "http://" not in html and "https://" not in html
