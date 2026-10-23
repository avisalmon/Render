"""The first time with a book (Avi, 2026-10-22): before the first sitting,
the cover (mine replaces a missing or small catalogue cover, never a good
one), the length, and what the back cover says (filling only what is
missing, suggesting corrections where it differs). The model is never
called: a fake client stands in."""

import io
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from books import catalog, firstread, reading, storage
from books.models import (BookDetail, CatalogEntry, Copy, CopyPhoto, EntryCorrection, EntryIdentifier, ModelCall,
                          Profile, ReadingSession)

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
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


def jpeg(w=800, h=1200):
    out = io.BytesIO()
    Image.new("RGB", (w, h), (90, 60, 40)).save(out, format="JPEG")
    return out.getvalue()


def photo(w=800, h=1200):
    return SimpleUploadedFile("p.jpg", jpeg(w, h), content_type="image/jpeg")


class FakeVision:
    def __init__(self, data):
        self.data = data
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kw):
        return SimpleNamespace(output_text=json.dumps(self.data), usage=SimpleNamespace(input_tokens=1500, output_tokens=200))


BACK = {"blurb": "סיפור על חנה וירושלים.", "isbn": "9789650703127", "publisher": "עם עובד", "year": 1968, "pages": 290}


# ---- the way in ---------------------------------------------------------------------

def test_the_first_start_of_a_book_goes_through_its_first_screen(client, noa, book):
    client.force_login(noa.user)
    r = client.post("/books/read/start/", {"entry": book.pk, "page": "5", "total_pages": "300"})
    assert r.status_code == 302 and r["Location"] == f"/books/read/first/{book.pk}/?page=5&total_pages=300"
    assert not ReadingSession.objects.exists()
    html = client.get(r["Location"]).content.decode()
    assert 'name="first_done" value="1"' in html and 'value="300"' in html and "כמה עמודים יש בספר?" in html
    r = client.post("/books/read/start/", {"entry": book.pk, "page": "5", "total_pages": "300", "first_done": "1"})
    assert r["Location"] == "/books/read/" and ReadingSession.objects.get().start_page == 5


def test_a_book_i_have_read_before_starts_at_once(client, noa, book):
    s = reading.start(noa, book, 1)
    reading.end(noa, s, 10)
    client.force_login(noa.user)
    r = client.post("/books/read/start/", {"entry": book.pk, "page": "10"})
    assert r["Location"] == "/books/read/"


def test_the_first_screen_shows_the_cover_there_is(client, noa, book):
    book.cover.save("c.jpg", ContentFile(jpeg()), save=True)
    client.force_login(noa.user)
    html = client.get(f"/books/read/first/{book.pk}/").content.decode()
    assert book.cover.url in html and "החלפה בצילום שלי" in html


# ---- the cover ----------------------------------------------------------------------

def test_my_cover_fills_an_empty_catalogue_cover_and_my_copy(noa, book):
    copy = Copy.objects.create(owner=noa, entry=book)
    done = firstread.save_cover(noa, book, photo())
    book.refresh_from_db()
    assert done == {"catalogue": True, "copy": True} and book.cover
    assert CopyPhoto.objects.get(copy=copy).kind == "cover"


def test_my_cover_replaces_a_small_catalogue_cover_but_never_someone_elses_good_one(noa, book):
    book.cover.save("small.jpg", ContentFile(jpeg(200, 300)), save=True)
    assert firstread.save_cover(noa, book, photo())["catalogue"] is True
    book.refresh_from_db()
    good = book.cover.name
    dan = Profile.objects.create(user=User.objects.create_user("dan", "dan@example.com", "pw"), display_name="dan",
                                 is_adult_confirmed=True)
    assert firstread.save_cover(dan, book, photo())["catalogue"] is False  # noa's is 800 wide now: it stays
    book.refresh_from_db()
    assert book.cover.name == good


def test_i_can_replace_my_own_photo_of_the_cover(noa, book):
    """Avi, 2026-10-23: a straightened cover that came out wrong is kept as shot, or taken again."""
    firstread.save_cover(noa, book, photo())
    book.refresh_from_db()
    first = book.cover.name
    assert firstread.save_cover(noa, book, photo())["catalogue"] is True
    book.refresh_from_db()
    assert book.cover.name != first


def test_a_second_photo_replaces_my_first(noa, book):
    copy = Copy.objects.create(owner=noa, entry=book)
    firstread.save_cover(noa, book, photo())
    firstread.save_cover(noa, book, photo())
    assert CopyPhoto.objects.filter(copy=copy, kind="cover").count() == 1


def test_the_cover_endpoint_answers_json(client, noa, book):
    client.force_login(noa.user)
    r = client.post(f"/books/read/first/{book.pk}/cover/", {"photo": photo()})
    assert r.status_code == 200 and r.json()["catalogue"] is True
    r = client.post(f"/books/read/first/{book.pk}/cover/", {})
    assert r.status_code == 400 and r.json()["error"]


