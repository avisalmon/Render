"""Friends (Avi, 2026-10-22): invite links that make both sides follow each
other, follow requests (at once for open libraries), quiet removal, and a
friend's library: followers see everything but "only me", spine photos
included unless turned off; strangers see only books open to everyone."""

import pytest
from django.contrib.auth import get_user_model

from books import catalog, friends, shelf, storage
from books.models import CatalogEntry, Copy, Follow, Invite, Notification, Profile

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


def person(name, **kw):
    u = User.objects.create_user(name, f"{name}@example.com", "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, **kw)


@pytest.fixture
def avi(db):
    return person("avi")


@pytest.fixture
def moshe(db):
    return person("moshe")


def shelf_of(owner, *visibilities):
    out = []
    for i, v in enumerate(visibilities):
        e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=f"ספר {i} ({v})")
        out.append(Copy.objects.create(owner=owner, entry=e, position=i, visibility=v))
    return out


# ---- the invite link -----------------------------------------------------------------

def test_my_invite_link_is_mine_and_stays_the_same(avi):
    a = friends.invite_for(avi)
    assert len(a.code) == 7 and friends.invite_for(avi).pk == a.pk


def test_a_visitor_through_my_link_joins_and_we_follow_each_other(client, avi):
    code = friends.invite_for(avi).code
    r = client.get(f"/books/i/{code}/?via=whatsapp")
    html = r.content.decode()
    # The link is the welcome page itself, with its own preview for WhatsApp and the rest, in English.
    assert r.status_code == 200 and 'property="og:title" content="avi invited you to Books"' in html
    assert "books/og-invite" in html and "avi הזמין/ה אותך" in html
    u = User.objects.create_user("dana", "dana@example.com", "pw")
    client.force_login(u)
    r = client.post("/books/welcome/", {"display_name": "דנה", "language": "he", "is_adult_confirmed": "on",
                                        "accept_terms": "on"})
    assert r.status_code == 302
    dana = Profile.objects.get(user=u)
    assert dana.invited_by == avi and dana.invited_via == "whatsapp"
    assert set(Follow.objects.values_list("follower__display_name", "followee__display_name", "status")) == {
        ("דנה", "avi", "accepted"), ("avi", "דנה", "accepted")}
    assert Notification.objects.get(profile=avi).kind == "friends.joined"
    assert Invite.objects.get(inviter=avi).joined == 1


def test_a_member_who_opens_my_link_follows_me_and_i_them(client, avi, moshe):
    client.force_login(moshe.user)
    r = client.get(f"/books/i/{friends.invite_for(avi).code}/")
    assert r["Location"] == f"/books/people/{avi.pk}/shelf/?joined=1"
    assert friends.status_between(moshe, avi) == "accepted" and friends.status_between(avi, moshe) == "accepted"


def test_my_own_link_does_nothing_to_me(client, avi):
    client.force_login(avi.user)
    client.get(f"/books/i/{friends.invite_for(avi).code}/")
    assert not Follow.objects.exists()


def test_a_wrong_code_goes_home(client):
    assert client.get("/books/i/nope123/")["Location"] == "/books/"


# ---- following ----------------------------------------------------------------------

def test_asking_to_follow_waits_for_an_answer(client, avi, moshe):
    client.force_login(moshe.user)
    client.post(f"/books/people/{avi.pk}/follow/")
    row = Follow.objects.get()
    assert row.status == Follow.PENDING and Notification.objects.get(profile=avi).kind == "friends.asked"
    client.force_login(avi.user)
    html = client.get("/books/friends/").content.decode()
    assert "מבקש/ת לעקוב אחריך" in html
    client.post(f"/books/friends/requests/{row.pk}/", {"action": "accept"})
    row.refresh_from_db()
    assert row.status == Follow.ACCEPTED and Notification.objects.get(profile=moshe).kind == "friends.accepted"


