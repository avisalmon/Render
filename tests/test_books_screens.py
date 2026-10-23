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

OVERFLOW_JS = """(expected) => {
    // A page wider than a phone makes a mobile browser zoom out, and then
    // clientWidth grows with it: measure against the device's own width too.
    const limit = Math.min(document.documentElement.clientWidth, expected || 1e9);
    const wide = document.documentElement.scrollWidth > limit + 1 ? ['html w=' + document.documentElement.scrollWidth] : [];
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

    # Discovery (BK9): tags on the records, the reader's taste, a suggestion
    # that is also offered nearby (the shelver's Jane Eyre).
    from books import discover
    from books.models import Tag
    a.tags.add(*Tag.objects.filter(key__in=["literary-fiction", "israeli-fiction", "emotional"]))
    c.tags.add(*Tag.objects.filter(key__in=["classics", "romance", "emotional"]))
    hobbit = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ההוביט", year=1937)
    catalog.set_creators(hobbit, ["J.R.R. Tolkien"])
    hobbit.tags.add(*Tag.objects.filter(key__in=["fantasy", "classics", "hopeful"]))
    discover.set_survey(rp, ["classics", "fantasy", "emotional"], ["thriller"])

    # Rare books and the museum (BK10): an old signed copy of the shelver's,
    # confirmed by a curator, accepted into a published exhibition; another
    # waiting on the curator's desk; an invitation the reader has not answered.
    from books import rare
    from books.models import CopyPhoto
    staff_p = Profile.objects.get(user=staff)

    def photo_for(copy, kind):
        buf = _io.BytesIO()
        _Image.new("RGB", (300, 400), (190, 170, 140)).save(buf, format="JPEG")
        ph = CopyPhoto(copy=copy, kind=kind)
        ph.image.save(f"museum-{copy.pk}-{kind}.jpg", ContentFile(buf.getvalue()), save=True)

    hasamba = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="חסמב״ה", year=1950)
    catalog.set_creators(hasamba, ["יגאל מוסינזון"])
    signed = Copy.objects.create(owner=sp, entry=hasamba, notes="חתום על ידי המחבר", position=50)
    photo_for(signed, "signed")
    review = rare.send_for_review(sp, signed, "חתימה של המחבר בעמוד הראשון")
    rare.decide(staff_p, review, True, "חתימה מקורית, מהדורה ראשונה")
    ex = rare.new_exhibit(staff_p, "חתימות של סופרים", "Authors' signatures", "עותקים חתומים מספריות החברים.")
    item = rare.invite(staff_p, ex, signed, "הקדשה בכתב ידו של המחבר.")
    rare.answer(sp, item, True, show_name=True, show_photos=True)
    rare.publish(staff_p, ex)
    old = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר ישן מאוד", year=1938)
    # The staff member's own copy (the reader's home must stay empty for the
    # empty-home screens).
    waiting = Copy.objects.create(owner=staff_p, entry=old, position=60)
    photo_for(waiting, "copyright_page")
    rare.send_for_review(staff_p, waiting, "נראה לי מהדורה ראשונה")

    # Tiers (BK11): the shelver applied the code; the reader is on the free tier.
    from books import tiers
    from books.models import Coupon
    # Live-server tests empty the database between tests, migration data too.
    Coupon.objects.get_or_create(code="helpavi", defaults={"tier": "plus", "days": 90})
    tiers.redeem(sp, "helpavi")

    # Reading sessions: the reader read Jane Eyre twice (one ended session to
    # summarise); the staff member has one running (the timer screen).
    from datetime import timedelta as _td

    from django.utils import timezone as _tz

    from books import reading
    from books.models import BookDetail, ReadingSession
    BookDetail.objects.update_or_create(entry=c, defaults={"pages": 420})
    for minutes, frm, to, ago in ((25, 0, 48, 1), (18, 48, 80, 0)):
        sess = reading.start(rp, c, frm)
        begun = _tz.now() - _td(days=ago, minutes=minutes)
        ReadingSession.objects.filter(pk=sess.pk).update(started_at=begun)
        sess.refresh_from_db()
        reading.end(rp, sess, to, now=begun + _td(minutes=minutes))
    running = reading.start(staff_p, hasamba, 12)
    ReadingSession.objects.filter(pk=running.pk).update(started_at=_tz.now() - _td(minutes=7))
    return {"reader": reader, "staff": staff, "fresh": fresh}


def _follow_and_shelf(viewer, owner):
    """A friend's shelf: the viewer follows the owner (Avi, 2026-10-22)."""
    from books.models import Follow, Profile
    v = Profile.objects.get(user__username=viewer)
    o = Profile.objects.get(user__username=owner)
    Follow.objects.get_or_create(follower=v, followee=o, defaults={"status": Follow.ACCEPTED, "source": Follow.INVITE})
    return f"/books/people/{o.pk}/shelf/"


