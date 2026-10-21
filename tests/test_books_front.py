"""Avi, 2026-10-21: the front door and the header.

A visitor gets a welcome page that says what Books is, with one big way in;
sign in leads with Google and folds the password away; the streak lives in
the header as a flame that is dim until today's reading counts, with every
minute read since joining; and one book can be photographed on its own."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from books import catalog, reading, shelf, storage
from books.models import CatalogEntry, Profile, ReadingSession, ShelfScan
from books.recognition import Reading
from tests.test_books_3 import upload

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


@pytest.fixture
def noa(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    return Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)


@pytest.fixture
def book(db):
    return CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")


def read_today(profile, entry, minutes):
    s = reading.start(profile, entry, 1)
    begun = timezone.now() - timedelta(minutes=minutes)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=begun)
    s.refresh_from_db()
    return reading.end(profile, s, 20, now=begun + timedelta(minutes=minutes))


# ---- the welcome page ----------------------------------------------------------------

def test_a_visitor_gets_the_welcome_page_with_one_big_way_in(client):
    r = client.get("/books/")
    html = r.content.decode()
    assert r.status_code == 200 and 'data-screen="landing"' in html
    assert html.count('class="bk-btn bk-btn--primary bk-hero-cta" href="/books/login/?next=/books/"') == 2
    assert "חוזרים לקרוא." in html
    # The demo shelf is drawn from made-up rows, never anyone's real books.
    assert 'id="demo-data"' in html and "/books/copy/" not in html


def test_other_pages_still_send_a_visitor_to_sign_in(client):
    r = client.get("/books/library/")
    assert r.status_code == 302 and r["Location"].startswith("/books/login/")


# ---- sign in: Google first ------------------------------------------------------------

def test_sign_in_leads_with_google_and_folds_the_password(client):
    html = client.get("/books/login/").content.decode()
    google = html.index('class="bk-btn bk-btn--primary bk-btn--wide bk-google"')
    other = html.index('<details class="bk-more bk-login-other" >')
    assert google < other < html.index('name="password"')


def test_a_wrong_password_opens_the_other_way_with_its_error(client, noa):
    html = client.post("/books/login/", {"username": "noa", "password": "nope"}).content.decode()
    assert '<details class="bk-more bk-login-other" open>' in html and 'role="alert"' in html


# ---- the flame -------------------------------------------------------------------------

def test_the_flame_is_dim_until_today_counts(client, noa, book):
    client.force_login(noa.user)
    html = client.get("/books/catalog/").content.decode()
    assert 'class="bk-flame" href="/books/play/"' in html and "(0 דק׳)" in html
    read_today(noa, book, 3)
    html = client.get("/books/catalog/").content.decode()
    assert 'class="bk-flame" href="/books/play/"' in html and "(3 דק׳)" in html


def test_the_flame_lights_after_five_minutes_and_counts_every_minute(client, noa, book):
    s = reading.start(noa, book, 1)
    old = timezone.now() - timedelta(days=30)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=old)
    s.refresh_from_db()
    reading.end(noa, s, 10, now=old + timedelta(minutes=40))
    read_today(noa, book, 6)
    client.force_login(noa.user)
    html = client.get("/books/catalog/").content.decode()
    assert 'class="bk-flame is-lit"' in html and "<b>1</b>" in html and "(46 דק׳)" in html


def test_the_flame_has_its_colours_in_every_palette():
    css = open("static/books/books.css", encoding="utf-8").read()
    assert css.count("--bk-flame:") == 5 and css.count("--bk-flame-core:") == 5


# ---- one book on its own -----------------------------------------------------------------

def test_home_offers_a_shelf_and_a_single_book(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert 'href="/books/scan/?book=1"' in html and 'href="/books/scan/"' in html


@pytest.mark.parametrize("single, strips", [(True, 1), (False, None)])
def test_a_single_book_is_read_whole_and_a_shelf_in_strips(client, noa, monkeypatch, single, strips):
    seen = {}

    def fake(data, strips=None, **kw):
        seen["strips"] = strips
        return Reading(model="gpt-6.1-sol", books=[], calls=[])

    monkeypatch.setattr(shelf, "read_shelf", fake)
    client.force_login(noa.user)
    data = {"photo": upload(), "default_visibility": "private"}
    if single:
        data["single"] = "1"
    r = client.post("/books/scan/", data)
    scan = ShelfScan.objects.get()
    assert scan.is_single is single and seen["strips"] == strips
    assert ("book=1" in r["Location"]) is single


def test_the_single_book_page_speaks_of_a_book(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/scan/?book=1").content.decode()
    assert '<input type="hidden" name="single" value="1">' in html and "צילום ספר" in html
    assert 'href="/books/scan/">' in html  # the way back to a whole shelf


def test_the_api_takes_a_single_book(client, noa, monkeypatch):
    monkeypatch.setattr(shelf, "read_shelf", lambda data, **kw: Reading(model="gpt-6.1-sol", books=[], calls=[]))
    client.force_login(noa.user)
    r = client.post("/books/api/scans/upload/", {"photo": upload(), "single": "1"})
    assert r.status_code == 201 and r.json()["is_single"] is True
