"""design3d in a real browser: a maker's whole job on a phone (methodology
27), the computer's three columns, and no sideways scroll at any phone
width (methodology 29, 34). The 3D view loads three.js from the CDN, as in
production. Turns run inline (DESIGN3D_SYNC); the model is the stub and the
builder is the real OpenSCAD when present, else a cube."""

import os

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.design3d

OVERFLOW = "(w) => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - w"
SHOTS = os.environ.get("D3_SHOTS")


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def world(transactional_db, settings, tmp_path, monkeypatch):
    from django.contrib.auth.models import User

    from design3d import builder
    from design3d.models import Maker

    from tests.test_design3d import CUBE

    settings.DESIGN3D_PRIVATE_DIR = tmp_path
    settings.DESIGN3D_SYNC = True
    settings.OPENAI_API_KEY = ""
    monkeypatch.setattr("app.safety.image_is_safe", lambda *a, **k: (True, ""), raising=False)
    if not builder.available():
        monkeypatch.setattr(builder, "build", lambda code: (CUBE, 0.2))
    dana = User.objects.create_user("dana@example.com", "dana@example.com", "d3-pass-55821", first_name="Dana")
    Maker.objects.create(user=dana, display_name="Dana", status=Maker.APPROVED)
    return {"dana": dana}


def _session(ctx, user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    s = SessionStore()
    s[SESSION_KEY] = str(user.pk)
    s[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    s[HASH_SESSION_KEY] = user.get_session_auth_hash()
    s.save()
    ctx.add_cookies([{"name": "sessionid", "value": s.session_key, "domain": "localhost", "path": "/"}])


def _shot(page, name):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_a_maker_describes_a_part_sees_it_and_changes_its_size(browser, live_server, world):
    from design3d.models import Design, Version

    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/design3d/designs/")
    _shot(page, "designs-empty-390")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    assert page.locator("#d3-hello").is_visible()
    view, chat = page.locator("#d3-view").bounding_box(), page.locator(".d3-chat").bounding_box()
    assert view["y"] < chat["y"], "on a phone the part is on top, the chat below"
    assert page.locator("#d3-camera").count() == 1 and page.get_attribute("#d3-camera", "capture") == "environment"

    page.fill("#d3-text", "A holder for three pencils")
    page.click("#d3-send")
    page.wait_for_selector(".d3-msg.assistant.done", timeout=60000)
    page.wait_for_function("document.getElementById('d3-view').dataset.loaded", timeout=30000)
    d = Design.objects.get()
    assert d.current and d.current.number == 1
    assert page.locator("#d3-view canvas").count() == 1
    page.wait_for_timeout(800)
    _shot(page, "design-phone-390")

    page.click("#d3-tools > summary")
    page.locator('#d3-sliders input[name="height"]').fill("60")
    page.click("#d3-apply")
    page.wait_for_function("document.querySelector('#d3-versions a.on') && document.querySelector('#d3-versions a.on').textContent === 'v2'", timeout=60000)
    v2 = Version.objects.get(design=d, number=2)
    assert v2.made_by == Version.SLIDERS and "height = 60;" in v2.code
    _shot(page, "design-phone-sliders-390")
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_an_older_turn_that_finishes_late_is_redrawn(browser, live_server, world):
    """Avi, 2026-10-28: the first turn kept saying "Building the part" after
    it was done, because a newer message had been sent and the page only
    asked for messages after the newest one."""
    from django.utils import timezone

    from design3d.models import Design, Maker, Message

    d = Design.objects.create(owner=Maker.objects.get(user=world["dana"]))
    first = Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.BUILDING, step="Building version 1")
    Message.objects.create(design=d, role=Message.PERSON, text="Make it bigger")
    Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.THINKING, step="Reading your message")
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    _session(ctx, world["dana"])
    page = ctx.new_page()
    page.goto(live_server.url + f"/design3d/d/{d.pk}/")
    page.wait_for_function(f"document.querySelector('#m{first.pk} .d3-elapsed').textContent.includes('s')", timeout=10000)
    Message.objects.filter(pk=first.pk).update(state=Message.DONE, step="", text="Here is your cube.", created_at=timezone.now())
    page.wait_for_function(f"document.querySelector('#m{first.pk}').dataset.state === 'done'", timeout=10000)
    assert page.inner_text(f"#m{first.pk}") == "Here is your cube."
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_on_a_computer_three_columns_and_no_page_slides_sideways(browser, live_server, world, client):
    from django.test import Client

    c = Client()
    c.force_login(world["dana"])
    r = c.post("/design3d/designs/new/")
    path = r["Location"]
    c.post(path + "send/", {"text": "A box"}, HTTP_ACCEPT="application/json")

    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    _session(ctx, world["dana"])
    page = ctx.new_page()
    page.goto(live_server.url + path)
    page.wait_for_function("document.getElementById('d3-view').dataset.loaded", timeout=30000)
    chat, view, tools = (page.locator(s).bounding_box() for s in (".d3-chat", "#d3-view", "#d3-tools"))
    assert chat["x"] < view["x"] < tools["x"], "chat, part, sizes from left to right"
    assert page.locator("#d3-tools").get_attribute("open") is not None
    page.wait_for_timeout(800)
    _shot(page, "design-desktop-1366")
    ctx.close()

    broken = []
    for width in (320, 360, 375, 390, 412, 1280):
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        _session(ctx, world["dana"])
        page = ctx.new_page()
        for p in ("/design3d/designs/", path, "/design3d/shared/"):
            page.goto(live_server.url + p)
            over = page.evaluate(OVERFLOW, width)
            wide = page.evaluate("(w) => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > w + 1 && !e.closest('canvas')).map(e => e.tagName + '.' + e.className).slice(0, 3)", width)
            if over > 1 or wide:
                broken.append(f"{p} at {width}: {over}px {wide}")
        ctx.close()
    ctx = browser.new_context(viewport={"width": 360, "height": 800})
    page = ctx.new_page()
    for p in ("/design3d/", "/design3d/login/"):
        page.goto(live_server.url + p)
        if page.evaluate(OVERFLOW, 360) > 1:
            broken.append(f"{p} at 360 (signed out)")
    _shot(page, "login-360")
    ctx.close()
    assert not broken, "\n".join(broken)
