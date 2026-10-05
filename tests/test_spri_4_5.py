"""SPR-I.4.5 improv: the remaining scoring kinds.

Guide tones, approach notes, rhythm motif and call and response are rules in the judge,
tested under Node in tests/js/spri45.test.js against golden cases over the judge's own chart
and the app's theory table. This file runs that suite, proves the golden file covers each
kind the spec names for version 1, and holds comping voicings to v2.

Traces: spec ch. 5, features 18 and 19, backlog SPR-I.4.5.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.spri45

JUDGE_JS = Path("static/improv/judge.js")
GOLDEN = Path("tests/js/fixtures/scoring.json")
SPEC = Path("docs/improv/spec.md")


def test_the_scoring_kinds_pass_their_golden_cases_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri45.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_the_golden_cases_cover_every_kind_the_spec_names_for_version_one():
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    kinds = {c["scoring"]["kind"] for c in cases}
    assert kinds >= {"guide_tones", "approach_notes", "rhythm_motif", "call_and_response"}
    for kind in ("guide_tones", "approach_notes", "rhythm_motif", "call_and_response"):
        scores = [c["score"] for c in cases if c["scoring"]["kind"] == kind and "score" in c]
        assert 100 in scores, f"{kind} has no full-marks case"
        assert any(s < 100 for s in scores), f"{kind} has no case that loses marks"
    assert any(c.get("throws") and c["scoring"]["kind"] == "comping_voicings" for c in cases), "comping voicings is v2"


def test_every_kind_in_the_spec_table_is_either_scored_or_named_as_v2():
    text = SPEC.read_text(encoding="utf-8")
    table = text.split("### Scoring kinds")[1].split("###")[0]
    rows = [r.split("|")[1].strip() for r in table.splitlines() if r.startswith("| ") and "---" not in r]
    rows = [r for r in rows if r and r != "Kind"]
    assert len(rows) == 8
    judge = JUDGE_JS.read_text(encoding="utf-8")
    kinds = re.findall(r'"([a-z_]+)"', judge.split("SCORING_KINDS = [")[1].split("]")[0])
    assert len(kinds) == 7
    assert "comping_voicings" not in kinds
    assert "Comping voicings" in rows


def test_the_judge_version_did_not_move_because_no_existing_score_changed():
    assert "JUDGE_VERSION = 1;" in JUDGE_JS.read_text(encoding="utf-8")


def test_each_kind_explains_itself_beside_the_score():
    judge = JUDGE_JS.read_text(encoding="utf-8")
    assert "scoring: scored.details" in judge
    for key in ("guideTones", "connections", "targets", "reached", "expected", "matched", "onsetsMatched", "shapesMatched"):
        assert key in judge, key
