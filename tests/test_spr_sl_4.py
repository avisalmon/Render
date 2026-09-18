"""SL-A4 — SensorLab: the design system (spec §7).

See docs/sensorlab/backlog.md (SL-A4). This turns spec §7 from prose into
tokens, components and two guard tests.

Why the guards are the point of this sprint rather than a nicety: SL-A1 and
SL-A2 each shipped a bug that every assertion passed over and only looking
at the page caught. A design system is where that keeps happening, because
"it looks wrong" is exactly the class of failure a unit test does not have
an opinion about. So three of these run in a real browser.

The CSS checks follow the shape memz's own stylesheet test already uses in
tests/test_smoke.py, and the phone checks follow tests/test_matazim_mobile.py.
Neither is invented here.
"""

import os
import re
from pathlib import Path

import pytest

# `live_server` runs the app on its own thread; Django refuses sync ORM calls
# from a thread with a live loop unless told this is deliberate. Same escape
# tests/test_matazim_mobile.py documents.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl4, pytest.mark.django_db]

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "static" / "sensorlab" / "css" / "sensorlab.css"

PHONE = {"width": 390, "height": 844}
MIN_TAP_PX = 44  # spec §7.4 — the app is used one-handed, possibly outdoors

DESIGN = "/sensorlab/design/"
PUBLIC_PAGES = ["/sensorlab/", "/sensorlab/login/", "/sensorlab/signup/"]
MEMBER_PAGES = ["/sensorlab/lab/", DESIGN]

def _code(css):
    """The stylesheet with its comments stripped.

    Written after the first run of `test_instrument_mode_is_a_scope...`
    failed on the sentence *explaining* the rule it enforces: the comment at
    the top of the stylesheet says a parallel `--sl-dark-*` set would defeat
    the scope, and the test matched that prose. A guard that reads the
    documentation instead of the code is worse than no guard, because it
    fails for reasons that have nothing to do with the thing it protects.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


#: Physical direction in CSS is what breaks a mirrored layout, and it breaks
#: it silently — the page still renders, just wrong way round. SL-A5 flips
#: this app to Hebrew; these properties are what would survive the flip and
#: keep pointing the old way.
PHYSICAL = re.compile(
    r"(?<![\w-])(?:margin|padding|border)-(?:left|right)\s*:"
    r"|(?<![\w-])(?:left|right)\s*:\s*(?!auto)"
    r"|text-align\s*:\s*(?:left|right)",
)


# ------------------------------------------------------------- the tokens


def test_every_token_used_is_defined():
    """A `var()` with no definition is a dead rule that still parses — the
    same silent failure memz's stylesheet test guards against."""
    css = _code(CSS.read_text(encoding="utf-8"))
    defined = set(re.findall(r"(--sl-[\w-]+)\s*:", css))
    used = set(re.findall(r"var\(\s*(--sl-[\w-]+)", css))
    missing = sorted(used - defined)
    assert not missing, f"used in a rule but never defined: {missing}"


def test_instrument_mode_is_a_scope_that_swaps_the_tokens():
    """spec §7.1: a screen *opts into* instrument mode; it does not restyle
    itself. So the dark mode must redefine the same token names rather than
    introduce a parallel set of `--sl-dark-*` ones."""
    css = _code(CSS.read_text(encoding="utf-8"))
    block = re.search(r"\.sl-instrument\b[^{]*\{(.*?)\}", css, re.S)
    assert block, "no .sl-instrument scope in the stylesheet"
    swapped = set(re.findall(r"(--sl-[\w-]+)\s*:", block.group(1)))
    for token in ("--sl-ground", "--sl-surface", "--sl-ink", "--sl-measurement"):
        assert token in swapped, f"instrument mode does not swap {token}"
    assert not re.search(r"--sl-dark-", css), "a parallel dark token set defeats the scope"


