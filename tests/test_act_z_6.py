"""ACT-Z.6 — memz: a WhatsApp share button and a QR code in the lobby
(docs/memz/spec.md §4.3, docs/memz/backlog.md). Avi: "When generating a
game code have an option to share like in whatsapp" (the WhatsApp button),
then "Want. Cont." to close the QR-code half of the same long-tracked
gap (F-Z.3.5) while he was at it.
"""

import pytest

from memz import game
from tests.test_memz_screens import PHONE, browser  # noqa: E402, F401 -- the shared phone fixture

pytestmark = [pytest.mark.actz6, pytest.mark.django_db]


def _lobby_world():
    session, host = game.create_session(host_user=None, round_count=3, round_seconds=60, vote_seconds=20)
    game.join_session(session, "שני")
    return session, host


_SPY_ON_WINDOW_OPEN_JS = (
    "window.__openedUrls = []; "
    "window.open = function (url) { window.__openedUrls.push(url); return null; };"
)


@pytest.fixture
def _phone_page(browser, live_server, db):
    pytest.importorskip("playwright.sync_api")
    session, host = _lobby_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
        + _SPY_ON_WINDOW_OPEN_JS
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    yield page, session
    context.close()


def test_the_lobby_offers_a_whatsapp_share_button(_phone_page):
    page, session = _phone_page
    btn = page.locator("[data-whatsapp-share-btn]")
    assert btn.count() == 1


def test_the_whatsapp_button_opens_a_prefilled_invite_with_the_real_code_and_join_link(_phone_page):
    from urllib.parse import parse_qs, unquote, urlsplit

    page, session = _phone_page
    page.click("[data-whatsapp-share-btn]")
    page.wait_for_timeout(100)
    opened = page.evaluate("window.__openedUrls")
    assert len(opened) == 1

    parts = urlsplit(opened[0])
    assert parts.scheme == "https" and parts.netloc == "wa.me"
    text = unquote(parse_qs(parts.query)["text"][0])
    assert session.code in text
    assert f"/memz/join/{session.code}/" in text


def test_the_big_screen_lobby_never_offers_the_whatsapp_button(browser, live_server, db):
    """No phone is attached to the shared TV browser to open WhatsApp
    from (spec §4.10) -- the button is host/guest-lobby only."""
    pytest.importorskip("playwright.sync_api")
    session, _host = _lobby_world()
    context = browser.new_context(viewport=PHONE)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/screen/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-lobby"
    assert page.locator("[data-whatsapp-share-btn]").count() == 0
    context.close()


# --------------------------------------------------------------- the QR code


def test_the_qr_endpoint_returns_a_real_png_of_the_join_url(client):
    session, _host = _lobby_world()
    resp = client.get(f"/memz/s/{session.code}/qr.png")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"   # the real PNG magic bytes, not just a 200


def test_the_qr_endpoint_404s_for_a_code_that_does_not_exist(client):
    resp = client.get("/memz/s/NOPE1234/qr.png")
    assert resp.status_code == 404


def test_the_qr_code_renders_in_both_the_player_lobby_and_the_big_screen(_phone_page, browser, live_server, db):
    page, session = _phone_page
    player_img = page.locator("img.memz-qr")
    assert player_img.count() == 1
    assert f"/memz/s/{session.code}/qr.png" in player_img.get_attribute("src")
    # A broken <img> still has a naturalWidth of 0; a real decoded PNG doesn't.
    assert page.evaluate("document.querySelector('img.memz-qr').naturalWidth") > 0

    screen_context = browser.new_context(viewport=PHONE)
    screen_page = screen_context.new_page()
    screen_page.goto(f"{live_server.url}/memz/s/{session.code}/screen/", wait_until="domcontentloaded")
    screen_page.wait_for_timeout(400)
    screen_img = screen_page.locator("img.memz-qr")
    assert screen_img.count() == 1
    assert screen_page.evaluate("document.querySelector('img.memz-qr').naturalWidth") > 0
    screen_context.close()
