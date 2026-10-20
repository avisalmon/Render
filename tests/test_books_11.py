"""BK11: tiers with payment blocked (Avi, 2026-10-20). One function decides,
the free tier is real, the code "helpavi" opens Plus for 90 days, once per
person, and staff are never locked out. Refusals first."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from books import catalog, circles, community, shelf, storage, tiers
from books.models import CatalogEntry, Copy, Coupon, Offer, Profile, Subscription, Thread

pytestmark = [pytest.mark.sprbk11, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.BOOKS_PILOT_EVERYONE_ASKS = False  # the tiers themselves, closed
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


def person(name, email, staff=False):
    u = User.objects.create_user(email.split("@")[0], email, "pw", is_staff=staff)
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name="הדר")


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com")


def offered_copy(owner):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי")
    c = Copy.objects.create(owner=owner, entry=e, visibility=Copy.PUBLIC)
    Offer.objects.create(copy=c, kind="lend", loan_days=30)
    return c


def login(client, p):
    client.force_login(p.user)
    return client


# ---- the free tier is real --------------------------------------------------------------------

def test_the_code_helpavi_exists_from_the_migration():
    c = Coupon.objects.get(code="helpavi")
    assert c.tier == Profile.PLUS and c.days == 90 and c.is_active


def test_a_free_person_cannot_start_a_request_post_or_create_a_circle(client, noa, dan):
    from books import hub

    c = offered_copy(dan)
    with pytest.raises(hub.DealError, match="tier"):
        hub.ask(noa, c, "lend")
    with pytest.raises(community.CommunityError, match="tier"):
        community.start_thread(noa, "discussion", "שלום", "טקסט")
    with pytest.raises(circles.CircleError, match="tier"):
        circles.create(noa, "מעגל")
    login(client, noa)
    page = client.get(f"/books/near/{c.pk}/").content.decode()
    assert "/books/plans/" in page and 'name="kind"' not in page
    assert "/books/plans/" in client.get("/books/club/new/").content.decode()
    assert "/books/plans/" in client.get("/books/circles/").content.decode()
    assert client.post("/books/api/deals/", {"copy": c.pk, "kind": "lend"}).json()["detail"] == "hub.err.tier"


def test_a_free_person_still_answers_reads_and_joins(noa, dan):
    from books import hub

    staff = person("אבי", "avi@example.com", staff=True)
    club = circles.create(staff, "מעגל")
    circles.join(noa, club, club.join_code)  # joining is free
    th = community.start_thread(staff, "discussion", "שיחה", "טקסט")
    assert community.can_read(noa, th)
    c = offered_copy(noa)
    deal = hub.ask(staff, c, "lend")
    hub.approve(deal, noa)  # a free person answers a request
    hub.send_message(deal, noa, "בשמחה")


def test_the_free_library_stops_at_1000(noa, monkeypatch):
    monkeypatch.setattr(shelf, "FREE_CAP", 2)
    for i in range(2):
        Copy.objects.create(owner=noa, entry=CatalogEntry.objects.create(collection_type=catalog.book_type(),
                                                                          title=f"ספר {i}"))
    assert shelf.room_left(noa) == 0
    tiers.redeem(noa, "helpavi")
    assert shelf.room_left(noa) is None


def test_payment_is_shown_but_blocked(client, noa):
    page = login(client, noa).get("/books/plans/").content.decode()
    assert page.count("disabled aria-disabled=\"true\"") == 2
    assert "התשלום ייפתח בקרוב" in page and "4.99" in page
    assert client.get("/books/api/plan/").json()["payment_open"] is False


# ---- codes -------------------------------------------------------------------------------------

def test_a_code_works_once_per_person_case_and_spaces_aside(noa):
    sub = tiers.redeem(noa, "  HelpAvi ")
    assert sub.tier == Profile.PLUS and (sub.ends_at - sub.started_at) == timedelta(days=90)
    assert tiers.effective(noa) == Profile.PLUS and tiers.allows(noa, "ask")
    with pytest.raises(tiers.TierError, match="already"):
        tiers.redeem(noa, "helpavi")
    assert Coupon.objects.get(code="helpavi").uses == 1


def test_unknown_inactive_expired_or_used_up_codes_are_refused(noa, dan):
    with pytest.raises(tiers.TierError, match="plans.err.code"):
        tiers.redeem(noa, "nope")
    Coupon.objects.create(code="old", is_active=False)
    with pytest.raises(tiers.TierError, match="plans.err.code"):
        tiers.redeem(noa, "old")
    Coupon.objects.create(code="past", expires_at=timezone.now() - timedelta(days=1))
    with pytest.raises(tiers.TierError, match="plans.err.code"):
        tiers.redeem(noa, "past")
    Coupon.objects.create(code="one", max_uses=1)
    tiers.redeem(noa, "one")
    with pytest.raises(tiers.TierError, match="used_up"):
        tiers.redeem(dan, "one")


def test_the_90_days_end_and_the_library_stays(noa):
    sub = tiers.redeem(noa, "helpavi")
    Subscription.objects.filter(pk=sub.pk).update(started_at=timezone.now() - timedelta(days=91),
                                                  ends_at=timezone.now() - timedelta(days=1))
    assert tiers.effective(noa) == Profile.FREE and not tiers.allows(noa, "ask")
    assert tiers.until(noa) is None


def test_a_second_code_starts_when_the_first_ends(noa):
    first = tiers.redeem(noa, "helpavi")
    Coupon.objects.create(code="more", days=30)
    second = tiers.redeem(noa, "more")
    assert second.started_at == first.ends_at
    assert tiers.until(noa) == first.ends_at  # the second is not in force yet


def test_staff_are_never_locked_out_and_hand_set_tiers_count(noa):
    staff = person("אבי", "avi@example.com", staff=True)
    assert all(tiers.allows(staff, f) for f in tiers.FEATURES)
    noa.tier = Profile.PLUS
    noa.save()
    assert tiers.allows(noa, "club_post")


# ---- the whole way through the pages ------------------------------------------------------------------

def test_from_refused_to_a_code_to_asking(client, noa, dan):
    c = offered_copy(dan)
    login(client, noa)
    r = client.post("/books/plans/", {"code": "wrong", "next": f"/books/near/{c.pk}/"})
    assert "הקוד לא מוכר" in r.content.decode()
    r = client.post("/books/plans/", {"code": "helpavi", "next": f"/books/near/{c.pk}/"})
    assert r["Location"] == f"/books/near/{c.pk}/?redeemed=1"
    page = client.get(r["Location"]).content.decode()
    assert 'name="kind"' in page
    client.post(f"/books/near/{c.pk}/", {"kind": "lend", "message": "אשמח"})
    assert c.deals.count() == 1
    plans = client.get("/books/plans/").content.decode()
    assert "המסלול שלך: מנוי" in plans and "עד " in plans
    community.start_thread(noa, "discussion", "עכשיו מותר", "טקסט")
    assert Thread.objects.count() == 1
    api = client.get("/books/api/plan/").json()
    assert api["tier"] == "plus" and api["features"]["ask"] is True
    assert client.post("/books/api/plan/redeem/", {"code": "helpavi"}).json()["detail"] == "plans.err.already"


def test_scans_of_a_free_person_do_not_search_the_web(noa, settings, monkeypatch):
    from books import weblookup

    settings.OPENAI_API_KEY = "sk-test"
    asked = []
    monkeypatch.setattr(weblookup, "lookup_many", lambda *a, **kw: asked.append(a) or {})
    from books.models import ScanItem, ShelfScan

    scan = ShelfScan.objects.create(owner=noa, status=ShelfScan.REVIEW, photo="x.jpg")
    ScanItem.objects.create(scan=scan, position=0, raw_title="ספר")
    assert shelf.web_candidates(scan) == 0 and asked == []
    tiers.redeem(noa, "helpavi")
    shelf.web_candidates(scan)
    assert len(asked) == 1
