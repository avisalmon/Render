"""SPR-Z.7 — memz: real content, tier admin, and the first deploy
(docs/memz/backlog.md). Spec references are docs/memz/spec.md rule numbers.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz7, pytest.mark.django_db]


def _png_bytes(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (300, 220), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


# --------------------------------------------------------- F-Z.7.3 tier admin


def test_granting_paid_in_the_admin_gives_the_full_paid_cap():
    """Rule 2.3: paid is admin-granted in v1, no payments. A `MemzProfile`
    row with tier=paid and a future paid_until is exactly what the admin's
    change form (memz/admin.py's MemzProfileAdmin, no readonly override on
    tier/paid_until) can already save — this proves that grant actually
    changes behaviour end to end, not just that the field is editable."""
    from memz import conf
    from memz.models import MemzProfile
    from memz.tiers import tier_for

    user = User.objects.create_user("payer", email="payer@example.com", password="x")
    assert tier_for(user) == "free"   # no profile yet: still free, never guest

    MemzProfile.objects.create(
        user=user, display_name="Payer",
        tier=MemzProfile.PAID, paid_until=timezone.now() + timezone.timedelta(days=30),
    )
    assert tier_for(user) == "paid"
    assert conf.cap("MAX_PLAYERS", tier_for(user)) == 50


def test_a_lapsed_paid_until_falls_back_to_free_not_paid():
    from memz.models import MemzProfile
    from memz.tiers import tier_for

    user = User.objects.create_user("lapsed", email="lapsed@example.com", password="x")
    MemzProfile.objects.create(
        user=user, display_name="Lapsed",
        tier=MemzProfile.PAID, paid_until=timezone.now() - timezone.timedelta(days=1),
    )
    assert tier_for(user) == "free"


def test_a_paid_host_actually_gets_fifty_players_at_create():
    """The behavioural claim the backlog names explicitly: not just that
    the cap constant is 50, but that create_session snapshots it for a
    real paid host."""
    from memz import game
    from memz.models import MemzProfile

    user = User.objects.create_user("host50", email="host50@example.com", password="x")
    MemzProfile.objects.create(
        user=user, display_name="Host", tier=MemzProfile.PAID,
        paid_until=timezone.now() + timezone.timedelta(days=1),
    )
    session, _host = game.create_session(host_user=user, round_count=3, round_seconds=60, vote_seconds=20)
    assert session.max_players == 50


def test_the_memz_profile_admin_lets_tier_and_paid_until_be_set():
    """A blunt structural check that memz/admin.py never quietly locked
    these two fields — the actual behaviour is proven by the tests above,
    this just guards the admin wiring they depend on."""
    from memz.admin import MemzProfileAdmin
    from memz.models import MemzProfile
    from django.contrib import admin as django_admin

    site_admin = django_admin.site._registry[MemzProfile]
    assert isinstance(site_admin, MemzProfileAdmin)
    form = site_admin.get_form(request=None)
    assert "tier" not in (site_admin.get_readonly_fields(request=None) or ())
    assert "paid_until" not in (site_admin.get_readonly_fields(request=None) or ())
    assert "tier" in form.base_fields
    assert "paid_until" in form.base_fields


# ------------------------------------------------------ F-Z.7.1 real content


def test_retiring_placeholders_rejects_them_without_deleting_anything(db):
    """Rule 6.1.1: retired, not deleted — the row and the file both stay,
    only the moderation status (and thus dealability/visibility) changes,
    the same mechanism a genuinely rejected upload already uses."""
    from memz.models import MemeImage

    placeholder = MemeImage(
        owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED,
        seed_key="family/placeholder-01.png",
    )
    placeholder.file.save("placeholder-01.png", ContentFile(_png_bytes()), save=True)
    real = MemeImage(
        owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED,
        seed_key="family/family-01.png",
    )
    real.file.save("family-01.png", ContentFile(_png_bytes()), save=True)

    call_command("retire_placeholder_images")

    placeholder.refresh_from_db()
    real.refresh_from_db()
    assert placeholder.moderation_status == MemeImage.REJECTED
    assert not placeholder.is_dealable
    assert real.moderation_status == MemeImage.APPROVED   # untouched: not a placeholder key
    assert real.is_dealable
    from pathlib import Path

    assert Path(placeholder.file.path).exists()   # the file itself is never deleted


def test_retiring_placeholders_is_safe_to_run_twice(db):
    from memz.models import MemeImage

    placeholder = MemeImage(
        owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED,
        seed_key="animals/placeholder-01.png",
    )
    placeholder.file.save("placeholder-01.png", ContentFile(_png_bytes()), save=True)
    call_command("retire_placeholder_images")
    call_command("retire_placeholder_images")   # must not error the second time
    placeholder.refresh_from_db()
    assert placeholder.moderation_status == MemeImage.REJECTED


def test_the_full_bank_reaches_nine_packs_after_the_real_content_seed(seeded_z7):
    """ACT-Z.5 (post-epic): a ninth pack, `reactions`, was added later the
    same day -- stock reaction photos standing in for the celebrity/meme
    template content that was asked for and declined (spec Rule 6.1.1)."""
    from memz.models import Pack

    packs = Pack.objects.filter(owner__isnull=True, is_public=True)
    assert packs.count() == 9
    for slug in ("family", "animals", "work", "school", "friends", "food", "holidays", "sports", "reactions"):
        assert packs.filter(slug=slug).exists(), f"pack {slug!r} missing"


def test_the_new_bank_images_carry_the_real_content_note_not_placeholder(seeded_z7):
    from memz.models import MemeImage

    real = MemeImage.objects.filter(seed_key__contains="friends/friends-")
    assert real.exists()
    for image in real:
        assert "placeholder" not in image.moderation_note
        assert image.moderation_status == MemeImage.APPROVED


def test_stock_photos_are_labelled_stock_not_ai_illustrated(seeded_z7):
    """ACT-Z.5: the note used to say 'AI-illustrated' for every non-placeholder
    image, stock photos included, which was simply wrong -- fixed so a
    `-stock-` filename (download_stock_images.py's own naming) gets an
    honest note instead of borrowing the AI batch's."""
    from memz.models import MemeImage

    stock = MemeImage.objects.filter(seed_key__contains="-stock-")
    assert stock.exists()
    for image in stock:
        assert "stock photo" in image.moderation_note
        assert "AI-illustrated" not in image.moderation_note

    illustrated = MemeImage.objects.filter(seed_key="friends/friends-01.jpg")
    assert illustrated.exists()
    assert "AI-illustrated" in illustrated.first().moderation_note


# -------------------------------------------------------- Google sign-in


def test_login_and_signup_offer_google_through_the_shared_babook_flow(client, db):
    """Avi: "google login option... use the babook user auth system." The
    exact allauth URL babook's own login page (and ustrip's, matazim's)
    already use, not a second implementation (spec §14.1, §3.3.3)."""
    login_body = client.get("/memz/login/").content.decode()
    assert "/accounts/google/login/?process=login&amp;next=/memz/" in login_body

    # next carried through, same as the password form on the same page.
    with_next = client.get("/memz/login/?next=/memz/me/").content.decode()
    assert "next=/memz/me/" in with_next

    signup_body = client.get("/memz/signup/").content.decode()
    assert "/accounts/google/login/?process=login&amp;next=" in signup_body


@pytest.fixture
def seeded_z7(media_tmp):
    call_command("seed_memz", verbosity=0)


# --------------------------------------------------- ACT-Z.5 Imgflip templates


_FAKE_TEMPLATES = {
    "success": True,
    "data": {"memes": [
        {"id": "181913649", "name": "Drake Hotline Bling", "url": "https://i.imgflip.com/30b1gx.jpg", "box_count": 2},
        {"id": "112126428", "name": "Distracted Boyfriend", "url": "https://i.imgflip.com/1ur9b0.jpg", "box_count": 3},
    ]},
}


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", status=200):
        self._json = json_data
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _no_real_imgflip_network(monkeypatch):
    """Every test below is explicit about which Imgflip call it fakes;
    nothing here should ever reach the real API (conftest.py already blanks
    the credentials, this is belt and suspenders for list_templates(),
    which needs none)."""
    from memz import imgflip_templates

    def _boom(*a, **k):
        raise AssertionError("a test tried to reach the real Imgflip API")

    monkeypatch.setattr(imgflip_templates.requests, "get", _boom)
    monkeypatch.setattr(imgflip_templates.requests, "post", _boom)
    yield


def test_list_templates_is_cached_after_the_first_call(monkeypatch):
    from memz import imgflip_templates

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _FakeResponse(json_data=_FAKE_TEMPLATES)

    monkeypatch.setattr(imgflip_templates.requests, "get", fake_get)

    first = imgflip_templates.list_templates()
    second = imgflip_templates.list_templates()
    assert len(first) == 2
    assert first == second
    assert len(calls) == 1   # the second call was served from cache


def test_list_templates_fails_closed_to_an_empty_list(monkeypatch):
    from memz import imgflip_templates

    def fake_get(url, timeout):
        raise ConnectionError("no network")

    monkeypatch.setattr(imgflip_templates.requests, "get", fake_get)
    assert imgflip_templates.list_templates() == []


def test_captioning_refuses_without_credentials_configured(settings):
    from memz import imgflip_templates

    assert not settings.IMGFLIP_USERNAME and not settings.IMGFLIP_PASSWORD
    with pytest.raises(imgflip_templates.ImgflipUnavailable):
        imgflip_templates.caption("181913649", "top", "bottom")


def test_captioning_refuses_an_unknown_template(settings, monkeypatch):
    from memz import imgflip_templates

    settings.IMGFLIP_USERNAME, settings.IMGFLIP_PASSWORD = "u", "p"
    monkeypatch.setattr(imgflip_templates.requests, "get", lambda url, timeout: _FakeResponse(json_data=_FAKE_TEMPLATES))
    with pytest.raises(imgflip_templates.ImgflipUnavailable):
        imgflip_templates.caption("not-a-real-id", "top", "bottom")


def test_captioning_refuses_two_blank_boxes(settings, monkeypatch):
    from memz import imgflip_templates

    settings.IMGFLIP_USERNAME, settings.IMGFLIP_PASSWORD = "u", "p"
    monkeypatch.setattr(imgflip_templates.requests, "get", lambda url, timeout: _FakeResponse(json_data=_FAKE_TEMPLATES))
    with pytest.raises(imgflip_templates.ImgflipUnavailable):
        imgflip_templates.caption("181913649", "   ", "")


def test_captioning_surfaces_imgflips_own_error(settings, monkeypatch):
    from memz import imgflip_templates

    settings.IMGFLIP_USERNAME, settings.IMGFLIP_PASSWORD = "u", "p"

    def fake_get(url, timeout):
        return _FakeResponse(json_data=_FAKE_TEMPLATES)

    def fake_post(url, data, timeout):
        return _FakeResponse(json_data={"success": False, "error_message": "invalid username/password"})

    monkeypatch.setattr(imgflip_templates.requests, "get", fake_get)
    monkeypatch.setattr(imgflip_templates.requests, "post", fake_post)
    with pytest.raises(imgflip_templates.ImgflipUnavailable, match="invalid username/password"):
        imgflip_templates.caption("181913649", "top", "bottom")


def test_captioning_succeeds_and_returns_bytes_and_template_name(settings, monkeypatch):
    from memz import imgflip_templates

    settings.IMGFLIP_USERNAME, settings.IMGFLIP_PASSWORD = "u", "p"
    seen_payloads = []

    def fake_get(url, timeout):
        if "get_memes" in url:
            return _FakeResponse(json_data=_FAKE_TEMPLATES)
        return _FakeResponse(content=b"\xff\xd8\xfake-jpeg-bytes")

    def fake_post(url, data, timeout):
        seen_payloads.append(data)
        return _FakeResponse(json_data={"success": True, "data": {"url": "https://i.imgflip.com/fake.jpg"}})

    monkeypatch.setattr(imgflip_templates.requests, "get", fake_get)
    monkeypatch.setattr(imgflip_templates.requests, "post", fake_post)

    jpeg_bytes, name = imgflip_templates.caption("181913649", "top text", "bottom text")
    assert jpeg_bytes == b"\xff\xd8\xfake-jpeg-bytes"
    assert name == "Drake Hotline Bling"
    assert seen_payloads[0]["text0"] == "top text"
    assert seen_payloads[0]["text1"] == "bottom text"
    assert seen_payloads[0]["username"] == "u" and seen_payloads[0]["password"] == "p"


def _configure_and_fake_imgflip(settings, monkeypatch):
    from memz import imgflip_templates

    settings.IMGFLIP_USERNAME, settings.IMGFLIP_PASSWORD = "u", "p"

    def fake_get(url, timeout):
        if "get_memes" in url:
            return _FakeResponse(json_data=_FAKE_TEMPLATES)
        return _FakeResponse(content=b"\xff\xd8\xfake-jpeg-bytes")

    def fake_post(url, data, timeout):
        return _FakeResponse(json_data={"success": True, "data": {"url": "https://i.imgflip.com/fake.jpg"}})

    monkeypatch.setattr(imgflip_templates.requests, "get", fake_get)
    monkeypatch.setattr(imgflip_templates.requests, "post", fake_post)


def test_make_meme_from_template_records_its_source_and_no_bank_image(settings, monkeypatch, media_tmp):
    from memz.memes import make_meme_from_template

    _configure_and_fake_imgflip(settings, monkeypatch)
    meme = make_meme_from_template(template_id="181913649", top_text="top text", bottom_text="bottom text")
    assert meme.image is None
    assert meme.source_credit == "Imgflip: Drake Hotline Bling"
    assert meme.caption_text == "top text / bottom text"
    assert meme.rendered.name


def test_make_meme_from_template_guest_gets_expiry_logged_in_user_does_not(settings, monkeypatch, media_tmp):
    from memz.memes import make_meme_from_template

    _configure_and_fake_imgflip(settings, monkeypatch)
    guest_meme = make_meme_from_template(template_id="181913649", top_text="hi", bottom_text="")
    assert guest_meme.expires_at is not None
    assert guest_meme.created_by_user is None

    user = User.objects.create_user("imgfliptester", password="x")
    user_meme = make_meme_from_template(template_id="181913649", top_text="hi", bottom_text="", user=user)
    assert user_meme.expires_at is None
    assert user_meme.created_by_user == user


def test_imgflip_templates_endpoint_lists_and_reports_availability(client, settings, monkeypatch):
    monkeypatch.setattr(
        "memz.imgflip_templates.requests.get", lambda url, timeout: _FakeResponse(json_data=_FAKE_TEMPLATES)
    )
    resp = client.get("/memz/api/imgflip/templates/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["templates"]) == 2
    assert body["templates"][0]["name"] == "Drake Hotline Bling"
    assert body["available"] is False   # conftest.py blanks the credentials for every test


def test_imgflip_caption_endpoint_requires_a_template_id(client):
    resp = client.post("/memz/api/imgflip/memes/", data={"top_text": "hi"})
    assert resp.status_code == 400


def test_imgflip_caption_endpoint_refuses_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(
        "memz.imgflip_templates.requests.get", lambda url, timeout: _FakeResponse(json_data=_FAKE_TEMPLATES)
    )
    resp = client.post(
        "/memz/api/imgflip/memes/", data={"template_id": "181913649", "top_text": "hi", "bottom_text": "there"}
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_imgflip_caption_endpoint_creates_a_meme_for_a_guest(client, settings, monkeypatch, media_tmp):
    _configure_and_fake_imgflip(settings, monkeypatch)
    resp = client.post(
        "/memz/api/imgflip/memes/", data={"template_id": "181913649", "top_text": "hi", "bottom_text": "there"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_credit"] == "Imgflip: Drake Hotline Bling"
    assert body["rendered_url"]
    assert resp["Location"].startswith("/memz/m/")

    from memz.models import Meme

    meme = Meme.objects.get(share_slug=body["share_slug"])
    assert meme.expires_at is not None   # a guest's, same as any other solo meme (spec §7.1)
