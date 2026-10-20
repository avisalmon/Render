"""Enriching records once each (Avi, 2026-10-20): free sources first, the
web only for what is still missing, only the same book, only blanks, every
record marked so it is never done twice, running by itself."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from books import catalog, enrich, jobs, storage, weblookup
from books.models import BookDetail, CatalogEntry, Copy, EntryEnrichment, Job, Profile
from books.sources.base import Record

pytestmark = [pytest.mark.sprbk3, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.OPENAI_API_KEY = ""
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    monkeypatch.setitem(jobs._registry, "catalog.fetch_cover", lambda job: None)
    from django.core.cache import cache

    cache.clear()
    yield
    storage.reset_for_tests()


@pytest.fixture
def noa(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    return Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)


def bare(title, author="", owner=None):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)
    if author:
        catalog.set_creators(e, [author])
    if owner:
        Copy.objects.create(owner=owner, entry=e)
    return e


def rec(**kw):
    base = dict(source="googlebooks", source_ref="g1", title="מיכאל שלי", creators=["עמוס עוז"], year=1968,
                publisher="עם עובד", isbns=["9789650700508"], cover_url="https://books.google.com/c.jpg",
                description="רומן", language="he")
    base.update(kw)
    return Record(**base)


def sources_answer(monkeypatch, records):
    calls = []
    monkeypatch.setattr(catalog, "lookup", lambda **kw: calls.append(kw) or list(records))
    return calls


# ---- refusals: never the wrong book, never overwrite, never twice -----------------------------

def test_a_different_book_is_never_copied_in(noa, monkeypatch):
    e = bare("מיכאל שלי", "עמוס עוז", noa)
    sources_answer(monkeypatch, [rec(title="מיכאל שלי ואחרים", creators=["מישהו אחר"]),
                                 rec(title="ספר אחר לגמרי", creators=["עמוס עוז"])])
    row = enrich.enrich(e)
    e.refresh_from_db()
    assert row.status == EntryEnrichment.NOT_FOUND and not e.year and not e.identifiers.exists()


def test_what_a_person_wrote_is_never_overwritten(noa, monkeypatch):
    e = bare("מיכאל שלי", "עמוס עוז", noa)
    e.year = 1970
    e.description = "כתבתי בעצמי"
    e.save()
    BookDetail.objects.create(entry=e, publisher="הוצאה שלי")
    sources_answer(monkeypatch, [rec()])
    enrich.enrich(e)
    e.refresh_from_db()
    assert e.year == 1970 and e.description == "כתבתי בעצמי" and e.book.publisher == "הוצאה שלי"
    assert e.identifiers.filter(value="9789650700508").exists()  # the blank was filled


def test_a_record_is_enriched_once_ever(noa, monkeypatch):
    e = bare("ספר נדיר", "", noa)
    calls = sources_answer(monkeypatch, [])
    enrich.enrich(e)
    enrich.enrich(e)
    assert len(calls) == 1 and EntryEnrichment.objects.get(entry=e).status == EntryEnrichment.NOT_FOUND
    assert e not in list(enrich.waiting())
    assert enrich.start(e, noa) is False


def test_an_isbn_that_fails_its_checksum_is_not_kept(noa, monkeypatch):
    e = bare("מיכאל שלי", "עמוס עוז", noa)
    sources_answer(monkeypatch, [rec(isbns=["9789650700509"])])
    enrich.enrich(e)
    assert not e.identifiers.filter(scheme="isbn13").exists()


def test_only_staff_see_the_sources_check(client, noa):
    client.force_login(noa.user)
    assert client.get("/books/internal/sources/").status_code == 404


# ---- the order of cost -----------------------------------------------------------------------------

def test_free_sources_fill_it_and_the_web_is_not_asked(noa, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    asked = []
    monkeypatch.setattr(weblookup, "lookup_many", lambda *a, **kw: asked.append(a) or {})
    e = bare("מיכאל שלי", "עמוס עוז", noa)
    sources_answer(monkeypatch, [rec()])
    row = enrich.enrich(e)
    e.refresh_from_db()
    assert row.status == EntryEnrichment.DONE and row.sources == ["googlebooks"] and not row.used_web
    assert e.year == 1968 and e.book.publisher == "עם עובד" and e.cover_source_url.startswith("https://")
    assert e.identifiers.get(scheme="isbn13").value == "9789650700508"
    assert asked == []


def test_by_isbn_when_the_record_has_one(noa, monkeypatch):
    e = bare("כותרת שונה קצת", "", noa)
    catalog.add_identifier(e, "isbn13", "9789650700508")
    calls = sources_answer(monkeypatch, [rec(title="מיכאל שלי")])
    enrich.enrich(e)
    e.refresh_from_db()
    assert calls[0]["isbn"] == "9789650700508" and calls[0]["query"] is None
    assert e.year == 1968  # matched by ISBN, though the titles differ


def test_the_web_fills_what_the_free_sources_could_not(noa, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    e = bare("תיכון לילה", "", noa)
    sources_answer(monkeypatch, [])
    answer = {"found": True, "title": "תיכון לילה", "authors": ["סי. ג'יי. דאוורטי"], "publisher": "ספרי עליית הגג",
              "year": "2012", "isbn": "9789655455205", "cover_url": "https://ybook.co.il/c.jpg",
              "source_url": "https://ybook.co.il/p", "confidence": 0.9}
    fake = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        output=[SimpleNamespace(type="web_search_call")] * 3, output_text=json.dumps(answer),
        usage=SimpleNamespace(input_tokens=5000, output_tokens=300))))
    monkeypatch.setattr(weblookup, "get_client", lambda: fake)
    row = enrich.enrich(e)
    e.refresh_from_db()
    assert row.used_web and "web" in row.sources and row.cost_usd > Decimal("0.03")
    assert e.identifiers.get(scheme="isbn13").value == "9789655455205" and e.year == 2012


# ---- running by itself -----------------------------------------------------------------------------

def test_a_book_added_to_a_library_is_enriched_in_the_background(client, noa, monkeypatch):
    e = bare("מיכאל שלי", "עמוס עוז")
    sources_answer(monkeypatch, [rec()])
    client.force_login(noa.user)
    client.post(f"/books/have/{e.pk}/")
    assert EntryEnrichment.objects.get(entry=e).status == EntryEnrichment.DONE


def test_the_backlog_is_worked_through_from_page_views(client, noa, monkeypatch):
    for i in range(3):
        bare(f"ספר {i}", "", noa)
    sources_answer(monkeypatch, [])
    client.force_login(noa.user)
    client.get("/books/library/")  # the reminder tag runs the sweep, at most every ten minutes
    assert EntryEnrichment.objects.count() == 3 and enrich.counts()["waiting"] == 0
    assert Job.objects.filter(kind="entries.enrich_batch").count() == 1
    client.get("/books/library/")
    assert Job.objects.filter(kind="entries.enrich_batch").count() == 1  # throttled


def test_the_command_and_the_pilot_desk(client, noa, monkeypatch):
    from django.core.management import call_command

    bare("מיכאל שלי", "עמוס עוז", noa)
    bare("ספר נדיר", "", noa)
    sources_answer(monkeypatch, [rec()])
    call_command("books_enrich", "--limit", "10", "--no-web")
    assert enrich.counts() == {"done": 1, "partial": 0, "not_found": 1, "waiting": 0}
    noa.user.is_staff = True
    noa.user.save()
    client.force_login(noa.user)
    assert "1 הושלמו" in client.get("/books/pilot/").content.decode()


def test_enriching_from_the_web_never_makes_a_second_copy_of_the_book(noa, monkeypatch, settings):
    """Found in testing: the web lookup also saved what it found as a new
    record, which then held the ISBN instead of the book being enriched."""
    settings.OPENAI_API_KEY = "sk-test"
    e = bare("תיכון לילה", "", noa)
    sources_answer(monkeypatch, [])
    answer = {"found": True, "title": "תיכון לילה", "authors": [], "publisher": "ספרי עליית הגג", "year": "2012",
              "isbn": "9789655455205", "cover_url": "", "source_url": "", "confidence": 0.9}
    monkeypatch.setattr(weblookup, "get_client", lambda: SimpleNamespace(responses=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(output=[], output_text=json.dumps(answer),
                                            usage=SimpleNamespace(input_tokens=1, output_tokens=1)))))
    before = CatalogEntry.objects.count()
    enrich.enrich(e)
    assert CatalogEntry.objects.count() == before
    assert e.identifiers.get(scheme="isbn13").value == "9789655455205"


def test_a_source_that_is_down_or_blocking_is_paused_not_asked_per_book(monkeypatch):
    """The National Library's Cloudflare answered 403 here and 502 from Render."""
    from django.core.cache import cache

    from books import sources
    from books.sources import SourceError

    cache.clear()
    calls = []

    def down(query, limit=8):
        calls.append(query)
        raise SourceError("nli: HTTP 502")

    monkeypatch.setattr(sources, "enabled", lambda: [s for s in [sources.nli] if not sources._paused(s)])
    monkeypatch.setattr(sources.nli, "search", down)
    sources.lookup(query="א")
    sources.lookup(query="ב")
    assert calls == ["א"]  # paused after the first failure
    assert sources.should_pause(SourceError("nli: HTTP 403")) and not sources.should_pause(SourceError("timeout"))
