"""exo on a real phone, in both directions (spec §0.2, §0.3).

Every other exo test asserts about strings in a response body. None of them
can see a 32px button, a page that scrolls sideways, or grey text on a grey
card — and this app is used in a lecture hall, on phones, by people who will
not persevere through a bad screen.

**Hebrew is the reason this file exists rather than a single-language phone
pass.** The whole app mirrors, and a mirrored layout fails in ways a Latin
layout never shows: a margin that pushed content away from the edge now pushes
it off the other one. So every page is measured in both directions, and the
RTL run is the one expected to find things.

The browser probes are imported from `sensorlab_phone` rather than copied.
That module exists because a third copy of these checks was about to diverge
from the other two, and its opening comment says so; tap size, sideways
overflow and contrast are browser physics, not any app's content, so exo uses
the same ones. The component-link probe is the exception: it names class
prefixes, so exo has its own.
"""

import os
import re

import pytest
from sensorlab_phone import CONTRAST_JS, MIN_TAP_PX, OVERFLOW_JS, PHONE, TAP_JS

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.django_db

PASSWORD = "exo-phone-passw0rd"

#: Template syntax that reaches the body means a template is being printed
#: rather than rendered. SensorLab shipped that bug once, past every
#: structural assertion in its suite.
TEMPLATE_SYNTAX = re.compile(r"\{%|\{\{|\{#")

#: exo's own version of the specificity trap: an anchor wearing a component's
#: clothes must not keep the shell's link styling.
EXO_COMPONENT_LINK_JS = """() => {
    const bad = [];
    document.querySelectorAll('a.exo-btn, a.exo-card, a.exo-concept-main, a.exo-paper')
        .forEach(el => {
            const s = getComputedStyle(el);
            if ((s.textDecorationLine || '').includes('underline')) {
                bad.push((el.className || '') + ' :: ' +
                         el.textContent.trim().slice(0, 24));
            }
        });
    return bad;
}"""

#: A page that mirrors must not leave text hanging off the inline edge. This
#: measures against the viewport rather than the parent, because the failure
#: is always "off the screen", never "off the div".
EDGE_JS = """() => {
    const bad = [];
    const w = document.documentElement.clientWidth;
    document.querySelectorAll('main *, header *, footer *').forEach(el => {
        if (!el.textContent || !el.textContent.trim()) return;
        if (el.children.length) return;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return;
        if (r.left < -1 || r.right > w + 1) {
            bad.push(el.textContent.trim().slice(0, 26) +
                     ' [' + Math.round(r.left) + '..' + Math.round(r.right) +
                     '] of ' + w);
        }
    });
    return [...new Set(bad)];
}"""


#: An element marked `hidden` that is still on screen. The `hidden` attribute
#: only carries the user agent's `display: none`, so any component rule with
#: its own `display` beats it silently. Computed style in a real browser is the
#: only place that is true or false.
HIDDEN_JS = """() => {
    const bad = [];
    document.querySelectorAll('[hidden]').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            bad.push((el.id || el.className || el.tagName) +
                     ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
        }
    });
    return bad;
}"""


@pytest.fixture(scope="module")
def phone_page():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport=PHONE, device_scale_factor=2, is_mobile=True,
                has_touch=True,
            )
            yield context.new_page()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_exo", quiet=True, stdout=StringIO())


def _member(django_user_model, name="phone-member"):
    from exo.access import approve, membership_for

    django_user_model.objects.filter(username=name).delete()
    user = django_user_model.objects.create_user(name, f"{name}@example.com",
                                                 PASSWORD)
    approve(membership_for(user, create=True))
    return user


def _a_finished_concept(user):
    from exo.models import Concept, ExoAttribute, GeneratedOption, NewspaperStyle, PressRelease

    concept = Concept.objects.create(
        owner=user, title="A car rental service", stage=Concept.Stage.OUTPUT,
        mtp="Movement without ownership",
    )
    attribute = ExoAttribute.objects.get(key="algorithms")
    concept.entries.create(attribute=attribute, text="predict demand per street")
    GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                   content="a demand model per street",
                                   is_selected=True)
    release = PressRelease.objects.create(
        concept=concept,
        headline="Cars arrive before anyone asks for them",
        body="A press release body long enough to wrap on a narrow screen and "
             "show whether the measure holds.",
        document_body="A longer document body.",
        exponential_score=61, score_rationale="Because.",
        newspaper_style=NewspaperStyle.objects.first(),
    )
    return concept, release


def _sign_in(page, live_server, name="phone-member"):
    page.goto(live_server.url + "/exo/login/", wait_until="domcontentloaded")
    page.fill("#id_username", name)
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")


