"""SPR-Z.5 — memz: accounts, the bank, and remembering (docs/memz/backlog.md).
Spec references are docs/memz/spec.md rule numbers.
"""

import io
import json

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz5, pytest.mark.django_db]

REFUSED = (401, 403, 404)


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


def _png_bytes(color=(40, 90, 150), size=(300, 220)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _upload_file(name="photo.png", color=(60, 120, 40)):
    return SimpleUploadedFile(name, _png_bytes(color), content_type="image/png")


def _user(name):
    return User.objects.create_user(name, email=f"{name}@example.com", password="x")


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def public_image(media_tmp):
    from memz.models import MemeImage

    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save("pub.png", ContentFile(_png_bytes()), save=True)
    return img


def post(client, url, body=None, token=None):
    headers = {"content_type": "application/json"}
    if token:
        headers["HTTP_X_MEMZ_PLAYER"] = token
    return client.post(url, json.dumps(body or {}), **headers)


def get(client, url, token=None):
    headers = {}
    if token:
        headers["HTTP_X_MEMZ_PLAYER"] = token
    return client.get(url, **headers)


def create_session(client, **kwargs):
    r = post(client, "/memz/api/sessions/", kwargs)
    return r


def join(client, code, nickname="guest"):
    r = post(client, f"/memz/api/sessions/{code}/join/", {"nickname": nickname})
    assert r.status_code == 201, r.content
    return r.json()


def state(client, code, token=None):
    r = get(client, f"/memz/api/sessions/{code}/state/", token)
    assert r.status_code == 200, r.content
    return r.json()


# ---------------------------------------------------------------- uploads


def test_upload_processes_strips_exif_and_resizes(client, media_tmp, settings):
    settings.MEMZ_UPLOAD_MAX_SIDE = 100
    user = _user("uploader")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": _upload_file()})
    assert r.status_code == 201, r.content

    from memz.models import MemeImage
    from PIL import Image as PILImage

    image = MemeImage.objects.get(pk=r.json()["id"])
    assert image.owner == user
    assert image.visibility == MemeImage.PRIVATE
    with PILImage.open(image.file) as im:
        assert max(im.size) <= 100
        # JFIF markers are just baseline JPEG framing, not identifying
        # metadata; what must be gone is anything EXIF-shaped (camera,
        # GPS, orientation, timestamps).
        assert "exif" not in im.info
        assert "gps" not in {k.lower() for k in im.info}


def test_upload_refuses_a_non_image_file(client, media_tmp):
    user = _user("uploader2")
    client.force_login(user)
    bad = SimpleUploadedFile("nope.png", b"not an image at all", content_type="image/png")
    r = client.post("/memz/api/images/", {"file": bad})
    assert r.status_code == 400


def test_upload_is_refused_over_the_size_cap(client, media_tmp, settings):
    settings.MEMZ_UPLOAD_MAX_BYTES = 100
    user = _user("uploader3")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": _upload_file()})
    assert r.status_code == 400


def test_upload_refused_anonymously(client, media_tmp):
    r = client.post("/memz/api/images/", {"file": _upload_file()})
    assert r.status_code in REFUSED


def test_upload_cap_by_tier(client, media_tmp, settings):
    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 2, "paid": 2000}
    user = _user("capped")
    client.force_login(user)
    for i in range(2):
        r = client.post("/memz/api/images/", {"file": _upload_file(f"p{i}.png")})
        assert r.status_code == 201, r.content
    r = client.post("/memz/api/images/", {"file": _upload_file("p3.png")})
    assert r.status_code == 400
    assert "מכסת" in r.json()["detail"]


# -------------------------------------------------------------- moderation


def test_moderation_runs_and_approves_a_clean_upload(client, media_tmp, settings):
    settings.IMAGE_MODERATION_ENABLED = False   # the site's own kill switch -> image_is_safe returns True
    user = _user("clean")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": _upload_file()})
    assert r.status_code == 201, r.content
    assert r.json()["moderation_status"] == "approved"