# (label, path, who, screen marker)
SCREENS = [
    ("landing", "/books/", None, "landing"),
    ("landing-invited", lambda: f"/books/i/{__import__('books.friends', fromlist=['invite_for']).invite_for(__import__('books.models', fromlist=['Profile']).Profile.objects.get(user__username='shelver')).code}/", None, "landing"),
    ("login", "/books/login/", None, "login"),
    ("scan-book", "/books/scan/?book=1", "reader", "scan-new"),
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
    ("first-read", "/books/read/first/1001/", "reader", "first-read"),
    ("friends", "/books/friends/?q=sh", "reader", "friends"),
    ("friends-home", "/books/friends/", "reader", "friends"),
    ("friends-all", "/books/friends/all/", "reader", "friends-all"),
    ("friend-shelf", lambda: _follow_and_shelf("reader", "shelver"), "reader", "friend-shelf"),
    ("friend-closed", lambda: f"/books/people/{__import__('books.models', fromlist=['Profile']).Profile.objects.get(user__username='staff').pk}/shelf/", "reader", "friend-shelf"),
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
    ("discover", "/books/discover/", "reader", "discover"),
    ("discover-empty", "/books/discover/", "staff", "discover"),
    ("taste", "/books/taste/", "reader", "taste"),
    ("taste-first", "/books/taste/?first=1", "staff", "taste"),
    ("museum", "/books/museum/", "reader", "museum"),
    ("museum-staff", "/books/museum/", "staff", "museum"),
    ("exhibit", lambda: f"/books/museum/{__import__('books.models', fromlist=['Exhibit']).Exhibit.objects.get().pk}/", "reader", "exhibit"),
    ("exhibit-staff", lambda: f"/books/museum/{__import__('books.models', fromlist=['Exhibit']).Exhibit.objects.get().pk}/", "staff", "exhibit"),
    ("rare-desk", "/books/curate/rare/", "staff", "rare-desk"),
    ("copy-rare", lambda: f"/books/copy/{__import__('books.models', fromlist=['Copy']).Copy.objects.get(entry__title='חסמב״ה').pk}/", "shelver", "copy"),
    ("copy-rare-waiting", lambda: f"/books/copy/{__import__('books.models', fromlist=['Copy']).Copy.objects.get(entry__title='ספר ישן מאוד').pk}/", "staff", "copy"),
    ("plans", "/books/plans/", "reader", "plans"),
    ("plans-plus", "/books/plans/?redeemed=1", "shelver", "plans"),
    ("read-start", "/books/read/", "reader", "read"),
    ("read-session", "/books/read/", "staff", "read-session"),
    ("history", "/books/history/", "reader", "history"),
    ("read-summary", lambda: f"/books/read/{__import__('books.models', fromlist=['ReadingSession']).ReadingSession.objects.filter(ended_at__isnull=False).order_by('-ended_at').first().pk}/", "reader", "read-summary"),
    ("person-me", lambda: f"/books/people/{__import__('books.models', fromlist=['Profile']).Profile.objects.get(user__username='reader').pk}/", "reader", "person"),
]


@pytest.fixture(autouse=True)
def _no_background_sweeps(settings):
    # The enrichment sweep starts a thread from page views; in a live-server
    # test it would still be writing while the test database is torn down
    # ("database table is locked", foreign key errors). Its own tests cover it.
    settings.BOOKS_ENRICH_SWEEP = False
    # Mail for requests runs as a job; on a thread it would write while the live
    # server's request holds the test database ("database table is locked").
    settings.BOOKS_JOBS_INLINE = True


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
        page.click(".bk-login-other > summary")  # the password is the other way in
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
        assert page.evaluate(OVERFLOW_JS, viewport["width"]) == [], f"{label} {viewport['width']}: overflows"
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
        page.wait_for_timeout(450)  # with a mouse, hold to pick a book up; a drag pans (Avi, 2026-10-22)
        page.mouse.move(b3["x"] + b3["width"] + 10, b1["y"] + b1["height"] / 2, steps=8)
        page.mouse.up()
        page.wait_for_timeout(400)
        order = page.evaluate("() => [...document.querySelectorAll('[data-shelf-view=\"living\"] .bk-spine')].sort((a,b)=>parseFloat(a.style.getPropertyValue('--spine-left'))-parseFloat(b.style.getPropertyValue('--spine-left'))).map(s=>s.dataset.book)")
        assert order[0] != "s1" and "s1" in order[:4]
    finally:
        context.close()


# Avi, 2026-10-20: "I want to see immediately the books in front of my eyes."
# On a phone, the first row of every list screen starts in the top half of
# the first screen: options live in a menu, search and filters fold.
CONTENT_FIRST = [
    ("library", "/books/library/", "shelver"),
    ("near", "/books/near/", "reader"),
    ("club", "/books/club/", "reader"),
    ("catalog", "/books/catalog/?q=%D7%9E%D7%99%D7%9B%D7%90%D7%9C", "reader"),
    ("deals", "/books/deals/", "reader"),
    ("discover", "/books/discover/", "reader"),
    ("notifications", "/books/notifications/", "reader"),
    ("my-reading", "/books/reading/", "reader"),
]


@pytest.mark.parametrize("label,path,who", CONTENT_FIRST, ids=[c[0] for c in CONTENT_FIRST])
def test_on_a_phone_the_list_comes_first(browser, live_server, db, label, path, who):
    build_world()
    context, page, _ = _open(browser, live_server, who, path, PHONE, "light")
    try:
        top = page.evaluate("() => { const r = document.querySelector('.bk-entry-list .bk-entry-row');"
                            " return r ? r.getBoundingClientRect().top : null; }")
        assert top is not None, f"{label}: no list row"
        assert top < PHONE["height"] / 2, f"{label}: the first row starts at {top:.0f}px of {PHONE['height']}"
    finally:
        context.close()


def test_on_a_phone_a_reader_can_find_a_book_start_and_finish(browser, live_server, db):
    """The task, not the page (Avi, 2026-10-20: "no search, no Start button"):
    on a phone, type part of a title, tap the book, tap Start, see the timer,
    enter a page, tap I'm done, see the summary."""
    from books import catalog
    from books.models import Copy, Profile, ReadingSession
    build_world()
    rp = Profile.objects.get(user__username="reader")
    for i in range(20):
        e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title=f"ספר מספר {i + 1}")
        Copy.objects.create(owner=rp, entry=e, position=i)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        page.fill("[data-read-search]", "מספר 17")
        page.wait_for_timeout(200)
        start = page.locator(".bk-read-row:not([hidden]) details[open] button[type=submit]")
        assert start.count() == 1 and start.is_visible()
        page.locator(".bk-read-row:not([hidden]) input[name=page]").fill("12")
        start.click()
        # A book read for the first time stops at its first screen (Avi, 2026-10-22): cover, length, go.
        page.wait_for_selector("[data-first]")
        assert page.input_value("[data-first] input[name=page]") == "12"
        page.fill("[data-first-pages]", "240")
        page.click(".bk-first-go button[type=submit]")
        page.wait_for_selector("[data-timer]")
        assert ReadingSession.objects.get(ended_at__isnull=True, profile=rp).start_page == 12
        page.fill("input[name=end_page]", "20")
        page.click("form[action$='/end/'] button[type=submit]")
        page.wait_for_load_state("domcontentloaded")
        assert page.url.rstrip("/").endswith("/books") and page.locator("[data-streak-moment]").count() == 0  # straight home; a few seconds do not count a day
        assert ReadingSession.objects.get(profile=rp, entry__title="ספר מספר 17").end_page == 20
    finally:
        context.close()


