"""memz's screen contract: every screen, by state, rendered on a phone.

The rule comes from the_manager.md Step 4a, learned on מט״צים: every screen
that got rendered had a defect no test had caught, and every one of them
lived in a state nobody had rendered. So this is a catalogue of screens by
state, opened in a real browser at phone width (memz is phone-first, spec
§11), asserting the handful of properties that only exist after layout:

- the contract landed on the screen it asked for (a `data-screen` marker),
- there is a heading and something to read,
- no template syntax, raw key, or alarm word reached the reader,
- text is readable (WCAG AA contrast, measured, spec Rule 11.4),
- nothing is wider than the phone (spec Rule 11.2),
- every control is a 44px thumb target with no neighbour inside that box
  (spec Rule 11.1).

Adding a screen means adding it here. Adding a state means adding that too.
Skipped, not failed, on a machine without Playwright's browser.
"""

import io
import os
import re

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.memzscreens, pytest.mark.django_db]

PASSWORD = "memz-screens-7781"
PHONE = {"width": 390, "height": 844}
MIN_TAP_PX = 44

# Words that mean something went wrong. A normal state never uses them.
ALARM_WORDS = ["Traceback", "None", "null", "undefined", "Error"]
# Enum values that must never reach a reader as-is.
RAW_KEYS = ["public_random", "same_meme", "moderation_status", "guest_token"]

VISIBLE_TEXT_JS = "() => document.body.innerText"

