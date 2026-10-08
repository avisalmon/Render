"""SPR-I.1.1 improv: the app, its chrome, its gate and its portal card.

Avi, 2026-10-04: the app was private to him, with a 404 for everyone else.
On 2026-10-08 he opened it on purpose: anyone who is signed in is a player, the
babook portal shows no card (the link is shared by hand), and a visitor who is
not signed in is sent to the app's own front door. test_spri_9_1 holds the new
door in detail; this file keeps the sweep and the registry entry honest.

**The load-bearing test is `test_every_route_admits_a_signed_in_person_and_stops_a_visitor`.**
It walks every route the app registers, and knocks on each as a visitor, a
signed-in person with no group, a member of the old group and an admin. It is
written so the next route somebody adds is covered the day it appears rather
than the day somebody remembers.

Traces: spec ch. 7, data model section 0.
"""

import io
import re

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.urls import URLPattern, URLResolver

pytestmark = pytest.mark.spri11

PASSWORD = "spri11-pass-5521"
GROUP = "improv_players"


def _user(name, **flags):
    user = User.objects.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    return user


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name=GROUP)
    made = {
        "stranger": _user("stranger"),
        "member": _user("member"),
        "admin": _user("admin", is_staff=True, is_superuser=True),
    }
    made["member"].groups.add(group)
    # The sweep fills a detail route with id 1; there has to be a row 1 behind it.
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return made


def _client_for(user=None, **kwargs):
    client = Client(**kwargs)
    if user is not None:
        client.force_login(user)
    return client


# ------------------------------------------------------ walking the routes


def _route_text(pattern):
    """One URL fragment from one pattern, with every parameter filled in.

    Handles the route syntax the app's own `path()` calls use and the regex
    syntax DRF's router emits. Format-suffix patterns return None: they are
    the same view as the one beside them under another spelling.
    """
    text = str(pattern.pattern)
    if "format" in text:
        return None
    text = re.sub(r"\(\?P<[^>]+>.*?\)\+?(?=/|$)", "1", text)
    text = re.sub(r"<int:[^>]+>", "1", text)
    text = re.sub(r"<[^>]+>", "x", text)
    return text.replace("^", "").replace("$", "").replace("\\.", ".")


def _walk(patterns, prefix=""):
    for entry in patterns:
        part = _route_text(entry)
        if part is None:
            continue
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + part)
        elif isinstance(entry, URLPattern):
            yield prefix + part


def improv_urls():
    import improv.urls

    return sorted({"/improv/" + route for route in _walk(improv.urls.urlpatterns)})


def test_the_walk_finds_the_routes_so_the_sweep_is_proving_something():
    """A sweep over an empty list passes forever. Pin that it sees the front door."""
    urls = improv_urls()
    assert "/improv/" in urls
    assert "/improv/api/chord-qualities/" in urls and "/improv/api/chord-qualities/1/" in urls
    assert all(u.startswith("/improv/") for u in urls)


# --------------------------------------------------------------- the group


def test_the_group_exists_the_moment_the_app_is_migrated(db):
    assert Group.objects.filter(name=GROUP).exists()


def test_nobody_is_in_the_group_at_launch(db):
    assert Group.objects.get(name=GROUP).user_set.count() == 0


# --------------------------------------------------------------- who may play


def test_who_may_play(people):
    from improv.access import is_player

    assert is_player(people["member"])
    assert is_player(people["admin"]), "the site admin was locked out of his own app"
    assert is_player(people["stranger"]), "a signed-in person with no group is admitted since 2026-10-08"


def test_an_anonymous_visitor_may_not_play(db):
    from django.contrib.auth.models import AnonymousUser

    from improv.access import is_player

    assert not is_player(AnonymousUser())
    assert not is_player(None)