def test_on_a_phone_a_thought_is_saved_while_the_timer_runs(browser, live_server, db):
    """Avi, 2026-10-21: "what I think" while reading, typed. "Type instead"
    opens the card with the keyboard, "save the thought" saves it and the
    card closes; the count opens the earlier thoughts."""
    from books import catalog, notes, reading
    from books.models import Profile, ReadingNote
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר עם מחשבות")
    notes.add(rp, e, "מחשבה ראשונה")
    reading.start(rp, e, 7)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        assert page.evaluate("document.activeElement.matches('[data-voice-text]')") is False
        page.click("[data-think-type]")
        assert page.is_visible("[data-think-card]")
        page.fill("[data-think] [data-voice-text]", "השורה על הים")
        page.click("[data-think] button[type=submit]")
        page.wait_for_function("document.querySelector('[data-think-card]').hidden")
        assert page.text_content("[data-notes-count]").strip() == "2" and page.locator("[data-timer]").count() == 1
        assert ReadingNote.objects.filter(profile=rp).order_by("pk").last().body == "השורה על הים"
        page.click("[data-think] [data-notes-open]")
        page.wait_for_selector("dialog[data-notes][open]")
        assert page.locator("[data-notes-list] li").count() == 2
        page.click("[data-notes-close]")
    finally:
        context.close()


FAKE_MIC = """
delete window.SpeechRecognition; delete window.webkitSpeechRecognition;
navigator.mediaDevices.getUserMedia = () => Promise.resolve({getTracks: () => [{stop() {}}]});
window.MediaRecorder = class {
  constructor(s, o) { this.state = 'inactive'; this.mimeType = 'audio/webm'; }
  static isTypeSupported() { return true; }
  start() { this.state = 'recording'; }
  stop() { this.state = 'inactive'; this.ondataavailable({data: new Blob(['x'], {type: 'audio/webm'})}); this.onstop(); }
};
"""


def test_on_a_phone_one_tap_listens_and_the_words_are_saved(browser, live_server, db, settings):
    """Avi, 2026-10-21: the breathing button listens at once; a second tap
    stops, the words come back with "save the thought". The microphone and
    the transcription are stood in for; everything else is real."""
    import json

    from books import catalog, reading
    from books.models import Profile, ReadingNote
    settings.OPENAI_API_KEY = "sk-test"
    settings.BOOKS_VOICE_PAID = True
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר מדבר")
    reading.start(rp, e, 40)
    context, page, _ = _open(browser, live_server, "reader", "/books/", PHONE, "light")
    try:
        page.add_init_script(FAKE_MIC)
        page.route("**/books/read/voice/", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps({"text": "המשפט על הגשם"})))
        page.goto(f"{live_server.url}/books/read/", wait_until="domcontentloaded")
        page.wait_for_selector("[data-orb][data-voice-mic]")
        page.click("[data-orb]")
        page.wait_for_selector("[data-orb].is-on")
        assert page.is_hidden("[data-think-card]")
        page.click("[data-orb]")
        page.wait_for_selector("[data-think-card]:not([hidden])")
        assert page.input_value("[data-think] [data-voice-text]") == "המשפט על הגשם"
        assert page.evaluate("document.activeElement.matches('[data-voice-text]')") is False  # no keyboard
        page.click("[data-think] button[type=submit]")
        page.wait_for_function("document.querySelector('[data-think-card]').hidden")
        note = ReadingNote.objects.get(profile=rp)
        assert note.body == "המשפט על הגשם" and note.source == "voice"
    finally:
        context.close()