def test_an_open_library_is_followed_at_once(client, avi, moshe):
    avi.public_library = True
    avi.save()
    client.force_login(moshe.user)
    client.post(f"/books/people/{avi.pk}/follow/")
    assert Follow.objects.get().status == Follow.ACCEPTED
    assert Notification.objects.get(profile=avi).kind == "friends.followed"


def test_declining_and_quiet_removal_tell_nobody(client, avi, moshe):
    friends.follow(moshe, avi)
    Notification.objects.all().delete()
    client.force_login(avi.user)
    client.post(f"/books/friends/requests/{Follow.objects.get().pk}/", {"action": "decline"})
    assert not Follow.objects.exists()
    friends.join_through_invite(moshe, friends.invite_for(avi))
    Notification.objects.all().delete()
    client.post(f"/books/people/{moshe.pk}/remove/")
    assert friends.status_between(moshe, avi) is None and friends.status_between(avi, moshe) == "accepted"
    assert not Notification.objects.exists()


def test_find_people_by_name(client, avi, moshe):
    client.force_login(avi.user)
    html = client.get("/books/friends/?q=mos").content.decode()
    assert f'action="/books/people/{moshe.pk}/follow/"' in html


# ---- a friend's library ---------------------------------------------------------------

def test_a_follower_sees_everything_but_only_me(client, avi, moshe):
    hidden, friends_only, public = shelf_of(avi, "hidden", "private", "public")
    friends.join_through_invite(moshe, friends.invite_for(avi))
    rows = shelf.shelf_books(avi, viewer=moshe)
    assert {r["id"] for r in rows} == {friends_only.pk, public.pk}
    assert all(r["url"].startswith("/books/catalog/") for r in rows)
    client.force_login(moshe.user)
    html = client.get(f"/books/people/{avi.pk}/shelf/").content.decode()
    assert "הספרייה של avi" in html and '<h1 class="bk-plate"' in html and "(hidden)" not in html


def test_a_stranger_sees_only_books_open_to_everyone_on_an_open_library(client, avi, moshe):
    shelf_of(avi, "private", "public")
    client.force_login(moshe.user)
    html = client.get(f"/books/people/{avi.pk}/shelf/").content.decode()
    assert "פתוח לעוקבים" in html and "(public)" not in html  # closed: ask to follow
    avi.public_library = True
    avi.save()
    rows = shelf.shelf_books(avi, viewer=moshe)
    assert [r["title"] for r in rows] == ["ספר 1 (public)"]


def test_followers_see_spine_photos_unless_turned_off(avi, moshe):
    friends.join_through_invite(moshe, friends.invite_for(avi))
    assert friends.can_see_spines(moshe, avi)
    avi.followers_see_spines = False
    avi.save()
    assert not friends.can_see_spines(moshe, avi)
    assert friends.can_see_spines(avi, avi)


def test_the_home_has_the_friends_tile_with_requests(client, avi, moshe):
    friends.follow(moshe, avi)
    client.force_login(avi.user)
    html = client.get("/books/").content.decode()
    assert 'class="bk-quick-tile bk-quick-friends" href="/books/friends/"' in html and '<b class="bk-quick-badge">1</b>' in html


def test_the_qr_code_is_my_link(client, avi):
    client.force_login(avi.user)
    r = client.get("/books/friends/qr.svg")
    assert r.status_code == 200 and r["Content-Type"] == "image/svg+xml" and b"<svg" in r.content


# ---- scanning defaults to public; "only me" is a choice -----------------------------------

def test_a_new_scan_is_public_by_default(client, avi):
    client.force_login(avi.user)
    html = client.get("/books/scan/").content.decode()
    import re
    checked = re.search(r'<input type="radio" name="default_visibility" value="(\w+)"[^>]*checked', html)
    assert checked and checked.group(1) == "public"


# ---- the API ------------------------------------------------------------------------

