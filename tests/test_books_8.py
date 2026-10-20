"""BK8: play (docs/books/backlog.md, spec BK8). The streak and freezes,
points as a ledger with caps and the anti-farming rules, badges, circle
leaderboards with opt-out, the year in books. Refusals and the "nothing for
farming" cases first."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from books import catalog, circles, community, hub, play, shelf, storage
from books.models import (CatalogEntry, Copy, Deal, Notification, Offer, PointEvent, Profile, ProfileBadge,
                          ReadingCheckin, StreakFreeze)

pytestmark = [pytest.mark.sprbk8, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.BOOKS_PILOT_EVERYONE_ASKS = True
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    from django.core.cache import cache

    cache.clear()
    yield
    storage.reset_for_tests()


def person(name, email, staff=False, public=False):
    u = User.objects.create_user(email.split("@")[0], email, "pw", is_staff=staff)
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name="הדר",
                                  show_points_public=public)


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com", public=True)


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com", public=True)


@pytest.fixture
def entry(db):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", language="he")
    catalog.set_creators(e, ["עמוס עוז"])
    return e


def book(title):
    return CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)


def login(client, p):
    client.force_login(p.user)
    return client


def loan(owner, borrower, copy, return_it=True):
    copy.offers.all().delete()
    copy.visibility = Copy.PUBLIC
    copy.save()
    Offer.objects.create(copy=copy, kind="lend", loan_days=30)
    deal = hub.ask(borrower, copy, "lend")
    hub.approve(deal, owner)
    hub.confirm_handover(deal, owner)
    hub.confirm_handover(deal, borrower)
    if return_it:
        hub.mark_returned(deal, borrower)
        hub.confirm_returned(deal, owner)
    deal.refresh_from_db()
    copy.refresh_from_db()
    return deal


def swap(a, b, a_copy, b_copy):
    a_copy.visibility = Copy.PUBLIC
    a_copy.save()
    a_copy.offers.all().delete()
    Offer.objects.create(copy=a_copy, kind="exchange")
    deal = hub.ask(b, a_copy, "exchange", swap_copy=b_copy)
    hub.approve(deal, a)
    hub.confirm_handover(deal, a)
    hub.confirm_handover(deal, b)
    a_copy.refresh_from_db()
    b_copy.refresh_from_db()
    return deal


# ---- nothing for farming, nothing unconfirmed ----------------------------------------------------

def test_a_request_or_one_sided_confirmation_earns_nothing(noa, dan, entry):
    c = Copy.objects.create(owner=noa, entry=entry, visibility=Copy.PUBLIC)
    Offer.objects.create(copy=c, kind="lend", loan_days=30)
    deal = hub.ask(dan, c, "lend")
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    assert play.total(noa) == 0 and play.total(dan) == 0
    hub.confirm_handover(deal, dan)
    assert play.total(noa) == 10 and play.total(dan) == 10


def test_lending_the_same_book_to_the_same_person_again_pays_nothing(noa, dan, entry):
    c = Copy.objects.create(owner=noa, entry=entry)
    loan(noa, dan, c)
    first = (play.total(noa), play.total(dan))
    assert first == (10, 20)  # owner: handover; borrower: handover + on time
    loan(noa, dan, c)
    loan(noa, dan, c)
    assert (play.total(noa), play.total(dan)) == first


def test_passing_one_book_back_and_forth_earns_nothing_the_second_time(noa, dan, entry):
    a_copy = Copy.objects.create(owner=noa, entry=entry)
    b_copy = Copy.objects.create(owner=dan, entry=book("אחר"))
    swap(noa, dan, a_copy, b_copy)
    after_first = (play.total(noa), play.total(dan))
    assert after_first == (10, 10)
    # Now dan holds a_copy and noa holds b_copy: swap them straight back.
    swap(dan, noa, a_copy, b_copy)
    assert (play.total(noa), play.total(dan)) == after_first


def test_one_deal_pays_once_even_if_asked_twice(noa, dan, entry):
    deal = loan(noa, dan, Copy.objects.create(owner=noa, entry=entry), return_it=False)
    play.deal_handed_over(deal)
    play.deal_handed_over(deal)
    assert PointEvent.objects.filter(deal=deal, kind="handover_confirmed").count() == 2  # one each


def test_a_late_return_earns_no_return_points(noa, dan, entry):
    deal = loan(noa, dan, Copy.objects.create(owner=noa, entry=entry), return_it=False)
    Deal.objects.filter(pk=deal.pk).update(due_date=play.today() - timedelta(days=3))
    deal.refresh_from_db()
    hub.mark_returned(deal, dan)
    hub.confirm_returned(deal, noa)
    assert not PointEvent.objects.filter(profile=dan, kind="returned_on_time").exists()


def test_rewriting_a_review_or_report_or_rescanning_earns_once(noa, entry):
    community.set_review(noa, entry, 4, "טוב")
    community.set_review(noa, entry, 5, "מעולה")  # an update, not a new review
    community.delete_review(noa, entry)
    assert play.total(noa) == 0  # deleted: reversed
    community.set_review(noa, entry, 5, "שוב")
    assert play.total(noa) == 0  # once per book, ever
    th = community.start_thread(noa, "report", "דוח", "טקסט", entry=entry)
    assert play.total(noa) == 10
    community.delete_post(noa, th.posts.first())
    community.start_thread(noa, "report", "דוח שוב", "טקסט", entry=entry)
    assert play.total(noa) == 0
    play.book_confirmed(noa, entry)
    play.book_confirmed(noa, entry)
    assert play.total(noa) == 1


def test_daily_caps_hold(noa, monkeypatch):
    monkeypatch.setitem(play.DAILY_CAP, "catalog_confirm", 3)
    for i in range(6):
        play.book_confirmed(noa, book(f"ספר {i}"))
    assert play.total(noa) == 3


def test_check_ins_earn_no_points_and_others_never_see_hidden_points(client, noa, dan):
    play.checkin(noa)
    assert play.total(noa) == 0 and play.streak(noa) == 1
    hidden = person("רון", "ron@example.com", public=False)
    club = circles.create(noa, "מועדון")
    for p in (dan, hidden):
        circles.join(p, club, club.join_code)
    board = play.leaderboard(club, dan)
    assert [r["profile"] for r in board["rows"]] == [dan, noa] or [r["profile"] for r in board["rows"]] == [noa, dan]
    assert hidden not in [r["profile"] for r in board["rows"]] and board["hidden"] == 1
    assert hidden in [r["profile"] for r in play.leaderboard(club, hidden)["rows"]]  # always see yourself
    hidden.profile_public = True
    hidden.save()
    page = login(client, dan).get(f"/books/people/{hidden.pk}/").content.decode()
    assert "ימים ברצף" not in page


def test_only_staff_reverse_and_nobody_creates_points_through_the_api(client, noa, dan, entry):
    community.set_review(noa, entry, 4)
    event = PointEvent.objects.get()
    login(client, dan)
    assert client.get("/books/api/points/").json() == []
    assert client.post(f"/books/api/points/{event.pk}/reverse/").status_code == 404
    login(client, noa)
    assert client.post(f"/books/api/points/{event.pk}/reverse/").status_code == 403
    assert client.post("/books/api/points/", {"kind": "review", "points": 1000}).status_code == 405
    staff = person("אבי", "avi@example.com", staff=True)
    login(client, staff)
    assert client.post(f"/books/api/points/{event.pk}/reverse/", {"note": "test"}).json()["reversed_at"]
    assert play.total(noa) == 0


def test_a_circle_board_is_for_its_members_only(client, noa, dan):
    club = circles.create(noa, "מועדון")
    login(client, dan)
    assert client.get(f"/books/api/play/board/?circle={club.pk}").status_code == 404


# ---- the streak ---------------------------------------------------------------------------------

def test_a_streak_counts_days_in_a_row_and_survives_until_tomorrow(noa):
    today = play.today()
    for i in range(3, 0, -1):
        play.checkin(noa, day=today - timedelta(days=i))
    assert play.streak(noa, today) == 3  # today not in yet, still alive
    play.checkin(noa, day=today)
    assert play.streak(noa, today) == 4
    assert play.streak(noa, today + timedelta(days=2)) == 0


def test_a_week_earns_a_freeze_and_a_missed_day_spends_it(noa):
    start = play.today() - timedelta(days=20)
    for i in range(7):
        play.checkin(noa, day=start + timedelta(days=i))
    assert play.freezes_held(noa) == 1
    assert ProfileBadge.objects.filter(profile=noa, badge__key="streak_7").exists()
    # Miss one day, come back: the freeze covers it, the streak goes on.
    back = start + timedelta(days=8)
    play.checkin(noa, day=back)
    assert play.freezes_held(noa) == 0
    assert StreakFreeze.objects.get().used_on == start + timedelta(days=7)
    assert play.streak(noa, back) == 9
    # Miss two days with no freeze: the streak starts again.
    later = back + timedelta(days=3)
    play.checkin(noa, day=later)
    assert play.streak(noa, later) == 1
    assert play.longest_streak(noa) == 9


def test_at_most_two_freezes_are_held(noa):
    start = play.today() - timedelta(days=40)
    for i in range(28):
        play.checkin(noa, day=start + timedelta(days=i))
    assert play.freezes_held(noa) == 2


def test_the_manual_check_in_is_retired_for_reading_sessions(client, noa):
    """Avi, 2026-10-20: a streak day is earned by five minutes of reading in a
    session, not by tapping "I read today"."""
    login(client, noa)
    page = client.get("/books/").content.decode()
    assert "קראתי היום" not in page and 'href="/books/read/"' in page
    r = client.post("/books/play/checkin/", {"next": "/books/"})
    assert r["Location"] == "/books/read/" and not ReadingCheckin.objects.filter(profile=noa).exists()
    assert client.post("/books/api/checkins/", {"minutes": 25}).status_code == 410
    assert client.get("/books/api/checkins/summary/").json()["streak"] == 0


# ---- badges, board, year ---------------------------------------------------------------------------

def test_badges_arrive_once_with_a_notification(noa, dan, entry):
    c = Copy.objects.create(owner=noa, entry=entry)
    loan(noa, dan, c)
    keys = set(ProfileBadge.objects.filter(profile=noa).values_list("badge__key", flat=True))
    assert {"first_lend"} <= keys
    play.check_badges(noa)
    assert ProfileBadge.objects.filter(profile=noa, badge__key="first_lend").count() == 1
    n = Notification.objects.filter(profile=noa, kind="badge.earned").first()
    assert n is not None and n.badge.key in keys


def test_the_play_page_board_and_year(client, noa, dan, entry):
    club = circles.create(noa, "מועדון הקריאה")
    circles.join(dan, club, club.join_code)
    c = Copy.objects.create(owner=noa, entry=entry)
    loan(noa, dan, c)
    community.log_reading(dan, entry, "read")
    play.checkin(dan)
    login(client, dan)
    page = client.get("/books/play/").content.decode()
    assert "מועדון הקריאה" in page and "20 נקודות" in page and "ספר עבר ידיים" in page
    assert "20 נקודות" in client.get(f"/books/circles/{club.pk}/").content.decode()
    year = client.get("/books/year/").content.decode()
    assert "מיכאל שלי" in year
    api = client.get(f"/books/api/play/board/?circle={club.pk}").json()
    assert [r["display_name"] for r in api["rows"]] == ["דן", "נועה"]
    assert client.get("/books/api/play/year/").json()["borrowed"] == 1
    assert client.get("/books/year/1999/").status_code == 404
    # The bell links to the play page for a badge (noa lent: "first lend").
    page = login(client, noa).get("/books/notifications/").content.decode()
    assert 'href="/books/play/"' in page and "הרווחת תג" in page


def test_confirming_a_scanned_book_pays_a_point_once(noa, entry, monkeypatch):
    from books.models import ScanItem, ShelfScan

    scan = ShelfScan.objects.create(owner=noa, status=ShelfScan.REVIEW, photo="x.jpg", books_found=1)
    item = ScanItem.objects.create(scan=scan, position=0, raw_title="מיכאל שלי")
    shelf.accept(item, entry, "private", [], "")
    shelf.accept(item, entry, "private", [], "סלון")  # editing it again pays nothing
    assert play.total(noa) == 1
