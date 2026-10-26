"""dentist's screen contract: every screen, as its role, in a real browser.

Each screen is opened at the narrow phone widths real phones have (mistake
34), at a tablet (the clinic's shared device) and on a desktop, asserting
what exists only after layout: nothing past the edge, every field 16px or
more (an iPhone zooms and slides otherwise, mistake 52), every control a
44px target, labels on every field, readable contrast, a heading and
nothing alarming. A screenshot of each screen at phone and desktop width
lands in the scratchpad for the builder to look at once (mistake 6).
Adding a screen means adding it here. Skipped, not failed, without a
browser.
"""

import os
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprd3, pytest.mark.django_db]

PASSWORD = "dentist-screens-7781"
PHONES = [320, 360, 375, 390, 412]
TABLET = {"width": 820, "height": 1180}
DESKTOP = {"width": 1280, "height": 800}
ALARM = ["Traceback", "None", "null", "undefined", "Error", "{{", "{%"]
SHOTS = Path(os.environ.get("DENTIST_SHOTS", str(Path(os.environ.get("TEMP", "/tmp")) / "dentist-shots")))

OVERFLOW_JS = """(w) => [...document.querySelectorAll('body *')].filter(el => {
    if (el.closest('.dn-table-wrap')) return false;  // the log table scrolls in its own box on purpose
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.width > 0 && (r.right > w + 1 || r.left < -1);
  }).slice(0, 5).map(el => el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + ' ' + Math.round(el.getBoundingClientRect().right))"""

SMALL_FIELDS_JS = """() => [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')]
    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.className)"""

TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1, bad = [];
    document.querySelectorAll('a, button, input[type=checkbox], select, summary').forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName === 'A' && el.closest('p, .dn-foot, .dn-fine, dd')) return;  // a link in running text
        if (el.type === 'checkbox') el = el.closest('label') || el;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        if (r.height < minPx - 4 && !el.classList.contains('dn-btn--sm') && !el.closest('.dn-nav'))
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


