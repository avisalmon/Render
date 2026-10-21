"""SPR-BK1.1: the skeleton and the seal (docs/books/backlog.md).

The refusals come first: who is turned away, where they are sent, what
they can never see or set. Then the happy paths."""

import json
import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from books.models import Profile

pytestmark = [pytest.mark.sprbk1_1, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture
def reader(db):
    return User.objects.create_user("noa", "noa@example.com", "pw-long-enough-1")


@pytest.fixture
def onboarded(reader):
    Profile.objects.create(user=reader, display_name="נועה", is_adult_confirmed=True)
    return reader


def onboard_post(client, **over):
    data = {"display_name": "נועה", "language": "he", "area_name": "כרמל, חיפה",
            "is_adult_confirmed": "on", "accept_terms": "on", **over}
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/books/welcome/", data)


# ---- refusals: pages ---------------------------------------------------------

def test_anonymous_is_sent_to_books_own_sign_in(client):
    # The home is a welcome page for a visitor (Avi, 2026-10-21); every other page sends them to sign in.
    r = client.get("/books/library/")
    assert r.status_code == 302 and r["Location"] == "/books/login/?next=/books/library/"


def test_signed_in_without_a_profile_is_sent_to_onboarding(client, reader):
    client.force_login(reader)
    r = client.get("/books/")
    assert r.status_code == 302 and r["Location"].startswith("/books/welcome/")


@pytest.mark.parametrize("missing", ["is_adult_confirmed", "accept_terms"])
def test_onboarding_refuses_without_age_or_terms(client, reader, missing):
    client.force_login(reader)
    r = onboard_post(client, **{missing: None})
    assert r.status_code == 200
    assert not Profile.objects.filter(user=reader).exists()


def test_onboarding_needs_a_name(client, reader):
    client.force_login(reader)
    onboard_post(client, display_name="")
    assert not Profile.objects.filter(user=reader).exists()


def test_next_cannot_send_a_person_out_of_books(client, reader):
    client.force_login(reader)
    r = onboard_post(client, next="https://evil.example/")
    # Onboarding now ends at the taste survey (BK9), carrying a safe next.
    assert r["Location"] == "/books/taste/?first=1&next=%2Fbooks%2F"
    r = client.post("/books/taste/", {"first": "1", "skip": "1", "next": "https://evil.example/"})
    assert r["Location"] == "/books/discover/"
    client.logout()
    r = client.post("/books/login/", {"username": "noa@example.com", "password": "pw-long-enough-1", "next": "/admin/"})
    assert r["Location"] == "/books/"


# ---- refusals: the API -------------------------------------------------------

def test_anonymous_gets_nothing_from_the_api(client):
    assert client.get("/books/api/profiles/").status_code in (401, 403)


def test_signed_in_without_profile_gets_nothing_from_the_api(client, reader):
    client.force_login(reader)
    assert client.get("/books/api/profiles/").status_code == 403


def test_the_list_holds_only_my_profile(client, onboarded):
    other = User.objects.create_user("dan", "dan@example.com", "pw")
    Profile.objects.create(user=other, display_name="דן")
    client.force_login(onboarded)
    data = client.get("/books/api/profiles/").json()
    rows = data["results"] if isinstance(data, dict) else data
    assert [r["display_name"] for r in rows] == ["נועה"]


def test_another_persons_profile_is_404_for_every_verb(client, onboarded):
    other = User.objects.create_user("dan", "dan@example.com", "pw")
    theirs = Profile.objects.create(user=other, display_name="דן")
    client.force_login(onboarded)
    url = f"/books/api/profiles/{theirs.pk}/"
    assert client.get(url).status_code == 404
    assert client.patch(url, {"display_name": "x"}, content_type="application/json").status_code == 404
    assert client.delete(url).status_code == 404
    theirs.refresh_from_db()
    assert theirs.display_name == "דן"


def test_nobody_sets_their_own_tier_age_or_terms_through_the_api(client, onboarded):
    me = onboarded.books_profile
    client.force_login(onboarded)
    client.patch(f"/books/api/profiles/{me.pk}/", {"tier": "pro", "is_adult_confirmed": False,
                                                   "accepted_terms_at": None}, content_type="application/json")
    me.refresh_from_db()
    assert me.tier == "free" and me.is_adult_confirmed is True


def test_the_api_cannot_create_a_profile(client, onboarded):
    client.force_login(onboarded)
    r = client.post("/books/api/profiles/", {"display_name": "x"}, content_type="application/json")
    assert r.status_code == 405


# ---- location is never precise -----------------------------------------------

def test_a_precise_point_is_rounded_on_save(reader):
    p = Profile.objects.create(user=reader, display_name="נ", area_lat=32.794567, area_lng=34.989123)
    p.refresh_from_db()
    assert (p.area_lat, p.area_lng) == (Decimal("32.79"), Decimal("34.99"))


def test_a_precise_point_sent_to_the_api_is_stored_rounded(client, onboarded):
    me = onboarded.books_profile
    client.force_login(onboarded)
    r = client.patch(f"/books/api/profiles/{me.pk}/", {"area_lat": "32.7945671", "area_lng": "34.9891234"},
                     content_type="application/json")
    assert r.status_code == 200
    me.refresh_from_db()
    assert (me.area_lat, me.area_lng) == (Decimal("32.79"), Decimal("34.99"))


# ---- happy paths -------------------------------------------------------------

def test_signup_logs_in_and_leads_to_onboarding(client, db):
    r = client.post("/books/signup/", {"email": "New@Example.com", "password1": "a-long-pass-123",
                                        "password2": "a-long-pass-123"})
    assert r.status_code == 302 and r["Location"] == "/books/welcome/"
    user = User.objects.get(email="new@example.com")
    assert client.session["_auth_user_id"] == str(user.pk)


def test_sign_in_with_the_email(client, reader):
    r = client.post("/books/login/", {"username": "noa@example.com", "password": "pw-long-enough-1"})
    assert r.status_code == 302 and r["Location"] == "/books/"


def test_onboarding_creates_the_profile_and_returns_to_the_library(client, reader):
    client.force_login(reader)
    r = onboard_post(client)
    assert r["Location"] == "/books/taste/?first=1&next=%2Fbooks%2F"  # the survey, then the library
    assert client.post("/books/taste/", {"first": "1", "skip": "1", "next": "/books/"})["Location"] == "/books/"
    p = Profile.objects.get(user=reader)
    assert p.is_adult_confirmed and p.accepted_terms_at is not None and p.area_name == "כרמל, חיפה"
    assert p.tier == "free"


def test_onboarding_twice_does_not_make_a_second_profile(client, onboarded):
    client.force_login(onboarded)
    r = client.get("/books/welcome/")
    assert r.status_code == 302
    assert Profile.objects.filter(user=onboarded).count() == 1


def test_the_empty_library_shows_the_empty_shelf(client, onboarded):
    client.force_login(onboarded)
    html = client.get("/books/").content.decode()
    shelf = re.search(r'<div class="bk-shelf".*?</div>\s*</div>', html, re.S).group(0)
    assert "המדף עוד ריק" in shelf
    assert 'data-screen="home"' in html


def test_deleting_my_profile_keeps_my_account(client, onboarded):
    me = onboarded.books_profile
    client.force_login(onboarded)
    assert client.delete(f"/books/api/profiles/{me.pk}/").status_code == 204
    assert User.objects.filter(pk=onboarded.pk).exists()
    assert not Profile.objects.filter(pk=me.pk).exists()


# ---- the seal ----------------------------------------------------------------

@pytest.mark.parametrize("path", ["/books/login/", "/books/signup/", "/books/terms/", "/books/privacy/",
                                  "/books/password/reset/", "/books/nope/"])
def test_books_pages_carry_no_babook_chrome_and_no_link_out(client, path):
    html = client.get(path).content.decode()
    assert "babook" not in html.lower()
    for href in re.findall(r'href="([^"]+)"', html):
        assert href.startswith(("/books/", "/static/", "/accounts/google/", "https://fonts.", "#")), href


def test_the_library_page_is_sealed_too(client, onboarded):
    client.force_login(onboarded)
    html = client.get("/books/").content.decode()
    # One door out, asked for by Avi (2026-10-21): the menu's "more on the site", to babook's main page.
    door = 'class="bk-nav-item bk-nav-item--site" href="/babook/"'
    assert html.count(door) == 2
    html = html.replace(door, "")
    assert "babook" not in html.lower()
    for href in re.findall(r'href="([^"]+)"', html):
        assert href.startswith(("/books/", "/static/", "https://fonts.", "#")), href


def test_babook_does_not_link_to_books(client, db):
    html = client.get("/babook/").content.decode()
    assert 'href="/books' not in html


def test_a_404_inside_books_is_books_own(client):
    r = client.get("/books/nope/")
    assert r.status_code == 404 and "הדף הזה לא על המדף" in r.content.decode()
