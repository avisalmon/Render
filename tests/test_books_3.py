"""BK3: shelf scan and confirmation (docs/books/backlog.md, spec BK3).

The model is never called here: `read_shelf` is replaced by a fake that
returns what the skill's pipeline returns. The pipeline itself is measured
for real by `manage.py books_measure` (the accuracy gate). What is pinned:
the merge rules from the skill, the job (cost recorded, a bad key stops it),
candidates, the confirmation (nothing becomes a copy without an accept,
offers imply public), the cap, privacy of the photo, the API refusals, and
the home shelf drawing the person's copies."""

import io
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from books import catalog, recognition, shelf, storage
from books.models import CatalogEntry, Copy, ModelCall, Offer, Profile, ScanItem, ShelfScan
from books.recognition import Book, Reading

pytestmark = [pytest.mark.sprbk3, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    # No network: the sources answer nothing unless a test says otherwise.
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


def photo_bytes(gps=False):
    img = Image.new("RGB", (1600, 900), (120, 80, 50))
    out = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (32.0, 47.0, 39.0), 3: "E", 4: (34.0, 59.0, 20.0)}
        img.save(out, format="JPEG", exif=exif.tobytes())
    else:
        img.save(out, format="JPEG")
    return out.getvalue()


def upload(gps=False):
    return SimpleUploadedFile("shelf.jpg", photo_bytes(gps), content_type="image/jpeg")


@pytest.fixture
def fake_reader(monkeypatch):
    books = [Book("מיכאל שלי", "עמוס עוז"), Book("Jane Eyre", "Charlotte Brontë"), Book("ספר לא מוכר", "")]
    calls = [{"input_tokens": 3000, "output_tokens": 400, "seconds": 12.5, "cost_usd": Decimal("0.01000")},
             {"input_tokens": 3100, "output_tokens": 380, "seconds": 14.0, "cost_usd": Decimal("0.01020")}]
    monkeypatch.setattr(shelf, "read_shelf", lambda data: Reading(model="gpt-6.1-sol", books=list(books), calls=calls))
    return books


@pytest.fixture
def known(db):
    a = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", is_verified=True)
    catalog.set_creators(a, ["עמוס עוז"])
    b = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Jane Eyre")
    catalog.set_creators(b, ["Charlotte Brontë"])
    return a, b


# ---- the skill's merge rules ------------------------------------------------------

def test_merge_drops_the_overlap_duplicate_but_keeps_sequels():
    # The skill's measured rule: loose matching only at the strip edge, so the
    # book both strips saw is listed once; a sequel on the same strip is kept.
    left = [Book("משחקי הרעב: בלדה על ציפורים ונחשים", "קולינס"), Book("Harry Potter 1", "Rowling"), Book("משחקי הרעב", "קולינס")]
    right = [Book("משחקי הרעב", "קולינס"), Book("Harry Potter 2", "Rowling")]
    titles = [b.title for b in recognition.merge_strips([left, right])]
    assert titles == ["משחקי הרעב: בלדה על ציפורים ונחשים", "Harry Potter 1", "משחקי הרעב", "Harry Potter 2"]


def test_series_numbers_never_match():
    assert recognition.similarity("Book 2", "Book 5") == 0.0


def test_score_counts_found_missed_extra():
    labels = recognition.load_labels("# c\nA Title | X\nB Title | Y\n? hidden | Z\n")
    s = recognition.score(labels, [Book("A Title", "X"), Book("Other", "")])
    assert [b.title for b in s["found"]] == ["A Title"] and [b.title for b in s["missed"]] == ["B Title"]
    assert [b.title for b in s["extra"]] == ["Other"]


def test_cost_is_computed_from_the_price_table():
    assert recognition.cost_of("gpt-6.1-sol", 1_000_000, 100_000) == Decimal("3.00000")


def test_a_missing_key_is_a_key_problem(settings):
    settings.OPENAI_API_KEY = ""
    with pytest.raises(recognition.KeyProblem):
        recognition.get_client()


# ---- starting a scan --------------------------------------------------------------

