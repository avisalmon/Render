"""BK5: the hub (docs/books/backlog.md, spec BK5). Books near you, asking,
approving, meeting, handing over, lending and returning, swapping, selling,
messages and the ways to talk after approval, in-app notifications, lost
loans at twice the loan time, blocking and reporting. Refusals first."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from books import catalog, hub, storage
from books.models import (CatalogEntry, Copy, CopyTransfer, Deal, MeetingPlace, Message, Notification, Offer,
                          Profile, Report, Wish)

pytestmark = [pytest.mark.sprbk5, pytest.mark.django_db]
User = get_user_model()

HAIFA = (Decimal("32.79"), Decimal("34.99"))
HAIFA_NEAR = (Decimal("32.81"), Decimal("35.00"))  # about 2 km
TEL_AVIV = (Decimal("32.08"), Decimal("34.78"))  # about 80 km


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


def person(name, email, point=HAIFA, area="הדר"):
    u = User.objects.create_user(email.split("@")[0], email, "pw")
    p = Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name=area,
                               area_lat=point[0] if point else None, area_lng=point[1] if point else None,
                               radius_km=10)
    return p


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com", HAIFA_NEAR)


@pytest.fixture
def far(db):
    return person("רון", "ron@example.com", TEL_AVIV, area="פלורנטין")


@pytest.fixture
def entry(db):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", language="he")
    catalog.set_creators(e, ["עמוס עוז"])
    return e


def offered(owner, entry, *kinds, loan_days=30, price=None):
    c = Copy.objects.create(owner=owner, entry=entry, visibility=Copy.PUBLIC)
    for k in kinds:
        Offer.objects.create(copy=c, kind=k, loan_days=loan_days if k == "lend" else None,
                             price_amount=price if k == "sell" else None)
    return c


def login(client, p):
    client.force_login(p.user)
    return client


# ---- refusals -------------------------------------------------------------------------------

def test_signed_out_people_cannot_open_the_hub(client):
    for url in ("/books/near/", "/books/deals/", "/books/notifications/"):
        r = client.get(url)
        assert r.status_code in (302, 403) and "/books/" in r.get("Location", "/books/")


def test_nobody_reads_a_deal_they_are_not_part_of(client, noa, dan, far, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    assert login(client, far).get(f"/books/deals/{deal.pk}/").status_code == 404
    assert client.post(f"/books/deals/{deal.pk}/act/", {"action": "approve"}).status_code == 404
    assert client.get("/books/api/deals/").json() == []
    assert client.get(f"/books/api/deals/{deal.pk}/").status_code == 404
    assert client.get(f"/books/api/messages/?deal={deal.pk}").json() == []


def test_you_cannot_ask_for_your_own_book(client, noa, entry):
    c = offered(noa, entry, "lend")
    with pytest.raises(hub.DealError, match="hub.err.own"):
        hub.ask(noa, c, "lend")
    assert login(client, noa).get(f"/books/near/{c.pk}/").status_code == 302


def test_a_private_or_unoffered_book_is_not_there_to_ask_for(client, noa, dan, entry):
    private = Copy.objects.create(owner=noa, entry=entry, visibility=Copy.PRIVATE)
    shown = Copy.objects.create(owner=noa, entry=entry, visibility=Copy.PUBLIC)
    login(client, dan)
    assert client.get(f"/books/near/{private.pk}/").status_code == 404
    assert client.get(f"/books/near/{shown.pk}/").status_code == 404
    with pytest.raises(hub.DealError, match="hub.err.not_offered"):
        hub.ask(dan, shown, "lend")
    c = offered(noa, entry, "lend")
    with pytest.raises(hub.DealError, match="hub.err.not_offered"):
        hub.ask(dan, c, "sell")


def test_a_block_hides_both_sides_and_stops_asking(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    open_deal = hub.ask(dan, c, "lend")
    hub.block(noa, dan)
    open_deal.refresh_from_db()
    assert open_deal.status == Deal.CANCELLED
    assert hub.offered_copies(dan) == []
    assert login(client, dan).get(f"/books/near/{c.pk}/").status_code == 404
    with pytest.raises(hub.DealError, match="hub.err.blocked"):
        hub.ask(dan, c, "lend")
    with pytest.raises(hub.DealError):
        hub.block(noa, noa)


def test_only_the_owner_approves_and_only_in_order(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    with pytest.raises(hub.DealError, match="hub.err.not_yours"):
        hub.approve(deal, dan)
    with pytest.raises(hub.DealError, match="hub.err.wrong_state"):
        hub.confirm_handover(deal, noa)
    r = login(client, dan).post(f"/books/api/deals/{deal.pk}/approve/")
    assert r.status_code == 409 and r.json()["detail"] == "hub.err.not_yours"
    r = client.post(f"/books/deals/{deal.pk}/act/", {"action": "approve"})
    assert r.status_code == 302 and "error=hub.err.not_yours" in r["Location"]
    assert client.get(r["Location"]).status_code == 200


def test_after_the_pilot_the_free_plan_answers_but_does_not_ask(settings, noa, dan, entry):
    settings.BOOKS_PILOT_EVERYONE_ASKS = False
    c = offered(noa, entry, "lend")
    with pytest.raises(hub.DealError, match="hub.err.tier"):
        hub.ask(dan, c, "lend")
    dan.tier = Profile.PLUS
    dan.save()
    assert hub.ask(dan, c, "lend").status == Deal.REQUESTED


def test_no_way_to_talk_shows_before_approval(noa, dan, entry):
    noa.phone = "050-1234567"
    noa.save()
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    with pytest.raises(hub.DealError, match="hub.err.wrong_state"):
        hub.set_shares(deal, noa, ["phone"])
    assert hub.contact_for(deal, dan) == {}


def test_an_exchange_names_one_of_your_own_books_or_none_yet(noa, dan, entry):
    # Avi, 2026-10-23: the book in return may be settled in the conversation; a named one must be yours.
    c = offered(noa, entry, "exchange")
    assert hub.ask(dan, c, "exchange").swap_copy is None
    Deal.objects.all().delete()
    theirs = Copy.objects.create(owner=noa, entry=entry)
    with pytest.raises(hub.DealError, match="hub.err.swap_copy"):
        hub.ask(dan, c, "exchange", swap_copy=theirs)


def test_reports_name_something_and_a_deal_only_if_yours(client, noa, dan, far, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    login(client, far)
    client.post("/books/report/", {"reason": "x", "deal": deal.pk})
    assert Report.objects.count() == 0
    client.post("/books/report/", {"reason": "", "copy": c.pk})
    assert Report.objects.count() == 0
    r = client.post("/books/report/", {"reason": "תמונה לא מתאימה", "copy": c.pk, "next": "https://evil.example/"})
    assert Report.objects.count() == 1 and r["Location"].startswith("/books/")


def test_the_meeting_places_are_written_by_staff_only(client, noa):
    login(client, noa)
    assert client.post("/books/api/meeting-places/", {"name": "קפה"}).status_code == 403
    assert client.get("/books/api/meeting-places/").status_code == 200


# ---- near you ----------------------------------------------------------------------------------

def test_near_lists_offered_books_inside_the_radius_nearest_first(client, noa, dan, far, entry):
    other = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="Jane Eyre", language="en")
    near_copy = offered(dan, entry, "lend")
    far_copy = offered(far, other, "sell", price=Decimal("30"))
    rows = hub.offered_copies(noa)
    assert [c.pk for c, _ in rows] == [near_copy.pk]
    assert 1 <= rows[0][1] <= 4
    noa.radius_km = 100
    noa.save()
    assert [c.pk for c, _ in hub.offered_copies(noa)] == [near_copy.pk, far_copy.pk]
    assert [c.pk for c, _ in hub.offered_copies(noa, kind="sell")] == [far_copy.pk]
    assert [c.pk for c, _ in hub.offered_copies(noa, language="en")] == [far_copy.pk]
    assert [c.pk for c, _ in hub.offered_copies(noa, q="מיכאל")] == [near_copy.pk]
    page = login(client, noa).get("/books/near/")
    assert page.status_code == 200 and "מיכאל שלי" in page.content.decode()
    api = client.get("/books/api/near/").json()
    assert {row["copy"] for row in api} == {near_copy.pk, far_copy.pk}
    assert all("lat" not in row and "area_lat" not in row for row in api)


def test_without_a_point_the_same_named_area_still_counts(noa, entry):
    a = person("א", "a@example.com", None, area="הדר")
    b = person("ב", "b@example.com", None, area="נווה שאנן")
    c = offered(a, entry, "lend")
    assert [(x.pk, km) for x, km in hub.offered_copies(noa)] == [(c.pk, None)]  # a has no point: area name
    noa.area_name = "כרמל"
    noa.save()
    assert hub.offered_copies(noa) == []
    assert hub.offered_copies(b) == []


def test_a_new_area_name_is_geocoded_and_rounded(monkeypatch, noa):
    class R:
        status_code = 200

        def json(self):
            return [{"lat": "32.123456", "lon": "34.987654"}]

    calls = []
    monkeypatch.setattr(hub.requests, "get", lambda *a, **kw: calls.append(kw["params"]["q"]) or R())
    noa.area_name = "כרמל"
    noa.save()
    hub.area_changed(noa)
    noa.refresh_from_db()
    assert calls == ["כרמל"]
    assert noa.area_lat == Decimal("32.12") and noa.area_lng == Decimal("34.99")


def test_changing_the_area_in_settings_geocodes_it(client, monkeypatch, noa):
    seen = []
    monkeypatch.setattr(hub, "area_changed", lambda p: seen.append(p.area_name))
    login(client, noa)
    data = {"display_name": noa.display_name, "language": "he", "area_name": "כרמל", "radius_km": 10,
            "phone": "", "theme": "light", "palette": "lamplit", "shelf_view": "lamp"}
    client.post("/books/settings/", data)
    assert seen == ["כרמל"]
    client.post("/books/settings/", data)
    assert seen == ["כרמל"]  # unchanged: no new lookup


# ---- a loan, start to finish ---------------------------------------------------------------------

def test_a_loan_from_asking_to_returning(client, noa, dan, far, entry):
    far.radius_km = 100
    far.save()
    c = offered(noa, entry, "lend", loan_days=14)
    login(client, dan)
    r = client.post(f"/books/near/{c.pk}/", {"kind": "lend", "message": "אשמח מאוד"})
    deal = Deal.objects.get()
    assert r["Location"] == f"/books/deals/{deal.pk}/"
    assert deal.loan_days == 14 and deal.messages.count() == 1
    assert Notification.objects.filter(profile=noa, kind="deal.requested").count() == 1
    second = hub.ask(far, c, "lend")

    login(client, noa)
    assert "1" in client.get("/books/near/").content.decode()  # the bell shows a count
    client.post(f"/books/deals/{deal.pk}/act/", {"action": "approve"})
    deal.refresh_from_db()
    second.refresh_from_db()
    assert deal.status == Deal.APPROVED and second.status == Deal.DECLINED

    place = MeetingPlace.objects.create(name="הספרייה העירונית", area_name="הדר")
    client.post(f"/books/deals/{deal.pk}/act/", {"action": "meeting", "place": place.pk, "meeting_note": "בחמש"})
    client.post(f"/books/deals/{deal.pk}/act/", {"action": "handover"})
    deal.refresh_from_db()
    assert deal.status == Deal.APPROVED and deal.owner_confirmed_handover_at and deal.meeting_place == place
    assert "deal.waiting_other" not in client.get(f"/books/deals/{deal.pk}/").content.decode()

    hub.confirm_handover(deal, dan)
    deal.refresh_from_db()
    c.refresh_from_db()
    assert deal.status == Deal.HANDED_OVER and c.status == Copy.ON_LOAN_OUT
    assert deal.due_date == timezone.now().date() + timedelta(days=14)
    assert hub.offered_copies(far) == []  # a lent book is not on offer

    hub.mark_returned(deal, dan)
    hub.confirm_returned(deal, noa)
    deal.refresh_from_db()
    c.refresh_from_db()
    assert deal.status == Deal.RETURNED and not deal.returned_late and c.status == Copy.WITH_OWNER
    rep = hub.reputation(dan)
    assert rep["reliability"] == 100 and rep["ended"] == 1
    assert hub.reputation(noa)["lent"] == 1


def test_every_deal_page_renders_for_both_sides_in_every_state(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend", "שלום")
    for step in (None, lambda: hub.approve(deal, noa), lambda: hub.confirm_handover(deal, noa),
                 lambda: hub.confirm_handover(deal, dan), lambda: hub.mark_returned(deal, dan),
                 lambda: hub.confirm_returned(deal, noa)):
        if step:
            step()
        for p in (noa, dan):
            r = login(client, p).get(f"/books/deals/{deal.pk}/")
            assert r.status_code == 200, deal.status
        assert login(client, p).get("/books/deals/").status_code == 200
    for lang in ("he", "en"):
        client.post(f"/books/lang/{lang}/", {"next": "/books/"})
        assert client.get("/books/notifications/").status_code == 200


def test_ways_to_talk_open_only_what_each_side_chose(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    hub.approve(deal, noa)
    login(client, noa)
    client.post(f"/books/deals/{deal.pk}/act/", {"action": "share", "ways": ["phone", "whatsapp"],
                                                 "phone": "050-1234567"})
    noa.refresh_from_db()
    deal.refresh_from_db()
    assert noa.phone == "050-1234567"
    contact = hub.contact_for(deal, dan)
    assert contact == {"phone": "050-1234567", "whatsapp": "https://wa.me/972501234567"}
    assert hub.contact_for(deal, noa) == {}  # dan shared nothing
    assert Notification.objects.filter(profile=dan, kind="deal.shared").exists()
    page = login(client, dan).get(f"/books/deals/{deal.pk}/").content.decode()
    assert "wa.me/972501234567" in page and "noa@example.com" not in page
    hub.set_shares(deal, noa, ["email"])
    assert hub.contact_for(deal, dan) == {"email": "noa@example.com"}


def test_messages_tell_the_other_side_once_until_read(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    hub.send_message(deal, dan, "שאלה")
    hub.send_message(deal, dan, "ועוד שאלה")
    assert Notification.objects.filter(profile=noa, kind="deal.message").count() == 1
    with pytest.raises(hub.DealError, match="hub.err.empty"):
        hub.send_message(deal, dan, "   ")
    login(client, noa).get(f"/books/deals/{deal.pk}/")
    assert not Message.objects.filter(deal=deal, read_at__isnull=True).exists()
    assert hub.unread_count(noa) == 0
    r = client.post("/books/api/messages/", {"deal": deal.pk, "body": "תשובה"})
    assert r.status_code == 201 and Message.objects.filter(sender=noa).count() == 1


# ---- swap and sale -------------------------------------------------------------------------------

def test_a_swap_moves_both_books_and_records_it(noa, dan, entry):
    c = offered(noa, entry, "exchange")
    mine = Copy.objects.create(owner=dan, entry=entry)
    Wish.objects.create(profile=dan, entry=entry)
    deal = hub.ask(dan, c, "exchange", swap_copy=mine)
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    hub.confirm_handover(deal, dan)
    c.refresh_from_db()
    mine.refresh_from_db()
    deal.refresh_from_db()
    assert deal.status == Deal.COMPLETED
    assert c.owner == dan and mine.owner == noa
    assert c.visibility == Copy.PRIVATE and not c.offers.exists() and c.added_via == "received"
    assert CopyTransfer.objects.filter(deal=deal).count() == 2
    assert not Wish.objects.filter(profile=dan, entry=entry).exists()
    assert hub.reputation(noa)["passed_on"] == 1 and hub.reputation(dan)["received"] == 1


def test_a_sale_passes_the_book_on_through_the_api(client, noa, dan, entry):
    c = offered(noa, entry, "sell", price=Decimal("40"))
    login(client, dan)
    r = client.post("/books/api/deals/", {"copy": c.pk, "kind": "sell", "message": "מתי נוח?"})
    assert r.status_code == 201 and r.json()["price_amount"] == "40.00"
    pk = r.json()["id"]
    assert client.post("/books/api/deals/", {"copy": c.pk, "kind": "sell"}).json()["detail"] == "hub.err.already"
    login(client, noa).post(f"/books/api/deals/{pk}/approve/")
    client.post(f"/books/api/deals/{pk}/handover/")
    r = login(client, dan).post(f"/books/api/deals/{pk}/handover/")
    assert r.json()["status"] == Deal.COMPLETED
    c.refresh_from_db()
    assert c.owner == dan
    assert client.get("/books/api/transfers/").json()


def test_either_side_may_cancel_before_the_handover(client, noa, dan, entry):
    c = offered(noa, entry, "lend")
    deal = hub.ask(dan, c, "lend")
    r = login(client, dan).delete(f"/books/api/deals/{deal.pk}/")
    assert r.status_code == 204
    deal.refresh_from_db()
    assert deal.status == Deal.CANCELLED and Deal.objects.filter(pk=deal.pk).exists()
    assert login(client, dan).get(f"/books/near/{c.pk}/").status_code == 200  # may ask again


# ---- late and lost ---------------------------------------------------------------------------------

def _lent(noa, dan, entry, days=30):
    c = offered(noa, entry, "lend", loan_days=days)
    deal = hub.ask(dan, c, "lend")
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    hub.confirm_handover(deal, dan)
    deal.refresh_from_db()
    return c, deal


def test_reminders_come_once_and_a_loan_is_lost_at_twice_its_time(noa, dan, entry):
    c, deal = _lent(noa, dan, entry, days=30)
    today = timezone.now().date()
    hub.sweep(today + timedelta(days=28))
    hub.sweep(today + timedelta(days=28))
    assert Notification.objects.filter(profile=dan, kind="deal.due_soon").count() == 1
    hub.sweep(today + timedelta(days=31))
    assert Notification.objects.filter(profile=dan, kind="deal.overdue").count() == 1
    assert Notification.objects.filter(profile=noa, kind="deal.overdue_owner").count() == 1
    hub.sweep(today + timedelta(days=59))
    deal.refresh_from_db()
    assert deal.status == Deal.HANDED_OVER
    hub.sweep(today + timedelta(days=60))
    deal.refresh_from_db()
    c.refresh_from_db()
    assert deal.status == Deal.LOST and c.status == Copy.LOST
    rep = hub.reputation(dan)
    assert rep["lost"] == 1 and rep["reliability"] == 0
    # Not blocked: the borrower may still ask for other books.
    other = offered(noa, CatalogEntry.objects.create(collection_type=catalog.book_type(), title="אחר"), "lend")
    assert hub.ask(dan, other, "lend").status == Deal.REQUESTED


def test_a_lost_book_that_comes_back_counts_as_late(noa, dan, entry):
    c, deal = _lent(noa, dan, entry, days=1)
    Deal.objects.filter(pk=deal.pk).update(due_date=timezone.now().date() - timedelta(days=5))
    deal.refresh_from_db()
    hub.sweep(timezone.now().date() + timedelta(days=3))
    deal.refresh_from_db()
    assert deal.status == Deal.LOST
    hub.confirm_returned(deal, noa)
    deal.refresh_from_db()
    c.refresh_from_db()
    assert deal.status == Deal.RETURNED and deal.returned_late and c.status == Copy.WITH_OWNER
    rep = hub.reputation(dan)
    assert rep["lost"] == 0 and rep["borrowed_late"] == 1 and rep["reliability"] == 0


def test_a_dispute_stays_between_the_two_and_reports_reach_the_desk(client, noa, dan, entry):
    c, deal = _lent(noa, dan, entry)
    hub.dispute(deal, noa, "הספר חזר קרוע")
    deal.refresh_from_db()
    assert deal.status == Deal.DISPUTED
    staff = person("אוצר", "cur@example.com")
    staff.user.is_staff = True
    staff.user.save()
    Report.objects.create(reporter=noa, profile=dan, reason="לא עונה")
    page = login(client, staff).get("/books/curate/").content.decode()
    assert "הספר חזר קרוע" not in page and "לא עונה" in page
    assert Notification.objects.filter(profile=dan, kind="deal.disputed").exists()
    deal_page = login(client, dan).get(f"/books/deals/{deal.pk}/").content.decode()
    assert "הספר חזר קרוע" in deal_page and "לא אחראית" in deal_page
    login(client, staff)
    client.post("/books/curate/act/", {"action": "report_handled", "report": Report.objects.get().pk})
    assert Report.objects.get().status == Report.HANDLED


# ---- wishes ---------------------------------------------------------------------------------------

def test_a_wished_book_offered_nearby_tells_the_wisher_once(django_capture_on_commit_callbacks, noa, dan, far,
                                                             entry):
    Wish.objects.create(profile=dan, entry=entry)
    Wish.objects.create(profile=far, entry=entry)
    with django_capture_on_commit_callbacks(execute=True):
        c = offered(noa, entry, "lend")
    assert Notification.objects.filter(profile=dan, kind="wish.available", copy=c).count() == 1
    assert not Notification.objects.filter(profile=far).exists()  # 80 km away
    hub.alert_wishers(c.offers.get())
    assert Notification.objects.filter(profile=dan, kind="wish.available").count() == 1
    page = login(Client(), dan).get("/books/notifications/")
    assert "מיכאל שלי" in page.content.decode()
    assert hub.unread_count(dan) == 0


def test_the_unread_count_is_json(client, noa, dan, entry):
    hub.ask(dan, offered(noa, entry, "lend"), "lend")
    assert login(client, noa).get("/books/notifications/unread/").json() == {"unread": 1}
    assert client.post("/books/api/notifications/read-all/").json() == {"read": 1}


# ---- colours made in code -------------------------------------------------------------------------

def _lum(hex_):
    def ch(v):
        v = int(v, 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    h = hex_.lstrip("#")
    r, g, b = (ch(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_every_spine_colour_pair_is_readable_as_body_text():
    """The palette lives in Python, outside the CSS tokens the guards check, so
    each pair is checked here, not only the ones a screen happens to show."""
    from books.shelf import SPINE_PALETTE

    for bg, ink in SPINE_PALETTE:
        hi, lo = sorted((_lum(bg), _lum(ink)), reverse=True)
        assert (hi + 0.05) / (lo + 0.05) >= 4.5, (bg, ink)
