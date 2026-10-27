"""bkm, SPR-B.2: the public exhibition of projects. docs/bkm/spec.md ch. 5.

Traces REQ-B.30 to B.36. The image safety check is the site's shared one,
which may call a free outside API; every test here replaces it (mistake 47).
"""

import io
import re

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from bkm.models import Bkm, Project, ProjectComment, ProjectLike, Reader

pytestmark = pytest.mark.bkm

PASSWORD = "bkm-pass-7731"
HEBREW = re.compile(r"[֐-׿]")


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path, monkeypatch):
    from bkm import images

    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(images, "safe", lambda data, user=None: (True, ""))


def _user(email, superuser=False, first=""):
    make = User.objects.create_superuser if superuser else User.objects.create_user
    return make(email, email, PASSWORD, first_name=first)


def _photo(size=(2400, 1800), fmt="JPEG", name="p.jpg", exif=True):
    from PIL import Image

    out = io.BytesIO()
    img = Image.new("RGB", size, (30, 120, 200))
    kw = {}
    if exif and fmt == "JPEG":
        ex = Image.Exif()
        ex[0x8825] = {2: (32.0, 4.0, 0.0)}  # GPS: a phone's location
        kw["exif"] = ex.tobytes()
    img.save(out, fmt, **kw)
    return SimpleUploadedFile(name, out.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture
def world(db):
    avi, dana, eli = _user("avi@example.com", True, "Avi"), _user("dana@example.com", first="Dana"), _user("eli@example.com", first="Eli")
    rd, re_ = Reader.objects.create(user=dana, display_name="Dana Levi"), Reader.objects.create(user=eli, display_name="Eli Cohen")
    kit = Bkm.objects.get(slug="single-button-kit")
    flappy = Project.objects.create(owner=rd, title="Flappy on an OLED", kind="video", url="https://youtu.be/dQw4w9WgXcQ",
                                    bkm=kit, topic="electronics", purpose="fun", tags="esp32, oled, game",
                                    description="A one-button game on a tiny screen.")
    shop = Project.objects.create(owner=re_, title="Class marketplace", kind="site", url="https://eli.example.com/shop/",
                                  bkm=Bkm.objects.get(slug="full-stack"), topic="web", purpose="teaching")
    return {"avi": avi, "dana": dana, "eli": eli, "rd": rd, "re": re_, "flappy": flappy, "shop": shop, "kit": kit}


def _card(html, pk):
    return html.split(f'id="p{pk}"', 1)[1].split("</article>", 1)[0]


# ------------------------------------------------------------ the exhibition


def test_a_visitor_sees_the_cards_and_pictures_and_nothing_opens(client, world):
    """REQ-B.30, B.32"""
    html = client.get("/bkm/projects/").content.decode()
    card = _card(html, world["flappy"].pk)
    assert "Flappy on an OLED" in card and "Dana Levi" in card
    assert 'src="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"' in card
    assert "data-gate" in card and "data-embed" not in card and "data-plike" not in card
    assert "youtu.be" not in html and "youtube.com/watch" not in html
    shop = _card(html, world["shop"].pk)
    assert "s0.wp.com/mshots/v1/" in shop and 'href="https://eli.example.com/shop/"' not in shop
    assert client.get(f"/bkm/projects/{world['flappy'].pk}/").status_code == 302


def test_signed_in_a_video_plays_in_its_card_and_goes_full_screen(client, world):
    """REQ-B.32"""
    client.force_login(world["eli"])
    card = _card(client.get("/bkm/projects/").content.decode(), world["flappy"].pk)
    assert 'data-embed="dQw4w9WgXcQ"' in card and 'data-full="dQw4w9WgXcQ"' in card
    page = client.get(f"/bkm/projects/{world['flappy'].pk}/").content.decode()
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in page and "allowfullscreen" in page
    shop = _card(client.get("/bkm/projects/").content.decode(), world["shop"].pk)
    assert 'href="https://eli.example.com/shop/" target="_blank" rel="noopener noreferrer"' in shop


def test_the_exhibition_is_english(client, world):
    client.force_login(world["dana"])
    ProjectComment.objects.create(project=world["flappy"], author=world["re"], body="Nice!")
    for path in ("/bkm/projects/", f"/bkm/projects/{world['flappy'].pk}/", "/bkm/projects/new/",
                 f"/bkm/projects/{world['flappy'].pk}/edit/", "/bkm/projects/?q=nothing-matches"):
        assert not HEBREW.search(client.get(path).content.decode()), path


# ------------------------------------------------------------ pinning a project


def test_anyone_signed_in_pins_a_video_a_site_or_a_photo(client, world):
    """REQ-B.31"""
    client.force_login(world["dana"])
    r = client.post("/bkm/projects/new/", {"kind": "video", "title": "Robot dog walks", "url": "https://www.youtube.com/watch?v=aircAruvnKk",
                                           "topic": "robotics", "tags": "Servo, ESP32, servo"})
    dog = Project.objects.get(title="Robot dog walks")
    assert r["Location"] == f"/bkm/projects/{dog.pk}/"
    assert dog.youtube_id == "aircAruvnKk" and dog.owner == world["rd"] and dog.tags == "servo, esp32"
    client.post("/bkm/projects/new/", {"kind": "site", "title": "My portfolio", "url": "https://dana.example.com/", "topic": "web"})
    client.post("/bkm/projects/new/", {"kind": "image", "title": "Soldered", "topic": "electronics", "image": _photo()})
    photo = Project.objects.get(title="Soldered")
    from PIL import Image

    with Image.open(photo.image.path) as img:
        assert max(img.size) == 1600, "made small"
        assert not img.getexif().get(0x8825), "where it was taken is gone"
    assert Project.objects.count() == 5


def test_a_project_must_be_what_it_says(client, world):
    client.force_login(world["dana"])
    before = Project.objects.count()
    client.post("/bkm/projects/new/", {"kind": "video", "title": "Not youtube", "url": "https://vimeo.com/123", "topic": "other"})
    client.post("/bkm/projects/new/", {"kind": "site", "title": "No link", "topic": "other"})
    client.post("/bkm/projects/new/", {"kind": "site", "title": "Script", "url": "javascript:alert(1)", "topic": "other"})
    client.post("/bkm/projects/new/", {"kind": "image", "title": "No photo", "topic": "other"})
    bad = SimpleUploadedFile("x.jpg", b"not a photo", content_type="image/jpeg")
    client.post("/bkm/projects/new/", {"kind": "image", "title": "Bad photo", "topic": "other", "image": bad})
    assert Project.objects.count() == before


def test_an_unsafe_photo_is_refused(client, world, monkeypatch):
    from bkm import images

    monkeypatch.setattr(images, "safe", lambda data, user=None: (False, "flagged"))
    client.force_login(world["dana"])
    r = client.post("/bkm/projects/new/", {"kind": "image", "title": "Bad", "topic": "other", "image": _photo()})
    assert not Project.objects.filter(title="Bad").exists()
    assert "cannot be shown here" in r.content.decode()


def test_only_the_owner_or_avi_changes_a_project(client, world):
    flappy = world["flappy"]
    client.force_login(world["eli"])
    assert client.get(f"/bkm/projects/{flappy.pk}/edit/").status_code == 404
    client.post(f"/bkm/projects/{flappy.pk}/edit/", {"action": "delete"})
    assert Project.objects.filter(pk=flappy.pk).exists()
    assert "bm-project-edit" not in client.get(f"/bkm/projects/{flappy.pk}/").content.decode()
    client.force_login(world["dana"])
    client.post(f"/bkm/projects/{flappy.pk}/edit/", {"kind": "video", "title": "Flappy v2", "url": flappy.url, "topic": "games"})
    flappy.refresh_from_db()
    assert flappy.title == "Flappy v2" and flappy.topic == "games"
    client.force_login(world["avi"])
    client.post(f"/bkm/projects/{flappy.pk}/edit/", {"action": "delete"})
    assert not Project.objects.filter(pk=flappy.pk).exists()


def test_a_bkm_page_points_to_what_was_made_with_it(client, world):
    client.force_login(world["eli"])
    html = client.get("/bkm/single-button-kit/").content.decode()
    assert 'href="/bkm/projects/?bkm=single-button-kit">1 project made with it</a>' in html
    assert 'href="/bkm/projects/new/?bkm=single-button-kit"' in html
    form = client.get("/bkm/projects/new/?bkm=single-button-kit").content.decode()
    assert re.search(rf'<option value="{world["kit"].pk}" selected>', form)


# ------------------------------------------------------------ finding a project


def _titles(client, query):
    html = client.get("/bkm/projects/" + query).content.decode()
    return re.findall(r'class="bm-ptitle">\s*(?:<a[^>]*>|<button[^>]*>)([^<]+)<', html)


def test_search_and_filters(client, world):
    """REQ-B.35: words, a BKM, a topic, a kind, a reason; no AI."""
    Project.objects.create(owner=world["rd"], title="Pocket oscilloscope", kind="site", url="https://o.example/",
                           topic="electronics", purpose="tool", tags="scope")
    assert _titles(client, "?q=oled") == ["Flappy on an OLED"]           # a tag
    assert _titles(client, "?q=tiny+screen") == ["Flappy on an OLED"]    # the description, every word
    assert _titles(client, "?q=eli") == ["Class marketplace"]             # the maker
    assert _titles(client, "?bkm=full-stack") == ["Class marketplace"]
    assert set(_titles(client, "?topic=electronics")) == {"Flappy on an OLED", "Pocket oscilloscope"}
    assert _titles(client, "?kind=video") == ["Flappy on an OLED"]
    assert _titles(client, "?purpose=teaching") == ["Class marketplace"]
    assert _titles(client, "?topic=electronics&kind=site") == ["Pocket oscilloscope"]
    html = client.get("/bkm/projects/?q=zzz").content.decode()
    assert "Nothing matches" in html


def test_sort_by_likes_and_by_conversation(client, world):
    """REQ-B.35: popularity."""
    for r in (world["rd"], world["re"]):
        ProjectLike.objects.create(reader=r, project=world["shop"])
    ProjectLike.objects.create(reader=world["re"], project=world["flappy"])
    for _ in range(3):
        ProjectComment.objects.create(project=world["flappy"], author=world["re"], body="Q")
    ProjectComment.objects.create(project=world["shop"], author=world["re"], body="gone", deleted_at="2026-10-27T10:00:00Z")
    assert _titles(client, "?sort=liked") == ["Class marketplace", "Flappy on an OLED"]
    assert _titles(client, "?sort=talked") == ["Flappy on an OLED", "Class marketplace"]
    card = _card(client.get("/bkm/projects/?sort=liked").content.decode(), world["shop"].pk)
    assert re.search(r">2</span>", card), "two likes, counted once each"


# ------------------------------------------------------------ likes and the thread


def test_likes_and_the_thread(client, world):
    """REQ-B.33, B.34"""
    pk = world["flappy"].pk
    assert client.post(f"/bkm/api/projects/{pk}/like/").status_code == 403
    client.force_login(world["eli"])
    assert client.post(f"/bkm/api/projects/{pk}/like/").json() == {"on": True, "count": 1}
    client.post(f"/bkm/projects/{pk}/", {"body": "Which display is it?"})
    q = ProjectComment.objects.get()
    client.force_login(world["dana"])
    assert client.post(f"/bkm/api/projects/{pk}/like/").json() == {"on": True, "count": 2}
    client.post(f"/bkm/projects/{pk}/", {"body": "A 0.96 inch SSD1306.", "reply_to": q.pk})
    a = ProjectComment.objects.get(body="A 0.96 inch SSD1306.")
    assert a.reply_to == q
    html = client.get(f"/bkm/projects/{pk}/").content.decode()
    note = html.split(f'id="c{a.pk}"', 1)[1].split("</article>", 1)[0]
    assert "Which display is it?" in note and 'class="bm-quote"' in note
    client.post(f"/bkm/projects/{pk}/", {"action": "delete", "comment": q.pk})
    q.refresh_from_db()
    assert q.deleted_at is None, "Dana cannot delete Eli's comment"


# ------------------------------------------------------------ the API


def test_the_api_reads_for_all_and_writes_for_the_owner(client, world):
    """REQ-B.36, Rule 6"""
    data = client.get("/bkm/api/projects/?bkm=single-button-kit").json()
    assert [d["title"] for d in data] == ["Flappy on an OLED"] and "url" not in data[0]
    assert client.post("/bkm/api/projects/", {"kind": "site", "title": "x", "url": "https://x.example/"}).status_code == 403
    client.force_login(world["eli"])
    r = client.post("/bkm/api/projects/", {"kind": "site", "title": "API site", "url": "https://x.example/", "topic": "web"})
    assert r.status_code == 201 and Project.objects.get(title="API site").owner == world["re"]
    assert client.post("/bkm/api/projects/", {"kind": "video", "title": "v", "url": "https://x.example/"}).status_code == 400
    r = client.post("/bkm/api/projects/", {"kind": "image", "title": "API photo", "topic": "art", "image": _photo()})
    assert r.status_code == 201
    from PIL import Image

    with Image.open(Project.objects.get(title="API photo").image.path) as img:
        assert max(img.size) == 1600
    fl = world["flappy"].pk
    assert client.patch(f"/bkm/api/projects/{fl}/", {"title": "mine now"}, content_type="application/json").status_code == 403
    assert client.delete(f"/bkm/api/projects/{fl}/").status_code == 403
    assert client.get("/bkm/api/project-comments/").status_code == 200
    client.logout()
    assert client.get("/bkm/api/project-comments/").status_code == 403
