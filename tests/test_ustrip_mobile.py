"""Is ustrip actually usable on a phone?

spec §0a declares ustrip phone-first. Until 2026-09-14 nothing enforced that,
and it showed: the packing checkbox — the control the family taps most — was
**20px**, under even WCAG 2.5.8's 24px floor, and four 26px buttons sat
shoulder to shoulder on every itinerary row with delete next to move-down.
מט״צים, which is *not* phone-first, had a test like this one. The app whose
spec makes the claim had none. Hence this file (spec §0a.1).

What it checks, in a real browser at 390px, signed in as a family member
(every page worth checking is behind the gate):

- **Horizontal overflow.** A page wider than the screen means the reader is
  fighting the layout sideways.
- **Effective tap targets.** Not the CSS box — what a thumb hits. Each control
  is probed at 22px from its centre in all four directions; if the tap lands on
  something else, the target is too small *or* its neighbour is too close. That
  catches both failures with one measure, including hit areas expanded by a
  pseudo-element, which a `getBoundingClientRect()` check cannot see.

Skipped rather than failed when Playwright or its browser is unavailable, so a
machine without it can still run the suite.
"""

import os

import pytest

# See tests/test_matazim_mobile.py: Playwright's sync API runs a loop in this
# thread and Django refuses sync ORM calls from one. `live_server` serves on its
# own thread, so nothing actually races.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.django_db]

PHONE = {"width": 390, "height": 844}

