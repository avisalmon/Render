"""SPR-I.1.1 improv: the app, its chrome, its gate and its portal card.

Avi, 2026-10-04: the app is available only to him until it is stable, linked
from babook for him alone, and "no other to see the link and the app".

**The load-bearing test is `test_every_route_refuses_outsiders_and_admits_a_player`.**
It walks every route the app registers, and knocks on each as an anonymous
visitor, a signed-in non-member and a member, GET and POST. It is written before
there is anything behind the gate worth hiding, so the next route somebody adds
is covered the day it appears rather than the day somebody remembers.

**Second is `test_a_refusal_is_the_same_page_as_a_url_that_does_not_exist`.** A 404
that looks different from the site's own 404 is an announcement that something is
here. The gate hides the app only if it is indistinguishable from nothing.

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
    assert not is_player(people["stranger"])


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


def test_every_route_refuses_outsiders_and_admits_a_player(people):
    urls = improv_urls()
    assert urls

    for url in urls:
        for label, user in (("anonymous", None), ("stranger", people["stranger"])):
            for method in ("get", "post"):
                client = _client_for(user, enforce_csrf_checks=True)
                response = getattr(client, method)(url)
                assert response.status_code == 404, (
                    f"{label} {method.upper()} {url} got {response.status_code}, not 404"
                )

        for label, user in (("member", people["member"]), ("admin", people["admin"])):
            client = _client_for(user)
            response = client.get(url)
            admitted = response.status_code < 400 or response.status_code == 405
            if not admitted and response.status_code == 404 and url.endswith("/1/"):
                # Sessions and takes are one player's own: row 1 does not exist for the other
                # one, and that is right. The endpoint still has to admit them, so the list
                # beside the row must answer.
                admitted = client.get(url[: -len("1/")]).status_code < 400
            assert admitted, f"{label} GET {url} got {response.status_code}"


# -------------------------------------------------- hiding it, not just refusing


def _normalised(response):
    """The page without the parts that legitimately differ between two requests."""
    html = response.content.decode("utf-8")
    html = re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)
    html = re.sub(r"[A-Za-z0-9]{64}", "TOKEN", html)
    return html


@pytest.mark.parametrize("who", ["anonymous", "stranger"])
def test_a_refusal_is_the_same_page_as_a_url_that_does_not_exist(people, who):
    user = None if who == "anonymous" else people["stranger"]
    # A fresh client per request: the site shows a first-visit script once per
    # session, which would make the first page differ from the rest for a reason
    # that has nothing to do with the gate.
    nothing = _client_for(user).get("/this-page-does-not-exist-zq/")
    refused = _client_for(user).get("/improv/")
    refused_deep = _client_for(user).get("/improv/api/")

    assert nothing.status_code == refused.status_code == refused_deep.status_code == 404
    assert _normalised(refused) == _normalised(nothing)
    assert _normalised(refused_deep) == _normalised(nothing)


@pytest.mark.parametrize("who", ["anonymous", "stranger"])
def test_the_bare_path_does_not_give_the_app_away(people, who):
    """Django's APPEND_SLASH answers /improv with a redirect to /improv/ when that
    exists, and a redirect is an announcement that it does. It must be a 404."""
    user = None if who == "anonymous" else people["stranger"]
    response = _client_for(user).get("/improv")
    assert response.status_code == 404, f"/improv answered {response.status_code}"
    assert not response.headers.get("Location")


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


def test_a_post_without_a_token_is_a_404_not_a_403(db):
    """A 403 from the CSRF check would say something is here."""
    anonymous = Client(enforce_csrf_checks=True)
    assert anonymous.post("/improv/").status_code == 404


# ------------------------------------------------------------------- the portal


def test_the_portal_shows_the_card_to_a_player_and_an_admin_and_to_nobody_else(people):
    from app.portal import visible_apps

    def slugs(user):
        return [a.slug for a in visible_apps(user)]

    assert "improv" in slugs(people["member"])
    assert "improv" in slugs(people["admin"])
    assert "improv" not in slugs(people["stranger"])


def test_the_card_never_exceeds_the_door(people):
    from app.portal import may_enter, visible_apps

    for user in people.values():
        shown = "improv" in [a.slug for a in visible_apps(user)]
        assert shown == may_enter(user, "improv")


def test_the_registry_entry_is_a_group_with_the_admin_bypass():
    from app.portal import APPS

    entry = next(a for a in APPS if a.slug == "improv")
    assert entry.audience == "group"
    assert entry.key == GROUP
    assert entry.admin_bypass is True
    assert entry.path == "/improv/"


def test_the_portal_does_not_name_improv_to_a_stranger(people):
    client = _client_for(people["stranger"])
    html = client.get("/").content.decode("utf-8")
    assert 'href="/improv/"' not in html


def test_the_portal_links_a_player_to_improv(people):
    client = _client_for(people["member"])
    html = client.get("/").content.decode("utf-8")
    assert 'href="/improv/"' in html


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
