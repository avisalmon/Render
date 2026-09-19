"""SL-B4 — SensorLab: the first real screens, and the first dead-link guard.

See docs/sensorlab/backlog.md (SL-B4), spec §9.2 and §7.

Two screens: the track list (the member's home) and a lab overview. They are
the first pages in this app built on real content rather than placeholder
copy, which makes them the first place content and chrome can disagree.

**The guard that is new here, and is the point.** Epic A proved links stay
*inside* SensorLab's walls. Nothing yet proves they go anywhere. A lab
overview is exactly the screen that grows a "Start" button pointing at a
runner which does not exist until Epic D — and a 404 behind a primary action
is the failure mode this project keeps naming: the app knew it could not do
the thing and said nothing until the person tapped it. So every link on
these screens is followed, and has to answer.

**And the bug this sprint inherited.** `sensors.html` has been rendering
English sensor names on a Hebrew page since SL-C2, because the view carries
an English-only label dict. That is SL-A2's bug for the third time. SL-B4
needs bilingual sensor names for "what you'll need" anyway, so it is fixed
here rather than noted.
"""

import os
import re

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl11, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
TRACKS = "/sensorlab/lab/"
OVERVIEW = "/sensorlab/lab/measuring-g/"
SENSORS_PAGE = "/sensorlab/sensors/"
PHONE = {"width": 390, "height": 844}
MIN_TAP_PX = 44

HEBREW = re.compile(r"[֐-׿]")
#: Template syntax that reached the body means a template is being *printed*
#: rather than rendered — SL-A1's multi-line-comment bug, which every
#: structural assertion in the suite passed straight over.
TEMPLATE_SYNTAX = re.compile(r"\{%|\{\{|\{#")


def _member(django_user_model, name="ada", language="en"):
    from sensorlab.profiles import profile_for

    user = django_user_model.objects.create_user(name, password=PASSWORD)
    profile = profile_for(user)
    profile.language = language
    profile.save(update_fields=["language"])
    return user


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _body(html):
    """Just the <main>, so the chrome's own copy does not answer for a screen."""
    match = re.search(r"<main[^>]*>(.*)</main>", html, re.S)
    return match.group(1) if match else html


# ------------------------------------------------------------- they exist


def test_both_screens_are_behind_the_gate(client):
    for path in (TRACKS, OVERVIEW):
        response = client.get(path)
        assert response.status_code == 302
        assert "/sensorlab/login/" in response["Location"]


def test_the_track_list_shows_the_seeded_course(client, django_user_model):
    _seed()
    client.force_login(_member(django_user_model))
    html = client.get(TRACKS).content.decode()

    assert "Free Fall" in html
    assert "Measuring g" in html
    assert 'data-screen="tracks"' in html


def test_the_lab_overview_says_what_the_lab_is(client, django_user_model):
    _seed()
    client.force_login(_member(django_user_model))
    html = client.get(OVERVIEW).content.decode()

    assert "Measuring g" in html
    assert "Your phone contains a scale" in html          # the summary
    assert "12" in html                                    # estimated minutes
    assert 'data-screen="lab-overview"' in html