def _measure(page, live_server, path, where, failures):
    page.goto(live_server.url + path, wait_until="domcontentloaded")

    body = page.inner_html("body")
    if TEMPLATE_SYNTAX.search(body):
        failures[f"{where} template printed"] = TEMPLATE_SYNTAX.findall(body)[:3]

    small = page.evaluate(TAP_JS, MIN_TAP_PX)
    if small:
        failures[f"{where} taps"] = small
    spill = page.evaluate(OVERFLOW_JS)
    if spill["overflow"]:
        failures[f"{where} overflow"] = spill
    invisible = page.evaluate(CONTRAST_JS)
    if invisible:
        failures[f"{where} contrast"] = invisible
    underlined = page.evaluate(EXO_COMPONENT_LINK_JS)
    if underlined:
        failures[f"{where} component links"] = underlined
    off_edge = page.evaluate(EDGE_JS)
    if off_edge:
        failures[f"{where} off the edge"] = off_edge
    showing = page.evaluate(HIDDEN_JS)
    if showing:
        failures[f"{where} hidden but visible"] = showing


def test_the_public_half_holds_up_on_a_phone(phone_page, live_server,
                                             django_user_model):
    """The landing, the handout, an attribute page and the museum — the four
    screens a person meets during the lecture itself, in both directions."""
    _seed()
    owner = _member(django_user_model, "phone-owner")
    _concept, release = _a_finished_concept(owner)

    paths = [
        "/exo/",
        "/exo/learn/",
        "/exo/learn/algorithms/",
        "/exo/museum/",
        f"/exo/museum/{release.pk}/",
        # The two doors. Left out of the first version of this list, which is
        # how a 17px "sign in" link reached production with the suite green.
        "/exo/join/",
        "/exo/login/",
    ]

    failures = {}
    for language in ("he", "en"):
        phone_page.goto(live_server.url + f"/exo/language/{language}/",
                        wait_until="domcontentloaded")
        for path in paths:
            _measure(phone_page, live_server, path, f"{language} {path}", failures)

    assert failures == {}, f"on a 390px phone: {failures}"


def test_the_builder_holds_up_on_a_phone(phone_page, live_server,
                                         django_user_model):
    """The four stages, which is where a member spends the workshop: long
    forms, chat bubbles, thirteen slots and a newspaper, all at 390px."""
    _seed()
    user = _member(django_user_model)
    concept, _release = _a_finished_concept(user)
    _sign_in(phone_page, live_server)

    paths = [
        "/exo/concepts/",
        f"/exo/concepts/{concept.pk}/interview/",
        f"/exo/concepts/{concept.pk}/brainstorm/",
        f"/exo/concepts/{concept.pk}/options/",
        f"/exo/concepts/{concept.pk}/output/",
    ]

    failures = {}
    for language in ("he", "en"):
        phone_page.goto(live_server.url + f"/exo/language/{language}/",
                        wait_until="domcontentloaded")
        for path in paths:
            _measure(phone_page, live_server, path, f"{language} {path}", failures)

    assert failures == {}, f"on a 390px phone: {failures}"


def test_every_newspaper_style_survives_a_narrow_screen(phone_page, live_server,
                                                        django_user_model):
    """Five papers, each with its own column rules. A broadsheet that looks
    right on a laptop and spills sideways on a phone is the likeliest
    regression in this app's CSS (spec §6.3)."""
    from exo.models import NewspaperStyle

    _seed()
    owner = _member(django_user_model, "phone-owner-2")
    _concept, release = _a_finished_concept(owner)

    failures = {}
    for style in NewspaperStyle.objects.all():
        release.newspaper_style = style
        release.save(update_fields=["newspaper_style"])
        for language in ("he", "en"):
            phone_page.goto(live_server.url + f"/exo/language/{language}/",
                            wait_until="domcontentloaded")
            _measure(phone_page, live_server, f"/exo/museum/{release.pk}/",
                     f"{language} {style.key}", failures)

    assert failures == {}, f"a paper broke on a 390px phone: {failures}"


def test_options_are_a_multiple_choice_in_a_real_browser(phone_page,
                                                         live_server,
                                                         django_user_model):
    """Ticking several options must accumulate, and removing one must not
    disturb the rest.

    This lives in the browser suite because the bug it guards could not be
    seen from the server. Every unit test called the select URL directly and
    passed, while in the page a delegated `closest("[data-drop]")` matched the
    container that held the delete URL, so every click anywhere in the list
    was handled as a delete and no tick ever registered. Only a real click on
    a real DOM shows that.
    """
    from exo.models import Concept, ExoAttribute, GeneratedOption

    _seed()
    user = _member(django_user_model, "phone-ticker")
    concept = Concept.objects.create(owner=user, title="A car rental service",
                                     stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    for i in range(4):
        GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                       content=f"option number {i}", order=i)

    _sign_in(phone_page, live_server, "phone-ticker")
    phone_page.goto(live_server.url + f"/exo/concepts/{concept.pk}/options/",
                    wait_until="domcontentloaded")

    rows = f'.exo-slot[data-key="{attribute.key}"] .exo-option'

    def ticked():
        return [i for i in range(phone_page.locator(rows).count())
                if "is-selected" in
                (phone_page.locator(rows).nth(i).get_attribute("class") or "")]

    assert ticked() == []
    for i in (0, 1, 2):
        phone_page.locator(rows).nth(i).click()
        phone_page.wait_for_timeout(350)
    assert ticked() == [0, 1, 2], "ticking one untick*ed* another"

    # It is the database that decides what reaches the final build.
    assert concept.options.filter(is_selected=True).count() == 3

    # Removing one is deliberate, and takes only that one.
    phone_page.locator(
        f'.exo-slot[data-key="{attribute.key}"] .exo-option-drop').nth(3).click()
    phone_page.wait_for_timeout(500)
    assert phone_page.locator(rows).count() == 3
    assert concept.options.filter(is_selected=True).count() == 3


