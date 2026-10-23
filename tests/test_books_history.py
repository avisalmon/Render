"""Avi, 2026-10-23: the book's details from the reading screen; my history
on a timeline from home; a ping and fireworks when the five minutes that
earn the day are reached; and a reading screen left open by mistake must
not keep counting."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from books import catalog, history, notes, reading
from books.models import CatalogEntry, Profile, ReadingCheckin, ReadingLog, ReadingSession

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""


def person(name):
    u = User.objects.create_user(name, f"{name}@example.com", "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True)


@pytest.fixture
def noa(db):
    return person("noa")


@pytest.fixture
def book(db):
    return CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")


def ago(session, **kw):
    """Move a sitting back in time, as if it started that long ago."""
    t = timezone.now() - timedelta(**kw)
    ReadingSession.objects.filter(pk=session.pk).update(started_at=t, last_beat_at=timezone.now())  # alive
    session.refresh_from_db()
    return session


# ---- a screen left open must not keep counting ------------------------------------------

def test_a_screen_that_went_silent_stops_one_beat_after_its_last_heartbeat(noa, book):
    s = ago(reading.start(noa, book, 1), minutes=60)
    now = timezone.now()
    ReadingSession.objects.filter(pk=s.pk).update(last_beat_at=now - timedelta(minutes=50))
    s.refresh_from_db()
    assert reading.settle(s, now)
    # ten minutes until the last beat, plus one beat of grace; not the hour
    assert reading.elapsed(s, now) == 10 * 60 + reading.BEAT_SECONDS
    assert not reading.settle(s, now)  # already stopped


def test_a_live_screen_is_not_stopped(noa, book):
    s = ago(reading.start(noa, book, 1), minutes=30)
    reading.heartbeat(noa, s)
    assert not reading.settle(s)
    assert s.paused_at is None


def test_coming_back_after_a_dead_battery_finds_the_real_time_not_a_day(client, noa, book):
    s = ago(reading.start(noa, book, 1), hours=20)
    ReadingSession.objects.filter(pk=s.pk).update(last_beat_at=s.started_at + timedelta(minutes=12))
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    s.refresh_from_db()
    assert s.paused_at is None  # running again from here
    assert abs(reading.elapsed(s) - (12 * 60 + reading.BEAT_SECONDS)) <= 2
    assert f'data-elapsed="{reading.elapsed(s)}"' in html or 'data-elapsed="' in html


def test_the_heartbeat_tells_a_frozen_screen_its_clock_was_stopped(client, noa, book):
    s = ago(reading.start(noa, book, 1), minutes=40)
    ReadingSession.objects.filter(pk=s.pk).update(last_beat_at=timezone.now() - timedelta(minutes=30))
    client.force_login(noa.user)
    r = client.post(f"/books/read/{s.pk}/tick/").json()
    assert r["paused"] is True and r["seconds"] == 10 * 60 + reading.BEAT_SECONDS


def test_trim_only_takes_time_away_and_stops_the_clock(client, noa, book):
    s = ago(reading.start(noa, book, 1), minutes=30)
    client.force_login(noa.user)
    assert client.post(f"/books/read/{s.pk}/trim/", {"seconds": "600"}).json()["elapsed"] == 600
    s.refresh_from_db()
    assert s.paused_at is not None and s.seconds == 600
    client.post(f"/books/read/{s.pk}/trim/", {"seconds": "5000"})
    s.refresh_from_db()
    assert reading.elapsed(s) == 600  # never adds
    reading.resume(noa, s)
    assert reading.elapsed(s) == 600  # the trimmed time stays gone after going on


def test_trimming_a_day_that_only_this_sitting_earned_takes_the_day_back(noa, book):
    s = ago(reading.start(noa, book, 1), minutes=20)
    reading.heartbeat(noa, s)
    assert ReadingCheckin.objects.filter(profile=noa).exists()
    reading.trim(noa, s, 60)
    assert not ReadingCheckin.objects.filter(profile=noa).exists()


def test_trimming_keeps_a_day_earned_by_an_earlier_sitting(noa, book):
    first = ago(reading.start(noa, book, 1), minutes=30)
    reading.end(noa, first, 10)
    s = reading.start(noa, book, 10)
    ReadingSession.objects.filter(pk=s.pk).update(started_at=timezone.now() - timedelta(minutes=5))
    s.refresh_from_db()
    reading.trim(noa, s, 0)
    assert ReadingCheckin.objects.filter(profile=noa).exists()


# ---- the five minutes that earn the day ---------------------------------------------------

def test_the_reading_screen_knows_how_far_the_day_is_from_its_five_minutes(client, noa, book):
    earlier = ago(reading.start(noa, book, 1), minutes=3)
    reading.end(noa, earlier, 5)
    reading.start(noa, book, 5)
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    assert 'data-day-before="180"' in html and 'data-goal="300"' in html
    assert "data-earned" in html and "עוד יום ברצף!" in html and "books/sky.js" in html
    assert 'name="celebrated"' in html


def test_the_streak_moment_on_home_comes_when_this_sitting_earned_the_day(client, noa, book):
    s = ago(reading.start(noa, book, 1), minutes=8)
    reading.heartbeat(noa, s)  # the heartbeat already counted the day
    client.force_login(noa.user)
    r = client.post(f"/books/read/{s.pk}/end/", {"end_page": "9"})
    assert r["Location"].endswith("?streak=1")


def test_no_second_moment_when_the_reading_screen_already_celebrated(client, noa, book):
    s = ago(reading.start(noa, book, 1), minutes=8)
    client.force_login(noa.user)
    r = client.post(f"/books/read/{s.pk}/end/", {"end_page": "9", "celebrated": "1"})
    assert "streak" not in r["Location"]


# ---- the book's details, and my history ---------------------------------------------------

def test_the_reading_screen_has_a_button_to_the_book_s_page(client, noa, book):
    reading.start(noa, book, 1)
    client.force_login(noa.user)
    html = client.get("/books/read/").content.decode()
    assert f'href="/books/catalog/{book.pk}/" data-book-details' in html and "פרטי הספר" in html


def test_my_history_puts_every_book_on_a_timeline(client, noa, book):
    other = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="סיפור על אהבה וחושך")
    marked = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="ספר שסימנתי")
    s1 = ago(reading.start(noa, book, 10), minutes=20)
    reading.end(noa, s1, 40, finished=True)
    notes.add(noa, book, "פתיחה חזקה", session=s1, page=12)
    reading.start(noa, other, 1)
    ReadingLog.objects.create(profile=noa, entry=marked, status=ReadingLog.READ,
                              finished_on=timezone.now().date() - timedelta(days=60))
    rows = history.books_read(noa)
    assert [r["entry"].title for r in rows] == ["סיפור על אהבה וחושך", "מיכאל שלי", "ספר שסימנתי"]
    done = rows[1]
    assert done["finished"] and done["sittings"] == 1 and done["pages"] == 30 and done["notes"] == 1
    assert done["minutes"] == 20 and done["pace"] == 1.5
    assert rows[0]["now"] and rows[2].get("marked")
    page = history.timeline(noa)
    assert page["total_books"] == 3 and page["total_finished"] == 2 and len(page["months"]) == 2

    client.force_login(noa.user)
    html = client.get("/books/history/").content.decode()
    assert "ההיסטוריה שלי" in html and f'href="/books/catalog/{book.pk}/"' in html and "1.5 עמודים לדקה" in html
    entry_html = client.get(f"/books/catalog/{book.pk}/").content.decode()
    assert "הישיבות שלי עם הספר" in entry_html and "20 דקות · עמודים 10 עד 40" in entry_html


def test_home_has_my_history(client, noa):
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert 'href="/books/history/"' in html and "ההיסטוריה שלי" in html


def test_history_is_mine_alone(client, noa, book):
    dan = person("dan")
    reading.end(noa, ago(reading.start(noa, book, 1), minutes=10), 5)
    client.force_login(dan.user)
    assert "מיכאל שלי" not in client.get("/books/history/").content.decode()
