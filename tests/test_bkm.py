"""bkm, the BKM gateway: the wall, the gate, the conversation, the API, and
Avi's chat command. docs/bkm/spec.md.
"""

import re
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from bkm.models import Bkm, Comment, Like, Reader, Star

pytestmark = pytest.mark.bkm

PASSWORD = "bkm-pass-7731"
HEBREW = re.compile(r"[֐-׿]")


@pytest.fixture(autouse=True)
def media(settings, tmp_path, monkeypatch):
    from bkm import images

    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(images, "safe", lambda data, user=None: (True, ""))  # mistake 47: no outside call


def _user(email, superuser=False, first=""):
    make = User.objects.create_superuser if superuser else User.objects.create_user
    return make(email, email, PASSWORD, first_name=first)


@pytest.fixture
def world(db):
    return {
        "avi": _user("avi.salmon@gmail.com", superuser=True, first="Avi"),
        "dana": _user("dana@example.com", first="Dana"),
        "eli": _user("eli@example.com", first="Eli"),
        "fs": Bkm.objects.get(slug="full-stack"),
        "kit": Bkm.objects.get(slug="single-button-kit"),
        "de10": Bkm.objects.get(slug="de10-lite"),
    }


def _card(html, slug):
    return html.split(f'id="{slug}"', 1)[1].split("</article>", 1)[0]


# ------------------------------------------------------------ the wall


def test_the_first_three_bkms_are_on_the_wall_in_order(db):
    """REQ-B.21: Avi's finished BKMs, put there once by a migration."""
    assert [b.slug for b in Bkm.objects.all()] == ["full-stack", "single-button-kit", "de10-lite"]
    assert not Bkm.objects.filter(slug__icontains="nano").exists(), "De10NanoBKM is not started"
    for b in Bkm.objects.all():
        assert b.page_url.startswith("https://avisalmon.github.io/") and b.repo_url.startswith("https://github.com/avisalmon/")
        assert b.tagline and b.name.endswith("BKM")


