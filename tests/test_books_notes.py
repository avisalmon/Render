"""My thoughts on a book while I read it (Avi, 2026-10-21): typed or spoken,
they add up per book, they are mine alone, and they wait for me after the
session and on the book's page. The transcription model is never called:
a fake client stands in, and the audio is never kept."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from books import catalog, notes, reading, storage
from books.models import CatalogEntry, ModelCall, Profile, ReadingNote, ReadingSession

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


def person(name):
    u = User.objects.create_user(name, f"{name}@example.com", "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True)


@pytest.fixture
def noa(db):
    return person("noa")


@pytest.fixture
def dan(db):
    return person("dan")


@pytest.fixture
def book(db):
    return CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")


class FakeAudio:
    def __init__(self, text="ספר מרגש מאוד", fail=False):
        self.text, self.fail, self.calls = text, fail, []
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("down")
        return SimpleNamespace(text=self.text)


def clip(kind="audio/webm", size=2000):
    return SimpleUploadedFile("note.webm", b"\x1a" * size, content_type=kind)


# ---- the rules -------------------------------------------------------------------------

def test_notes_add_up_per_book_in_order_with_the_page_and_the_session(noa, book):
    s = reading.start(noa, book, 12)
    notes.add(noa, book, "  פתיחה חזקה  ", session=s, page=14)
    notes.add(noa, book, "הדמות של חנה", source="voice", session=s, page="30")
    rows = notes.for_book(noa, book)
    assert [n.body for n in rows] == ["פתיחה חזקה", "הדמות של חנה"]
    assert rows[0].page == 14 and rows[1].page == 30 and rows[1].source == "voice" and rows[0].session == s


def test_an_empty_or_huge_note_is_refused(noa, book):
    with pytest.raises(notes.NoteError, match="notes.err.empty"):
        notes.add(noa, book, "   ")
    with pytest.raises(notes.NoteError, match="notes.err.long"):
        notes.add(noa, book, "א" * 2001)


def test_someone_elses_session_is_not_attached(noa, dan, book):
    s = reading.start(dan, book, 1)
    assert notes.add(noa, book, "שלי", session=s).session is None


def test_only_the_owner_edits_or_removes(noa, dan, book):
    n = notes.add(noa, book, "שלי")
    with pytest.raises(notes.NoteError):
        notes.edit(dan, n, "שלו")
    with pytest.raises(notes.NoteError):
        notes.remove(dan, n)
    notes.edit(noa, n, "שלי, מתוקן")
    assert ReadingNote.objects.get().body == "שלי, מתוקן"


# ---- a spoken note -----------------------------------------------------------------------

def test_a_spoken_note_comes_back_as_words_and_only_its_cost_is_kept(settings, noa):
    settings.OPENAI_API_KEY = "sk-test"
    fake = FakeAudio()
    assert notes.transcribe(noa, clip(), seconds=30, client=fake) == "ספר מרגש מאוד"
    call = fake.calls[0]
    assert call["model"] == notes.DEFAULT_VOICE_MODEL and call["language"] == "he" and call["file"][0] == "note.webm"
    row = ModelCall.objects.get()
    assert row.purpose == "voice_note" and row.ok and str(row.cost_usd) == "0.00300"
    assert not ReadingNote.objects.exists()  # nothing saved until I save it


def test_no_key_no_voice(settings, noa):
    settings.OPENAI_API_KEY = ""
    with pytest.raises(notes.NoteError, match="notes.err.no_voice"):
        notes.transcribe(noa, clip(), client=FakeAudio())


@pytest.mark.parametrize("upload, key", [
    (None, "notes.err.no_audio"),
    (SimpleUploadedFile("x.webm", b"x" * (notes.MAX_CLIP_BYTES + 1), content_type="audio/webm"), "notes.err.too_long"),
    (SimpleUploadedFile("x.txt", b"hello", content_type="text/plain"), "notes.err.format"),
])
def test_bad_recordings_are_refused_before_any_call(settings, noa, upload, key):
    settings.OPENAI_API_KEY = "sk-test"
    fake = FakeAudio()
    with pytest.raises(notes.NoteError, match=key):
        notes.transcribe(noa, upload, client=fake)
    assert fake.calls == [] and not ModelCall.objects.exists()


def test_the_daily_caps_stop_recording(settings, noa, dan):
    settings.OPENAI_API_KEY = "sk-test"
    for _ in range(notes.CLIPS_PER_DAY):
        ModelCall.objects.create(profile=noa, provider="openai", model="m", purpose="voice_note", cost_usd=0)
    with pytest.raises(notes.NoteError, match="notes.err.cap"):
        notes.transcribe(noa, clip(), client=FakeAudio())
    settings.BOOKS_VOICE_DAILY_USD = "0.001"
    ModelCall.objects.create(profile=None, provider="openai", model="m", purpose="voice_note", cost_usd="0.002")
    with pytest.raises(notes.NoteError, match="notes.err.cap"):
        notes.transcribe(dan, clip(), client=FakeAudio())


def test_a_failed_transcription_is_logged_and_refused(settings, noa):
    settings.OPENAI_API_KEY = "sk-test"
    with pytest.raises(notes.NoteError, match="notes.err.voice_failed"):
        notes.transcribe(noa, clip(), client=FakeAudio(fail=True))
    assert ModelCall.objects.get().ok is False


# ---- the pages -------------------------------------------------------------------------

def test_the_timer_page_has_the_notes_sheet_with_my_earlier_notes(client, noa, book):
    notes.add(noa, book, "מחשבה מאתמול", page=5)
    reading.start(noa, book, 6)
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    assert "data-notes-open" in html and "מחשבה מאתמול" in html and "books/notes.js" in html
    assert '<span class="bk-notes-count" data-notes-count>1</span>' in html


def test_adding_by_fetch_answers_json_and_takes_the_running_session(client, noa, book):
    s = reading.start(noa, book, 6)
    client.force_login(noa.user)
    r = client.post(f"/books/read/notes/{book.pk}/add/", {"body": "שורה יפה", "page": "9"},
                    HTTP_ACCEPT="application/json")
    assert r.status_code == 201 and r.json()["note"]["body"] == "שורה יפה" and r.json()["note"]["page"] == 9
    assert ReadingNote.objects.get().session == s
    r = client.post(f"/books/read/notes/{book.pk}/add/", {"body": ""}, HTTP_ACCEPT="application/json")
    assert r.status_code == 400 and r.json()["error"]


def test_a_plain_post_still_works_without_script(client, noa, book):
    reading.start(noa, book, 6)
    client.force_login(noa.user)
    r = client.post(f"/books/read/notes/{book.pk}/add/", {"body": "בלי סקריפט", "next": "/books/read/"})
    assert r.status_code == 302 and r["Location"] == "/books/read/" and ReadingNote.objects.count() == 1


def test_nobody_deletes_my_note(client, noa, dan, book):
    n = notes.add(noa, book, "שלי")
    client.force_login(dan.user)
    assert client.post(f"/books/read/notes/{n.pk}/delete/", HTTP_ACCEPT="application/json").status_code == 404
    client.force_login(noa.user)
    assert client.post(f"/books/read/notes/{n.pk}/delete/", HTTP_ACCEPT="application/json").json() == {"ok": True}
    assert not ReadingNote.objects.exists()


def test_the_voice_endpoint_returns_the_words(client, settings, noa, monkeypatch):
    settings.OPENAI_API_KEY = "sk-test"
    from books import recognition
    monkeypatch.setattr(recognition, "get_client", lambda: FakeAudio("ציטוט שאהבתי"))
    client.force_login(noa.user)
    r = client.post("/books/read/voice/", {"audio": clip(), "seconds": "12"})
    assert r.status_code == 200 and r.json() == {"text": "ציטוט שאהבתי"}


def test_after_finishing_the_book_every_thought_is_there_and_open(client, noa, book):
    s = reading.start(noa, book, 1)
    notes.add(noa, book, "אחת", session=s)
    notes.add(noa, book, "שתיים", session=s)
    begun = timezone.now() - timedelta(minutes=20)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=begun)
    s.refresh_from_db()
    reading.end(noa, s, 300, finished=True, now=begun + timedelta(minutes=20))
    client.force_login(noa.user)
    html = client.get(f"/books/read/{s.pk}/").content.decode()
    assert '<details class="bk-filterbox bk-notes-read" open>' in html and "אחת" in html and "שתיים" in html


def test_the_books_page_shows_my_notes_and_never_someone_elses(client, noa, dan, book):
    notes.add(noa, book, "המחשבה של נועה")
    notes.add(dan, book, "המחשבה של דן")
    client.force_login(noa.user)
    html = client.get(f"/books/catalog/{book.pk}/").content.decode()
    assert "המחשבה של נועה" in html and "המחשבה של דן" not in html


# ---- the API ---------------------------------------------------------------------------

def test_the_api_reads_and_writes_only_my_notes(client, noa, dan, book):
    notes.add(dan, book, "של דן")
    client.force_login(noa.user)
    r = client.post("/books/api/notes/", {"entry": book.pk, "body": "דרך ה-API", "page": 3},
                    content_type="application/json")
    assert r.status_code == 201
    nid = r.json()["id"]
    rows = client.get(f"/books/api/notes/?entry={book.pk}").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [n["body"] for n in rows] == ["דרך ה-API"]
    assert client.patch(f"/books/api/notes/{nid}/", {"body": "תוקן"}, content_type="application/json").status_code == 200
    other = ReadingNote.objects.get(profile=dan).pk
    assert client.delete(f"/books/api/notes/{other}/").status_code == 404
    assert client.delete(f"/books/api/notes/{nid}/").status_code == 204


def test_the_api_runs_a_reading_session(client, noa, book):
    client.force_login(noa.user)
    r = client.post("/books/api/sessions/start/", {"entry": book.pk, "page": 10}, content_type="application/json")
    assert r.status_code == 201 and r.json()["start_page"] == 10
    sid = r.json()["id"]
    r = client.post(f"/books/api/sessions/{sid}/end/", {"end_page": 25}, content_type="application/json")
    assert r.status_code == 200 and r.json()["end_page"] == 25
    rows = client.get("/books/api/sessions/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [s["id"] for s in rows] == [sid]