def build_world():
    from dentist.models import (
        Appointment,
        Chair,
        Clinic,
        ClinicMember,
        HistoryItem,
        Invitation,
        Patient,
        PatientLink,
        PlanItem,
        ProcedureType,
        Visit,
        VisitProcedure,
    )

    clinic = Clinic.objects.create(name="Neighbourhood Dental Clinic", slug="neighbourhood", address="12 Levinsky Street, Tel Aviv",
                                   opening_notes="Sundays and Tuesdays, 16:00 to 20:00. Call 050-0000000 if you cannot come.")
    admin = User.objects.create_user("admin", "admin@example.com", PASSWORD, first_name="Rina", last_name="Admin")
    dentist = User.objects.create_user("dentist", "dentist@example.com", PASSWORD, first_name="Noa", last_name="Dentist")
    patient_user = User.objects.create_user("patient", "patient@example.com", PASSWORD)
    ClinicMember.objects.create(clinic=clinic, user=admin, role="admin", display_name="Rina")
    doc = ClinicMember.objects.create(clinic=clinic, user=dentist, role="dentist", display_name="Dr. Noa")
    Chair.objects.create(clinic=clinic, name="Chair 1")
    Chair.objects.create(clinic=clinic, name="Chair 2", active=False)
    Invitation.objects.create(clinic=clinic, email="waiting.dentist@example.com", role="dentist", invited_by=admin)
    filling = ProcedureType.objects.create(clinic=clinic, code="FILL", name_en="Filling")
    crown = ProcedureType.objects.create(clinic=clinic, code="CROWN", name_en="Crown")
    people = []
    for i, (name, lang, year) in enumerate([("Amal Tesfay", "ti", 1990), ("Boris Ivanov", "ru", 1975), ("Chen Wei", "en", 1988),
                                             ("Dalia Haddad", "ar", 2001), ("Efrem Gebre", "ti", 1997), ("Fatima Noor", "hi", 1969),
                                             ("Georgios Pappas", "en", 1982), ("Hanna Berg", "he", 1995)]):
        first, last = name.split()
        p = Patient.objects.create(clinic=clinic, first_name=first, last_name=last, preferred_language=lang, birth_year=year,
                                   phone=f"050-000000{i}", needs_interpreter=lang in ("ti", "hi"))
        people.append(p)
    me = people[0]
    me.user = patient_user
    me.id_kind = "unhcr"
    me.id_number = "DEMO-U-0001"
    me.front_desk_notes = "Prefers afternoons; comes with her brother who translates."
    me.save()
    HistoryItem.objects.create(patient=me, kind="allergy", what="penicillin", noted_by=dentist)
    HistoryItem.objects.create(patient=me, kind="condition", what="diabetes", detail="type 2, metformin", noted_by=dentist)
    HistoryItem.objects.create(patient=me, kind="condition", what="hypertension", active=False, noted_by=dentist)
    PlanItem.objects.create(patient=me, tooth=16, procedure=filling, status="done", priority=1)
    PlanItem.objects.create(patient=me, tooth=36, procedure=crown, status="planned", priority=2, note="after the root canal")
    visit = Visit.objects.create(patient=me, dentist=doc, notes="working notes", started_at=timezone.now() - timedelta(days=20))
    VisitProcedure.objects.create(visit=visit, procedure=filling, tooth=16, surface="O")
    Appointment.objects.create(clinic=clinic, patient=me, dentist=doc, starts_at=timezone.now() + timedelta(days=4, hours=2), reason="Crown, tooth 36")
    Appointment.objects.create(clinic=clinic, patient=me, dentist=doc, starts_at=timezone.now() + timedelta(days=25))
    Appointment.objects.create(clinic=clinic, patient=me, dentist=doc, starts_at=timezone.now() - timedelta(days=20), status="done")
    other = people[1]
    PatientLink.objects.create(patient=other, made_by=admin, expires_at=timezone.now() + timedelta(days=7))
    return clinic, me, other


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


