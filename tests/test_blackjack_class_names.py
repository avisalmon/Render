"""Every class this app's markup uses is a class this app's stylesheet styles.

**This test exists because I invented two class names that styled nothing.**
`bj-btn-quiet` was meant to make a second-rank button quieter, and
`bj-lede` to set an intro paragraph. Neither existed in the stylesheet, so
three gold buttons shouted equally on the share screen and one of them closes a
link for good. Nothing failed. A class that does not exist is not an error in
CSS, it is silence, and no test that reads HTML can tell the difference between
a styled element and an unstyled one.

It is the same family as the `.bj-card` collision that left the front page
broken for four sprints: CSS fails quietly, so the guards have to be structural.

A few names are deliberately unstyled, used as hooks for JavaScript or for
tests. They are listed here by name, so leaving one unstyled is a decision
somebody wrote down rather than something that happened.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.bjclasses

# Named for meaning, styled by their parent. Each one has been looked at.
UNSTYLED_ON_PURPOSE = {
    "bj-body-public": "the public shell; the look comes from .bj-body",
    "bj-hand-what": "a span inside a styled .bj-hand-row",
    "bj-note-text": "a span inside a styled note list item",
    "bj-worst-hand": "a span inside a styled row on the progress screen",
    "bj-redeem-form": "a form whose controls are styled individually",
}


def _defined():
    css = pathlib.Path("static/blackjack/blackjack.css").read_text(encoding="utf-8")
    return set(re.findall(r"\.(bj-[a-z0-9-]+)", css))


def _used():
    found = {}
    for path in sorted(pathlib.Path("templates/blackjack").glob("*.html")):
        for match in re.finditer(r'class="([^"]*)"', path.read_text(encoding="utf-8")):
            for word in match.group(1).split():
                # Classes assembled from template variables are not names.
                if word.startswith("bj-") and "{" not in word:
                    found.setdefault(word, path.name)
    for path in sorted(pathlib.Path("static/blackjack").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"""["'`]([^"'`]*bj-[a-z0-9 -]*)["'`]""", text):
            for word in match.group(1).split():
                if word.startswith("bj-"):
                    found.setdefault(word, path.name)
    return found


def test_no_markup_uses_a_class_the_stylesheet_never_heard_of():
    defined = _defined()
    orphans = {
        name: where
        for name, where in _used().items()
        if name not in defined and name not in UNSTYLED_ON_PURPOSE
    }
    assert not orphans, (
        "classes that style nothing:\n"
        + "\n".join(f"  {name} (in {where})" for name, where in sorted(orphans.items()))
    )


def test_the_deliberate_exceptions_are_still_real():
    """So the list cannot quietly become a parking space for dead names."""
    used = _used()
    defined = _defined()
    for name in UNSTYLED_ON_PURPOSE:
        assert name in used, f"{name} is excused but no longer used anywhere"
        assert name not in defined, f"{name} is styled now and does not need excusing"
