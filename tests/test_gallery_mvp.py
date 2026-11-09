"""gallery, SPR-G.1 to G.4: the frame, pages, the training question, likes,
stars, comments, people and search.

Sharpest: `test_the_training_never_leaks` (the one private fact a person gives
the gallery) and `test_a_visitor_sees_everything_and_can_do_nothing`
(the app's whole promise, both halves).

Traces: REQ-G.1 to G.6, G.10 to G.13, G.20 to G.23, G.30 to G.33, G.80,
G.90, G.102, G.103.
"""

import importlib
import io
import re
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import User

from gallery import shots
from gallery.models import Comment, Exhibit, Like, Person, Star, Topic, Training
from gallery.strings import STRINGS

PASSWORD = "gallery-pass-5521"
ROOT = Path(__file__).resolve().parent.parent


def _jpeg():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1200, 750), (40, 120, 160)).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def offline(settings, tmp_path, monkeypatch):
    settings.GALLERY_FILES_DIR = tmp_path
    settings.GALLERY_SHOTS_ENABLED = True
    settings.OPENAI_API_KEY = ""  # methodology 26
    calls = []

    def fake_fetch(url, timeout=12):
        calls.append(url)
        return None if "broken" in url else _jpeg()

    monkeypatch.setattr(shots, "fetch", fake_fetch)
    return calls


def _user(email, first="", last="", superuser=False):
    user = User.objects.create_user(email, email, PASSWORD, first_name=first, last_name=last)
    if superuser:
        user.is_superuser = user.is_staff = True
        user.save()
    return user


def _person(user, training=True):
    from gallery.access import ensure_person

    person = ensure_person(user)
    if training:
        person.training = Training.objects.first()
        person.training_set_at = person.created_at
        person.save()
    return person


@pytest.fixture
def people(db):
    return {
        "dana": _person(_user("dana@example.com", "דנה", "לוי")),
        "omer": _person(_user("omer@example.com", "Omer", "Katz")),
        "avi": _person(_user("avi@example.com", "אבי", "סלמון", superuser=True)),
    }


def _card(owner, title="מחשבון משכנתא", url="https://dana.github.io/mortgage/", kind=Exhibit.PAGE, topics=()):
    card = Exhibit.objects.create(owner=owner, title=title, url=url, kind=kind)
    for slug in topics:
        card.topics.add(Topic.objects.get(slug=slug))
    return card


# ------------------------------------------------------------ open to look at


def test_a_visitor_sees_everything_and_can_do_nothing(client, people):
    """REQ-G.1, G.2"""
    card = _card(people["dana"])
    Comment.objects.create(exhibit=card, author=people["omer"], body="יפה מאוד")
    home = client.get("/gallery/")
    assert home.status_code == 200
    page = home.content.decode()
    assert "מחשבון משכנתא" in page and "דנה לוי" in page
    detail = client.get(f"/gallery/e/{card.pk}/").content.decode()
    assert "יפה מאוד" in detail and 'id="gl-sign-in-to-comment"' in detail and 'id="gl-comment-form"' not in detail
    assert client.get(f"/gallery/u/{people['dana'].slug}/").status_code == 200
    assert client.get("/gallery/api/exhibits/").status_code == 200
    assert client.get(f"/gallery/api/comments/?exhibit={card.pk}").json()[0]["body"] == "יפה מאוד"
    # ...and doing anything is refused, never quietly accepted.
    assert client.post(f"/gallery/api/exhibits/{card.pk}/like/").status_code in (401, 403)
    assert client.post("/gallery/api/comments/", {"exhibit": card.pk, "body": "x"}).status_code in (401, 403)
    assert client.post("/gallery/api/exhibits/", {"title": "x", "url": "https://x.io"}).status_code in (401, 403)
    assert Like.objects.count() == 0 and Comment.objects.count() == 1 and Exhibit.objects.count() == 1
    # Looking never creates a person row.
    assert Person.objects.count() == 3