def test_on_a_phone_the_page_is_flicked_not_typed(browser, live_server, db):
    """Avi, 2026-10-21: a wheel to flick the pages, not a box to type in. A
    drag in the reading direction (right, in Hebrew) turns pages forward, the
    number and the form follow, a drag back turns them back, and never below
    the page I started from."""
    from books import catalog, reading
    from books.models import Profile, ReadingSession
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר לדפדוף")
    reading.start(rp, e, 30)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        page.wait_for_selector("[data-flip-pad]")
        # The wheel sits below the candle: scroll it to the middle, as a reader would.
        page.evaluate("document.querySelector('[data-flip-pad]').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(200)
        box = page.locator("[data-flip-pad]").bounding_box()
        y = box["y"] + box["height"] / 2
        x0 = box["x"] + box["width"] / 2 - 100
        page.mouse.move(x0, y)
        page.mouse.down()
        for i in range(1, 21):
            page.mouse.move(x0 + i * 10, y)  # 200px to the right, slowly: no glide
            page.wait_for_timeout(16)
        page.wait_for_timeout(120)
        page.mouse.up()
        page.wait_for_timeout(600)
        forward = int(page.input_value("input[name=end_page]"))
        assert forward > 40 and page.text_content("[data-flip-n]").strip() == str(forward)
        assert "עמודים היום" in page.text_content("[data-flip-read]")
        # Back past the start: it stops at the page I started from.
        page.mouse.move(x0 + 200, y)
        page.mouse.down()
        for i in range(1, 41):
            page.mouse.move(x0 + 200 - i * 12, y)
            page.wait_for_timeout(16)
        page.mouse.up()
        page.wait_for_timeout(900)
        assert int(page.input_value("input[name=end_page]")) == 30
        page.click("[data-flip-step='10']")
        page.click("form[action$='/end/'] button[type=submit]")
        page.wait_for_load_state("domcontentloaded")
        assert ReadingSession.objects.get(profile=rp, entry=e).end_page == 40
    finally:
        context.close()


def test_on_a_phone_finishing_the_book_celebrates_and_goes_home(browser, live_server, db):
    """Avi, 2026-10-21: a festive "I finished the book" button. The clock stops,
    fireworks go up, a summary can be written (or skipped), and the book is
    finished and I am home."""
    from books import catalog, reading
    from books.models import Profile, ReadingNote, ReadingSession
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר שנגמר")
    reading.start(rp, e, 250)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        page.click("[data-finish-open]")
        page.wait_for_selector("dialog[data-finish][open]")
        page.wait_for_timeout(400)
        assert ReadingSession.objects.get(entry=e).paused_at is not None  # the clock stopped
        drawn = page.evaluate("""() => { const c = document.querySelector('[data-sky]');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true; return false; }""")
        assert drawn  # something is in the sky
        page.fill("dialog[data-finish] [data-voice-text]", "ספר על זמן ועל בית")
        page.click("[data-finish-form] button[type=submit]:not([data-finish-skip])")
        page.wait_for_url("**/books/?finished=*")
        assert "כל הכבוד" in page.text_content(".bk-finished-note")
        s = ReadingSession.objects.get(entry=e)
        assert s.finished_book and s.end_page == 250
        note = ReadingNote.objects.get(entry=e)
        assert note.is_summary and note.body == "ספר על זמן ועל בית"
    finally:
        context.close()


def test_on_a_phone_the_streak_moment_plays_and_leaves_the_main_screen(browser, live_server, db):
    """Avi, 2026-10-21: like Duolingo, the day turns over with a "wow", then the
    main screen. Shown once: the address loses ?streak=1."""
    from datetime import timedelta

    from django.utils import timezone

    from books import catalog, reading
    from books.models import Profile, ReadingCheckin, ReadingSession
    build_world()
    rp = Profile.objects.get(user__username="reader")
    # The seeded world already counted today for this reader: start from a clean slate.
    ReadingCheckin.objects.filter(profile=rp).delete()
    ReadingSession.objects.filter(profile=rp).delete()
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר של רצף")
    s = reading.start(rp, e, 1)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=timezone.now() - timedelta(minutes=7))
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        page.click("form[action$='/end/'] button[type=submit]")
        page.wait_for_selector("[data-streak-moment]")
        assert "streak=1" not in page.url
        page.wait_for_timeout(2600)  # the roll, the week, the button
        assert page.text_content(".bk-sm-title").strip() == "רצף של 1 ימים!"
        roll = page.evaluate("getComputedStyle(document.querySelector('.bk-sm-roll')).transform")
        assert roll not in ("none", "matrix(1, 0, 0, 1, 0, 0)")  # rolled over to the new day
        page.click("[data-streak-close]")
        page.wait_for_selector("[data-streak-moment]", state="detached")
        assert page.locator(".bk-dial").count() == 1  # the main screen
    finally:
        context.close()


NARROW_PHONES = (320, 360, 375, 412)
NARROW_PATHS = [("landing", None, "/books/"), ("login", None, "/books/login/"), ("home", "shelver", "/books/"),
                ("library", "shelver", "/books/library/"), ("catalog", "reader", "/books/catalog/"),
                ("entry", "reader", "/books/catalog/1001/"), ("scan", "reader", "/books/scan/"),
                ("settings", "reader", "/books/settings/"), ("play", "reader", "/books/play/"),
                ("club", "reader", "/books/club/"), ("near", "reader", "/books/near/"), ("read", "shelver", "/books/read/"),
                ("friends", "reader", "/books/friends/"), ("history", "reader", "/books/history/"),
                ("friends-all", "reader", "/books/friends/all/"),
                ("friend-shelf", "reader", None)]


def test_on_every_phone_width_the_page_never_slides_sideways(browser, live_server, db):
    """Avi, 2026-10-21: "a little wider than the screen, it moves left and
    right". Checked at the narrow widths real phones have, not only at 390:
    the page itself is never wider than the screen, and the header fits."""
    from books import catalog
    from books.models import Copy, Profile
    build_world()
    # A long shelf: wide content is what pushes a page past the screen.
    sp = Profile.objects.get(user__username="shelver")
    for i in range(30):
        e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title=f"ספר ארוך {i}")
        Copy.objects.create(owner=sp, entry=e, position=300 + i, visibility="public")
    wide = []
    for w in NARROW_PHONES:
        for name, who, path in NARROW_PATHS:
            if path is None:
                path = _follow_and_shelf("reader", "shelver")
            ctx, page, _ = _open(browser, live_server, who, path, {"width": w, "height": 780}, "light")
            try:
                sw = page.evaluate("document.documentElement.scrollWidth")
                header = page.evaluate("document.querySelector('.bk-header').scrollWidth")
                if sw > w or header > w:
                    wide.append(f"{name}@{w}: page {sw}, header {header}")
                # The page clips sideways overflow (a safety net), which hides it from scrollWidth:
                # look at every element itself, outside the shelves that scroll on purpose.
                out = page.evaluate("""(w) => [...document.querySelectorAll('body *')].filter(el => {
                    if (el.closest('.bk-shelf-scroll, .bk-sm-burst')) return false;
                    const r = el.getBoundingClientRect();
                    return r.height > 0 && r.width > 0 && (r.right > w + 1 || r.left < -1);
                  }).slice(0, 4).map(el => el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0])""", w)
                if out:
                    wide.append(f"{name}@{w}: past the edge {out}")
                # An iPhone zooms into any field under 16px, and the zoomed page slides sideways.
                small = page.evaluate("""[...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')]
                    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.className)""")
                if small:
                    wide.append(f"{name}@{w}: fields under 16px {small}")
            finally:
                ctx.close()
    assert wide == []