def test_the_api_follows_answers_and_removes(client, avi, moshe):
    client.force_login(moshe.user)
    r = client.post("/books/api/follows/", {"followee": avi.pk}, content_type="application/json")
    assert r.status_code == 201 and r.json()["status"] == "pending"
    client.force_login(avi.user)
    fid = r.json()["id"]
    assert client.post(f"/books/api/follows/{fid}/accept/").json()["status"] == "accepted"
    assert client.delete(f"/books/api/follows/{fid}/").status_code == 204  # quietly removed
    assert not Follow.objects.exists()
    codes = client.get("/books/api/invites/").json()
    codes = codes["results"] if isinstance(codes, dict) else codes
    assert len(codes) == 1 and len(codes[0]["code"]) == 7


def test_the_invitation_is_one_share_button_in_english(client, avi):
    client.force_login(avi.user)
    html = client.get("/books/friends/").content.decode()
    assert html.count("data-share=") == 1 and "wa.me" not in html and "mailto:" not in html
    assert "Come see my bookshelf" in html and "Hi! I put my bookshelf on Books." in html
    assert "data-qr-open" in html


# ---- the invited person's way in (Avi, 2026-10-22) ----------------------------------------

def test_the_invited_welcome_shows_the_inviters_shelf_from_afar(client, avi):
    import json
    shelf_of(avi, "hidden", "private", "public")
    html = client.get(f"/books/i/{friends.invite_for(avi).code}/").content.decode()
    assert 'data-theme="dark"' in html  # new people and visitors start dark
    assert "avi מזמין/ה אותך להציץ במדף" in html and "מצטרפים ורואים את המדף של avi" in html
    assert '<h1 class="bk-plate"' in html and "הספרייה של avi" in html
    rows = json.loads(html.split('id="demo-data">')[1].split("</script>")[0])
    assert [r["title"] for r in rows] == ["ספר 1 (private)", "ספר 2 (public)"]  # what a follower will see, not "only me"
    assert all(r["url"] == "" and "photo" not in r for r in rows)  # from afar: drawn, no doors


def test_sign_in_and_onboarding_say_who_invited_me(client, avi):
    client.get(f"/books/i/{friends.invite_for(avi).code}/")
    assert "avi הזמין/ה אותך" in client.get("/books/login/").content.decode()
    u = User.objects.create_user("dana", "dana@example.com", "pw")
    client.force_login(u)
    assert "עוד צעד אחד והמדף של avi פתוח לך" in client.get("/books/welcome/").content.decode()


def test_joining_lands_on_the_friends_shelf_in_the_dark(client, avi):
    shelf_of(avi, "public")
    client.get(f"/books/i/{friends.invite_for(avi).code}/")
    u = User.objects.create_user("dana", "dana@example.com", "pw")
    client.force_login(u)
    r = client.post("/books/welcome/", {"display_name": "דנה", "language": "he", "is_adult_confirmed": "on",
                                        "accept_terms": "on"})
    assert r["Location"] == f"/books/people/{avi.pk}/shelf/?joined=1"  # no survey in the way
    assert Profile.objects.get(user=u).theme == "dark"
    html = client.get(r["Location"]).content.decode()
    assert 'data-theme="dark"' in html and "את/ה וavi חברים עכשיו" in html
    assert "עכשיו תורך: צילום המדף שלי" in html  # my own shelf is still empty


def test_a_friends_shelf_wears_their_own_look(client, avi, moshe):
    shelf_of(avi, "public")
    friends.join_through_invite(moshe, friends.invite_for(avi))
    client.force_login(moshe.user)
    for mine, shown in (("bookcase", "bookcase"), ("living", "lamp"), ("lamp", "lamp")):
        avi.shelf_view = mine
        avi.save()
        assert f'data-shelf-view="{shown}"' in client.get(f"/books/people/{avi.pk}/shelf/").content.decode()



# ---- the friends page, rebuilt (Avi, 2026-10-23) ------------------------------------------

