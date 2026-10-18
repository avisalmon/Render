"""SPR-BK2.3: matching and search (docs/books/backlog.md, spec 12.7).
Identifiers first, then title and creator, tolerant of spelling and vowel
marks, in both languages; the search page and the add-by-hand page."""

import pytest
from django.contrib.auth import get_user_model

from books import catalog, textnorm
from books.models import CatalogEntry, Profile

pytestmark = [pytest.mark.sprbk2_3, pytest.mark.django_db]
User = get_user_model()


# ---- normalisation ---------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("מִיכָאֵל שֶׁלִּי", "מיכאל שלי"),
    ("ש״י עגנון", "שי עגנונ"),
    ("The Little Prince", "little prince"),
    ("  Moby-Dick;  or, The Whale ", "moby dick or the whale"),
    ("אַלְטְנוֹיְלַנְד", "אלטנוילנד"),
])
def test_normalize_folds_vowels_finals_quotes_and_articles(raw, expected):
    assert textnorm.normalize(raw) == expected


@pytest.mark.parametrize("raw,isbn13", [
    ("978-0-15-603160-8", "9780156031608"),
    ("0156031604", "9780156031608"),
    ("0-306-40615-2", "9780306406157"),
    ("9780306406158", None),  # bad check digit
    ("12345", None),
])
def test_isbn_normalisation_and_validation(raw, isbn13):
    assert textnorm.normalize_isbn(raw) == isbn13


def test_identifier_scheme_tells_isbn_from_danacode():
    assert textnorm.identifier_scheme("978-0-15-603160-8") == ("isbn13", "9780156031608")
    assert textnorm.identifier_scheme("978-965-13-2085-6") is None  # a mistyped ISBN is not a danacode
    assert textnorm.identifier_scheme("110-20145678") == ("danacode", "11020145678")
    assert textnorm.identifier_scheme("my michael") is None


def test_similarity_ranks_the_closer_title_higher():
    assert textnorm.similarity("מיכאל שלי", "מיכאל שלי עמוס עוז") > textnorm.similarity("מיכאל שלי", "סיפור על אהבה וחושך")
    assert textnorm.similarity("Jane Eyre", "Jane Eyre Charlotte Brontë") > 0.6


# ---- search ---------------------------------------------------------------------

@pytest.fixture
def library(db):
    t = catalog.book_type()
    rows = [("מיכאל שלי", ["עמוס עוז"]), ("סיפור על אהבה וחושך", ["עמוס עוז"]), ("תמול שלשום", ["ש״י עגנון"]),
            ("Jane Eyre", ["Charlotte Brontë"]), ("Emma", ["Jane Austen"]), ("The Little Prince", ["Antoine de Saint-Exupéry"])]
    out = {}
    for title, creators in rows:
        e = CatalogEntry.objects.create(collection_type=t, title=title)
        catalog.set_creators(e, creators)
        out[title] = e
    catalog.add_identifier(out["Emma"], "isbn13", "9780156031608")
    catalog.add_identifier(out["תמול שלשום"], "danacode", "11020145678")
    return out


def test_search_by_title_in_hebrew_with_vowel_marks(library):
    assert [e.title for e in catalog.search_local("מִיכָאֵל שֶׁלִּי")][:1] == ["מיכאל שלי"]


def test_search_by_author_finds_every_book(library):
    titles = {e.title for e in catalog.search_local("עמוס עוז")}
    assert titles == {"מיכאל שלי", "סיפור על אהבה וחושך"}


def test_search_tolerates_final_letters_and_quotes(library):
    assert [e.title for e in catalog.search_local("שי עגנונ")] == ["תמול שלשום"]
    assert [e.title for e in catalog.search_local('ש"י עגנון')] == ["תמול שלשום"]


def test_search_in_english_ignores_the_article_and_case(library):
    assert [e.title for e in catalog.search_local("little prince")] == ["The Little Prince"]
    assert [e.title for e in catalog.search_local("JANE EYRE")][:1] == ["Jane Eyre"]


def test_a_typed_isbn_or_danacode_goes_straight_to_the_record(library):
    assert [e.title for e in catalog.search_local("978-0-15-603160-8")] == ["Emma"]
    assert [e.title for e in catalog.search_local("110-20145678")] == ["תמול שלשום"]


def test_a_merged_entry_never_comes_back(library):
    dup = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Emma")
    catalog.merge(dup, library["Emma"])
    assert [e.pk for e in catalog.search_local("Emma")] == [library["Emma"].pk]


def test_an_empty_or_meaningless_query_returns_nothing(library):
    assert catalog.search_local("") == [] and catalog.search_local("   ") == [] and catalog.search_local("!!") == []


# ---- the pages -----------------------------------------------------------------

@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


def test_search_page_shows_results_and_offers_the_sources_and_adding_by_hand(client, reader, library):
    client.force_login(reader)
    html = client.get("/books/catalog/?q=עוז").content.decode()
    assert "מיכאל שלי" in html and "סיפור על אהבה וחושך" in html
    assert "sources=1" in html and "/books/catalog/new/?q=" in html


def test_search_page_asks_the_sources_when_told_to(client, reader, library, monkeypatch):
    called = {}
    monkeypatch.setattr(catalog, "import_lookup", lambda **kw: called.update(kw) or [])
    client.force_login(reader)
    html = client.get("/books/catalog/?q=nothing+like+this&sources=1").content.decode()
    assert called["query"] == "nothing like this" and called["isbn"] is None
    assert "החיפוש" in html or "חיפשנו" in html


def test_search_page_requires_onboarding(client, db):
    assert client.get("/books/catalog/").status_code == 302


def test_adding_by_hand_makes_an_unverified_entry_with_creators_and_identifier(client, reader, library):
    from django.core.management import call_command
    call_command("seed_books", verbosity=0)
    client.force_login(reader)
    r = client.post("/books/catalog/new/", {"title": "הכפר", "creators": "מאיר שלו", "language": "he", "year": 2009,
                                             "publisher": "עם עובד", "identifier": "978-965-13-2085-9"})
    assert r.status_code == 302
    e = CatalogEntry.objects.get(title="הכפר")
    assert e.creator_names == "מאיר שלו" and e.is_verified is False and e.created_by == reader.books_profile
    assert e.book.publisher == "עם עובד"
    assert e.identifiers.filter(scheme="isbn13", value="9789651320859").exists()
    html = client.get(r["Location"]).content.decode()
    assert "הכפר" in html and "עדיין לא אומת" in html


def test_a_bad_identifier_is_refused_with_a_message(client, reader):
    client.force_login(reader)
    r = client.post("/books/catalog/new/", {"title": "x", "identifier": "abc"})
    assert r.status_code == 200 and "לא נראה כמו" in r.content.decode()
    assert not CatalogEntry.objects.filter(title="x").exists()


def test_the_entry_page_redirects_a_merged_record_to_its_winner(client, reader, library):
    dup = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Emma")
    catalog.merge(dup, library["Emma"])
    client.force_login(reader)
    r = client.get(f"/books/catalog/{dup.pk}/")
    assert r.status_code == 302 and r["Location"].endswith(f"/books/catalog/{library['Emma'].pk}/")
