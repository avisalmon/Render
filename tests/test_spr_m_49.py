"""SPR-M.49 — מצב לילה, from two requests in the queue.

The first two requests the improvement loop ever carried through to a sprint,
both filed by Avi on 13.09 and approved the same day:

  #1  "להוסיף מצב לילה ויום"
  #2  "מצב לילה אוטומתי לפי שעות היום"

Together they are one feature with two halves: a palette, and a clock that
chooses it. A third state falls out of them, which is a person overriding the
clock, and that is the one the requests do not mention and the product needs.

**The load-bearing test here is `test_every_colour_token_has_a_night_value`.**
Night mode is a token swap, so it holds for every screen in the product,
including screens nobody has written yet. That property survives exactly as long
as nobody adds a colour token and forgets its dark twin, which is a mistake that
shows up as one unreadable badge on one screen months later. The test reads both
blocks out of the stylesheet and compares them, so the omission fails here
instead.

Traces: REQ-M.5 (the product is read on a phone), and the queue.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.sprm49

REPO = pathlib.Path(__file__).resolve().parent.parent
CSS = (REPO / "static" / "matazim" / "matazim.css").read_text(encoding="utf-8")
BASE = (REPO / "templates" / "matazim" / "base.html").read_text(encoding="utf-8")


def _tokens(block_start):
    """The --mz-* names defined in one block of the stylesheet."""
    i = CSS.index(block_start)
    j = CSS.index("\n}", i)
    return set(re.findall(r"(--mz-[a-z0-9-]+)\s*:", CSS[i:j]))


def test_there_is_a_night_palette_at_all():
    assert ':root[data-theme="dark"]' in CSS


def test_every_colour_token_has_a_night_value():
    """A token with no dark twin is a colour that keeps its daylight value on a
    dark screen, which is how one badge ends up dark green on dark green.

    The exemptions are the tokens that are not colours: a radius and a width and
    a font stack look the same at midnight.
    """
    NOT_A_COLOUR = {"--mz-radius", "--mz-radius-sm", "--mz-container", "--mz-font"}

    light = _tokens(":root {") - NOT_A_COLOUR
    dark = _tokens(':root[data-theme="dark"] {')

    missing = sorted(light - dark)
    assert not missing, (
        "these colours keep their daylight value in night mode:\n  "
        + "\n  ".join(missing)
    )


def test_the_choice_is_made_before_the_page_paints():
    """In the head, inline, above the content.

    If the theme is decided after the stylesheet has painted, somebody opening
    the site at night gets a white flash in the face first. That flash is the
    single most common reason people distrust a night mode, and it cannot be
    fixed further down the page.
    """
    head = BASE[: BASE.index("</head>")]
    # The specific call, not the words and not any call. Two earlier versions of
    # this test passed on a head that had lost it: the first because the phrase
    # survived in a comment, the second because the once-a-minute timer contains
    # the same `setAttribute` and looks identical to a substring search. What
    # makes this one the pre-paint decision is that it runs `decide()` inline.
    assert 'setAttribute("data-theme", decide())' in head, (
        "nothing decides the theme before the page paints"
    )
    assert "localStorage" in head, "the override has to be read before paint too"


def test_the_clock_decides_when_nobody_has_chosen():
    """Request #2: automatic, by the hour."""
    head = BASE[: BASE.index("</head>")]
    assert "NIGHT_FROM" in head and "NIGHT_UNTIL" in head
    assert "getHours" in head, "the reader's own clock, not the server's"


def test_a_persons_choice_outranks_the_clock():
    """Request #1: a switch. Somebody who turned the light on at midnight meant
    it, and the clock must stop arguing with them."""
    assert 'localStorage.setItem("mz-theme"' in BASE
    head = BASE[: BASE.index("</head>")]
    assert re.search(r'saved\s*===\s*"dark"', head), "a saved choice is read first"


def test_the_switch_is_reachable_and_says_what_it_does():
    """SPR-M.24 cut the menu to six items deliberately, so this is not a menu
    item. It is beside the bell, and it is shown to visitors too."""
    assert 'id="mzTheme"' in BASE
    assert "mz-theme-btn" in CSS
    assert "aria-label=" in BASE[BASE.index('id="mzTheme"') - 200: BASE.index('id="mzTheme"') + 200]
    # Outside the {% if user.is_authenticated %} that wraps the bell.
    button_at = BASE.index('id="mzTheme"')
    auth_at = BASE.index("{% if user.is_authenticated %}", BASE.index("mz-header-action"))
    assert button_at < auth_at, "a visitor reading at night is reading at night too"


@pytest.mark.parametrize("hardcoded", ["background: #fff;"])
def test_the_surfaces_that_must_swap_no_longer_paint_themselves_white(hardcoded):
    """`.mz-file` and `.mz-field input` painted a fixed white, so a form field
    was a white box in the middle of a dark page. Found by measuring, not by
    reading: the contrast sweep put one at 2.48:1."""
    for rule in (".mz-file {", ".mz-field input {"):
        i = CSS.index(rule)
        assert hardcoded not in CSS[i: CSS.index("}", i)], f"{rule} still paints itself white"


def test_the_tags_follow_the_palette():
    """These carried their own hardcoded ink, so a done tag stayed dark green on
    what became a dark green ground: 2.18:1."""
    i = CSS.index(".mz-tag-done {")
    block = CSS[i: CSS.index("}", i)]
    assert "var(--mz-tag-done-ink)" in block
    assert "#0a6b58" not in block


def test_links_have_a_colour_of_their_own():
    """Purple is an excellent button and a poor piece of text on a dark ground.
    It measured 2.65:1 as a link, and every link in the product used it."""
    assert "a { color: var(--mz-link);" in CSS
    assert "--mz-link" in _tokens(":root {")
    assert "--mz-link" in _tokens(':root[data-theme="dark"] {')