def test_adding_sends_a_visitor_to_sign_in_and_back(client, db):
    """REQ-G.2"""
    response = client.get("/gallery/new/")
    assert response.status_code == 302 and response["Location"] == "/gallery/login/?next=%2Fgallery%2Fnew%2F"


def test_a_new_account_can_post_at_once(client, db):
    """REQ-G.2, G.3: sign up in the gallery's look, no approval step."""
    page = client.get("/gallery/signup/?next=/gallery/new/").content.decode()
    assert "gl-bar" in page and "babook" in page
    response = client.post("/gallery/signup/", {
        "name": "נועה ברק", "email": "noa@example.com", "password1": "Zq8!long-pass-x", "password2": "Zq8!long-pass-x",
        "next": "/gallery/new/",
    })
    assert response.status_code == 302 and response["Location"] == "/gallery/new/"
    # The first post asks the training first (REQ-G.4).
    response = client.get("/gallery/new/")
    assert response.status_code == 302 and response["Location"].startswith("/gallery/training/?next=")


def test_login_next_cannot_leave_the_gallery(client, people):
    response = client.post("/gallery/login/?next=https://evil.example/", {
        "username": "dana@example.com", "password": PASSWORD, "next": "https://evil.example/"})
    assert response.status_code == 302 and response["Location"] == "/gallery/"


# ------------------------------------------------------------ the training question


def test_the_first_post_asks_the_training_once(client, db):
    """REQ-G.4"""
    user = _user("rami@example.com", "Rami")
    client.force_login(user)
    response = client.get("/gallery/new/")
    assert response["Location"] == "/gallery/training/?next=%2Fgallery%2Fnew%2F"
    page = client.get(response["Location"]).content.decode()
    for t in Training.objects.filter(is_open=True):
        assert t.name_he in page
    assert "אחר" in page
    technion = Training.objects.get(name_en="Technion semester course")
    response = client.post("/gallery/training/", {"training": str(technion.pk), "next": "/gallery/new/"})
    assert response["Location"] == "/gallery/new/"
    person = Person.objects.get(user=user)
    assert person.training == technion and person.training_set_at
    assert client.get("/gallery/new/").status_code == 200


def test_other_with_a_line(client, db):
    """REQ-G.4: "other", and where they came from if they want to say."""
    client.force_login(_user("x@example.com"))
    client.post("/gallery/training/", {"training": "other", "other": "חבר שלח לי", "next": "/gallery/new/"})
    person = Person.objects.get(user__email="x@example.com")
    assert person.training is None and person.training_other == "חבר שלח לי" and person.answered_training


def test_a_closed_training_leaves_the_list(client, db):
    """REQ-G.91"""
    t = Training.objects.first()
    t.is_open = False
    t.save()
    client.force_login(_user("y@example.com"))
    page = client.get("/gallery/training/").content.decode()
    assert t.name_he not in page


def test_liking_and_commenting_never_ask_the_training(client, db):
    """REQ-G.4: only posting asks."""
    owner = _person(_user("o@example.com", "Own"))
    card = _card(owner)
    client.force_login(_user("z@example.com"))
    assert client.post(f"/gallery/api/exhibits/{card.pk}/like/").json()["on"] is True
    assert client.post("/gallery/api/comments/", {"exhibit": card.pk, "body": "שלום"}, content_type="application/json").status_code == 201
    assert not Person.objects.get(user__email="z@example.com").answered_training


