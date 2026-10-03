"""F-13.5 — the apps reach babook's nav, not just its home page.

The portal has shown app cards since F-13.2, but cards on one page are not
navigation: from anywhere else on babook there was no way into any app at all.
A person reading a lesson had to go back to the home page to reach מט״צים.

**The load-bearing test is `test_the_nav_never_links_an_app_a_person_may_not_open`.**
The nav is on every page of the site, which makes it the widest possible place
to leak. A card that should not be on the home page is one page wrong; a nav
entry that should not be there is wrong everywhere, on every screen, including
the ones a stranger is reading.

This also removes a second answer rather than adding one. The house used to be
linked from the nav by its own flag; it is in this list now, under the same
function each app's own door asks.

Traces: main_spec 0.5, 0.6.
"""

import re

import pytest
from django.contrib.auth.models import Group, User

pytestmark = pytest.mark.spr135

PASSWORD = "spr135-pass-2208"

# Pages across babook, not just the home page: the nav is on all of them.
PAGES = ["/", "/courses/", "/blog/", "/profile/"]


@pytest.fixture
def people(db, settings):
    settings.SECURITY_VIEWER_EMAILS = ["avi@example.com"]
    settings.SECURITY_OWNER_EMAIL = ""
    settings.CONTENT_RELEVANCE_ENABLED = False

    family, _ = Group.objects.get_or_create(name="family")
    made = {}
    for key, email in (("stranger", "stranger@example.com"),
                       ("relative", "relative@example.com"),
                       ("owner", "avi@example.com")):
        made[key] = User.objects.create_user(username=email, email=email, password=PASSWORD)
    made["relative"].groups.add(family)
    return made


def _links(html):
    return set(re.findall(r'href="(/[a-z]+/)"', html))


# ------------------------------------------------- the one that matters


def test_the_nav_never_links_an_app_a_person_may_not_open(client, people):
    """Every page, every person, against the one function that decides.

    The nav is on every screen of the site, which makes a wrong entry here
    wrong everywhere at once.
    """
    from app.portal import APPS, may_enter

    for who, person in people.items():
        client.force_login(person)
        for page in PAGES:
            response = client.get(page)
            if response.status_code != 200:
                continue
            linked = _links(response.content.decode())
            for app in APPS:
                allowed = may_enter(person, app.slug)
                shown = app.path in linked
                if shown and not allowed:
                    pytest.fail(f"{who} is offered {app.path} on {page} and cannot open it")


def test_a_stranger_signed_out_is_offered_no_app(client, db, settings):
    settings.CONTENT_RELEVANCE_ENABLED = False
    body = client.get("/").content.decode()
    for path in ("/matazim/", "/blackjack/", "/memz/", "/ustrip/", "/home/"):
        assert f'href="{path}"' not in body


# ------------------------------------------------- it is actually there


def test_blackjack_is_reachable_from_any_page_not_only_the_home_page(client, people):
    """The request this was built for. A person two pages deep into babook
    could not reach the app at all."""
    client.force_login(people["stranger"])

    found = 0
    for page in PAGES:
        response = client.get(page)
        if response.status_code != 200:
            continue
        found += 1
        assert '/blackjack/' in _links(response.content.decode()), (
            f"blackjack is not linked from {page}"
        )
    assert found >= 2, "the sample did not cover enough pages to mean anything"


def test_everyone_sees_the_open_apps_and_only_the_owner_sees_the_house(client, people):
    client.force_login(people["stranger"])
    linked = _links(client.get("/").content.decode())
    for path in ("/blackjack/", "/matazim/", "/memz/", "/sensorlab/"):
        assert path in linked, f"{path} is missing from the nav"
    assert "/home/" not in linked
    assert "/ustrip/" not in linked

    client.force_login(people["relative"])
    assert "/ustrip/" not in _links(client.get("/").content.decode())

    client.force_login(people["owner"])
    assert "/home/" not in _links(client.get("/").content.decode())

    owner = people["owner"]
    owner.is_superuser = True
    owner.is_staff = True
    owner.save(update_fields=["is_staff", "is_superuser"])
    client.force_login(owner)
    assert "/home/" in _links(client.get("/").content.decode())


def test_the_nav_reads_the_registry_rather_than_a_list_of_its_own(client, people):
    """The property, not the behaviour. A hardcoded nav would survive an empty
    registry, and would then be the second answer section 0.5 exists to
    prevent."""
    import app.portal as portal

    real = portal.APPS
    try:
        portal.APPS = []
        portal._BY_SLUG = {}
        client.force_login(people["owner"])
        linked = _links(client.get("/").content.decode())
    finally:
        portal.APPS = real
        portal._BY_SLUG = {a.slug: a for a in real}

    for path in ("/blackjack/", "/matazim/", "/home/"):
        assert path not in linked, f"{path} is written into the template, not read"


def test_the_house_is_no_longer_linked_by_a_second_rule(client, people):
    """It used to have its own flag in the nav. One answer now, so the two
    cannot drift."""
    import pathlib

    base = pathlib.Path("templates/base.html").read_text(encoding="utf-8")
    assert "show_home_security" not in base, "the nav still has a second rule for the house"
    assert "nav_apps" in base
