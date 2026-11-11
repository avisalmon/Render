"""The official apps' shared "more on babook" menu (Avi, 2026-11-11).

Every official app shows it, listing every other official app and not
itself; מט״צים, deliberately not official, shows none. Adding an app to
`mysite/more_on_babook.OFFICIAL` without its menu fails here, which is the
point: "a new official app gets a link in every app" cannot be forgotten.
"""

import re

import pytest
from django.contrib.auth.models import User

from mysite.more_on_babook import OFFICIAL

# One page in each official app where its own frame is drawn. babook itself
# (courses) is listed in the menu but draws none: its drawer already lists the
# apps from the portal registry, and its own rules (tests/test_spr_13_5.py,
# test_smoke.py) keep that the one list there.
NO_MENU = {"courses"}
PAGES = {
    "books": "/books/login/",
    "design3d": "/design3d/login/",
    "blackjack": "/blackjack/",
    "bkm": "/bkm/",
    "gallery": "/gallery/",
}


@pytest.fixture
def signed_in(client, db, settings):
    settings.OPENAI_API_KEY = ""  # methodology 26
    user = User.objects.create_user("mob@example.com", "mob@example.com", "mob-pass-8812")
    client.force_login(user)
    return client


def _menu(html):
    m = re.search(r'<(details|div)[^>]*data-more-on-babook[^>]*>(.*?)</\1>', html, re.S)
    return re.findall(r'href="([^"]+)"', m.group(2)) if m else None


def test_every_official_app_has_a_page_here():
    assert set(PAGES) | NO_MENU == {a.slug for a in OFFICIAL}


@pytest.mark.parametrize("slug", sorted(PAGES))
def test_every_official_app_shows_every_other(signed_in, slug):
    client = signed_in
    if slug in ("books", "design3d"):
        client.logout()  # their sign-in page is open to everybody and uses the app's own frame
    html = client.get(PAGES[slug], follow=True).content.decode()
    links = _menu(html)
    assert links is not None, f"{slug}: no 'more on babook' menu"
    own = next(a.path for a in OFFICIAL if a.slug == slug)
    assert links == [a.path for a in OFFICIAL if a.path != own], slug


def test_matazim_is_its_own_and_has_no_menu(signed_in):
    html = signed_in.get("/matazim/", follow=True).content.decode()
    assert "data-more-on-babook" not in html
    assert "/matazim/" not in [a.path for a in OFFICIAL]
