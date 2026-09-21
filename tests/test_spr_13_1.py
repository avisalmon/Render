"""SPR-13.1 — who sees which app (EPIC-13, main_spec §0.5, REQ-13.1).

Avi, 2026-09-21, answering ACT-27 with the list itself:

> memz everyone. Home security, I only for now. Matazim everyone. Ustrip
> family. Sensorlab everyone.

Three kinds of audience, and all three already existed in the code before this
module did: open to everyone, a Django group, and a named list of people.

**The load-bearing test is `test_the_card_and_the_door_never_disagree`.** The
whole reason this is one function rather than a list on the home page is that
two answers drift, and the drift is invisible in exactly the way that matters:
a card that 403s when clicked is embarrassing, and a hidden card whose URL still
opens is a leak. So the sweep asks both questions about every app for every kind
of person and fails if they ever differ.

Second in importance is `test_the_house_is_invisible_rather_than_refused`. The
existence of a private home security system is itself private, so the answer for
everybody else is 404 and not 403, and the portal must not name it either.

Traces: REQ-13.1, REQ-13.2, main_spec §0.5.
"""

import pytest
from django.contrib.auth.models import Group, User

pytestmark = pytest.mark.spr131

PASSWORD = "spr131-pass-7712"


def _user(email, name="someone"):
    return User.objects.create_user(username=email, email=email, password=PASSWORD)


@pytest.fixture
def people(db, settings):
    """One of each kind of person the answer distinguishes."""
    settings.SECURITY_VIEWER_EMAILS = ["avi@example.com"]
    settings.SECURITY_OWNER_EMAIL = ""

    # get_or_create, not create: `family` is seeded by a migration, so a test
    # that made its own was asserting against a world ustrip does not live in.
    family, _ = Group.objects.get_or_create(name="family")
    made = {
        "stranger": _user("stranger@example.com"),
        "relative": _user("relative@example.com"),
        "owner": _user("avi@example.com"),
        "staff": _user("staff@example.com"),
    }
    made["relative"].groups.add(family)
    made["staff"].is_staff = True
    made["staff"].is_superuser = True
    made["staff"].save(update_fields=["is_staff", "is_superuser"])
    return made


def _slugs(user):
    from app.portal import visible_apps

    return [a.slug for a in visible_apps(user)]


# ------------------------------------------------- the one that matters


def test_the_card_and_the_door_never_disagree(people):
    """One function, asked two ways, for every app and every person.

    A card the portal shows must open, and an app the portal hides must not.
    This is the sweep rather than five hand-written cases, because the app that
    drifts will be the one nobody remembered to check.
    """
    from app.portal import APPS, may_enter, visible_apps

    for who, person in people.items():
        shown = {a.slug for a in visible_apps(person)}
        for app in APPS:
            opens = may_enter(person, app.slug)
            assert opens == (app.slug in shown), (
                f"{who}: the portal says {app.slug in shown} about {app.slug} "
                f"and the door says {opens}"
            )


# ------------------------------------------------- Avi's list, as written


def test_everyone_means_every_signed_in_person(people):
    """memz, מט״צים and SensorLab. Note what "everyone" does *not* mean: an app
    open to all still runs its own rules inside. מט״צים shows a stranger its
    front door and an entrance test, not a member's screens."""
    for who in ("stranger", "relative", "owner", "staff"):
        for slug in ("memz", "matazim", "sensorlab"):
            assert slug in _slugs(people[who]), f"{who} cannot see {slug}"


def test_ustrip_is_the_family_and_nobody_else(people):
    assert "ustrip" in _slugs(people["relative"])
    for who in ("stranger", "owner"):
        assert "ustrip" not in _slugs(people[who]), f"{who} was shown the family trip"


def test_the_house_is_one_person(people):
    assert "home" in _slugs(people["owner"])
    for who in ("stranger", "relative"):
        assert "home" not in _slugs(people[who])


