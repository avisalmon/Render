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


# ---- continue the book I stopped in -----------------------------------------------------

def test_home_says_continue_with_the_book_and_one_tap_starts_at_my_page(client, noa, book):
    client.force_login(noa.user)
    assert "מתחילים לקרוא" in client.get("/books/").content.decode()
    read_today(noa, book, 10)  # pages 1 to 20, not finished
    html = client.get("/books/").content.decode()
    assert "<b>המשך לקרוא</b><i>מיכאל שלי</i>" in html and 'name="page" value="20"' in html
    client.post("/books/read/start/", {"first_done": "1", "entry": book.pk, "page": "20"})
    assert ReadingSession.objects.get(ended_at__isnull=True).start_page == 20


def test_a_finished_book_is_not_offered_to_continue(client, noa, book):
    s = reading.start(noa, book, 1)
    reading.end(noa, s, 300, finished=True)
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert "המשך לקרוא" not in html and "מתחילים לקרוא" in html


def test_the_timer_page_has_the_page_wheel(client, noa, book):
    reading.start(noa, book, 30)
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    assert 'data-flip data-min="30"' in html and "books/flip.js" in html
    assert 'name="end_page" min="30"' in html and "data-flip-input" in html


def test_the_dial_and_its_pebbles_carry_no_icons(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    zone = html[html.index('<section class="bk-dial-zone"'):html.index("</section>", html.index("bk-dial-zone"))]
    assert "<svg" not in zone
    assert '<a class="bk-pebble" href="/books/scan/">' in zone and '<a class="bk-pebble" href="/books/scan/?book=1">' in zone


def test_a_reader_gives_the_page_count_once_and_never_overwrites_one(noa, book):
    from books.models import BookDetail
    assert reading.set_pages(book, "abc") is None and reading.set_pages(book, 3) is None
    assert reading.set_pages(book, 80, at_least=120) is None  # fewer pages than the page I am on
    assert reading.set_pages(book, 412) == 412 and BookDetail.objects.get(entry=book).pages == 412
    assert reading.set_pages(book, 999) == 412  # a count already there stays


def test_starting_a_book_asks_its_length_and_saves_it(client, noa, book):
    """Avi, 2026-10-21: ask how many pages when starting a book, every time, filled in when known."""
    from books.models import BookDetail
    client.force_login(noa.user)
    html = client.get(f"/books/read/?entry={book.pk}").content.decode()
    assert 'name="total_pages"' in html and "נניח 200" in html
    client.post("/books/read/start/", {"first_done": "1", "entry": book.pk, "page": "10", "total_pages": "300"})
    assert BookDetail.objects.get(entry=book).pages == 300
    s = ReadingSession.objects.get(ended_at__isnull=True)
    assert 'name="total_pages"' not in client.get("/books/read/").content.decode()  # the timer never asks
    reading.end(noa, s, 30)
    assert 'name="total_pages" min="10" max="5000" inputmode="numeric" value="300"' in client.get(f"/books/read/?entry={book.pk}").content.decode()  # always asked, filled in


def test_with_no_answer_200_is_assumed_for_progress_only(client, noa, book):
    from books.models import BookDetail
    client.force_login(noa.user)
    client.post("/books/read/start/", {"first_done": "1", "entry": book.pk, "page": "1", "total_pages": ""})
    s = ReadingSession.objects.get(ended_at__isnull=True)
    s = reading.end(noa, s, 250)
    assert s.finished_book is False  # page 250 of an assumed 200 does not finish the book
    assert not BookDetail.objects.filter(entry=book, pages__isnull=False).exists()  # never written
    progress = reading.book_progress(noa, book)
    assert progress["pages"] == 200 and progress["pages_assumed"] and progress["percent"] == 100


def test_the_dials_inner_ring_is_the_book(client, noa, book):
    client.force_login(noa.user)
    read_today(noa, book, 3)  # ends on page 20
    html = client.get("/books/").content.decode()
    assert "--book: 10" in html and "בערך 10% מהספר" in html  # 20 of an assumed 200
    reading.set_pages(book, 80)
    html = client.get("/books/").content.decode()
    assert "--book: 25" in html and '<span class="bk-dial-book" aria-hidden="true"></span>' in html
    assert "25% מהספר" in html and "בערך" not in html


def test_the_dials_ring_is_todays_reading_toward_five_minutes(client, noa, book):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert 'style="--goal: 0"' in html and "0/5 דק׳ היום" in html
    read_today(noa, book, 3)
    html = client.get("/books/").content.decode()
    assert 'style="--goal: 60;' in html and "3/5 דק׳ היום" in html and "is-done" not in html
    read_today(noa, book, 4)
    html = client.get("/books/").content.decode()
    assert 'style="--goal: 100;' in html and "bk-dial is-done" in html and "היום נספר · 7 דק׳" in html


# ---- one book on its own -----------------------------------------------------------------

def test_home_offers_a_shelf_and_a_single_book(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert 'href="/books/scan/?book=1"' in html and 'href="/books/scan/"' in html


@pytest.mark.parametrize("single", [True, False])
def test_a_single_book_is_read_whole_and_a_shelf_in_strips(client, noa, monkeypatch, single):
    seen = []
    monkeypatch.setattr(shelf, "read_shelf", lambda data, **kw: seen.append("shelf") or Reading(model="m", books=[], calls=[]))
    monkeypatch.setattr(shelf, "read_single", lambda data, **kw: seen.append("single") or Reading(model="m", books=[], calls=[]))
    client.force_login(noa.user)
    data = {"photo": upload(), "default_visibility": "private"}
    if single:
        data["single"] = "1"
    r = client.post("/books/scan/", data)
    scan = ShelfScan.objects.get()
    assert scan.is_single is single and seen == (["single"] if single else ["shelf"])
    assert ("book=1" in r["Location"]) is single


def _single_scan(client, noa, monkeypatch, box=(0.2, 0.1, 0.8, 0.9), title="מיכאל שלי"):
    from books.recognition import Book
    monkeypatch.setattr(shelf, "read_single", lambda data, **kw: Reading(
        model="m", books=[Book(title, "עמוס עוז")], calls=[], box=box))
    client.force_login(noa.user)
    client.post("/books/scan/", {"photo": upload(), "default_visibility": "private", "single": "1"})
    return ShelfScan.objects.get()


def test_a_single_book_photo_becomes_its_picture(client, noa, monkeypatch, book):
    """Avi, 2026-10-21: I photographed the book itself; that is its picture."""
    from books.models import CopyPhoto
    scan = _single_scan(client, noa, monkeypatch)
    assert scan.cover_box == "0.2,0.1,0.8,0.9"
    item = scan.items.get()
    client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "accept", "entry": book.pk, "visibility": "private"})
    book.refresh_from_db()
    photo = CopyPhoto.objects.get(copy__entry=book, kind="cover")
    from PIL import Image
    with photo.image.open("rb") as fh:
        w, h = Image.open(fh).size
    assert book.cover and 0.6 * 1600 * 0.9 < w < 0.7 * 1600 and 0.8 * 900 * 0.9 < h < 0.9 * 900  # the box, plus a margin


