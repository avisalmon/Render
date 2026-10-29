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
        monkeypatch.setattr(builder, "build", lambda code, part=None: (CUBE, 0.2))
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
    # Avi, 2026-10-28: a part built while the page is open can be downloaded without a reload.
    assert "/v/1/stl/" in page.get_attribute("#d3-stl", "href")
    assert page.get_attribute("#d3-filebox", "hidden") is None
    assert page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id).filter((x, i, a) => a.indexOf(x) !== i)") == []
    page.wait_for_timeout(800)
    _shot(page, "design-phone-390")

    page.click("#d3-tools > summary")
    page.locator('#d3-sliders input[name="height"]').fill("60")
    page.click("#d3-apply")
    page.wait_for_function("document.querySelector('#d3-versions a.on') && document.querySelector('#d3-versions a.on').textContent === 'v2'", timeout=60000)
    v2 = Version.objects.get(design=d, number=2)
    assert v2.made_by == Version.SLIDERS and "height = 60;" in v2.code
    assert "/v/2/stl/" in page.get_attribute("#d3-stl", "href")
    assert page.inner_text("#d3-stl") == "Download STL (v2)"
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
        for p in ("/design3d/designs/", path, path + "done/", "/design3d/shared/"):
            page.goto(live_server.url + p)
            over = page.evaluate(OVERFLOW, width)
            wide = page.evaluate("(w) => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > w + 1 && !e.closest('canvas')).map(e => e.tagName + '.' + e.className).slice(0, 3)", width)
            if over > 1 or wide:
                broken.append(f"{p} at {width}: {over}px {wide}")
        ctx.close()
    # Avi's People screen with an invitation, and the invitation page signed out (2026-10-29).
    from django.contrib.auth.models import User

    from design3d.models import Invite

    avi = User.objects.create_superuser("avi@example.com", "avi@example.com", "d3-pass-55822")
    inv = Invite.objects.create(email="noa@example.com", name="Noa", created_by=avi)
    for width in (320, 390):
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        _session(ctx, avi)
        page = ctx.new_page()
        page.goto(live_server.url + "/design3d/people/")
        if page.evaluate(OVERFLOW, width) > 1:
            broken.append(f"/design3d/people/ at {width}")
        _shot(page, f"people-{width}")
        ctx.close()
    ctx = browser.new_context(viewport={"width": 360, "height": 800})
    page = ctx.new_page()
    for p in ("/design3d/", "/design3d/login/", f"/design3d/i/{inv.token}/"):
        page.goto(live_server.url + p)
        if page.evaluate(OVERFLOW, 360) > 1:
            broken.append(f"{p} at 360 (signed out)")
    _shot(page, "login-360")
    ctx.close()
    assert not broken, "\n".join(broken)


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_a_print_warning_is_fixed_with_one_tap(browser, live_server, world, monkeypatch):
    """D3.7: the chat line says what the print check found; Fix it sends the
    fix to the chat as the person's message."""
    from design3d import builder
    from design3d.models import Design, Message

    from tests.test_design3d import _box, _stl

    floating = _stl(_box(0, 0, 0, 10, 10, 10), _box(30, 0, 4, 35, 5, 9))
    monkeypatch.setattr(builder, "build", lambda code, part=None: (floating, 0.2))
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/design3d/designs/")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    page.fill("#d3-text", "Two cubes")
    page.click("#d3-send")
    page.wait_for_selector(".d3-msg.assistant.done .d3-built .d3-warn", timeout=60000)
    assert page.inner_text(".d3-msg.assistant.done .d3-built .d3-warn") == "1 print warning"
    page.click(".d3-msg.assistant.done .d3-built .d3-warn")  # opens the panel at the findings
    page.wait_for_function("document.getElementById('d3-tools').open")
    assert "floats in the air" in page.inner_text("#d3-checks")
    page.wait_for_timeout(700)
    _shot(page, "print-check-390")
    page.click("#d3-checks .d3-fix")
    page.wait_for_function("document.querySelectorAll('.d3-msg.assistant.done').length === 2", timeout=60000)
    said = list(Message.objects.filter(design=Design.objects.get(), role=Message.PERSON).values_list("text", flat=True))
    assert said[-1].startswith("Before I print: Some pieces float above the bed.")
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_mark_a_point_measure_keep_the_part_on_top_and_finish(browser, live_server, world):
    """D3.9 (Avi, 2026-10-29): tap the part to say "here", tap two points to
    measure, the part stays at the top while the chat scrolls (and can be
    unpinned), and Done opens the finished part."""
    from design3d.models import Design, Message

    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/design3d/designs/")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    page.fill("#d3-text", "A pencil holder")
    page.click("#d3-send")
    page.wait_for_function("document.getElementById('d3-view').dataset.loaded", timeout=60000)
    page.wait_for_timeout(600)
    assert page.is_visible("#d3-view-tools") and page.is_visible("#d3-done")

    # Measure: two taps on the part.
    canvas = page.locator("#d3-view canvas")
    box = canvas.bounding_box()
    page.click('[data-d3-mode="measure"]')
    page.touchscreen.tap(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
    page.touchscreen.tap(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.3)
    page.wait_for_selector("#d3-measure-label:not([hidden])", timeout=5000)
    assert page.inner_text("#d3-measure-label").split(" mm")[0].replace(".", "").isdigit()
    _shot(page, "measure-390")

    # Point: tap the part, say what to do there, send.
    page.click('[data-d3-mode="pin"]')
    page.touchscreen.tap(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
    page.wait_for_selector("#d3-pinned:not([hidden])", timeout=5000)
    _shot(page, "pin-390")
    page.fill("#d3-text", "Make the wall thicker here")
    page.click("#d3-send")
    page.wait_for_function("document.querySelectorAll('.d3-msg.assistant.done').length === 2", timeout=60000)
    said = Message.objects.filter(design=Design.objects.get(), role=Message.PERSON).last()
    assert said.pin and set(said.pin) == {"x", "y", "z", "nx", "ny", "nz", "version"} and said.pin["version"] == 1
    assert said.pictures.count() == 1, "a picture of the view with the marker"
    assert page.is_hidden("#d3-pinned")

    # The part stays at the top while the page scrolls; unpinned, it scrolls away.
    bar = page.locator(".d3-bar").bounding_box()["height"]
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)
    assert abs(page.locator(".d3-viewcol").bounding_box()["y"] - bar) < 3
    page.click("#d3-stick")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)
    assert page.locator(".d3-viewcol").bounding_box()["y"] < 0, "unpinned, it scrolls away"
    page.reload()
    assert page.get_attribute("#d3-stick", "aria-pressed") == "false", "remembered"

    page.click("#d3-done")
    page.wait_for_url("**/done/")
    page.wait_for_function("document.getElementById('d3-view').dataset.loaded", timeout=30000)
    assert page.evaluate(OVERFLOW, 390) <= 1
    _shot(page, "done-390")
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_a_box_and_its_lid(browser, live_server, world, monkeypatch):
    """Chapter 7: two parts in their colours, the plate, hide a part, pull
    them apart, and a marked point that knows its part."""
    from design3d import builder, llm
    from design3d.models import Design, Message

    from tests.test_design3d import BOX_AND_LID, REAL_BUILD, TWO_PARTS

    if not builder.available():
        pytest.skip("no OpenSCAD on this PC")
    monkeypatch.setattr(builder, "build", REAL_BUILD)
    monkeypatch.setattr(llm, "ask", lambda items: ({"title": "Box with lid", "message": "Here it is.", "assumptions": [],
                                                    "code": BOX_AND_LID, "parameters": [], "parts": TWO_PARTS},
                                                   {"in": 1, "cached": 0, "out": 1}, "stub"))
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/design3d/designs/")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    page.fill("#d3-text", "A box with a lid")
    page.click("#d3-send")
    page.wait_for_selector("#d3-parts-bar:not([hidden]) [data-part='lid']", timeout=60000)
    page.wait_for_function("(document.getElementById('d3-view').dataset.loaded || '').split(' ').length === 2", timeout=30000)
    assert page.inner_text(".d3-part-chips").replace("\n", " ").strip() == "Box Lid"
    page.locator("#d3-explode").fill("0.6")
    page.wait_for_timeout(500)
    _shot(page, "parts-exploded-390")
    page.click("[data-part='lid']")
    assert page.get_attribute("[data-part='lid']", "aria-pressed") == "false"
    page.click("[data-part='lid']")
    page.locator("#d3-explode").fill("0")

    canvas = page.locator("#d3-view canvas").bounding_box()
    page.click('[data-d3-mode="pin"]')
    page.touchscreen.tap(canvas["x"] + canvas["width"] * 0.5, canvas["y"] + canvas["height"] * 0.5)
    page.wait_for_selector("#d3-pinned:not([hidden])", timeout=5000)
    page.fill("#d3-text", "Make this thicker")
    page.click("#d3-send")
    page.wait_for_function("document.querySelectorAll('.d3-msg.assistant.done').length === 2", timeout=60000)
    pin = Message.objects.filter(design=Design.objects.get(), role=Message.PERSON).last().pin
    assert pin and pin.get("part") in ("box", "lid")

    page.click("[data-view='plate']")
    page.wait_for_function("(document.getElementById('d3-view').dataset.loaded || '').split(' ').length === 1", timeout=30000)
    page.wait_for_timeout(400)
    _shot(page, "parts-plate-390")
    page.click("#d3-tools > summary")
    assert page.locator("#d3-partlist li").count() == 2 and page.is_visible("#d3-3mf")
    assert page.evaluate(OVERFLOW, 390) <= 1
    _shot(page, "parts-list-390")
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_a_picture_opens_full_size(browser, live_server, world, tmp_path):
    """Avi, 2026-10-29: tap a picture in the chat to see it, save it or share it."""
    from PIL import Image

    photo = tmp_path / "sketch.jpg"
    Image.new("RGB", (900, 600), (220, 200, 160)).save(photo)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/design3d/designs/")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    page.set_input_files("#d3-files", str(photo))
    page.fill("#d3-text", "A bracket like this")
    page.click("#d3-send")
    page.wait_for_selector(".d3-msg.person .d3-pic", timeout=60000)
    page.click(".d3-msg.person .d3-pic")
    page.wait_for_selector("#d3-lightbox[open]", timeout=5000)
    assert page.get_attribute("#d3-pic-save", "href").endswith("?download=1")
    page.wait_for_function("document.querySelector('#d3-lightbox img').naturalWidth > 0", timeout=10000)
    assert page.evaluate(OVERFLOW, 390) <= 1
    _shot(page, "picture-390")
    page.click("#d3-pic-close")
    assert page.locator("#d3-lightbox[open]").count() == 0
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_home_puts_the_view_back(browser, live_server, world):
    """Avi, 2026-10-29: a Home button in the 3D view, back to the first view."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    _session(ctx, world["dana"])
    page = ctx.new_page()
    page.goto(live_server.url + "/design3d/designs/")
    page.click("#d3-new")
    page.wait_for_url("**/design3d/d/*/")
    page.fill("#d3-text", "A pencil holder")
    page.click("#d3-send")
    page.wait_for_function("document.getElementById('d3-view').dataset.loaded", timeout=60000)
    page.wait_for_timeout(500)
    first = page.evaluate("window.d3View.camera()")
    box = page.locator("#d3-view canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.8, box["y"] + box["height"] * 0.3, steps=8)
    page.mouse.up()
    page.wait_for_timeout(800)
    turned = page.evaluate("window.d3View.camera()")
    assert max(abs(a - b) for a, b in zip(first, turned)) > 5, "the drag turned the view"
    assert page.is_visible("#d3-home")
    page.click("#d3-home")
    page.wait_for_timeout(300)
    back = page.evaluate("window.d3View.camera()")
    assert max(abs(a - b) for a, b in zip(first, back)) < 0.5
    ctx.close()
