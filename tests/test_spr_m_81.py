"""SPR-M.81 - The only logo on the site is the matazim programme's, in burgundy.

Lital, by mail, 2026-10-31, answering the bot's two questions from SPR-M.79:
"בשלב זה תוריד את הלוגו מה שתכניס זה רק את הלוגו של תכנית מטצים תעשה איתה
בצבע בורגונדי" (REQ-M.213).

Read as: the חמ״ד logo comes off the partners card (and the card with it, since
nothing would be left in it but "וגופים נוספים נפלאים"), and the logo at the top
of every page, עתיד שבילים משותפים, gives way to a מטצים wordmark in burgundy.
"""

import re
from pathlib import Path

import pytest
from PIL import Image

LOGO = Path(__file__).resolve().parent.parent / "static" / "matazim" / "matazim_logo.png"
BURGUNDY = (136, 2, 52)  # the עתיד in the old logo.png, sampled
PAGES = ["/matazim/", "/matazim/about/", "/matazim/register/"]


@pytest.mark.parametrize("path", PAGES)
def test_the_header_logo_is_the_matazim_wordmark(client, db, path):
    html = client.get(path).content.decode()
    brand = re.search(r'<a class="mz-brand".*?</a>', html, re.S).group(0)
    assert 'src="/static/matazim/matazim_logo.png"' in brand
    assert 'alt="מטצים"' in brand
    assert "matazim/logo.png" not in html
    assert "עתיד שבילים משותפים" not in html


def test_the_favicon_is_the_new_logo(client, db):
    html = client.get("/matazim/").content.decode()
    assert re.search(r'<link rel="icon" href="/static/matazim/matazim_logo.png"', html)


def test_the_tag_does_not_repeat_the_word_the_logo_says(client, db):
    html = client.get("/matazim/").content.decode()
    assert '<span class="mz-brand-tag">מנהיגות טכנולוגית צעירה</span>' in html


def test_the_wordmark_is_burgundy():
    im = Image.open(LOGO).convert("RGBA")
    solid = [p[:3] for p in im.getdata() if p[3] == 255]
    assert solid, "the logo has no solid pixels"
    assert all(p == BURGUNDY for p in solid)


@pytest.mark.parametrize("path", ["/matazim/", "/matazim/about/"])
def test_the_partner_logos_and_card_are_off(client, db, path):
    html = client.get(path).content.decode()
    assert "partners/hemed_logo.png" not in html
    assert "partners/atid.svg" not in html
    assert 'class="mz-partners"' not in html
    assert "שותפים מרכזיים לעשייה" not in html


@pytest.mark.parametrize("path", ["/matazim/", "/matazim/about/"])
def test_the_only_logo_on_the_public_pages_is_matazim(client, db, path):
    html = client.get(path).content.decode()
    logos = [t for t in re.findall(r"<img[^>]*>", html) if "logo" in t]
    assert logos and all("matazim_logo.png" in t for t in logos)


def test_the_words_still_name_the_partners(client, db):
    """The logos went, not the partnership: the words in the page stay."""
    html = client.get("/matazim/").content.decode()
    assert "מתנדבי אינטל" in html
