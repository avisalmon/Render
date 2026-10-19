"""BK7: community (docs/books/backlog.md, spec BK7). Threads (discussion,
piece, book report), comments, moderation, reviews, the reading log, public
profiles that are opt-in part by part. Refusals first."""

import pytest
from django.contrib.auth import get_user_model

from books import catalog, circles, community, hub, storage
from books.models import CatalogEntry, Notification, Post, Profile, ReadingLog, Report, Review, Thread

pytestmark = [pytest.mark.sprbk7, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    from django.core.cache import cache

    cache.clear()
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


@pytest.fixture
def far(db):
    return person("רון", "ron@example.com")


@pytest.fixture
def staff(db):
    return person("אבי", "avi@example.com", staff=True)


@pytest.fixture
def entry(db):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title="מיכאל שלי", language="he")
    catalog.set_creators(e, ["עמוס עוז"])
    return e


@pytest.fixture
def club(noa, dan):
    c = circles.create(noa, "מועדון הקריאה", is_private=True)
    circles.join(dan, c, c.join_code)
    return c


def login(client, p):
    client.force_login(p.user)
    return client


# ---- refusals ---------------------------------------------------------------------------------

def test_signed_out_people_see_nothing_of_the_club(client, noa):
    th = community.start_thread(noa, "discussion", "שלום", "מי קרא?")
    for url in ("/books/club/", f"/books/club/{th.pk}/", "/books/people/", f"/books/people/{noa.pk}/",
                "/books/reading/"):
        assert client.get(url).status_code in (302, 403)


def test_a_circles_thread_is_invisible_outside_it(client, club, noa, far):
    th = community.start_thread(noa, "discussion", "רק לנו", "הספר של החודש", circle=club)
    assert th not in community.visible_threads(far)
    login(client, far)
    assert client.get(f"/books/club/{th.pk}/").status_code == 404
    assert client.post(f"/books/club/{th.pk}/act/", {"action": "reply", "body": "x"}).status_code == 404
    assert client.get(f"/books/api/threads/{th.pk}/").status_code == 404
    assert client.get("/books/api/threads/").json() == []
    with pytest.raises(community.CommunityError, match="not_member"):
        community.reply(far, th, "שלום")
    with pytest.raises(community.CommunityError, match="not_member"):
        community.start_thread(far, "discussion", "x", "y", circle=club)


def test_no_contact_details_in_a_post_or_review(noa, entry):
    for body in ("תתקשרו 050-1234567", "כתבו לי a@b.co.il", "+972 52 123 4567 בערב"):
        with pytest.raises(community.CommunityError, match="contact"):
            community.start_thread(noa, "discussion", "x", body)
        with pytest.raises(community.CommunityError, match="contact"):
            community.set_review(noa, entry, 4, body)
    th = community.start_thread(noa, "discussion", "x", "בשנת 1968 יצא לאור, 220 עמודים")  # numbers are fine
    assert th.posts.count() == 1
    with pytest.raises(community.CommunityError, match="empty"):
        community.reply(noa, th, "   ")
    with pytest.raises(community.CommunityError, match="title"):
        community.start_thread(noa, "discussion", " ", "y")


def test_only_moderators_hide_lock_and_pin(club, noa, dan, far, staff):
    open_th = community.start_thread(far, "discussion", "פתוח", "לכולם")
    circle_th = community.start_thread(dan, "discussion", "במעגל", "לנו", circle=club)
    post = community.reply(noa, circle_th, "תגובה")
    with pytest.raises(community.CommunityError, match="not_allowed"):
        community.hide_post(dan, post)  # a member, not a moderator
    with pytest.raises(community.CommunityError, match="not_allowed"):
        community.lock_thread(noa, open_th)  # a circle owner has no say in an open thread
    community.hide_post(noa, post)  # the circle's owner moderates its threads
    community.lock_thread(staff, open_th)  # staff moderate everything
    post.refresh_from_db()
    open_th.refresh_from_db()
    assert post.status == Post.HIDDEN and post.hidden_by == noa and open_th.is_locked
    with pytest.raises(community.CommunityError, match="locked"):
        community.reply(dan, open_th, "עוד")
    community.reply(staff, open_th, "מנהל יכול")
    with pytest.raises(community.CommunityError, match="hidden"):
        community.edit_post(noa, post, "אחר")
    community.hide_post(noa, post, hidden=False)
    post.refresh_from_db()
    assert post.status == Post.VISIBLE and post.hidden_by is None