def test_a_catalogue_cover_is_never_replaced_by_my_photo(client, noa, monkeypatch, book):
    from django.core.files.base import ContentFile
    from tests.test_books_3 import photo_bytes
    book.cover.save("existing.jpg", ContentFile(photo_bytes()), save=True)
    before = book.cover.name
    scan = _single_scan(client, noa, monkeypatch)
    item = scan.items.get()
    client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "accept", "entry": book.pk, "visibility": "private"})
    book.refresh_from_db()
    assert book.cover.name == before


def test_a_box_too_small_is_not_used(client, noa, monkeypatch):
    from books.recognition import sane_box
    assert sane_box({"x0": 0.5, "y0": 0.5, "x1": 0.55, "y1": 0.9}) is None
    assert sane_box({"x0": -1, "y0": 0, "x1": 2, "y1": 1}) == (0.0, 0.0, 1.0, 1.0)
    assert sane_box({"x0": "a"}) is None


def test_starting_always_asks_the_length_filled_with_what_is_known(client, noa, book):
    reading.set_pages(book, 412)
    client.force_login(noa.user)
    html = client.get(f"/books/read/?entry={book.pk}").content.decode()
    assert 'name="total_pages" min="10" max="5000" inputmode="numeric" value="412"' in html and "אפשר לתקן" in html


