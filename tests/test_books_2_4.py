"""SPR-BK2.4: curation (docs/books/backlog.md, spec BK2). Verify, merge
duplicates without losing anything, accept or decline corrections; the
curator's desk is staff-only and a reader's suggestion reaches it."""

import json

import pytest
from django.contrib.auth import get_user_model

from books import catalog
from books.models import BookDetail, CatalogEntry, EntryCorrection, EntryIdentifier, Profile, Tag

pytestmark = [pytest.mark.sprbk2_4, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


@pytest.fixture
def curator(db):
    u = User.objects.create_user("avi", "avi@example.com", "pw", is_staff=True)
    Profile.objects.create(user=u, display_name="אבי", is_adult_confirmed=True)
    return u


@pytest.fixture
def pair(db):
    t = catalog.book_type()
    a = CatalogEntry.objects.create(collection_type=t, title="מיכאל שלי", year=1968)
    b = CatalogEntry.objects.create(collection_type=t, title="מיכאל שלי", language="he", description="רומן")
    catalog.set_creators(a, ["עמוס עוז"]); catalog.set_creators(b, ["עמוס עוז", "ניצה בן-ארי"])
    catalog.add_identifier(b, "isbn13", "9780156031608")
    tag = Tag.objects.create(kind="genre", key="israeli", name_he="ישראלי", name_en="Israeli")
    b.tags.add(tag)
    BookDetail.objects.create(entry=b, publisher="עם עובד")
    return a, b


def test_merge_moves_everything_to_the_winner_and_leaves_a_pointer(pair):
    a, b = pair
    child = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מהדורה", parent=b)
    catalog.merge(b, a)
    a.refresh_from_db(); b.refresh_from_db(); child.refresh_from_db()
    assert b.merged_into == a
    assert EntryIdentifier.objects.get(value="9780156031608").entry == a
    assert set(a.creators.values_list("name", flat=True)) == {"עמוס עוז", "ניצה בן-ארי"}
    assert a.tags.filter(key="israeli").exists()
    assert a.language == "he" and a.description == "רומן" and a.year == 1968  # blanks filled, nothing overwritten
    assert child.parent == a
    assert catalog.find_by_identifier("isbn13", "9780156031608") == a
    assert "ניצה" in a.search_text.replace("ניצה", "ניצה")  # the creators are searchable on the winner


def test_merging_an_entry_into_itself_is_a_no_op(pair):
    a, _ = pair
    assert catalog.merge(a, a) == a and a.merged_into is None


def test_duplicate_suspects_pair_same_title_same_creator(pair):
    a, b = pair
    pairs = catalog.duplicate_suspects()
    assert (a.pk, b.pk) in {(x.pk, y.pk) for x, y in pairs}
    other = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")
    catalog.set_creators(other, ["מישהו אחר"])
    assert not any(other.pk in (x.pk, y.pk) for x, y in catalog.duplicate_suspects())


def test_a_reader_suggests_and_only_a_curator_decides(client, reader, curator, pair):
    a, _ = pair
    client.force_login(reader)
    r = client.post(f"/books/api/catalog/{a.pk}/suggest/", json.dumps({"field": "year", "value": "1968", "note": "x"}),
                    content_type="application/json")
    assert r.status_code == 201
    cid = r.json()["id"]
    assert EntryCorrection.objects.get(pk=cid).profile == reader.books_profile
    assert client.patch(f"/books/api/corrections/{cid}/", json.dumps({"status": "accepted"}), content_type="application/json").status_code == 403
    client.force_login(curator)
    assert len(client.get("/books/api/corrections/").json()) == 1
    r = client.patch(f"/books/api/corrections/{cid}/", json.dumps({"status": "accepted"}), content_type="application/json")
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert EntryCorrection.objects.get(pk=cid).handled_by == curator.books_profile


def test_accepting_a_correction_changes_the_record(curator, pair):
    a, _ = pair
    me = curator.books_profile
    for field, value in (("title", "מיכאל שלי (מהדורה חדשה)"), ("year", "1970"), ("publisher", "כתר"),
                         ("creators", "עמוס עוז, מתרגם כלשהו"), ("language", "he")):
        c = EntryCorrection.objects.create(entry=a, profile=me, field=field, value=value)
        catalog.accept_correction(c, me)
    a.refresh_from_db()
    assert a.title.startswith("מיכאל שלי (") and a.year == 1970 and a.language == "he"
    assert a.book.publisher == "כתר"
    assert a.creators.count() == 2
    assert "מהדורה" in a.search_text


def test_declining_changes_nothing(curator, pair):
    a, _ = pair
    c = EntryCorrection.objects.create(entry=a, profile=curator.books_profile, field="title", value="wrong")
    catalog.decline_correction(c, curator.books_profile)
    a.refresh_from_db()
    assert a.title == "מיכאל שלי" and c.status == "declined"


def test_a_reader_sees_only_their_own_corrections(client, reader, curator, pair):
    a, _ = pair
    EntryCorrection.objects.create(entry=a, profile=curator.books_profile, field="title", value="x")
    EntryCorrection.objects.create(entry=a, profile=reader.books_profile, field="title", value="y")
    client.force_login(reader)
    assert [c["value"] for c in client.get("/books/api/corrections/").json()] == ["y"]


def test_the_desk_is_404_for_readers_and_works_for_a_curator(client, reader, curator, pair):
    a, b = pair
    EntryCorrection.objects.create(entry=a, profile=reader.books_profile, field="year", value="1968")
    client.force_login(reader)
    assert client.get("/books/curate/").status_code == 404
    assert client.post("/books/curate/act/", {"action": "verify", "entry": a.pk}).status_code == 404
    assert CatalogEntry.objects.get(pk=a.pk).is_verified is False
    client.force_login(curator)
    html = client.get("/books/curate/").content.decode()
    assert "מיכאל שלי" in html and 'name="action" value="merge"' in html and 'value="accept"' in html
    assert client.post("/books/curate/act/", {"action": "verify", "entry": a.pk}).status_code == 302
    assert CatalogEntry.objects.get(pk=a.pk).is_verified is True
    client.post("/books/curate/act/", {"action": "merge", "winner": a.pk, "loser": b.pk})
    assert CatalogEntry.objects.get(pk=b.pk).merged_into == a
    c = EntryCorrection.objects.get(entry=a)
    client.post("/books/curate/act/", {"action": "accept", "correction": c.pk})
    assert EntryCorrection.objects.get(pk=c.pk).status == "accepted"


def test_the_entry_page_form_sends_a_correction(client, reader, pair):
    a, _ = pair
    client.force_login(reader)
    r = client.post(f"/books/catalog/{a.pk}/", {"field": "year", "value": "1968", "note": ""})
    assert r.status_code == 200 and "תודה" in r.content.decode()
    assert EntryCorrection.objects.filter(entry=a, profile=reader.books_profile, field="year").exists()
