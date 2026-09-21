"""A guard over every SensorLab template, not one screen at a time.

`{# ... #}` is a **single-line** comment in Django. Written across two
lines it does not comment anything out — the remainder renders as body text,
mid-page, looking like the app has lost its mind.

This app shipped that bug three times: SL-A1 (the shell), SL-F2 (the capture
screen) and SL-G1 (the analysis screen). Each was caught by a render
assertion on *that* screen — which means it was only ever caught where
somebody had already thought to look, and a new screen got through every
time. So this reads the source of every template instead. One cheap test a
new screen cannot outrun.

**And it strips comments before it counts anything**, because the first
version did not and immediately failed on a sentence inside a comment that
mentioned `{%` `comment` `%}`. That is the fourth time this project has
written a guard that trips over its own documentation — SL-A4's token guard
matched the comment explaining it, SL-C1's raw-API guard matched the comment
explaining *that*, and two guards in SL-F2 matched the JavaScript they were
checking. The rule, now stated where the next one will be written:
**anything that scans source must first remove the source that is about the
rule.**
"""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.sprsl20]

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "sensorlab"

#: Django's comment blocks do not nest, so a non-greedy sweep is exact.
COMMENT_BLOCK = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.S)


def _templates():
    found = sorted(TEMPLATES.rglob("*.html"))
    assert found, f"no templates found under {TEMPLATES}"
    return found


def _without_comments(text):
    """The template minus its comment blocks — see the module docstring."""
    return COMMENT_BLOCK.sub("", text)


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_no_hash_comment_spans_more_than_one_line(path):
    code = _without_comments(path.read_text(encoding="utf-8"))
    for number, line in enumerate(code.splitlines(), start=1):
        assert line.count("{#") == line.count("#}"), (
            f"{path.name}: a `{{#` comment is opened and not closed on the same "
            f"line. Django's hash comment is single-line, so everything after it "
            f"renders into the page. Use a comment block instead.\n  {line.strip()}"
        )


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_every_comment_block_is_closed(path):
    text = path.read_text(encoding="utf-8")
    remaining = _without_comments(text)
    assert "{% comment" not in remaining.replace("{% comment %}`", ""), (
        f"{path.name}: a comment block is opened and never closed."
    )


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_every_template_closes_its_blocks(path):
    """The cheap structural check that catches a truncated edit.

    Not a parser — it counts openers against closers for the tags this app
    uses, outside comments. Enough to catch a half-finished change, and it
    costs nothing.
    """
    code = _without_comments(path.read_text(encoding="utf-8"))
    for tag in ("if", "for", "block", "with"):
        opens = len(re.findall(r"\{%\s*" + tag + r"[\s%]", code))
        closes = len(re.findall(r"\{%\s*end" + tag + r"\s*%\}", code))
        assert opens == closes, (
            f"{path.name}: {opens} `{{% {tag} %}}` against {closes} "
            f"`{{% end{tag} %}}`"
        )
