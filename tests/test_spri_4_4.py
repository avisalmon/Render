"""SPR-I.4.4 improv: the Takes screen, and replay over the same band through the demo output.

The rules (a take is replayed from its own snapshot and nothing else, the notes to sound,
the words of the list) are tested under Node in tests/js/spri44.test.js. This file runs that
suite, proves the page is served to a player and nobody else, and checks that the page and
its script agree and that the replay path is the one the spec asks for.

Traces: spec ch. 6 and 8, feature 15, backlog SPR-I.4.4.
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

pytestmark = pytest.mark.spri44

URL = "/improv/takes/"
TEMPLATE = Path("templates/improv/takes.html")
PAGE_JS = Path("static/improv/takes-page.js")
LOGIC_JS = Path("static/improv/takes.js")
SYNTH_JS = Path("static/improv/synth.js")
PASSWORD = "spri44-pass-5027"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p44member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p44stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def test_the_takes_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri44.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_a_player_gets_the_page_and_nobody_else_does(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    assert 'id="takes"' in html
    assert _client(None).get(URL).status_code == 404
    assert _client(people["stranger"]).get(URL).status_code == 404


def test_the_page_says_where_everything_it_needs_is_and_it_all_answers(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    client = _client(people["member"])
    urls = re.findall(r'data-api-[a-z-]+="([^"]+)"', html)
    assert len(urls) == 5, "takes, the titles, the bands, the chords, the profile"
    for url in urls:
        assert client.get(url).status_code == 200, url
    assert re.search(r'data-csrf="[^"]{32,}"', html), "keeping and deleting go through the API"
    assert 'data-play-url="/improv/play/"' in html


def test_the_menu_leads_to_the_takes(people):
    for url in ("/improv/", URL, "/improv/play/"):
        html = _client(people["member"]).get(url).content.decode("utf-8")
        assert f'href="{URL}"' in html, url


def test_every_script_the_page_loads_is_served_and_the_band_comes_before_the_page(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html)]
    assert names == [
        "chart.js", "band.js", "scheduler.js", "synth.js", "chart-view.js", "play.js",
        "midi.js", "setup.js", "timing.js", "takes.js", "takes-page.js",
    ]  # fmt: skip
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_every_control_the_script_reads_exists_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([a-z-]+)"\)', script))
    assert len(wanted) >= 8
    missing = wanted - set(re.findall(r'\bid="([^"]+)"', html))
    assert not missing, f"the script reads controls the template does not have: {sorted(missing)}"


def test_every_dataset_attribute_the_script_reads_is_in_the_template():
    script = PAGE_JS.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    camels = set(re.findall(r"host\.dataset\.(\w+)", script))
    assert len(camels) >= 6
    for camel in camels:
        kebab = "data-" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), camel)
        assert kebab in html, f"the script reads {camel} but the template has no {kebab}"


def test_a_replay_is_built_from_the_takes_own_snapshot_and_the_same_band():
    """The band plan comes from ImprovPlay.buildPlan over the take's own chart, key, bar
    length, tempo and feel, exactly as Play builds it, so what is heard is the same band."""
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "P.buildPlan({ progression: T.replayProgression(take" in page
    assert "settings: T.replaySettings(take)" in page
    assert "state.scheduler.start(built.plan, { bpm: take.tempo" in page


def test_the_notes_go_to_the_piano_over_midi_or_sound_as_a_plain_tone():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert 'demo_output !== "piano"' in page, "the profile decides"
    assert "M.noteOnBytes(" in page and "M.noteOffBytes(" in page
    assert "Timing.heardAt(anchor, n.when)" in page, "MIDI out is timed on the clock the sound comes out on"
    assert 'voice: "demo"' in page
    synth = SYNTH_JS.read_text(encoding="utf-8")
    assert '"demo"' in synth and "function demo(" in synth


def test_stopping_a_replay_lets_every_note_go():
    """A MIDI note-on with no note-off is a stuck key on a real piano."""
    page = PAGE_JS.read_text(encoding="utf-8")
    stop = page.split("function stopReplay()")[1].split("\n  }\n")[0]
    assert "noteOffBytes" in stop


def test_deleting_takes_two_clicks_and_keeping_takes_one():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "Click again to delete" in page
    assert 'send("PATCH"' in page and "is_kept: !take.is_kept" in page
    assert 'send("DELETE"' in page


def test_the_page_builds_its_screen_without_html_injection():
    for path in (PAGE_JS, LOGIC_JS):
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_logic_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LOGIC_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"takes.js reaches for {forbidden}"


def test_the_page_links_nowhere_outside_the_app(people):
    html = _client(people["member"]).get(URL).content.decode("utf-8")
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert href.startswith(("/improv/", "/static/")), f"the page points at {href}"
    assert "http://" not in html and "https://" not in html
