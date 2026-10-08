"""SPR-I.9.1 and SPR-I.9.2 improv: open to anyone who signs in, with a front door for visitors.

Avi, 2026-10-08: "enable login in the main page of this app and get everything free to anyone
entering. I want users to try and feedback." And: a person given https://babook.co.il/improv/ is
not sent to babook; they are invited to log in or sign up, and a person already logged in goes
straight into the app.

What stays true from the private days: every improv page and API is behind a sign-in, a person
sees only their own sittings, takes and runs, and the shared catalogue (presets, lessons, theory)
cannot be written by an ordinary person.

Traces: spec ch. 7, backlog SPR-I.9.1 and SPR-I.9.2.
"""

import io
import re

import pytest
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client
from django.urls import URLPattern, URLResolver

pytestmark = [pytest.mark.spri9, pytest.mark.django_db]

PASSWORD = "spri9-pass-7731-x"


def _user(name, **flags):
    user = User.objects.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    return user


def _client(user=None, **kwargs):
    client = Client(**kwargs)
    if user is not None:
        client.force_login(user)
    return client


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def seeded(db):
    for command in ("seed_improv_theory", "seed_improv_fingerings", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(command, stdout=io.StringIO())


# ------------------------------------------------------ walking the routes


def _route_text(pattern):
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


# --------------------------------------------------------- who may play


def test_anyone_signed_in_may_play(db):
    from improv.access import is_player

    assert is_player(_user("anyone"))
    assert is_player(_user("boss", is_staff=True, is_superuser=True))


def test_nobody_signed_out_may_play(db):
    from django.contrib.auth.models import AnonymousUser

    from improv.access import is_player

    assert not is_player(AnonymousUser())
    assert not is_player(None)


def test_the_door_still_asks_the_registry():
    import pathlib

    src = pathlib.Path("improv/access.py").read_text(encoding="utf-8")
    body = re.search(r"def is_player\(.*?\n(?=\n\ndef |\n\n# |\Z)", src, re.S)
    assert body and "portal" in body.group(0), "improv decides for itself who may play"


def test_the_registry_says_everyone_and_shows_the_card_to_the_owner_only():
    from app.portal import APPS, EVERYONE

    entry = next(a for a in APPS if a.slug == "improv")
    assert entry.audience == EVERYONE
    assert entry.path == "/improv/"
    assert entry.listed is True and entry.card_admin_only is True, "improv is shared by link; the card is the owner's alone"


def test_the_card_never_exceeds_the_door(db):
    from app.portal import may_enter, visible_apps

    for user in (_user("a"), _user("b", is_superuser=True, is_staff=True)):
        shown = "improv" in [a.slug for a in visible_apps(user)]
        assert shown <= may_enter(user, "improv")


# --------------------------------------------------- a signed-in stranger is in


def test_every_route_admits_a_signed_in_person_and_stops_a_visitor(seeded):
    urls = improv_urls()
    assert "/improv/" in urls and "/improv/login/" in urls and "/improv/signup/" in urls
    person = _user("walker")
    public = {"/improv/", "/improv/login/", "/improv/signup/"}
    for url in urls:
        client = _client(person)
        response = client.get(url)
        admitted = response.status_code < 400 or response.status_code == 405
        if not admitted and response.status_code == 404 and url.endswith("/1/"):
            admitted = client.get(url[: -len("1/")]).status_code < 400
        assert admitted, f"a signed-in person got {response.status_code} on GET {url}"

        visitor = Client(enforce_csrf_checks=True)
        got = visitor.get(url)
        if url == "/improv/logout/":
            assert got.status_code == 405, "logging out is a POST, for anyone"
        elif url in public:
            assert got.status_code == 200, f"{url} should be open to a visitor, got {got.status_code}"
        elif url.startswith("/improv/api/"):
            assert got.status_code in (401, 403), f"visitor GET {url} got {got.status_code}"
            assert visitor.post(url).status_code in (401, 403), f"visitor POST {url}"
        else:
            assert got.status_code == 302, f"visitor GET {url} got {got.status_code}"
            assert got.headers["Location"].startswith("/improv/?next="), got.headers["Location"]


def test_the_first_visit_makes_the_players_profile(db):
    from improv.models import Player

    person = _user("fresh")
    assert not Player.objects.filter(user=person).exists()
    assert _client(person).get("/improv/").status_code == 200
    assert Player.objects.filter(user=person).exists()


def test_a_signed_in_person_on_the_bare_path_is_sent_on(db):
    response = _client(_user("bare")).get("/improv")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/improv/")


def test_a_visitor_on_the_bare_path_lands_on_the_front_door(db):
    response = Client().get("/improv")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/improv/")


def test_a_signed_in_person_gets_today_not_the_front_door(db):
    html = _client(_user("today")).get("/improv/").content.decode("utf-8")
    assert 'id="continue-line"' in html
    assert 'action="/improv/login/"' not in html


def test_the_gate_still_covers_only_its_own_prefix():
    from improv.access import is_improv_path

    assert is_improv_path("/improv/") and is_improv_path("/improv") and is_improv_path("/improv/api/takes/")
    assert not is_improv_path("/improvement/") and not is_improv_path("/")


# ------------------------------------------------ a person's own data stays theirs


def test_one_person_never_reads_another_persons_takes(seeded):
    from django.utils import timezone

    from improv.models import Player, PracticeSession, Progression, Take

    a, b = _user("owner-a"), _user("owner-b")
    chart = Progression.objects.first()
    pa = Player.objects.create(user=a)
    session = PracticeSession.objects.create(player=pa, active_seconds=30)
    Take.objects.create(
        player=pa, session=session, progression=chart, chart=chart.chart, home_key=chart.home_key, key=0, tempo=80,
        loop_from=0, loop_to=4, started_at=timezone.now(), duration_ms=1000, bars=4, events=[], score=50, metrics={}, judge_version=1,
    )

    def rows(body):
        return body["results"] if isinstance(body, dict) and "results" in body else body

    assert len(rows(_client(a).get("/improv/api/takes/").json())) == 1
    assert rows(_client(b).get("/improv/api/takes/").json()) == []


def test_an_ordinary_person_cannot_change_the_shared_catalogue(seeded):
    from improv.models import Phrase, Progression, Style

    client = _client(_user("tinkerer"))
    for route, model in (("progressions", Progression), ("styles", Style), ("phrases", Phrase)):
        preset = model.objects.filter(is_preset=True).first()
        if preset is None:
            continue
        url = f"/improv/api/{route}/{preset.pk}/"
        assert client.patch(url, data="{}", content_type="application/json").status_code in (403, 404), route
        assert client.delete(url).status_code in (403, 404), route
        assert model.objects.filter(pk=preset.pk).exists()


@pytest.mark.parametrize("route", ["chord-qualities", "scales", "scale-fingerings", "chord-scales", "tags", "lessons", "exercises"])
def test_the_reference_and_teaching_tables_are_read_only_for_everyone(seeded, route):
    client = _client(_user("reader"))
    assert client.get(f"/improv/api/{route}/").status_code == 200
    assert client.post(f"/improv/api/{route}/", data="{}", content_type="application/json").status_code == 405


# ----------------------------------------------------------- the front door


def test_the_front_door_invites_a_visitor_to_log_in_or_sign_up(db):
    response = Client().get("/improv/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'action="/improv/login/"' in html
    assert 'name="email"' in html and 'name="password"' in html
    assert 'href="/improv/signup/' in html
    assert "/accounts/google/login/?process=login&amp;next=/improv/" in html or "/accounts/google/login/?process=login&next=/improv/" in html
    assert 'name="csrfmiddlewaretoken"' in html


def test_the_front_door_is_improv_not_babook(db):
    html = Client().get("/improv/").content.decode("utf-8")
    assert re.search(r"<title>[^<]*improv", html)
    assert 'lang="en"' in html and 'dir="ltr"' in html
    assert "babook" not in html.lower()
    for link in re.findall(r'href="([^"]*)"', html):
        assert link.startswith(("/improv/", "/static/", "/accounts/google/login/", "/accounts/password/reset/", "#")), link


def test_the_front_door_shows_no_app_menu_to_a_visitor(db):
    html = Client().get("/improv/").content.decode("utf-8")
    for name in ("Lessons", "Challenges", "Library", "Timing spike"):
        assert f">{name}<" not in html
    assert "control-page.js" not in html


def test_the_front_door_says_it_is_free(db):
    assert "free" in Client().get("/improv/").content.decode("utf-8").lower()


def test_the_front_door_carries_a_safe_next_to_the_login_form(db):
    html = Client().get("/improv/?next=/improv/lessons/").content.decode("utf-8")
    assert 'name="next" value="/improv/lessons/"' in html
    outside = Client().get("/improv/?next=https://evil.example/x").content.decode("utf-8")
    assert "evil.example" not in outside
    other_app = Client().get("/improv/?next=/matazim/").content.decode("utf-8")
    assert 'value="/matazim/"' not in other_app


def test_a_visitor_on_a_deep_page_is_asked_to_sign_in_and_brought_back(db):
    response = Client().get("/improv/lessons/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/?next=/improv/lessons/"


# --------------------------------------------------------------------- log in


def test_logging_in_with_an_email_and_password_goes_to_today(db):
    user = _user("emailer")
    client = Client()
    response = client.post("/improv/login/", {"email": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"
    assert client.get("/improv/").content.decode("utf-8").count('id="continue-line"') == 1


def test_the_email_is_not_case_sensitive(db):
    user = _user("casey")
    response = Client().post("/improv/login/", {"email": user.email.upper(), "password": PASSWORD})
    assert response.status_code == 302


def test_a_username_works_too_for_people_who_already_have_one(db):
    _user("oldtimer")
    response = Client().post("/improv/login/", {"email": "oldtimer", "password": PASSWORD})
    assert response.status_code == 302


def test_logging_in_brings_the_person_back_to_where_they_were_going(db):
    user = _user("returner")
    response = Client().post("/improv/login/", {"email": user.email, "password": PASSWORD, "next": "/improv/lessons/"})
    assert response.headers["Location"] == "/improv/lessons/"


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/", "/matazim/", "/admin/", "javascript:alert(1)"])
def test_logging_in_never_leaves_improv(db, target):
    user = _user("careful")
    response = Client().post("/improv/login/", {"email": user.email, "password": PASSWORD, "next": target})
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"


def test_a_wrong_password_says_so_and_stays_signed_out(db):
    user = _user("wrong")
    client = Client()
    response = client.post("/improv/login/", {"email": user.email, "password": "nope-nope"})
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "did not match" in html
    assert 'id="login-error"' in html
    assert client.get("/improv/api/player/").status_code in (401, 403)


def test_an_unknown_email_gets_the_same_answer_as_a_wrong_password(db):
    user = _user("known")
    wrong = Client().post("/improv/login/", {"email": user.email, "password": "nope-nope"}).content.decode("utf-8")
    unknown = Client().post("/improv/login/", {"email": "nobody@example.com", "password": "nope-nope"}).content.decode("utf-8")

    def pick(html):
        return re.search(r'id="login-error"[^>]*>(.*?)<', html, re.S).group(1).strip()

    assert pick(wrong) == pick(unknown)


def test_an_empty_login_asks_for_both(db):
    response = Client().post("/improv/login/", {"email": "", "password": ""})
    assert response.status_code == 200
    assert 'id="login-error"' in response.content.decode("utf-8")


def test_the_login_address_shows_the_front_door_on_a_get(db):
    response = Client().get("/improv/login/")
    assert response.status_code == 200
    assert 'action="/improv/login/"' in response.content.decode("utf-8")


def test_a_signed_in_person_who_opens_the_login_address_goes_to_today(db):
    response = _client(_user("loggedin")).get("/improv/login/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"


def test_too_many_wrong_passwords_slow_a_guesser_down(db):
    user = _user("targeted")
    client = Client()
    last = None
    for _ in range(12):
        last = client.post("/improv/login/", {"email": user.email, "password": "guess-guess"})
    assert last.status_code == 200
    assert "Too many" in last.content.decode("utf-8")
    right = client.post("/improv/login/", {"email": user.email, "password": PASSWORD})
    assert right.status_code == 200, "even the right password waits while the lock holds"


# -------------------------------------------------------------------- sign up


def test_the_sign_up_page_asks_for_an_email_and_a_password(db):
    response = Client().get("/improv/signup/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'action="/improv/signup/"' in html
    assert 'name="email"' in html and 'name="password"' in html
    assert 'href="/improv/"' in html


def test_signing_up_makes_the_account_signs_in_and_goes_to_today(db):
    from improv.models import Player

    client = Client()
    response = client.post("/improv/signup/", {"email": "New.Person@Example.com", "password": PASSWORD, "name": "Dana"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"
    user = User.objects.get(email="new.person@example.com")
    assert user.first_name == "Dana"
    assert not user.is_staff and not user.is_superuser
    assert client.get("/improv/").status_code == 200
    assert Player.objects.filter(user=user).exists()


def test_the_name_is_optional(db):
    response = Client().post("/improv/signup/", {"email": "noname@example.com", "password": PASSWORD})
    assert response.status_code == 302
    assert User.objects.filter(email="noname@example.com").exists()


def test_a_taken_email_is_said_plainly(db):
    _user("taken")
    response = Client().post("/improv/signup/", {"email": "TAKEN@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert "already" in response.content.decode("utf-8")
    assert User.objects.filter(email__iexact="taken@example.com").count() == 1


@pytest.mark.parametrize("email", ["", "not-an-email", "a@b", "x" * 300 + "@example.com"])
def test_a_bad_email_is_refused(db, email):
    before = User.objects.count()
    response = Client().post("/improv/signup/", {"email": email, "password": PASSWORD})
    assert response.status_code == 200
    assert User.objects.count() == before


@pytest.mark.parametrize("password", ["", "short", "12345678", "password"])
def test_a_weak_password_is_refused_with_the_reason(db, password):
    before = User.objects.count()
    response = Client().post("/improv/signup/", {"email": "weak@example.com", "password": password})
    assert response.status_code == 200
    assert 'id="signup-error"' in response.content.decode("utf-8")
    assert User.objects.count() == before


def test_a_refused_sign_up_keeps_what_was_typed_but_never_the_password(db):
    html = Client().post("/improv/signup/", {"email": "keep@example.com", "name": "Kit", "password": "shortpw"}).content.decode("utf-8")
    assert 'value="keep@example.com"' in html and 'value="Kit"' in html
    assert 'value="shortpw"' not in html


def test_the_username_is_made_for_them_and_never_clashes(db):
    _user("pat")
    Client().post("/improv/signup/", {"email": "pat@elsewhere.com", "password": PASSWORD})
    Client().post("/improv/signup/", {"email": "pat@third.com", "password": PASSWORD})
    names = list(User.objects.filter(email__in=["pat@elsewhere.com", "pat@third.com"]).values_list("username", flat=True))
    assert len(set(names)) == 2 and "pat" not in names


def test_a_burst_of_sign_ups_from_one_address_is_stopped(db):
    codes = [Client().post("/improv/signup/", {"email": f"burst{i}@example.com", "password": PASSWORD}).status_code for i in range(14)]
    assert codes[:10] == [302] * 10, "a room of people trying it together must get in"
    assert 200 in codes[10:], codes
    assert User.objects.filter(email__startswith="burst").count() < 14


def test_a_new_account_is_not_in_the_old_group_and_needs_not_to_be(db):
    Client().post("/improv/signup/", {"email": "grp@example.com", "password": PASSWORD})
    user = User.objects.get(email="grp@example.com")
    assert not Group.objects.filter(name="improv_players", user=user).exists()


def test_signing_up_while_signed_in_just_goes_to_today(db):
    response = _client(_user("already")).get("/improv/signup/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"


# -------------------------------------------------------------------- log out


def test_logging_out_is_a_post_and_goes_to_the_front_door(db):
    client = _client(_user("leaver"))
    assert client.get("/improv/logout/").status_code in (302, 405)
    assert client.get("/improv/api/player/").status_code == 200, "a GET must not log anyone out"
    response = client.post("/improv/logout/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/improv/"
    assert client.get("/improv/api/player/").status_code in (401, 403)


def test_the_menu_of_a_signed_in_person_has_log_out_and_who_they_are(db):
    html = _client(_user("shown")).get("/improv/").content.decode("utf-8")
    assert 'action="/improv/logout/"' in html
    assert "shown@example.com" in html


def test_the_timing_spike_is_in_the_menu_only_for_staff(db):
    plain = _client(_user("plain")).get("/improv/").content.decode("utf-8")
    staff = _client(_user("staffer", is_staff=True)).get("/improv/").content.decode("utf-8")
    assert "Timing spike" not in plain
    assert "Timing spike" in staff
