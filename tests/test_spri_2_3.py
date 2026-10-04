"""SPR-I.2.3 improv: the band engine (planner, look-ahead scheduler, synth voices).

The planner and the scheduler are pure and tested under Node, because the same files
run in the browser. This file runs that suite, keeps the three modules free of the
browser, and checks that the lists the band understands are the lists the server
validates, and that the spec says what the band does.

Traces: spec ch. 3, feature 5; backlog SPR-I.2.3.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.spri23

STATIC = Path("static/improv")
MODULES = ("band.js", "scheduler.js", "synth.js")
SPEC = Path("docs/improv/spec.md")
DATA_MODEL = Path("docs/improv/data_model.md")


def _node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    return node


def test_the_band_engine_passes_under_node():
    result = subprocess.run(
        [_node(), "--test", "tests/js/spri23.test.js"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


@pytest.mark.parametrize("name", MODULES)
def test_the_module_touches_no_browser_api(name):
    """The clock, the timer and the AudioContext are handed in, which is what lets a
    test run the whole band without a browser."""
    text = re.sub(r"//[^\n]*", "", (STATIC / name).read_text(encoding="utf-8"))
    for forbidden in ("document.", "window.", "navigator.", "new AudioContext", "fetch(", "Math.random", "setTimeout", "setInterval"):
        assert forbidden not in text, f"{name} reaches for {forbidden}"


def test_the_band_plays_exactly_what_the_server_lets_a_style_say():
    from improv import grooves

    out = subprocess.run(
        [
            _node(),
            "-e",
            "const b=require('./static/improv/band.js');"
            "console.log(JSON.stringify({bass:b.BASS_RULES,voicings:b.VOICINGS,drums:b.DRUM_INSTRUMENTS}))",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    js = json.loads(out.stdout)
    assert sorted(js["bass"]) == sorted(grooves.BASS_RULES)
    assert sorted(js["voicings"]) == sorted(grooves.VOICINGS)
    assert sorted(js["drums"]) == sorted(grooves.DRUM_INSTRUMENTS)


def test_the_synth_has_a_voice_for_every_drum_the_server_accepts():
    from improv import grooves

    text = (STATIC / "synth.js").read_text(encoding="utf-8")
    for inst in grooves.DRUM_INSTRUMENTS:
        assert re.search(rf"\b{inst}:", text), f"synth.js has no voice for {inst}"


def test_the_spec_says_what_each_rule_and_voicing_does():
    from improv import grooves

    spec = SPEC.read_text(encoding="utf-8")
    assert "Rules in v1" in spec
    for rule in grooves.BASS_RULES:
        assert f"`{rule}`" in spec, f"spec.md does not describe the bass rule {rule}"
    for voicing in grooves.VOICINGS:
        assert f"`{voicing}`" in spec, f"spec.md does not describe the voicing {voicing}"
    for word in ("look-ahead", "swing", "limiter", "bar line"):
        assert word in spec, f"spec.md does not explain {word}"


def test_the_minimum_spans_are_documented_where_the_checker_lives():
    from improv import grooves

    assert grooves.BASS_MIN_SPAN == 12 and grooves.COMP_MIN_SPAN == 19
    model = DATA_MODEL.read_text(encoding="utf-8")
    assert "12 semitones" in model and "19 semitones" in model
    assert "span" in (grooves.__doc__ or "")
