"""Fixing a book's details (Avi, 2026-10-22: "a title was wrong and I could
not change it"). Whoever holds a copy may edit the record directly; every
change is kept as an accepted correction with the old value."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from books import catalog, storage
from books.models import BookDetail, CatalogEntry, Copy, EntryCorrection, Profile

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


def person(name, staff=False):
    u = User.objects.create_user(name, f"{name}@example.com", "pw", is_staff=staff)
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True)


@pytest.fixture
def book(db):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלו", source="scan",
                                    is_verified=True)
    catalog.set_creators(e, ["עמוס עוז"])
    BookDetail.objects.create(entry=e, publisher="עם עובד", pages=200)
    return e


def form(**over):
    data = {"title": "מיכאל שלי", "subtitle": "", "creators": "עמוס עוז", "language": "he", "year": "1968",
            "publisher": "עם עובד", "identifier": "", "pages": "290", "description": "רומן על חנה."}
    data.update(over)
    return data


def test_a_holder_fixes_the_title_and_the_change_is_kept_with_the_old_value(client, book):
    noa = person("noa")
    Copy.objects.create(owner=noa, entry=book)
    client.force_login(noa.user)
    html = client.get(f"/books/catalog/{book.pk}/").content.decode()
    assert f'href="/books/catalog/{book.pk}/edit/"' in html and "עריכת פרטי הספר" in html
    r = client.post(f"/books/catalog/{book.pk}/edit/", form())
    assert r.status_code == 302 and r["Location"] == f"/books/catalog/{book.pk}/?edited=1"
    book.refresh_from_db()
    assert book.title == "מיכאל שלי" and book.description == "רומן על חנה."
    assert BookDetail.objects.get(entry=book).pages == 290
    logged = {c.note.split(":")[0]: c for c in EntryCorrection.objects.filter(entry=book)}
    assert set(logged) == {"title", "pages", "description", "year", "language"}
    assert logged["title"].status == EntryCorrection.ACCEPTED and "was: מיכאל שלו" in logged["title"].note
    assert "הפרטים עודכנו" in client.get(r["Location"]).content.decode()


def test_someone_without_the_book_cannot_edit_it(client, book):
    dan = person("dan")
    client.force_login(dan.user)
    assert client.get(f"/books/catalog/{book.pk}/edit/").status_code == 404
    assert client.post(f"/books/catalog/{book.pk}/edit/", form()).status_code == 404
    assert "עריכת פרטי הספר" not in client.get(f"/books/catalog/{book.pk}/").content.decode()


def test_staff_edit_without_a_trail(client, book):
    boss = person("boss", staff=True)
    client.force_login(boss.user)
    client.post(f"/books/catalog/{book.pk}/edit/", form())
    book.refresh_from_db()
    assert book.title == "מיכאל שלי" and not EntryCorrection.objects.exists()


def test_a_holder_replaces_the_cover(client, book):
    noa = person("noa")
    Copy.objects.create(owner=noa, entry=book)
    client.force_login(noa.user)
    buf = io.BytesIO()
    Image.new("RGB", (600, 900), (40, 60, 90)).save(buf, format="JPEG")
    client.post(f"/books/catalog/{book.pk}/edit/", form(cover=SimpleUploadedFile("c.jpg", buf.getvalue(), content_type="image/jpeg")))
    book.refresh_from_db()
    assert book.cover and EntryCorrection.objects.filter(entry=book, field="cover").exists()


def test_my_copy_page_leads_to_the_edit(client, book):
    noa = person("noa")
    copy = Copy.objects.create(owner=noa, entry=book)
    client.force_login(noa.user)
    assert f'href="/books/catalog/{book.pk}/edit/"' in client.get(f"/books/copy/{copy.pk}/").content.decode()