def test_the_stylesheet_uses_logical_properties_only():
    """spec §7.7 / SL-A5. `padding-left` survives a mirror and keeps pointing
    the same way; `padding-inline-start` does not. Caught here rather than in
    SL-A5, because by then it is a sweep of every component instead of a
    habit."""
    offenders = []
    for i, line in enumerate(CSS.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("/*")[0]
        if PHYSICAL.search(code):
            offenders.append(f"{i}: {line.strip()[:70]}")
    assert offenders == [], "physical direction in a stylesheet that must mirror:\n" + "\n".join(offenders)


# -------------------------------------------------- the reference page


def test_the_reference_page_shows_every_component(client, django_user_model):
    """spec §7 / backlog: one page rendering the whole system, so a
    regression is visible instead of theoretical."""
    user = django_user_model.objects.create_user("designer", password="x")
    client.force_login(user)
    html = client.get(DESIGN).content.decode()
    assert 'data-screen="design"' in html
    shown = set(re.findall(r'data-component="([\w-]+)"', html))
    for component in ("rail", "card", "button", "chip", "stat", "chart", "nav"):
        assert component in shown, f"the reference page does not show: {component}"


def test_the_reference_page_shows_both_modes(client, django_user_model):
    user = django_user_model.objects.create_user("designer2", password="x")
    client.force_login(user)
    html = client.get(DESIGN).content.decode()
    assert "sl-instrument" in html, "instrument mode is not on the reference page"


def test_a_chart_never_mirrors(client, django_user_model):
    """spec §7.7, the rule that lives in the component rather than in each
    caller's memory: chrome mirrors, geometry and numerals do not."""
    user = django_user_model.objects.create_user("designer3", password="x")
    client.force_login(user)
    html = client.get(DESIGN).content.decode()
    charts = re.findall(r"<[^>]*data-component=\"chart\"[^>]*>", html)
    assert charts, "no chart on the reference page"
    for chart in charts:
        assert 'dir="ltr"' in chart, f"a chart that would mirror in Hebrew: {chart[:90]}"


# ------------------------------------------------ in a real browser


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


TAP_JS = """(minPx) => {
    const bad = [];
    document.querySelectorAll('a, button, input, select, [role=button]').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.height < minPx) {
            bad.push((el.textContent || el.name || el.tagName).trim().slice(0, 28) +
                     ' h=' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    return {overflow: doc.scrollWidth > doc.clientWidth + 1,
            scrollW: doc.scrollWidth, clientW: doc.clientWidth};
}"""


def _sign_in(page, live_server, django_user_model):
    django_user_model.objects.filter(username="phone-tester").delete()
    django_user_model.objects.create_user("phone-tester", password="phone-pass-w0rd")
    page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    page.fill("#id_username", "phone-tester")
    page.fill("#id_password", "phone-pass-w0rd")
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")


def test_everything_tappable_clears_44px(phone_page, live_server, django_user_model):
    """spec §7.4. ustrip's equivalent exists *because* "phone-first" was an
    intention with nothing checking it, and it shipped 20px checkboxes."""
    _sign_in(phone_page, live_server, django_user_model)
    failures = {}
    for path in PUBLIC_PAGES + MEMBER_PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            failures[path] = small
    assert failures == {}, f"under {MIN_TAP_PX}px: {failures}"


def test_instrument_mode_actually_applies_its_own_tokens(phone_page, live_server, django_user_model):
    """Found by looking at the reference page: the big "9.81" readout was
    almost invisible — dark grey on near-black.

    `.sl-instrument` redefined every token correctly, and the file-level test
    above passed, because redefining a custom property is not the same as
    *using* it. `color` is inherited: `body` had already resolved
    `var(--sl-ink)` to the light mode's dark ink, and that inherited straight
    through the dark panel. Any component that did not set its own colour —
    which is most of them, deliberately — kept the wrong one.

    So the scope has to apply its tokens to itself, not merely declare them.
    This checks the computed result in a browser, which is the only place the
    difference between "declared" and "applied" is visible at all.
    """
    _sign_in(phone_page, live_server, django_user_model)
    phone_page.goto(live_server.url + DESIGN, wait_until="domcontentloaded")

    readings = phone_page.evaluate(
        """() => {
            const panel = document.querySelector('[data-mode=instrument]');
            const value = panel.querySelector('.sl-stat-value');
            const rgb = s => s.match(/\\d+/g).slice(0, 3).map(Number);
            const lum = c => (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
            return {
                text: lum(rgb(getComputedStyle(value).color)),
                ground: lum(rgb(getComputedStyle(panel).backgroundColor)),
            };
        }"""
    )
    # Dark ground, light text — and far enough apart to actually read.
    assert readings["ground"] < 0.2, f"instrument mode is not dark: {readings}"
    assert readings["text"] > 0.6, f"text in instrument mode is not light: {readings}"
    assert readings["text"] - readings["ground"] > 0.5, f"no contrast: {readings}"


def test_no_page_scrolls_sideways_on_a_phone(phone_page, live_server, django_user_model):
    """A phone-only app that scrolls sideways is broken, not imperfect."""
    _sign_in(phone_page, live_server, django_user_model)
    failures = {}
    for path in PUBLIC_PAGES + MEMBER_PAGES:
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        result = phone_page.evaluate(OVERFLOW_JS)
        if result["overflow"]:
            failures[path] = result
    assert failures == {}, f"sideways scroll: {failures}"


def test_no_native_dialog_ever_fires(phone_page, live_server, django_user_model):
    """spec §7.4. A native confirm blocks the page, ignores the app's design,
    and on iOS announces the site's domain. ustrip proved this test catches a
    real regression rather than merely passing.

    Armed with a dialog listener: if anything calls confirm/alert/prompt the
    listener records it, and SensorLab's own in-page confirm must appear
    instead.
    """
    _sign_in(phone_page, live_server, django_user_model)
    fired = []
    phone_page.on("dialog", lambda d: (fired.append(d.type), d.dismiss()))

    phone_page.goto(live_server.url + DESIGN, wait_until="domcontentloaded")
    phone_page.click("[data-demo='confirm']")
    phone_page.wait_for_selector(".sl-dialog", timeout=3000)

    assert fired == [], f"a native dialog fired: {fired}"
    assert phone_page.is_visible(".sl-dialog"), "SensorLab's own confirm did not appear"