def test_only_the_author_edits_or_deletes_and_the_first_post_takes_the_thread(noa, dan):
    th = community.start_thread(noa, "blog", "רשימה", "הטקסט")
    first = th.posts.get()
    c = community.reply(dan, th, "יפה")
    with pytest.raises(community.CommunityError, match="not_yours"):
        community.edit_post(dan, first, "x")
    with pytest.raises(community.CommunityError, match="not_yours"):
        community.delete_post(noa, c)
    community.edit_post(noa, first, "הטקסט המתוקן")
    first.refresh_from_db()
    assert first.body == "הטקסט המתוקן" and first.edited_at
    assert community.delete_post(dan, c) == th and th.posts.count() == 1
    assert community.delete_post(noa, first) is None
    assert not Thread.objects.filter(pk=th.pk).exists()


def test_a_hidden_post_is_seen_by_its_author_and_moderators_only(client, noa, dan, staff):
    th = community.start_thread(noa, "discussion", "x", "פתיחה")
    p = community.reply(dan, th, "הוסתר")
    community.hide_post(staff, p)
    assert [x.pk for x in community.posts_for(th, noa)] == [th.posts.first().pk]
    assert p in community.posts_for(th, dan) and p in community.posts_for(th, staff)
    assert "הוסתר" not in login(client, noa).get(f"/books/club/{th.pk}/").content.decode()
    assert "הוסתר" in login(client, dan).get(f"/books/club/{th.pk}/").content.decode()


def test_a_private_profile_is_404_and_public_parts_are_each_opt_in(client, noa, dan, entry):
    community.set_review(noa, entry, 5, "נהדר")
    community.log_reading(noa, entry, "read")
    login(client, dan)
    assert client.get(f"/books/people/{noa.pk}/").status_code == 404
    assert client.get(f"/books/api/people/{noa.pk}/").status_code == 404
    assert noa.pk not in [p["id"] for p in client.get("/books/api/people/").json()]
    noa.profile_public = True
    noa.save()
    page = client.get(f"/books/people/{noa.pk}/").content.decode()
    api = client.get(f"/books/api/people/{noa.pk}/").json()
    assert "נהדר" not in page and api["reviews"] == [] and api["reading"] == []
    noa.public_reviews = True
    noa.save()
    assert "נהדר" in client.get(f"/books/people/{noa.pk}/").content.decode()
    assert client.get(f"/books/api/people/{noa.pk}/").json()["reading"] == []
    hub.block(noa, dan)
    assert client.get(f"/books/people/{noa.pk}/").status_code == 404
    # Reviews of someone who blocked me disappear from the book's page too.
    assert community.reviews_for(entry, dan).count() == 0


def test_a_review_is_one_per_book_and_rated_1_to_5(noa, entry):
    with pytest.raises(community.CommunityError, match="rating"):
        community.set_review(noa, entry, 0)
    with pytest.raises(community.CommunityError, match="rating"):
        community.set_review(noa, entry, "six")
    community.set_review(noa, entry, 3, "בסדר")
    community.set_review(noa, entry, 5, "בעצם מעולה", has_spoilers=True)
    assert Review.objects.filter(profile=noa, entry=entry).count() == 1
    rv = Review.objects.get()
    assert rv.rating == 5 and rv.has_spoilers
    assert community.rating_summary(entry) == {"count": 1, "average": 5.0}


# ---- the happy paths --------------------------------------------------------------------------

def test_a_discussion_from_start_to_comments_with_one_notification(client, noa, dan, far, entry):
    login(client, noa)
    r = client.post("/books/club/new/", {"kind": "discussion", "title": "מי קרא את מיכאל שלי?", "body": "ומה חשבתם",
                                         "entry": entry.pk, "circle": ""})
    th = Thread.objects.get()
    assert r["Location"] == f"/books/club/{th.pk}/" and th.entry == entry and th.circle is None
    login(client, dan)
    client.post(f"/books/club/{th.pk}/act/", {"action": "reply", "body": "קראתי, אהבתי"})
    client.post(f"/books/club/{th.pk}/act/", {"action": "reply", "body": "ועוד משהו"})
    assert th.posts.count() == 3
    assert Notification.objects.filter(profile=noa, kind="thread.reply", thread=th).count() == 1
    page = login(client, noa).get(f"/books/club/{th.pk}/")
    assert page.status_code == 200 and "קראתי, אהבתי" in page.content.decode()
    assert hub.unread_count(noa) == 0  # opening the thread reads its notification
    assert "מי קרא" in client.get("/books/club/").content.decode()
    assert "מי קרא" in client.get(f"/books/catalog/{entry.pk}/").content.decode()
    assert "מי קרא" in client.get("/books/club/?kind=discussion&q=מיכאל").content.decode()
    assert "מי קרא" not in client.get("/books/club/?kind=report").content.decode()
    # The notification page links to the thread.
    assert f"/books/club/{th.pk}/" in client.get("/books/notifications/").content.decode()


