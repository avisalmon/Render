"""SPR-BK2.2: the sources (docs/books/backlog.md, spec BK2, 12.14). Each
adapter is driven with a canned payload in the real shape of its API, every
result is copied into our own records, duplicates land on one entry, covers
are fetched by a job, and a failing source never breaks a look-up."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from PIL import Image

from books import catalog
from books.models import CatalogEntry, EntryIdentifier, Job, Profile
from books.sources import base, googlebooks, lookup, nli, openlibrary

pytestmark = [pytest.mark.sprbk2_2, pytest.mark.django_db]
User = get_user_model()

OL_SEARCH = {"docs": [{
    "key": "/works/OL1W", "title": "My Michael", "author_name": ["Amos Oz"], "first_publish_year": 1968,
    "isbn": ["9780156031608", "0156031604"], "language": ["eng", "heb"], "publisher": ["Harcourt"], "cover_i": 123,
    "number_of_pages_median": 287,
}]}
OL_ISBN = {"key": "/books/OL2M", "title": "My Michael", "authors": [{"key": "/authors/OL3A"}], "publish_date": "1972",
           "publishers": ["Vintage"], "isbn_13": ["9780156031608"], "number_of_pages": 300, "covers": [555],
           "languages": [{"key": "/languages/eng"}]}
OL_AUTHOR = {"name": "Amos Oz"}
GB = {"items": [{"id": "gb1", "volumeInfo": {
    "title": "My Michael", "authors": ["Amos Oz"], "publishedDate": "1968-01-01", "publisher": "Keter",
    "language": "en", "pageCount": 287, "description": "A novel.",
    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780156031608"}],
    "imageLinks": {"thumbnail": "http://books.google.com/x.jpg&edge=curl"},
}}]}
NLI = [{
    "@id": "https://www.nli.org.il/en/books/NNL_ALEPH990012345670205171/NLI",
    "http://purl.org/dc/elements/1.1/title": [{"@value": "מיכאל שלי"}],
    "http://purl.org/dc/elements/1.1/creator": [{"@value": "עוז, עמוס"}],
    "http://purl.org/dc/elements/1.1/date": [{"@value": "1968"}],
    "http://purl.org/dc/elements/1.1/publisher": [{"@value": "עם עובד"}],
    "http://purl.org/dc/elements/1.1/identifier": [{"@value": "danacode 123-45678"}],
    "http://purl.org/dc/elements/1.1/language": [{"@value": "heb"}],
}]


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def canned(monkeypatch):
    calls = []

    def fake_get_json(name, url, params=None, min_interval=0.0):
        calls.append((name, url, params))
        if name == "openlibrary":
            if url.endswith("/search.json"):
                return OL_SEARCH
            if "/isbn/" in url:
                return OL_ISBN
            if "/authors/" in url:
                return OL_AUTHOR
        if name == "googlebooks":
            return GB
        if name == "nli":
            return NLI
        return None

    monkeypatch.setattr(base, "get_json", fake_get_json)
    monkeypatch.setattr(openlibrary, "get_json", fake_get_json)
    monkeypatch.setattr(googlebooks, "get_json", fake_get_json)
    monkeypatch.setattr(nli, "get_json", fake_get_json)
    return calls


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


def test_open_library_search_and_isbn_are_read_into_records(canned):
    recs = openlibrary.search("my michael")
    assert recs[0].title == "My Michael" and recs[0].creators == ["Amos Oz"]
    assert recs[0].isbns == ["9780156031608"] and recs[0].language == "en" and recs[0].year == 1968
    assert recs[0].cover_url.endswith("/id/123-L.jpg")
    rec = openlibrary.by_isbn("9780156031608")[0]
    assert rec.creators == ["Amos Oz"] and rec.year == 1972 and rec.publisher == "Vintage"


def test_google_books_is_read_and_its_cover_link_cleaned(canned):
    rec = googlebooks.search("my michael")[0]
    assert rec.cover_url == "https://books.google.com/x.jpg" and rec.description == "A novel."
    assert rec.isbns == ["9780156031608"]


def test_nli_reads_hebrew_records_and_the_danacode(canned, settings):
    settings.BOOKS_NLI_API_KEY = "k"
    rec = nli.search("מיכאל שלי")[0]
    assert rec.title == "מיכאל שלי" and rec.creators == ["עוז, עמוס"] and rec.language == "he"
    assert rec.danacode == "123-45678" and rec.publisher == "עם עובד"


def test_nli_is_skipped_without_a_key(canned, settings):
    from books import sources
    settings.BOOKS_NLI_API_KEY = ""
    assert [m.NAME for m in sources.enabled()] == ["openlibrary", "googlebooks"]
    settings.BOOKS_NLI_API_KEY = "k"
    assert [m.NAME for m in sources.enabled()] == ["openlibrary", "googlebooks", "nli"]


def test_lookup_keeps_every_sources_record_and_caches(canned):
    recs = lookup(query="my michael")
    assert {r.source for r in recs} == {"openlibrary", "googlebooks"}
    n = len(canned)
    lookup(query="my michael")
    assert len(canned) == n  # the second ask came from the cache


def test_a_failing_source_does_not_break_the_lookup(monkeypatch):
    monkeypatch.setattr(openlibrary, "search", lambda q, limit=8: (_ for _ in ()).throw(base.SourceError("down")))
    monkeypatch.setattr(googlebooks, "search", lambda q, limit=8: [base.Record("googlebooks", "g", "Still here")])
    assert [r.title for r in lookup(query="x")] == ["Still here"]


def test_the_user_agent_names_us_and_a_contact(settings):
    settings.BOOKS_CONTACT_EMAIL = "avi@example.com"
    assert "babook-books" in base.user_agent() and "avi@example.com" in base.user_agent()


# ---- copying in -----------------------------------------------------------------

def test_import_copies_every_source_into_one_entry_per_book(canned, reader, settings):
    settings.BOOKS_JOBS_INLINE = False
    entries = catalog.import_lookup(query="my michael", created_by=reader.books_profile)
    assert len(entries) == 1
    e = CatalogEntry.objects.get(pk=entries[0].pk)
    assert e.title == "My Michael" and e.creator_names == "Amos Oz" and e.source == "openlibrary"
    schemes = {(i.scheme, i.value) for i in EntryIdentifier.objects.filter(entry=e)}
    assert ("isbn13", "9780156031608") in schemes and ("googlebooks", "gb1") in schemes
    assert e.book.publisher == "Harcourt" and e.description == "A novel."  # blanks filled from the later source
    assert e.is_verified is False
    assert Job.objects.filter(kind="catalog.fetch_cover", ref_id=e.pk).exists()


def test_importing_twice_changes_nothing(canned, reader):
    catalog.import_lookup(query="my michael")
    n_entries, n_ids = CatalogEntry.objects.count(), EntryIdentifier.objects.count()
    cache.clear()
    catalog.import_lookup(query="my michael")
    assert (CatalogEntry.objects.count(), EntryIdentifier.objects.count()) == (n_entries, n_ids)


def test_a_record_with_no_identifier_matches_an_existing_entry_by_title_and_creator(reader):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")
    catalog.set_creators(e, ["עמוס עוז"])
    rec = base.Record("nli", "n1", "מִיכָאֵל שֶׁלִּי", creators=["עמוס עוז"], year=1968)
    entry, created = catalog.upsert_from_record(rec)
    assert created is False and entry.pk == e.pk
    entry.refresh_from_db()
    assert entry.year == 1968  # the blank got filled


def test_a_different_book_with_the_same_title_stays_separate(reader):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Emma")
    catalog.set_creators(e, ["Jane Austen"])
    entry, created = catalog.upsert_from_record(base.Record("x", "1", "Emma", creators=["Someone Else"]))
    assert created is True and entry.pk != e.pk


def test_the_cover_job_stores_our_own_copy_and_ignores_a_placeholder(monkeypatch, settings, tmp_path, reader):
    from books import storage
    settings.MEDIA_ROOT = str(tmp_path); settings.BOOKS_GCS_BUCKET = ""; settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    big = io.BytesIO(); Image.new("RGB", (900, 1300), (90, 20, 20)).save(big, format="JPEG")

    class R:
        def __init__(self, content, status=200): self.content, self.status_code = content, status

    responses = {"https://x/cover.jpg": R(big.getvalue()), "https://x/blank.gif": R(b"GIF89a" + b"\0" * 40)}
    monkeypatch.setattr(catalog.requests, "get", lambda url, **kw: responses[url])
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="A", cover_source_url="https://x/cover.jpg")
    job = catalog.jobs.enqueue("catalog.fetch_cover", ref_id=e.pk)
    e.refresh_from_db(); job.refresh_from_db()
    assert job.status == Job.DONE and e.cover and e.cover.name.endswith(".jpg")
    assert max(Image.open(e.cover.path).size) <= 800
    f = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="B", cover_source_url="https://x/blank.gif")
    catalog.jobs.enqueue("catalog.fetch_cover", ref_id=f.pk)
    f.refresh_from_db()
    assert not f.cover
    storage.reset_for_tests()
