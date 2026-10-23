"""Giving, and the hand-to-hand flow (spec BK5b, Avi 2026-10-23). The rules
first: a gift moves the book; the pilot's Pro; friends first for two days;
a free person's four with friends; a friend asks for an unoffered book; the
line of askers; "went to someone else"; every step by email; the terms."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.utils import timezone

from books import catalog, friends, hub, storage, tiers
from books.models import CatalogEntry, Copy, CopyTransfer, Deal, Offer, Profile, Subscription

pytestmark = [pytest.mark.django_db]
User = get_user_model()
HAIFA = (Decimal("32.79"), Decimal("34.99"))


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.BOOKS_PILOT_EVERYONE_ASKS = False
    settings.BOOKS_PILOT_GIFT = False
    settings.BOOKS_FRIENDS_FIRST_HOURS = 48
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


def person(name, email, lang="he"):
    u = User.objects.create_user(email.split("@")[0], email, "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name="הדר",
                                  area_lat=HAIFA[0], area_lng=HAIFA[1], radius_km=10, language=lang)


def pro(profile):
    Subscription.objects.create(profile=profile, tier=Profile.PLUS, started_at=timezone.now() - timedelta(days=1),
                                ends_at=timezone.now() + timedelta(days=30), provider=Subscription.MANUAL)
    return profile


def befriend(a, b):
    friends.join_through_invite(b, friends.invite_for(a))


def book(owner, title="מיכאל שלי", visibility=Copy.PUBLIC, *kinds, hours=0):
    """A copy with offers; `hours` makes the offers that old (past the friends-first window)."""
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)
    c = Copy.objects.create(owner=owner, entry=e, visibility=visibility)
    for k in kinds:
        o = Offer.objects.create(copy=c, kind=k, loan_days=30 if k == "lend" else None)
        if hours:
            older(o, hours)
    return c


def older(offer_or_copy, hours):
    model = Offer if isinstance(offer_or_copy, Offer) else Copy
    model.objects.filter(pk=offer_or_copy.pk).update(created_at=timezone.now() - timedelta(hours=hours))


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com", lang="en")


@pytest.fixture
def stranger(db):
    return pro(person("זר", "zar@example.com"))


# ---- a gift ----------------------------------------------------------------------------------

def test_a_gift_is_offered_asked_for_and_the_book_moves_to_the_receiver(noa, dan):
    befriend(noa, dan)
    c = book(noa, "מיכאל שלי", Copy.PUBLIC, "give")
    deal = hub.ask(dan, c, "give", "אשמח!")
    assert deal.kind == "give" and deal.offer.kind == "give" and deal.status == Deal.REQUESTED
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    deal.refresh_from_db()
    assert deal.status == Deal.APPROVED  # one side is not enough
    hub.confirm_handover(deal, dan)
    deal.refresh_from_db()
    c.refresh_from_db()
    assert deal.status == Deal.COMPLETED and c.owner == dan and c.visibility == Copy.PRIVATE and not c.offers.exists()
    assert CopyTransfer.objects.get(copy=c).kind == "given"
    assert hub.reputation(noa)["given"] == 1 and hub.reputation(dan)["received"] == 1


def test_the_api_asks_for_a_gift_too(client, noa, dan):
    befriend(noa, dan)
    c = book(noa, "ספר", Copy.PUBLIC, "give")
    client.force_login(dan.user)
    r = client.post("/books/api/deals/", {"copy": c.pk, "kind": "give"})
    assert r.status_code == 201 and r.json()["kind"] == "give"


# ---- the pilot's gift ----------------------------------------------------------------------

def test_during_the_pilot_everyone_is_pro_and_is_told_it_is_a_gift(client, settings, noa):
    settings.BOOKS_PILOT_GIFT = True
    assert tiers.effective(noa) == Profile.PLUS and tiers.gifted(noa) and tiers.allows(noa, "ask")
    client.force_login(noa.user)
    me = client.get("/books/settings/").content.decode()
    assert "המסלול Pro הוא מתנה" in me
    plans = client.get("/books/plans/").content.decode()
    assert "המסלול שלך: Pro" in plans and "המסלול Pro הוא מתנה" in plans
    pro(noa)  # their own Pro: still Pro, no longer a gift
    assert tiers.effective(noa) == Profile.PLUS and not tiers.gifted(noa)
    settings.BOOKS_PILOT_GIFT = False
    free = person("חדש", "new@example.com")
    assert tiers.effective(free) == Profile.FREE and not tiers.gifted(free)
    client.force_login(free.user)
    assert "המסלול Pro הוא מתנה" not in client.get("/books/settings/").content.decode()


# ---- a free person: friends only, four times ------------------------------------------------

def test_a_free_person_asks_friends_only_and_four_times_on_pro_terms(noa, dan, stranger):
    befriend(noa, dan)
    with pytest.raises(hub.DealError, match="hub.err.tier"):
        hub.ask(noa, book(stranger, "זר 1", Copy.PUBLIC, "give", hours=72), "give")
    declined = hub.ask(noa, book(dan, "דן נדחה", Copy.PUBLIC, "give"), "give")
    hub.decline(declined, dan)  # a declined ask costs nothing
    for i in range(4):
        d = hub.ask(noa, book(dan, f"דן {i}", Copy.PUBLIC, "give"), "give")
        assert hub.friend_deals_left(noa) == 4 - i  # asking costs nothing until it is approved
        hub.approve(d, dan)
        assert hub.friend_deals_left(noa) == 3 - i
    with pytest.raises(hub.DealError, match="hub.err.friends_quota"):
        hub.ask(noa, book(dan, "דן 5", Copy.PUBLIC, "give"), "give")
    # Answering is always free: dan (free too) can approve noa; and Pro has no limit.
    pro(noa)
    assert hub.ask(noa, book(dan, "דן 6", Copy.PUBLIC, "give"), "give").status == Deal.REQUESTED
    assert hub.ask(noa, book(stranger, "זר 2", Copy.PUBLIC, "give", hours=72), "give").status == Deal.REQUESTED


# ---- friends first --------------------------------------------------------------------------

def test_a_fresh_offer_is_the_friends_alone_for_two_days(noa, dan, stranger):
    befriend(noa, dan)
    pro(dan)
    c = book(noa, "חדש על המדף", Copy.PUBLIC, "lend")
    assert [x.pk for x, _ in hub.offered_copies(dan)] == [c.pk]
    assert hub.offered_copies(stranger) == []
    with pytest.raises(hub.DealError, match="hub.err.not_offered"):
        hub.ask(stranger, c, "lend")
    assert hub.ask(dan, c, "lend").status == Deal.REQUESTED
    older(c.offers.get(), hub.FRIENDS_FIRST_HOURS + 1)
    assert [x.pk for x, _ in hub.offered_copies(stranger)] == [c.pk]
    assert hub.ask(stranger, c, "lend").offer is not None


# ---- a friend asks for a book that is not offered ---------------------------------------------

def test_a_friend_may_ask_for_any_book_they_can_see_offered_or_not(noa, dan, stranger):
    befriend(noa, dan)
    pro(dan)
    quiet = book(noa, "לא מוצע", Copy.PRIVATE)
    d = hub.ask(dan, quiet, "lend")
    assert d.offer is None and d.kind == "lend" and d.loan_days is None
    with pytest.raises(hub.DealError, match="hub.err.not_offered"):
        hub.ask(stranger, book(noa, "פומבי לא מוצע", Copy.PUBLIC), "give")
    with pytest.raises(hub.DealError, match="hub.err.not_offered"):
        hub.ask(dan, book(noa, "רק אני", Copy.HIDDEN), "give")
    swap = hub.ask(dan, book(noa, "להחלפה", Copy.PRIVATE, "exchange"), "exchange")  # no book named yet
    assert swap.swap_copy is None
    hub.approve(swap, noa)
    hub.confirm_handover(swap, noa)
    hub.confirm_handover(swap, dan)
    swap.refresh_from_db()
    assert swap.status == Deal.COMPLETED and swap.copy.owner == dan


def test_offers_on_a_friends_only_book_reach_the_friends_and_only_me_withdraws_them(client, noa, dan):
    befriend(noa, dan)
    c = book(noa, "לחברים", Copy.PRIVATE)
    client.force_login(noa.user)
    client.post(f"/books/copy/{c.pk}/", {"visibility": "private", "give": "on", "location_note": "", "condition": "",
                                         "notes": "", "rarity_note": ""})
    c.refresh_from_db()
    assert c.visibility == Copy.PRIVATE and [o.kind for o in c.offers.all()] == ["give"]
    assert hub.offered_copies(dan) == []  # not on "near": that is for public books
    assert hub.ask(dan, c, "give").offer.kind == "give"  # but a friend asks on the offer
    client.post(f"/books/copy/{c.pk}/", {"visibility": "hidden", "give": "on", "location_note": "", "condition": "",
                                         "notes": "", "rarity_note": ""})
    c.refresh_from_db()
    assert c.visibility == Copy.HIDDEN and not c.offers.exists()  # "only me" is explicit: the offer goes


# ---- the line of askers -----------------------------------------------------------------------

def test_the_owner_sees_the_askers_in_order_chooses_and_the_others_are_told_where_else(client, noa, dan, stranger):
    befriend(noa, dan)
    third = pro(person("שלישי", "third@example.com"))
    befriend(noa, third)
    c = book(noa, "מבוקש", Copy.PUBLIC, "give")
    older(c.offers.get(), 72)
    first = hub.ask(dan, c, "give")
    Deal.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(minutes=30))
    second = hub.ask(stranger, c, "give")
    Deal.objects.filter(pk=second.pk).update(created_at=timezone.now() - timedelta(minutes=20))
    last = hub.ask(third, c, "give")
    first.refresh_from_db()
    second.refresh_from_db()
    assert [d.requester for d in hub.askers(c)] == [dan, stranger, third]
    assert hub.place_in_line(last) == 3 and hub.place_in_line(first) == 1
    client.force_login(noa.user)
    html = client.get(f"/books/deals/{last.pk}/").content.decode()
    assert "3 מבקשים את הספר" in html and "מקום 3 בתור" in html
    assert html.index(">דן<") < html.index(">זר<") < html.index(">שלישי<")

    hub.approve(last, noa)  # the owner's choice, not the first in line
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == Deal.DECLINED and hub.went_elsewhere(first) and hub.went_elsewhere(second)
    # dan is told, and shown another friend's copy of the same book
    other_friend = pro(person("רותי", "ruti@example.com"))
    befriend(dan, other_friend)
    spare = Copy.objects.create(owner=other_friend, entry=c.entry, visibility=Copy.PRIVATE)
    client.force_login(dan.user)
    html = client.get(f"/books/deals/{first.pk}/").content.decode()
    assert "נועה gave the book to someone else." in html and "It may be had here:" in html  # dan reads English
    assert f'href="/books/people/{other_friend.pk}/shelf/"' in html and "Your friend has it" in html
    assert [e["copy"].pk for e in hub.elsewhere(dan, c.entry, exclude_copy=c)] == [spare.pk]
    # nobody else has it: the wish
    Copy.objects.filter(pk=spare.pk).delete()
    html = client.get(f"/books/deals/{first.pk}/").content.decode()
    assert "data-wish-link" in html and "It may be had here" not in html


# ---- every step and every message by email ----------------------------------------------------

def test_every_step_of_a_request_and_every_message_also_go_by_email(noa, dan):
    befriend(noa, dan)
    c = book(noa, "מיכאל שלי", Copy.PUBLIC, "give")
    django_mail.outbox.clear()
    deal = hub.ask(dan, c, "give", "אשמח לקבל")
    assert len(django_mail.outbox) == 1
    m = django_mail.outbox[0]
    assert m.to == ["noa@example.com"] and m.subject.startswith("ספרים: ") and "דן מבקש/ת את מיכאל שלי" in m.subject
    assert f"https://babook.co.il/books/deals/{deal.pk}/" in m.body and "ספרים רק מחברת ביניכם" in m.body
    hub.send_message(deal, noa, "בשמחה, מתי נוח לך?")
    assert len(django_mail.outbox) == 2
    m = django_mail.outbox[1]
    assert m.to == ["dan@example.com"] and m.subject == "Books: A message from נועה about מיכאל שלי"  # dan reads English
    assert "בשמחה, מתי נוח לך?" in m.body and "Books only connects you" in m.body
    hub.send_message(deal, dan, "Tomorrow at six?")
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    assert [x.to[0] for x in django_mail.outbox[2:]] == ["noa@example.com", "dan@example.com", "dan@example.com"]
    assert "Your request for מיכאל שלי was approved" in django_mail.outbox[3].subject


def test_a_notification_that_is_not_about_a_request_stays_in_the_app(noa, dan):
    django_mail.outbox.clear()
    friends.follow(dan, noa)  # a friend request: the bell, no mail
    assert django_mail.outbox == []


def test_a_person_without_an_email_breaks_nothing(noa, dan):
    befriend(noa, dan)
    noa.user.email = ""
    noa.user.save()
    django_mail.outbox.clear()
    assert hub.ask(dan, book(noa, "ספר", Copy.PUBLIC, "give"), "give").status == Deal.REQUESTED
    assert django_mail.outbox == []


# ---- the terms --------------------------------------------------------------------------------

def test_the_terms_and_the_welcome_say_books_is_only_a_go_between(client, noa):
    html = client.get("/books/terms/").content.decode()
    assert "מתווכת בלבד" in html and "לא צד בשום עסקה" in html and "משלוח" in html and "מסירות, השאלות, החלפות ומכירות הן ביניכם" in html
    assert "לא מתווכת בתשלום" in html
