"""SPR-I.3.3 improv: which scale a run of single notes fits.

The rule is a pure function, tested under Node in tests/js/spri33.test.js against the
app's own scale table. This file runs that suite and checks the screen that uses it: the
Setup page names the fits while a run comes in, and says how many more notes it wants
before it will claim anything.

Traces: spec ch. 4, feature 2, backlog SPR-I.3.3.
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

from improv.models import Scale

pytestmark = pytest.mark.spri33

LOGIC_JS = Path("static/improv/recognize.js")
PAGE_JS = Path("static/improv/setup-page.js")
PASSWORD = "spri33-pass-8820"


@pytest.fixture
def player(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p33member", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    client = Client()
    client.force_login(user)
    return client


def test_the_scale_hints_pass_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri33.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_every_scale_in_the_table_can_be_found(player):
    """A scale nobody can ever be told they are playing is a scale that may as well not be
    in the table, so each row has to be reachable by playing it."""
    node = shutil.which("node")
    assert node
    rows = [{"slug": s.slug, "name": s.name, "intervals": s.intervals} for s in Scale.objects.all()]
    assert len(rows) >= 20
    script = """
      const R = require("./static/improv/recognize.js");
      const scales = JSON.parse(process.argv[1]).map((s, order) => ({ ...s, order }));
      const missed = [];
      for (const scale of scales) {
        const notes = scale.intervals.map((i) => 60 + i);
        const got = R.scaleFits(notes, scales, { spelling: "sharps" });
        const found = got.fits.some((f) => f.slug === scale.slug && f.rootPc === 0);
        if (!found) missed.push(`${scale.slug} was not offered for its own notes`);
      }
      if (missed.length) { console.log(missed.join("; ")); process.exit(1); }
    """
    result = subprocess.run([node, "-e", script, __import__("json").dumps(rows)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_setup_page_shows_the_fits_and_knows_where_the_scales_are(player):
    html = player.get("/improv/setup/").content.decode("utf-8")
    assert 'id="scale-fits"' in html
    assert 'data-api-scales="/improv/api/scales/"' in html
    reply = player.get("/improv/api/scales/")
    assert reply.status_code == 200
    rows = reply.json()
    assert len(rows) >= 20
    for row in rows:
        assert row["intervals"] and row["name"] and row["slug"]


def test_the_page_asks_the_recognizer_rather_than_deciding_for_itself():
    page = PAGE_JS.read_text(encoding="utf-8")
    assert "Rec.scaleFits(" in page
    assert "Rec.recentNotes(" in page, "the window belongs to the tested function, not the page"
    body = re.sub(r"//[^\n]*", "", page)
    for invented in ("dorian", "Dorian", "pentatonic", "intervals"):
        assert invented not in body, f"setup-page.js decides {invented} itself instead of asking"


def test_the_window_is_a_few_seconds_and_says_so_once():
    page = PAGE_JS.read_text(encoding="utf-8")
    window = re.search(r"RUN_SECONDS = (\d+)", page)
    assert window, "the window has to be one named number, not a figure sprinkled about"
    assert 2 <= int(window.group(1)) <= 10, "a run is a few seconds (spec ch. 4)"


def test_the_minimum_before_a_scale_is_named_is_the_spec_number():
    text = LOGIC_JS.read_text(encoding="utf-8")
    assert "MIN_PCS_FOR_A_SCALE = 5" in text, "five different notes before a scale is claimed (spec ch. 4)"
