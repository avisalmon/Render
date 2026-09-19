"""SPR-Z.11 — memz: your own photos, by default (docs/memz/backlog.md).

Avi: "the images of the memes are boring. I want every signed-in user to
be able to upload his own images, and whenever he's playing, a random
picture will be chosen from his pictures... as well as all the other
banks. I want a clear interface of upload your own image."

Most of the machinery existed since SPR-Z.5/Z.9 and never reached a
table: it was behind a setting nobody chose, the setting's own pool query
didn't match its label, and the only way in was a profile tab. Spec
references are docs/memz/spec.md rule numbers.
"""

import io
import json

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image

from tests.test_memz_screens import PHONE, browser  # noqa: F401 -- the shared phone fixture

pytestmark = [pytest.mark.sprz11, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


def _png_bytes(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


def _user(name="uploader"):
    return User.objects.create_user(name, email=f"{name}@example.com", password="x")


def _public_images(media_tmp, n=6):
    from memz.models import MemeImage

    out = []
    for i in range(n):
        img = MemeImage(
            owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title=f"pub{i}"
        )
        img.file.save(f"pub{i}.png", ContentFile(_png_bytes((i * 30, 80, 150))), save=True)
        out.append(img)
    return out


def _own_images(user, media_tmp, n=4):
    from memz.models import MemeImage

    out = []
    for i in range(n):
        img = MemeImage(
            owner=user, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED, title=f"own{i}"
        )
        img.file.save(f"own{user.pk}_{i}.png", ContentFile(_png_bytes((200, i * 40, 40))), save=True)
        out.append(img)
    return out


def post(client, url, body=None, token=None):
    headers = {"content_type": "application/json"}
    if token:
        headers["HTTP_X_MEMZ_PLAYER"] = token
    return client.post(url, json.dumps(body or {}), **headers)


# ------------------------------------------- the default actually deals them


def test_a_new_game_mixes_the_players_own_photos_in_without_anyone_choosing_it(client, media_tmp):
    """The heart of it: the engine could already deal seated players'
    uploads (SPR-Z.9), but only when the host went and picked a setting,
    so in practice nobody's photos ever reached a table."""
    from memz.models import Session

    _public_images(media_tmp)
    user = _user("hosty")
    _own_images(user, media_tmp)
    client.force_login(user)

    r = post(client, "/memz/api/sessions/", {"round_count": 1})
    assert r.status_code == 201, r.content
    session = Session.objects.get(code=r.json()["code"])
    assert session.image_source == Session.MIX, "a game no longer defaults to the public bank alone"


def test_mix_really_means_own_plus_the_public_bank(client, media_tmp):
    """The bug under the label: `mix` said "my photos + the public bank"
    on screen and, with no packs chosen, quietly queried the player's own
    images *only* — so the public bank never appeared, and a room where
    nobody had uploaded had an empty pool."""
    from memz import dealing, game
    from memz.models import Session

    public = _public_images(media_tmp)
    user = _user("mixer")
    own = _own_images(user, media_tmp)

    session, host = game.create_session(
        host_user=user, round_count=1, round_seconds=60, vote_seconds=20, image_source=Session.MIX,
    )
    pool_ids = {img.id for img in dealing.pool_for(session)}
    assert {img.id for img in own} <= pool_ids, "the host's own uploads are missing from mix"
    assert {img.id for img in public} <= pool_ids, "the public bank is missing from mix"


def test_mix_with_nobody_signed_in_still_has_the_public_bank_to_deal(client, media_tmp):
    """The same bug's worst case: a guest-hosted room used to end up with
    an empty pool, which is a game that cannot start."""
    from memz import dealing, game
    from memz.models import Session

    public = _public_images(media_tmp)
    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=60, vote_seconds=20, image_source=Session.MIX,
    )
    assert {img.id for img in dealing.pool_for(session)} == {img.id for img in public}


def test_a_joining_players_photos_reach_a_game_a_guest_opened(client, media_tmp):
    """Rule 2.1 used to force a guest-hosted room to the public bank
    alone, which meant a signed-in player's photos played only in rooms a
    signed-in friend happened to open. SPR-Z.11: they play wherever that
    player plays."""
    from memz import dealing, game
    from memz.models import Session

    _public_images(media_tmp)
    joiner = _user("joiner")
    own = _own_images(joiner, media_tmp)

    session, host = game.create_session(host_user=None, round_count=1, round_seconds=60, vote_seconds=20)
    assert session.image_source == Session.MIX
    game.join_session(session, "אורח", user=joiner)

    pool_ids = {img.id for img in dealing.pool_for(session)}
    assert {img.id for img in own} <= pool_ids, "a seated signed-in player's photos never reached the pool"


def test_personal_photos_can_now_be_half_the_game(client, media_tmp):
    """Rule 6.5.3, raised from 30% to 50% — Avi's call. Checked against
    the real dealt history across a played game, not the constant."""
    from memz import game
    from memz.models import Session, Submission

    _public_images(media_tmp, n=10)
    user = _user("halfie")
    _own_images(user, media_tmp, n=10)

    session, host = game.create_session(
        host_user=user, round_count=4, round_seconds=60, vote_seconds=20, image_source=Session.MIX,
    )
    p2 = game.join_session(session, "ב")
    p3 = game.join_session(session, "ג")
    game.start_session(session, host)

    for number in range(1, 5):
        round_obj = game.current_round(session)
        if round_obj is None or round_obj.number != number:
            break
        for player in (host, p2, p3):
            try:
                game.submit_caption(session, player, number, caption_text=f"כיתוב {player.nickname}")
            except game.GameError:
                pass
        round_obj.refresh_from_db()
        if round_obj.status == round_obj.REVEALED:
            game.advance(session, host)
        round_obj.refresh_from_db()
        if round_obj.status == round_obj.DONE:
            game.advance(session, host)

    dealt = Submission.objects.filter(round__session=session, image__isnull=False)
    total = dealt.count()
    personal = dealt.filter(image__owner__isnull=False).count()
    assert total, "no images were dealt at all"
    assert personal > 0, "not one personal photo was dealt in a whole game"
    assert personal / total <= 0.5 + 1e-9, f"personal share {personal}/{total} went over the 50% ceiling"


# --------------------------------------------------- the clear way to upload


def test_the_home_screen_offers_a_signed_in_user_a_way_to_add_photos(client, media_tmp):
    user = _user("homey")
    client.force_login(user)
    body = client.get("/memz/").content.decode()
    assert "data-home-uploader" in body, "no uploader on the home screen"
    assert "התמונות שלכם" in body


def test_the_home_screen_tells_a_guest_what_an_account_buys_instead(client, media_tmp):
    body = client.get("/memz/").content.decode()
    assert "data-home-uploader" not in body, "a guest was offered an upload they cannot make"
    assert "/memz/signup/" in body


def test_the_lobby_carries_an_uploader_for_a_signed_in_player(client, media_tmp):
    """And it lives *outside* the game root: everything inside that div is
    rebuilt from the state on every poll, which would take a half-made
    file selection with it every couple of seconds."""
    from memz import game

    _public_images(media_tmp)
    user = _user("lobbyist")
    client.force_login(user)
    session, host = game.create_session(
        host_user=user, round_count=1, round_seconds=60, vote_seconds=20,
    )
    body = client.get(f"/memz/s/{session.code}/").content.decode()
    assert "data-lobby-uploader" in body, "no uploader in the lobby"
    root_at = body.index("data-game-root")
    uploader_at = body.index("data-lobby-upload")
    assert uploader_at > root_at, "the uploader is inside the poll-rebuilt game root"


def test_the_lobby_uploader_is_not_offered_to_a_guest(client, media_tmp):
    from memz import game

    _public_images(media_tmp)
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=60, vote_seconds=20)
    body = client.get(f"/memz/s/{session.code}/").content.decode()
    assert "data-lobby-uploader" not in body