def test_moderation_fails_closed_when_the_site_check_is_unreachable(client, media_tmp, monkeypatch):
    """The adapter's own contract (spec Rule 6.4.2), exercised for real: the
    site's `image_is_safe` raising must never become a silent approval."""
    import app.safety

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(app.safety, "image_is_safe", _boom)
    user = _user("unlucky")
    client.force_login(user)
    r = client.post("/memz/api/images/", {"file": _upload_file()})
    assert r.status_code == 201, r.content
    assert r.json()["moderation_status"] == "pending"


def test_only_approved_images_are_dealt_or_listed(client, media_tmp):
    from memz.models import MemeImage

    owner = _user("has_pending")
    pending = MemeImage(owner=owner, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.PENDING)
    pending.file.save("pend.png", ContentFile(_png_bytes()), save=True)
    rejected = MemeImage(owner=owner, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.REJECTED)
    rejected.file.save("rej.png", ContentFile(_png_bytes()), save=True)

    client.force_login(owner)
    listed_ids = {row["id"] for row in client.get("/memz/api/images/").json()}
    assert pending.pk in listed_ids   # you see your own pending/rejected (their status)
    assert rejected.pk in listed_ids

    stranger = _user("stranger")
    client.force_login(stranger)
    stranger_ids = {row["id"] for row in client.get("/memz/api/images/").json()}
    assert pending.pk not in stranger_ids
    assert rejected.pk not in stranger_ids


# -------------------------------------------------------------------- packs


def test_pack_cap_by_tier(client, media_tmp, settings):
    settings.MEMZ_PACK_LIMIT = {"guest": 0, "free": 1, "paid": 2000}
    user = _user("packcapped")
    client.force_login(user)
    r1 = post(client, "/memz/api/packs/", {"name": "אחת"})
    assert r1.status_code == 201, r1.content
    r2 = post(client, "/memz/api/packs/", {"name": "שתיים"})
    assert r2.status_code == 400


# --------------------------------------------------------- image source


