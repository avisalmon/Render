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

    from ustrip.models import ChecklistGroup, ChecklistItem, JournalPost, Trip

    group, _ = Group.objects.get_or_create(name="family")
    user = User.objects.create_user("phone_tester", password="x")
    user.groups.add(group)
    call_command("seed_ustrip")

    trip = Trip.objects.get(name="USA Trip 2026")

    # Seeding deliberately creates no packing lists and no journal posts (spec
    # §4.2/§4.3: nothing fabricated). That left both pages rendering empty here,
    # so their controls — the checkbox, the row buttons, the filter chips, the
    # journal's own row actions — were never actually measured. Give them
    # something to draw.
    packing = ChecklistGroup.objects.create(trip=trip, name="Packing — tester", assigned_to=user, order=0)
    for order, text in enumerate(["Socks", "Toothbrush", "Charger"]):
        ChecklistItem.objects.create(group=packing, text=text, order=order, done=order == 0)
    ChecklistGroup.objects.create(trip=trip, name="Before we leave", order=1)
    JournalPost.objects.create(trip=trip, author=user, caption="Made it.", location="Times Square")
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


def test_reordering_a_day_keeps_your_place_and_retimes_the_day(phone_context, live_server, trip_pages):
    """Sprint 11 F8, and a guard on the page's JS, which nothing else covers.

    Moving a stop used to reload the page, which on a twelve-stop day cost you
    your place to nudge one item. The arrows now swap in the DOM and re-time
    from the response. This asserts all three: the order changed, the times
    after it moved with it, and the page never navigated.
    """
    day_path = next(p for p in trip_pages if p.startswith("/ustrip/itinerary/") and p.count("/") == 4)
    page = phone_context.new_page()
    try:
        page.goto(live_server.url + day_path, wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        rows = page.locator("#timeline [data-item-id]")
        if rows.count() < 3:
            pytest.skip("need a few stops to reorder")
        before = rows.evaluate_all("els => els.map(e => e.dataset.itemId)")
        moved_id = before[0]
        moved_start_before = page.locator(f'#timeline [data-item-id="{moved_id}"] .tstart').inner_text()

        # Mark the document so a reload is detectable: a reload throws it away.
        page.evaluate("() => { window.__notReloaded = true; }")

        page.locator('#timeline [data-item-id] [data-move="down"]').first.click()
        page.wait_for_timeout(700)

        after = rows.evaluate_all("els => els.map(e => e.dataset.itemId)")
        assert after[:2] == [before[1], before[0]], f"order did not swap: {before} -> {after}"
        assert page.evaluate("() => window.__notReloaded === true"), "the page reloaded"

        # The moved stop now runs second, so its start time must have moved
        # with it. This is the half that a plain DOM swap would get wrong.
        moved_start_after = page.locator(f'#timeline [data-item-id="{moved_id}"] .tstart').inner_text()
        assert moved_start_after != moved_start_before, (
            f"the stop moved but its time did not: still {moved_start_before}"
        )
        assert page.locator("#day-summary").inner_text() != "", "the day summary went blank"
    finally:
        page.close()


def test_no_native_dialog_ever_fires(phone_context, live_server, trip_pages):
    """Spec §0a.1 point 3, F7 (Sprint 15): no browser-native alert/confirm/
    prompt, anywhere. 47 call sites across 10 templates used one of the
    three; own toast, confirm sheet and inline text edit replaced every one
    (ustrip.js). This is the guard, not a description of it: Playwright's
    `dialog` event is the one thing that cannot be faked by code that merely
    looks right, and it is exercised against the two flows that used to be a
    `confirm()` and a `prompt()` on the busiest page in the app.

    An unhandled native dialog blocks Chromium's event loop, so the listener
    both records and dismisses it — a hang here would itself be the proof
    that something regressed, on top of the assertion.
    """
    packing_path = next(p for p in trip_pages if p.endswith("/packing/"))
    page = phone_context.new_page()
    fired = []
    page.on("dialog", lambda d: (fired.append(d.message), d.dismiss()))
    try:
        page.goto(live_server.url + packing_path, wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        row = page.locator("#packing-list [data-item-id]").first
        assert row.count(), "seed data changed shape — nothing to test against"

        # Edit: used to be prompt(). Now an input replaces the label in place.
        row.locator("[data-edit]").click()
        field = row.locator(".u-edit-field")
        assert field.count(), "editInPlace did not swap in a field"
        field.fill("Edited from the phone guard")
        field.press("Enter")
        page.wait_for_timeout(300)
        assert row.locator(".itxt").inner_text() == "Edited from the phone guard"

        # Delete: used to be confirm(). Now a sheet with Cancel and Delete.
        row.locator("[data-delete]").click()
        sheet = page.locator(".u-sheet")
        assert sheet.count(), "confirm() sheet did not open"
        sheet.locator("[data-cancel]").click()
        page.wait_for_timeout(200)
        assert page.locator(f'[data-item-id="{row.get_attribute("data-item-id")}"]').count() == 1, (
            "Cancel deleted the row anyway"
        )

        item_id = row.get_attribute("data-item-id")
        row.locator("[data-delete]").click()
        page.locator(".u-sheet [data-ok]").click()
        page.wait_for_timeout(300)
        assert page.locator(f'[data-item-id="{item_id}"]').count() == 0, "Delete did not remove the row"

        assert not fired, f"a native dialog fired: {fired}"
    finally:
        page.close()


def test_journal_headers_merge_and_clean_up_after_themselves(phone_context, live_server, trip_pages):
    """F11 (Sprint 15), and a guard on the page's own JS, which the backend
    tests in test_ustrip_journal_grouping.py cannot see — they prove the
    label is correct, not that the DOM the family actually reads updates
    correctly as posts come and go.

    trip_pages seeds one journal post before this test starts. Posting a
    second one "now" lands in the same day-group as the seeded one (nothing
    in this app makes two posts a second apart land on different days), so
    the real question is whether the page joins the existing header instead
    of stamping a duplicate one above it — and, symmetrically, whether
    deleting the seeded post drops it back to a lone post with its header
    intact, then deleting the last one clears the header too.
    """
    journal_path = next(p for p in trip_pages if p.endswith("/journal/"))
    page = phone_context.new_page()
    try:
        page.goto(live_server.url + journal_path, wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        headers_before = page.locator(".feed-daylabel").count()
        assert headers_before == 1, "the seeded post should start with exactly one header"

        page.fill('textarea[name="caption"]', "Posted from the phone guard")
        page.click('#journal-form button[type=submit]')
        page.wait_for_timeout(500)

        assert page.locator(".feed-daylabel").count() == headers_before, (
            "a second post from the same day should join the existing header, not add one"
        )
        posts = page.locator("#journal-feed [data-post-id]")
        assert posts.count() == 2, "the new post did not land in the feed"
        # It has to be the first post under the (single, shared) header, not
        # appended after the seeded one — reverse-chron holds inside a group too.
        assert posts.first.locator(".caption").inner_text() == "Posted from the phone guard"

        # Delete the newer post: the header must survive, the seeded post remains.
        posts.first.locator("[data-delete]").click()
        page.locator(".u-sheet [data-ok]").click()
        page.wait_for_timeout(400)
        assert page.locator("#journal-feed [data-post-id]").count() == 1
        assert page.locator(".feed-daylabel").count() == 1, "the header should not have been removed yet"

        # Delete the last remaining post: now the header goes with it.
        page.locator("#journal-feed [data-post-id]").first.locator("[data-delete]").click()
        page.locator(".u-sheet [data-ok]").click()
        page.wait_for_timeout(400)
        assert page.locator("#journal-feed [data-post-id]").count() == 0
        assert page.locator(".feed-daylabel").count() == 0, "an orphaned header was left behind"
        assert page.locator("#journal-empty").count() == 1
    finally:
        page.close()
