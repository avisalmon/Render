"""breakout's screen contract: every screen in a real browser at the narrow
phone widths real phones have (mistake 34), a tablet and a desktop: nothing
past the edge, every field 16px or more (mistake 52), every control a 44px
target, labels, readable contrast, a heading, nothing alarming, and the
first card in the top half of a phone screen (mistake 25). A screenshot of
each screen at a phone and a desktop width lands in BREAKOUT_SHOTS (or the
temp folder) for the builder to look at once (mistake 6). Then the teacher's
job on a phone, start to finish (mistake 27). Skipped, not failed, without a
browser.
"""

import os
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
PHONES = [320, 360, 375, 390, 412]
TABLET = 820
DESKTOP = 1280
ALARM = ["Traceback", "None", "null", "undefined", "Error", "{{", "{%"]
SHOTS = Path(os.environ.get("BREAKOUT_SHOTS", str(Path(os.environ.get("TEMP", "/tmp")) / "breakout-shots")))

OVERFLOW_JS = """(w) => [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.width > 0 && (r.right > w + 1 || r.left < -1);
  }).slice(0, 5).map(el => el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + ' ' + Math.round(el.getBoundingClientRect().right))"""

SMALL_FIELDS_JS = """() => [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')]
    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.id || e.className)"""

TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1, bad = [];
    document.querySelectorAll('a, button, input[type=checkbox], select, summary, input[type=number], input[type=search]').forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName === 'A' && el.closest('p, .br-foot, td, .br-byline')) return;  // a link in running text
        if (el.type === 'checkbox') el = el.closest('label') || el;
        if (!el.getClientRects().length) return;  // inside a closed <details>
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        if (r.height < minPx - 4) bad.push('short ' + (el.textContent || el.name || el.className).trim().slice(0, 24) + ' ' + Math.round(r.height));
    });
    return [...new Set(bad)];
}"""

A11Y_JS = """() => {
    const bad = [];
    document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) bad.push('img without alt'); });
    document.querySelectorAll('button, a').forEach(b => {
        if (!(b.textContent || '').trim() && !b.getAttribute('aria-label')) bad.push('unlabelled ' + b.tagName);
    });
    document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(i => {
        const labelled = i.closest('label') || (i.id && document.querySelector('label[for="' + i.id + '"]')) || i.getAttribute('aria-label');
        if (!labelled) bad.push('unlabelled field ' + (i.name || i.type));
    });
    if (!document.querySelector('main')) bad.push('no main');
    if (!document.querySelector('h1')) bad.push('no h1');
    return bad;
}"""

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
        if (cs.visibility === 'hidden' || cs.display === 'none' || !el.getClientRects().length) return;
        let node = el, bg = null;
        while (node && node !== document.documentElement) {
            const c = parse(getComputedStyle(node).backgroundColor);
            if (c.length === 3 && !/rgba\(.*,\s*0\)/.test(getComputedStyle(node).backgroundColor)) { bg = c; break; }
            node = node.parentElement;
        }
        if (!bg) bg = parse(getComputedStyle(document.body).backgroundColor);
        const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
        const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
        const got = ratio(parse(cs.color), bg);
        if (got + 0.005 < need) bad.push(`${got.toFixed(2)}:1 (needs ${need}) "${own.slice(0, 32)}"`);
    });
    return [...new Set(bad)];
}"""

FIRST_CARD_TOP_JS = """() => { const c = document.querySelector('.br-card'); return c ? c.getBoundingClientRect().top : -1; }"""


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


def build_world():
    """The seeded flagship plus a second, long-titled experience with runs, so
    the numbers on the screenshots can be read against something (mistake 21)."""
    from breakout.models import Experience, Run, Station

    avi = User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")
    dana = User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה")
    call_command("seed_breakout", verbosity=0)
    flagship = Experience.objects.get(slug="hamachshev-shenichba")
    Run.objects.create(experience=flagship, user=dana, group_count=5, kids_count=28, actual_minutes=50, rating=5, what_worked="הבאג היה הלהיט")
    Run.objects.create(experience=flagship, user=avi, group_count=6, kids_count=31, actual_minutes=42, rating=4)
    second = Experience.objects.create(
        author=dana, title="הודעה מהעתיד: שרשרת צפנים ארוכה במיוחד לשם ארוך על כרטיס", slug="message-from-the-future",
        tagline="הקבוצה מפענחת שרשרת צפנים כדי לגלות מה הטכנולוגיה ממציאה בעוד חמישים שנה. " * 2,
        status=Experience.PUBLISHED, audience_from=5, audience_to=8, duration_minutes=60, difficulty=Experience.HARD,
    )
    Station.objects.create(experience=second, order=1, name="הצופן הראשון", puzzle_text="א" * 40, solution="ב", estimated_minutes=10)
    return flagship, second


