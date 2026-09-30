"""exo — the workshop link and the group wall, in a real browser (spec EPIC K).

Everything here is something the Django test client cannot see. The link has to
work for somebody who has never signed in, in a browser with no cookie, and end
with them looking at the builder. The publish choice saves over fetch, so a
server-side test proves the view and nothing about whether the radio reaches
it. And the group wall is two links whose whole job is to change what is on the
screen.

Every bug Avi found in this app so far was found by using it, not by reading it.
This file is the attempt to get there first.
"""

import os

import pytest
from sensorlab_phone import PHONE

# Playwright's sync API keeps an event loop alive in this thread, and Django
# refuses ordinary database calls while one is running. Same flag, same
# reason, as tests/test_exo_phone.py.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.django_db

PASSWORD = "exo-workshop-passw0rd"
DESKTOP = {"width": 1280, "height": 900}


@pytest.fixture(scope="module")
def browser(django_db_setup):
    """`django_db_setup` first, deliberately: the test database gets built
    before the event loop exists, rather than depending on which file ran
    earlier in the session."""
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch()
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_exo", quiet=True, stdout=StringIO())


def _phone(browser):
    return browser.new_context(viewport=PHONE, device_scale_factor=2,
                               is_mobile=True, has_touch=True).new_page()


def _desktop(browser):
    return browser.new_context(viewport=DESKTOP).new_page()


def _a_finished_concept(user, cohort, headline):
    from exo.models import Concept, NewspaperStyle, PressRelease

    concept = Concept.objects.create(
        owner=user, title="A falafel shop", stage=Concept.Stage.OUTPUT,
        cohort=cohort, mtp="Lunch worth queueing for",
    )
    return PressRelease.objects.create(
        concept=concept, headline=headline,
        body="A paragraph long enough to wrap.\n\nAnd a second one.",
        document_body="A longer document body.",
        exponential_score=58, score_rationale="Because.",
        newspaper_style=NewspaperStyle.objects.first(),
    )


def _joins_through(page, live_server, cohort):
    """Open the link the way a participant does, and return their account."""
    from django.contrib.auth import get_user_model

    before = set(get_user_model().objects.values_list("pk", flat=True))
    page.goto(live_server.url + cohort.join_url(), wait_until="domcontentloaded")
    assert page.url.endswith("/exo/concepts/"), (
        f"the link should land in the builder, landed on {page.url}")
    return get_user_model().objects.exclude(pk__in=before).get()


def test_a_stranger_with_the_link_is_working_one_click_later(browser,
                                                             live_server):
    """The promise of the whole epic, in the only place it can be checked: a
    browser that has never been here, with no account and no cookie."""
    from exo.access import is_exo_member
    from exo.models import Cohort, CohortMember

    _seed()
    cohort = Cohort.objects.create(name="סדנת מנהלים, אוקטובר")
    page = _phone(browser)

    participant = _joins_through(page, live_server, cohort)

    assert is_exo_member(participant)
    assert CohortMember.objects.filter(cohort=cohort, user=participant).exists()
    # And they are looking at a page that invites them to start, not at a
    # sign-in form or an empty shell.
    assert page.locator("form[action*='concepts/new']").count() >= 1


def test_the_group_choice_saves_from_the_radio(browser, live_server, settings):
    """The panel posts over fetch, so only a browser proves the fifth option is
    wired to the view rather than merely rendered next to the other four."""
    from exo.models import Cohort, PressRelease

    # Saving a group piece screens it, and the live server runs in this
    # process, so an unset key keeps the test off the network.
    settings.OPENAI_API_KEY = ""

    _seed()
    cohort = Cohort.objects.create(name="סדנה, יום שני")
    page = _desktop(browser)
    participant = _joins_through(page, live_server, cohort)
    release = _a_finished_concept(participant, cohort, "Eighteen months of queues")

    page.goto(live_server.url + f"/exo/concepts/{release.concept.pk}/output/",
              wait_until="domcontentloaded")
    radio = page.locator("input[name=visibility][value=cohort]")
    assert radio.count() == 1, "the group option should be offered inside a workshop"
    radio.check()
    # The panel saves on the button, not on the radio, the same way it does for
    # the other four. Clicking the radio and walking away saves nothing, which
    # is the behaviour the rest of the panel already had.
    page.click("#savevis")
    page.wait_for_load_state("domcontentloaded")

    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.COHORT

    # And it comes back checked, so somebody returning tomorrow can see what
    # they chose.
    page.reload(wait_until="domcontentloaded")
    assert page.locator("input[name=visibility][value=cohort]").is_checked()