# Spec §0a.1. Not WCAG 2.5.8's 24px floor: this app is used one-handed, walking,
# in the cold, in a country nobody in the family lives in.
MIN_TAP_PX = 44

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    const limit = doc.clientWidth;
    const wide = [];
    document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width > limit + 1 || r.right > limit + 1) && r.height > 0) {
            wide.push(el.tagName.toLowerCase() + '.' +
                String(el.className || '').split(' ')[0] +
                ' w=' + Math.round(r.width) + ' right=' + Math.round(r.right));
        }
    });
    return {
        // Element-based, not scrollWidth-based. Under mobile emulation
        // `scrollWidth` tracks the *visual* viewport (390 client, 394 inner on a
        // page that scrolls), so it reports 4px of overflow on a page where
        // nothing overflows. An element sticking out past the screen is the
        // real, actionable signal, and it names the culprit.
        overflow: wide.length > 0,
        scrollW: doc.scrollWidth,
        innerW: limit,
        offenders: [...new Set(wide)].slice(0, 5),
    };
}"""

# Probe the four edge midpoints of the required target box. A point that lands
# on the control (or inside it) counts; anything else means a thumb aiming
# there hits a neighbour, or nothing.
#
# Two things this has to get right or it reports noise instead of bugs:
#
#   - A control below the fold has its centre outside the viewport, where
#     elementFromPoint returns null. Each one is scrolled into view first.
#   - A control that is present but not on top — the account menu's contents
#     while the <details> is closed — fails every probe for a reason that has
#     nothing to do with size. If the *centre* does not hit the control, it is
#     hidden or covered, which is a different question; those are skipped.
TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1;
    const bad = [];
    const controls = document.querySelectorAll(
        'a, button, summary, input[type=checkbox], input[type=file], .drag-handle');
    controls.forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        // Inline links inside a paragraph are read, not aimed at; a whole
        // sentence of body text cannot be 44px tall. Only standalone controls.
        if (el.tagName === 'A' && el.closest('p, figcaption, .tsummary, .detail-desc')) return;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => {
            if (x < 1 || y < 1 || x > window.innerWidth - 1 || y > window.innerHeight - 1) return null;
            return document.elementFromPoint(x, y);
        };
        const hits = (node) => node && (node === el || el.contains(node));
        if (!hits(at(cx, cy))) return;   // covered or off-screen, not a size question
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]]
            .some(([x, y]) => {
                const node = at(x, y);
                return node !== null && !hits(node);   // off-viewport edge is not a failure
            });
        if (missed) {
            bad.push((el.getAttribute('title') || el.textContent || el.className || el.tagName)
                .trim().slice(0, 28) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""


@pytest.fixture(scope="module")
def phone_context():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
            )
            yield context
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture(scope="module")
def phone_page(phone_context):
    return phone_context.new_page()


@pytest.fixture
def trip_pages(db, live_server, phone_page):
    """A seeded trip, a signed-in family member, and every page worth checking.

    The real seeded trip rather than fixtures: the pages that break on a phone
    break because of real content lengths, and 84 items is what the family will
    actually be scrolling.
    """
    from django.contrib.auth.models import Group, User
    from django.core.management import call_command

    from ustrip.models import Trip

    group, _ = Group.objects.get_or_create(name="family")
    user = User.objects.create_user("phone_tester", password="x")
    user.groups.add(group)
    call_command("seed_ustrip")

    trip = Trip.objects.get(name="USA Trip 2026")
    day = trip.days.first()
    item = day.items.first()
    flight = trip.flights.first()

    # Sign in through the real form, so the session cookie is the real one.
    phone_page.goto(live_server.url + "/ustrip/login/", wait_until="domcontentloaded")
    phone_page.fill("input[name=username]", "phone_tester")
    phone_page.fill("input[name=password]", "x")
    phone_page.click("button[type=submit]")
    phone_page.wait_for_timeout(400)

    return [
        "/ustrip/",
        "/ustrip/itinerary/",
        f"/ustrip/itinerary/{day.id}/",
        f"/ustrip/itinerary/item/{item.id}/",
        f"/ustrip/itinerary/item/{item.id}/edit/",
        f"/ustrip/flight/{flight.id}/edit/",
        f"/ustrip/rental-car/{trip.rental_car.id}/edit/",
        "/ustrip/packing/",
        "/ustrip/journal/",
        "/ustrip/offline/",
    ]


def test_every_page_fits_a_phone(phone_page, live_server, trip_pages):
    broken = []
    for path in trip_pages:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(200)
        result = phone_page.evaluate(OVERFLOW_JS)
        if result["overflow"]:
            broken.append(f"{path}: {result['scrollW']} > {result['innerW']} {result['offenders']}")
    assert not broken, "pages scroll sideways at 390px:\n" + "\n".join(broken)


def test_every_control_is_big_enough_for_a_thumb(phone_page, live_server, trip_pages):
    """The check that would have caught the 20px packing checkbox."""
    broken = []
    for path in trip_pages:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(200)
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            broken.append(f"{path}: {small}")
    assert not broken, f"controls a thumb cannot hit at {MIN_TAP_PX}px:\n" + "\n".join(broken)


def test_the_itinerary_still_opens_with_no_signal(phone_context, live_server, trip_pages):
    """Spec §0a.2: the whole point of the app is holding the plan, and the
    Finger Lakes are where signal goes.

    The real check, not a proxy for it: load the day page so the worker caches
    it, cut the network at the browser, reload, and require the day's real
    content to still be on screen. `live_server` runs on localhost, which is a
    secure context, so service workers register exactly as they do in prod.
    """
    day_path = next(p for p in trip_pages if p.startswith("/ustrip/itinerary/") and p.count("/") == 4)
    page = phone_context.new_page()
    try:
        page.goto(live_server.url + day_path, wait_until="domcontentloaded")
        # Wait for the worker to take control; without it there is nothing to test.
        try:
            page.wait_for_function(
                "navigator.serviceWorker && navigator.serviceWorker.controller !== null", timeout=8000
            )
        except Exception:  # pragma: no cover - a browser build without SW support
            pytest.skip("service worker did not take control")
        page.reload(wait_until="domcontentloaded")   # first load the worker actually serves
        page.wait_for_timeout(400)
        expected = page.locator(".ttitle").first.inner_text()

        phone_context.set_offline(True)
        try:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            body = page.inner_text("body")
        finally:
            phone_context.set_offline(False)

        assert expected[:20] in body, (
            "the day page did not survive going offline; "
            f"looked for {expected[:20]!r} in:\n{body[:400]}"
        )
    finally:
        page.close()


def test_the_app_is_installable(phone_page, live_server, trip_pages):
    """A manifest and an icon, so it lands on the home screen as an app rather
    than a bookmark (spec §0a.2)."""
    phone_page.goto(live_server.url + "/ustrip/", wait_until="domcontentloaded")
    manifest_href = phone_page.get_attribute("link[rel=manifest]", "href")
    assert manifest_href, "no manifest linked"

    manifest = phone_page.evaluate(
        "async (href) => (await fetch(href)).json()", manifest_href
    )
    assert manifest["start_url"] == "/ustrip/"
    assert manifest["scope"] == "/ustrip/", "scope must stay inside ustrip"
    assert manifest["display"] == "standalone"
    assert manifest["icons"], "an installable app needs an icon"

    for icon in manifest["icons"]:
        status = phone_page.evaluate(
            "async (src) => (await fetch(src)).status", icon["src"]
        )
        assert status == 200, f"icon {icon['src']} is missing ({status})"
