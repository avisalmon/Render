"""BK6: circles and the first launch (docs/books/backlog.md, spec BK6).
Circles (create, invite by link or code, join, leave, moderators, a circle's
books beyond the radius, its meeting places), feedback from inside the app,
and the pilot desk. Refusals first."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from books import catalog, circles, hub, storage
from books.models import (CatalogEntry, Circle, CircleMember, Copy, Deal, Feedback, MeetingPlace, Notification,
                          Offer, Profile, Wish)

pytestmark = [pytest.mark.sprbk6, pytest.mark.django_db]
User = get_user_model()

HAIFA = (Decimal("32.79"), Decimal("34.99"))
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


def person(name, email, point=HAIFA, area="הדר", staff=False):
    u = User.objects.create_user(email.split("@")[0], email, "pw", is_staff=staff)
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name=area,
                                  area_lat=point[0], area_lng=point[1], radius_km=10)


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com")


@pytest.fixture
def far(db):
    return person("רון", "ron@example.com", TEL_AVIV, area="פלורנטין")


@pytest.fixture
def entry(db):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", language="he")
    catalog.set_creators(e, ["עמוס עוז"])
    return e


@pytest.fixture
def club(noa):
    return circles.create(noa, "מועדון הקריאה של הדר", "club", "הדר", is_private=True)


def offered(owner, entry, kind="lend"):
    c = Copy.objects.create(owner=owner, entry=entry, visibility=Copy.PUBLIC)
    Offer.objects.create(copy=c, kind=kind, loan_days=30 if kind == "lend" else None)
    return c


def login(client, p):
    client.force_login(p.user)
    return client


# ---- refusals ---------------------------------------------------------------------------------

def test_signed_out_people_see_no_circle(client, club):
    for url in ("/books/circles/", f"/books/circles/{club.pk}/", f"/books/join/{club.join_code}/", "/books/pilot/"):
        r = client.get(url)
        assert r.status_code in (302, 403)


def test_a_private_circle_is_invisible_without_its_code(client, club, dan, far):
    login(client, dan)
    assert client.get(f"/books/circles/{club.pk}/").status_code == 404
    assert client.post(f"/books/circles/{club.pk}/act/", {"action": "join"}).status_code == 404
    with pytest.raises(circles.CircleError, match="circle.err.code"):
        circles.join(dan, club, "WRONGCODE")
    assert "מועדון הקריאה" not in client.get("/books/circles/").content.decode()
    r = client.post("/books/circles/", {"action": "join", "code": "NOPE1234"})
    assert r.status_code == 200 and CircleMember.objects.filter(profile=dan).count() == 0
    assert client.get("/books/api/circles/").json() == []
    assert client.get(f"/books/api/circles/{club.pk}/").status_code == 404


def test_only_the_owner_names_moderators_and_nobody_removes_the_owner(club, noa, dan, far):
    circles.join(dan, club, club.join_code)
    circles.join(far, club, club.join_code)
    dan_m = circles.membership(dan, club)
    noa_m = circles.membership(noa, club)
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.set_role(dan, circles.membership(far, club), CircleMember.MODERATOR)
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.remove(dan, circles.membership(far, club))
    circles.set_role(noa, dan_m, CircleMember.MODERATOR)
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.remove(dan, noa_m)  # a moderator never removes the owner
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.set_role(noa, noa_m, CircleMember.MEMBER)  # ownership is not given away here
    circles.remove(dan, circles.membership(far, club))  # a moderator removes a member
    assert not CircleMember.objects.filter(profile=far).exists()


def test_a_non_member_never_sees_the_circles_books_or_code(client, club, noa, dan, far, entry):
    offered(noa, entry)
    open_circle = circles.create(far, "ספרייה פתוחה", "neighbourhood", is_private=False)
    offered(far, entry)
    assert circles.books(open_circle, dan) == []  # not a member yet
    login(client, dan)
    page = client.get(f"/books/circles/{open_circle.pk}/").content.decode()
    assert "מיכאל שלי" not in page and open_circle.join_code not in page
    assert client.get(f"/books/api/circles/{open_circle.pk}/").json()["join_code"] is None
    assert client.get(f"/books/api/circles/{open_circle.pk}/books/").json() == []


def test_the_pilot_desk_and_feedback_list_are_staff_only(client, noa):
    login(client, noa)
    assert client.get("/books/pilot/").status_code == 404
    assert client.get("/books/api/pilot/").status_code == 404
    Feedback.objects.create(profile=noa, body="שלי")
    other = person("אחר", "o@example.com")
    Feedback.objects.create(profile=other, body="של אחר")
    assert [f["body"] for f in client.get("/books/api/feedback/").json()] == ["שלי"]
    mine = Feedback.objects.get(profile=noa)
    r = client.patch(f"/books/api/feedback/{mine.pk}/", {"status": "read"}, content_type="application/json")
    assert r.status_code == 400
    assert client.post(f"/books/pilot/feedback/{mine.pk}/read/").status_code == 404


def test_a_circles_meeting_place_is_offered_only_to_its_members(club, noa, dan, far, entry):
    circles.join(dan, club, club.join_code)
    place = circles.add_place(noa, club, "בית הקפה של השכונה", "הדר", "cafe")
    everyone = MeetingPlace.objects.create(name="הספרייה העירונית")
    assert set(circles.places_for(noa, dan)) == {place, everyone}
    assert set(circles.places_for(noa, far)) == {everyone}
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.remove_place(dan, place)
    with pytest.raises(circles.CircleError, match="not_allowed"):
        circles.remove_place(noa, everyone)  # everyone's places are staff's
    c = offered(noa, entry)
    deal = hub.ask(far, c, "lend")
    hub.approve(deal, noa)
    hub.set_meeting(deal, noa, circles.places_for(noa, far).filter(pk=place.pk).first(), "")
    deal.refresh_from_db()
    assert deal.meeting_place is None  # a circle's place does not leak to an outsider's deal


# ---- creating, joining, leaving -------------------------------------------------------------------

def test_create_join_by_code_and_by_link(client, noa, dan, far):
    login(client, noa)
    r = client.post("/books/circles/", {"action": "create", "name": "  המעגל  ", "kind": "work", "area_name": "חיפה",
                                        "description": "", "is_private": "1"})
    circle = Circle.objects.get()
    assert r["Location"] == f"/books/circles/{circle.pk}/"
    assert circle.name == "המעגל" and circle.is_private and len(circle.join_code) == 8
    assert circles.membership(noa, circle).role == CircleMember.OWNER
    assert not set("0O1I") & set(circle.join_code)

    # By code, typed with spaces and lower case.
    typed = f" {circle.join_code[:4].lower()} {circle.join_code[4:]} "
    r = login(client, dan).post("/books/circles/", {"action": "join", "code": typed})
    assert r["Location"] == f"/books/circles/{circle.pk}/"
    assert circles.membership(dan, circle).role == CircleMember.MEMBER
    circles.join(dan, circle, circle.join_code)  # idempotent
    assert CircleMember.objects.filter(profile=dan).count() == 1

    # By link: a page that names the circle, then one tap.
    login(client, far)
    page = client.get(f"/books/join/{circle.join_code}/")
    assert page.status_code == 200 and "המעגל" in page.content.decode()
    r = client.post(f"/books/join/{circle.join_code}/")
    assert r["Location"].startswith(f"/books/circles/{circle.pk}/")
    assert circle.members.count() == 3
    assert client.get("/books/join/NOSUCH00/").status_code == 404

    # The page for a member shows the code and the link.
    page = client.get(f"/books/circles/{circle.pk}/").content.decode()
    assert circle.join_code in page and f"/books/join/{circle.join_code}/" in page


def test_a_new_code_retires_the_old_link_and_keeps_members(client, club, noa, dan):
    circles.join(dan, club, club.join_code)
    old = club.join_code
    login(client, noa).post(f"/books/circles/{club.pk}/act/", {"action": "new_code"})
    club.refresh_from_db()
    assert club.join_code != old
    assert client.get(f"/books/join/{old}/").status_code == 404
    assert circles.membership(dan, club) is not None


def test_leaving_hands_the_circle_on_and_the_last_one_out_closes_it(club, noa, dan, far):
    circles.join(dan, club, club.join_code)
    circles.join(far, club, club.join_code)
    circles.set_role(noa, circles.membership(far, club), CircleMember.MODERATOR)
    circles.leave(noa, club)
    assert circles.membership(far, club).role == CircleMember.OWNER  # the moderator, not the older member
    circles.leave(far, club)
    assert circles.membership(dan, club).role == CircleMember.OWNER
    assert circles.leave(dan, club) is None
    assert not Circle.objects.filter(pk=club.pk).exists()
    with pytest.raises(circles.CircleError, match="not_member"):
        circles.leave(dan, circles.create(noa, "אחר"))


def test_member_counts_count_everyone_not_only_me(client, club, noa, dan, far, entry):
    circles.join(dan, club, club.join_code)
    circles.join(far, club, club.join_code)
    assert circles.my_circles(noa).get().n_members == 3
    open_circle = circles.create(dan, "פתוח", is_private=False)
    circles.join(far, open_circle)
    assert circles.open_circles(noa).get().n_members == 2
    login(client, noa)
    assert client.get(f"/books/api/circles/{club.pk}/").json()["n_members"] == 3
    assert "3 חברים" in client.get("/books/circles/").content.decode()
    # The owner whose own books are the only ones offered is told so, not "none".
    offered(noa, entry)
    page = client.get(f"/books/circles/{club.pk}/").content.decode()
    assert "הם שלך" in page and "עוד אין ספרים" not in page


def test_an_open_circle_is_listed_and_joined_in_one_tap(client, noa, dan):
    open_circle = circles.create(noa, "שכונת הדר", "neighbourhood", "הדר", is_private=False)
    login(client, dan)
    assert "שכונת הדר" in client.get("/books/circles/").content.decode()
    r = client.post(f"/books/circles/{open_circle.pk}/act/", {"action": "join"})
    assert r.status_code == 302 and circles.membership(dan, open_circle)
    r = client.post("/books/api/circles/", {"name": "API", "is_private": False})
    assert r.status_code == 201 and r.json()["my_role"] == "owner" and r.json()["join_code"]


# ---- the circle's books ------------------------------------------------------------------------------

def test_members_see_each_others_books_beyond_the_radius(client, club, noa, far, entry):
    c = offered(far, entry)  # 80 km away
    assert hub.offered_copies(noa) == []
    circles.join(far, club, club.join_code)
    assert [x.pk for x, _ in hub.offered_copies(noa)] == [c.pk]
    assert [x.pk for x, _ in hub.offered_copies(noa, circles_only=True)] == [c.pk]
    assert [x.pk for x, _ in circles.books(club, noa)] == [c.pk]
    private = Copy.objects.create(owner=far, entry=entry, visibility=Copy.PRIVATE)
    assert private.pk not in [x.pk for x, _ in circles.books(club, noa)]
    hub.block(far, noa)
    assert circles.books(club, noa) == [] and hub.offered_copies(noa) == []
    hub.unblock(far, noa)
    login(client, noa)
    page = client.get(f"/books/circles/{club.pk}/").content.decode()
    assert "מיכאל שלי" in page and f"/books/near/{c.pk}/" in page
    assert client.get(f"/books/api/circles/{club.pk}/books/").json()[0]["copy"] == c.pk
    assert "near.in_circles" not in client.get("/books/near/").content.decode()
    assert "מיכאל שלי" in client.get("/books/near/?circles=1").content.decode()


def test_a_wished_book_offered_by_a_circle_member_far_away_still_alerts(django_capture_on_commit_callbacks, club,
                                                                        noa, far, entry):
    circles.join(far, club, club.join_code)
    Wish.objects.create(profile=noa, entry=entry)
    with django_capture_on_commit_callbacks(execute=True):
        offered(far, entry)
    assert Notification.objects.filter(profile=noa, kind="wish.available").count() == 1


def test_a_request_between_members_may_meet_at_the_circles_place(client, club, noa, dan, entry):
    circles.join(dan, club, club.join_code)
    place = circles.add_place(noa, club, "בית הקפה", "הדר", "cafe", is_partner=True)
    c = offered(noa, entry)
    deal = hub.ask(dan, c, "lend")
    hub.approve(deal, noa)
    login(client, dan)
    assert "בית הקפה" in client.get(f"/books/deals/{deal.pk}/").content.decode()
    client.post(f"/books/deals/{deal.pk}/act/", {"action": "meeting", "place": place.pk})
    deal.refresh_from_db()
    assert deal.meeting_place == place


# ---- feedback and the pilot desk ------------------------------------------------------------------

def test_feedback_goes_from_any_page_to_the_pilot_desk(client, noa, entry):
    login(client, noa)
    assert 'action="/books/feedback/"' in client.get("/books/near/").content.decode()
    r = client.post("/books/feedback/", {"body": "הכפתור קטן מדי", "path": "/books/near/?q=x", "next": "/books/near/"})
    assert r["Location"] == "/books/near/?thanks=1"
    assert "feedback.thanks" not in client.get(r["Location"]).content.decode()
    f = Feedback.objects.get()
    assert f.profile == noa and f.path == "/books/near/?q=x" and f.status == Feedback.OPEN
    client.post("/books/feedback/", {"body": "   "})
    assert Feedback.objects.count() == 1
    staff = person("אבי", "avi@example.com", staff=True)
    login(client, staff)
    page = client.get("/books/pilot/").content.decode()
    assert "הכפתור קטן מדי" in page
    client.post(f"/books/pilot/feedback/{f.pk}/read/")
    f.refresh_from_db()
    assert f.status == Feedback.READ


def test_the_pilot_numbers_count_people_not_events(client, noa, dan, far, entry, club):
    from books.pilot import numbers

    c = offered(noa, entry)
    offered(noa, CatalogEntry.objects.create(collection_type=catalog.book_type(), title="שני"))
    deal = hub.ask(dan, c, "lend")
    hub.approve(deal, noa)
    hub.confirm_handover(deal, noa)
    hub.confirm_handover(deal, dan)
    hub.mark_returned(deal, dan)
    hub.confirm_returned(deal, noa)
    hub.ask(dan, Copy.objects.exclude(pk=c.pk).get(), "lend")
    circles.join(dan, club, club.join_code)
    n = numbers()
    assert dict(n["funnel"]) == {"people": 3, "scanned": 0, "with_books": 1, "offering": 1, "asked": 1, "completed": 2}
    assert n["deals"]["total"] == 2 and n["deals"]["completed"] == 1 and n["deals"]["open"] == 1
    assert n["books"]["held"] == 2 and n["books"]["offered"] == 2
    assert n["circles"][0].n_members == 2 and n["circles"][0].n_books == 2
    staff = person("אבי", "avi@example.com", staff=True)
    login(client, staff)
    assert client.get("/books/pilot/").status_code == 200
    api = client.get("/books/api/pilot/?days=30").json()
    assert api["days"] == 30 and api["circles"][0]["members"] == 2 and "as_of" in api
    assert Deal.objects.count() == 2
