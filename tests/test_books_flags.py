"""My library's rows (spec BK5b, SPR-G.3): show / give / lend / sell on every
book, saved the moment one is tapped, with no page reload."""

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


def test_each_switch_does_one_thing_and_the_four_stay_consistent(noa):
    c = book(noa, "ספר", Copy.HIDDEN)
    f = shelf.set_flag(c, "give", True)  # an offer on a hidden book shows it to the friends
    assert f["give"] and f["show"] and f["visibility"] == "private" and f["label"] == "למסירה"
    f = shelf.set_flag(c, "lend", True)
    assert Offer.objects.get(copy=c, kind="lend").loan_days == shelf.DEFAULT_LOAN_DAYS and f["label"] == "למסירה · להשאלה"
    f = shelf.set_flag(c, "lend", False)
    assert not f["lend"] and f["give"] and not Offer.objects.filter(copy=c, kind="lend").exists()
    f = shelf.set_flag(c, "show", False)  # "only me": the offers go with it
    assert f == {**f, "show": False, "give": False, "lend": False, "sell": False, "visibility": "hidden", "label": "רק אני"}
    assert not c.offers.exists()
    f = shelf.set_flag(c, "show", True)
    assert f["visibility"] == "private" and f["label"] == "לחברים"
    public = book(noa, "פומבי", Copy.PUBLIC)
    assert shelf.set_flag(public, "sell", True)["label"] == "למכירה"
    f = shelf.set_flag(public, "sell", False)
    assert f["visibility"] == "public" and f["label"] == "גלוי, לא מוצע"  # a switch off never hides the book
    with pytest.raises(ValueError):
        shelf.set_flag(public, "exchange", True)


def test_the_api_saves_one_switch_and_answers_with_all_four(client, noa):
    c = book(noa, "ספר", Copy.HIDDEN)
    other = book(person("דן", "dan@example.com"), "של דן")
    client.force_login(noa.user)
    url = f"/books/api/copies/{c.pk}/flags/"
    r = client.post(url, json.dumps({"flag": "give", "on": True}), content_type="application/json")
    assert r.status_code == 200 and r.json()["give"] is True and r.json()["show"] is True
    r = client.post(url, json.dumps({"flag": "show", "on": False}), content_type="application/json")
    assert r.json() == {**r.json(), "show": False, "give": False, "visibility": "hidden"}
    assert client.post(url, json.dumps({"flag": "exchange", "on": True}), content_type="application/json").status_code == 400
    assert client.post(f"/books/api/copies/{other.pk}/flags/", json.dumps({"flag": "give", "on": True}),
                       content_type="application/json").status_code == 404
    other.refresh_from_db()
    assert not other.offers.exists()


def test_every_row_of_my_library_carries_the_four_switches_as_they_stand(client, noa):
    a = book(noa, "אלף", Copy.PUBLIC, "give", "sell")
    b = book(noa, "בית", Copy.HIDDEN)
    client.force_login(noa.user)
    html = client.get("/books/library/").content.decode()
    assert "books/library.js" in html and "data-flag-list" in html
    rows = html.split("data-copy-row")[1:]
    assert len(rows) == 2
    row_a = next(r for r in rows if "אלף" in r)
    row_b = next(r for r in rows if "בית" in r)
    assert f'data-url="/books/api/copies/{a.pk}/flags/"' in row_a
    assert 'data-flag="show" checked' in row_a and 'data-flag="give" checked' in row_a and 'data-flag="sell" checked' in row_a
    assert 'data-flag="lend" checked' not in row_a and "<span data-copy-status>למסירה · למכירה</span>" in row_a
    assert 'data-flag="show" checked' not in row_b and "<span data-copy-status>רק אני</span>" in row_b
    assert row_a.count("<label") == 5  # the pick box and the four switches
    assert "לתצוגה" in row_a and "למסירה" in row_a and "להשאלה" in row_a and "למכירה" in row_a
    assert "data-flag" not in html.split("data-flag-list")[0]  # nowhere else
    _ = b