def _open(browser, live_server, who, path, viewport):
    phone = viewport["width"] < 600
    context = browser.new_context(viewport=viewport, device_scale_factor=1, is_mobile=phone, has_touch=phone, locale="en-US")
    page = context.new_page()
    if who:
        page.goto(f"{live_server.url}/dentist/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', f"{who}@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
    page.goto(f"{live_server.url}{path}", wait_until="networkidle")
    return context, page


def _screens(clinic, me, other):
    s = clinic.slug
    link = other.links.first()
    return [
        ("home-out", None, "/dentist/"), ("login", None, "/dentist/login/"),
        ("accept", None, f"/dentist/accept/{clinic.invitations.first().token}/"),
        ("join", None, f"/dentist/join/{link.token}/"),
        ("clinic-home-admin", "admin", f"/dentist/c/{s}/"), ("clinic-home-dentist", "dentist", f"/dentist/c/{s}/"),
        ("people", "admin", f"/dentist/c/{s}/people/"), ("setup", "admin", f"/dentist/c/{s}/setup/"),
        ("patients", "dentist", f"/dentist/c/{s}/patients/"), ("patients-found", "dentist", f"/dentist/c/{s}/patients/?q=a"),
        ("patient-new", "dentist", f"/dentist/c/{s}/patients/new/"),
        ("patient-dentist", "dentist", f"/dentist/c/{s}/p/{me.pk}/"), ("patient-admin", "admin", f"/dentist/c/{s}/p/{other.pk}/"),
        ("patient-edit", "admin", f"/dentist/c/{s}/p/{me.pk}/edit/"), ("patient-delete", "admin", f"/dentist/c/{s}/p/{me.pk}/delete/"),
        ("log", "admin", f"/dentist/c/{s}/log/"), ("me", "patient", "/dentist/me/"),
    ]


def test_every_screen_holds_on_every_phone_a_tablet_and_a_desktop(browser, live_server):
    clinic, me, other = build_world()
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = []
    for name, who, path in _screens(clinic, me, other):
        for width in PHONES + [TABLET["width"], DESKTOP["width"]]:
            viewport = {"width": width, "height": 844 if width < 600 else (1180 if width < 1000 else 800)}
            context, page = _open(browser, live_server, who, path, viewport)
            try:
                if not page.url.startswith(live_server.url + path.split("?")[0]):
                    problems.append(f"{name}@{width}: landed on {page.url}")
                    continue
                text = page.inner_text("body")
                for word in ALARM:
                    if re.search(rf"\b{re.escape(word)}\b", text):
                        problems.append(f"{name}@{width}: says {word!r}")
                if "Pilot. Not an official system" not in text:
                    problems.append(f"{name}@{width}: no pilot banner")
                for label, js, arg in (("past the edge", OVERFLOW_JS, width), ("fields under 16px", SMALL_FIELDS_JS, None),
                                       ("tap targets", TAP_JS, 44), ("a11y", A11Y_JS, None), ("contrast", CONTRAST_JS, None)):
                    found = page.evaluate(js, arg) if arg is not None else page.evaluate(js)
                    if found:
                        problems.append(f"{name}@{width}: {label} {found}")
                if page.evaluate("document.documentElement.scrollWidth") > width:
                    problems.append(f"{name}@{width}: page wider than the screen")
                if width in (390, 1280):
                    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
            finally:
                context.close()
    assert problems == [], "\n".join(problems)


def test_on_a_phone_the_dentist_finds_a_patient_and_reads_the_alert_first(browser, live_server):
    """The dentist's job, start to finish, on a phone (mistake 27): sign in,
    land on the clinic, search, open, see the alert before the name."""
    clinic, me, other = build_world()
    context, page = _open(browser, live_server, "dentist", "/dentist/", {"width": 390, "height": 844})
    try:
        assert page.url.endswith(f"/dentist/c/{clinic.slug}/")
        page.click("a.dn-nav-a, .dn-nav a:has-text('Patients')")
        page.fill('input[name="q"]', "ama")
        page.click("form.dn-search button")
        page.click(f'a[href="/dentist/c/{clinic.slug}/p/{me.pk}/"]')
        page.wait_for_selector(".dn-alert")
        alert = page.locator(".dn-alert").first.bounding_box()
        name = page.locator("h1").bounding_box()
        assert alert["y"] < name["y"], "the alert is read before the name"
        assert any("Penicillin" in t for t in page.locator(".dn-alert").all_inner_texts())
        # The first row of the list screens starts in the top half of the first screen (mistake 25).
        page.goto(f"{live_server.url}/dentist/c/{clinic.slug}/patients/", wait_until="networkidle")
        first_row = page.locator("a.dn-row").first.bounding_box()
        assert first_row["y"] < 844 / 2, first_row
    finally:
        context.close()


def test_on_a_phone_the_patient_opens_their_link_and_sees_their_appointment(browser, live_server):
    """The patient's road (mistake 40): the link, the sign-in, the record."""
    from dentist.models import PatientLink

    clinic, me, other = build_world()
    fresh = User.objects.create_user("fresh", "fresh@example.com", PASSWORD)
    link = PatientLink.objects.create(patient=other, made_by=None, expires_at=timezone.now() + timedelta(days=7))
    context, page = _open(browser, live_server, None, f"/dentist/join/{link.token}/", {"width": 390, "height": 844})
    try:
        page.click("a:has-text('I already have an account')")
        assert "/dentist/login/" in page.url
        page.fill('input[name="username"]', "fresh@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/dentist/me/")
        assert "Hello, Boris" in page.inner_text("h1")
        assert "your next appointment" in page.inner_text("body").lower()  # inner_text applies text-transform
        other.refresh_from_db()
        assert other.user == fresh
    finally:
        context.close()
