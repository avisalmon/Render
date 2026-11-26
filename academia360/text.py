"""Text helpers for Academia360's pages.

`render_markdown` turns a row's markdown (the guideline sections, later the
letters' shared sections) into HTML and then cleans it: python-markdown
passes raw HTML through, so a <script> in a row would otherwise run for
every reader. nh3 keeps the harmless tags only (same rule as the forum,
security review 2026-10-24).
"""

import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

_EXTENSIONS = ["tables", "sane_lists"]
_BLOCK_START = re.compile(r"(?<=\S)[ \t]*\n(?=(?:[-*] |\d+\. |#{1,6} ))")
_LIST_LINE = re.compile(r"^(?:[-*] |\d+\. )")


def _loosen(text):
    """Documents written by hand glue a list or a heading to the paragraph
    before it (a line break, no blank line); markdown then prints the dashes
    as text. A blank line is put before a list or heading that follows a
    line of prose; consecutive list items are left as they are."""
    out = []
    lines = (text or "").replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if i and _LIST_LINE.match(line.strip()) or line.startswith("#"):
            prev = lines[i - 1].strip() if i else ""
            if prev and not _LIST_LINE.match(prev) and not prev.startswith("#") and not prev.startswith("|"):
                out.append("")
        out.append(line)
    return "\n".join(out)


def render_markdown(text):
    import markdown
    import nh3

    try:
        html = markdown.markdown(_loosen(text), extensions=_EXTENSIONS)
    except Exception:
        html = "<p>" + escape(text or "").replace("\n", "<br>") + "</p>"
    return mark_safe(nh3.clean(html))


def slug_anchor(prefix, order):
    """A stable in-page anchor for a numbered section."""
    return f"{prefix}-{int(order) + 1}"