def test_the_training_never_leaks(client, people):
    """REQ-G.5: the person and Avi only."""
    dana = people["dana"]
    dana.training_other = "SECRET-ORIGIN"
    dana.save()
    name_he, name_en = dana.training.name_he, dana.training.name_en
    card = _card(dana)
    public = [
        client.get("/gallery/").content.decode(),
        client.get(f"/gallery/e/{card.pk}/").content.decode(),
        client.get(f"/gallery/u/{dana.slug}/").content.decode(),
        client.get("/gallery/api/persons/").content.decode(),
        client.get(f"/gallery/api/persons/{dana.slug}/").content.decode(),
        client.get("/gallery/api/exhibits/").content.decode(),
    ]
    client.force_login(people["omer"].user)
    public += [client.get(f"/gallery/u/{dana.slug}/").content.decode(),
               client.get("/gallery/api/persons/").content.decode()]
    for body in public:
        assert name_he not in body and name_en not in body and "SECRET-ORIGIN" not in body and '"training"' not in body
    # Herself, and Avi.
    client.force_login(dana.user)
    assert client.get("/gallery/api/persons/me/").json()["training_other"] == "SECRET-ORIGIN"
    client.force_login(people["avi"].user)
    assert client.get(f"/gallery/api/persons/{dana.slug}/").json()["training_other"] == "SECRET-ORIGIN"


# ------------------------------------------------------------ pages


def test_hang_a_page_with_topics_and_a_picture(client, people, offline):
    """REQ-G.10, G.11"""
    client.force_login(people["dana"].user)
    ai = Topic.objects.get(slug="ai")
    response = client.post("/gallery/new/", {"title": "צ'אט לבית ספר", "url": "https://dana.github.io/chat/",
                                              "blurb": "", "topics": [ai.pk]})
    card = Exhibit.objects.get(title="צ'אט לבית ספר")
    assert response["Location"] == f"/gallery/e/{card.pk}/"
    assert card.owner == people["dana"] and card.kind == Exhibit.PAGE and list(card.topics.all()) == [ai]
    assert card.shot_status == Exhibit.OK and offline == ["https://dana.github.io/chat/"]
    picture = client.get(f"/gallery/files/{card.shot.name}")
    assert picture.status_code == 200 and picture["Content-Type"] == "image/jpeg"
    client.logout()
    assert client.get(f"/gallery/files/{card.shot.name}").status_code == 200  # public, like the card


def test_only_http_links(client, people):
    """REQ-G.10"""
    client.force_login(people["dana"].user)
    response = client.post("/gallery/new/", {"title": "x", "url": "javascript:alert(1)"})
    assert response.status_code == 200 and not Exhibit.objects.exists()
    api = client.post("/gallery/api/exhibits/", {"title": "x", "url": "ftp://x.io/"}, content_type="application/json")
    assert api.status_code == 400


def test_links_are_safe_to_follow(client, people):
    """REQ-G.13"""
    card = _card(people["dana"])
    for path in ("/gallery/", f"/gallery/e/{card.pk}/"):
        body = client.get(path).content.decode()
        links = re.findall(r'<a [^>]*href="https://dana\.github\.io/mortgage/"[^>]*>', body)
        assert links and all('target="_blank"' in a and 'rel="noopener noreferrer"' in a for a in links)
        assert "<iframe" not in body


def test_owner_edits_and_others_cannot(client, people):
    """REQ-G.12"""
    card = _card(people["dana"])
    client.force_login(people["omer"].user)
    assert client.get(f"/gallery/e/{card.pk}/edit/").status_code == 404
    assert client.patch(f"/gallery/api/exhibits/{card.pk}/", {"title": "x"}, content_type="application/json").status_code == 403
    assert client.delete(f"/gallery/api/exhibits/{card.pk}/").status_code == 403
    client.force_login(people["dana"].user)
    client.post(f"/gallery/e/{card.pk}/edit/", {"action": "save", "title": "מחשבון 2", "url": card.url})
    card.refresh_from_db()
    assert card.title == "מחשבון 2"
    client.post(f"/gallery/e/{card.pk}/edit/", {"action": "delete"})
    assert not Exhibit.objects.filter(pk=card.pk).exists()


def test_avi_deletes_anything(client, people):
    """REQ-G.90"""
    card = _card(people["dana"])
    note = Comment.objects.create(exhibit=card, author=people["omer"], body="ספאם")
    client.force_login(people["avi"].user)
    assert client.delete(f"/gallery/api/comments/{note.pk}/").status_code == 204
    note.refresh_from_db()
    assert note.deleted
    client.post(f"/gallery/e/{card.pk}/edit/", {"action": "delete"})
    assert not Exhibit.objects.filter(pk=card.pk).exists()