def test_the_switch_changes_what_is_on_the_wall(browser, live_server):
    """Two participants, one room. The piece is on the group wall and on no
    public wall, and the switch moves between them."""
    from exo.models import Cohort, PressRelease
    from exo.strings import STRINGS

    _seed()
    cohort = Cohort.objects.create(name="סדנה, יום שלישי")
    headline = "Eighteen months of queues"

    writer_page = _phone(browser)
    writer = _joins_through(writer_page, live_server, cohort)
    release = _a_finished_concept(writer, cohort, headline)
    release.visibility = PressRelease.Visibility.COHORT
    release.save()

    reader_page = _phone(browser)
    _joins_through(reader_page, live_server, cohort)

    group_label = STRINGS["museum.wall_group"]["he"]
    all_label = STRINGS["museum.wall_all"]["he"]

    reader_page.goto(live_server.url + "/exo/museum/",
                     wait_until="domcontentloaded")
    assert headline not in reader_page.content(), (
        "a group piece must not be on the everyone wall")

    reader_page.get_by_role("link", name=group_label).click()
    reader_page.wait_for_load_state("domcontentloaded")
    assert headline in reader_page.content(), "the room should see the room's work"

    reader_page.get_by_role("link", name=all_label).click()
    reader_page.wait_for_load_state("domcontentloaded")
    assert headline not in reader_page.content()

    # Somebody who never attended sees neither the piece nor the switch.
    passerby = _phone(browser)
    passerby.goto(live_server.url + "/exo/museum/", wait_until="domcontentloaded")
    assert headline not in passerby.content()
    assert group_label not in passerby.content()


def test_the_switch_fits_a_phone_and_a_desktop(browser, live_server):
    """Two rows of links now sit above the wall where there was one. Neither
    may run off the edge or shrink below the tap size."""
    from sensorlab_phone import MIN_TAP_PX, OVERFLOW_JS

    from exo.models import Cohort

    _seed()
    cohort = Cohort.objects.create(name="סדנה, יום רביעי")
    failures = {}

    for page, where in ((_phone(browser), "phone"), (_desktop(browser), "desktop")):
        _joins_through(page, live_server, cohort)
        page.goto(live_server.url + "/exo/museum/?wall=group",
                  wait_until="domcontentloaded")

        spill = page.evaluate(OVERFLOW_JS)
        if spill["overflow"]:
            failures[f"{where} sideways"] = spill

        for link in page.locator(".exo-sorts .exo-sort").all():
            box = link.bounding_box()
            if box and box["height"] < MIN_TAP_PX:
                failures[f"{where} {link.inner_text()}"] = round(box["height"])

    assert not failures, failures


def test_the_nav_still_fits_with_the_managers_extra_link(browser, live_server,
                                                          django_user_model):
    """An admin's nav carries one item more than anybody else's, and Hebrew
    and English set it at different widths. The narrowest screen is where a
    fifth item would wrap into the masthead."""
    from sensorlab_phone import MIN_TAP_PX, OVERFLOW_JS

    from exo.access import approve, membership_for
    from exo.strings import STRINGS

    _seed()
    boss = django_user_model.objects.create_superuser(
        "look-boss", "boss@example.com", PASSWORD)
    approve(membership_for(boss, create=True))

    page = _phone(browser)
    page.goto(live_server.url + "/exo/login/", wait_until="domcontentloaded")
    page.fill("#id_username", "look-boss")
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")

    failures = {}
    for language in ("he", "en"):
        page.goto(f"{live_server.url}/exo/language/{language}/",
                  wait_until="domcontentloaded")
        for path in ("/exo/", "/exo/museum/", "/exo/manage/cohorts/"):
            page.goto(live_server.url + path, wait_until="domcontentloaded")
            where = f"{language} {path}"

            link = page.get_by_role("link", name=STRINGS["nav.manage"][language],
                                    exact=True).first
            if link.count() == 0:
                failures[f"{where} no way in"] = True
                continue
            box = link.bounding_box()
            if box and box["height"] < MIN_TAP_PX:
                failures[f"{where} tap"] = round(box["height"])

            spill = page.evaluate(OVERFLOW_JS)
            if spill["overflow"]:
                failures[f"{where} sideways"] = spill

    assert not failures, failures
