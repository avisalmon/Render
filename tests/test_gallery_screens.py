"""gallery's screen contract: every screen, as its role, in a real browser
(the_manager.md step 4a; same checks as tests/test_dentist_screens.py, copied).

Each screen is opened at the narrowest phones (mistake 34) and on a desktop,
in Hebrew and on one screen in English, asserting what exists only after
layout: nothing past the edge, every field 16px or more (mistake 52), 44px
tap targets, labels, readable contrast, a heading, nothing alarming. A
screenshot of each at 390 and 1280 lands in GALLERY_SHOTS for the builder to
look at once (mistake 6). Adding a screen means adding it here. Skipped, not
failed, without a browser.

Traces: REQ-G.100, G.101, G.102.
"""

import os
import re
from pathlib import Path
from urllib.parse import unquote

import pytest
from django.contrib.auth.models import User

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.django_db(transaction=True)]

PASSWORD = "gallery-screens-4410"
PHONES = [320, 360, 390]
DESKTOP = 1280
ALARM = ["Traceback", "None", "null", "undefined", "{{", "{%"]
RAW_KEY = re.compile(r"\b(?:chat|skill|skills|manage|form|auth|nav|card|thread|training|settings)\.[a-z_]+\b")
SHOTS = Path(os.environ.get("GALLERY_SHOTS", str(Path(os.environ.get("TEMP", "/tmp")) / "gallery-shots")))

OVERFLOW_JS = """(w) => [...document.querySelectorAll('body *')].filter(el => {
    if (el.closest('.gl-table-wrap, .gl-code')) return false;  // tables and code scroll in their own box on purpose
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.width > 0 && (r.right > w + 1 || r.left < -1);
  }).slice(0, 5).map(el => el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + ' ' + Math.round(el.getBoundingClientRect().right))"""

SMALL_FIELDS_JS = """() => [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')]
    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.className)"""

TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1, bad = [];
    document.querySelectorAll('a, button, input[type=checkbox], select, summary').forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName === 'A' && el.closest('p, li, td, .gl-card-text, .gl-file-list')) return;  // a link in running text
        if (el.type === 'checkbox') el = el.closest('label') || el;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        if (r.height < minPx - 4 && !el.closest('.gl-nav'))
            bad.push('short ' + (el.textContent || el.name || el.className).trim().slice(0, 24) + ' ' + Math.round(r.height));
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => (x < 1 || y < 1 || x > innerWidth - 1 || y > innerHeight - 1) ? null : document.elementFromPoint(x, y);
        const hits = (n) => n && (n === el || el.contains(n) || n.contains(el));
        if (!hits(at(cx, cy))) return;
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]].some(([x, y]) => { const n = at(x, y); return n !== null && !hits(n) && n.closest('a, button, summary, label') && n.closest('a, button, summary, label') !== el; });
        if (missed) bad.push('crowded ' + (el.textContent || el.className).trim().slice(0, 24));
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




GOOD = b"---\nname: excel-tables\ndescription: Builds clean Excel tables from CSV files, with totals.\n---\n# Excel tables\nWrite an .xlsx with openpyxl.\n"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.GALLERY_FILES_DIR = tmp_path
    settings.GALLERY_SHOTS_ENABLED = False
    settings.OPENAI_API_KEY = ""  # methodology 26: the stub reads, nothing is paid


def build_world():
    from gallery import skill_chat, skills
    from gallery.access import ensure_person
    from gallery.models import Comment, Exhibit, Like, SkillChat, Topic, Training

    def person(email, first, last, superuser=False, answered=True):
        u = User.objects.create_user(email, email, PASSWORD, first_name=first, last_name=last)
        if superuser:
            u.is_superuser = u.is_staff = True
            u.save()
        p = ensure_person(u)
        if answered:
            p.training, p.training_set_at = Training.objects.first(), p.created_at
            p.save()
        return p

    dana = person("dana@example.com", "דנה", "לוי")
    omer = person("omer@example.com", "Omer", "Katz")
    person("new@example.com", "נועם", "חדש", answered=False)
    person("avi@example.com", "אבי", "סלמון", superuser=True)
    page = Exhibit.objects.create(owner=dana, title="מחשבון משכנתא עם שם ארוך מאוד שלא נגמר בכלל", url="https://dana.github.io/m/",
                                  blurb="כמה מילים על הדף.", shot_status=Exhibit.FAILED)
    page.topics.set(Topic.objects.filter(slug__in=["data", "frontend"]))
    Exhibit.objects.create(owner=omer, title="BKM: GitHub Pages מאפס", url="https://babook.co.il/bkm/", kind=Exhibit.BKM,
                           shot_status=Exhibit.FAILED)
    c = Comment.objects.create(exhibit=page, author=omer, body="Very clean. How did you do the chart?")
    Comment.objects.create(exhibit=page, author=dana, body="Chart.js, שלוש שורות.", reply_to=c)
    Like.objects.create(person=omer, exhibit=page)
    chat, bundle, _ = skills.start(dana, "SKILL.md", GOOD)
    skill_chat.begin(chat, "he")               # stub: clean, waiting for "publish"
    chat.refresh_from_db()
    confirm = chat.pk
    skill_chat.act(chat, "publish", "he")
    skill = chat.skill
    risky, _, _ = skills.start(omer, "SKILL.md", GOOD.replace(b"excel-tables", b"cleanup") + b"\nrm -rf ~\n")
    skill_chat.begin(risky, "he")               # stub: risky, waiting for a fix
    waiting, _, _ = skills.start(omer, "SKILL.md", GOOD.replace(b"excel-tables", b"word-letters"))
    skill_chat.begin(waiting, "he")
    return {"page": page, "skill": skill, "confirm": confirm, "risky": risky.pk, "waiting": waiting.pk,
            "dana": dana, "omer": omer, "ended": SkillChat.objects.get(pk=confirm)}