# ---- the back cover -----------------------------------------------------------------

def test_the_back_cover_fills_what_is_missing(settings, noa, book):
    settings.OPENAI_API_KEY = "sk-test"
    done = firstread.read_back(noa, book, photo(), client=FakeVision(BACK))
    book.refresh_from_db()
    detail = BookDetail.objects.get(entry=book)
    assert book.description == "סיפור על חנה וירושלים." and book.year == 1968
    assert detail.publisher == "עם עובד" and detail.pages == 290
    assert EntryIdentifier.objects.get(entry=book).value == "9789650703127"
    assert set(done["filled"]) == {"description", "isbn", "publisher", "year", "pages"} and done["suggested"] == []
    call = ModelCall.objects.get()
    assert call.purpose == "back_cover" and call.ok and call.cost_usd > 0


def test_what_differs_becomes_a_correction_never_an_overwrite(settings, noa, book):
    settings.OPENAI_API_KEY = "sk-test"
    book.year = 1970
    book.description = "תיאור קיים"
    book.save()
    BookDetail.objects.create(entry=book, publisher="כתר", pages=300)
    done = firstread.read_back(noa, book, photo(), client=FakeVision(BACK))
    book.refresh_from_db()
    # The blurb joins an existing description under its own line (Avi, 2026-10-23); the year is a suggestion.
    assert book.year == 1970 and book.description == "תיאור קיים\n\nמהכריכה האחורית:\nסיפור על חנה וירושלים."
    assert BookDetail.objects.get(entry=book).pages == 300
    assert set(done["suggested"]) == {"publisher", "year"}
    firstread.read_back(noa, book, photo(), client=FakeVision(BACK))
    book.refresh_from_db()
    assert book.description.count("מהכריכה האחורית") == 1  # read twice: joined once
    assert set(EntryCorrection.objects.values_list("field", "value")) == {("publisher", "עם עובד"), ("year", "1968")}


def test_the_phones_barcode_is_used_when_the_model_saw_none(settings, noa, book):
    settings.OPENAI_API_KEY = "sk-test"
    firstread.read_back(noa, book, photo(), isbn_hint="9789650703127", client=FakeVision({**BACK, "isbn": ""}))
    assert EntryIdentifier.objects.get(entry=book).value == "9789650703127"


def test_a_bad_isbn_is_not_stored(settings, noa, book):
    settings.OPENAI_API_KEY = "sk-test"
    firstread.read_back(noa, book, photo(), client=FakeVision({**BACK, "isbn": "1234567890123"}))
    assert not EntryIdentifier.objects.exists()


def test_the_back_cover_needs_a_key_and_keeps_to_its_daily_budget(settings, noa, book):
    settings.OPENAI_API_KEY = ""
    with pytest.raises(firstread.FirstReadError, match="first.err.no_back"):
        firstread.read_back(noa, book, photo(), client=FakeVision(BACK))
    settings.OPENAI_API_KEY = "sk-test"
    settings.BOOKS_BACK_DAILY_USD = "0.01"
    ModelCall.objects.create(profile=noa, provider="openai", model="m", purpose="back_cover", cost_usd=Decimal("0.02"))
    with pytest.raises(firstread.FirstReadError, match="first.err.cap"):
        firstread.read_back(noa, book, photo(), client=FakeVision(BACK))


def test_the_back_endpoint_says_what_was_added(client, settings, noa, book, monkeypatch):
    settings.OPENAI_API_KEY = "sk-test"
    from books import recognition
    monkeypatch.setattr(recognition, "get_client", lambda: FakeVision(BACK))
    client.force_login(noa.user)
    r = client.post(f"/books/read/first/{book.pk}/back/", {"photo": photo()})
    assert r.status_code == 200 and "תקציר" in r.json()["filled"] and r.json()["pages"] == 290


def test_the_reading_screen_lets_me_photograph_both_covers(client, settings, noa, book):
    settings.OPENAI_API_KEY = "sk-test"
    reading.start(noa, book, 12)
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    assert "data-first-cover-input" in html and f'data-url="/books/read/first/{book.pk}/cover/"' in html
    assert "books/rectify.js" in html and "לא יצא טוב? לשמור כמו שצולם" in html
    assert f'data-first-back-input\n             data-url="/books/read/first/{book.pk}/back/"' in html
    assert "books/first.js" in html and "צילום הכריכה" in html and "צילום הגב" in html
    r = client.post(f"/books/read/first/{book.pk}/cover/", {"photo": photo()})
    assert r.status_code == 200
    book.refresh_from_db()
    assert book.cover  # the cover photographed mid-sitting is the book's picture