def test_a_visitor_sees_the_wall_and_nothing_opens(client, world):
    """REQ-B.1, B.2: the message and the cards, but no way out of them."""
    r = client.get("/bkm/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Best Known Methods" in html and "Hi, what do I do now?" in html
    for b in (world["fs"], world["kit"], world["de10"]):
        card = _card(html, b.slug)
        assert b.name in card and b.tagline in card
        assert b.page_url not in card and b.repo_url not in card
        assert "data-gate" in card and "data-like" not in card and "data-star" not in card
    assert "github.io" not in html and "github.com" not in html
    assert 'id="bm-gate"' in html


def test_the_gate_puts_google_first_and_the_password_folded(client, db):
    """REQ-B.3"""
    html = client.get("/bkm/").content.decode()
    gate = html.split('id="bm-gate"', 1)[1].split("</dialog>", 1)[0]
    assert gate.index("Continue with Google") < gate.index("<details")
    assert 'href="/accounts/google/login/?process=login&amp;next=/bkm/"' in gate
    assert 'name="password"' in gate.split("<details", 1)[1]
    login = client.get("/bkm/login/?next=/bkm/%23de10-lite").content.decode()
    assert "next=/bkm/%23de10-lite" in login and login.index("Continue with Google") < login.index("<details")


def test_signed_in_the_cards_open_and_count(client, world):
    """REQ-B.10 to B.13"""
    Like.objects.create(reader=Reader.objects.create(user=world["eli"], display_name="Eli"), bkm=world["kit"])
    client.force_login(world["dana"])
    html = client.get("/bkm/").content.decode()
    card = _card(html, "single-button-kit")
    assert f'href="{world["kit"].page_url}" target="_blank" rel="noopener"' in card
    assert 'data-like="single-button-kit"' in card and 'data-star="single-button-kit"' in card
    assert re.search(r'data-like="single-button-kit"[^>]*aria-pressed="false"', card)
    assert re.search(r'data-count>1<', card)
    assert "data-gate" not in card
    assert 'id="bm-gate"' not in html


def test_the_wall_and_its_pages_are_english(client, world):
    """REQ-B.5, dates included: the site's default language is Hebrew."""
    client.force_login(world["dana"])
    client.post("/bkm/full-stack/", {"body": "A comment, so a date is on the page"})
    for path in ("/bkm/", "/bkm/?starred=1", "/bkm/full-stack/", "/bkm/nope/"):
        assert not HEBREW.search(client.get(path).content.decode()), path
    client.logout()
    for path in ("/bkm/", "/bkm/login/", "/bkm/signup/"):
        assert not HEBREW.search(client.get(path).content.decode()), path


def test_the_wall_never_links_to_babook(client, world):
    """Rule 3: no way from the app to the main site."""
    client.force_login(world["dana"])
    for path in ("/bkm/", "/bkm/full-stack/"):
        html = client.get(path).content.decode()
        hrefs = re.findall(r'href="([^"]+)"', html)
        inside = [h for h in hrefs if h.startswith("/") and not h.startswith(("/bkm/", "/static/", "/media/", "/accounts/google/"))]
        assert inside == [], (path, inside)
        assert "babook.co.il" not in html


# ------------------------------------------------------------ likes and stars


def test_likes_are_public_stars_are_private(client, world):
    """REQ-B.13, B.14"""
    client.force_login(world["dana"])
    assert client.post("/bkm/api/bkms/de10-lite/like/").json() == {"on": True, "count": 1}
    assert client.post("/bkm/api/bkms/de10-lite/star/").json()["on"] is True
    client.force_login(world["eli"])
    assert client.post("/bkm/api/bkms/de10-lite/like/").json() == {"on": True, "count": 2}
    assert client.post("/bkm/api/bkms/de10-lite/like/").json() == {"on": False, "count": 1}
    assert client.get("/bkm/api/stars/").json() == []
    html = client.get("/bkm/?starred=1").content.decode()
    assert 'id="de10-lite"' not in html
    client.force_login(world["dana"])
    html = client.get("/bkm/?starred=1").content.decode()
    assert 'id="de10-lite"' in html and 'id="full-stack"' not in html
    assert Star.objects.count() == 1 and Like.objects.count() == 1


def test_a_visitor_cannot_like_star_or_read_the_thread(client, world):
    assert client.post("/bkm/api/bkms/de10-lite/like/").status_code == 403
    assert client.post("/bkm/api/bkms/de10-lite/star/").status_code == 403
    for route in ("likes", "stars", "comments", "readers"):
        assert client.get(f"/bkm/api/{route}/").status_code == 403, route
    r = client.get("/bkm/de10-lite/")
    assert r.status_code == 302 and r["Location"] == "/bkm/login/?next=/bkm/de10-lite/"


# ------------------------------------------------------------ the conversation


def test_one_thread_with_quoted_replies_edit_and_delete(client, world):
    """REQ-B.15, B.16"""
    client.force_login(world["dana"])
    client.post("/bkm/de10-lite/", {"body": "Does it work with Quartus 23?"})
    q = Comment.objects.get()
    client.force_login(world["eli"])
    r = client.post("/bkm/de10-lite/", {"body": "Yes, I used 23.1.", "reply_to": q.pk})
    a = Comment.objects.get(body="Yes, I used 23.1.")
    assert a.reply_to == q and r["Location"] == f"/bkm/de10-lite/#c{a.pk}"
    html = client.get("/bkm/de10-lite/").content.decode()
    note = html.split(f'id="c{a.pk}"', 1)[1].split("</article>", 1)[0]
    assert 'class="bm-quote"' in note and "Does it work with Quartus 23?" in note

    # Eli cannot touch Dana's comment; Dana edits and deletes her own.
    client.post("/bkm/de10-lite/", {"action": "edit", "comment": q.pk, "body": "hacked"})
    client.post("/bkm/de10-lite/", {"action": "delete", "comment": q.pk})
    q.refresh_from_db()
    assert q.body == "Does it work with Quartus 23?" and q.deleted_at is None
    client.force_login(world["dana"])
    client.post("/bkm/de10-lite/", {"action": "edit", "comment": q.pk, "body": "Does it work with Quartus 23.1?"})
    q.refresh_from_db()
    assert q.body.endswith("23.1?") and q.edited_at
    client.post("/bkm/de10-lite/", {"action": "delete", "comment": q.pk})
    q.refresh_from_db()
    assert q.deleted_at
    html = client.get("/bkm/de10-lite/").content.decode()
    assert "Quartus 23.1?" not in html and "This comment was deleted." in html

    # A reply to a comment of another BKM is not a reply.
    client.post("/bkm/full-stack/", {"body": "Elsewhere", "reply_to": a.pk})
    assert Comment.objects.get(body="Elsewhere").reply_to is None


def test_avi_deletes_any_comment(client, world):
    reader = Reader.objects.create(user=world["dana"], display_name="Dana")
    c = Comment.objects.create(bkm=world["fs"], author=reader, body="spam")
    client.force_login(world["avi"])
    assert "Delete" in client.get("/bkm/full-stack/").content.decode()
    client.post("/bkm/full-stack/", {"action": "delete", "comment": c.pk})
    c.refresh_from_db()
    assert c.deleted_at


def test_the_page_shows_this_bkms_own_commands(client, world):
    """REQ-B.11"""
    client.force_login(world["dana"])
    html = client.get("/bkm/de10-lite/").content.decode()
    assert "git clone https://github.com/avisalmon/De10LiteBKM.git" in html
    assert "code De10LiteBKM" in html
    assert f'href="{world["de10"].page_url}" target="_blank"' in html


def test_a_comment_is_text_not_html(client, world):
    client.force_login(world["dana"])
    client.post("/bkm/full-stack/", {"body": "<script>alert(1)</script>"})
    html = client.get("/bkm/full-stack/").content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


# ------------------------------------------------------------ only Avi adds BKMs


def test_only_avi_changes_bkms_through_the_api(client, world):
    """REQ-B.20, Rule 6"""
    body = {"slug": "robo-dog", "name": "RoboDogBKM", "tagline": "A dog.", "repo_url": "https://github.com/a/b",
            "page_url": "https://a.github.io/b/"}
    assert client.post("/bkm/api/bkms/", body, content_type="application/json").status_code == 403
    client.force_login(world["dana"])
    assert client.post("/bkm/api/bkms/", body, content_type="application/json").status_code == 403
    assert client.patch("/bkm/api/bkms/full-stack/", {"name": "x"}, content_type="application/json").status_code == 403
    assert client.delete("/bkm/api/bkms/full-stack/").status_code == 403
    client.force_login(world["avi"])
    assert client.post("/bkm/api/bkms/", body, content_type="application/json").status_code == 201
    assert client.patch("/bkm/api/bkms/robo-dog/", {"is_published": False}, content_type="application/json").status_code == 200


def test_a_hidden_bkm_is_seen_by_avi_only(client, world):
    world["kit"].is_published = False
    world["kit"].save()
    assert 'id="single-button-kit"' not in client.get("/bkm/").content.decode()
    client.force_login(world["dana"])
    assert 'id="single-button-kit"' not in client.get("/bkm/").content.decode()
    assert client.get("/bkm/single-button-kit/").status_code == 404
    assert client.post("/bkm/api/bkms/single-button-kit/like/").status_code == 404
    assert client.get("/bkm/api/bkms/single-button-kit/").status_code == 404
    client.force_login(world["avi"])
    html = client.get("/bkm/").content.decode()
    assert "Hidden: only you see it" in _card(html, "single-button-kit")


def test_a_visitor_reads_the_wall_from_the_api_without_its_links(client, world):
    data = client.get("/bkm/api/bkms/").json()
    assert [d["slug"] for d in data] == ["full-stack", "single-button-kit", "de10-lite"]
    assert all("page_url" not in d and "repo_url" not in d for d in data)
    client.force_login(world["dana"])
    assert client.get("/bkm/api/bkms/de10-lite/").json()["page_url"] == world["de10"].page_url


def test_every_model_has_an_endpoint():
    """Rule 6, as a guard."""
    from django.apps import apps

    from bkm.api import ROUTES

    assert {m for _p, _v, m in ROUTES} == set(apps.get_app_config("bkm").get_models())


def test_the_reader_is_made_on_first_use_and_names_the_comment(client, world):
    client.force_login(world["dana"])
    assert not Reader.objects.filter(user=world["dana"]).exists()
    client.post("/bkm/full-stack/", {"body": "Hello"})
    assert Reader.objects.get(user=world["dana"]).display_name == "Dana"
    assert client.get("/bkm/api/readers/").json()[0]["display_name"] == "Dana"


# ------------------------------------------------------------ signing in


def test_sign_in_comes_back_to_the_card(client, world):
    r = client.post("/bkm/login/", {"username": "dana@example.com", "password": PASSWORD, "next": "/bkm/#de10-lite"})
    assert r.status_code == 302 and r["Location"] == "/bkm/#de10-lite"
    client.logout()
    r = client.post("/bkm/login/", {"username": "dana@example.com", "password": PASSWORD, "next": "https://evil.example/"})
    assert r["Location"] == "/bkm/"


def test_sign_up_makes_one_shared_account(client, db):
    r = client.post("/bkm/signup/", {"name": "Noa Barak", "email": "noa@example.com", "password1": "noa-long-pass-6612",
                                     "password2": "noa-long-pass-6612", "next": "/bkm/full-stack/"})
    assert r["Location"] == "/bkm/full-stack/"
    assert User.objects.get(email="noa@example.com").first_name == "Noa"


# ------------------------------------------------------------ the chat command and the seed


def test_avi_adds_a_bkm_from_the_chat(world, monkeypatch, tmp_path):
    """REQ-B.20: no form; the command fills from GitHub once."""
    from bkm.management.commands import bkm as cmd

    monkeypatch.setattr(cmd, "github_facts", lambda url: {
        "name": "RoboDogBKM", "tagline": "Build a robotic dog.", "page_url": "https://avisalmon.github.io/RoboDogBKM/",
        "repo_url": "https://github.com/avisalmon/RoboDogBKM"})
    pic = tmp_path / "dog.jpg"
    from PIL import Image

    Image.new("RGB", (40, 30), (200, 100, 50)).save(pic)
    call_command("bkm", "add", "https://github.com/avisalmon/RoboDogBKM", "--picture", str(pic), stdout=StringIO())
    dog = Bkm.objects.get(slug="robodog")
    assert dog.position == 40 and dog.picture and dog.page_url.endswith("/RoboDogBKM/")
    call_command("bkm", "set", "robodog", "tagline", "A dog that walks.", stdout=StringIO())
    call_command("bkm", "hide", "robodog", stdout=StringIO())
    dog.refresh_from_db()
    assert dog.tagline == "A dog that walks." and not dog.is_published
    with pytest.raises(CommandError):
        call_command("bkm", "add", "https://github.com/avisalmon/RoboDogBKM", stdout=StringIO())
    with pytest.raises(CommandError):
        call_command("bkm", "add", "https://github.com/avisalmon/RoboDogBKM", "--slug", "api", stdout=StringIO())


def test_the_seed_attaches_pictures_once_and_never_over_avis(world):
    """Methodology: seeding is one-time, checked by running it twice."""
    call_command("seed_bkm", stdout=StringIO())
    for b in Bkm.objects.all():
        assert b.picture, b.slug
    fs = Bkm.objects.get(slug="full-stack")
    first = fs.picture.name
    call_command("seed_bkm", stdout=StringIO())
    fs.refresh_from_db()
    assert fs.picture.name == first
    for slug in ("full-stack", "single-button-kit", "de10-lite"):
        assert (Path("bkm/seed_assets") / f"{slug}.jpg").exists()


# ------------------------------------------------------------ Avi's own form (REQ-B.23)


def _jpeg(size=(1200, 900)):
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, (20, 140, 60)).save(out, "JPEG")
    return SimpleUploadedFile("board.jpg", out.getvalue(), content_type="image/jpeg")


