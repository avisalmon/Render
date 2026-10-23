"""My library's rows (spec BK5b, SPR-G.3, Avi's second word 2026-10-23): one
"show" box per book, and when it is on, a small menu of how it is offered;
saved the moment it is touched, with no page reload."""

import json

import pytest
from django.contrib.auth import get_user_model

from books import catalog, shelf, storage
from books.models import CatalogEntry, Copy, Offer, Profile

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True  # no thread outlives a test (mistake 26)
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


def book(owner, title, visibility=Copy.PUBLIC, *kinds):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)
    c = Copy.objects.create(owner=owner, entry=e, visibility=visibility)
    for k in kinds:
        Offer.objects.create(copy=c, kind=k)
    return c


def test_the_show_box_and_the_offer_menu_keep_one_consistent_state(noa):
    c = book(noa, "ספר", Copy.HIDDEN)
    f = shelf.set_flag(c, "offer", "give")  # an offer on a hidden book shows it to the friends
    assert f == {"show": True, "offer": "give", "visibility": "private", "label": "למסירה"}
    f = shelf.set_flag(c, "offer", "lend")  # one way at a time
    assert f["offer"] == "lend" and [o.kind for o in c.offers.all()] == ["lend"]
    assert Offer.objects.get(copy=c).loan_days == shelf.DEFAULT_LOAN_DAYS and f["label"] == "להשאלה"
    f = shelf.set_flag(c, "offer", "")
    assert f == {"show": True, "offer": "", "visibility": "private", "label": "לחברים"}
    shelf.set_flag(c, "offer", "sell")
    f = shelf.set_flag(c, "show", False)  # "only me": the offer goes with it
    assert f == {"show": False, "offer": "", "visibility": "hidden", "label": "רק אני"} and not c.offers.exists()
    f = shelf.set_flag(c, "show", True)
    assert f["visibility"] == "private" and f["offer"] == ""
    public = book(noa, "פומבי", Copy.PUBLIC, "lend", "sell")
    assert shelf.flags_of(public)["offer"] == "lend"  # several old offers: the first in the menu's order shows
    f = shelf.set_flag(public, "offer", "")
    assert f["visibility"] == "public" and f["label"] == "גלוי, לא מוצע"  # the menu never hides the book
    with pytest.raises(ValueError):
        shelf.set_flag(public, "offer", "steal")
    with pytest.raises(ValueError):
        shelf.set_flag(public, "give", True)


def test_the_api_saves_the_box_or_the_menu_and_answers_with_the_row(client, noa):
    c = book(noa, "ספר", Copy.HIDDEN)
    other = book(person("דן", "dan@example.com"), "של דן")
    client.force_login(noa.user)
    url = f"/books/api/copies/{c.pk}/flags/"
    r = client.post(url, json.dumps({"flag": "offer", "on": "give"}), content_type="application/json")
    assert r.status_code == 200 and r.json() == {"show": True, "offer": "give", "visibility": "private", "label": "למסירה"}
    r = client.post(url, json.dumps({"flag": "show", "on": False}), content_type="application/json")
    assert r.json()["show"] is False and r.json()["offer"] == ""
    assert client.post(url, json.dumps({"flag": "offer", "on": "steal"}), content_type="application/json").status_code == 400
    assert client.post(url, json.dumps({"flag": "give", "on": True}), content_type="application/json").status_code == 400
    assert client.post(f"/books/api/copies/{other.pk}/flags/", json.dumps({"flag": "offer", "on": "give"}),
                       content_type="application/json").status_code == 404
    assert not other.offers.exists()


def test_every_row_of_my_library_has_the_show_box_and_the_menu_and_no_pick_box(client, noa):
    a = book(noa, "אלף", Copy.PUBLIC, "give")
    book(noa, "בית", Copy.HIDDEN)
    client.force_login(noa.user)
    html = client.get("/books/library/").content.decode()
    assert "books/library.js" in html and "data-flag-list" in html
    assert "bk-copy-pick" not in html and "data-bulk" not in html  # the pick box by the title is gone
    rows = html.split("data-copy-row")[1:]
    assert len(rows) == 2
    row_a = next(r for r in rows if "אלף" in r)
    row_b = next(r for r in rows if "בית" in r)
    assert f'data-url="/books/api/copies/{a.pk}/flags/"' in row_a
    assert "data-flag-show checked" in row_a and '<option value="give" selected>' in row_a
    select_a = row_a.split("<select")[1].split(">")[0]
    select_b = row_b.split("<select")[1].split(">")[0]
    assert " hidden" not in select_a and " hidden" in select_b  # no menu while the book is only mine
    assert "<span data-copy-status>למסירה</span>" in row_a and row_a.count("<label") == 1
    assert "data-flag-show checked" not in row_b and "<span data-copy-status>רק אני</span>" in row_b
    assert "לא מוצע" in row_a and "למסירה" in row_a and "להשאלה" in row_a and "להחלפה" in row_a and "למכירה" in row_a
