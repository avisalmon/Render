"""Turning a lesson's markdown into the HTML a learner reads.

Extracted 2026-09-13, when מט״צים needed to render the same notes in its own
chrome (REQ-M.126: the trainings are babook's, the experience is מט״צים's).

The alternative was eight lines copied into a second view, and this codebase has
paid for a second copy of one truth twice in a week — RULE-3 exists because of
it. A lesson's notes should look the same wherever they are read, and when
somebody improves this rendering both products should get the improvement.

Nothing here is מט״צים-specific. It is babook's content and babook's rendering;
what differs between the two products is the page around it.
"""

import re

import markdown as md_lib

# Anchors that do not already say where they open. Lesson bodies link out to
# tools and articles, and a learner following one should not lose the lesson.
_BARE_ANCHOR = re.compile(r"<a (?![^>]*\btarget=)")


def render_lesson_notes(markdown_text):
    """Markdown to HTML, with outbound links opening in their own tab.

    Falls back to paragraphs-and-breaks rather than raising: a lesson with
    malformed markdown should still show its text, because the learner cannot
    fix it and losing the words entirely helps nobody.
    """
    source = markdown_text or ""
    if not source.strip():
        return ""

    try:
        html = md_lib.markdown(source, extensions=["fenced_code", "tables", "nl2br"])
    except Exception:  # pragma: no cover - depends on the content
        html = "<p>" + source.replace("\n", "<br>") + "</p>"

    return _BARE_ANCHOR.sub('<a target="_blank" rel="noopener noreferrer" ', html)
