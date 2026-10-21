"""Finding scanned books on the web (Avi, 2026-10-20): only for books the
free sources missed, once per book for the whole site, within $2 a day,
never trusted blindly (checksum, never "sure"), as part of the scan."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from books import catalog, shelf, storage, weblookup
from books.models import CatalogEntry, ModelCall, Profile, ScanCandidate, ShelfScan, WebLookup
from books.recognition import Book, Reading
from tests.test_books_3 import upload

pytestmark = [pytest.mark.sprbk3, pytest.mark.django_db]
User = get_user_model()

FOUND = {"found": True, "title": "מיכאל שלי", "authors": ["עמוס עוז"], "publisher": "כתר", "year": "2008",
         "isbn": "9789650700508", "cover_url": "https://example.co.il/cover.jpg",
         "source_url": "https://example.co.il/book", "confidence": 0.95}


class FakeClient:
    def __init__(self, answers, searches=2):
        self.answers = answers
        self.searches = searches
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        title = kw["input"].split("Title as read: ")[1].split("\n")[0]
        answer = self.answers.get(title, {"found": False, "title": "", "authors": [], "publisher": "", "year": "",
                                          "isbn": "", "cover_url": "", "source_url": "", "confidence": 0})
        output = [SimpleNamespace(type="web_search_call")] * self.searches + [SimpleNamespace(type="message")]
        return SimpleNamespace(output=output, output_text=json.dumps(answer),
                               usage=SimpleNamespace(input_tokens=5000, output_tokens=300))


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.OPENAI_API_KEY = "sk-test"
    settings.BOOKS_WEB_LOOKUP = True
    settings.BOOKS_WEB_DAILY_USD = "2"
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])  # the free sources find nothing
    # No cover download in tests: replace only that job's worker, not the queue
    # (stubbing jobs.enqueue would also stop the scan's own reading job).
    monkeypatch.setitem(catalog.jobs._registry, "catalog.fetch_cover", lambda job: None)
    from django.core.cache import cache

    cache.clear()
    yield
    storage.reset_for_tests()


@pytest.fixture
def noa(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    return Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)


@pytest.fixture
def reader_sees(monkeypatch):
    def setup(books, answers, searches=2):
        monkeypatch.setattr(shelf, "read_shelf", lambda data, **kw: Reading(
            model="gpt-6.1-sol", books=[Book(t, a) for t, a in books],
            calls=[{"input_tokens": 1, "output_tokens": 1, "seconds": 1, "cost_usd": Decimal("0.01")}]))
        fake = FakeClient(answers, searches)
        monkeypatch.setattr(weblookup, "get_client", lambda: fake)
        return fake
    return setup


# ---- refusals: money and trust ---------------------------------------------------------------

def test_books_the_free_sources_matched_are_never_searched(noa, reader_sees, monkeypatch):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")
    catalog.set_creators(e, ["עמוס עוז"])
    fake = reader_sees([("מיכאל שלי", "עמוס עוז")], {"מיכאל שלי": FOUND})
    shelf.start_scan(noa, upload(), "סלון")
    assert fake.calls == []


def test_the_same_book_is_searched_once_for_the_whole_site(noa, reader_sees):
    fake = reader_sees([("ספר נדיר", "מחבר")], {})
    shelf.start_scan(noa, upload(), "סלון")
    shelf.start_scan(noa, upload(), "חדר שינה")
    assert len(fake.calls) == 1 and WebLookup.objects.get().found is False


def test_the_daily_cap_stops_searching(noa, reader_sees, settings):
    settings.BOOKS_WEB_DAILY_USD = "0.05"  # room for one book (reserve 0.04)
    fake = reader_sees([("א", ""), ("ב", ""), ("ג", "")], {})
    shelf.start_scan(noa, upload(), "")
    assert len(fake.calls) == 1
    fake.calls.clear()
    shelf.start_scan(noa, upload(), "")  # the spend so far fills the cap
    assert len(fake.calls) == 0


def test_no_key_or_switched_off_means_no_search(noa, reader_sees, settings):
    fake = reader_sees([("ספר נדיר", "")], {})
    settings.BOOKS_WEB_LOOKUP = False
    shelf.start_scan(noa, upload(), "")
    settings.BOOKS_WEB_LOOKUP = True
    settings.OPENAI_API_KEY = ""
    shelf.start_scan(noa, upload(), "")
    assert fake.calls == []


def test_a_bad_isbn_year_or_cover_link_is_dropped():
    rec = weblookup.to_record({**FOUND, "isbn": "9789650700509", "year": "שנת 3021", "cover_url": "http://x/y.jpg"})
    assert rec.isbns == [] and rec.year is None and rec.cover_url == ""
    assert weblookup.to_record({**FOUND, "found": False}) is None
    good = weblookup.to_record(FOUND)
    assert good.isbns == ["9789650700508"] and good.year == 2008 and good.publisher == "כתר"


def test_a_web_find_is_never_sure_so_it_is_never_confirmed_without_the_person(noa, reader_sees):
    reader_sees([("מיכאל שלי", "עמוס עוז")], {"מיכאל שלי": FOUND})
    scan = shelf.start_scan(noa, upload(), "סלון")
    item = scan.items.get()
    assert item.confidence <= shelf.WEB_CEILING < shelf.HIGH_CONFIDENCE
    assert shelf.accept_all_confident(scan) == 0


def test_each_search_is_costed_with_its_fee(noa, reader_sees):
    reader_sees([("ספר נדיר", "")], {}, searches=2)
    shelf.start_scan(noa, upload(), "")
    call = ModelCall.objects.get(purpose="web_lookup")
    assert call.cost_usd == Decimal("0.02") + weblookup.cost_of("gpt-6-luna", 5000, 300)
    assert WebLookup.objects.get().searches == 2


# ---- part of the scan ----------------------------------------------------------------------------

def test_a_book_found_on_the_web_waits_on_the_review_screen_with_its_details(client, noa, reader_sees):
    fake = reader_sees([("מיכאל שלי", "עמוס עוז"), ("ספר שלא קיים", "")], {"מיכאל שלי": FOUND})
    scan = shelf.start_scan(noa, upload(), "סלון")
    assert len(fake.calls) == 2  # both were weak, both searched, in one go
    kw = fake.calls[0]
    assert kw["model"] == "gpt-6-luna" and kw["max_tool_calls"] == weblookup.MAX_SEARCHES
    assert kw["tools"] == [{"type": "web_search"}]
    found = scan.items.get(raw_title="מיכאל שלי")
    cand = found.candidates.first()
    entry = cand.entry
    assert entry.source == "web" and entry.identifiers.filter(value="9789650700508").exists()
    assert entry.book.publisher == "כתר" and entry.year == 2008
    assert entry.cover_source_url == "https://example.co.il/cover.jpg"
    assert scan.items.get(raw_title="ספר שלא קיים").candidates.count() == 0
    client.force_login(noa.user)
    page = client.get(f"/books/scan/{scan.pk}/").content.decode()
    assert "כתר" in page and "2008" in page
    # The next person with the same spine reading pays nothing and sees the same record.
    u = User.objects.create_user("dan", "dan@example.com", "pw")
    dan = Profile.objects.create(user=u, display_name="דן", is_adult_confirmed=True)
    fake.calls.clear()
    scan2 = shelf.start_scan(dan, upload(), "")
    assert fake.calls == [] and scan2.items.get(raw_title="מיכאל שלי").candidates.first().entry == entry


def test_the_pilot_desk_shows_the_web_spend_against_the_cap(client, noa, reader_sees):
    reader_sees([("מיכאל שלי", "עמוס עוז")], {"מיכאל שלי": FOUND})
    shelf.start_scan(noa, upload(), "")
    noa.user.is_staff = True
    noa.user.save()
    client.force_login(noa.user)
    page = client.get("/books/pilot/").content.decode()
    assert "מתוך 2.00$" in page and "1 נמצאו מתוך 1 ספרים" in page
    assert ScanCandidate.objects.count() == 1 and ShelfScan.objects.get().status == ShelfScan.REVIEW