def test_sign_out_lives_in_settings_too(client, db):
    build_world()
    from django.contrib.auth import get_user_model
    client.force_login(get_user_model().objects.get(username="reader"))
    html = client.get("/books/settings/").content.decode()
    assert '<form method="post" action="/books/logout/" class="bk-signout">' in html


FAKE_SPEECH = """
window.webkitSpeechRecognition = window.SpeechRecognition = class {
  start() { window.__lang = this.lang; setTimeout(() => this.onresult({resultIndex: 0, results: [Object.assign([{transcript: 'השורה על השקט'}], {isFinal: true})]}), 50); }
  stop() { setTimeout(() => this.onend(), 10); }
};
"""


def test_on_a_phone_the_phones_own_recognition_listens_in_hebrew_for_free(browser, live_server, db):
    """Avi, 2026-10-21: no tokens for my thoughts. The phone's recognition,
    in Hebrew; nothing is sent to the server but the saved words."""
    from books import catalog, reading
    from books.models import ModelCall, Profile, ReadingNote
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר שקט")
    reading.start(rp, e, 3)
    context, page, _ = _open(browser, live_server, "reader", "/books/", PHONE, "light")
    try:
        page.add_init_script(FAKE_SPEECH)
        voice_calls = []
        page.on("request", lambda r: voice_calls.append(r.url) if "/read/voice/" in r.url else None)
        page.goto(f"{live_server.url}/books/read/", wait_until="domcontentloaded")
        page.click("[data-orb]")
        page.wait_for_selector("[data-orb].is-on")
        assert page.evaluate("window.__lang") == "he-IL"
        page.wait_for_timeout(200)
        page.click("[data-orb]")
        page.wait_for_selector("[data-think-card]:not([hidden])")
        assert page.input_value("[data-think] [data-voice-text]") == "השורה על השקט"
        page.click("[data-think] button[type=submit]")
        page.wait_for_function("document.querySelector('[data-think-card]').hidden")
        assert ReadingNote.objects.get(profile=rp).source == "voice"
        assert voice_calls == [] and not ModelCall.objects.filter(purpose="voice_note").exists()
    finally:
        context.close()


FAKE_ANDROID_SPEECH = """
(() => {
  const r = (t, fin) => Object.assign([{transcript: t}], {isFinal: fin});
  // What Chrome on Android sends: finals sent again on every update, growing,
  // with resultIndex stuck at 0 (Avi, 2026-10-23: each thought written 3-4 times).
  const waves = [
    [r('אני חושב', false)],
    [r('אני חושב', true)],
    [r('אני חושב', true), r('אני חושב שהספר', true)],
    [r('אני חושב', true), r('אני חושב שהספר', true), r('אני חושב שהספר יפה', false)],
    [r('אני חושב', true), r('אני חושב שהספר', true), r('אני חושב שהספר יפה', true)],
  ];
  window.__speechText = null;
  window.webkitSpeechRecognition = window.SpeechRecognition = class {
    start() {
      const own = window.__speechText;
      const list = own ? [[r(own, true)], [r(own, true)], [r(own, true)]] : waves;
      list.forEach((w, i) => setTimeout(() => this.onresult({resultIndex: 0, results: w}), 20 + i * 20));
    }
    stop() { setTimeout(() => this.onend(), 10); }
  };
})();
"""


def test_a_spoken_thought_on_android_is_written_once_and_thoughts_add_up(browser, live_server, db):
    """Avi, 2026-10-23: whatever I said came back three or four times. Each
    thought is written once, and each saved thought joins the book's list."""
    from books import catalog, reading
    from books.models import Profile, ReadingNote
    build_world()
    rp = Profile.objects.get(user__username="reader")
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר מדבר")
    reading.start(rp, e, 3)
    context, page, _ = _open(browser, live_server, "reader", "/books/", PHONE, "light")
    try:
        page.add_init_script(FAKE_ANDROID_SPEECH)
        page.goto(f"{live_server.url}/books/read/", wait_until="domcontentloaded")
        for said in (None, "ועוד מחשבה על הסוף"):
            page.evaluate("t => { window.__speechText = t; }", said)
            page.click("[data-orb]")
            page.wait_for_selector("[data-orb].is-on")
            page.wait_for_timeout(250)
            page.click("[data-orb]")
            page.wait_for_selector("[data-think-card]:not([hidden])")
            assert page.input_value("[data-think] [data-voice-text]") == (said or "אני חושב שהספר יפה")
            page.click("[data-think] button[type=submit]")
            page.wait_for_function("document.querySelector('[data-think-card]').hidden")
        notes = list(ReadingNote.objects.filter(profile=rp, entry=e).order_by("pk").values_list("body", flat=True))
        assert notes == ["אני חושב שהספר יפה", "ועוד מחשבה על הסוף"]
        assert page.text_content("[data-notes-count]") == "2"
    finally:
        context.close()


