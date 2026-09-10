"""Does מט״צים still work on a phone?

Avi, 2026-09-10: "make sure everything we develop is adaptive to phone." A
one-off look does not make that true a week later, so this drives a real browser
at 390px on every page and fails when it stops being true.

Two things it checks, both of which are bugs a reader cannot see in a template:

- **Horizontal overflow.** A page wider than the screen is the classic mobile
  break: the whole layout slides sideways and the reader is fighting the page.
- **Tap targets.** A 15px inline link is a link a thumb misses. This caught
  exactly that on the locked student door, where the offending link was the only
  way forward.

Skipped rather than failed when Playwright or its browser is unavailable, so a
machine without it can still run the suite.
"""

import os

import pytest

# Playwright's sync API runs an event loop in this thread, and Django refuses
# synchronous ORM calls from a thread with a live loop. Safe here: `live_server`
# serves the app on its own thread, so nothing is actually racing. This is the
# documented escape for driving a real browser from a sync test.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprmobile, pytest.mark.django_db]

PHONE = {"width": 390, "height": 844}

PAGES = [
    "/matazim/",
    "/matazim/about/",
    "/matazim/track/",
    "/matazim/courses/",
    "/matazim/test/",
    "/matazim/test/lessons/",
    "/matazim/schools/",
    "/matazim/community/",
    "/matazim/events/",
    "/matazim/login/",
    "/matazim/register/",
]

# The smallest comfortable touch target. Anything shorter is a link a thumb
# misses, and on a phone that is a dead end rather than a nuisance.
MIN_TAP_PX = 36

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    const wide = [];
    document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > window.innerWidth + 1 && r.height > 0) {
            wide.push(el.tagName.toLowerCase() + '.' +
                String(el.className || '').split(' ')[0] + ' w=' + Math.round(r.width));
        }
    });
    return {
        overflow: doc.scrollWidth > window.innerWidth + 1,
        scrollW: doc.scrollWidth,
        innerW: window.innerWidth,
        offenders: [...new Set(wide)].slice(0, 5),
    };
}"""

TAP_JS = """(minPx) => {
    const bad = [];
    document.querySelectorAll('a, button').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.height < minPx) {
            bad.push((el.textContent || '').trim().slice(0, 24) + ' h=' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""


@pytest.fixture(scope="module")
def phone_page():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
            )
            yield context.new_page()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def test_every_page_fits_a_phone(phone_page, live_server):
    """Nothing may be wider than the screen at 390px, on any page.

    One pass over every page rather than one test each: it halves the browser
    navigations, and a failure names every broken page at once instead of the
    first one alphabetically.
    """
    broken = []
    for path in PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(200)
        result = phone_page.evaluate(OVERFLOW_JS)
        if result["overflow"]:
            broken.append(f"{path}: {result['scrollW']} > {result['innerW']} {result['offenders']}")
    assert not broken, "pages scroll sideways at 390px:\n" + "\n".join(broken)


def test_everything_tappable_is_big_enough(phone_page, live_server):
    """A thumb is not a mouse pointer.

    This caught two real ones the day it was written: the link out of a locked
    door, and the link between the login and register screens. Both were the
    only way forward from where they sat, and both were 17px tall.
    """
    broken = []
    for path in PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(200)
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            broken.append(f"{path}: {small}")
    assert not broken, f"targets under {MIN_TAP_PX}px:\n" + "\n".join(broken)


def test_the_menu_opens_on_a_phone(phone_page, live_server):
    """The nav collapses behind a button on a phone, so that button must work.

    The welcome notice is dismissed first on purpose. It covers the page until
    acknowledged, which is correct behaviour and not something to work around
    in the product just to make a test easier.
    """
    phone_page.goto(live_server.url + "/matazim/", wait_until="domcontentloaded")
    phone_page.wait_for_timeout(250)
    welcome = phone_page.locator(".mz-welcome button[type=submit]")
    if welcome.count():
        welcome.click()
        phone_page.wait_for_timeout(400)

    nav = phone_page.locator("#mzNav")
    assert not nav.is_visible(), "the menu should start closed on a phone"

    phone_page.click(".mz-nav-toggle")
    phone_page.wait_for_timeout(250)
    assert nav.is_visible(), "the menu button did not open the menu"