def test_the_door_asks_the_registry_rather_than_repeating_it():
    """The same grep `test_spr_13_1` runs for ustrip and the house.

    Two functions that agree today are one edit from disagreeing, and the
    disagreement is a card that opens a 404 or a hidden app that still opens.
    """
    import pathlib

    src = pathlib.Path("improv/access.py").read_text(encoding="utf-8")
    body = re.search(r"def is_player\(.*?\n(?=\n\ndef |\n\n# |\Z)", src, re.S)
    assert body, "is_player not found"
    assert "portal" in body.group(0), "improv decides for itself who may play"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/improv", True),
        ("/improv/", True),
        ("/improv/play/", True),
        ("/improv/api/takes/3/", True),
        ("/improvement/", False),
        ("/improvs/", False),
        ("/improv-x/", False),
        ("/", False),
        ("/matazim/improv/", False),
    ],
)
def test_the_gate_covers_the_prefix_and_nothing_that_merely_looks_like_it(path, expected):
    from improv.access import is_improv_path

    assert is_improv_path(path) is expected


# ----------------------------------------------------------- the load-bearing one


def test_every_route_admits_a_signed_in_person_and_stops_a_visitor(people):
    urls = improv_urls()
    assert urls
    public = {"/improv/", "/improv/login/", "/improv/signup/", "/improv/logout/"}

    for url in urls:
        # A visitor: pages go to the front door, the API answers 401 or 403, GET and POST alike.
        # The four public pages are checked in test_spri_9_1; a POST there fails the CSRF check.
        if url not in public:
            for method in ("get", "post"):
                client = _client_for(None, enforce_csrf_checks=True)
                response = getattr(client, method)(url)
                if url.startswith("/improv/api/"):
                    assert response.status_code in (401, 403), f"visitor {method.upper()} {url} got {response.status_code}"
                else:
                    assert response.status_code == 302, f"visitor {method.upper()} {url} got {response.status_code}"
                    assert response.headers["Location"].startswith("/improv/?next="), response.headers["Location"]

        # Every kind of signed-in person is a full player, with or without the old group.
        for label, user in (("stranger", people["stranger"]), ("member", people["member"]), ("admin", people["admin"])):
            client = _client_for(user)
            response = client.get(url)
            admitted = response.status_code < 400 or response.status_code == 405
            if not admitted and response.status_code == 404 and url.endswith("/1/"):
                # Sessions and takes are one player's own: row 1 does not exist for the other
                # one, and that is right. The endpoint still has to admit them, so the list
                # beside the row must answer.
                admitted = client.get(url[: -len("1/")]).status_code < 400
            assert admitted, f"{label} GET {url} got {response.status_code}"


# -------------------------------------------------- the edges of the door


def test_a_visitor_on_the_bare_path_is_sent_to_the_front_door_not_hidden(people):
    response = _client_for(None).get("/improv")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/improv/")


