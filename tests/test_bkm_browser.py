"""bkm in a real browser.

`test_a_visitor_signs_in_from_a_card_and_starts_a_conversation` walks the
newcomer's road (methodology 40): the wall, a click on a card, the sign-in
window, back on that card, like and star, its page, a question and a reply.
The others measure what HTML cannot: the phone notice and its dismissal
(REQ-B.4), and that no page slides sideways (methodology 29, 34).
"""

import os

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.bkm

PASSWORD = "bkm-browser-5521"
OVERFLOW = "(w) => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - w"
SHOTS = os.environ.get("BKM_SHOTS")


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chrome = pw.chromium.launch()
            yield chrome
            chrome.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def world(transactional_db, settings, tmp_path):
    from django.contrib.auth.models import User
    from django.core.management import call_command

    from bkm.models import Bkm, Comment, Reader

    settings.MEDIA_ROOT = tmp_path
    # A transactional test empties the tables, data migrations included.
    if not Bkm.objects.exists():
        from importlib import import_module

        first = import_module("bkm.migrations.0002_first_bkms").FIRST
        for i, (slug, name, tagline, repo, page) in enumerate(first):
            Bkm.objects.create(slug=slug, name=name, tagline=tagline, repo_url=repo, page_url=page, position=(i + 1) * 10)
    call_command("seed_bkm", stdout=open(os.devnull, "w"))
    avi = User.objects.create_superuser("avi@example.com", "avi@example.com", PASSWORD, first_name="Avi")
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PASSWORD, first_name="Dana")
    reader = Reader.objects.create(user=dana, display_name="Dana Levi")
    Comment.objects.create(bkm=Bkm.objects.get(slug="de10-lite"), author=reader, body="Which Quartus version do I need?")
    return {"avi": avi, "dana": dana}


def _context(browser, width, **kw):
    return browser.new_context(viewport={"width": width, "height": 900 if width > 600 else 844}, device_scale_factor=1, **kw)


def _shot(page, name):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))


@pytest.mark.django_db(transaction=True)
def test_a_visitor_signs_in_from_a_card_and_starts_a_conversation(browser, live_server, world):
    from bkm.models import Comment, Like, Star

    ctx = _context(browser, 1280)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/bkm/")
    assert page.locator(".bm-card").count() == 3
    assert not page.locator("#bm-phone").is_visible(), "a computer is not told to use a computer"
    _shot(page, "wall-visitor-1280")

    page.click("#de10-lite .bm-card-pic")
    assert page.locator("#bm-gate").is_visible()
    assert "next=%2Fbkm%2F%23de10-lite" in page.get_attribute("#bm-gate-google", "href")
    _shot(page, "gate-1280")
    assert not page.locator("#bm-gate-form").is_visible(), "the password is folded away"
    page.click(".bm-gate-more summary")
    page.fill("#bm-gate-form [name=username]", "dana@example.com")
    page.fill("#bm-gate-form [name=password]", PASSWORD)
    page.click("#bm-gate-form button[type=submit]")
    page.wait_for_url("**/bkm/#de10-lite")
    assert page.locator('#de10-lite [data-like]').count() == 1

    page.click('#de10-lite [data-like]')
    page.wait_for_function("document.querySelector('#de10-lite [data-like]').getAttribute('aria-pressed') === 'true'")
    assert page.inner_text("#de10-lite [data-like] [data-count]") == "1"
    page.click('#de10-lite [data-star]')
    page.wait_for_function("document.querySelector('#de10-lite [data-star]').getAttribute('aria-pressed') === 'true'")
    assert Like.objects.count() == 1 and Star.objects.count() == 1
    _shot(page, "wall-signed-1280")

    page.click("#de10-lite .bm-start")
    page.wait_for_url("**/bkm/de10-lite/")
    assert "git clone https://github.com/avisalmon/De10LiteBKM.git" in page.inner_text("#bm-clone")
    question = Comment.objects.get()
    page.click(f'[data-reply="{question.pk}"]')
    assert page.locator("#bm-replying").is_visible()
    page.fill("#bm-comment-form textarea", "Quartus Lite 23.1 worked for me.")
    page.click("#bm-comment-form button[type=submit]")
    page.wait_for_selector("text=Quartus Lite 23.1 worked for me.")
    reply = Comment.objects.get(body="Quartus Lite 23.1 worked for me.")
    assert reply.reply_to == question
    assert "Which Quartus version" in page.inner_text(f"#c{reply.pk} .bm-quote")
    _shot(page, "bkm-page-1280")
    page.goto(live_server.url + "/bkm/?starred=1")
    assert page.locator(".bm-card").count() == 1
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_the_notice_comes_first_and_can_be_dismissed(browser, live_server, world):
    """REQ-B.4"""
    ctx = _context(browser, 390, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    page.goto(live_server.url + "/bkm/")
    assert page.locator("#bm-phone").is_visible()
    box = page.locator(".bm-phone-paper").bounding_box()
    assert box["width"] > 300, "a big notice, not a strip"
    _shot(page, "phone-notice-390")
    page.click("#bm-phone-ok")
    assert not page.locator("#bm-phone").is_visible()
    page.reload()
    assert not page.locator("#bm-phone").is_visible(), "dismissed stays dismissed on this device"
    _shot(page, "phone-wall-390")
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_no_page_slides_sideways(browser, live_server, world):
    """Methodology 29 and 34: every phone width, and a computer."""
    broken = []
    for signed in (False, True):
        for width in (320, 360, 375, 390, 412, 1280):
            ctx = _context(browser, width)
            if signed:
                from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
                from django.contrib.sessions.backends.db import SessionStore

                s = SessionStore()
                s[SESSION_KEY] = str(world["dana"].pk)
                s[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
                s[HASH_SESSION_KEY] = world["dana"].get_session_auth_hash()
                s.save()
                ctx.add_cookies([{"name": "sessionid", "value": s.session_key, "domain": "localhost", "path": "/"}])
            page = ctx.new_page()
            paths = ["/bkm/", "/bkm/de10-lite/", "/bkm/?starred=1"] if signed else ["/bkm/", "/bkm/login/", "/bkm/signup/"]
            for path in paths:
                page.goto(live_server.url + path)
                over = page.evaluate(OVERFLOW, width)
                if over > 1:
                    broken.append(f"{path} at {width} ({'in' if signed else 'out'}): {over}px")
            ctx.close()
    assert not broken, "\n".join(broken)
