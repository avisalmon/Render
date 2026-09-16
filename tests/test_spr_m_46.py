"""SPR-M.46 — the privacy page says what the product actually does.

SPR-M.45 found that opening a lesson reached ten third-party hosts while the
privacy page said, in bold, "אין כאן גוגל אנליטיקס, אין פיקסל של פייסבוק, ואין
שום סקריפט של חברה אחרת", and used that to explain why the site asks for no
cookie consent. The code half was fixed there: the player is built on a click,
so nothing is sent until a member chooses to watch.

This is the other half, which was Avi's to approve and he did on 2026-09-16.
The paragraph now names the video service, says nothing is sent before the
click, and keeps the cookie sentence, which was measured and is still true:
zero third-party cookies before the click and after sixteen seconds of playing.

**The test that matters here is the last one.** Naming Bunny today fixes today.
The way this goes wrong again is somebody embedding a map, a font, an analytics
snippet or a chat widget in a מט״צים template a year from now, with the privacy
page still describing a product that had one external service. So the check is
not "does it mention Bunny": it reads every external host out of the templates
and fails on any whose owner the privacy page does not name.

Traces: REQ-M.81, §4.10.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.sprm46

REPO = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates" / "matazim"
PRIVACY = TEMPLATES / "privacy.html"

# Who owns a host, in the words a reader would recognise. A host that is not in
# here is not "assumed fine": the sweep below fails on it, which is the point.
OWNERS = {
    "mediadelivery.net": "Bunny",
    "b-cdn.net": "Bunny",
    "bunny.net": "Bunny",
    "bunnyinfra.net": "Bunny",
    # Found by this very test, on its first run: the entrance test's 3D view
    # and the staff target bank both pull three.js from here, eagerly, and
    # nobody had written it down anywhere.
    "jsdelivr.net": "jsDelivr",
}

# Ours, or a placeholder, rather than another company.
NOT_A_THIRD_PARTY = ("babook.co.il", "127.0.0.1", "localhost", "example.com",
                     "scratch.mit.edu", "w3.org", "schema.org")


def _privacy_text():
    """The page as a reader sees it.

    Template comments are stripped: this file explains itself at length, and
    quoting the old false sentence inside a comment about why it was false must
    not read as the page still making the claim.
    """
    raw = PRIVACY.read_text(encoding="utf-8")
    return re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", raw, flags=re.S)


def test_the_page_names_the_video_service():
    text = _privacy_text()
    assert "Bunny" in text, "the lessons play from somewhere and the page does not say where"
    assert "וידאו" in text


def test_the_page_names_the_graphics_library_too():
    """Found by the sweep below rather than by anybody noticing.

    The entrance test's 3D view loads three.js from jsDelivr the moment the
    screen opens, which is the first thing a fourteen-year-old does here."""
    text = _privacy_text()
    assert "jsDelivr" in text
    assert "three.js" in text


def test_the_blanket_claim_is_gone():
    """"ואין שום סקריפט של חברה אחרת" was false on the busiest screen in the
    product. It may still be said about the screens where it is true, but never
    about the site as a whole."""
    text = _privacy_text()
    for match in re.finditer(r"אין שום סקריפט של חברה אחרת", text):
        before = text[max(0, match.start() - 120):match.start()]
        assert "בכל שאר המסכים" in before, (
            "the page claims no third-party scripts anywhere, which the lesson pages break"
        )


def test_the_page_says_nothing_is_sent_before_the_click():
    """The thing that makes the trade fair, and the reason the sentence above
    can be qualified rather than simply deleted."""
    text = _privacy_text()
    assert "לא נשלח לשם כלום" in text


def test_the_cookie_sentence_still_stands():
    """Measured, not assumed: zero third-party cookies before the click and
    after sixteen seconds of playback."""
    text = _privacy_text()
    assert "עוגייה" in text
    assert "באנר" in text


def test_every_outside_company_in_the_markup_is_named_on_the_privacy_page():
    """The tripwire for the next one.

    Reads every external host out of the מט״צים templates and requires the
    privacy page to name whoever owns it. A future embed, a font, a widget or
    an analytics snippet fails this until somebody writes the sentence.
    """
    hosts = set()
    for template in sorted(TEMPLATES.glob("*.html")):
        for url in re.findall(r"https?://([A-Za-z0-9.-]+)", template.read_text(encoding="utf-8")):
            if any(url.endswith(ours) or url == ours for ours in NOT_A_THIRD_PARTY):
                continue
            hosts.add(url)

    undisclosed = []
    for host in sorted(hosts):
        owner = next((name for suffix, name in OWNERS.items() if host.endswith(suffix)), None)
        if owner is None:
            undisclosed.append(f"{host} (nobody has said who this is)")
        elif owner not in _privacy_text():
            undisclosed.append(f"{host} -> {owner}, not named on the privacy page")

    assert not undisclosed, (
        "מט״צים contacts companies the privacy page does not mention:\n  "
        + "\n  ".join(undisclosed)
    )
