"""BK4: my library (docs/books/backlog.md, spec BK4). The list and its
filters, one copy's page, offers, photos, moving many at once, adding by
hand, the wishlist, export, scan history; every page the owner's alone."""

import csv
import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from books import catalog, shelf, storage
from books.models import CatalogEntry, Copy, CopyPhoto, Offer, Profile, Tag, Wish

pytestmark = [pytest.mark.sprbk4, pytest.mark.django_db]
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
def books(db):
    t = catalog.book_type()
    a = CatalogEntry.objects.create(collection_type=t, title="מיכאל שלי", year=1968, language="he")
    catalog.set_creators(a, ["עמוס עוז"])
    catalog.add_identifier(a, "isbn13", "9780156031608")
    b = CatalogEntry.objects.create(collection_type=t, title="Jane Eyre")
    catalog.set_creators(b, ["Charlotte Brontë"])
    tag = Tag.objects.create(kind="genre", key="classics-x", name_he="קלאסיקה", name_en="Classics")
    b.tags.add(tag)
    return a, b


@pytest.fixture
def shelved(reader, books):
    p = reader.books_profile
    a = Copy.objects.create(owner=p, entry=books[0], location_note="סלון", position=1)
    b = Copy.objects.create(owner=p, entry=books[1], location_note="חדר עבודה", position=2, visibility="public")
    Offer.objects.create(copy=b, kind="lend", loan_days=14)
    return a, b


def jpeg(gps=False):
    img = Image.new("RGB", (900, 1200), (90, 60, 40))
    out = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (32.0, 47.0, 39.0), 3: "E", 4: (34.0, 59.0, 20.0)}
        img.save(out, format="JPEG", exif=exif.tobytes())
    else:
        img.save(out, format="JPEG")
    return SimpleUploadedFile("p.jpg", out.getvalue(), content_type="image/jpeg")


# ---- refusals ------------------------------------------------------------------------

def test_every_library_page_is_the_owners_alone(client, shelved, other):
    a, _ = shelved
    client.force_login(other)
    for url in (f"/books/copy/{a.pk}/",):
        assert client.get(url).status_code == 404
    assert client.post(f"/books/copy/{a.pk}/", {"visibility": "public", "location_note": "x"}).status_code == 404
    assert client.post(f"/books/copy/{a.pk}/delete/", {"confirm": "yes"}).status_code == 404
    assert client.post(f"/books/copy/{a.pk}/photo/", {"photo": jpeg(), "kind": "cover"}).status_code == 404
    assert Copy.objects.filter(pk=a.pk).exists()
    html = client.get("/books/library/").content.decode()
    assert "מיכאל שלי" not in html


def test_bulk_touches_only_my_copies(client, shelved, other):
    a, b = shelved
    client.force_login(other)
    client.post("/books/library/bulk/", {"copy": [a.pk, b.pk], "action": "move", "location_note": "גנוב"})
    a.refresh_from_db()
    assert a.location_note == "סלון"


def test_copy_photos_are_private(client, shelved, reader, other):
    a, _ = shelved
    client.force_login(reader)
    client.post(f"/books/copy/{a.pk}/photo/", {"photo": jpeg(gps=True), "kind": "copyright_page"})
    photo = CopyPhoto.objects.get(copy=a)
    assert client.get(f"/books/copy/{a.pk}/photo/{photo.pk}.jpg").status_code == 200
    with photo.image.open("rb") as fh:
        assert Image.open(io.BytesIO(fh.read())).getexif().get_ifd(0x8825) == {}  # stripped like a shelf photo
    client.force_login(other)
    assert client.get(f"/books/copy/{a.pk}/photo/{photo.pk}.jpg").status_code == 404
    assert client.post(f"/books/copy/{a.pk}/photo/{photo.pk}/delete/").status_code == 404


@pytest.mark.parametrize("name", ["copy-photos", "wishes"])
def test_the_api_shows_only_my_rows(client, shelved, other, name):
    client.force_login(other)
    assert client.get(f"/books/api/{name}/").json() == []


# ---- the list -------------------------------------------------------------------------

def test_the_list_filters_by_text_place_status_and_genre(client, shelved, reader):
    client.force_login(reader)
    def titles(qs):
        html = client.get("/books/library/" + qs).content.decode()
        return [t for t in ("מיכאל שלי", "Jane Eyre") if f'<span class="bk-entry-title">{t}</span>' in html]
    assert titles("") == ["מיכאל שלי", "Jane Eyre"]
    assert titles("?q=עוז") == ["מיכאל שלי"]
    assert titles("?where=חדר+עבודה") == ["Jane Eyre"]
    assert titles("?show=private") == ["מיכאל שלי"]
    assert titles("?show=lend") == ["Jane Eyre"]
    assert titles("?tag=classics-x") == ["Jane Eyre"]


def test_bulk_move_and_visibility(client, shelved, reader):
    a, b = shelved
    client.force_login(reader)
    client.post("/books/library/bulk/", {"copy": [a.pk, b.pk], "action": "move", "location_note": "ארגז במחסן"})
    assert set(Copy.objects.values_list("location_note", flat=True)) == {"ארגז במחסן"}
    client.post("/books/library/bulk/", {"copy": [b.pk], "action": "private"})
    b.refresh_from_db()
    assert b.visibility == "private" and not b.offers.exists()


# ---- one copy --------------------------------------------------------------------------

