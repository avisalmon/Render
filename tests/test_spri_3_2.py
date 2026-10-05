"""SPR-I.3.2 improv: naming the chord the player is holding.

The recognizer is a pure function with golden cases, tested under Node in
tests/js/spri32.test.js against the app's own theory table. This file runs that suite,
proves the golden file is real work and not a stub, and checks the one screen that uses
the recognizer so far: Setup names what is played, so a player can see the piano is
understood before any score depends on it.

Traces: spec ch. 4, feature 2, backlog SPR-I.3.2.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import Client

from improv.models import ChordQuality

pytestmark = pytest.mark.spri32

LOGIC_JS = Path("static/improv/recognize.js")
PAGE_JS = Path("static/improv/setup-page.js")
TEMPLATE = Path("templates/improv/setup.html")
GOLDEN = Path("tests/js/fixtures/chords.json")
PASSWORD = "spri32-pass-4418"


@pytest.fixture
def player(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p32member", password=PASSWORD)
    user.groups.add(group)
    from django.core.management import call_command

    call_command("seed_improv_theory", stdout=__import__("io").StringIO())
    client = Client()
    client.force_login(user)
    return client


def test_the_recognizer_passes_its_golden_cases_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri32.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_the_golden_file_covers_the_cases_the_spec_argues_about():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) >= 30
    names = [c.get("name", "") for c in cases]
    kinds = [c.get("kind", "chord") for c in cases]

    assert sum(1 for n in names if "/" in n) >= 4, "slash chords are a rule of their own (spec ch. 4)"
    assert sum(1 for k in kinds if k == "notes") >= 4, "fewer than three notes must not be forced into a chord"
    assert any(c.get("guesses") for c in cases), "the rootless shell has to be covered"
    assert any(c.get("exact") is False for c in cases), "a reading with a note missing has to be covered"
    assert sum(1 for c in cases if c.get("spelling") == "flats") >= 1, "both spellings have to be covered"
    assert sum(1 for c in cases if len(c["notes"]) >= 5) >= 3, "the extensions have to be covered"
    for case in cases:
        assert case.get("why") or case.get("name") or case.get("kind"), case


def test_every_chord_quality_in_the_table_can_be_recognized(player):
    """The recognizer is only as good as the table, so no row may be unreachable."""
    node = shutil.which("node")
    assert node
    rows = [
        {"symbol": q.symbol, "intervals": q.intervals, "roles": q.roles, "family": q.family, "sort_order": q.sort_order}
        for q in ChordQuality.objects.all()
    ]
    assert len(rows) >= 20
    script = """
      const R = require("./static/improv/recognize.js");
      const qualities = JSON.parse(process.argv[1]);
      const missed = [];
      for (const q of qualities) {
        const notes = q.intervals.map((i) => 60 + i);
        const got = R.recognize(notes, qualities, { spelling: "sharps" });
        const wanted = "C" + (q.symbol === "maj" ? "" : q.symbol);
        if (got.kind !== "chord" || got.name !== wanted) missed.push(`${wanted} came back as ${got.name || got.kind}`);
      }
      if (missed.length) { console.log(missed.join("; ")); process.exit(1); }
    """
    result = subprocess.run([node, "-e", script, json.dumps(rows)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_logic_module_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", LOGIC_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
        assert forbidden not in text, f"recognize.js reaches for {forbidden}"


def test_the_recognizer_keeps_the_theory_table_as_the_only_source_of_chords():
    """No chord spelling may be hard-coded here: the table is the one place that says
    what a chord is, so the admin can add one without a code change."""
    text = LOGIC_JS.read_text(encoding="utf-8")
    body = re.sub(r"//[^\n]*", "", text)
    assert "intervals" in body and "roles" in body
    for invented in ("maj7", "m7b5", "dim7", "7alt", "sus4"):
        assert invented not in body, f"recognize.js names {invented} itself instead of reading the table"


def test_the_setup_page_names_what_is_played(player):
    html = player.get("/improv/setup/").content.decode("utf-8")
    assert 'id="heard"' in html
    assert 'id="heard-notes"' in html
    assert 'data-api-qualities="/improv/api/chord-qualities/"' in html
    assert player.get("/improv/api/chord-qualities/").status_code == 200


def test_the_setup_page_loads_the_recognizer_and_what_it_needs_in_order(player):
    html = player.get("/improv/setup/").content.decode("utf-8")
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html)]
    assert "recognize.js" in names
    assert names.index("chart.js") < names.index("recognize.js"), "recognize.js spells notes with chart.js"
    assert names.index("recognize.js") < names.index("setup-page.js")
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


def test_the_page_names_the_chord_as_text_only():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "Rec.recognize(" in page
    assert "spelling" in page, "the name has to follow the player's own note spelling"
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert forbidden not in re.sub(r"//[^\n]*", "", page), f"setup-page.js uses {forbidden}"