def test_a_scan_reads_records_cost_and_finds_candidates(reader, fake_reader, known):
    a, b = known
    scan = shelf.start_scan(reader.books_profile, upload(), "סלון, עליון", "private", [])
    scan.refresh_from_db()
    assert scan.status == ShelfScan.REVIEW and scan.books_found == 3
    assert scan.cost_usd == Decimal("0.02020") and scan.model_name == "gpt-6.1-sol"
    assert ModelCall.objects.filter(profile=reader.books_profile, purpose="shelf_read").count() == 2
    items = list(scan.items.order_by("position"))
    assert [i.raw_title for i in items] == ["מיכאל שלי", "Jane Eyre", "ספר לא מוכר"]
    assert items[0].candidates.first().entry == a and items[0].confidence >= shelf.HIGH_CONFIDENCE
    assert items[1].candidates.first().entry == b
    assert not items[2].candidates.exists() and items[2].confidence == 0
    assert Copy.objects.count() == 0  # nothing becomes a copy without an accept


def test_the_photo_is_stored_without_metadata_and_gps_only_rounded(reader, fake_reader):
    scan = shelf.start_scan(reader.books_profile, upload(gps=True), "", "private", [])
    with scan.photo.open("rb") as fh:
        stored = Image.open(io.BytesIO(fh.read()))
    assert stored.getexif().get_ifd(0x8825) == {}
    reader.books_profile.refresh_from_db()
    assert (reader.books_profile.area_lat, reader.books_profile.area_lng) == (Decimal("32.79"), Decimal("34.99"))


def test_a_person_with_an_area_keeps_it(reader, fake_reader):
    reader.books_profile.area_lat, reader.books_profile.area_lng = Decimal("31.00"), Decimal("35.00")
    reader.books_profile.save()
    shelf.start_scan(reader.books_profile, upload(gps=True), "", "private", [])
    reader.books_profile.refresh_from_db()
    assert reader.books_profile.area_lat == Decimal("31.00")


def test_a_bad_key_stops_the_scan_with_a_clear_reason(reader, monkeypatch):
    def boom(data):
        raise recognition.KeyProblem("401")
    monkeypatch.setattr(shelf, "read_shelf", boom)
    scan = shelf.start_scan(reader.books_profile, upload(), "", "private", [])
    scan.refresh_from_db()
    assert scan.status == ShelfScan.FAILED and scan.error == "key"


def test_offers_by_default_make_the_scan_public(reader, fake_reader):
    scan = shelf.start_scan(reader.books_profile, upload(), "", "private", ["lend", "nonsense"])
    assert scan.default_visibility == "public" and scan.default_offers == "lend"


# ---- confirming --------------------------------------------------------------------

@pytest.fixture
def scan(reader, fake_reader, known):
    return shelf.start_scan(reader.books_profile, upload(), "סלון", "private", [])


def test_accept_makes_a_copy_with_offers_and_offers_imply_public(scan, known):
    item = scan.items.get(position=0)
    copy = shelf.accept(item, known[0], "private", ["lend", "exchange"], "סלון")
    assert copy.visibility == Copy.PUBLIC and copy.added_via == "scan" and copy.location_note == "סלון"
    assert set(copy.offers.values_list("kind", flat=True)) == {"lend", "exchange"}
    assert copy.offers.get(kind="lend").loan_days == 30
    item.refresh_from_db(); scan.refresh_from_db()
    assert item.review_status == ScanItem.ACCEPTED and item.copy == copy and scan.books_accepted == 1


def test_re_accepting_updates_the_same_copy_and_drops_removed_offers(scan, known):
    item = scan.items.get(position=0)
    first = shelf.accept(item, known[0], "public", ["lend", "sell"], "")
    second = shelf.accept(item, known[0], "private", [], "")
    assert first.pk == second.pk and second.visibility == "private" and not second.offers.exists()


def test_an_offer_on_a_private_copy_is_refused(scan, known):
    copy = shelf.accept(scan.items.get(position=0), known[0], "private", [], "")
    with pytest.raises(Exception):
        Offer.objects.create(copy=copy, kind="lend")


def test_keep_as_read_makes_an_unverified_record(scan, reader):
    item = scan.items.get(position=2)
    entry = shelf.entry_from_text(item.raw_title, item.raw_author, reader.books_profile)
    shelf.accept(item, entry, "private", [], "")
    assert entry.is_verified is False and entry.created_by == reader.books_profile and entry.source == "manual"


