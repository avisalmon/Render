"""Books' screen contract: every screen, by state, in a real browser.

The rule from the_manager.md Step 4a and memz's contract: every screen that
got rendered had a defect no HTML test had caught. So each screen is opened
at phone width (390) and desktop width (1280), in the light theme and in
dark, asserting what only exists after layout:

- the contract landed on the screen it asked for (data-screen),
- there is a heading and something to read, nothing alarming,
- text meets WCAG AA contrast, measured,
- nothing is wider than the viewport,
- every control is a 44px target with no neighbour inside that box,
- every image has alt text, every icon-only button a label,
- the shelf lifts a book on tap and the label shows it.

Adding a screen means adding it here. Skipped, not failed, without a browser.
"""

import os
import re

import pytest
from django.contrib.auth import get_user_model

from books.models import Profile

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.booksscreens, pytest.mark.django_db]
User = get_user_model()

PASSWORD = "books-screens-4412"
PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 800}
ALARM_WORDS = ["Traceback", "None", "null", "undefined", "Error", "{{", "{%"]

CONTRAST_JS = r"""() => {
    const srgb = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
    const parse = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
    const bad = [];
    document.querySelectorAll('body *').forEach((el) => {
        const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).map((n) => n.textContent.trim()).join(' ');
        if (!own) return;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
        if (!el.getClientRects().length) return;
        if (el.closest('.bk-spine')) return;  // spine colours are the book's own
        let node = el, bg = null;
        while (node && node !== document.documentElement) {
            const s = getComputedStyle(node);
            if (s.backgroundImage && s.backgroundImage !== 'none' && !node.classList.contains('bk-room')) return;
            const c = parse(s.backgroundColor);
            if (c.length === 3 && !/rgba\(.*,\s*0\)/.test(s.backgroundColor)) { bg = c; break; }
            node = node.parentElement;
        }
        if (!bg) { bg = parse(getComputedStyle(document.body).backgroundColor); }
        const size = parseFloat(cs.fontSize);
        const weight = parseInt(cs.fontWeight, 10) || 400;
        const large = size >= 24 || (size >= 18.66 && weight >= 700);
        const need = large ? 3 : 4.5;
        const got = ratio(parse(cs.color), bg);
        if (got + 0.005 < need) bad.push(`${got.toFixed(2)}:1 (needs ${need}) ${cs.fontSize} "${own.slice(0, 32)}"`);
    });
    return [...new Set(bad)];
}"""

OVERFLOW_JS = """() => {
    const limit = document.documentElement.clientWidth;
    const wide = [];
    document.querySelectorAll('body *').forEach(el => {
        if (el.closest('.bk-shelf-scroll')) return;  // the shelf scrolls sideways on purpose
        const r = el.getBoundingClientRect();
        if ((r.width > limit + 1 || r.right > limit + 1 || r.left < -1) && r.height > 0)
            wide.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + ' w=' + Math.round(r.width));
    });
    return [...new Set(wide)].slice(0, 6);
}"""

TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1, bad = [];
    document.querySelectorAll('a, button, input[type=checkbox], input[type=radio], select').forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden' || el.classList.contains('bk-skip')) return;
        if (el.classList.contains('bk-spine')) return;  // adjacent by nature, like keys; min width 24px is set in shelf.js
        if (el.tagName === 'A' && el.closest('p, .bk-footer, .bk-check')) return;
        if (el.type === 'radio' || el.type === 'checkbox') el = el.closest('label') || el;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => (x < 1 || y < 1 || x > innerWidth - 1 || y > innerHeight - 1) ? null : document.elementFromPoint(x, y);
        const hits = (n) => n && (n === el || el.contains(n));
        if (!hits(at(cx, cy))) return;
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]].some(([x, y]) => { const n = at(x, y); return n !== null && !hits(n); });
        if (missed) bad.push((el.getAttribute('aria-label') || el.textContent || el.className).trim().slice(0, 28) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    });
    return [...new Set(bad)];
}"""

A11Y_JS = """() => {
    const bad = [];
    document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) bad.push('img without alt'); });
    document.querySelectorAll('button, a').forEach(b => {
        const text = (b.textContent || '').trim();
        if (!text && !b.getAttribute('aria-label') && !b.getAttribute('title')) bad.push('unlabelled ' + b.tagName);
    });
    document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(i => {
        const labelled = i.closest('label') || (i.id && document.querySelector('label[for="' + i.id + '"]')) || i.getAttribute('aria-label');
        if (!labelled) bad.push('unlabelled field ' + (i.name || i.type));
    });
    if (!document.querySelector('main')) bad.push('no main');
    if (!document.documentElement.getAttribute('lang')) bad.push('no lang');
    return bad;
}"""


def build_world():
    from django.core.management import call_command

    from books import catalog
    from books.models import EntryCorrection

    reader = User.objects.create_user("reader", "reader@example.com", PASSWORD)
    rp = Profile.objects.create(user=reader, display_name="נועה", is_adult_confirmed=True)
    staff = User.objects.create_user("staff", "staff@example.com", PASSWORD, is_staff=True)
    Profile.objects.create(user=staff, display_name="אבי", is_adult_confirmed=True)
    fresh = User.objects.create_user("fresh", "fresh@example.com", PASSWORD)
    call_command("seed_books", verbosity=0)
    # A small real catalogue: two of the same title for the curator's desk,
    # an open correction, a verified record with a publisher and an ISBN.
    a = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", year=1968,
                                            language="he", is_verified=True, pk=1001)
    catalog.set_creators(a, ["עמוס עוז"])
    catalog.add_identifier(a, "isbn13", "9780156031608")
    catalog.BookDetail.objects.create(entry=a, publisher="עם עובד", pages=220)
    b = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", created_by=rp)
    catalog.set_creators(b, ["עמוס עוז"])
    c = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Jane Eyre", year=1847)
    catalog.set_creators(c, ["Charlotte Brontë"])
    EntryCorrection.objects.create(entry=a, profile=rp, field="year", value="1968", note="בדקתי")

    # A scan waiting for confirmation, the way the job leaves it.
    import io as _io

    from django.core.files.base import ContentFile
    from PIL import Image as _Image

    from books.models import Copy, ScanCandidate, ScanItem, ShelfScan

    buf = _io.BytesIO(); _Image.new("RGB", (800, 400), (110, 80, 50)).save(buf, format="JPEG")
    scan = ShelfScan(pk=2001, owner=rp, shelf_label="סלון, מדף עליון", status=ShelfScan.REVIEW, books_found=3,
                     default_visibility="private")
    scan.photo.save("screens.jpg", ContentFile(buf.getvalue()), save=False)
    scan.save()
    i1 = ScanItem.objects.create(scan=scan, position=0, raw_title="מיכאל שלי", raw_author="עמוס עוז", confidence="0.95")
    ScanCandidate.objects.create(item=i1, entry=a, confidence="0.95", rank=0)
    ScanCandidate.objects.create(item=i1, entry=b, confidence="0.90", rank=1)
    ScanItem.objects.create(scan=scan, position=1, raw_title="ספר שלא זוהה", raw_author="")
    ScanItem.objects.create(scan=scan, position=2, raw_title="Jane Eyre", raw_author="Charlotte Brontë",
                            review_status=ScanItem.SKIPPED)

    # Someone whose shelf has books on it.
    shelver = User.objects.create_user("shelver", "shelver@example.com", PASSWORD)
    sp = Profile.objects.create(user=shelver, display_name="דנה", is_adult_confirmed=True)
    for i, e in enumerate((a, b, c)):
        Copy.objects.create(owner=sp, entry=e, position=i, visibility="public" if i else "private")
    ShelfScan.objects.create(owner=sp, status=ShelfScan.REVIEW, photo="x.jpg")
    first = Copy.objects.filter(owner=sp).order_by("position").first()
    first.pk  # the copy page below is the shelver's first book
    from books.models import Wish
    Wish.objects.create(profile=sp, entry=c)
    Wish.objects.create(profile=sp, free_text="ספר שעוד לא בקטלוג")

    # The hub (BK5): both in the same neighbourhood, the shelver's public
    # books offered, and one loan the reader asked for and was approved.
    from books import hub
    from books.models import MeetingPlace, Offer
    Profile.objects.filter(pk__in=[rp.pk, sp.pk]).update(area_name="הדר")
    rp.refresh_from_db()
    sp.refresh_from_db()
    lent, sold = Copy.objects.filter(owner=sp, visibility="public").order_by("position")
    Offer.objects.create(copy=lent, kind="lend", loan_days=30)
    Offer.objects.create(copy=sold, kind="sell", price_amount=35)
    Offer.objects.create(copy=sold, kind="exchange", wants_note="ספרי מדע בדיוני")
    MeetingPlace.objects.create(name="הספרייה העירונית", area_name="הדר")
    deal = hub.ask(rp, lent, "lend", "שלום, אשמח לשאול אותו לחודש")
    hub.approve(deal, sp)
    hub.send_message(deal, sp, "בשמחה. מתי נוח לך?")

    # Circles (BK6): the shelver owns a private club the reader is in, with a
    # partner cafe; an open neighbourhood circle the reader is not in; feedback.
    from books import circles
    from books.models import Feedback
    club = circles.create(sp, "מועדון הקריאה של הדר", "club", "הדר", "נפגשים כל חודש", is_private=True)
    Circle = type(club)
    Circle.objects.filter(pk=club.pk).update(join_code="HADAR247")
    club.refresh_from_db()
    circles.join(rp, club, club.join_code)
    circles.add_place(sp, club, "בית הקפה של השכונה", "הדר", "cafe", is_partner=True)
    circles.create(sp, "שכונת נווה שאנן", "neighbourhood", "נווה שאנן", is_private=False)
    Feedback.objects.create(profile=rp, path="/books/near/", body="הכפתור לבקשה קטן מדי בטלפון")

    # The club (BK7): an open discussion about a book with comments (one hidden),
    # a book report inside the club, a review, a reading log, a public profile.
    from books import community
    th = community.start_thread(sp, "discussion", "מי קרא את מיכאל שלי?", "ומה חשבתם על הסוף?", entry=a)
    community.reply(rp, th, "קראתי לפני שנים. הסוף נשאר איתי.")
    hidden = community.reply(rp, th, "תגובה שהוסתרה")
    community.hide_post(Profile.objects.get(user=staff), hidden)
    community.start_thread(rp, "report", "דוח קריאה: ג׳יין אייר", "רשימה ארוכה על הספר.\n\nפסקה שנייה.",
                           circle=club, entry=c)
    community.set_review(sp, a, 4, "יפה ועצוב.")
    community.set_review(rp, a, 5, "הסוף מפתיע.", has_spoilers=True)
    community.log_reading(rp, a, "read")
    community.log_reading(rp, c, "reading")
    Profile.objects.filter(pk=sp.pk).update(profile_public=True, public_library=True, public_reviews=True,
                                            show_points_public=True)

    # Play (BK8): a reading streak with a freeze, points, a badge, a board.
    from datetime import timedelta

    from books import play
    for i in range(8, 0, -1):
        play.checkin(rp, day=play.today() - timedelta(days=i))
    play.book_confirmed(rp, a)
    play.book_confirmed(sp, c)
    return {"reader": reader, "staff": staff, "fresh": fresh}


# (label, path, who, screen marker)
SCREENS = [
    ("login", "/books/login/", None, "login"),
    ("signup", "/books/signup/", None, "signup"),
    ("reset", "/books/password/reset/", None, "password-reset"),
    ("404", "/books/nope/", None, "404"),
    ("terms", "/books/terms/", None, "terms"),
    ("onboarding", "/books/welcome/", "fresh", "onboarding"),
    ("home-empty", "/books/", "reader", "home"),
    ("settings", "/books/settings/", "reader", "settings"),
    ("my-data", "/books/me/data/", "reader", "my-data"),
    ("design", "/books/design/", "staff", "design"),
    ("catalog-empty", "/books/catalog/", "reader", "catalog"),
    ("catalog-results", "/books/catalog/?q=עוז", "reader", "catalog"),
    ("catalog-none", "/books/catalog/?q=zzzz", "reader", "catalog"),
    ("catalog-entry", "/books/catalog/1001/", "reader", "catalog-entry"),
    ("catalog-new", "/books/catalog/new/", "reader", "catalog-new"),
    ("catalog-tag", "/books/catalog/tag/fiction/", "reader", "catalog-tag"),
    ("curate", "/books/curate/", "staff", "curate"),
    ("scan-new", "/books/scan/", "reader", "scan-new"),
    ("scan-review", "/books/scan/2001/", "reader", "scan-review"),
    ("home-shelf", "/books/", "shelver", "home"),
    ("library", "/books/library/", "shelver", "library"),
    ("library-empty", "/books/library/", "reader", "library"),
    ("copy", lambda: f"/books/copy/{__import__('books.models', fromlist=['Copy']).Copy.objects.order_by('pk').first().pk}/", "shelver", "copy"),
    ("library-add", "/books/library/add/?q=עוז", "shelver", "library-add"),
    ("wishlist", "/books/wishlist/", "shelver", "wishlist"),
    ("scans", "/books/library/scans/", "shelver", "scans"),
    ("near", "/books/near/", "reader", "near"),
    ("near-no-area", "/books/near/", "staff", "near"),
    ("offered", lambda: f"/books/near/{__import__('books.models', fromlist=['Copy']).Copy.objects.filter(offers__kind='sell').first().pk}/", "reader", "offered"),
    ("deals", "/books/deals/", "reader", "deals"),
    ("deal-borrower", lambda: f"/books/deals/{__import__('books.models', fromlist=['Deal']).Deal.objects.get().pk}/", "reader", "deal"),
    ("deal-owner", lambda: f"/books/deals/{__import__('books.models', fromlist=['Deal']).Deal.objects.get().pk}/", "shelver", "deal"),
    ("notifications", "/books/notifications/", "reader", "notifications"),
    ("circles", "/books/circles/", "reader", "circles"),
    ("circles-empty", "/books/circles/", "staff", "circles"),
    ("circle-owner", lambda: f"/books/circles/{__import__('books.models', fromlist=['Circle']).Circle.objects.get(is_private=True).pk}/", "shelver", "circle"),
    ("circle-member", lambda: f"/books/circles/{__import__('books.models', fromlist=['Circle']).Circle.objects.get(is_private=True).pk}/", "reader", "circle"),
    ("circle-open-outside", lambda: f"/books/circles/{__import__('books.models', fromlist=['Circle']).Circle.objects.get(is_private=False).pk}/", "reader", "circle"),
    ("circle-join", "/books/join/HADAR247/", "staff", "circle-join"),
    ("pilot", "/books/pilot/", "staff", "pilot"),
    ("club", "/books/club/", "reader", "club"),
    ("club-empty", "/books/club/?q=zzzz", "reader", "club"),
    ("thread-new", "/books/club/new/?kind=report&entry=1001", "reader", "thread-new"),
    ("thread-author", lambda: f"/books/club/{__import__('books.models', fromlist=['Thread']).Thread.objects.get(kind='discussion').pk}/", "shelver", "thread"),
    ("thread-mod", lambda: f"/books/club/{__import__('books.models', fromlist=['Thread']).Thread.objects.get(kind='discussion').pk}/", "staff", "thread"),
    ("my-reading", "/books/reading/", "reader", "my-reading"),
    ("people", "/books/people/", "reader", "people"),
    ("person", lambda: f"/books/people/{__import__('books.models', fromlist=['Profile']).Profile.objects.get(user__username='shelver').pk}/", "reader", "person"),
    ("play", "/books/play/", "reader", "play"),
    ("play-empty", "/books/play/", "staff", "play"),
    ("year", "/books/year/", "reader", "year"),
    ("person-me", lambda: f"/books/people/{__import__('books.models', fromlist=['Profile']).Profile.objects.get(user__username='reader').pk}/", "reader", "person"),
]


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")


def _open(browser, live_server, who, path, viewport, theme, lang="he"):
    context = browser.new_context(viewport=viewport, device_scale_factor=1, is_mobile=viewport is PHONE,
                                  has_touch=viewport is PHONE, locale="he-IL" if lang == "he" else "en-US")
    page = context.new_page()
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    if who:
        page.goto(f"{live_server.url}/books/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', f"{who}@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click('form.bk-form button[type="submit"]')
        page.wait_for_timeout(300)
        assert "/login/" not in page.url, f"could not sign in as {who}"
    # The theme and language are session choices, set through the real switches.
    page.goto(f"{live_server.url}/books/login/", wait_until="domcontentloaded")
    page.evaluate("""([theme, lang]) => {
        const csrf = document.body.getAttribute('data-csrf');
        const post = (url) => fetch(url, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: new URLSearchParams({next: '/books/login/'})});
        return post('/books/theme/' + theme + '/').then(() => post('/books/lang/' + lang + '/'));
    }""", [theme, lang])
    page.goto(live_server.url + path, wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    return context, page, dialogs


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("label,path,who,screen", SCREENS, ids=[s[0] for s in SCREENS])
def test_screen_contract(browser, live_server, db, label, path, who, screen, theme, viewport):
    build_world()
    if callable(path):
        path = path()
    context, page, dialogs = _open(browser, live_server, who, path, viewport, theme)
    try:
        assert page.get_attribute("body", "data-screen") == screen, page.url
        assert page.get_attribute("html", "data-theme") == theme
        assert page.locator("h1").count() >= 1
        text = page.evaluate("() => document.body.innerText")
        assert len(text.strip()) > 20
        for word in ALARM_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", text), f"{label}: '{word}' reached the reader"
        assert not dialogs
        assert page.evaluate(OVERFLOW_JS) == [], f"{label} {viewport['width']}: overflows"
        assert page.evaluate(CONTRAST_JS) == [], f"{label} {theme}: contrast"
        assert page.evaluate(TAP_JS, 44) == [], f"{label}: tap targets"
        assert page.evaluate(A11Y_JS) == [], f"{label}: accessibility"
    finally:
        context.close()


def test_the_shelf_lifts_a_book_and_shows_its_label(browser, live_server, db):
    build_world()
    context, page, _ = _open(browser, live_server, "staff", "/books/design/", PHONE, "light")
    try:
        shelf = page.locator('[data-shelf-view="lamp"]')
        spines = shelf.locator(".bk-spine")
        assert spines.count() >= 8
        # One book is lifted on load (the sample's rare one) and labelled.
        assert shelf.locator(".bk-spine.is-lifted").count() == 1
        label = page.locator("#sample-lamp-label")
        assert label.is_visible() and "אלטנוילנד" in label.inner_text()
        # Tapping another spine lifts it instead and the label follows.
        spines.nth(0).click()
        page.wait_for_timeout(350)
        assert shelf.locator(".bk-spine.is-lifted").count() == 1
        assert spines.nth(0).get_attribute("aria-pressed") == "true"
        assert "מיכאל שלי" in label.inner_text()
        # Tapping it again puts it back.
        spines.nth(0).click()
        page.wait_for_timeout(350)
        assert shelf.locator(".bk-spine.is-lifted").count() == 0
        assert label.is_hidden()
        # Keyboard: arrows walk the shelf.
        spines.nth(1).focus()
        page.keyboard.press("ArrowRight")
        assert page.evaluate("() => document.activeElement.getAttribute('data-book')") == "s3"
        # The spine's title really is vertical and the colour really is the book's.
        assert page.evaluate("() => getComputedStyle(document.querySelector('.bk-spine-title')).writingMode") == "vertical-rl"
        assert page.evaluate("() => getComputedStyle(document.querySelector('.bk-spine[data-book=\"s1\"]')).backgroundColor") == "rgb(107, 35, 32)"
    finally:
        context.close()


def test_the_english_home_is_left_to_right(browser, live_server, db):
    build_world()
    context, page, _ = _open(browser, live_server, "reader", "/books/", PHONE, "light", lang="en")
    try:
        assert page.get_attribute("html", "dir") == "ltr"
        assert "Your books will stand here" in page.inner_text("main")
        # The wordmark sits at the start edge: on the left in English.
        box = page.locator(".bk-wordmark").bounding_box()
        assert box["x"] < 100
    finally:
        context.close()


def test_the_bookcase_and_living_views_render_their_spines(browser, live_server, db):
    build_world()
    context, page, _ = _open(browser, live_server, "staff", "/books/design/", DESKTOP, "dark")
    try:
        case = page.locator('[data-shelf-view="bookcase"]')
        assert case.locator(".bk-case-back").count() == 2
        assert case.locator(".bk-spine").count() >= 8
        living = page.locator('[data-shelf-view="living"]')
        assert living.locator(".bk-spine").count() >= 8
        # Drag the first spine past the third; the order changes and the shelf relays out.
        first = living.locator(".bk-spine").nth(0)
        third = living.locator(".bk-spine").nth(2)
        first.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        b1, b3 = first.bounding_box(), third.bounding_box()
        page.mouse.move(b1["x"] + b1["width"] / 2, b1["y"] + b1["height"] / 2)
        page.mouse.down()
        page.mouse.move(b3["x"] + b3["width"] + 10, b1["y"] + b1["height"] / 2, steps=8)
        page.mouse.up()
        page.wait_for_timeout(400)
        order = page.evaluate("() => [...document.querySelectorAll('[data-shelf-view=\"living\"] .bk-spine')].sort((a,b)=>parseFloat(a.style.getPropertyValue('--spine-left'))-parseFloat(b.style.getPropertyValue('--spine-left'))).map(s=>s.dataset.book)")
        assert order[0] != "s1" and "s1" in order[:4]
    finally:
        context.close()