def test_an_upload_is_tagged_to_its_owner_and_private(client, media_tmp):
    """"Stored in the site and tagged for that user" — it already was, and
    this pins it: an upload belongs to the uploader, is never public bank
    material, and another account cannot see it."""
    from memz.models import MemeImage

    user = _user("tagged")
    other = _user("stranger")
    client.force_login(user)

    r = client.post("/memz/api/images/", {"file": ContentFile(_png_bytes(), name="mine.png")})
    assert r.status_code == 201, r.content
    image = MemeImage.objects.get(pk=r.json()["id"])
    assert image.owner == user
    assert image.visibility == MemeImage.PRIVATE

    client.force_login(other)
    assert client.get(f"/memz/api/images/{image.pk}/").status_code == 404


# ------------------------------------ ACT-Z.15: a phone's camera and files


def test_an_iphone_heic_photo_is_accepted_and_stored_as_a_clean_jpeg(client, media_tmp):
    """ACT-Z.15 (Avi: "it needs to allow images from phone, real camera
    and files"). An iPhone's camera roll is HEIC, and Pillow can't open it
    alone: every such upload used to be refused with "choose JPEG in the
    share sheet". The HEIC bytes here are real, written by the same
    plugin that now reads them."""
    from PIL import Image as PILImage

    from memz import uploads
    from memz.models import MemeImage

    assert uploads.HEIF_SUPPORTED, "pillow-heif is not installed in this environment"
    buf = io.BytesIO()
    PILImage.new("RGB", (640, 480), (120, 60, 200)).save(buf, format="HEIF", quality=80)
    heic = ContentFile(buf.getvalue(), name="IMG_0042.HEIC")
    heic.content_type = "image/heic"

    user = _user("iphone")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": heic})
    assert r.status_code == 201, r.content

    image = MemeImage.objects.get(pk=r.json()["id"])
    with PILImage.open(image.file) as stored:
        assert stored.format == "JPEG", "the upload was not re-encoded to the bank's own format"
        assert stored.size == (640, 480)


