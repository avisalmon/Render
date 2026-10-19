"""The scan flow after Avi's first real use (2026-10-19): several shelves
reading at once, a reminder that never lets waiting books go unnoticed, a
scan that never silently disappears, and one place per batch."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from books import catalog, shelf, storage
from books.models import Copy, Job, Notification, Profile, ScanItem, ShelfScan
from books.recognition import Book, Reading
from tests.test_books_3 import upload

pytestmark = [pytest.mark.sprbk3, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    from django.core.cache import cache

    cache.clear()
    yield
    storage.reset_for_tests()


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    return Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)


@pytest.fixture
def other(db):
    u = User.objects.create_user("dan", "dan@example.com", "pw")
    return Profile.objects.create(user=u, display_name="דן", is_adult_confirmed=True)


@pytest.fixture
def fake_reader(monkeypatch):
    books = [Book("מיכאל שלי", "עמוס עוז"), Book("Jane Eyre", "Charlotte Brontë"), Book("ספר שלישי", "")]
    calls = [{"input_tokens": 3000, "output_tokens": 400, "seconds": 12.5, "cost_usd": Decimal("0.01")}]
    monkeypatch.setattr(shelf, "read_shelf", lambda data: Reading(model="gpt-6.1-sol", books=list(books), calls=calls))


def login(client, p):
    client.force_login(p.user)
    return client


def stuck_scan(profile, minutes_ago=10, job_status=Job.RUNNING):
    """A scan whose reading thread died mid-run (a deploy restarted the server)."""
    scan = ShelfScan(owner=profile, shelf_label="סלון", status=ShelfScan.READING)
    from django.core.files.base import ContentFile

    from tests.test_books_3 import photo_bytes
    scan.photo.save("x.jpg", ContentFile(photo_bytes()), save=False)
    scan.save()
    then = timezone.now() - timedelta(minutes=minutes_ago)
    ShelfScan.objects.filter(pk=scan.pk).update(created_at=then)
    if job_status:
        Job.objects.create(kind="scan.read", ref_id=scan.pk, profile=profile, status=job_status, started_at=then)
    scan.refresh_from_db()
    return scan


# ---- refusals --------------------------------------------------------------------------------

def test_nobody_else_can_label_retry_remove_or_see_the_queue(client, reader, other, fake_reader):
    login(client, reader).post("/books/scan/", {"photo": upload(), "default_visibility": "private"})
    scan = ShelfScan.objects.get()
    login(client, other)
    for action in ("label", "retry", "remove"):
        assert client.post(f"/books/scan/{scan.pk}/{action}/", {"shelf_label": "x"}).status_code == 404
    assert client.get("/books/scan/queue/").json()["scans"] == []
    assert "מחכים לאישור שלך" not in client.get("/books/").content.decode()
    scan.refresh_from_db()
    assert scan.shelf_label == ""


def test_a_scan_still_inside_its_time_is_not_read_twice(reader, monkeypatch):
    calls = []
    monkeypatch.setattr(shelf.jobs, "enqueue", lambda *a, **kw: calls.append(a))
    scan = stuck_scan(reader, minutes_ago=2)
    assert shelf.heal(scan) is False and calls == []


def test_a_key_problem_is_not_retried_from_the_page(client, reader, monkeypatch):
    scan = stuck_scan(reader, job_status=None)
    ShelfScan.objects.filter(pk=scan.pk).update(status=ShelfScan.FAILED, error="key")
    calls = []
    monkeypatch.setattr(shelf.jobs, "enqueue", lambda *a, **kw: calls.append(a))
    login(client, reader).post(f"/books/scan/{scan.pk}/retry/")
    assert calls == []


# ---- several shelves at once ----------------------------------------------------------------------

def test_sending_a_photo_returns_to_the_camera_and_lists_every_shelf(client, reader, fake_reader):
    login(client, reader)
    r1 = client.post("/books/scan/", {"photo": upload(), "shelf_label": "סלון", "default_visibility": "private"})
    r2 = client.post("/books/scan/", {"photo": upload(), "shelf_label": "חדר שינה", "default_visibility": "private"})
    first, second = ShelfScan.objects.order_by("pk")
    assert r1["Location"] == f"/books/scan/?sent={first.pk}" and r2["Location"] == f"/books/scan/?sent={second.pk}"
    page = client.get(r2["Location"]).content.decode()
    assert "חדר שינה" in page and "נקרא ברקע" in page
    assert page.count('class="bk-queue-row"') == 2
    data = client.get("/books/scan/queue/").json()
    assert {s["label"] for s in data["scans"]} == {"סלון", "חדר שינה"}
    assert data["books"] == 6 and data["shelves"] == 2


def test_a_finished_reading_rings_the_bell(reader, fake_reader):
    scan = shelf.start_scan(reader, upload(), "סלון")
    n = Notification.objects.get(profile=reader)
    assert n.kind == "scan.ready" and n.scan == scan


# ---- always reminded --------------------------------------------------------------------------

def test_every_books_page_reminds_until_every_book_is_decided(client, reader, fake_reader):
    scan = shelf.start_scan(reader, upload(), "סלון")
    login(client, reader)
    for url in ("/books/", "/books/library/", "/books/near/", "/books/club/"):
        page = client.get(url).content.decode()
        assert "3 ספרים מ-1 מדפים מחכים לאישור שלך" in page, url
        assert f'href="/books/scan/{scan.pk}/"' in page
    for item in scan.items.all():
        client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "skip"})
    assert "מחכים לאישור שלך" not in client.get("/books/").content.decode()


def test_the_reminder_never_breaks_a_page_for_someone_without_a_profile(client):
    u = User.objects.create_user("fresh", "fresh@example.com", "pw")
    client.force_login(u)
    assert client.get("/books/welcome/").status_code == 200


# ---- never lost ---------------------------------------------------------------------------------

def test_a_scan_whose_thread_died_is_read_again(client, reader, fake_reader):
    scan = stuck_scan(reader, minutes_ago=10)
    login(client, reader).get("/books/scan/")  # any visit heals
    scan.refresh_from_db()
    assert scan.status == ShelfScan.REVIEW and scan.items.count() == 3
    jobs = Job.objects.filter(kind="scan.read", ref_id=scan.pk).order_by("created_at")
    assert jobs[0].status == Job.FAILED and "abandoned" in jobs[0].error and jobs.count() == 2


def test_a_scan_with_no_job_at_all_is_read_too(reader, fake_reader):
    scan = stuck_scan(reader, minutes_ago=10, job_status=None)
    ShelfScan.objects.filter(pk=scan.pk).update(status=ShelfScan.UPLOADED)
    scan.refresh_from_db()
    assert shelf.heal(scan) is True
    scan.refresh_from_db()
    assert scan.status == ShelfScan.REVIEW


def test_after_three_tries_a_scan_says_so_instead_of_reading_forever(client, reader, monkeypatch):
    monkeypatch.setattr(shelf.jobs, "enqueue", lambda *a, **kw: None)
    scan = stuck_scan(reader, minutes_ago=10)
    for _ in range(2):
        Job.objects.create(kind="scan.read", ref_id=scan.pk, profile=reader, status=Job.FAILED)
    assert shelf.heal(scan) is False
    scan.refresh_from_db()
    assert scan.status == ShelfScan.FAILED and scan.error == "stuck"
    assert Notification.objects.filter(profile=reader, kind="scan.failed", scan=scan).exists()
    page = login(client, reader).get(f"/books/scan/{scan.pk}/").content.decode()
    assert "שלוש פעמים" in page and f"/books/scan/{scan.pk}/retry/" in page
    assert "לא נקראו, לנסות שוב" in client.get("/books/").content.decode()


def test_try_again_reads_the_same_photo_and_remove_forgets_it(client, reader, fake_reader):
    scan = stuck_scan(reader, job_status=None)
    ShelfScan.objects.filter(pk=scan.pk).update(status=ShelfScan.FAILED, error="Timeout")
    login(client, reader).post(f"/books/scan/{scan.pk}/retry/")
    scan.refresh_from_db()
    assert scan.status == ShelfScan.REVIEW and scan.items.count() == 3
    item = scan.items.first()
    client.post(f"/books/scan/{scan.pk}/item/{item.pk}/", {"action": "accept", "entry": "", "title": "ספר",
                                                            "author": "", "visibility": "private"})
    client.post(f"/books/scan/{scan.pk}/remove/")
    assert not ShelfScan.objects.filter(pk=scan.pk).exists()
    assert Copy.objects.filter(owner=reader).count() == 1  # what was shelved stays


# ---- one place per batch ----------------------------------------------------------------------------

def test_the_first_place_typed_becomes_the_batchs_default(client, reader, fake_reader):
    scan = shelf.start_scan(reader, upload(), "")  # forgot the place
    first, second, third = scan.items.order_by("position")
    login(client, reader)
    client.post(f"/books/scan/{scan.pk}/item/{first.pk}/", {"action": "accept", "entry": "", "title": first.raw_title,
                                                             "author": first.raw_author, "visibility": "private",
                                                             "location_note": "חדר עבודה, מדף שני"})
    scan.refresh_from_db()
    assert scan.shelf_label == "חדר עבודה, מדף שני"
    page = client.get(f"/books/scan/{scan.pk}/").content.decode()
    assert page.count('value="חדר עבודה, מדף שני" data-location') == 2  # both waiting cards
    client.post(f"/books/scan/{scan.pk}/accept-confident/")
    client.post(f"/books/scan/{scan.pk}/item/{second.pk}/", {"action": "accept", "entry": "", "title": second.raw_title,
                                                              "author": "", "visibility": "private",
                                                              "location_note": scan.shelf_label})
    assert set(Copy.objects.filter(owner=reader).values_list("location_note", flat=True)) == {"חדר עבודה, מדף שני"}


def test_setting_the_place_for_the_whole_shelf_fills_books_already_shelved_without_one(client, reader, fake_reader):
    scan = shelf.start_scan(reader, upload(), "")
    first = scan.items.order_by("position").first()
    login(client, reader)
    client.post(f"/books/scan/{scan.pk}/item/{first.pk}/", {"action": "accept", "entry": "", "title": first.raw_title,
                                                             "author": "", "visibility": "private", "location_note": ""})
    assert Copy.objects.get().location_note == ""
    client.post(f"/books/scan/{scan.pk}/label/", {"shelf_label": "מסדרון"})
    scan.refresh_from_db()
    assert scan.shelf_label == "מסדרון" and Copy.objects.get().location_note == "מסדרון"
    assert scan.items.filter(review_status=ScanItem.PENDING).count() == 2
