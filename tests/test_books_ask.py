"""One tap from a friend's shelf, or from the book's page (spec BK5b, SPR-G.2a):
"I want to receive / borrow / swap for / buy this" lands in the conversation."""

import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from books import catalog, friends, hub, shelf, storage
from books.models import CatalogEntry, Copy, Deal, Offer, Profile

pytestmark = [pytest.mark.django_db]
User = get_user_model()
HAIFA = (Decimal("32.79"), Decimal("34.99"))


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.BOOKS_PILOT_GIFT = True  # the pilot: everyone may ask
    settings.BOOKS_FRIENDS_FIRST_HOURS = 48
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


def person(name, email):
    u = User.objects.create_user(email.split("@")[0], email, "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name="הדר",
                                  area_lat=HAIFA[0], area_lng=HAIFA[1])


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com")


@pytest.fixture
def stranger(db):
    return person("זר", "zar@example.com")


def book(owner, title, visibility=Copy.PUBLIC, *kinds):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)
    c = Copy.objects.create(owner=owner, entry=e, visibility=visibility)
    for k in kinds:
        Offer.objects.create(copy=c, kind=k)
    return c


def test_a_friends_shelf_rows_say_what_i_may_ask_for(noa, dan, stranger):
    friends.join_through_invite(dan, friends.invite_for(noa))
    offered = book(noa, "מוצע", Copy.PUBLIC, "give", "lend")
    quiet = book(noa, "שקט", Copy.PRIVATE)
    hidden = book(noa, "רק אני", Copy.HIDDEN)
    rows = {r["title"]: r for r in shelf.shelf_books(noa, viewer=dan)}
    assert "רק אני" not in rows
    assert rows["מוצע"]["kinds"] == ["give", "lend"] and rows["מוצע"]["ask"] == f"/books/ask/{offered.pk}/"
    assert rows["שקט"]["kinds"] == [] and rows["שקט"]["ask"] == f"/books/ask/{quiet.pk}/"  # a friend may ask anyway
    assert rows["מוצע"]["status"] == "give"
    # a stranger sees only public books (of an open library), and may ask only on an offer that is open
    noa.public_library = True
    noa.save()
    rows = {r["title"]: r for r in shelf.shelf_books(noa, viewer=stranger)}
    assert "שקט" not in rows and "ask" not in rows["מוצע"]
    Offer.objects.filter(copy=offered).update(created_at=__import__("django.utils.timezone", fromlist=["now"]).now()
                                              - __import__("datetime").timedelta(hours=49))
    rows = {r["title"]: r for r in shelf.shelf_books(noa, viewer=stranger)}
    assert rows["מוצע"]["ask"] == f"/books/ask/{offered.pk}/" and rows["מוצע"]["kinds"] == ["give", "lend"]
    # my own shelf carries no ask
    assert "ask" not in shelf.shelf_books(noa, viewer=noa)[0]


def test_one_tap_opens_the_conversation(client, noa, dan):
    friends.join_through_invite(dan, friends.invite_for(noa))
    c = book(noa, "מיכאל שלי", Copy.PUBLIC, "give")
    client.force_login(dan.user)
    r = client.post(f"/books/ask/{c.pk}/", {"kind": "give", "next": f"/books/people/{noa.pk}/shelf/"})
    deal = Deal.objects.get()
    assert r.status_code == 302 and r["Location"] == f"/books/deals/{deal.pk}/" and deal.kind == "give"
    # a second tap goes to the same conversation, no second request
    r = client.post(f"/books/ask/{c.pk}/", {"kind": "lend"})
    assert r["Location"] == f"/books/deals/{deal.pk}/" and Deal.objects.count() == 1
    html = client.get(r["Location"]).content.decode()
    assert "מסירה במתנה" in html and "מקום 1 בתור" in html


