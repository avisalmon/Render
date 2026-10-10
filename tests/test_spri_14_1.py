"""SPR-I.14.1 improv: hearing the piano through a microphone, the pitch reading under Node.

The detector (static/improv/pitch.js) is pure: it is proved with made notes in tests/js/spri141.test.js. This file
runs that suite from pytest so the marker finds it.

Traces: spec ch. 13, backlog SPR-I.14.1.
"""

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.spri141


def test_the_pitch_reading_passes_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run([node, "--test", "tests/js/spri141.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]
