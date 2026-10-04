"""SPR-I.2.1 improv: the chart parser and transposition.

The grammar and the transposition rules are tested under Node against golden
fixtures (tests/js/fixtures/charts.json), because the same file has to run in the
browser. This file runs that suite, keeps the parser pure, and checks that the
grammar is written down where the editor, the library and the recognizer will look.

Traces: spec ch. 3, feature 6; backlog SPR-I.2.1.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.spri21

CHART_JS = Path("static/improv/chart.js")
THEORY = Path("improv/seed_data/theory.json")
API_DOC = Path("docs/improv/api.md")


def test_the_chart_parser_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run(
        [node, "--test", "tests/js/spri21.test.js"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_the_parser_touches_no_browser_api():
    text = re.sub(r"//[^\n]*", "", CHART_JS.read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "performance.now", "AudioContext", "fetch("):
        assert forbidden not in text, f"chart.js reaches for {forbidden}"


def test_the_vocabulary_the_parser_is_fed_comes_from_the_serializer_fields():
    """The page builds the parser's vocabulary from /improv/api/chord-qualities/, so
    the API has to expose exactly the two fields the parser reads."""
    from improv.serializers import ChordQualitySerializer

    fields = ChordQualitySerializer().get_fields()
    assert "symbol" in fields and "aliases" in fields


def test_the_seed_gives_every_quality_a_symbol_the_parser_can_read_back():
    seed = json.loads(THEORY.read_text(encoding="utf-8"))
    symbols = [q["symbol"] for q in seed["chord_qualities"]]
    assert len(symbols) == len(set(symbols)), "two qualities share a symbol, so the parser could not tell them apart"
    aliases = [a for q in seed["chord_qualities"] for a in q.get("aliases", [])]
    assert not set(aliases) & set(symbols), "an alias is also somebody's symbol"


def test_the_grammar_is_documented():
    text = API_DOC.read_text(encoding="utf-8")
    assert "## Chart grammar" in text
    for must in ("`%`", "`|:`", "`:|`", "`[1`", "`{key:", "slash", "first error", "transpos"):
        assert must in text, f"the chart grammar does not cover {must}"