def test_bkm_cards_are_avis(client, people):
    """REQ-G.80"""
    client.force_login(people["dana"].user)
    form = client.get("/gallery/new/").content.decode()
    assert 'name="kind"' not in form
    client.post("/gallery/new/", {"kind": "bkm", "title": "x", "url": "https://babook.co.il/bkm/x/"})
    assert Exhibit.objects.get(title="x").kind == Exhibit.PAGE
    api = client.post("/gallery/api/exhibits/", {"kind": "bkm", "title": "y", "url": "https://babook.co.il/bkm/y/"},
                      content_type="application/json")
    assert api.status_code == 403
    assert client.post("/gallery/api/exhibits/", {"kind": "skill", "title": "z"}, content_type="application/json").status_code == 400
    client.force_login(people["avi"].user)
    assert 'name="kind"' in client.get("/gallery/new/").content.decode()
    client.post("/gallery/new/", {"kind": "bkm", "title": "BKM: GitHub Pages", "url": "https://babook.co.il/bkm/pages/"})
    bkm = Exhibit.objects.get(title="BKM: GitHub Pages")
    assert bkm.kind == Exhibit.BKM
    assert "ל-BKM" in client.get("/gallery/?kind=bkm").content.decode()


# ------------------------------------------------------------ likes, stars, comments


def test_a_like_count_is_the_number_of_likes(client, people):
    """REQ-G.20; methodology 20: a count beside a filter on another relation must not inflate."""
    card = _card(people["dana"], topics=["ai", "frontend"])
    for p in people.values():
        Like.objects.create(person=p, exhibit=card)
    Comment.objects.create(exhibit=card, author=people["omer"], body="a")
    Comment.objects.create(exhibit=card, author=people["avi"], body="b")
    page = client.get("/gallery/?topic=ai").content.decode()
    assert re.search(r'data-like="%d"[^>]*>.*?<span class="gl-count">3</span>' % card.pk, page, re.S)
    client.force_login(people["omer"].user)
    r = client.post(f"/gallery/api/exhibits/{card.pk}/like/").json()
    assert r == {"on": False, "count": 2}


def test_stars_are_private_everywhere(client, people):
    """REQ-G.21"""
    card = _card(people["dana"])
    Star.objects.create(person=people["omer"], exhibit=card)
    client.force_login(people["dana"].user)
    assert client.get("/gallery/api/stars/").json() == []
    assert 'aria-pressed="true"' not in client.get("/gallery/?show=stars").content.decode()
    client.force_login(people["omer"].user)
    assert len(client.get("/gallery/api/stars/").json()) == 1
    assert "מחשבון משכנתא" in client.get("/gallery/?show=stars").content.decode()
    client.logout()
    assert client.get("/gallery/api/stars/").status_code in (401, 403)


def test_comments_reply_edit_delete(client, people):
    """REQ-G.22, G.23"""
    card = _card(people["dana"])
    client.force_login(people["omer"].user)
    first = client.post("/gallery/api/comments/", {"exhibit": card.pk, "body": "שאלה"}, content_type="application/json").json()
    client.force_login(people["dana"].user)
    reply = client.post("/gallery/api/comments/", {"exhibit": card.pk, "body": "תשובה", "reply_to": first["id"]},
                        content_type="application/json").json()
    assert reply["reply_to"] == first["id"]
    assert client.patch(f"/gallery/api/comments/{first['id']}/", {"body": "x"}, content_type="application/json").status_code == 403
    assert client.delete(f"/gallery/api/comments/{first['id']}/").status_code == 403
    client.force_login(people["omer"].user)
    client.delete(f"/gallery/api/comments/{first['id']}/")
    page = client.get(f"/gallery/e/{card.pk}/").content.decode()
    assert "התגובה נמחקה" in page and "תשובה" in page and "שאלה" not in page


# ------------------------------------------------------------ people and search