def test_the_uploader_offers_the_camera_and_the_gallery_as_real_buttons(browser, live_server, db, media_tmp):
    """The browser's own "Choose Files" control is gone. Two hidden file
    inputs stand behind two buttons in the house style: the camera one
    carries `capture` (what makes a phone open the camera rather than a
    file browser) and is *not* `multiple` (with it set, iOS drops the
    camera option from its sheet); the gallery one is `multiple`."""
    pytest.importorskip("playwright.sync_api")
    from tests.test_memz_screens import PHONE

    _user("shooter")
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/memz/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', "shooter@example.com")
        page.fill('input[name="password"]', "x")
        page.click('form button[type="submit"]')
        page.wait_for_timeout(400)
        page.goto(f"{live_server.url}/memz/", wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        camera = page.locator("[data-home-uploader] input[data-uploader-camera]")
        gallery = page.locator("[data-home-uploader] input[data-uploader-gallery]")
        assert camera.count() == 1 and gallery.count() == 1
        assert camera.get_attribute("capture") is not None, "the camera input has no `capture`"
        assert camera.get_attribute("multiple") is None, "the camera input is `multiple`, which hides the camera on iOS"
        assert gallery.get_attribute("multiple") is not None
        assert page.locator("[data-home-uploader] input[type=file]:visible").count() == 0, (
            "a raw file input is still visible"
        )
        assert page.locator("[data-home-uploader] [data-uploader-take]").count() == 1
        assert page.locator("[data-home-uploader] [data-uploader-pick]").count() == 1
    finally:
        context.close()


# ----------------------------------- ACT-Z.16: not a camera's worth of pixels


def _camera_photo_bytes(w=4032, h=3024):
    """A 12MP phone-shaped photo with real detail. A flat colour would
    compress to almost nothing and prove nothing about storage."""
    import random

    from PIL import ImageDraw, ImageFilter

    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    for y in range(0, h, 4):
        d.rectangle([0, y, w, y + 4], fill=(30 + y * 180 // h, 90 + y * 90 // h, 160 - y * 60 // h))
    for _ in range(900):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.randrange(20, 260)
        d.ellipse([x, y, x + r, y + r], fill=(rnd.randrange(255), rnd.randrange(255), rnd.randrange(255)))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_a_phone_photo_is_stored_at_phone_size_not_camera_size(client, media_tmp):
    """ACT-Z.16 (Avi: "they probably are very big images from cameras on
    the phone, and we don't really need this resolution, it's all going to
    a phone screen"). Measured, not assumed: the same photo through the
    real upload path, at the old settings and the new ones."""
    from memz import conf, uploads
    from memz.models import MemeImage

    photo = _camera_photo_bytes()
    user = _user("shutterbug")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": ContentFile(photo, name="IMG_9001.JPG")})
    assert r.status_code == 201, r.content

    image = MemeImage.objects.get(pk=r.json()["id"])
    with Image.open(image.file) as stored:
        assert max(stored.size) <= conf.get("UPLOAD_MAX_SIDE") == 1280
    assert image.file.size < len(photo) / 4, "a camera-sized photo is still being stored near camera size"

    # And the tightening is real: the old settings on the same bytes.
    real_get = conf.get
    try:
        conf.get = lambda k: {"UPLOAD_MAX_SIDE": 1600, "UPLOAD_JPEG_QUALITY": 88}.get(k, real_get(k))
        old = uploads.process_upload(io.BytesIO(photo)).size
    finally:
        conf.get = real_get
    assert image.file.size < old * 0.8, f"expected a real saving, got {image.file.size} vs {old}"


def test_a_rendered_meme_got_lighter_without_changing_its_size_on_screen(public_image_source):
    """The finished meme keeps its 1080 px width -- it is the thing people
    share, and it gets opened on laptops too -- so only the encoder moved."""
    from memz import conf, render

    data, w, h = render.render(io.BytesIO(public_image_source), "כשמבינים שזה כבר יום שלישי", watermark=False)
    assert w == conf.get("RENDER_WIDTH") == 1080, "the shared output's width must not shrink"

    real_get = conf.get
    try:
        conf.get = lambda k: 85 if k == "RENDER_JPEG_QUALITY" else real_get(k)
        before, _w, _h = render.render(io.BytesIO(public_image_source), "כשמבינים שזה כבר יום שלישי", watermark=False)
    finally:
        conf.get = real_get
    assert len(data) < len(before), "the rendered meme did not get any lighter"


@pytest.fixture
def public_image_source(media_tmp):
    return _camera_photo_bytes(1600, 1200)


def test_the_phone_shrinks_the_photo_before_it_is_ever_uploaded(browser, live_server, db, media_tmp, tmp_path):
    """The server resizes anyway, so this is not a security boundary: it
    is the difference between a 1 MB upload and a 150 KB one over a
    party's wifi, and it is what lets a 48MP photo through at all, since
    the raw file can exceed the 8 MB the server refuses at."""
    pytest.importorskip("playwright.sync_api")
    from tests.test_memz_screens import PHONE

    photo = tmp_path / "IMG_9002.JPG"
    photo.write_bytes(_camera_photo_bytes())
    _user("bandwidth")

    # Measured by wrapping fetch in the page, not by reading the request
    # from Playwright's side: `post_data_buffer` comes back empty for a
    # large multipart body, which made the first version of this test pass
    # just as happily with the shrinking turned off.
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "window.__sentBytes = [];"
        "var _fetch = window.fetch;"
        "window.fetch = function (url, options) {"
        "  try {"
        "    if (options && options.body instanceof FormData) {"
        "      var f = options.body.get('file');"
        "      if (f && typeof f.size === 'number') window.__sentBytes.push(f.size);"
        "    }"
        "  } catch (e) {}"
        "  return _fetch.apply(this, arguments);"
        "};"
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/memz/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', "bandwidth@example.com")
        page.fill('input[name="password"]', "x")
        page.click('form button[type="submit"]')
        page.wait_for_timeout(400)
        page.goto(f"{live_server.url}/memz/", wait_until="domcontentloaded")
        page.wait_for_timeout(300)

        page.set_input_files("[data-home-uploader] input[data-uploader-gallery]", str(photo))
        page.wait_for_timeout(2500)

        sent = page.evaluate("window.__sentBytes")
        on_disk = photo.stat().st_size
        assert sent, "nothing was uploaded at all"
        assert sent[0] < on_disk / 3, (
            f"the browser sent {sent[0]} bytes of a {on_disk}-byte photo; it did not shrink it first"
        )
    finally:
        context.close()


def test_the_upload_quota_is_enforced_at_the_new_limit(client, media_tmp, settings):
    """Thirty, not five — but still a real ceiling."""
    from memz.models import MemeImage

    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 2, "paid": 50}
    user = _user("quota")
    client.force_login(user)
    for i in range(2):
        r = client.post("/memz/api/images/", {"file": ContentFile(_png_bytes(), name=f"ok{i}.png")})
        assert r.status_code == 201, r.content
    refused = client.post("/memz/api/images/", {"file": ContentFile(_png_bytes(), name="over.png")})
    assert refused.status_code == 400
    assert MemeImage.objects.filter(owner=user).count() == 2
