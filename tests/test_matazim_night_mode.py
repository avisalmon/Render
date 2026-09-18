"""The screen contract again, in the dark.

SPR-M.49 added מצב לילה as a token swap, which is what makes it hold on every
screen including ones nobody has written yet. "Holds on every screen" is a claim,
and this is the only thing that checks it: the same catalogue of screens and
states, rendered with the dark palette pinned.

It earned its place immediately. The sprint's own contrast sweep covered eight
screens and reported zero failures; this one, covering the whole catalogue,
found `.mz-btn-done` at 2.18:1 on a state the sweep never opened. That gap
between "the screens I thought to check" and "the screens that exist" is the
reason the screen contract was written in the first place.

Running it is one line, because the contract already knows how to be pointed at
a palette:

    MZ_THEME=dark pytest tests/test_screen_contract.py -m screens

This module makes that run part of the suite rather than something somebody
remembers to do.
"""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.sprm49


@pytest.mark.slow
def test_every_screen_in_the_catalogue_survives_the_dark_palette():
    """The whole contract, re-run with MZ_THEME=dark.

    A subprocess rather than a fixture, because the theme is read once when the
    module loads and pytest has already imported it by the time a fixture could
    change anything. The cost is one extra process; the alternative is a flag
    threaded through every page-opening call for the sake of a single run.
    """
    env = dict(os.environ, MZ_THEME="dark")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_screen_contract.py",
         "-m", "screens", "-q", "--no-header", "-p", "no:cacheprovider"],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.strip().splitlines()[-25:])
        pytest.fail("the screen contract fails in night mode:\n" + tail)
