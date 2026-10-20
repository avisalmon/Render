"""BK10: rare books and the museum (spec BK10, 12.8). Hints never decide,
the owner sends, a curator looks, nothing is valued, an owner's copy is
shown only after they agree, with their name and photos only if they
chose. Refusals and privacy first."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image

from books import catalog, rare, storage
from books.models import (CatalogEntry, Copy, CopyPhoto, CopyTransfer, Exhibit, ExhibitItem, Notification, Profile,
                          RareReview)

pytestmark = [pytest.mark.sprbk10, pytest.mark.django_db]
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


def person(name, email, staff=False, public=False):
    u = User.objects.create_user(email.split("@")[0], email, "pw", is_staff=staff)
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, profile_public=public)


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


@pytest.fixture
def dan(db):
    return person("דן", "dan@example.com")


@pytest.fixture
def curator(db):
    return person("אבי", "avi@example.com", staff=True)


def old_copy(owner, title="חסמב״ה", year=1950, notes=""):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title, year=year)
    return Copy.objects.create(owner=owner, entry=e, notes=notes)


def add_photo(copy, kind="copyright_page"):
    buf = io.BytesIO()
    Image.new("RGB", (60, 80), (200, 180, 150)).save(buf, format="JPEG")
    p = CopyPhoto(copy=copy, kind=kind)
    p.image.save(f"{copy.pk}-{kind}.jpg", ContentFile(buf.getvalue()), save=True)
    return p


def login(client, p):
    client.force_login(p.user)
    return client


def confirmed(owner, curator):
    c = old_copy(owner)
    add_photo(c)
    review = rare.send_for_review(owner, c, "חתימה של המחבר")
    rare.decide(curator, review, True, "מהדורה ראשונה, 1950")
    return c


# ---- refusals and privacy -------------------------------------------------------------------

def test_a_copys_photos_stay_private_until_the_owner_sends_or_agrees(client, noa, dan, curator):
    c = old_copy(noa)
    p = add_photo(c)
    assert login(client, dan).get(f"/books/photo/{p.pk}.jpg").status_code == 404
    assert login(client, curator).get(f"/books/photo/{p.pk}.jpg").status_code == 404  # not sent yet
    assert login(client, noa).get(f"/books/photo/{p.pk}.jpg").status_code == 200
    rare.send_for_review(noa, c)
    assert login(client, curator).get(f"/books/photo/{p.pk}.jpg").status_code == 200  # sending is consent
    assert login(client, dan).get(f"/books/photo/{p.pk}.jpg").status_code == 404


def test_only_the_owner_sends_and_a_photo_is_needed(noa, dan):
    c = old_copy(noa)
    with pytest.raises(rare.RareError, match="photo"):
        rare.send_for_review(noa, c)
    add_photo(c, kind="cover")
    with pytest.raises(rare.RareError, match="photo"):
        rare.send_for_review(noa, c)  # a cover shows nothing rare
    add_photo(c, kind="signed")
    with pytest.raises(rare.RareError, match="not_yours"):
        rare.send_for_review(dan, c)
    assert rare.send_for_review(noa, c).status == RareReview.PENDING


def test_only_curators_decide_build_or_see_drafts(client, noa, dan, curator):
    c = old_copy(noa)
    add_photo(c)
    review = rare.send_for_review(noa, c)
    with pytest.raises(rare.RareError, match="not_allowed"):
        rare.decide(dan, review, True)
    with pytest.raises(rare.RareError, match="not_allowed"):
        rare.new_exhibit(dan, "תערוכה")
    ex = rare.new_exhibit(curator, "תערוכה ראשונה")
    login(client, dan)
    assert client.get("/books/curate/rare/").status_code == 404
    assert client.get(f"/books/museum/{ex.pk}/").status_code == 404  # a draft
    assert client.post("/books/museum/", {"title_he": "שלי"}).status_code == 404
    assert client.get("/books/api/exhibits/").json() == []
    assert client.post("/books/api/exhibits/", {"title_he": "x"}).status_code == 409


def test_only_a_confirmed_copy_can_be_invited(noa, curator):
    c = old_copy(noa)
    add_photo(c)
    rare.send_for_review(noa, c)
    ex = rare.new_exhibit(curator, "תערוכה")
    with pytest.raises(rare.RareError, match="not_confirmed"):
        rare.invite(curator, ex, c)


def test_an_invited_copy_shows_nothing_until_the_owner_agrees(client, noa, dan, curator):
    c = confirmed(noa, curator)
    p = c.photos.first()
    ex = rare.new_exhibit(curator, "ספרי ילדות")
    item = rare.invite(curator, ex, c, "עותק עם הקדשה")
    rare.publish(curator, ex)
    page = login(client, dan).get(f"/books/museum/{ex.pk}/").content.decode()
    assert "חסמב״ה" not in page
    assert client.get(f"/books/photo/{p.pk}.jpg").status_code == 404
    with pytest.raises(rare.RareError, match="not_yours"):
        rare.answer(dan, item, True)
    rare.answer(noa, item, accept=False)
    assert "חסמב״ה" not in login(client, dan).get(f"/books/museum/{ex.pk}/").content.decode()


def test_books_never_puts_a_value_on_anything(curator, noa):
    for model in (RareReview, Exhibit, ExhibitItem):
        names = {f.name for f in model._meta.get_fields()}
        assert not names & {"value", "price", "price_amount", "estimate", "worth"}


# ---- hints -----------------------------------------------------------------------------------------

def test_hints_suggest_and_never_decide(client, noa):
    assert rare.hints(old_copy(noa, "ספר ישן", 1950)) == ["rare.why_old"]
    assert rare.hints(old_copy(noa, "ספר", 1990, notes="עם הקדשה מהמחבר")) == ["rare.why_signed"]
    assert rare.hints(old_copy(noa, "Dune, first edition", 1965)) == ["rare.why_old", "rare.why_first"]
    plain = old_copy(noa, "ספר חדש", 2015)
    assert rare.hints(plain) == []
    c = old_copy(noa, "ספר ישן", 1940)
    assert not Copy.objects.get(pk=c.pk).is_rare_candidate  # a hint marks nothing
    page = login(client, noa).get(f"/books/copy/{c.pk}/").content.decode()
    assert "ייתכן שהעותק הזה מיוחד" in page
    client.post(f"/books/copy/{c.pk}/rare/", {"action": "mark"})
    assert Copy.objects.get(pk=c.pk).is_rare_candidate


# ---- the whole way, from a member's shelf to the museum --------------------------------------------

def test_from_a_shelf_to_a_published_exhibition(client, noa, dan, curator):
    c = old_copy(noa, "חסמב״ה", 1950, notes="חתום")
    add_photo(c, "signed")
    login(client, noa)
    client.post(f"/books/copy/{c.pk}/rare/", {"action": "mark"})
    client.post(f"/books/copy/{c.pk}/rare/", {"note": "חתימה של יגאל מוסינזון"})
    review = RareReview.objects.get(copy=c)
    assert review.status == RareReview.PENDING
    login(client, curator)
    desk = client.get("/books/curate/rare/").content.decode()
    assert "חסמב״ה" in desk and "חתימה של יגאל מוסינזון" in desk
    client.post("/books/curate/rare/", {"review": review.pk, "action": "confirm", "note": "חתימה מקורית"})
    review.refresh_from_db()
    assert review.status == RareReview.CONFIRMED
    assert Notification.objects.filter(profile=noa, kind="rare.reviewed").exists()
    r = client.post("/books/museum/", {"title_he": "חתימות של סופרים", "text_he": "עותקים חתומים מספריות החברים"})
    ex = Exhibit.objects.get()
    assert r["Location"] == f"/books/museum/{ex.pk}/"
    client.post("/books/curate/rare/", {"review": review.pk, "action": "invite", "exhibit": ex.pk, "note": "הקדשה"})
    item = ExhibitItem.objects.get()
    assert item.consent == ExhibitItem.INVITED
    inv = Notification.objects.get(profile=noa, kind="rare.invited")
    client.post(f"/books/museum/{ex.pk}/", {"action": "publish"})
    # The owner agrees, without their name, with photos.
    login(client, noa)
    assert f"/books/museum/invitation/{item.pk}/" in client.get("/books/notifications/").content.decode()
    client.post(f"/books/museum/invitation/{item.pk}/", {"accept": "1", "show_photos": "1"})
    item.refresh_from_db()
    assert item.consent == ExhibitItem.ACCEPTED and not item.show_owner_name and inv.pk
    page = login(client, dan).get(f"/books/museum/{ex.pk}/").content.decode()
    assert "חסמב״ה" in page and "מאוסף של חבר/ה" in page and "נועה" not in page
    photo = c.photos.first()
    assert f"/books/photo/{photo.pk}.jpg" in page and client.get(f"/books/photo/{photo.pk}.jpg").status_code == 200
    assert "חתימות של סופרים" in client.get("/books/museum/").content.decode()
    # The owner changes their mind: name on, photos off.
    login(client, noa).post(f"/books/museum/invitation/{item.pk}/", {"accept": "1", "show_name": "1"})
    page = login(client, dan).get(f"/books/museum/{ex.pk}/").content.decode()
    assert "מהאוסף של נועה" in page and client.get(f"/books/photo/{photo.pk}.jpg").status_code == 404
    # Withdrawing takes it out of every exhibition.
    login(client, noa).post(f"/books/copy/{c.pk}/rare/", {"action": "withdraw"})
    assert not ExhibitItem.objects.exists() and not RareReview.objects.exists()


def test_provenance_names_only_public_profiles(noa, dan, curator):
    c = old_copy(noa)
    pub = person("ציבורי", "pub@example.com", public=True)
    CopyTransfer.objects.create(copy=c, from_profile=pub, to_profile=dan, kind="sold")
    CopyTransfer.objects.create(copy=c, from_profile=dan, to_profile=noa, kind="given")
    rows = rare.provenance(c, viewer=noa)
    assert [(r["kind"], r["from"], r["to"]) for r in rows] == [("sold", "ציבורי", ""), ("given", "", "נועה")]


def test_the_api_follows_the_same_rules(client, noa, dan, curator):
    c = old_copy(noa)
    add_photo(c)
    login(client, noa)
    r = client.post("/books/api/rare-reviews/", {"copy": c.pk, "owner_note": "ישן"})
    assert r.status_code == 201
    pk = r.json()["id"]
    login(client, dan)
    assert client.get("/books/api/rare-reviews/").json() == []
    assert client.post(f"/books/api/rare-reviews/{pk}/decide/", {"confirmed": "1"}).status_code == 404
    login(client, curator)
    assert client.post(f"/books/api/rare-reviews/{pk}/decide/", {"confirmed": "1"}).json()["status"] == "confirmed"
    ex = client.post("/books/api/exhibits/", {"title_he": "תערוכה"}).json()["id"]
    item = client.post("/books/api/exhibit-items/", {"exhibit": ex, "copy": c.pk}).json()["id"]
    client.post(f"/books/api/exhibits/{ex}/publish/")
    login(client, dan)
    assert client.get(f"/books/api/exhibits/{ex}/items/").json() == []
    login(client, noa)
    assert client.post(f"/books/api/exhibit-items/{item}/answer/", {"accept": "1"}).json()["consent"] == "accepted"
    login(client, dan)
    shown = client.get(f"/books/api/exhibits/{ex}/items/").json()
    assert len(shown) == 1 and shown[0]["owner_name"] is None
