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
def pw():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def browser(pw):
    try:
        chrome = pw.chromium.launch()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")
    yield chrome
    chrome.close()


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
    from bkm.models import Bkm, Comment, Like, Star

    ctx = _context(browser, 1280)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/bkm/")
    assert page.locator(".bm-card").count() == Bkm.objects.filter(is_published=True).count()
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


def _signed(ctx, user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    s = SessionStore()
    s[SESSION_KEY] = str(user.pk)
    s[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    s[HASH_SESSION_KEY] = user.get_session_auth_hash()
    s.save()
    ctx.add_cookies([{"name": "sessionid", "value": s.session_key, "domain": "localhost", "path": "/"}])


@pytest.fixture
def projects(world, monkeypatch):
    from bkm import images
    from bkm.models import Bkm, Project, Reader

    monkeypatch.setattr(images, "safe", lambda data, user=None: (True, ""))
    eli = Reader.objects.create(user=world["avi"], display_name="Avi S")
    kit = Bkm.objects.get(slug="single-button-kit")
    made = []
    for i in range(7):
        made.append(Project.objects.create(owner=eli, title=f"Gadget number {i}", kind="video", url="https://youtu.be/dQw4w9WgXcQ",
                                           bkm=kit if i % 2 else None, topic="electronics" if i % 2 else "games",
                                           description="A small thing with a button and a screen.", tags="esp32, oled"))
    return made


@pytest.mark.django_db(transaction=True)
def test_the_menu_stays_on_top_while_scrolling(pw, browser, live_server, world, projects):
    """Avi, 2026-10-27: the top menu is always there when scrolling, on a
    computer and on an iPad (WebKit), and it never covers the first line."""
    broken = []
    try:
        webkit = pw.webkit.launch()
    except Exception:  # pragma: no cover
        webkit = None
    for engine, b in (("chromium", browser), ("webkit", webkit)):
        if b is None:
            continue
        for vp in ({"width": 1280, "height": 700}, {"width": 1024, "height": 768}):
            ctx = b.new_context(viewport=vp)
            page = ctx.new_page()
            for path in ("/bkm/", "/bkm/projects/"):
                page.goto(live_server.url + path)
                bar = page.locator(".bm-bar").bounding_box()
                first = page.locator(".bm-main").bounding_box()
                if first["y"] < bar["y"] + bar["height"] - 1:
                    broken.append(f"{engine} {vp['width']} {path}: the bar covers the page")
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(300)
                if page.evaluate("window.scrollY") < 100:
                    broken.append(f"{engine} {vp['width']} {path}: did not scroll")
                if page.locator(".bm-bar").bounding_box()["y"] != 0:
                    broken.append(f"{engine} {vp['width']} {path}: the bar scrolled away")
            ctx.close()
    if webkit:
        webkit.close()
    assert not broken, "\n".join(broken)


@pytest.mark.django_db(transaction=True)
def test_the_exhibition_on_a_computer(browser, live_server, world, projects, tmp_path):
    """REQ-B.30 to B.35, walked: a visitor is asked in, a maker pins a photo,
    a video plays in its card, a photo opens large, the filters find."""
    from PIL import Image

    from bkm.models import Project

    ctx = _context(browser, 1280)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/bkm/projects/")
    _shot(page, "projects-visitor-1280")
    first = projects[-1]
    page.click(f"#p{first.pk} .bm-pmedia-btn")
    assert page.locator("#bm-gate").is_visible()
    assert f"%23p{first.pk}" in page.get_attribute("#bm-gate-google", "href")
    assert page.locator("iframe").count() == 0
    ctx.close()

    ctx = _context(browser, 1280)
    _signed(ctx, world["dana"])
    page = ctx.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/bkm/projects/")
    page.click(f"#p{first.pk} [data-embed]")
    assert page.locator(f'#p{first.pk} iframe[src*="youtube-nocookie.com/embed/dQw4w9WgXcQ"]').count() == 1
    page.click(f"#p{first.pk} [data-plike]")
    page.wait_for_function(f"document.querySelector('#p{first.pk} [data-plike]').getAttribute('aria-pressed') === 'true'")

    page.click("#bm-pin-project")
    page.wait_for_url("**/bkm/projects/new/")
    page.check("input[name=kind][value=image]")
    assert page.locator('[data-field="image"]').is_visible()
    photo = tmp_path / "board.jpg"
    Image.new("RGB", (1200, 900), (180, 60, 40)).save(photo)
    page.fill("#id_title", "My soldered board")
    page.set_input_files("#id_image", str(photo))
    page.select_option("#id_topic", "electronics")
    page.fill("#id_tags", "soldering, first")
    _shot(page, "project-form-1280")
    page.click("#bm-project-form button[type=submit]")
    page.wait_for_url("**/bkm/projects/*/")
    mine = Project.objects.get(title="My soldered board")
    assert mine.owner.user == world["dana"] and mine.image
    page.click(".bm-pcard-big [data-zoom]")
    assert page.locator("#bm-zoom").is_visible()
    page.keyboard.press("Escape")

    page.goto(live_server.url + "/bkm/projects/")
    page.fill(".bm-search input", "soldering")
    page.click("#bm-filters button[type=submit]")
    page.wait_for_url("**q=soldering**")
    assert page.locator(".bm-pcard").count() == 1
    page.goto(live_server.url + "/bkm/projects/")
    page.select_option("select[name=bkm]", "single-button-kit")
    page.click("#bm-filters button[type=submit]")
    page.wait_for_url("**bkm=single-button-kit**")
    assert page.locator(".bm-pcard").count() == 3
    _shot(page, "projects-filtered-1280")
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_avi_replaces_a_cards_picture_from_the_wall(browser, live_server, world, projects, tmp_path):
    """REQ-B.23, walked: from the card, through the form, back to the card
    with the new picture. No deploy."""
    from PIL import Image

    from bkm.models import Bkm

    before = Bkm.objects.get(slug="de10-lite").picture.name
    ctx = _context(browser, 1280)
    _signed(ctx, world["avi"])
    page = ctx.new_page()
    page.goto(live_server.url + "/bkm/")
    page.click("#de10-lite .bm-admin-edit")
    page.wait_for_url("**/bkm/de10-lite/edit/")
    photo = tmp_path / "lcd.jpg"
    Image.new("RGB", (1600, 900), (10, 160, 90)).save(photo)
    page.set_input_files("#id_picture", str(photo))
    assert "lcd.jpg" in page.inner_text("[data-upload-name]")
    page.click('[data-rot-by="90"]')
    assert page.get_attribute("[data-rot-value]", "value") == "90"
    assert "rotate(90deg)" in page.get_attribute("[data-rot-img]", "style")
    _shot(page, "bkm-form-1280")
    page.click("#bm-bkm-form button[type=submit]")
    page.wait_for_url("**/bkm/#de10-lite")
    saved = Bkm.objects.get(slug="de10-lite").picture
    assert saved.name != before
    assert saved.name.split("/")[-1] in page.get_attribute("#de10-lite .bm-card-pic img", "src")
    with Image.open(saved.path) as img:
        assert img.size == (900, 1600), "saved turned, as previewed"
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_no_page_slides_sideways(browser, live_server, world, projects):
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
            paths = (["/bkm/", "/bkm/de10-lite/", "/bkm/?starred=1", "/bkm/projects/", f"/bkm/projects/{projects[0].pk}/",
                      "/bkm/projects/new/"] if signed else ["/bkm/", "/bkm/login/", "/bkm/signup/", "/bkm/projects/"])
            for path in paths:
                page.goto(live_server.url + path)
                over = page.evaluate(OVERFLOW, width)
                if over > 1:
                    broken.append(f"{path} at {width} ({'in' if signed else 'out'}): {over}px")
            ctx.close()
    assert not broken, "\n".join(broken)