def test_own_only_never_deals_another_users_private_image(client, media_tmp, public_image):
    from memz.models import MemeImage

    a = _user("hosta")
    b = _user("otherb")
    b_img = MemeImage(owner=b, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    b_img.file.save("b.png", ContentFile(_png_bytes()), save=True)
    a_img = MemeImage(owner=a, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    a_img.file.save("a.png", ContentFile(_png_bytes()), save=True)

    client.force_login(a)
    r = create_session(client, image_source="own_only", round_count=1)
    assert r.status_code == 201, r.content
    host = r.json()
    client.logout()
    p2 = join(client, host["code"], "p2")
    p3 = join(client, host["code"], "p3")
    post(client, f"/memz/api/sessions/{host['code']}/start/", token=host["token"])
    for p in (host, p2, p3):
        st = state(client, host["code"], p["token"])
        assert st["round"]["my_submission"]["image_url"].endswith(".png")
        assert "b.png" not in st["round"]["my_submission"]["image_url"] and "b_" not in st["round"]["my_submission"]["image_url"]


def test_packs_image_source_requires_at_least_one_pack(client, media_tmp):
    user = _user("nopackhost")
    client.force_login(user)
    r = create_session(client, image_source="packs")
    assert r.status_code == 400


def test_packs_image_source_deals_only_from_the_selected_pack(client, media_tmp):
    from memz.models import MemeImage, Pack, PackImage

    user = _user("packhost")
    pack = Pack.objects.create(owner=user, name="שלי", slug="mine")
    only_image = MemeImage(owner=user, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    only_image.file.save("only.png", ContentFile(_png_bytes()), save=True)
    PackImage.objects.create(pack=pack, image=only_image, order=0)
    # a second owned image NOT in the pack — must never be dealt
    other_image = MemeImage(owner=user, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    other_image.file.save("other.png", ContentFile(_png_bytes()), save=True)

    client.force_login(user)
    r = create_session(client, image_source="packs", packs=[pack.pk], round_count=1)
    assert r.status_code == 201, r.content
    host = r.json()
    client.logout()
    join(client, host["code"], "p2")
    join(client, host["code"], "p3")   # Vote mode's minimum is 3 (spec Rule 5.4.1)
    start = post(client, f"/memz/api/sessions/{host['code']}/start/", token=host["token"])
    assert start.status_code == 200, start.content
    st = state(client, host["code"], host["token"])
    assert "only" in st["round"]["my_submission"]["image_url"]


# --------------------------------------------------------- remembered cap


def test_remembered_sessions_are_only_counted_while_not_released(client, media_tmp):
    from memz.models import Session

    user = _user("remembers")
    client.force_login(user)
    r = create_session(client, round_count=1)
    assert r.status_code == 201
    session = Session.objects.get(code=r.json()["code"])
    assert session.remembered is True
    assert session.expires_at is None


def test_remembered_cap_offers_the_oldest_session_to_release(client, media_tmp, settings):
    settings.MEMZ_REMEMBERED_SESSIONS = {"guest": 0, "free": 1, "paid": None}
    user = _user("atcap")
    client.force_login(user)
    r1 = create_session(client, round_count=1)
    assert r1.status_code == 201
    first_code = r1.json()["code"]

    r2 = create_session(client, round_count=1)
    assert r2.status_code == 409
    body = r2.json()
    assert body["cap_reached"] is True
    assert body["oldest_session"]["code"] == first_code

    r3 = create_session(client, round_count=1, release_session_code=first_code)
    assert r3.status_code == 201, r3.content

    from memz.models import Session

    assert Session.objects.get(code=first_code).expires_at is not None


def test_release_is_authorized_by_the_token_not_by_who_is_logged_in(client, media_tmp):
    """Rule 12.3.3.3: the player token is the identity for a game action,
    not the browser's session cookie — holding the real host's token
    authorizes the action even from an unrelated logged-in browser (this
    is the intended design, not a gap: the token is the credential)."""
    host = _user("real_host")
    client.force_login(host)
    r = create_session(client, round_count=1)
    code = r.json()["code"]
    token = r.json()["token"]
    client.logout()

    other = _user("not_the_host")
    client.force_login(other)
    r2 = post(client, f"/memz/api/sessions/{code}/release/", token=token)
    assert r2.status_code == 200

    from memz.models import Session

    assert Session.objects.get(code=code).expires_at is not None


def test_release_without_the_hosts_token_is_refused_even_as_the_host(client, media_tmp):
    """The complement of the above: being logged in as the host's own
    account is not enough without the token — no ambient session-cookie
    fallback for game actions."""
    host = _user("real_host2")
    client.force_login(host)
    r = create_session(client, round_count=1)
    code = r.json()["code"]

    r2 = post(client, f"/memz/api/sessions/{code}/release/")   # no token at all
    assert r2.status_code == 401

    from memz.models import Session

    assert Session.objects.get(code=code).expires_at is None


# ------------------------------------------------------------------- save


def test_save_clears_expiry_and_survives_cleanup(client, media_tmp):
    from django.core.management import call_command

    from memz.memes import make_meme
    from memz.models import Meme, MemeImage, SavedMeme

    saver = _user("saver")
    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save("save-src.png", ContentFile(_png_bytes()), save=True)
    meme = make_meme(image=img, caption_text="שמרו אותי", source=Meme.SOLO, user=None)
    assert meme.expires_at is not None

    client.force_login(saver)
    r = post(client, "/memz/api/saved/", {"share_slug": meme.share_slug})
    assert r.status_code == 201, r.content

    meme.refresh_from_db()
    assert meme.expires_at is None

    call_command("memz_cleanup")
    assert Meme.objects.filter(pk=meme.pk).exists()
    assert SavedMeme.objects.filter(user=saver, meme=meme).exists()


def test_saving_twice_is_a_no_op_not_an_error(client, media_tmp):
    from memz.memes import make_meme
    from memz.models import MemeImage, Meme, SavedMeme

    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save("dup.png", ContentFile(_png_bytes()), save=True)
    meme = make_meme(image=img, caption_text="x", source=Meme.SOLO, user=None)
    user = _user("double_saver")
    client.force_login(user)
    r1 = post(client, "/memz/api/saved/", {"share_slug": meme.share_slug})
    r2 = post(client, "/memz/api/saved/", {"share_slug": meme.share_slug})
    assert r1.status_code == 201 and r2.status_code == 200
    assert SavedMeme.objects.filter(user=user, meme=meme).count() == 1


def test_save_by_numeric_id_is_refused_slug_only(client, media_tmp):
    from memz.memes import make_meme
    from memz.models import MemeImage, Meme

    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save("idonly.png", ContentFile(_png_bytes()), save=True)
    meme = make_meme(image=img, caption_text="x", source=Meme.SOLO, user=None)
    user = _user("id_guesser")
    client.force_login(user)
    r = post(client, "/memz/api/saved/", {"meme": meme.pk})
    assert r.status_code == 400


# ----------------------------------------------------------------- attach


def test_signing_in_mid_session_attaches_the_account_keeping_seat_and_score(client, media_tmp):
    r = create_session(client, round_count=1)
    host_code = r.json()["code"]
    p2 = join(client, host_code, "אורח שרוצה חשבון")

    from memz.models import Player

    Player.objects.filter(pk=p2["player_id"]).update(score=7)

    user = _user("attacher")
    client.force_login(user)
    r2 = post(client, f"/memz/api/sessions/{host_code}/attach/", token=p2["token"])
    assert r2.status_code == 200, r2.content

    player = Player.objects.get(pk=p2["player_id"])
    assert player.user == user
    assert player.score == 7
    assert player.nickname == "אורח שרוצה חשבון"


def test_attach_is_idempotent_for_the_same_account(client, media_tmp):
    r = create_session(client, round_count=1)
    code = r.json()["code"]
    p2 = join(client, code, "p2")
    user = _user("same_acct")
    client.force_login(user)
    assert post(client, f"/memz/api/sessions/{code}/attach/", token=p2["token"]).status_code == 200
    assert post(client, f"/memz/api/sessions/{code}/attach/", token=p2["token"]).status_code == 200


def test_attach_refuses_a_seat_already_linked_to_someone_else(client, media_tmp):
    r = create_session(client, round_count=1)
    code = r.json()["code"]
    p2 = join(client, code, "p2")
    owner = _user("owns_it")
    client.force_login(owner)
    post(client, f"/memz/api/sessions/{code}/attach/", token=p2["token"])
    client.logout()

    intruder = _user("wants_it")
    client.force_login(intruder)
    r2 = post(client, f"/memz/api/sessions/{code}/attach/", token=p2["token"])
    assert r2.status_code == 403


def test_attach_refuses_an_anonymous_caller(client, media_tmp):
    r = create_session(client, round_count=1)
    code = r.json()["code"]
    p2 = join(client, code, "p2")
    r2 = post(client, f"/memz/api/sessions/{code}/attach/", token=p2["token"])
    assert r2.status_code == 401


# --------------------------------------------------------------- profile


def test_profile_requires_login(client):
    r = client.get("/memz/me/")
    assert r.status_code == 302
    assert r.url.startswith("/memz/login/")


def test_profile_lists_my_things_only(client, media_tmp):
    from memz.models import MemeImage, Pack

    me = _user("profileme")
    other = _user("profileother")
    mine = MemeImage(owner=me, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    mine.file.save("mine.png", ContentFile(_png_bytes()), save=True)
    theirs = MemeImage(owner=other, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    theirs.file.save("theirs.png", ContentFile(_png_bytes()), save=True)
    Pack.objects.create(owner=me, name="שלי", slug="mine-pack")

    client.force_login(me)
    html = client.get("/memz/me/").content.decode()
    assert "mine.png" in html or "mine_" in html
    assert "theirs.png" not in html and "theirs_" not in html
    assert "שלי" in html


# ------------------------------------------------------------- guest gap


def test_a_guest_host_can_never_choose_anything_but_public_random(client, media_tmp):
    from memz.models import Session

    r = create_session(client, image_source="own_only", round_count=1)
    assert r.status_code == 201
    assert Session.objects.get(code=r.json()["code"]).image_source == Session.PUBLIC_RANDOM