def test_a_page_for_every_person(client, people):
    """REQ-G.30"""
    _card(people["omer"], title="Omer's dashboard", url="https://omer.dev/")
    _card(people["dana"])
    page = client.get(f"/gallery/u/{people['omer'].slug}/").content.decode()
    assert "Omer Katz" in page and "Omer&#x27;s dashboard" in page and "מחשבון משכנתא" not in page
    home = client.get("/gallery/").content.decode()
    assert f'href="/gallery/u/{people["omer"].slug}/"' in home


def test_hebrew_names_get_a_working_page(client, people):
    slug = people["dana"].slug
    assert slug == "דנה-לוי"
    assert client.get(f"/gallery/u/{slug}/").status_code == 200


def test_search_without_ai(client, people):
    """REQ-G.32: title, person's name, topic name in either language, kind, topic."""
    _card(people["dana"], title="מחשבון משכנתא", topics=["data"])
    _card(people["omer"], title="Snake", url="https://omer.dev/snake/", topics=["games"])
    _card(people["avi"], title="BKM: Pages", url="https://babook.co.il/bkm/p/", kind=Exhibit.BKM)

    def titles(query):
        body = client.get("/gallery/?" + query).content.decode()
        return {t for t in ("מחשבון משכנתא", "Snake", "BKM: Pages") if t in body}

    assert titles("q=משכנתא") == {"מחשבון משכנתא"}
    assert titles("q=katz") == {"Snake"}
    assert titles("q=משחקים") == {"Snake"}
    assert titles("q=games") == {"Snake"}
    assert titles("topic=data") == {"מחשבון משכנתא"}
    assert titles("kind=bkm") == {"BKM: Pages"}
    assert titles("q=nothing-like-this") == set()
    assert len(client.get("/gallery/api/exhibits/?q=snake").json()) == 1


def test_settings_name_language_training(client, people):
    """REQ-G.31, G.6"""
    client.force_login(people["omer"].user)
    t = Training.objects.last()
    response = client.post("/gallery/settings/", {"display_name": "Omer K.", "language": "en", "training": t.pk, "training_other": ""})
    assert response.status_code == 302
    p = Person.objects.get(pk=people["omer"].pk)
    assert p.display_name == "Omer K." and p.language == "en" and p.training == t
    page = client.get("/gallery/").content.decode()
    assert '<html lang="en" dir="ltr">' in page and "The gallery" in page


# ------------------------------------------------------------ language


def test_a_visitor_switches_to_english_and_it_sticks(client, db):
    """REQ-G.6"""
    assert '<html lang="he" dir="rtl">' in client.get("/gallery/").content.decode()
    response = client.post("/gallery/language/en/", {"next": "/gallery/?kind=page"})
    assert response["Location"] == "/gallery/?kind=page" and response.cookies["gallery_lang"].value == "en"
    page = client.get("/gallery/").content.decode()
    assert '<html lang="en" dir="ltr">' in page and "Sign in" in page
    assert Person.objects.count() == 0


def test_a_signed_in_choice_follows_the_person(client, people):
    """REQ-G.6: saved on the row, so a fresh browser shows it too."""
    client.force_login(people["dana"].user)
    client.post("/gallery/language/en/", {"next": "/gallery/"})
    assert Person.objects.get(pk=people["dana"].pk).language == "en"
    from django.test import Client

    fresh = Client()
    fresh.force_login(people["dana"].user)
    assert '<html lang="en" dir="ltr">' in fresh.get("/gallery/").content.decode()


def test_the_language_stays_inside_the_gallery(client, db):
    client.post("/gallery/language/en/", {"next": "/gallery/"})
    body = client.get("/").content.decode()
    assert 'lang="en"' not in body[:400]