def test_a_visitor_on_a_deep_page_is_sent_to_the_front_door(people):
    response = _client_for(None).get("/improv/play/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/?next=/improv/play/"


def test_a_player_on_the_bare_path_is_sent_to_the_app(people):
    response = _client_for(people["member"]).get("/improv")
    assert response.status_code in (301, 302)
    assert response.headers["Location"].endswith("/improv/")


def test_the_gate_sits_late_so_a_refusal_has_had_everything_a_real_404_gets():
    """Early, the gate answers before the first-touch capture, so a stranger's
    first visit to /improv sets no session and shows no welcome strip, which a
    visit to any other missing path does. Late, the two are the same request."""
    from django.conf import settings

    stack = settings.MIDDLEWARE
    gate = stack.index("improv.middleware.GateMiddleware")
    for before in (
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "app.middleware.OnboardingMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ):
        assert gate > stack.index(before), f"the gate is ahead of {before}"


def test_a_refusal_sets_the_same_cookies_as_a_url_that_does_not_exist(db):
    nothing = Client().get("/this-page-does-not-exist-zq/")
    refused = Client().get("/improv/")
    assert sorted(nothing.cookies) == sorted(refused.cookies)


def test_a_player_who_leaves_off_the_slash_is_sent_on_in_the_app(people):
    response = _client_for(people["member"]).get("/improv/play")
    assert response.status_code == 301
    assert response.headers["Location"] == "/improv/play/"


def test_a_post_without_a_token_is_refused_for_a_signed_in_person(people):
    """Being open does not mean being forgeable: a signed-in POST with no CSRF token is a 403."""
    client = _client_for(people["stranger"], enforce_csrf_checks=True)
    assert client.post("/improv/").status_code == 403
    assert client.post("/improv/api/player/").status_code == 403


def test_a_visitors_post_to_a_page_behind_the_door_is_redirected(db):
    client = Client(enforce_csrf_checks=True)
    response = client.post("/improv/play/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/improv/?next=")


# ------------------------------------------------------------------- the portal


def test_the_portal_shows_the_card_to_the_owner_alone_though_everyone_may_enter(people):
    from app.portal import may_enter, visible_apps

    for who, user in people.items():
        shown = "improv" in [a.slug for a in visible_apps(user)]
        assert shown == user.is_superuser, f"{who}: card shown={shown}"
        assert may_enter(user, "improv"), f"{who} may not enter"


def test_the_registry_entry_is_everyone_and_card_for_the_owner_only():
    from app.portal import APPS, EVERYONE

    entry = next(a for a in APPS if a.slug == "improv")
    assert entry.audience == EVERYONE
    assert entry.listed is True and entry.card_admin_only is True
    assert entry.path == "/improv/"


def test_the_portal_does_not_name_improv_to_anyone_but_the_owner(people):
    for who in ("stranger", "member"):
        html = _client_for(people[who]).get("/").content.decode("utf-8")
        assert 'href="/improv/"' not in html, who


# ------------------------------------------------------------------- the chrome


def test_a_player_gets_the_front_door(people):
    response = _client_for(people["member"]).get("/improv/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "<title>" in html and "improv" in re.search(r"<title>(.*?)</title>", html, re.S).group(1)


def test_the_app_is_english_and_left_to_right(people):
    html = _client_for(people["member"]).get("/improv/").content.decode("utf-8")
    root = re.search(r"<html[^>]*>", html).group(0)
    assert 'lang="en"' in root
    assert 'dir="ltr"' in root


def _hrefs(html):
    return re.findall(r'href="([^"]*)"', html)


def test_no_link_leaves_the_app(people):
    """Rule 3: nothing points back at babook unless Avi asks. Every link on the
    page is inside the app or is a stylesheet from our own static files."""
    html = _client_for(people["member"]).get("/improv/").content.decode("utf-8")
    hrefs = _hrefs(html)
    assert hrefs, "the page has no links at all, so this is proving nothing"
    for href in hrefs:
        assert href.startswith("/improv/") or href.startswith("/static/") or href.startswith("#"), (
            f"a link leaves the app: {href}"
        )


def test_the_app_has_its_own_menu(people):
    html = _client_for(people["member"]).get("/improv/").content.decode("utf-8")
    nav = re.search(r'<nav class="im-nav".*?</nav>', html, re.S)
    assert nav, "no <nav class=im-nav> found"
    assert 'href="/improv/"' in nav.group(0)


def test_no_template_extends_the_main_sites_base():
    import pathlib

    templates = list(pathlib.Path("templates/improv").glob("*.html"))
    assert templates
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"{%\s*extends\s+['\"](?!improv/)", text), (
            f"{path} extends something outside improv"
        )


def test_every_class_the_markup_uses_is_a_class_the_stylesheet_defines():
    """Methodology entry 13: an undefined class is silence, not an error."""
    import pathlib

    css = pathlib.Path("static/improv/improv.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(im-[a-z0-9_-]+)", css))
    used = set()
    for path in pathlib.Path("templates/improv").glob("*.html"):
        for value in re.findall(r'class="([^"]*)"', path.read_text(encoding="utf-8")):
            used.update(token for token in value.split() if token.startswith("im-"))
    assert used, "no im- classes found in the templates, so this is proving nothing"
    assert used <= defined, f"classes with no style: {sorted(used - defined)}"


def test_improv_has_a_home_in_the_docs_and_the_error_handler_is_not_improvs():
    """The gate relies on the site's own 404, so improv must not install a 404 page
    of its own: a branded one would tell a stranger what they had found."""
    import pathlib

    errors = pathlib.Path("mysite/errors.py").read_text(encoding="utf-8")
    assert "improv" not in errors
    assert not pathlib.Path("improv/errors.py").exists()
