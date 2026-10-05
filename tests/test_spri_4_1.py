"""SPR-I.4.1 improv: the judge as a pure function, judge_version 1.

The judge is tested under Node in tests/js/spri41.test.js against golden takes in
tests/js/fixtures/takes.json, with the app's own theory table. This file runs that suite,
proves the golden file covers what spec chapter 5 argues about, and holds the judge to the
shape the rest of the app relies on: pure, versioned, and the only source of a score.

Traces: spec ch. 5, feature 13, backlog SPR-I.4.1.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.spri41

JUDGE_JS = Path("static/improv/judge.js")
GOLDEN = Path("tests/js/fixtures/takes.json")


def test_the_judge_passes_its_golden_takes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri41.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_the_golden_takes_cover_what_the_spec_argues_about():
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 15
    classes = {c for item in cases for c in item.get("classes", [])}
    assert classes >= {"chord", "scale", "approach", "outside"}, "all four classes (spec ch. 5)"
    assert any("anticipat" in item["name"] for item in cases), "the half-beat look-ahead"
    assert any(item.get("withOffset") for item in cases), "the latency offset"
    assert any(item.get("grid") == "swung" for item in cases), "the swung grid"
    assert any(item.get("ignored") for item in cases), "notes during the count-in"
    assert any(item.get("score") is None and item.get("scoring", {}).get("kind") == "free_play" for item in cases)
    kinds = {item.get("scoring", {}).get("kind") for item in cases if item.get("scoring")}
    assert kinds >= {"chord_tones_on_beats", "scale_only", "free_play"}, "the three kinds of this sprint"
    for item in cases:
        assert item.get("name"), "every case says what it proves"


def test_the_judge_is_pure():
    text = re.sub(r"//[^\n]*", "", JUDGE_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "Date.now", "performance."):
        assert forbidden not in text, f"judge.js reaches for {forbidden}"


def test_the_judge_is_versioned_and_the_version_is_one():
    text = JUDGE_JS.read_text(encoding="utf-8")
    assert re.search(r"JUDGE_VERSION = 1;", text), "judge_version 1 is this sprint's rules; a rule change bumps it"


def test_the_judge_reads_chords_and_scales_from_the_table_not_from_itself():
    body = re.sub(r"//[^\n]*", "", JUDGE_JS.read_text(encoding="utf-8"))
    assert "intervals" in body and "roles" in body and "scales" in body
    for invented in ("dorian", "maj7", "[0, 4, 7]", "mixolydian"):
        assert invented not in body, f"judge.js spells out {invented} instead of reading the table"


def test_the_spec_numbers_are_the_judges_numbers():
    """Half a beat of look-ahead, an approach within a beat, a tenth of a beat of tolerance."""
    text = JUDGE_JS.read_text(encoding="utf-8")
    assert "LOOKAHEAD_BEATS = 0.5" in text
    assert "APPROACH_BEATS = 1" in text
    assert "TOLERANCE_OF_BEAT = 0.1" in text