def _bkm_post(b, **change):
    data = {"name": b.name, "tagline": b.tagline, "repo_url": b.repo_url, "page_url": b.page_url,
            "position": b.position, "is_published": "on"}
    data.update(change)
    return {k: v for k, v in data.items() if v is not None}


def test_only_avi_sees_the_bkm_form(client, world):
    assert client.get("/bkm/full-stack/edit/").status_code == 302          # sign in first
    client.force_login(world["dana"])
    assert client.get("/bkm/full-stack/edit/").status_code == 404
    assert client.get("/bkm/new/").status_code == 404
    client.post("/bkm/full-stack/edit/", _bkm_post(world["fs"], name="Hacked"))
    client.post("/bkm/full-stack/edit/", {"action": "delete"})
    assert Bkm.objects.get(slug="full-stack").name == "FullStackBKM"
    for path in ("/bkm/", "/bkm/full-stack/"):
        html = client.get(path).content.decode()
        assert "/edit/" not in html and 'id="bm-add-bkm"' not in html


def test_avi_changes_text_links_and_picture_with_no_deploy(client, world):
    client.force_login(world["avi"])
    html = client.get("/bkm/").content.decode()
    assert 'href="/bkm/de10-lite/edit/"' in _card(html, "de10-lite") and 'id="bm-add-bkm"' in html
    r = client.post("/bkm/de10-lite/edit/", _bkm_post(world["de10"], tagline="FFT on an LCD, with an AI beside you.",
                                                      picture=_jpeg((2400, 1800))))
    assert r.status_code == 302 and r["Location"] == "/bkm/#de10-lite"
    de10 = Bkm.objects.get(slug="de10-lite")
    assert de10.tagline == "FFT on an LCD, with an AI beside you." and de10.picture
    from PIL import Image

    with Image.open(de10.picture.path) as img:
        assert max(img.size) == 1600
    assert "FFT on an LCD" in client.get("/bkm/").content.decode()
    client.post("/bkm/de10-lite/edit/", _bkm_post(de10, page_url="javascript:alert(1)"))
    assert Bkm.objects.get(slug="de10-lite").page_url.startswith("https://")