def test_every_string_in_both_languages_and_every_key_exists():
    for key, entry in STRINGS.items():
        assert entry.get("he") and entry.get("en"), key
    used = set()
    for path in (ROOT / "templates" / "gallery").glob("*.html"):
        used |= set(re.findall(r'{%\s*t\s+["\']([\w.]+)["\']\s*%}', path.read_text(encoding="utf-8")))
    for path in (ROOT / "gallery").glob("*.py"):
        used |= set(re.findall(r'text\(\s*"([\w.]+)"', path.read_text(encoding="utf-8")))
    used |= {"error.404", "error.403", "error.500"}
    assert used and not (used - set(STRINGS)), sorted(used - set(STRINGS))


# ------------------------------------------------------------ the frame and the walls


def test_its_own_frame(client, db):
    """REQ-G.102, Rule 3: no babook chrome, no link out."""
    body = client.get("/gallery/").content.decode()
    assert "gl-bar" in body and "gallery/gallery.css" in body
    assert 'href="/"' not in body and "cohort.css" not in body and "base.html" not in body


def test_peoples_text_takes_its_own_direction(client, people):
    """Methodology 30: "BKM: GitHub Pages מאפס" read backwards on a Hebrew page
    until people's text got dir="auto" (found by eye, 2026-11-09)."""
    card = _card(people["avi"], title="BKM: GitHub Pages מאפס", url="https://babook.co.il/bkm/", kind=Exhibit.BKM)
    card.blurb = "כרטיס הדגמה."
    card.save()
    Comment.objects.create(exhibit=card, author=people["omer"], body="Nice")
    home = client.get("/gallery/").content.decode()
    assert re.search(r'class="gl-card-title" dir="auto"[^>]*>BKM: GitHub Pages מאפס<', home)
    detail = client.get(f"/gallery/e/{card.pk}/").content.decode()
    assert '<h1 class="gl-h1" dir="auto">BKM: GitHub Pages מאפס</h1>' in detail
    assert '<p class="gl-blurb" dir="auto">' in detail and '<p class="gl-note-body" dir="auto">Nice' in detail


def test_errors_stay_inside(client, db):
    response = client.get("/gallery/e/999999/")
    assert response.status_code == 404 and "gl-bar" in response.content.decode()


def test_files_only_pictures_from_the_shots_folder(client, db, settings):
    (Path(settings.GALLERY_FILES_DIR) / "shots").mkdir(parents=True, exist_ok=True)
    (Path(settings.GALLERY_FILES_DIR) / "shots" / "x.txt").write_text("hello")
    for path in ("shots/x.txt", "../mysite/settings.py", "shots/../../x.jpg", "other/x.jpg"):
        assert client.get(f"/gallery/files/{path}").status_code == 404


def test_the_seed_is_one_time(db):
    """Methodology: a seed never touches a row that exists, so Avi's edits survive."""
    seed = importlib.import_module("gallery.migrations.0002_seed_trainings_topics").seed
    t = Training.objects.get(name_en="Technion semester course")
    t.name_he = "שם שאבי שינה"
    t.save()
    Topic.objects.filter(slug="games").delete()
    n_trainings = Training.objects.count()
    seed(django_apps, None)
    seed(django_apps, None)
    t.refresh_from_db()
    assert t.name_he == "שם שאבי שינה"
    assert Training.objects.count() == n_trainings
    assert Topic.objects.filter(slug="games").count() == 1  # a missing row comes back once
    assert Training.objects.count() == 5 and Topic.objects.count() == 12


def test_full_rest_api_routes(client, people):
    """REQ-G.103, Rule 6"""
    root = client.get("/gallery/api/").json()
    assert set(root) == {"persons", "trainings", "topics", "exhibits", "likes", "stars", "comments",
                         "skills", "skillchats", "aicalls", "strikes"}
    client.force_login(people["dana"].user)
    assert client.post("/gallery/api/topics/", {"slug": "x", "name_he": "x", "name_en": "x"}).status_code == 403
    assert client.post("/gallery/api/trainings/", {"name_he": "x", "name_en": "x"}).status_code == 403
    client.force_login(people["avi"].user)
    assert client.post("/gallery/api/topics/", {"slug": "x", "name_he": "x", "name_en": "x"}).status_code == 201
