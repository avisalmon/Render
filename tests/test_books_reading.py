"""Reading sessions (Avi, 2026-10-20): start with the page you are on, the
clock runs, end with the page reached; a streak day after five minutes;
pace; "where was I"; finishing a book. Plus: my shelf photo on a book's
page, mine alone. Refusals first."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from books import catalog, play, reading, storage
from books.models import BookDetail, CatalogEntry, Copy, Profile, ReadingCheckin, ReadingLog, ReadingSession

pytestmark = [pytest.mark.sprbk8, pytest.mark.django_db]
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


def person(name, email):
    u = User.objects.create_user(email.split("@")[0], email, "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True)


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def book(noa):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")
    BookDetail.objects.create(entry=e, pages=300)
    Copy.objects.create(owner=noa, entry=e)
    return e


def login(client, p):
    client.force_login(p.user)
    return client


def read_for(profile, entry, minutes, start_page, end_page, finished=False, days_ago=0):
    """A finished session that started `days_ago` days ago and lasted `minutes`."""
    s = reading.start(profile, entry, start_page)
    begun = timezone.now() - timedelta(days=days_ago, minutes=minutes)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=begun)
    s.refresh_from_db()
    return reading.end(profile, s, end_page, finished, now=begun + timedelta(minutes=minutes))


# ---- refusals ----------------------------------------------------------------------------------

def test_one_session_at_a_time_and_only_mine(client, noa, book):
    s = reading.start(noa, book, 10)
    with pytest.raises(reading.ReadingError, match="active"):
        reading.start(noa, book, 10)
    dan = person("דן", "dan@example.com")
    with pytest.raises(reading.ReadingError, match="not_yours"):
        reading.end(dan, s, 20)
    login(client, dan)
    assert client.post(f"/books/read/{s.pk}/end/", {"end_page": 20}).status_code == 404
    assert client.get(f"/books/read/{s.pk}/").status_code == 404


def test_pages_cannot_go_backwards_and_a_session_ends_once(noa, book):
    s = reading.start(noa, book, 50)
    with pytest.raises(reading.ReadingError, match="backwards"):
        reading.end(noa, s, 40)
    with pytest.raises(reading.ReadingError, match="page"):
        reading.end(noa, s, "abc")
    reading.end(noa, s, 60)
    with pytest.raises(reading.ReadingError, match="ended"):
        reading.end(noa, s, 70)


def test_less_than_five_minutes_earns_no_streak_day(noa, book):
    read_for(noa, book, 4, 1, 5)
    assert play.streak(noa) == 0 and not ReadingCheckin.objects.exists()
    read_for(noa, book, 2, 5, 8)  # the day's total passes five minutes
    assert play.streak(noa) == 1
    assert ReadingCheckin.objects.get().minutes == 6


def test_a_forgotten_timer_counts_at_most_four_hours(noa, book):
    s = read_for(noa, book, 60 * 10, 1, 40)
    assert s.seconds == reading.MAX_SESSION_SECONDS


def test_another_persons_shelf_photo_is_never_shown(client, noa):
    from books.models import ScanItem, ShelfScan

    scan = ShelfScan.objects.create(owner=noa, status=ShelfScan.DONE, photo="x.jpg", shelf_label="סלון")
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר")
    c = Copy.objects.create(owner=noa, entry=e)
    ScanItem.objects.create(scan=scan, position=2, raw_title="ספר", copy=c)
    page = login(client, noa).get(f"/books/copy/{c.pk}/").content.decode()
    assert f"/books/scan/{scan.pk}/photo.jpg" in page and "סלון" in page
    dan = person("דן", "dan@example.com")
    login(client, dan)
    assert client.get(f"/books/scan/{scan.pk}/photo.jpg").status_code == 404
    assert client.get(f"/books/copy/{c.pk}/").status_code == 404


# ---- the reading screen -----------------------------------------------------------------------------

def test_start_read_and_finish_through_the_pages(client, noa, book):
    login(client, noa)
    page = client.get(f"/books/read/?entry={book.pk}").content.decode()
    assert 'name="page"' in page and "מיכאל שלי" in page
    r = client.post("/books/read/start/", {"first_done": "1", "entry": book.pk, "page": 120})
    assert r["Location"] == "/books/read/"
    s = ReadingSession.objects.get()
    assert s.start_page == 120 and s.ended_at is None
    assert ReadingLog.objects.get(profile=noa, entry=book).status == ReadingLog.READING
    page = client.get("/books/read/").content.decode()
    # The tip about Do Not Disturb left the timer (Avi, 2026-10-21: it took too much room); it stays on the start page.
    assert "data-timer" in page and "נא לא להפריע" not in page and "wakeLock" in page
    # Every other page shows that a session is running.
    assert "קוראים עכשיו: מיכאל שלי" in client.get("/books/library/").content.decode()
    ReadingSession.objects.filter(pk=s.pk).update(started_at=timezone.now() - timedelta(minutes=20))
    r = client.post(f"/books/read/{s.pk}/end/", {"end_page": 150})
    # Straight home, with the streak moment: twenty minutes made today count (Avi, 2026-10-21).
    assert r["Location"] == "/books/?streak=1"
    summary = client.get(f"/books/read/{s.pk}/").content.decode()  # the sitting's page is still there
    s.refresh_from_db()
    assert s.pages == 30 and 1190 <= s.seconds <= 1210
    assert "1.5" in summary and "היום נספר ברצף" in summary
    # Next time: where was I.
    page = client.get("/books/read/").content.decode()
    assert "עצרת בעמוד 150" in page
    assert "להמשיך מעמוד 150" in client.get(f"/books/catalog/{book.pk}/").content.decode()


def test_reaching_the_last_page_finishes_the_book(noa, book):
    s = read_for(noa, book, 30, 280, 300)
    assert s.finished_book
    assert ReadingLog.objects.get(profile=noa, entry=book).status == ReadingLog.READ
    other = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="בלי מספר עמודים")
    s2 = read_for(noa, other, 10, 0, 50, finished=True)
    assert s2.finished_book and ReadingLog.objects.get(profile=noa, entry=other).status == ReadingLog.READ


def test_pace_progress_and_the_parallel_minute_counts(noa, book):
    read_for(noa, book, 20, 0, 40, days_ago=2)
    read_for(noa, book, 10, 40, 60, days_ago=1)
    read_for(noa, book, 30, 60, 120)
    prog = reading.book_progress(noa, book)
    assert prog["last_page"] == 120 and prog["pages"] == 300 and prog["percent"] == 40
    assert prog["pace"] == 2.0 and prog["minutes_left"] == 90 and prog["minutes"] == 60
    st = reading.stats(noa)
    assert st["streak"] == 3 and st["today_minutes"] == 30 and st["streak_minutes"] == 60
    assert st["all_minutes"] == 60 and st["pace"] == 2.0


def test_discarding_a_mistaken_start_counts_nothing(client, noa, book):
    s = reading.start(noa, book, 5)
    login(client, noa).post(f"/books/read/{s.pk}/discard/")
    assert not ReadingSession.objects.exists() and play.streak(noa) == 0


def test_my_shelf_photos_are_listed_for_me(client, noa):
    from books.models import ShelfScan

    ShelfScan.objects.create(owner=noa, status=ShelfScan.DONE, photo="x.jpg", shelf_label="מדף עליון")
    page = login(client, noa).get("/books/library/scans/").content.decode()
    assert "bk-scan-thumb" in page and "מדף עליון" in page and "רק את/ה רואה" in page


def test_my_shelf_photo_also_shows_on_the_books_catalogue_page_for_me_only(client, noa):
    from books.models import ScanItem, ShelfScan

    scan = ShelfScan.objects.create(owner=noa, status=ShelfScan.DONE, photo="x.jpg", shelf_label="חדר עבודה")
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר")
    c = Copy.objects.create(owner=noa, entry=e)
    ScanItem.objects.create(scan=scan, position=0, raw_title="ספר", copy=c)
    page = login(client, noa).get(f"/books/catalog/{e.pk}/").content.decode()
    assert f"/books/scan/{scan.pk}/photo.jpg" in page and "חדר עבודה" in page
    dan = person("דן", "dan@example.com")
    page = login(client, dan).get(f"/books/catalog/{e.pk}/").content.decode()
    assert f"/books/scan/{scan.pk}/photo.jpg" not in page and "חדר עבודה" not in page


def test_starting_is_one_list_with_search_and_a_start_button_per_book(client, noa, book):
    """Avi on his phone: "I have to choose from a list, there is no search, no
    start button." Now: a search box, every book of mine as a row, and each
    row opens to the page and a Start button."""
    other = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Jane Eyre")
    Copy.objects.create(owner=noa, entry=other)
    read_for(noa, book, 10, 0, 33)
    page = login(client, noa).get("/books/read/").content.decode()
    assert "data-read-search" in page and "<select" not in page
    assert page.count('class="bk-read-row"') == 2
    assert page.count('name="entry"') == 2 and page.count("bk-btn--big") == 2
    assert page.index("מיכאל שלי") < page.index("Jane Eyre")  # the book I am in comes first
    assert 'value="33"' in page  # where I stopped
    picked = client.get(f"/books/read/?entry={other.pk}").content.decode()
    assert "<details open>" in picked