def test_avi_adds_hides_and_removes_a_bkm(client, world):
    client.force_login(world["avi"])
    new = {"slug": "robo-dog", "name": "RoboDogBKM", "tagline": "Build a robotic dog.",
           "repo_url": "https://github.com/avisalmon/RoboDogBKM", "page_url": "https://avisalmon.github.io/RoboDogBKM/",
           "position": "", "is_published": "on", "picture": _jpeg()}
    client.post("/bkm/new/", new)
    dog = Bkm.objects.get(slug="robo-dog")
    assert dog.position == 40 and dog.picture
    client.post("/bkm/new/", {**new, "slug": "projects", "picture": _jpeg()})
    assert not Bkm.objects.filter(slug="projects").exists()
    client.post("/bkm/robo-dog/edit/", _bkm_post(dog, is_published=None))
    assert not Bkm.objects.get(slug="robo-dog").is_published
    client.force_login(world["dana"])
    assert 'id="robo-dog"' not in client.get("/bkm/").content.decode()
    client.force_login(world["avi"])
    client.post("/bkm/robo-dog/edit/", {"action": "delete"})
    assert not Bkm.objects.filter(slug="robo-dog").exists()


def _size(fieldfile):
    from PIL import Image

    with Image.open(fieldfile.path) as img:
        return img.size


