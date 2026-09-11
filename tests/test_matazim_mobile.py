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
    "/matazim/leaders/",
    # The legal pages are read on a phone by someone deciding whether to sign
    # up, which makes them exactly the wrong place for a sideways scroll.
    "/matazim/privacy/",
    "/matazim/terms/",
]

# REQ-M.85 — the rights screens, which a member reaches on a phone or not at all.
MEMBER_PAGES = ["/matazim/profile/", "/matazim/me/data/", "/matazim/me/delete/"]

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


# --------------------------------------------------------------- SPR-M.8
#
# Everything above is reachable logged out. The leader's screens are not, and
# they are the ones a leader actually lives in: the roster is read standing in
# a classroom, on a phone, which is exactly where a table quietly becomes a
# sideways scroll. So this signs in for real and walks them.

LEADER_PAGES = [
    "/matazim/leader/",
    "/matazim/leader/students/",
    "/matazim/leader/classes/",
]

LEADER_EMAIL = "phone-leader@example.com"
LEADER_PASSWORD = "phone-guard-9912"


def _a_leader_with_a_student():
    """A roster with somebody on it. An empty screen cannot overflow."""
    from django.contrib.auth.models import User
    from django.utils import timezone

    from app.models import UserProfile
    from matazim.models import Leader, MemberProfile, Student, StudyClass

    teacher = User.objects.create_user(
        username=LEADER_EMAIL, email=LEADER_EMAIL, password=LEADER_PASSWORD
    )
    UserProfile.objects.update_or_create(user=teacher, defaults={"display_name": "נעה מורה"})
    leader = Leader.objects.create(user=teacher)
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")

    kid = User.objects.create_user(
        username="phone-kid@example.com", email="phone-kid@example.com", password="x-4417-y"
    )
    UserProfile.objects.update_or_create(
        user=kid, defaults={"display_name": "יובל בן ארצי לוינשטיין"}
    )
    MemberProfile.objects.update_or_create(
        user=kid, defaults={"entrance_test_passed_at": timezone.now()}
    )
    Student.objects.create(user=kid, leader=leader)
    return leader


def _sign_in(page, live_server):
    """Through the real form, because the real form is what a leader uses.

    Two details here were found the hard way, and both made the guard pass
    while looking at the wrong page.

    The welcome notice is dismissed first. It covers the page until
    acknowledged, and it carries its own submit button which sits *before* the
    login form in the DOM, so a bare `button[type=submit]` clicks the welcome
    and never touches the login. The click is then scoped to the login form for
    the same reason.

    And the landing is asserted rather than assumed. A guard that fails to sign
    in still passes every check, because the login page it gets bounced back to
    fits a phone perfectly well.
    """
    page.goto(live_server.url + "/matazim/login/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)

    welcome = page.locator(".mz-welcome button[type=submit]")
    if welcome.count():
        welcome.click()
        page.wait_for_timeout(400)

    page.fill('input[name="email"]', LEADER_EMAIL)
    page.fill('input[name="password"]', LEADER_PASSWORD)
    page.click('form:has(input[name="password"]) button[type="submit"]')
    page.wait_for_timeout(600)

    assert (
        "/login/" not in page.url
    ), f"the guard never signed in, so it would have checked the login page: {page.url}"


def test_the_leader_screens_fit_a_phone(phone_page, live_server, db):
    """REQ-M.75 over the screens a leader spends their time in.

    A roster is a table in spirit, and a table is the classic way a page starts
    scrolling sideways. Worth checking with a long name on it, because the
    longest name in the class is what finds the bug.
    """
    _a_leader_with_a_student()
    _sign_in(phone_page, live_server)

    broken = []
    for path in LEADER_PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(250)
        result = phone_page.evaluate(OVERFLOW_JS)
        if result["overflow"]:
            broken.append(f"{path}: {result['scrollW']} > {result['innerW']} {result['offenders']}")
    assert not broken, "leader pages scroll sideways at 390px:\n" + "\n".join(broken)


def test_the_leader_screens_are_tappable(phone_page, live_server, db):
    """REQ-M.75. The roster is one long column of links, so every one counts."""
    _a_leader_with_a_student()
    _sign_in(phone_page, live_server)

    broken = []
    for path in LEADER_PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(250)
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            broken.append(f"{path}: {small}")
    assert not broken, f"targets under {MIN_TAP_PX}px:\n" + "\n".join(broken)


def test_the_rights_screens_fit_a_phone(phone_page, live_server, db):
    """REQ-M.75 over REQ-M.85. A right that is unusable on a phone is a right a
    fourteen-year-old does not have."""
    _a_leader_with_a_student()
    _sign_in(phone_page, live_server)

    broken = []
    for path in MEMBER_PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        phone_page.wait_for_timeout(250)
        result = phone_page.evaluate(OVERFLOW_JS)
        if result["overflow"]:
            broken.append(f"{path}: {result['scrollW']} > {result['innerW']} {result['offenders']}")
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            broken.append(f"{path}: targets {small}")
    assert not broken, "the rights screens break on a phone:\n" + "\n".join(broken)
