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


# ACT-Z.15 (2026-09-19, Avi: "the share game on whatsapp is not working
# well"): the button used to be a window.open() on a wa.me URL, which an
# installed PWA and several phone browsers block or bounce to wa.me's
# "continue to chat" page. It is now a real <a href> to wa.me (a universal
# link WhatsApp claims), upgraded on click to the phone's own share sheet
# wherever `navigator.share` exists. Two spies: one records what the share
# sheet was handed, the other stands in for a browser with no share sheet.
_SPY_ON_SHARE_JS = (
    "window.__shared = []; "
    "navigator.share = function (data) { window.__shared.push(data); return Promise.resolve(); };"
)
_NO_SHARE_SHEET_JS = "Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });"


def _lobby_page(browser, live_server, extra_init_js):
    session, host = _lobby_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token) + extra_init_js
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    return context, page, session


@pytest.fixture
def _phone_page(browser, live_server, db):
    pytest.importorskip("playwright.sync_api")
    context, page, session = _lobby_page(browser, live_server, _SPY_ON_SHARE_JS)
    yield page, session
    context.close()


def _assert_is_a_real_invite(url_text, session):
    from urllib.parse import parse_qs, unquote, urlsplit

    parts = urlsplit(url_text)
    assert parts.scheme == "https" and parts.netloc == "wa.me"
    text = unquote(parse_qs(parts.query)["text"][0])
    assert session.code in text
    assert f"/memz/join/{session.code}/" in text


def test_the_lobby_offers_a_whatsapp_share_button(_phone_page):
    page, session = _phone_page
    btn = page.locator("[data-whatsapp-share-btn]")
    assert btn.count() == 1


def test_the_whatsapp_button_is_a_real_link_to_a_prefilled_invite(_phone_page):
    """The anchor itself carries the invite, so it works with no script
    at all and inside an installed PWA where a popup would be blocked."""
    page, session = _phone_page
    href = page.locator("[data-whatsapp-share-btn]").get_attribute("href")
    assert page.locator("[data-whatsapp-share-btn]").evaluate("el => el.tagName") == "A"
    _assert_is_a_real_invite(href, session)


def test_on_a_phone_with_a_share_sheet_the_button_opens_it_with_the_join_link(_phone_page):
    page, session = _phone_page
    page.click("[data-whatsapp-share-btn]")
    page.wait_for_timeout(150)
    shared = page.evaluate("window.__shared")
    assert len(shared) == 1, "the native share sheet was not opened"
    assert shared[0]["url"].endswith(f"/memz/join/{session.code}/")
    assert session.code in shared[0]["text"]
    # And it did not *also* navigate away (the anchor's default was suppressed).
    assert f"/memz/s/{session.code}/" in page.url


def test_without_a_share_sheet_the_link_simply_is_the_invite(browser, live_server, db):
    pytest.importorskip("playwright.sync_api")
    context, page, session = _lobby_page(browser, live_server, _NO_SHARE_SHEET_JS)
    try:
        assert page.evaluate("typeof navigator.share") == "undefined"
        href = page.locator("[data-whatsapp-share-btn]").get_attribute("href")
        _assert_is_a_real_invite(href, session)
        assert page.locator("[data-whatsapp-share-btn]").get_attribute("target") == "_blank"
    finally:
        context.close()


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
    # SPR-W.4: the TV's own lobby markup (Rule 4.10.1). Same requirement:
    # the code on the wall is useless without something to scan.
    screen_img = screen_page.locator("img.memz-tv-qr")
    assert screen_img.count() == 1
    assert screen_page.evaluate("document.querySelector('img.memz-tv-qr').naturalWidth") > 0
    screen_context.close()
