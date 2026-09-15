"""SPR-M.41 — what a full UX review measured.

Every screen walked as every role in a real browser, at 390px and at 1440px,
measuring rather than looking: effective tap area by probing elementFromPoint
outward from each control, contrast against the resolved background, overflow
by finding the elements that actually stick out, queries per screen.

Most of it came back clean. These are the tests for the findings that did not,
and they are deliberately static checks over the source rather than rendered
pages: every one of these defects is a literal in a template or a constant in a
module, and a fixture elaborate enough to render the screen would test less
while breaking more often.

The one that mattered most was F-M.41.1. `my_path.html` had two panels headed
הפרקטיקום שלי, and the first one listed הדרכות with lesson progress. A member
reading the screen whose whole job is telling them where they are saw
"הפרקטיקום שלי 23/34" above their Scratch lessons, naming a stage they had not
started.

Traces: REQ-M.76, REQ-M.106, REQ-M.130, REQ-M.139, Rule 3.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.sprm41

REPO = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates" / "matazim"
APP = REPO / "matazim"


def _read(path):
    return path.read_text(encoding="utf-8")


def _headings(html, level="h2"):
    """The literal heading texts in a template, tags and tags' contents stripped."""
    out = []
    for raw in re.findall(rf"<{level}[^>]*>(.*?)</{level}>", html, re.S):
        # Drop the template tags first, then the markup around them, so a count
        # badge like {{ done }}/{{ total }} does not leave its slash behind and
        # turn into part of the heading's words.
        text = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", raw, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = " ".join(text.split()).strip(" /·-|:")
        if text:
            out.append(text)
    return out


def test_no_screen_says_the_same_heading_twice():
    """F-M.41.1. Two panels named the same thing is two panels a member cannot
    tell apart, and here the first one named the wrong stage of the programme.

    Swept over every template rather than asserted about the one that was
    wrong, because the defect is a shape rather than a place: the next screen
    to grow a second panel should fail this too."""
    offenders = {}
    for path in sorted(TEMPLATES.glob("*.html")):
        heads = _headings(_read(path))
        seen, dupes = set(), set()
        for head in heads:
            if head in seen:
                dupes.add(head)
            seen.add(head)
        if dupes:
            offenders[path.name] = sorted(dupes)
    assert not offenders, f"the same heading twice on one screen: {offenders}"


def test_the_training_panel_says_what_it_lists():
    """F-M.41.1, the specific one. The panel that lists courses is named for
    them, and the practicum panel keeps its own name."""
    html = _read(TEMPLATES / "my_path.html")
    heads = _headings(html)
    assert "ההדרכות שלי" in heads
    assert "הפרקטיקום שלי" in heads


def test_nothing_a_member_reads_says_kursim():
    """F-M.41.2. `assess.py` records the decision itself: "הדרכות", לא
    "קורסים" (החלטה של אבי, 13.9.26). The nav and the page titles honoured it
    and three strings did not, one of them on the public home page inside a
    card whose own second line said הדרכות.

    `assess.py` is excluded because it is where the rule is written down, and
    `model_script.py` because it matches phrases a person typed at us rather
    than printing any."""
    exclude = {"assess.py", "model_script.py"}
    offenders = []
    for path in sorted(APP.glob("*.py")) + sorted(TEMPLATES.glob("*.html")):
        if path.name in exclude:
            continue
        for number, line in enumerate(_read(path).splitlines(), start=1):
            if "קורס" in line:
                offenders.append(f"{path.name}:{number}: {line.strip()[:70]}")
    assert not offenders, "קורסים in copy a member reads:\n" + "\n".join(offenders)


def test_not_yet_is_never_a_bare_bullet():
    """F-M.41.6. The unmet state was `·` painted in .mz-check's teal, the same
    colour as the ✓ beside it, so the two were told apart by glyph alone. And
    `·` is a bullet everywhere else here, in the privacy and terms lists, so on
    a checklist it read as decoration rather than as something outstanding."""
    for name in ("my_path.html", "student.html"):
        html = _read(TEMPLATES / name)
        assert "mz-check-todo" in html, f"{name} lost the unmet-state marker"
        assert not re.search(r'class="mz-check">\{%\s*if', html), (
            f"{name} is back to one class deciding the glyph inline"
        )


def test_every_state_marker_carries_a_word():
    """F-M.41.6, the half that assistive technology needs. A ✓ and a ○ are
    punctuation to a screen reader, so the word rides along in .mz-sr."""
    css = _read(REPO / "static" / "matazim" / "matazim.css")
    assert ".mz-sr" in css, "the visually-hidden utility is gone"
    for name in ("my_path.html", "student.html"):
        html = _read(TEMPLATES / name)
        markers = len(re.findall(r'class="mz-check(?:-todo)?"', html))
        words = len(re.findall(r'class="mz-sr"', html))
        assert words >= markers, f"{name}: {markers} markers but {words} words"


def test_every_copy_field_can_be_named_out_loud():
    """F-M.41.7. A readonly input holding a join link announced itself as a
    blank edit field. The prose beside it explains what it is to somebody who
    can see the prose."""
    missing = []
    for path in sorted(TEMPLATES.glob("*.html")):
        html = _read(path)
        for tag in re.findall(r"<input[^>]*mz-copy[^>]*>", html, re.S):
            if "aria-label" not in tag:
                missing.append(f"{path.name}: {' '.join(tag.split())[:70]}")
    assert not missing, "copy fields with no accessible name:\n" + "\n".join(missing)


def test_prose_has_a_reading_measure():
    """F-M.41.3. Measured at 1440px, 18 paragraphs across nine screens ran
    1088px wide, about 136 characters a line, against the 45 to 90 that is
    comfortable. The product had solved this twice already, in .mz-legal and
    .mz-hero-text, and never applied it to the panels."""
    css = _read(REPO / "static" / "matazim" / "matazim.css")
    block = re.search(r"\.mz-page-head > p,(.*?)\}", css, re.S)
    assert block, "the measure rule for panel prose is gone"
    assert "max-width" in block.group(1)
    for selector in (".mz-panel > p", ".mz-path-body > p"):
        assert selector in block.group(0), f"{selector} no longer gets a measure"


def test_the_lamp_keeps_its_word_on_a_phone():
    """F-M.41.5. The label used to be display:none under 640px, leaving a 52px
    circle. The lamp is deliberately not a nav item (REQ-M.106), so it is the
    only entrance to the improvement loop, and a touch screen has no hover to
    reveal the title."""
    css = _read(REPO / "static" / "matazim" / "matazim.css")
    assert ".mz-lamp-text" in css, "the lamp's label rule is gone entirely"
    # Anywhere in the file, not inside the first 640px block: there are several
    # of those, and scoping to one of them is how this test passed while the
    # label was hidden by another.
    hidden = re.search(r"\.mz-lamp-text[^{}]*\{[^}]*display:\s*none", css)
    assert not hidden, "the lamp is an unlabelled circle on phones again"