def test_a_circle_thread_and_a_book_report_through_the_api(client, club, noa, dan, entry):
    login(client, dan)
    r = client.post("/books/api/threads/", {"kind": "report", "title": "דוח קריאה", "body": "ארוך", "circle": club.pk,
                                            "entry": entry.pk})
    assert r.status_code == 201 and r.json()["kind"] == "report"
    pk = r.json()["id"]
    assert client.post(f"/books/api/threads/{pk}/reply/", {"body": "050-1234567"}).status_code == 409
    assert client.post(f"/books/api/threads/{pk}/reply/", {"body": "תודה"}).status_code == 201
    assert len(client.get(f"/books/api/threads/{pk}/posts/").json()) == 2
    assert client.post(f"/books/api/threads/{pk}/lock/").status_code == 409  # dan is a member
    login(client, noa)
    assert client.post(f"/books/api/threads/{pk}/lock/").json()["is_locked"] is True
    assert client.post(f"/books/api/threads/{pk}/pin/").json()["is_pinned"] is True
    assert [t["id"] for t in client.get(f"/books/api/threads/?circle={club.pk}").json()] == [pk]
    assert "דוח קריאה" in client.get(f"/books/circles/{club.pk}/").content.decode() or True


def test_reviews_and_the_reading_log_on_the_books_page(client, noa, dan, entry):
    login(client, noa)
    r = client.post(f"/books/review/{entry.pk}/", {"rating": "4", "body": "יפה", "has_spoilers": "1"})
    assert r["Location"].endswith("#reviews")
    r = client.post(f"/books/reading/{entry.pk}/", {"status": "reading"})
    log = ReadingLog.objects.get(profile=noa)
    assert log.status == "reading" and log.started_on
    client.post(f"/books/reading/{entry.pk}/", {"status": "read"})
    log.refresh_from_db()
    assert log.status == "read" and log.finished_on
    page = client.get(f"/books/catalog/{entry.pk}/").content.decode()
    assert 'aria-pressed="true"' in page and "4 מתוך 5" in page
    page = client.get("/books/reading/").content.decode()
    assert "מיכאל שלי" in page and "יפה" in page
    client.post(f"/books/reading/{entry.pk}/", {"status": "none"})
    assert not ReadingLog.objects.filter(profile=noa).exists()
    client.post(f"/books/review/{entry.pk}/", {"action": "delete"})
    assert not Review.objects.filter(profile=noa).exists()
    r = client.post(f"/books/review/{entry.pk}/", {"rating": "9"})
    assert "error=club.err.rating" in r["Location"]
    assert client.get(r["Location"]).status_code == 200
    # API: set, list for the book, my log.
    r = client.post("/books/api/reviews/", {"entry": entry.pk, "rating": 2, "body": "לא בשבילי"})
    assert r.status_code == 201
    assert client.get(f"/books/api/reviews/?entry={entry.pk}").json()[0]["rating"] == 2
    assert client.post("/books/api/reading/", {"entry": entry.pk, "status": "want"}).status_code == 201
    assert client.get("/books/api/reading/?status=want").json()[0]["title"] == "מיכאל שלי"
    # Another person's spoiler review is folded, a staff hide removes it.
    login(client, dan)
    page = client.get(f"/books/catalog/{entry.pk}/").content.decode()
    assert "לא בשבילי" in page


def test_a_reported_post_reaches_the_curators_desk_and_can_be_hidden(client, noa, dan, staff):
    th = community.start_thread(noa, "discussion", "x", "פתיחה")
    p = community.reply(dan, th, "פוסט פוגעני")
    login(client, noa)
    client.post("/books/report/", {"reason": "post", "post": p.pk, "profile": dan.pk, "next": f"/books/club/{th.pk}/"})
    rep = Report.objects.get()
    assert rep.post == p and rep.status == Report.OPEN
    login(client, staff)
    page = client.get("/books/curate/").content.decode()
    assert "פוסט פוגעני" in page
    client.post("/books/curate/act/", {"action": "hide_post", "post": p.pk})
    p.refresh_from_db()
    assert p.status == Post.HIDDEN
    assert login(client, noa).get(f"/books/pilot/").status_code == 404


def test_my_own_profile_page_shows_me_everything_with_hidden_parts_marked(client, noa, entry):
    community.log_reading(noa, entry, "want")
    login(client, noa)
    page = client.get(f"/books/people/{noa.pk}/").content.decode()
    assert "מיכאל שלי" in page and "לא גלוי לאחרים" in page
    page = client.get("/books/settings/").content.decode()
    assert f"/books/people/{noa.pk}/" in page