def test_on_a_computer_the_mouse_pans_the_shelf_and_the_wheel_slides_it(browser, live_server, db):
    """Avi, 2026-10-22: on a computer the mouse moved the books, not the shelf.
    A drag pans the shelf and leaves the books where they are; the wheel slides
    it sideways; holding still is what picks a book up."""
    from books import catalog
    from books.models import Copy, Profile
    build_world()
    sp = Profile.objects.get(user__username="shelver")
    for i in range(40):
        e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title=f"ספר מדף {i}")
        Copy.objects.create(owner=sp, entry=e, position=200 + i)
    context, page, _ = _open(browser, live_server, "shelver", "/books/", DESKTOP, "light")
    try:
        sc = page.locator(".bk-shelf-scroll").first
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelector('.bk-shelf-scroll').scrollWidth > document.querySelector('.bk-shelf-scroll').clientWidth")
        order = "() => [...document.querySelectorAll('.bk-shelf-row .bk-spine')].map(s => s.dataset.book).join(',')"
        before_order = page.evaluate(order)
        start = page.evaluate("document.querySelector('.bk-shelf-scroll').scrollLeft")
        box = sc.bounding_box()
        y = box["y"] + box["height"] * 0.6
        page.mouse.move(box["x"] + box["width"] * 0.3, y)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] * 0.7, y, steps=10)
        page.mouse.up()
        page.wait_for_timeout(600)
        after_drag = page.evaluate("document.querySelector('.bk-shelf-scroll').scrollLeft")
        assert abs(after_drag - start) > 100 and page.evaluate(order) == before_order
        page.mouse.move(box["x"] + box["width"] * 0.5, y)
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelector('.bk-shelf-scroll').scrollLeft") != after_drag
    finally:
        context.close()


def test_a_tapped_book_grows_and_the_next_tap_puts_it_back(browser, live_server, db):
    """Avi, 2026-10-22: tap a book and it grows so I can see it; tap again
    and it is its size again; tap another and the first shrinks as it grows."""
    build_world()
    context, page, _ = _open(browser, live_server, "shelver", "/books/", PHONE, "light")
    try:
        spines = page.locator(".bk-shelf-row .bk-spine")
        first, second = spines.nth(0), spines.nth(2)  # a book still in sight beside the enlarged one
        row_h = page.evaluate("document.querySelector('.bk-shelf-row').offsetHeight")
        scale = "(el) => { const m = new DOMMatrix(getComputedStyle(el).transform); return Math.hypot(m.a, m.b); }"
        first.click()
        page.wait_for_timeout(900)
        assert first.evaluate(scale) > 1.25
        assert page.evaluate("document.querySelector('.bk-shelf-row').offsetHeight") > row_h + 100
        second.click()
        page.wait_for_timeout(900)
        assert abs(first.evaluate(scale) - 1) < 0.02 and second.evaluate(scale) > 1.25
        second.click()
        page.wait_for_timeout(900)
        assert abs(second.evaluate(scale) - 1) < 0.02
        assert page.evaluate("document.querySelector('.bk-shelf-row').offsetHeight") == row_h
    finally:
        context.close()


def test_on_a_phone_an_invited_person_lands_on_the_friends_shelf_with_its_pictures(browser, live_server, db):
    """Avi, 2026-10-22: the invited person's journey, made amazing. Open a
    friend's link: dark, the friend's name, their shelf from afar. Join with
    an email, one short form that still names the friend, and land on their
    shelf: friends now, dark, the real spine pictures loaded, and "your turn"."""
    from books import friends, shelf
    from books.models import Copy, Profile, ScanItem, ShelfScan
    from tests.test_books_spines import CORNERS, TITLES, shelf_photo
    from django.core.files.base import ContentFile
    build_world()
    sp = Profile.objects.get(user__username="shelver")
    sp.display_name = "משה"
    sp.save()
    scan = ShelfScan(owner=sp, status=ShelfScan.DONE, spines_done=True)
    scan.photo.save("s.jpg", ContentFile(shelf_photo()), save=False)
    scan.save()
    from books import catalog
    pairs = []
    for i, t in enumerate(TITLES):
        e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title=t)
        copy = Copy.objects.create(owner=sp, entry=e, position=i, visibility="private")
        pairs.append((ScanItem.objects.create(scan=scan, position=i, raw_title=t, copy=copy), CORNERS[i]))
    shelf.cut_spines(scan, pairs)
    code = friends.invite_for(sp).code
    context = browser.new_context(viewport=PHONE, device_scale_factor=1, is_mobile=True, has_touch=True, locale="he-IL")
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/books/i/{code}/?via=whatsapp", wait_until="domcontentloaded")
        assert page.get_attribute("html", "data-theme") == "dark"
        assert "משה" in page.text_content("h1.bk-hero-title") and "משה" in page.text_content("h1.bk-plate")
        assert page.locator("#demo-data").count() == 1 and page.locator(".bk-shelf-row .bk-spine").count() >= 3
        page.click(".bk-hero-cta")
        page.wait_for_url("**/books/login/**")
        assert "משה הזמין/ה אותך" in page.text_content(".bk-invited")
        page.click(".bk-login-other > summary")
        page.click('a[href^="/books/signup/"]')
        page.wait_for_url("**/books/signup/**")
        page.fill("input[name=email]", "dana@example.com")
        page.fill("input[name=password1]", "Shelf-Lamp-2026!")
        page.fill("input[name=password2]", "Shelf-Lamp-2026!")
        page.click("form.bk-form button[type=submit]")
        page.wait_for_url("**/books/welcome/**")
        assert "משה" in page.text_content(".bk-invited")
        page.fill("input[name=display_name]", "דנה")
        page.check("input[name=is_adult_confirmed]")
        page.check("input[name=accept_terms]")
        page.click("form.bk-form button[type=submit]")
        page.wait_for_url(f"**/books/people/{sp.pk}/shelf/?joined=1")
        assert page.get_attribute("html", "data-theme") == "dark"
        assert "חברים עכשיו" in page.text_content(".bk-joined-title")
        assert page.locator(".bk-joined a[href='/books/scan/']").count() == 1  # your turn
        page.wait_for_selector(".bk-spine--photo")  # the picture arrived through the real endpoint
        assert page.locator(".bk-spine--photo").count() == 3
        assert friends.status_between(Profile.objects.get(display_name="דנה"), sp) == "accepted"
    finally:
        context.close()