def test_skip_and_finishing_the_scan(scan, known):
    items = list(scan.items.order_by("position"))
    shelf.accept(items[0], known[0], "private", [], "")
    shelf.accept(items[1], known[1], "private", [], "")
    shelf.skip(items[2])
    scan.refresh_from_db()
    assert scan.status == ShelfScan.DONE and scan.books_accepted == 2


def test_accept_all_confident_takes_only_the_sure_ones(scan):
    n = shelf.accept_all_confident(scan)
    assert n == 2  # both catalogue matches are sure; the unknown book waits
    assert scan.items.filter(review_status=ScanItem.PENDING).count() == 1


def test_a_missed_book_can_be_added_and_matched(scan, known):
    item = shelf.add_missed(scan, "מיכאל שלי", "עמוס עוז")
    assert item.added_by_hand and item.candidates.first().entry == known[0]


def test_the_free_cap_stops_accepting(scan, known, monkeypatch, settings):
    settings.BOOKS_PILOT_EVERYONE_ASKS = False  # the cap is the free tier's (tests/conftest.py opens tiers)
    monkeypatch.setattr(shelf, "FREE_CAP", 1)
    shelf.accept(scan.items.get(position=0), known[0], "private", [], "")
    with pytest.raises(shelf.CapReached):
        shelf.accept(scan.items.get(position=1), known[1], "private", [], "")
    assert shelf.room_left(scan.owner) == 0


def test_a_paid_tier_has_no_cap(scan, known, monkeypatch):
    monkeypatch.setattr(shelf, "FREE_CAP", 0)
    scan.owner.tier = "plus"; scan.owner.save()
    shelf.accept(scan.items.get(position=0), known[0], "private", [], "")


# ---- the pages ----------------------------------------------------------------------

def test_the_scan_pages_are_the_owners_alone(client, scan, other):
    client.force_login(other)
    for url in (f"/books/scan/{scan.pk}/", f"/books/scan/{scan.pk}/status/", f"/books/scan/{scan.pk}/photo.jpg"):
        assert client.get(url).status_code == 404, url
    item = scan.items.first()
    r = client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "skip"})
    assert r.status_code == 404
    item.refresh_from_db()
    assert item.review_status == ScanItem.PENDING


def test_the_photo_is_served_to_its_owner_privately(client, scan, reader):
    client.force_login(reader)
    r = client.get(f"/books/scan/{scan.pk}/photo.jpg")
    assert r.status_code == 200 and r["Cache-Control"].startswith("private")
    html = client.get(f"/books/scan/{scan.pk}/").content.decode()
    assert "/media/" not in html


def test_upload_page_starts_a_scan_and_returns_to_the_camera(client, reader, fake_reader, known):
    client.force_login(reader)
    r = client.post("/books/scan/", {"photo": upload(), "shelf_label": "חדר עבודה", "default_visibility": "public",
                                     "default_offers": ["lend"]})
    scan = ShelfScan.objects.get(owner=reader.books_profile)
    # Back to the camera (Avi, 2026-10-19): the next shelf can go while this one reads.
    assert r.status_code == 302 and r["Location"] == f"/books/scan/?sent={scan.pk}"
    html = client.get(f"/books/scan/{scan.pk}/").content.decode()
    assert "מיכאל שלי" in html and "Jane Eyre" in html and 'data-scan-card' in html
    assert client.get(f"/books/scan/{scan.pk}/status/").json()["status"] == "review"


def test_the_confirmation_form_accepts_a_candidate_with_choices(client, scan, reader, known):
    client.force_login(reader)
    item = scan.items.get(position=0)
    r = client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {
        "action": "accept", "entry": known[0].pk, "visibility": "private", "offers": ["sell"], "location_note": "ארגז"})
    assert r.status_code == 302
    copy = Copy.objects.get(owner=reader.books_profile)
    assert copy.entry == known[0] and copy.visibility == "public" and copy.location_note == "ארגז"
    assert list(copy.offers.values_list("kind", flat=True)) == ["sell"]