def test_my_own_count_is_mine_and_the_catalogue_keeps_its_own(client, noa, book):
    from books.models import BookDetail
    reading.set_pages(book, 412)
    client.force_login(noa.user)
    client.post("/books/read/start/", {"first_done": "1", "entry": book.pk, "page": "10", "total_pages": "380"})
    assert BookDetail.objects.get(entry=book).pages == 412  # never written over
    assert reading.total_pages(book, noa) == 380 and reading.total_pages(book) == 412
    s = ReadingSession.objects.get(ended_at__isnull=True)
    reading.end(noa, s, 380)
    s.refresh_from_db()
    assert s.finished_book  # my count says I reached the end
    html = client.get(f"/books/read/?entry={book.pk}").content.decode()
    assert 'value="380"' in html


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


# ---- the domain opens Books (Avi, 2026-10-21: Books is the site) ----------------------

def test_the_domain_opens_books(client):
    r = client.get("/")
    assert r.status_code == 302 and r["Location"] == "/books/"


def test_babooks_main_page_lives_on_and_its_name_points_there(client):
    from django.urls import reverse
    assert reverse("home") == "/babook/" and client.get("/babook/").status_code == 200


def test_books_menu_leads_to_the_rest_of_the_site(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert html.count('class="bk-nav-item bk-nav-item--site" href="/babook/"') == 2  # phone bar and desktop side
    assert "עוד באתר" in html


# ---- beside the shelf: the spines' direction and search (Avi, 2026-10-22) --------------

def test_the_shelf_has_its_two_tools_and_the_direction_is_saved(client, noa):
    from books.models import CatalogEntry, Copy
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר על המדף")
    Copy.objects.create(owner=noa, entry=e)
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert "data-spine-flip" in html and 'href="/books/library/?find=1"' in html
    assert "is-text-down" not in html.split('data-shelf data-shelf-view')[0].rsplit('class="bk-shelf', 1)[1]
    assert client.post("/books/shelf/spines/", {"down": "1"}).json()["down"] is True
    noa.refresh_from_db()
    assert noa.spine_text_down is True
    assert 'class="bk-shelf is-text-down is-drawn"' in client.get("/books/").content.decode()


def test_search_opens_my_books_with_the_box_ready(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/library/?find=1").content.decode()
    assert '<details class="bk-filterbox" open>' in html and 'name="q" value="" autofocus' in html


# ---- "me" is facts with a small edit button (Avi, 2026-10-22) ----------------------------

def test_me_shows_facts_not_a_form(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/settings/").content.decode()
    assert '<span class="bk-prop-value">נועה</span>' in html
    assert html.count('class="bk-prop"') >= 14 and "bk-prop-edit" in html
    assert '<span class="bk-prop-value is-empty">לא הוזן</span>' in html  # no phone yet


def test_editing_one_fact_keeps_the_others(client, noa):
    client.force_login(noa.user)
    page = client.get("/books/settings/")
    form = page.context["form"]
    data = {k: v for k, v in form.initial.items() if v not in (None, False)}
    data["display_name"] = "נועה כהן"
    r = client.post("/books/settings/", data)
    assert r.status_code == 302
    noa.refresh_from_db()
    assert noa.display_name == "נועה כהן" and noa.language == "he"