def _fresh_reader():
    """The reader with no reading yet today, so the day's five minutes are still ahead."""
    from books.models import Profile, ReadingCheckin, ReadingSession
    rp = Profile.objects.get(user__username="reader")
    ReadingSession.objects.filter(profile=rp).delete()
    ReadingCheckin.objects.filter(profile=rp).delete()
    return rp


def test_the_five_minutes_that_earn_the_day_ping_and_light_up_and_the_clock_goes_on(browser, live_server, db):
    """Avi, 2026-10-23: when the first five minutes are reached, a ping and
    fireworks with "another day on the streak", then the count goes on."""
    from datetime import timedelta

    from django.utils import timezone

    from books import catalog, reading
    from books.models import ReadingCheckin, ReadingSession
    build_world()
    rp = _fresh_reader()
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר של חמש דקות")
    earlier = reading.start(rp, e, 1)
    ReadingSession.objects.filter(pk=earlier.pk).update(started_at=timezone.now() - timedelta(seconds=288))
    earlier.refresh_from_db()
    reading.end(rp, earlier, 3)
    assert not ReadingCheckin.objects.filter(profile=rp).exists()
    reading.start(rp, e, 3)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "dark")
    try:
        page.wait_for_selector("[data-earned]:not([hidden])", timeout=15000)
        assert page.evaluate("window.__bkPings") >= 1
        assert "עוד יום ברצף!" in page.text_content("[data-earned]")
        assert page.evaluate("[...document.querySelectorAll('[data-celebrated]')].every(i => i.value === '1')")
        assert page.evaluate("document.querySelector('.bk-flame').classList.contains('is-lit')")
        assert page.text_content(".bk-flame b").strip() == "1"
        page.wait_for_selector("[data-earned]", state="hidden", timeout=8000)
        before = page.text_content("[data-timer]")
        page.wait_for_timeout(1500)
        assert page.text_content("[data-timer]") != before  # the clock goes on
        for _ in range(20):
            if ReadingCheckin.objects.filter(profile=rp).exists():
                break
            page.wait_for_timeout(200)
        assert ReadingCheckin.objects.filter(profile=rp).exists()  # counted on the server at that moment
        page.click("[data-end-form] button[type=submit]")
        page.wait_for_url("**/books/")
        assert "streak=1" not in page.url  # celebrated once, not twice
    finally:
        context.close()


def test_a_screen_left_open_asks_and_stops_the_clock_when_nobody_answers(browser, live_server, db):
    """Avi, 2026-10-23: if I leave the reading open by mistake it must not
    keep counting. After a while without a touch it asks; no answer stops
    the clock where the question came up; a tap goes on."""
    from books import catalog, reading
    from books.models import ReadingSession
    build_world()
    rp = _fresh_reader()
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר שנשכח פתוח")
    s = reading.start(rp, e, 1)
    context, page, _ = _open(browser, live_server, "reader", "/books/", PHONE, "light")
    try:
        page.add_init_script("window.bkReadingTest = {idle: 2, answer: 2};")
        page.goto(f"{live_server.url}/books/read/", wait_until="domcontentloaded")
        page.wait_for_selector('[data-still][data-state="ask"]:not([hidden])', timeout=8000)
        assert page.text_content("[data-still-title]") == "עדיין קוראים?"
        page.wait_for_selector('[data-still][data-state="stopped"]', timeout=8000)
        assert page.text_content("[data-still-yes]") == "ממשיכים לקרוא"
        for _ in range(20):
            s.refresh_from_db()
            if s.paused_at is not None:
                break
            page.wait_for_timeout(200)
        assert s.paused_at is not None and s.seconds <= 5  # stopped where the question came up
        frozen = page.text_content("[data-timer]")
        page.wait_for_timeout(1500)
        assert page.text_content("[data-timer]") == frozen
        page.click("[data-still-yes]")
        page.wait_for_selector("[data-still]", state="hidden")
        for _ in range(20):
            s.refresh_from_db()
            if s.paused_at is None:
                break
            page.wait_for_timeout(200)
        assert s.paused_at is None and ReadingSession.objects.get(pk=s.pk).ended_at is None
    finally:
        context.close()


def test_an_angled_cover_photo_is_found_and_straightened_and_can_be_undone(browser, live_server, db, tmp_path):
    """Avi, 2026-10-23: "I always shoot at an angle; find the book and square
    it, in proportion." On the phone, nothing sent but the finished cover."""
    from PIL import Image

    from books import catalog, reading
    from tests._cover_scenes import scene
    build_world()
    rp = _fresh_reader()
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר בזווית")
    reading.start(rp, e, 3)
    data, _, ratio = scene(1002, "dark")
    photo = tmp_path / "angled.jpg"
    photo.write_bytes(data)
    context, page, _ = _open(browser, live_server, "reader", "/books/read/", PHONE, "light")
    try:
        page.set_input_files("[data-first-cover-input]", str(photo))
        page.wait_for_selector("[data-first-cover-undo]", timeout=15000)
        assert "יושרה" in page.text_content("[data-first-cover-status]")
        e.refresh_from_db()
        with e.cover.open("rb") as fh:
            w, h = Image.open(fh).size
        assert abs(w / h - ratio) <= 0.05  # the book's own proportion, not 2 by 3
        first = e.cover.name
        page.click("[data-first-cover-undo]")
        page.wait_for_function("document.querySelector('[data-first-cover-status]').textContent.trim() === 'נשמרה.'")
        e.refresh_from_db()
        assert e.cover.name != first
        with e.cover.open("rb") as fh:
            w, h = Image.open(fh).size
        assert abs(w / h - 2 / 3) < 0.01  # as taken: the middle of the photo
    finally:
        context.close()


