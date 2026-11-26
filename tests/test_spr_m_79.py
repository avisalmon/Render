"""SPR-M.79 - The Atid network logo comes off the partners section.

Lital, by mail, 2026-10-31: "מבקשת אם אפשר להוריד את הלוגו של רשת החינוך עתיד
ולהשאיר בשלב זה רק לוגו של אינטל" (REQ-M.210).

There was never an Intel logo on the site (static/matazim/img/partners/README.md
says why), so the bot took the Atid logo off and asked Avi about the Intel one.
SPR-M.81 (REQ-M.213) then took the חמ״ד logo and the partners card off too, at
Lital's answer; tests/test_spr_m_81.py covers that.
"""

import re

import pytest

PAGES = ["/matazim/", "/matazim/about/"]


@pytest.mark.parametrize("path", PAGES)
def test_no_logo_anywhere_on_the_page_is_atid_s(client, db, path):
    html = client.get(path).content.decode()
    assert "partners/atid.svg" not in html
    assert 'alt="רשת עתיד"' not in html


@pytest.mark.parametrize("path", PAGES)
def test_no_intel_corporate_mark_was_added(client, db, path):
    """Adding Intel's logo waits for Avi: it would claim company sponsorship."""
    html = client.get(path).content.decode()
    images = re.findall(r"<img[^>]*>", html)
    assert not any("intel" in tag.lower() for tag in images)