def test_being_staff_grants_nothing_unless_an_app_says_so(people):
    """Deliberate, and the opposite of what most permission code does.

    A superuser can already reach anything through /admin/, so a blanket bypass
    here buys nothing and costs the rules that are actually about privacy.

    **One exception, and it is declared rather than assumed.** ustrip has let
    any superuser in since it was built, so the site admin never has to
    remember to add themself to `family` before opening his own app. F-13.4
    found that as a disagreement: the door opened and the portal showed no
    card. The fix was to move the exception onto the app in the registry, where
    the portal can see it, rather than to change what ustrip allows. Nobody
    gained access they did not already have.

    The house declares no such exception, and that is the point of having the
    flag per app instead of one rule for staff: a superuser who is not on the
    list still cannot see it.
    """
    seen = _slugs(people["staff"])
    assert "home" not in seen, "an admin was handed somebody's house"
    assert "ustrip" in seen, "the card still hides what ustrip's door opens"

    from app.portal import APPS

    declared = {a.slug for a in APPS if a.admin_bypass}
    assert declared == {"ustrip"}, f"an app quietly granted admins access: {declared}"


def test_a_stranger_signed_out_sees_no_cards(db):
    """The portal is a per-person thing, so an anonymous visitor gets the
    public home page rather than a menu of other people's apps."""
    from django.contrib.auth.models import AnonymousUser

    assert _slugs(AnonymousUser()) == []


# ------------------------------------------------- privacy properties


def test_the_house_is_invisible_rather_than_refused(client, people):
    """404, not 403. "You may not see this" still says the thing exists, and
    the existence of a private security system in a named person's house is
    itself the private part."""
    client.force_login(people["relative"])
    assert client.get("/home/").status_code == 404


def test_the_portal_never_names_an_app_it_is_hiding(client, people, settings):
    """The card is not the only way a page can leak. A hidden app must not be
    linked at all, including from a disabled card or a tooltip.

    Checked as a link target rather than as a substring: the first version of
    this test searched the HTML for "/home/" and failed on `/static/img/home/`,
    an image folder that has nothing to do with the house. A test that fails
    for the wrong reason teaches you to ignore it.
    """
    settings.CONTENT_RELEVANCE_ENABLED = False
    client.force_login(people["stranger"])
    body = client.get("/").content.decode()
    for hidden in ("/ustrip/", "/home/"):
        assert f'href="{hidden}"' not in body, f"the home page links {hidden} to a stranger"


# ------------------------------------------------- the registry itself


def test_every_installed_app_is_in_the_registry_or_deliberately_out():
    """§0.6 is a directory, and a directory that silently omits something is
    worse than no directory. An app added to the site without an audience
    decision fails here rather than quietly appearing to nobody.
    """
    from app.portal import APPS, NOT_IN_THE_PORTAL

    known = {a.slug for a in APPS} | set(NOT_IN_THE_PORTAL)
    installed = {"matazim", "ustrip", "memz", "sensorlab"}
    assert installed <= known, f"no audience decided for: {sorted(installed - known)}"


def test_an_audience_nobody_implemented_hides_the_app(people):
    """The fallthrough, exercised rather than assumed.

    Found by the perturbation run: breaking the final `return False` changed
    nothing, because every app in the registry uses one of the three kinds and
    the line is unreachable. It is reachable the day somebody adds a fourth
    kind and forgets a branch, and that day it must hide the app rather than
    show it to the whole internet. So the test builds that app itself.
    """
    from app.portal import App, _may

    invented = App(slug="x", name="x", path="/x/", audience="whatever-comes-next",
                   blurb="", key="")
    for person in people.values():
        assert _may(person, invented) is False


def test_crashtech_is_out_until_avi_says(people):
    """He listed five apps on 2026-09-21 and CrashTech was not among them.
    Absent from the portal is the honest reading of that, and this pins it so
    that adding it is a decision rather than a drift."""
    from app.portal import NOT_IN_THE_PORTAL

    assert "crashtech" in NOT_IN_THE_PORTAL
    assert "crashtech" not in _slugs(people["staff"])


# ------------------------------------------------- F-13.2, the page itself


def _home(client, person, settings):
    settings.CONTENT_RELEVANCE_ENABLED = False
    client.force_login(person)
    return client.get("/").content.decode()


def test_the_page_shows_a_person_their_own_apps(client, people, settings):
    """The card is a link to the app, so it is checked as one. A heading that
    says the right word above nothing is not a portal."""
    body = _home(client, people["relative"], settings)
    for expected in ('href="/memz/"', 'href="/matazim/"', 'href="/sensorlab/"',
                     'href="/ustrip/"'):
        assert expected in body, f"the family member's home page is missing {expected}"
    assert 'href="/home/"' not in body


