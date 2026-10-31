"""SPR-M.79 - The Atid network logo comes off the partners section.

Lital, by mail, 2026-10-31: "מבקשת אם אפשר להוריד את הלוגו של רשת החינוך עתיד
ולהשאיר בשלב זה רק לוגו של אינטל" (REQ-M.210).

There was never an Intel logo on the site (static/matazim/img/partners/README.md
says why), so the bot took the Atid logo off and asked Avi about the Intel one.
"""

import re

import pytest

PAGES = ["/matazim/", "/matazim/about/"]


def _partners(html):
    """The partners section alone, so a logo elsewhere on the page does not count."""
    match = re.search(r'<section class="mz-partners".*?</section>', html, re.S)
    assert match, "the partners section is missing"
    return match.group(0)


@pytest.mark.parametrize("path", PAGES)
def test_the_atid_logo_is_gone_from_the_partners(client, db, path):
    section = _partners(client.get(path).content.decode())
    assert "partners/atid.svg" not in section
    assert 'alt="רשת עתיד"' not in section


@pytest.mark.parametrize("path", PAGES)
def test_the_section_keeps_its_title_and_the_other_logo(client, db, path):
    section = _partners(client.get(path).content.decode())
    assert "שותפים מרכזיים לעשייה" in section
    assert "partners/hemed_logo.png" in section
    assert "וגופים נוספים נפלאים" in section


@pytest.mark.parametrize("path", PAGES)
def test_no_logo_anywhere_on_the_page_is_atid_s(client, db, path):
    html = client.get(path).content.decode()
    assert "partners/atid.svg" not in html


@pytest.mark.parametrize("path", PAGES)
def test_no_intel_corporate_mark_was_added(client, db, path):
    """Adding Intel's logo waits for Avi: it would claim company sponsorship."""
    section = _partners(client.get(path).content.decode())
    images = re.findall(r"<img[^>]*>", section)
    assert len(images) == 1
    assert not any("intel" in tag.lower() for tag in images)