def test_avi_rotates_a_picture_new_or_already_saved(client, world):
    """REQ-B.24: rotate before saving; with no new file, rotate the one on
    the card. Degrees are clockwise; anything but 0/90/180/270 is 0."""
    client.force_login(world["avi"])
    de10 = world["de10"]
    client.post("/bkm/de10-lite/edit/", _bkm_post(de10, picture=_jpeg((1200, 900)), rotate="90"))
    de10.refresh_from_db()
    assert _size(de10.picture) == (900, 1200)
    client.post("/bkm/de10-lite/edit/", _bkm_post(de10, rotate="270"))
    de10.refresh_from_db()
    assert _size(de10.picture) == (1200, 900), "turned back, with no new upload"
    name = de10.picture.name
    client.post("/bkm/de10-lite/edit/", _bkm_post(de10, rotate="45"))
    de10.refresh_from_db()
    assert de10.picture.name == name, "a bad angle does nothing"
    client.post("/bkm/de10-lite/edit/", _bkm_post(de10, tagline="Only the words changed"))
    de10.refresh_from_db()
    assert de10.picture.name == name, "saving without rotate keeps the picture as it is"


def test_a_project_photo_can_be_rotated_too(client, world):
    from bkm.models import Project

    client.force_login(world["dana"])
    client.post("/bkm/projects/new/", {"kind": "image", "title": "Sideways", "topic": "other",
                                       "image": _jpeg((1200, 900)), "rotate": "90"})
    p = Project.objects.get(title="Sideways")
    assert _size(p.image) == (900, 1200)
    client.post(f"/bkm/projects/{p.pk}/edit/", {"kind": "image", "title": "Sideways", "topic": "other", "rotate": "90"})
    p.refresh_from_db()
    assert _size(p.image) == (1200, 900)


# ------------------------------------------------------------ the stylesheet


def test_every_class_the_markup_uses_is_a_class_the_stylesheet_defines():
    """Mistake 13: an undefined class is silence, not an error."""
    css = Path("static/bkm/bkm.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(bm-[a-z0-9_-]+)", css))
    used = set()
    for path in Path("templates/bkm").rglob("*.html"):
        for classes in re.findall(r'class="([^"]+)"', path.read_text(encoding="utf-8")):
            used |= {c for c in re.sub(r"\{[%{].*?[%}]\}", " ", classes).split() if c.startswith("bm-")}
    assert used <= defined, sorted(used - defined)