def test_the_overview_lists_the_five_steps_and_the_sensors_needed():
    """Before you spend twelve minutes, you should know what it will ask of
    you. spec §1 refuses a degradation tier, so "this lab needs your
    accelerometer" has to be readable *before* the lab starts, not discovered
    as a refusal halfway through."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.profiles import profile_for

    _seed()
    user = get_user_model().objects.create_user("bob", password=PASSWORD)
    profile_for(user)
    client = Client()
    client.force_login(user)
    html = _body(client.get(OVERVIEW).content.decode())

    for step in ("Intro", "Learn", "Predict", "Experiment", "Analysis"):
        assert step in html, f"the overview does not mention {step}"
    assert "Accelerometer" in html, "the overview never says which sensor it needs"


def test_an_unfinished_lab_does_not_appear(client, django_user_model):
    """Authoring happens against the live database, so an unpublished lab
    must be absent from the screens exactly as it is from the API."""
    from sensorlab.models import Lab

    _seed()
    lab = Lab.objects.get(slug="measuring-g")
    lab.is_published = False
    lab.save(update_fields=["is_published"])

    client.force_login(_member(django_user_model))
    assert "Measuring g" not in client.get(TRACKS).content.decode()
    assert client.get(OVERVIEW).status_code == 404


def test_an_empty_course_says_so_out_loud(client, django_user_model):
    """The state on the day this deploys, before the seed has run.

    A screen with nothing on it is the failure this project calls silence:
    the app knows there is no content and shows a blank page, which reads as
    broken rather than as empty. There is no seeding in this test on purpose.
    """
    client.force_login(_member(django_user_model))
    html = _body(client.get(TRACKS).content.decode())
    assert len(re.sub(r"<[^>]+>|\s", "", html)) > 40, "an empty track list renders nearly nothing"
    assert "nothing" in html.lower() or "no tracks" in html.lower() or "soon" in html.lower()


# -------------------------------------------------------------- both languages


@pytest.mark.parametrize("language,direction", [("en", "ltr"), ("he", "rtl")])
def test_each_screen_renders_in_each_language(client, django_user_model, language, direction):
    _seed()
    client.force_login(_member(django_user_model, name=f"u-{language}", language=language))

    for path in (TRACKS, OVERVIEW):
        html = client.get(path).content.decode()
        assert f'lang="{language}"' in html
        assert f'dir="{direction}"' in html
        assert not TEMPLATE_SYNTAX.search(_body(html)), f"template syntax leaked into {path}"

        has_hebrew = bool(HEBREW.search(_body(html)))
        if language == "he":
            assert has_hebrew, f"{path} in Hebrew contains no Hebrew"
        else:
            assert not has_hebrew, f"{path} in English contains Hebrew"


def test_the_sensor_names_are_in_the_pages_own_language(client, django_user_model):
    """SL-A2's bug, third appearance, this time shipped in SL-C2.

    The sensors screen built its labels from an English-only dict in the
    view, so a Hebrew reader was told "Accelerometer". The names are
    interface copy like everything else, so they now live in `strings.py`
    with both languages — and both screens that name a sensor read from
    there.
    """
    _seed()
    client.force_login(_member(django_user_model, name="hebrew-reader", language="he"))

    for path in (SENSORS_PAGE, OVERVIEW):
        body = _body(client.get(path).content.decode())
        assert "מד־תאוצה" in body, f"{path} shows the sensor name in English"
        assert "Accelerometer" not in body, f"{path} still shows the English label"


# --------------------------------------------------- the new guard: links answer


def _links(html):
    hrefs = set(re.findall(r'href="([^"]+)"', html))
    return sorted(h for h in hrefs if h.startswith("/sensorlab/"))


def test_every_link_on_the_new_screens_actually_answers(client, django_user_model):
    """Epic A proved links stay inside the walls. Nothing proved they arrive.

    A lab overview is precisely the screen that grows a primary action
    pointing at a runner that does not exist yet, and a 404 behind a "Start"
    button is this project's recurring failure: the app knew it could not do
    the thing and waited for somebody to tap it before saying so.
    """
    _seed()
    client.force_login(_member(django_user_model))

    dead = {}
    for path in (TRACKS, OVERVIEW):
        for href in _links(client.get(path).content.decode()):
            code = client.get(href).status_code
            if code not in (200, 302):
                dead[f"{path} → {href}"] = code
    assert dead == {}, f"links that do not answer: {dead}"


def test_the_overview_does_not_offer_what_it_cannot_do(client, django_user_model):
    """Epic D builds the runner. Until then the overview must say that
    plainly rather than present a button and fail behind it."""
    _seed()
    client.force_login(_member(django_user_model))
    html = _body(client.get(OVERVIEW).content.decode())

    # If a start control is shown at all, it is not a link to nowhere.
    assert "disabled" in html, "no honest not-yet state on the overview"
    assert 'href="/sensorlab/run/' not in html


def test_a_locked_lab_says_what_unlocks_it(client, django_user_model):
    """`prerequisite_lab` is in the model from SL-B1 and would otherwise stay
    invisible until Epic D — a lock with no label on it."""
    from sensorlab.models import Lab

    _seed()
    first = Lab.objects.get(slug="measuring-g")
    Lab.objects.create(
        track=first.track, slug="terminal-velocity", title_en="Terminal Velocity",
        title_he="מהירות סופית", summary_en="Why a feather loses.",
        summary_he="למה נוצה מפסידה.", order=2, is_published=True, prerequisite_lab=first,
    )

    client.force_login(_member(django_user_model))
    html = _body(client.get("/sensorlab/lab/terminal-velocity/").content.decode())
    assert "Measuring g" in html, "the overview does not name what unlocks it"


# ------------------------------------------------------------ on a real phone


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
            bad.push((el.textContent || el.tagName).trim().slice(0, 28) + ' h=' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    return {overflow: doc.scrollWidth > doc.clientWidth + 1,
            scrollW: doc.scrollWidth, clientW: doc.clientWidth};
}"""