def test_a_half_typed_answer_survives_closing_the_tab(phone_page, live_server,
                                                      django_user_model):
    """The other half of "it forgot what I started".

    Everything sent is stored server-side and was never at risk. What was lost
    is the sentence still sitting in the box when the tab closes, which is the
    thought you were in the middle of. It is kept in this browser, per concept,
    and cleared once the turn is actually sent.
    """
    from exo.models import Concept

    _seed()
    user = _member(django_user_model, "phone-drafter")
    concept = Concept.objects.create(owner=user, title="A car rental service")

    _sign_in(phone_page, live_server, "phone-drafter")
    url = live_server.url + f"/exo/concepts/{concept.pk}/interview/"
    phone_page.goto(url, wait_until="domcontentloaded")

    half_typed = "What I actually want to build is a service that"
    phone_page.fill("#say", half_typed)
    phone_page.wait_for_timeout(200)

    # Close the tab on it, the way a person does.
    phone_page.goto(live_server.url + "/exo/learn/", wait_until="domcontentloaded")
    phone_page.goto(url, wait_until="domcontentloaded")
    assert phone_page.input_value("#say") == half_typed, "the draft was lost"

    # And it does not leak into another concept's box.
    other = Concept.objects.create(owner=user, title="A different idea")
    phone_page.goto(live_server.url + f"/exo/concepts/{other.pk}/interview/",
                    wait_until="domcontentloaded")
    assert phone_page.input_value("#say") == ""


def test_a_new_feature_is_offered_above_and_below_and_always_asks(
        phone_page, live_server, django_user_model):
    """Two copies of one control, and neither replaces a feature silently.

    In the browser because that is where both facts live: that the top copy
    exists at all, and that a click puts a real question in front of the
    person before anything is overwritten. Two buttons wired to one behaviour
    is exactly the arrangement where one of them quietly stops working.
    """
    from exo.models import Concept, NewspaperStyle, PressRelease

    _seed()
    user = _member(django_user_model, "phone-writer")
    concept = Concept.objects.create(owner=user, title="A falafel shop",
                                     stage=Concept.Stage.OUTPUT)
    PressRelease.objects.create(
        concept=concept, headline="Eighteen months on",
        body="A feature long enough to fill the page. " * 12,
        document_body="The document.",
        newspaper_style=NewspaperStyle.objects.first(),
    )

    _sign_in(phone_page, live_server, "phone-writer")
    phone_page.goto(live_server.url + f"/exo/concepts/{concept.pk}/output/",
                    wait_until="domcontentloaded")

    buttons = phone_page.locator("[data-regen]")
    assert buttons.count() == 2, "the control is not offered in both places"

    # The top copy comes before the article, which is the whole point of it.
    positions = [buttons.nth(i).bounding_box()["y"] for i in range(2)]
    paper_y = phone_page.locator(".exo-paper").bounding_box()["y"]
    assert min(positions) < paper_y, "no copy of the control above the article"
    assert max(positions) > paper_y, "no copy of the control below the article"

    # Each asks before replacing anything, and a dismissed question changes
    # nothing at all.
    for i in range(2):
        asked = {}
        phone_page.once("dialog", lambda d: (asked.update(text=d.message),
                                             d.dismiss()))
        buttons.nth(i).click()
        phone_page.wait_for_timeout(400)
        assert asked.get("text"), f"copy {i} replaced the feature without asking"

    concept.refresh_from_db()
    assert concept.release.headline == "Eighteen months on", "it regenerated anyway"


def test_the_mirror_is_real_and_not_just_an_attribute(phone_page, live_server,
                                                      django_user_model):
    """`dir="rtl"` on the html element is easy to assert and easy to have
    without the layout actually mirroring. This checks a laid-out element
    really does sit on the other side of the screen in Hebrew."""
    _seed()

    def wordmark_left():
        phone_page.goto(live_server.url + "/exo/", wait_until="domcontentloaded")
        box = phone_page.locator(".exo-wordmark").bounding_box()
        return box["x"], box["width"]

    phone_page.goto(live_server.url + "/exo/language/en/",
                    wait_until="domcontentloaded")
    ltr_x, width = wordmark_left()

    phone_page.goto(live_server.url + "/exo/language/he/",
                    wait_until="domcontentloaded")
    rtl_x, _ = wordmark_left()

    viewport = PHONE["width"]
    assert ltr_x < viewport / 2, "in English the wordmark should start on the left"
    assert rtl_x + width > viewport / 2, "in Hebrew it never moved to the right"