CONTRAST_JS = r"""() => {
    const srgb = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92
                                                        : Math.pow((c + 0.055) / 1.055, 2.4); };
    const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
    const parse = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const ratio = (a, b) => {
        const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
        return (hi + 0.05) / (lo + 0.05);
    };
    const bad = [];
    document.querySelectorAll('body *').forEach((el) => {
        const own = [...el.childNodes]
            .filter((n) => n.nodeType === 3 && n.textContent.trim())
            .map((n) => n.textContent.trim()).join(' ');
        if (!own) return;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
        if (!el.getClientRects().length) return;
        let node = el, bg = null;
        while (node && node !== document.documentElement) {
            const s = getComputedStyle(node);
            if (s.backgroundImage && s.backgroundImage !== 'none') return;
            const c = parse(s.backgroundColor);
            if (c.length === 3 && !/rgba\(.*,\s*0\)/.test(s.backgroundColor)) { bg = c; break; }
            node = node.parentElement;
        }
        if (!bg) return;
        const size = parseFloat(cs.fontSize);
        const weight = parseInt(cs.fontWeight, 10) || 400;
        const large = size >= 24 || (size >= 18.66 && weight >= 700);
        const need = large ? 3 : 4.5;
        const got = ratio(parse(cs.color), bg);
        if (got + 0.005 < need) {
            bad.push(`${got.toFixed(2)}:1 (needs ${need}) ${cs.fontSize} "${own.slice(0, 32)}"`);
        }
    });
    return [...new Set(bad)];
}"""

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    const limit = doc.clientWidth;
    const wide = [];
    document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width > limit + 1 || r.right > limit + 1 || r.left < -1) && r.height > 0) {
            wide.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0]
                + ' w=' + Math.round(r.width) + ' left=' + Math.round(r.left) + ' right=' + Math.round(r.right));
        }
    });
    return [...new Set(wide)].slice(0, 6);
}"""

# Probe the four edge midpoints of the required target box (the ustrip
# guard's method): a point that lands on the control counts; anything else
# means a thumb aiming there hits a neighbour, or nothing.
TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1;
    const bad = [];
    const controls = document.querySelectorAll('a, button, summary, input[type=checkbox], input[type=file]');
    controls.forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName === 'A' && el.closest('p, figcaption, .memz-fineprint')) return;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => {
            if (x < 1 || y < 1 || x > window.innerWidth - 1 || y > window.innerHeight - 1) return null;
            return document.elementFromPoint(x, y);
        };
        const hits = (node) => node && (node === el || el.contains(node));
        if (!hits(at(cx, cy))) return;
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]]
            .some(([x, y]) => { const node = at(x, y); return node !== null && !hits(node); });
        if (missed) {
            bad.push((el.getAttribute('title') || el.textContent || el.className || el.tagName)
                .trim().slice(0, 28) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""


# ---------------------------------------------------------------- the world


def _png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (60, 120, 170)).save(buf, format="PNG")
    return buf.getvalue()


def build_world():
    from memz.memes import make_meme
    from memz.models import Meme, MemeImage

    user = User.objects.create_user("screens", email="screens@example.com", password=PASSWORD, first_name="נועה")
    taken = User.objects.create_user("taken", email="taken@example.com", password=PASSWORD)

    image = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title="לצילום מסך")
    image.file.save("screenshot-source.png", ContentFile(_png_bytes()), save=True)

    meme = make_meme(image=image, caption_text="זה מם לדוגמה, בשביל לבדוק את המסך", source=Meme.SOLO, user=None)
    from django.utils import timezone

    expired = make_meme(image=image, caption_text="זה מם שפג לו התוקף", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timezone.timedelta(hours=1))

    return {"user": user, "taken": taken, "image": image, "meme": meme, "expired_slug": expired.share_slug}


def _wrong_password(page):
    page.fill('input[name="username"]', "screens@example.com")
    page.fill('input[name="password"]', "not-the-password")
    page.click('form button[type="submit"]')
    page.wait_for_timeout(400)


def _taken_email(page):
    page.fill('input[name="email"]', "taken@example.com")
    page.fill('input[name="password1"]', PASSWORD)
    page.fill('input[name="password2"]', PASSWORD)
    page.click('form button[type="submit"]')
    page.wait_for_timeout(400)


# (label, path, sign in as, action to reach the state, expected data-screen).
# `path` may be a callable taking the world dict, for a screen whose URL
# carries something build_world() created (a share slug).
SCREENS = [
    ("home/anonymous", "/memz/", None, None, "home"),
    ("home/signed-in", "/memz/", "screens@example.com", None, "home"),
    ("login/empty", "/memz/login/", None, None, "login"),
    ("login/wrong-password", "/memz/login/", None, _wrong_password, "login"),
    ("signup/empty", "/memz/signup/", None, None, "signup"),
    ("signup/taken-email", "/memz/signup/", None, _taken_email, "signup"),
    ("password-reset/form", "/memz/password/reset/", None, None, "password-reset"),
    ("coming/game-not-yet", "/memz/new/", None, None, "coming"),
    ("creator/empty", "/memz/create/", None, None, "creator"),
    ("creator/signed-in", "/memz/create/", "screens@example.com", None, "creator"),
    ("creator/result", lambda w: f"/memz/create/{w['meme'].share_slug}/", None, None, "creator-result"),
    ("share/live", lambda w: f"/memz/m/{w['meme'].share_slug}/", None, None, "share"),
    ("share/expired", lambda w: f"/memz/m/{w['expired_slug']}/", None, None, "share-expired"),
    ("share/never-existed", "/memz/m/not-a-real-slug-at-all/", None, None, "share-expired"),
    ("404", "/memz/nowhere/", None, None, "404"),
]


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _open(browser, live_server, email, path):
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = context.new_page()
    if email:
        page.goto(f"{live_server.url}/memz/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', email)
        page.fill('input[name="password"]', PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_timeout(400)
        assert "/login/" not in page.url, f"could not sign in as {email}"
    page.goto(live_server.url + path, wait_until="domcontentloaded")
    page.wait_for_timeout(350)
    return context, page


@pytest.mark.parametrize("label,path,who,action,screen", SCREENS, ids=[s[0] for s in SCREENS])
def test_screen_contract(browser, live_server, db, label, path, who, action, screen):
    world = build_world()
    if callable(path):
        path = path(world)
    context, page = _open(browser, live_server, who, path)
    try:
        if action:
            action(page)
        landed = page.locator("[data-screen]").first
        assert landed.count(), f"{label}: no data-screen marker, so the contract cannot tell what it is looking at"
        assert landed.get_attribute("data-screen") == screen, (
            f"{label}: asked for {screen!r} and landed on {landed.get_attribute('data-screen')!r}"
        )

        complaints = []
        text = page.evaluate(VISIBLE_TEXT_JS)
        heading = page.locator("h1, h2").first
        assert heading.count() and heading.inner_text().strip(), f"{label}: the screen has no heading"
        assert len(text.strip()) > 40, f"{label}: only {len(text.strip())} characters of visible text"

        for token in ("{#", "#}", "{%", "%}", "{{", "}}"):
            if token in text:
                complaints.append(f"unrendered template syntax reached the reader: {token!r}")
        for key in RAW_KEYS:
            if key in text:
                complaints.append(f"a raw key reached the reader: {key!r}")
        for word in ALARM_WORDS:
            if re.search(rf"(?<![\w/]){re.escape(word)}(?![\w/])", text):
                complaints.append(f"reads as a fault rather than a state: {word!r}")
        for entry in page.evaluate(CONTRAST_JS):
            complaints.append(f"text under the readable contrast line: {entry}")
        for entry in page.evaluate(OVERFLOW_JS):
            complaints.append(f"wider than the phone: {entry}")
        for entry in page.evaluate(TAP_JS, MIN_TAP_PX):
            complaints.append(f"tap target under {MIN_TAP_PX}px or crowded: {entry}")

        assert not complaints, f"{label} ({path}):\n  " + "\n  ".join(complaints)
    finally:
        context.close()