def test_a_refused_tap_goes_back_with_the_reason(client, noa, dan, stranger):
    hidden = book(noa, "רק אני", Copy.HIDDEN)
    client.force_login(stranger.user)
    r = client.post(f"/books/ask/{hidden.pk}/", {"kind": "give", "next": f"/books/people/{noa.pk}/shelf/"})
    assert r["Location"] == f"/books/people/{noa.pk}/shelf/?error=hub.err.not_offered"
    noa.public_library = True
    noa.save()
    html = client.get(r["Location"]).content.decode()
    assert "הספר הזה כבר לא מוצע כך." in html
    r = client.post(f"/books/ask/{hidden.pk}/", {"kind": "give"})
    assert r["Location"] == f"/books/catalog/{hidden.entry_id}/?error=hub.err.not_offered"


def test_the_books_page_shows_which_friends_hold_it_with_one_tap_each(client, noa, dan, stranger):
    friends.join_through_invite(dan, friends.invite_for(noa))
    c = book(noa, "מיכאל שלי", Copy.PRIVATE, "lend")
    Copy.objects.create(owner=stranger, entry=c.entry, visibility=Copy.PUBLIC)  # not a friend: not listed here
    client.force_login(dan.user)
    html = client.get(f"/books/catalog/{c.entry_id}/").content.decode()
    assert "אצל החברים (1)" in html and f'action="/books/ask/{c.pk}/"' in html
    block = html.split("data-holders")[1].split("</section>")[0]
    assert ">נועה<" in block and 'value="lend" class="bk-btn bk-btn--small bk-btn--primary"' in block
    assert 'value="give" class="bk-btn bk-btn--small"' in block  # not offered, still askable
    client.post(f"/books/ask/{c.pk}/", {"kind": "lend"})
    html = client.get(f"/books/catalog/{c.entry_id}/").content.decode()
    assert f'href="/books/deals/{Deal.objects.get().pk}/"' in html  # my open request on it
    assert [h["copy"].pk for h in hub.friends_holding(stranger, c.entry)] == []


def test_the_shelf_label_strings_carry_the_ask_words(client, noa, dan):
    friends.join_through_invite(dan, friends.invite_for(noa))
    book(noa, "ספר", Copy.PUBLIC, "give")
    client.force_login(dan.user)
    html = client.get(f"/books/people/{noa.pk}/shelf/").content.decode()
    strings = json.loads(html.split('id="friend-strings">')[1].split("</script>")[0])
    assert strings["status.give"] == "למסירה" and "ask.offered" in strings
    assert "data-label-ask" in html and 'data-ask-kind="give"' in html


def test_the_conversation_endpoint_gives_new_messages_and_marks_them_read(client, noa, dan):
    friends.join_through_invite(dan, friends.invite_for(noa))
    c = book(noa, "ספר", Copy.PUBLIC, "give")
    deal = hub.ask(dan, c, "give", "ראשונה")
    second = hub.send_message(deal, noa, "שנייה")
    client.force_login(dan.user)
    d = client.get(f"/books/deals/{deal.pk}/messages/").json()
    assert [m["body"] for m in d["messages"]] == ["ראשונה", "שנייה"] and d["messages"][1]["who"] == "נועה"
    assert d["status"] == "requested"
    second.refresh_from_db()
    assert second.read_at is not None
    assert client.get(f"/books/deals/{deal.pk}/messages/?after={second.pk}").json()["messages"] == []
    stranger = person("זר", "zar@example.com")
    client.force_login(stranger.user)
    assert client.get(f"/books/deals/{deal.pk}/messages/").status_code == 404


def test_the_request_page_opens_as_a_conversation(client, noa, dan):
    friends.join_through_invite(dan, friends.invite_for(noa))
    c = book(noa, "ספר", Copy.PUBLIC, "give")
    deal = hub.ask(dan, c, "give")
    client.force_login(noa.user)
    html = client.get(f"/books/deals/{deal.pk}/").content.decode()
    assert "data-chat" in html and 'data-chat-form' in html and "books/deal.js" in html
    assert "הודעה לדן..." in html and "כל הודעה מגיעה גם למייל" in html
    hub.decline(deal, noa)
    html = client.get(f"/books/deals/{deal.pk}/").content.decode()
    assert "data-chat-form" not in html  # a closed request takes no more messages