def _open(browser, live_server, who, path, width):
    phone = width < 600
    height = 844 if phone else (1180 if width < 1000 else 800)
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1, is_mobile=phone, has_touch=phone, locale="he-IL")
    page = context.new_page()
    if who:
        page.goto(f"{live_server.url}/breakout/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', f"{who}@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
    page.goto(f"{live_server.url}{path}", wait_until="networkidle")
    return context, page


def _screens(flagship, second):
    station = flagship.stations.order_by("order").first()
    return [
        ("login", None, "/breakout/login/"),
        ("signup", None, "/breakout/signup/"),
        ("home", "dana", "/breakout/"),
        ("experience", "dana", f"/breakout/x/{flagship.slug}/"),
        ("experience-thin", "dana", f"/breakout/x/{second.slug}/"),
        ("not-found", "dana", "/breakout/no-such-page/"),
        # The editor (B.3), as the flagship's author.
        ("edit-new", "avi", "/breakout/new/"),
        ("edit-hub", "avi", f"/breakout/x/{flagship.slug}/edit/"),
        ("edit-about", "avi", f"/breakout/x/{flagship.slug}/edit/about/"),
        ("edit-story", "avi", f"/breakout/x/{flagship.slug}/edit/story/"),
        ("edit-stations", "avi", f"/breakout/x/{flagship.slug}/edit/stations/"),
        ("edit-station", "avi", f"/breakout/x/{flagship.slug}/edit/stations/{station.pk}/"),
        ("edit-lock", "avi", f"/breakout/x/{flagship.slug}/edit/lock/"),
        ("edit-hub-thin", "dana", f"/breakout/x/{second.slug}/edit/"),
    ]


def test_every_screen_holds_on_every_phone_a_tablet_and_a_desktop(browser, live_server):
    flagship, second = build_world()
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = []
    for name, who, path in _screens(flagship, second):
        for width in PHONES + [TABLET, DESKTOP]:
            context, page = _open(browser, live_server, who, path, width)
            try:
                if not page.url.startswith(live_server.url + path):
                    problems.append(f"{name}@{width}: landed on {page.url}")
                    continue
                text = page.inner_text("body")
                for word in ALARM:
                    if re.search(rf"\b{re.escape(word)}\b", text):
                        problems.append(f"{name}@{width}: says {word!r}")
                if name == "experience" or name.startswith("edit-"):
                    # Open every fold and station so the checks see the whole page.
                    page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                for label, js, arg in (("past the edge", OVERFLOW_JS, width), ("fields under 16px", SMALL_FIELDS_JS, None),
                                       ("tap targets", TAP_JS, 44), ("a11y", A11Y_JS, None), ("contrast", CONTRAST_JS, None)):
                    found = page.evaluate(js, arg) if arg is not None else page.evaluate(js)
                    if found:
                        problems.append(f"{name}@{width}: {label} {found}")
                if page.evaluate("document.documentElement.scrollWidth") > width:
                    problems.append(f"{name}@{width}: page wider than the screen")
                if name == "home" and width < 600:
                    top = page.evaluate(FIRST_CARD_TOP_JS)
                    if not 0 <= top <= 844 / 2:
                        problems.append(f"{name}@{width}: the first card starts at {top}px, below the top half")
                if width in (390, 1280):
                    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
            finally:
                context.close()
    assert problems == [], "\n".join(problems)


def test_on_a_phone_a_teacher_finds_the_experience_and_reads_a_solution(browser, live_server):
    """The teacher's job, start to finish, on a phone (mistake 27): sign in,
    search, open the experience, open a station, read the solution and the
    code, scale the shopping list."""
    flagship, _second = build_world()
    context, page = _open(browser, live_server, "dana", "/breakout/", 390)
    try:
        page.click("#br-filters summary")
        page.fill("#br-q", "רובוט")
        shown = page.evaluate("[...document.querySelectorAll('.br-card:not(.br-hidden) .br-card-title a')].map(a => a.textContent.trim())")
        assert shown == ["המחשב שנכבה"]
        page.fill("#br-q", "אין כזה דבר")
        assert page.is_visible("#br-no-match")
        page.fill("#br-q", "")
        page.select_option("#br-grade", "6")
        shown = page.evaluate("[...document.querySelectorAll('.br-card:not(.br-hidden)')].length")
        assert shown == 1  # only the second experience reaches grade 6
        page.select_option("#br-grade", "")
        page.check("#br-has-runs")
        shown = page.evaluate("[...document.querySelectorAll('.br-card:not(.br-hidden) .br-card-title a')].map(a => a.textContent.trim())")
        assert shown == ["המחשב שנכבה"]
        page.click(".br-card:not(.br-hidden) .br-card-title a")
        page.wait_for_load_state("networkidle")
        assert page.url.endswith(f"/breakout/x/{flagship.slug}/")
        page.click(".br-station:nth-child(3) summary")
        solution = page.inner_text(".br-station:nth-child(3) .br-solution")
        assert "4" in solution
        page.click("text=המנעול הסופי")
        assert page.inner_text(".br-code").strip() == "4326"
        page.click("text=רשימת קניות")
        page.fill("#br-groups", "6")
        page.dispatch_event("#br-groups", "input")
        cards = page.evaluate("[...document.querySelectorAll('#br-shopping tr')].find(tr => tr.textContent.includes('כרטיסיות')).querySelector('.br-qty').textContent")
        assert cards == "48"
        # One number for one question (B.2): the kit form followed the shopping list.
        assert page.input_value("#br-kit-groups") == "6"
        page.fill("#br-kit-groups", "3")
        page.dispatch_event("#br-kit-groups", "input")
        assert page.input_value("#br-groups") == "3"
        with page.expect_download() as waiting:
            page.click("#br-kitform button[type=submit]")
        download = waiting.value
        assert download.suggested_filename.endswith(".pdf")
        assert download.url.endswith(f"/breakout/x/{flagship.slug}/kit/?groups=3")
        from breakout.models import Download
        assert list(Download.objects.values_list("groups", flat=True)) == [3]
    finally:
        context.close()


def test_on_a_phone_a_teacher_writes_an_experience_and_publishes_it(browser, live_server):
    """The author's job on a phone (mistake 27, B.3): about, story, a station
    with its puzzle, solution, hint and material, the lock, publish, and the
    new experience is on the library."""
    from breakout.models import Experience, Material

    build_world()
    context, page = _open(browser, live_server, "dana", "/breakout/", 390)
    try:
        page.click("a.br-pagehead-action")
        page.wait_for_load_state("networkidle")
        assert page.url.endswith("/breakout/new/")
        page.fill('input[name="title"]', "צופן הפסנתר")
        page.fill('input[name="tagline"]', "הקבוצה מנגנת את הקוד")
        page.select_option('select[name="audience_from"]', "7")
        page.select_option('select[name="audience_to"]', "9")
        page.check('input[name="difficulty"][value="easy"]')
        page.click("form.br-form button[type=submit]")
        page.wait_for_load_state("networkidle")
        exp = Experience.objects.get(title="צופן הפסנתר")
        assert page.url.endswith(f"/breakout/x/{exp.slug}/edit/story/")
        page.fill('textarea[name="story"]', "הפסנתר של בית הספר שכח את המנגינה.")
        page.click("form.br-form button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.url.endswith("/edit/stations/")
        page.fill('input[name="name"]', "הקלידים")
        page.click("form.br-addrow button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert "/edit/stations/" in page.url and page.url.rstrip("/").split("/")[-1].isdigit()
        page.fill('textarea[name="puzzle_text"]', "כל קליד הוא אות. נגנו: 3 1 4")
        page.fill('textarea[name="solution"]', "גאד (הספרה 3)")
        page.click("#br-station-form button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.click("a.br-row-title")
        page.wait_for_load_state("networkidle")
        page.fill('#br-hints input[name="text"]', "הקליד הלבן הראשון הוא א")
        page.click("#br-hints form.br-addrow button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.locator("#br-hints .br-row").count() == 1
        paper = Material.objects.get(name="דף A4")
        page.select_option('#br-materials select[name="material"]', str(paper.pk))
        page.fill('#br-materials input[name="quantity"]', "1")
        page.click("#br-materials form.br-addrow button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.locator("#br-materials .br-row").count() == 1
        page.goto(f"{live_server.url}/breakout/x/{exp.slug}/edit/lock/", wait_until="networkidle")
        page.fill('input[name="final_code"]', "3")
        page.click("form.br-form button[type=submit]")
        page.wait_for_load_state("networkidle")
        assert page.url.endswith(f"/breakout/x/{exp.slug}/edit/")
        assert page.locator(".br-checklist .br-missing").count() == 0
        page.click("form[action$='/edit/publish/'] button")
        page.wait_for_load_state("networkidle")
        assert page.url.endswith(f"/breakout/x/{exp.slug}/")
        assert Experience.objects.get(pk=exp.pk).status == Experience.PUBLISHED
        page.goto(f"{live_server.url}/breakout/", wait_until="networkidle")
        titles = page.evaluate("[...document.querySelectorAll('.br-card .br-card-title a')].map(a => a.textContent.trim())")
        assert "צופן הפסנתר" in titles
    except Exception:
        # Where the flow broke, for the person reading the failure (mistake 6).
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "authoring-failed.png"), full_page=True)
        print("authoring flow failed at", page.url)
        raise
    finally:
        context.close()