def test_the_search_finds_a_friend_from_two_letters_anywhere_in_the_name(client, avi):
    salmon = person("salmon")
    salmon.display_name = "אבי סלמון"
    salmon.save()
    other = person("other")
    other.display_name = "מוטי מוסקוביץ"
    other.save()
    friends.join_through_invite(salmon, friends.invite_for(avi))
    found = friends.search(avi, "מו")
    assert found["friends"] == [salmon]  # "מו" inside "סלמון"
    assert [f["p"] for f in found["others"]] == [other]
    assert friends.search(avi, "סלמונ")["friends"] == [salmon]  # a final letter typed as an ordinary one
    assert friends.search(avi, "מ") == {"q": "מ", "friends": [], "others": []}

    client.force_login(avi.user)
    html = client.get("/books/friends/search/?q=מו").content.decode()
    assert "החברים שלי" in html and "עוד אנשים בספרים" in html and "אבי סלמון" in html
    assert html.index("אבי סלמון") < html.index("מוטי מוסקוביץ")
    assert f'action="/books/people/{other.pk}/follow/"' in html and "בקשת חברות" in html
    assert f'action="/books/people/{salmon.pk}/follow/"' not in html
    assert "עוד אות או שתיים" in client.get("/books/friends/search/?q=מ").content.decode()


def test_not_searching_the_page_is_the_invite_button_and_only_what_needs_me(client, avi, moshe):
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from books.models import Deal

    asker = person("asker")
    friends.follow(asker, avi)  # waits for my answer
    friends.join_through_invite(moshe, friends.invite_for(avi))  # new, through my invitation
    old = person("old")
    friends.follow(avi, old)
    friends.follow(old, avi)
    Follow.objects.filter(follower=old).update(status=Follow.ACCEPTED)
    Follow.objects.filter(followee=old).update(status=Follow.ACCEPTED)
    long_ago = timezone.now() - timedelta(days=friends.NEW_DAYS + 5)
    Follow.objects.filter(Q(follower=old) | Q(followee=old)).update(created_at=long_ago, accepted_at=long_ago)
    copy = shelf_of(avi, "public")[0]
    Deal.objects.create(copy=copy, owner=avi, requester=moshe, kind="lend")

    client.force_login(avi.user)
    html = client.get("/books/friends/").content.decode()
    assert 'data-friend-results aria-live="polite" hidden' in html  # no results until I search
    assert "data-invite-open" in html and '<dialog class="bk-invite-sheet" data-invite' in html
    assert "מחכים לתשובה שלך" in html and "asker" in html and "מבקש/ת לעקוב אחריך" in html
    assert "רוצים ספר שלך" in html and f"מבקש/ת את &quot;{copy.entry.title}&quot;" in html
    assert "חברים חדשים" in html and "הצטרף/ה דרך ההזמנה שלך" in html
    new_part = html.split("חברים חדשים")[1]
    assert "moshe" in new_part and ">old<" not in new_part  # a friend from long ago is not new
    assert 'href="/books/friends/all/"' in html and "כל החברים (2)" in html


def test_a_friends_wishlist_stays_private_on_my_friends_page(client, avi, moshe):
    from books.models import Wish

    friends.join_through_invite(moshe, friends.invite_for(avi))
    copy = shelf_of(avi, "public")[0]
    Wish.objects.create(profile=moshe, entry=copy.entry)
    client.force_login(avi.user)
    assert copy.entry.title not in client.get("/books/friends/").content.decode()


def test_all_my_friends_is_one_link_away(client, avi, moshe):
    friends.join_through_invite(moshe, friends.invite_for(avi))
    client.force_login(avi.user)
    html = client.get("/books/friends/all/").content.decode()
    assert "כל החברים" in html and "moshe" in html and "אני עוקב/ת · 1" in html
    assert "moshe" in client.get("/books/friends/all/?tab=followers").content.decode()


def test_a_newcomer_sees_the_invite_and_why(client, avi):
    client.force_login(avi.user)
    html = client.get("/books/friends/").content.decode()
    assert "עוד אין לך חברים כאן" in html and "כל החברים" not in html
