"""SPR-BK2.1: the catalogue models, the one-time seed, and the API with its
refusals (docs/books/backlog.md, spec BK2)."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from books import catalog
from books.models import BookDetail, CatalogEntry, CollectionType, Creator, EntryIdentifier, Profile, Tag

pytestmark = [pytest.mark.sprbk2_1, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


@pytest.fixture
def other(db):
    u = User.objects.create_user("dan", "dan@example.com", "pw")
    Profile.objects.create(user=u, display_name="דן", is_adult_confirmed=True)
    return u


@pytest.fixture
def curator(db):
    u = User.objects.create_user("avi", "avi@example.com", "pw", is_staff=True)
    Profile.objects.create(user=u, display_name="אבי", is_adult_confirmed=True)
    return u


@pytest.fixture
def seeded(db):
    call_command("seed_books", verbosity=0)


# ---- the seed is one-time --------------------------------------------------------

def test_seed_adds_the_book_type_and_tags_once_and_never_overwrites(db):
    call_command("seed_books", verbosity=0)
    assert CollectionType.objects.get(key="book").name_en == "Books"
    n = Tag.objects.count()
    assert n >= 50
    assert Tag.objects.get(key="thriller").parent.key == "fiction"
    # A curator renames a tag; the next deploy leaves it alone.
    Tag.objects.filter(key="thriller").update(name_he="מתח")
    call_command("seed_books", verbosity=0)
    assert Tag.objects.count() == n
    assert Tag.objects.get(key="thriller").name_he == "מתח"


# ---- models --------------------------------------------------------------------

def test_creator_and_entry_keep_a_normalised_search_text(seeded):
    c = Creator.objects.create(name="ש״י עַגְנוֹן")
    assert c.search_name == "שי עגנונ"
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="תְּמוֹל שִׁלְשׁוֹם")
    catalog.set_creators(e, ["ש״י עגנון"])
    e.refresh_from_db()
    assert e.search_text == "תמול שלשומ שי עגנונ"
    assert e.creators.count() == 1 and e.creators.first().pk == c.pk  # the same person, found by normalised name


def test_an_identifier_is_unique_across_the_catalogue(seeded):
    a = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="A")
    b = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="B")
    catalog.add_identifier(a, "isbn13", "9789655450000")
    catalog.add_identifier(b, "isbn13", "9789655450000")  # ignored, not duplicated
    assert EntryIdentifier.objects.filter(value="9789655450000").count() == 1
    assert catalog.find_by_identifier("isbn13", "9789655450000") == a


# ---- the API: refusals first -----------------------------------------------------

@pytest.mark.parametrize("name", ["catalog", "creators", "tags", "identifiers", "book-details", "corrections"])
def test_anonymous_and_unonboarded_get_nothing(client, db, name):
    assert client.get(f"/books/api/{name}/").status_code in (401, 403)
    u = User.objects.create_user("x", "x@example.com", "pw")
    client.force_login(u)
    assert client.get(f"/books/api/{name}/").status_code == 403


def test_anyone_onboarded_reads_the_catalogue_and_may_add_an_unverified_record(client, reader, seeded):
    client.force_login(reader)
    r = client.post("/books/api/catalog/", json.dumps({"title": "מיכאל שלי", "creator_names": ["עמוס עוז"],
                                                      "year": 1968, "language": "he", "tag_keys": ["israeli-fiction"]}),
                    content_type="application/json")
    assert r.status_code == 201, r.content
    data = r.json()
    assert data["is_verified"] is False and data["source"] == "manual"
    assert data["creators"][0]["name"] == "עמוס עוז"
    assert data["tag_keys"] == ["israeli-fiction"]
    assert CatalogEntry.objects.get(pk=data["id"]).created_by == reader.books_profile
    assert BookDetail.objects.filter(entry_id=data["id"]).exists()
    assert client.get(f"/books/api/catalog/{data['id']}/").json()["title"] == "מיכאל שלי"


def test_nobody_sets_verified_or_owner_through_the_api(client, reader, seeded):
    client.force_login(reader)
    r = client.post("/books/api/catalog/", json.dumps({"title": "x", "is_verified": True, "created_by": 999,
                                                      "source": "openlibrary"}), content_type="application/json")
    e = CatalogEntry.objects.get(pk=r.json()["id"])
    assert e.is_verified is False and e.created_by == reader.books_profile and e.source == "manual"


def test_the_adder_may_edit_until_verified_then_only_a_curator(client, reader, other, curator, seeded):
    client.force_login(reader)
    eid = client.post("/books/api/catalog/", json.dumps({"title": "typo"}), content_type="application/json").json()["id"]
    assert client.patch(f"/books/api/catalog/{eid}/", json.dumps({"title": "fixed"}), content_type="application/json").status_code == 200
    client.force_login(other)
    assert client.patch(f"/books/api/catalog/{eid}/", json.dumps({"title": "hijack"}), content_type="application/json").status_code == 403
    assert client.delete(f"/books/api/catalog/{eid}/").status_code == 403
    client.force_login(curator)
    assert client.post(f"/books/api/catalog/{eid}/verify/").status_code == 200
    client.force_login(reader)
    assert client.patch(f"/books/api/catalog/{eid}/", json.dumps({"title": "again"}), content_type="application/json").status_code == 403
    assert client.delete(f"/books/api/catalog/{eid}/").status_code == 403
    assert CatalogEntry.objects.get(pk=eid).title == "fixed"
    client.force_login(curator)
    assert client.delete(f"/books/api/catalog/{eid}/").status_code == 204


def test_only_a_curator_verifies_or_merges(client, reader, seeded):
    a = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="A")
    b = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="A")
    client.force_login(reader)
    assert client.post(f"/books/api/catalog/{a.pk}/verify/").status_code == 403
    assert client.post(f"/books/api/catalog/{b.pk}/merge/", json.dumps({"into": a.pk}), content_type="application/json").status_code == 403
    assert CatalogEntry.objects.get(pk=b.pk).merged_into is None


def test_tags_and_creators_are_read_only_for_readers(client, reader, curator, seeded):
    client.force_login(reader)
    assert client.get("/books/api/tags/").status_code == 200
    assert client.post("/books/api/tags/", {"kind": "genre", "key": "x", "name_he": "x", "name_en": "x"}).status_code == 403
    assert client.post("/books/api/creators/", {"name": "x"}).status_code == 403
    client.force_login(curator)
    assert client.post("/books/api/creators/", {"name": "x"}).status_code == 201


def test_merged_entries_leave_the_list_and_resolve_to_their_winner(client, reader, seeded):
    a = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Winner")
    b = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Loser")
    catalog.merge(b, a)
    client.force_login(reader)
    titles = [e["title"] for e in client.get("/books/api/catalog/").json()]
    assert titles == ["Winner"]
    assert client.get(f"/books/api/catalog/{b.pk}/").json()["id"] == a.pk


def test_list_filters_by_tag_and_creator(client, reader, seeded):
    a = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="A")
    b = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="B")
    a.tags.add(Tag.objects.get(key="poetry"))
    catalog.set_creators(b, ["רחל"])
    client.force_login(reader)
    assert [e["title"] for e in client.get("/books/api/catalog/?tag=poetry").json()] == ["A"]
    rid = Creator.objects.get(name="רחל").pk
    assert [e["title"] for e in client.get(f"/books/api/catalog/?creator={rid}").json()] == ["B"]