def test_the_page_never_hardcodes_the_list(client, people, settings):
    """§0.5 as a property of the template rather than a promise.

    If the cards came from the template instead of from `visible_apps`, they
    would survive an empty registry, and the home page would become the second
    answer this whole module exists to prevent.
    """
    import app.portal as portal

    real = portal.APPS
    try:
        portal.APPS = []
        portal._BY_SLUG = {}
        body = _home(client, people["owner"], settings)
    finally:
        portal.APPS = real
        portal._BY_SLUG = {a.slug: a for a in real}

    for gone in ('href="/memz/"', 'href="/matazim/"', 'href="/sensorlab/"'):
        assert gone not in body, f"{gone} is written into the template, not read from the registry"


def test_a_logged_out_visitor_sees_the_page_they_saw_before(client, db, settings):
    """The portal is per person, so the public page is unchanged. Asserted
    because "add a section for signed-in people" is one careless `{% if %}`
    away from changing what a stranger sees."""
    settings.CONTENT_RELEVANCE_ENABLED = False
    body = client.get("/").content.decode()
    assert "המרחבים שלך" not in body
    for hidden in ('href="/ustrip/"', 'href="/home/"'):
        assert hidden not in body
    assert "הדרכות" in body, "the training hero is what a visitor comes for"


def test_training_is_still_the_hero(client, people, settings):
    """§0.1: babook keeps training as its core business, and the apps sit
    under it. If the cards ever climb above the training hero, this fails and
    somebody decides that on purpose."""
    body = _home(client, people["owner"], settings)
    assert body.index("training-hero") < body.index("home-apps")


# ------------------------------------------- F-13.4, the doors themselves


def test_a_verified_address_on_the_list_gets_both_the_card_and_the_door(client, people, settings):
    """The first disagreement F-13.4 found, and it was already live.

    `/home`'s door accepts a *verified allauth address* that differs from
    `User.email`, because allauth may hold a confirmed address the User row
    does not. The portal only ever looked at `User.email`. So somebody in
    exactly that position could open the house and never see a card for it.

    The door's rule is the right one, so the card adopts it rather than the
    door being narrowed: this is a person the owner deliberately let in.
    """
    from app.portal import may_enter

    person = people["stranger"]
    emailaddress = pytest.importorskip("allauth.account.models").EmailAddress
    emailaddress.objects.create(user=person, email="AVI@example.com",
                                verified=True, primary=False)

    assert may_enter(person, "home"), "the card does not know what the door allows"
    client.force_login(person)
    assert client.get("/home/").status_code == 200


def test_the_ustrip_door_and_the_ustrip_card_agree_for_an_admin(client, people):
    """The second disagreement, also already live.

    ustrip lets any superuser in on purpose, so the site admin never has to
    remember to add themself to `family` before they can open their own app.
    The portal said staff get nothing. So an admin who is not in the family
    saw no card and could still open the trip.

    Recorded as one rule rather than two: the exception is declared on the app
    in the registry, where it is visible, instead of living inside ustrip where
    the portal could not see it.
    """
    from app.portal import may_enter

    admin = people["staff"]
    assert may_enter(admin, "ustrip"), "the card hides what the door opens"

    client.force_login(admin)
    assert client.get("/ustrip/").status_code == 200


def test_each_door_asks_the_registry_rather_than_repeating_it():
    """F-13.4 as a grep, so the next person cannot quietly add a second copy.

    The property this sprint is about is not "these two agree today", it is
    "there is only one of them". Two functions that agree are one edit away
    from not agreeing.
    """
    import pathlib
    import re

    for path, name in (("ustrip/access.py", "is_family"),
                       ("app/security_views.py", "can_view")):
        src = pathlib.Path(path).read_text(encoding="utf-8")
        body = re.search(rf"def {name}\(.*?\n(?=\n\ndef |\n\n# )", src, re.S)
        assert body, f"{name} not found in {path}"
        assert "portal" in body.group(0), f"{path}:{name} decides for itself"