def test_the_friends_search_answers_as_i_type_and_the_invite_opens_from_its_button(browser, live_server, db):
    """Avi, 2026-10-23: results from the second letter, anywhere in the name, with
    nothing else on the screen; not searching, one invite button opens the sheet."""
    from books import friends
    from books.models import Profile
    build_world()
    rp = Profile.objects.get(user__username="reader")
    other = Profile.objects.exclude(pk=rp.pk).first()
    other.display_name = "אבי סלמון"
    other.save()
    friends.join_through_invite(other, friends.invite_for(rp))
    context, page, _ = _open(browser, live_server, "reader", "/books/friends/", PHONE, "dark")
    try:
        assert page.is_visible("[data-invite-open]") and not page.is_visible("[data-invite]")
        page.click("[data-invite-open]")
        page.wait_for_selector("dialog[data-invite][open]")
        assert page.is_visible("[data-share]")
        page.click("[data-invite-close]")
        page.wait_for_selector("dialog[data-invite]:not([open])", state="attached")
        page.fill("[data-friend-q]", "מו")
        page.wait_for_selector("[data-results-mine]")
        assert "אבי סלמון" in page.text_content("[data-friend-results]")
        assert not page.is_visible("[data-friend-rest]")  # nothing else while searching
        assert "q=" in page.url
        page.fill("[data-friend-q]", "")
        page.wait_for_selector("[data-friend-rest]", state="visible")
        assert not page.is_visible("[data-friend-results]")
    finally:
        context.close()


def test_on_a_phone_one_tap_on_a_friends_book_opens_the_conversation(browser, live_server, db, settings):
    """Avi, 2026-10-23: "if I see a book at a friend's I say in one tap that I
    want to receive, borrow or buy it, and a conversation opens." """
    from books import catalog, friends
    from books.models import Copy, Deal, Offer, Profile
    settings.BOOKS_PILOT_GIFT = True
    build_world()
    rp = Profile.objects.get(user__username="reader")
    owner = Profile.objects.get(user__username="shelver")
    friends.join_through_invite(rp, friends.invite_for(owner))
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר למסירה")
    c = Copy.objects.create(owner=owner, entry=e, visibility=Copy.PUBLIC, position=0)
    Offer.objects.create(copy=c, kind="give")
    context, page, _ = _open(browser, live_server, "reader", f"/books/people/{owner.pk}/shelf/", PHONE, "dark")
    try:
        page.wait_for_selector(f'.bk-spine[data-book="{c.pk}"]')
        page.click(f'.bk-spine[data-book="{c.pk}"]')
        page.wait_for_selector("[data-label-ask]:not([hidden])")
        give = page.locator('[data-label-ask] [data-ask-kind="give"]')
        assert "bk-btn--primary" in give.get_attribute("class")  # offered: the bold one
        assert "bk-btn--primary" not in page.locator('[data-label-ask] [data-ask-kind="sell"]').get_attribute("class")
        give.scroll_into_view_if_needed()
        give.click()
        page.wait_for_url(re.compile(r"/books/deals/\d+/$"))
        deal = Deal.objects.get(copy=c)  # build_world seeds a deal of its own
        assert deal.kind == "give" and deal.requester == rp and page.url.endswith(f"/books/deals/{deal.pk}/")
        assert "מסירה במתנה" in page.text_content(".bk-narrow")
    finally:
        context.close()


def test_on_a_phone_the_request_is_a_conversation_that_sends_and_receives_without_reloading(browser, live_server, db, settings):
    """Avi, 2026-10-23: a request is a conversation. A message goes without a
    page reload, the other side's words arrive on their own, the composer
    stays at the bottom, and the one next step is on top."""
    from books import catalog, friends, hub
    from books.models import Copy, Message, Offer, Profile
    settings.BOOKS_PILOT_GIFT = True
    build_world()
    rp = Profile.objects.get(user__username="reader")
    owner = Profile.objects.get(user__username="shelver")
    friends.join_through_invite(rp, friends.invite_for(owner))
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר לשיחה")
    c = Copy.objects.create(owner=owner, entry=e, visibility=Copy.PUBLIC)
    Offer.objects.create(copy=c, kind="give")
    deal = hub.ask(rp, c, "give", "אשמח לקבל אותו")
    context, page, _ = _open(browser, live_server, "reader", f"/books/deals/{deal.pk}/", PHONE, "dark")
    try:
        assert page.locator("[data-chat-list] .bk-bubble").count() == 1
        url = page.url
        page.fill("[data-chat-form] [name=body]", "מתי נוח לך?")
        page.click("[data-chat-send]")
        page.wait_for_function("document.querySelectorAll('[data-chat-list] .bk-bubble').length === 2")
        assert page.url == url  # no reload, no navigation
        assert page.input_value("[data-chat-form] [name=body]") == ""
        assert "bk-bubble--mine" in page.locator("[data-chat-list] .bk-bubble").nth(1).get_attribute("class")
        assert Message.objects.filter(deal=deal, sender=rp, body="מתי נוח לך?").exists()
        hub.send_message(deal, owner, "מחר בשש?")  # the other side writes
        page.evaluate("window.bkChat.fetchNew()")
        page.wait_for_function("document.querySelectorAll('[data-chat-list] .bk-bubble').length === 3")
        third = page.locator("[data-chat-list] .bk-bubble").nth(2)
        assert "bk-bubble--mine" not in third.get_attribute("class") and "מחר בשש?" in third.text_content()
        # the composer is on screen without scrolling to it
        box = page.locator("[data-chat-form]").bounding_box()
        assert box and box["y"] + box["height"] <= PHONE["height"]
        assert Message.objects.filter(deal=deal, sender=owner, read_at__isnull=False).exists()  # fetched = read
    finally:
        context.close()