def _screens(w):
    p, s = w["page"].pk, w["skill"].exhibit_id
    return [
        ("home", None, "/gallery/"), ("home-search-empty", None, "/gallery/?q=nothing-like-this"),
        ("skills", None, "/gallery/skills/"), ("skill-guide", None, "/gallery/skills/guide/"), ("home-all", "dana", "/gallery/?scope=all&sort=new"), ("page", None, f"/gallery/e/{p}/"), ("skill", None, f"/gallery/e/{s}/"),
        ("person", None, f"/gallery/u/{w['dana'].slug}/"), ("login", None, "/gallery/login/"), ("signup", None, "/gallery/signup/"),
        ("home-in", "dana", "/gallery/"), ("page-in", "omer", f"/gallery/e/{p}/"), ("new", "dana", "/gallery/new/"),
        ("edit", "dana", f"/gallery/e/{p}/edit/"), ("materials", "dana", "/gallery/materials/"), ("materials-avi", "avi", "/gallery/materials/"), ("material-new", "dana", "/gallery/materials/new/?shelf=mine"), ("settings", "dana", "/gallery/settings/"),
        ("training", "new", "/gallery/training/"), ("skill-new", "omer", "/gallery/skills/new/"),
        ("skill-at-limit", "dana", "/gallery/skills/new/"),
        ("chat-published", "dana", f"/gallery/skills/chat/{w['confirm']}/"),
        ("chat-risky", "omer", f"/gallery/skills/chat/{w['risky']}/"),
        ("manage", "avi", "/gallery/manage/"), ("manage-people", "avi", "/gallery/manage/people/"),
        ("manage-person", "avi", f"/gallery/manage/people/{w['dana'].pk}/"),
        ("manage-trainings", "avi", "/gallery/manage/trainings/"), ("manage-topics", "avi", "/gallery/manage/topics/"),
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


def _context(browser, live_server, who, width, lang="he"):
    phone = width < 600
    ctx = browser.new_context(viewport={"width": width, "height": 844 if phone else 800}, device_scale_factor=1,
                              is_mobile=phone, has_touch=phone, locale="en-US")
    ctx.add_cookies([{"name": "gallery_lang", "value": lang, "url": live_server.url}])
    if who:
        page = ctx.new_page()
        page.goto(f"{live_server.url}/gallery/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', f"{who}@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click("form.gl-form button[type=submit]")
        page.wait_for_load_state("domcontentloaded")
        page.close()
    return ctx


def _check(page, name, width, problems):
    text = page.inner_text("body")
    for word in ALARM:
        if re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", text):
            problems.append(f"{name}@{width}: says {word!r}")
    for key in RAW_KEY.findall(text):
        if key.lower() not in ("skill.md",):
            problems.append(f"{name}@{width}: raw key {key!r}")
    for label, js, arg in (("past the edge", OVERFLOW_JS, width), ("fields under 16px", SMALL_FIELDS_JS, None),
                           ("tap targets", TAP_JS, 44), ("a11y", A11Y_JS, None), ("contrast", CONTRAST_JS, None)):
        found = page.evaluate(js, arg) if arg is not None else page.evaluate(js)
        if found:
            problems.append(f"{name}@{width}: {label} {found}")
    if page.evaluate("document.documentElement.scrollWidth") > width:
        problems.append(f"{name}@{width}: page wider than the screen")


def test_every_screen_holds_on_the_narrowest_phones_and_a_desktop(browser, live_server):
    w = build_world()
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = []
    for width in PHONES + [DESKTOP]:
        contexts = {}
        try:
            for name, who, path in _screens(w):
                if who not in contexts:
                    contexts[who] = _context(browser, live_server, who, width)
                page = contexts[who].new_page()
                page.goto(f"{live_server.url}{path}", wait_until="networkidle")
                if not unquote(page.url).startswith(live_server.url + path.split("?")[0]):
                    problems.append(f"{name}@{width}: landed on {page.url}")
                else:
                    _check(page, name, width, problems)
                    if width in (390, DESKTOP):
                        page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
                page.close()
        finally:
            for ctx in contexts.values():
                ctx.close()
    assert problems == [], "\n".join(problems)


def test_english_reads_left_to_right_everywhere(browser, live_server):
    """REQ-G.101: the same checks in English on the screens people use most."""
    w = build_world()
    w["dana"].language = "en"  # her saved choice wins over the cookie (REQ-G.6)
    w["dana"].save(update_fields=["language"])
    problems = []
    ctx = _context(browser, live_server, "dana", 360, lang="en")
    try:
        for name, who, path in _screens(w):
            if who not in (None, "dana"):
                continue
            page = ctx.new_page()
            page.goto(f"{live_server.url}{path}", wait_until="networkidle")
            if page.evaluate("document.documentElement.dir") != "ltr":
                problems.append(f"{name}: not ltr")
            if re.search("[֐-׿]", page.inner_text(".gl-nav")):
                problems.append(f"{name}: Hebrew in the English menu")
            _check(page, f"{name}-en", 360, problems)
            page.close()
    finally:
        ctx.close()
    assert problems == [], "\n".join(problems)