CONTRAST_JS = """() => {
    const lum = (c) => {
        const m = c.match(/[\\d.]+/g) || [0, 0, 0];
        const [r, g, b] = m.slice(0, 3).map(v => {
            const s = v / 255;
            return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const bg = (el) => {
        let n = el;
        while (n && n !== document.documentElement) {
            const c = getComputedStyle(n).backgroundColor;
            if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c;
            n = n.parentElement;
        }
        return getComputedStyle(document.body).backgroundColor;
    };
    const bad = [];
    document.querySelectorAll('main *').forEach(el => {
        if (!el.textContent || !el.textContent.trim()) return;
        if (el.children.length) return;
        const s = getComputedStyle(el);
        if (s.visibility === 'hidden' || s.display === 'none') return;
        const a = lum(s.color), b = lum(bg(el));
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        if (ratio < 2) bad.push(el.textContent.trim().slice(0, 30) + ' ratio=' + ratio.toFixed(2));
    });
    return bad;
}"""


COMPONENT_LINK_JS = """() => {
    const bad = [];
    document.querySelectorAll('a.sl-card, a.sl-button, a.sl-chip').forEach(el => {
        const s = getComputedStyle(el);
        if ((s.textDecorationLine || '').includes('underline')) {
            bad.push((el.className || '') + ' :: ' + el.textContent.trim().slice(0, 24));
        }
    });
    return bad;
}"""


def _phone_sign_in(page, live_server, django_user_model):
    django_user_model.objects.filter(username="phone-b4").delete()
    django_user_model.objects.create_user("phone-b4", password="phone-pass-w0rd")
    page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    page.fill("#id_username", "phone-b4")
    page.fill("#id_password", "phone-pass-w0rd")
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")


def test_the_new_screens_hold_up_on_a_phone(phone_page, live_server, django_user_model):
    """Rendered and measured, in both languages, because this app's whole
    history is bugs that every assertion passed over and one look caught.

    Three things at once on purpose — taps, overflow, contrast — since each
    page load in a real browser is the expensive part, not each check.
    """
    _seed()
    _phone_sign_in(phone_page, live_server, django_user_model)

    failures = {}
    for language in ("en", "he"):
        phone_page.goto(live_server.url + f"/sensorlab/language/{language}/",
                        wait_until="domcontentloaded")
        for path in (TRACKS, OVERVIEW):
            phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
            where = f"{language} {path}"

            small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
            if small:
                failures[f"{where} taps"] = small
            spill = phone_page.evaluate(OVERFLOW_JS)
            if spill["overflow"]:
                failures[f"{where} overflow"] = spill
            invisible = phone_page.evaluate(CONTRAST_JS)
            if invisible:
                failures[f"{where} contrast"] = invisible
            underlined = phone_page.evaluate(COMPONENT_LINK_JS)
            if underlined:
                failures[f"{where} component links"] = underlined

    assert failures == {}, f"on a 390px phone: {failures}"


def test_an_anchor_dressed_as_a_component_keeps_the_components_look(
    phone_page, live_server, django_user_model
):
    """The specificity trap, second occurrence, now guarded generally.

    `.sl-shell a` is (0,1,1) and outranks any single component class
    (0,1,0), so an anchor wearing a component's clothes silently keeps the
    shell's link styling. In SL-A4.1 that painted the deployed landing
    page's primary button ink-on-ink, and it was fixed for `.sl-button`
    alone. Here the same rule underlined every row of the lab list.

    Patching a third class would have left a fourth to find, so the CSS now
    states the general rule and this states it back: a component owns its
    own affordance. Computed style in a real browser is the only place that
    is true or false — a stylesheet grep cannot resolve a cascade.
    """
    _seed()
    _phone_sign_in(phone_page, live_server, django_user_model)

    offenders = {}
    for path in (TRACKS, OVERVIEW):
        phone_page.goto(live_server.url + path, wait_until="domcontentloaded")
        found = phone_page.evaluate(COMPONENT_LINK_JS)
        if found:
            offenders[path] = found
    assert offenders == {}, f"component anchors still wearing the shell's underline: {offenders}"