def test_the_copy_page_saves_offers_and_details(client, shelved, reader):
    a, _ = shelved
    client.force_login(reader)
    r = client.post(f"/books/copy/{a.pk}/", {"visibility": "private", "location_note": "מדף עליון", "condition": "good",
                                             "notes": "עותק של סבא", "lend": "on", "loan_days": 21, "sell": "on",
                                             "price": "35"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.visibility == "public"  # an offer makes it visible
    assert a.condition == "good" and a.notes == "עותק של סבא" and a.location_note == "מדף עליון"
    offers = {o.kind: o for o in a.offers.all()}
    assert set(offers) == {"lend", "sell"} and offers["lend"].loan_days == 21 and str(offers["sell"].price_amount) == "35.00"
    client.post(f"/books/copy/{a.pk}/", {"visibility": "private", "location_note": "מדף עליון"})
    a.refresh_from_db()
    assert a.visibility == "private" and not a.offers.exists()


def test_display_only_cannot_be_offered(client, shelved, reader):
    a, _ = shelved
    client.force_login(reader)
    r = client.post(f"/books/copy/{a.pk}/", {"visibility": "public", "display_only": "on", "lend": "on"})
    assert r.status_code == 200 and "לא יכול להיות מוצע" in r.content.decode()
    assert not Offer.objects.filter(copy=a).exists()


def test_rare_candidate_with_a_note(client, shelved, reader):
    a, _ = shelved
    client.force_login(reader)
    client.post(f"/books/copy/{a.pk}/", {"visibility": "public", "is_rare_candidate": "on",
                                         "rarity_note": "מהדורה ראשונה, חתום", "display_only": "on"})
    a.refresh_from_db()
    assert a.is_rare_candidate and a.display_only and a.rarity_note.startswith("מהדורה")


def test_removing_a_copy_keeps_the_record(client, shelved, reader, books):
    a, _ = shelved
    client.force_login(reader)
    client.post(f"/books/copy/{a.pk}/delete/", {"confirm": "yes"})
    assert not Copy.objects.filter(pk=a.pk).exists() and CatalogEntry.objects.filter(pk=books[0].pk).exists()


def test_home_spines_lead_to_the_copy_page(client, shelved, reader):
    client.force_login(reader)
    html = client.get("/books/").content.decode()
    rows = json.loads(html.split('id="home-data">', 1)[1].split("</script>", 1)[0])
    assert rows[0]["url"] == f"/books/copy/{shelved[0].pk}/"


# ---- adding without a scan ---------------------------------------------------------------

def test_add_by_isbn_finds_the_record_and_i_have_it(client, reader, books):
    client.force_login(reader)
    html = client.get("/books/library/add/?q=978-0-15-603160-8").content.decode()
    assert "מיכאל שלי" in html and f"/books/have/{books[0].pk}/" in html
    r = client.post(f"/books/have/{books[0].pk}/")
    copy = Copy.objects.get(owner=reader.books_profile)
    assert r["Location"] == f"/books/copy/{copy.pk}/" and copy.visibility == "private" and copy.added_via == "manual"
    html = client.get("/books/library/add/?q=978-0-15-603160-8").content.decode()
    assert "כבר בספרייה שלך" in html


def test_having_a_book_fulfils_its_wish(client, reader, books):
    Wish.objects.create(profile=reader.books_profile, entry=books[1])
    client.force_login(reader)
    client.post(f"/books/have/{books[1].pk}/")
    assert not Wish.objects.filter(profile=reader.books_profile).exists()


def test_have_respects_the_cap(client, reader, books, monkeypatch):
    monkeypatch.setattr(shelf, "FREE_CAP", 0)
    client.force_login(reader)
    r = client.post(f"/books/have/{books[0].pk}/")
    assert "cap=1" in r["Location"] and not Copy.objects.exists()


# ---- the wishlist ---------------------------------------------------------------------------

def test_wishlist_from_the_catalogue_and_by_text(client, reader, books):
    client.force_login(reader)
    client.post(f"/books/wishlist/add/{books[0].pk}/", {"next": f"/books/catalog/{books[0].pk}/"})
    client.post(f"/books/wishlist/add/{books[0].pk}/")  # twice is once
    client.post("/books/wishlist/", {"free_text": "ספר שלא בקטלוג"})
    assert Wish.objects.filter(profile=reader.books_profile).count() == 2
    html = client.get(f"/books/catalog/{books[0].pk}/").content.decode()
    assert "ברשימת המשאלות" in html
    w = Wish.objects.get(free_text="ספר שלא בקטלוג")
    client.post(f"/books/wishlist/{w.pk}/delete/")
    assert Wish.objects.filter(profile=reader.books_profile).count() == 1


def test_the_api_refuses_a_duplicate_or_empty_wish(client, reader, books):
    client.force_login(reader)
    assert client.post("/books/api/wishes/", json.dumps({"entry": books[0].pk}), content_type="application/json").status_code == 201
    assert client.post("/books/api/wishes/", json.dumps({"entry": books[0].pk}), content_type="application/json").status_code == 400
    assert client.post("/books/api/wishes/", json.dumps({}), content_type="application/json").status_code == 400


# ---- export, history, polish -------------------------------------------------------------------

def test_export_is_a_spreadsheet_excel_opens_in_hebrew(client, shelved, reader):
    client.force_login(reader)
    r = client.get("/books/library/export.csv")
    body = r.content.decode("utf-8")
    assert r["Content-Type"].startswith("text/csv") and body.startswith("﻿")
    rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
    assert rows[0][0] == "שם הספר"
    assert rows[1][0] == "מיכאל שלי" and rows[1][4] == "9780156031608"
    assert rows[2][8] == "להשאלה"


def test_scan_history_lists_my_scans(client, reader):
    client.force_login(reader)
    html = client.get("/books/library/scans/").content.decode()
    assert "עוד לא צילמת מדף" in html


def test_the_record_page_names_the_language(client, reader, books):
    client.force_login(reader)
    html = client.get(f"/books/catalog/{books[0].pk}/").content.decode()
    assert "· עברית" in html and "· he" not in html