def test_the_form_cannot_attach_an_entry_that_is_not_a_candidate(client, scan, reader):
    stranger = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="x")
    client.force_login(reader)
    item = scan.items.get(position=0)
    r = client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "accept", "entry": stranger.pk})
    assert r.status_code == 404 and not Copy.objects.exists()


def test_keep_as_read_through_the_form_with_a_fix(client, scan, reader):
    client.force_login(reader)
    item = scan.items.get(position=2)
    client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "accept", "entry": "", "title": "ספר מוכר עכשיו",
                                                            "author": "מישהי", "visibility": "private"})
    item.refresh_from_db()
    assert item.review_status == ScanItem.EDITED and item.copy.entry.title == "ספר מוכר עכשיו"


def test_json_replies_for_fetch(client, scan, reader):
    client.force_login(reader)
    item = scan.items.get(position=2)
    r = client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "skip"}, HTTP_ACCEPT="application/json")
    assert r.json()["ok"] is True


def test_home_draws_the_persons_copies_on_the_shelf(client, scan, reader, known):
    shelf.accept(scan.items.get(position=0), known[0], "public", ["lend"], "")
    client.force_login(reader)
    html = client.get("/books/").content.decode()
    raw = html.split('id="home-data">', 1)[1].split("</script>", 1)[0]
    rows = json.loads(raw)
    assert rows[0]["title"] == "מיכאל שלי" and rows[0]["status"] == "lend" and rows[0]["author"] == "עמוס עוז"
    assert rows[0]["color"].startswith("#") and 24 <= rows[0]["w"] <= 41
    assert shelf.spine_for(known[0].pk, "מיכאל שלי") == shelf.spine_for(known[0].pk, "מיכאל שלי")  # stable


def test_the_living_shelf_order_is_saved_for_the_owner_only(client, scan, reader, other, known):
    c1 = shelf.accept(scan.items.get(position=0), known[0], "private", [], "")
    c2 = shelf.accept(scan.items.get(position=1), known[1], "private", [], "")
    client.force_login(other)
    client.post("/books/shelf/reorder/", {"order": [c2.pk, c1.pk]})
    c1.refresh_from_db()
    assert c1.position < Copy.objects.get(pk=c2.pk).position
    client.force_login(reader)
    client.post("/books/shelf/reorder/", {"order": [c2.pk, c1.pk]})
    assert Copy.objects.get(pk=c2.pk).position == 1 and Copy.objects.get(pk=c1.pk).position == 2


# ---- the API ------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["scans", "scan-items", "copies", "offers"])
def test_the_api_shows_only_my_rows(client, scan, other, name):
    client.force_login(other)
    data = client.get(f"/books/api/{name}/").json()
    assert data == [] or data.get("results") == []


def test_api_accept_and_offer_rules(client, scan, reader, other, known):
    client.force_login(reader)
    item = scan.items.get(position=0)
    r = client.post(f"/books/api/scan-items/{item.pk}/accept/", json.dumps({"entry": known[0].pk, "visibility": "private"}),
                    content_type="application/json")
    assert r.status_code == 200
    cid = r.json()["id"]
    r = client.post("/books/api/offers/", json.dumps({"copy": cid, "kind": "lend"}), content_type="application/json")
    assert r.status_code == 400  # private copy
    client.patch(f"/books/api/copies/{cid}/", json.dumps({"visibility": "public"}), content_type="application/json")
    assert client.post("/books/api/offers/", json.dumps({"copy": cid, "kind": "lend"}), content_type="application/json").status_code == 201
    client.patch(f"/books/api/copies/{cid}/", json.dumps({"visibility": "private"}), content_type="application/json")
    assert not Offer.objects.filter(copy_id=cid).exists()  # going private withdraws every offer
    client.force_login(other)
    assert client.get(f"/books/api/copies/{cid}/").status_code == 404
    assert client.post("/books/api/offers/", json.dumps({"copy": cid, "kind": "lend"}), content_type="application/json").status_code == 400


def test_api_upload_creates_a_scan(client, reader, fake_reader, known):
    client.force_login(reader)
    r = client.post("/books/api/scans/upload/", {"photo": upload(), "shelf_label": "x"})
    assert r.status_code == 201 and r.json()["books_found"] == 3
    assert "photo" not in r.json()
