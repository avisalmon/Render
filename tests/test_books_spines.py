"""Real spines on my shelf (Avi, 2026-10-22): the call that reads a shelf
also gives each spine's four corners; the spine is cut and straightened
locally and my shelf shows it. Old scans are read again once, in the
background. The model is never called: a fake reading stands in."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from PIL import Image

from books import catalog, jobs, recognition, shelf, storage
from books.models import CatalogEntry, Copy, ModelCall, Profile, ScanItem, ShelfScan
from books.recognition import Book, Reading

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    cache.clear()
    yield
    storage.reset_for_tests()


@pytest.fixture
def noa(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    return Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)


@pytest.fixture
def dan(db):
    u = User.objects.create_user("dan", "dan@example.com", "pw")
    return Profile.objects.create(user=u, display_name="דן", is_adult_confirmed=True)


def shelf_photo():
    img = Image.new("RGB", (1600, 900), (200, 190, 170))
    for i, colour in enumerate([(120, 30, 30), (30, 90, 40), (40, 50, 120)]):
        for x in range(200 + i * 300, 400 + i * 300):
            for y in range(150, 800, 4):
                img.putpixel((x, y), colour)
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


CORNERS = [(0.125, 0.25, 0.16, 0.125, 0.25, 0.89), (0.3125, 0.4375, 0.2, 0.3, 0.43, 0.89),
           (0.5, 0.625, 0.16, 0.5, 0.625, 0.89)]
TITLES = ["מיכאל שלי", "סיפור על אהבה וחושך", "קופסה שחורה"]


def make_scan(owner, done=False):
    scan = ShelfScan(owner=owner, status=ShelfScan.DONE, spines_done=done)
    scan.photo.save("s.jpg", ContentFile(shelf_photo()), save=False)
    scan.save()
    return scan


# ---- the corners --------------------------------------------------------------------

def test_a_strips_corners_become_the_whole_photos():
    c = recognition.corners_in_photo({"top_left_x": 0.5, "top_right_x": 1.0, "top_y": 0.1, "bottom_left_x": 0.5,
                                      "bottom_right_x": 1.0, "bottom_y": 0.9}, 800, 800, 1600)
    assert c == (0.75, 1.0, 0.1, 0.75, 1.0, 0.9)
    assert recognition.corners_in_photo({"top_left_x": 0.6, "top_right_x": 0.5, "top_y": 0, "bottom_left_x": 0,
                                         "bottom_right_x": 1, "bottom_y": 1}, 0, 100, 100) is None


def test_neighbours_never_share_a_slice():
    a = Book("א", corners=(0.10, 0.30, 0.1, 0.10, 0.32, 0.9))
    b = Book("ב", corners=(0.26, 0.40, 0.1, 0.28, 0.42, 0.9))
    recognition.separate([b, a])
    assert a.corners[1] == b.corners[0] == pytest.approx(0.28)
    assert a.corners[4] == b.corners[3] == pytest.approx(0.30)


# ---- a new read cuts its spines --------------------------------------------------------

def test_a_new_shelf_read_cuts_every_spine(noa, monkeypatch):
    books = [Book(t, "", c) for t, c in zip(TITLES, CORNERS)]
    monkeypatch.setattr(shelf, "read_shelf", lambda data, **kw: Reading(model="m", books=books, calls=[]))
    scan = make_scan(noa)
    scan.status = ShelfScan.UPLOADED
    scan.save()
    jobs.enqueue("scan.read", ref_id=scan.pk, profile=noa)
    scan.refresh_from_db()
    items = list(scan.items.order_by("position"))
    assert scan.spines_done and all(i.spine for i in items)
    first = Image.open(items[0].spine)
    assert first.height > first.width * 3  # a tall, thin spine
    assert items[0].spine_height == int((0.89 - 0.16) * 900)


# ---- old scans, once, in the background -------------------------------------------------

def test_an_old_scan_is_read_again_and_matched_by_title(noa, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    scan = make_scan(noa)
    for i, t in enumerate(TITLES):
        ScanItem.objects.create(scan=scan, position=i, raw_title=t)
    again = [Book(TITLES[2], "", CORNERS[2]), Book("ספר אחר לגמרי", "", CORNERS[1]), Book(TITLES[0], "", CORNERS[0])]
    calls = [{"input_tokens": 3000, "output_tokens": 500, "seconds": 9.0, "cost_usd": 0.011}]
    monkeypatch.setattr(shelf, "read_shelf", lambda data, **kw: Reading(model="m", books=again, calls=calls))
    assert shelf.sweep_spines(noa) is True
    assert shelf.sweep_spines(noa) is False  # once per ten minutes
    scan.refresh_from_db()
    by_title = {i.raw_title: bool(i.spine) for i in scan.items.all()}
    assert scan.spines_done and by_title == {TITLES[0]: True, TITLES[1]: False, TITLES[2]: True}
    assert ModelCall.objects.get().purpose == "spine_backfill"


def test_no_key_no_sweep(noa, settings):
    settings.OPENAI_API_KEY = ""
    make_scan(noa)
    assert shelf.sweep_spines(noa) is False


# ---- my shelf shows them; nobody else's does ---------------------------------------------

def _shelf_with_spines(owner):
    scan = make_scan(owner, done=True)
    rows = []
    for i, t in enumerate(TITLES):
        e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=t)
        copy = Copy.objects.create(owner=owner, entry=e, position=i)
        item = ScanItem.objects.create(scan=scan, position=i, raw_title=t, copy=copy)
        rows.append((copy, item))
    shelf.cut_spines(scan, [(item, CORNERS[i]) for i, (_, item) in enumerate(rows)])
    return rows


def test_my_shelf_rows_carry_the_real_spine(noa):
    rows = _shelf_with_spines(noa)
    shown = {r["id"]: r for r in shelf.shelf_books(noa, photos=True)}
    first = shown[rows[0][0].pk]
    assert first["photo"] == f"/books/copy/{rows[0][0].pk}/spine.jpg?v={rows[0][1].pk}"
    assert 24 <= first["w"] < first["h"] and 130 <= first["h"] <= 215
    assert all("photo" not in r for r in shelf.shelf_books(noa))  # without photos: drawn


def test_the_spine_image_is_mine_alone(client, noa, dan):
    copy, _ = _shelf_with_spines(noa)[0]
    client.force_login(noa.user)
    r = client.get(f"/books/copy/{copy.pk}/spine.jpg")
    assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"
    client.force_login(dan.user)
    assert client.get(f"/books/copy/{copy.pk}/spine.jpg").status_code == 404


def test_the_setting_turns_them_off(client, noa):
    _shelf_with_spines(noa)
    client.force_login(noa.user)
    assert "spine.jpg" in client.get("/books/").content.decode()
    noa.spine_photos = False
    noa.save()
    assert "spine.jpg" not in client.get("/books/").content.decode()
