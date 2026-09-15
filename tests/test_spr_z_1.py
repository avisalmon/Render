"""SPR-Z.1 — memz: the skeleton and the seal (docs/memz/backlog.md).

What can break silently in a skeleton sprint is not the pages, it is the
boundaries: the app leaking babook's chrome, the API letting a signed-in
stranger read or edit somebody else's bank, the seed quietly overwriting an
edit on the next deploy, a tier cap that stops reading its setting. Every
test here is one of those, plus the happy half that proves the lock is not
just "everything refused".

Spec references are docs/memz/spec.md rule numbers (spec §0: the numbered
rules are the requirement IDs).
"""

import io
import json
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz1, pytest.mark.django_db]

REFUSED = (401, 403, 404)
PASSWORD = "memz-test-passw0rd"


# ------------------------------------------------------------------ helpers


def _png_bytes(size=(64, 48), color=(200, 90, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _user(name, staff=False):
    user = User.objects.create_user(name, email=f"{name}@example.com", password=PASSWORD)
    if staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def media_tmp(settings, tmp_path):
    """Uploads and seeded files land in a throwaway folder, never in dev media."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def bank(media_tmp):
    """Two users with private things each, and public things owned by nobody."""
    from django.core.files.base import ContentFile

    from memz.models import CaptionCard, CaptionDeck, MemeImage, Meme, Pack, PackImage, SavedMeme, Topic

    a = _user("alice")
    b = _user("bob")
    staff = _user("root", staff=True)

    def image(owner, visibility, status, title):
        img = MemeImage(owner=owner, visibility=visibility, moderation_status=status, title=title)
        img.file.save(f"{title}.png", ContentFile(_png_bytes()), save=True)
        return img

    a_img = image(a, "private", "approved", "alice-private")
    a_pending = image(a, "private", "pending", "alice-pending")
    b_img = image(b, "private", "approved", "bob-private")
    pub = image(None, "public", "approved", "public-approved")
    pub_pending = image(None, "public", "pending", "public-pending")

    a_pack = Pack.objects.create(owner=a, name="של אליס", slug="alice-pack")
    PackImage.objects.create(pack=a_pack, image=a_img, order=0)
    b_pack = Pack.objects.create(owner=b, name="של בוב", slug="bob-pack")
    PackImage.objects.create(pack=b_pack, image=b_img, order=0)
    pub_pack = Pack.objects.create(owner=None, name="משפחה", slug="family", is_public=True)
    PackImage.objects.create(pack=pub_pack, image=pub, order=0)

    a_deck = CaptionDeck.objects.create(owner=a, name="קלפים של אליס", language="he")
    a_card = CaptionCard.objects.create(deck=a_deck, text="כשאמא מתקשרת", order=0)
    b_deck = CaptionDeck.objects.create(owner=b, name="קלפים של בוב", language="he")
    b_card = CaptionCard.objects.create(deck=b_deck, text="יום ראשון בבוקר", order=0)
    pub_deck = CaptionDeck.objects.create(owner=None, name="ציבורי", is_public=True, language="he")
    pub_card = CaptionCard.objects.create(deck=pub_deck, text="אני אחרי קפה", order=0)

    a_topic = Topic.objects.create(owner=a, text="חופש גדול")
    b_topic = Topic.objects.create(owner=b, text="פקקים")
    pub_topic = Topic.objects.create(owner=None, text="יום ראשון", is_public=True)

    def meme(user, image):
        m = Meme(image=image, caption_text="כשזה סוף סוף יום שישי", source="solo", created_by_user=user)
        m.rendered.save("m.jpg", ContentFile(_png_bytes(color=(10, 10, 10))), save=True)
        return m

    a_meme = meme(a, pub)
    b_meme = meme(b, pub)
    a_saved = SavedMeme.objects.create(user=a, meme=a_meme)
    b_saved = SavedMeme.objects.create(user=b, meme=b_meme)

    return {
        "a": a, "b": b, "staff": staff,
        "a_img": a_img, "a_pending": a_pending, "b_img": b_img, "pub": pub, "pub_pending": pub_pending,
        "a_pack": a_pack, "b_pack": b_pack, "pub_pack": pub_pack,
        "a_deck": a_deck, "b_deck": b_deck, "pub_deck": pub_deck,
        "a_card": a_card, "b_card": b_card, "pub_card": pub_card,
        "a_topic": a_topic, "b_topic": b_topic, "pub_topic": pub_topic,
        "a_meme": a_meme, "b_meme": b_meme, "a_saved": a_saved, "b_saved": b_saved,
    }


def _fingerprint():
    """Everything a write could plausibly change, in one comparable value.

    `MemzProfile` is deliberately not here: the caller's own profile appears
    on their first authenticated call (Rule 3.3.4), which is the one
    legitimate side effect of touching the API. That it is *only* the
    caller's, and never an anonymous one, is asserted separately.
    """
    from memz import models as m

    out = {}
    for model in (m.MemeImage, m.Pack, m.PackImage, m.CaptionDeck, m.CaptionCard, m.Topic,
                  m.Meme, m.SavedMeme):
        rows = list(model.objects.order_by("pk").values())
        for row in rows:
            row.pop("last_seen_at", None)
        out[model.__name__] = rows
    return out


# ------------------------------------------------------ F-Z.1.1 the wiring


def test_memz_is_installed_and_mounted(client):
    from django.conf import settings

    assert "memz" in settings.INSTALLED_APPS
    response = client.get("/memz/")
    assert response.status_code == 200
    assert response.resolver_match.namespace == "memz"


def test_home_is_hebrew_rtl_and_installable(client):
    """Rule 11.3 (Hebrew, RTL) and Rule 11.5 (a PWA manifest)."""
    html = client.get("/memz/").content.decode()
    assert re.search(r"<html[^>]*\blang=\"he\"", html)
    assert re.search(r"<html[^>]*\bdir=\"rtl\"", html)
    assert 'rel="manifest"' in html
    assert 'data-screen="home"' in html


def test_a_bad_url_under_memz_gets_memz_own_404(client):
    """Rule 3 of building_an_app.md: even the error page stays inside the walls."""
    response = client.get("/memz/this-does-not-exist/")
    assert response.status_code == 404
    html = response.content.decode()
    assert 'data-screen="404"' in html
    assert "babook" not in html.lower()


@pytest.mark.parametrize("path", ["/memz/", "/memz/login/", "/memz/signup/", "/memz/new/", "/memz/this-does-not-exist/"])
def test_nothing_in_memz_points_out_of_memz(client, path):
    """Rule 3.3.2 and building_an_app.md Rule 3: no link back to the main site.

    Every href on every memz page stays under /memz/, or is a static/media
    asset, or is a font host, or is an in-page anchor, or is the one
    deliberate exception: /accounts/, the site's shared allauth flow
    (Google sign-in, spec §14.1/Rule 3.3.3, 2026-09-15). That is not a
    content or navigation leak back to babook — Rule 3.3.1 already made
    accounts themselves shared; this only extends *how* a person can prove
    who they are, the same door ustrip and matazim link to from their own
    sealed chrome.
    """
    html = client.get(path).content.decode()
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs, f"{path} has no links at all, which is not a page"
    outside = [
        h for h in hrefs
        if not (h.startswith("/memz/") or h.startswith("/static/") or h.startswith("/media/")
                or h.startswith("/accounts/") or h.startswith("#")
                or "fonts.googleapis.com" in h or "fonts.gstatic.com" in h)
    ]
    assert not outside, f"{path} links outside memz: {outside}"
    assert "babook" not in html.lower()


def test_the_game_doors_exist_on_home(client):
    """F-Z.1.5, updated: Start and Join exist on Home. Both led to an
    honest 'coming in SPR-Z.3' placeholder at the time this test was
    written; SPR-Z.3 replaced both with the real create/join screens
    (tests/test_spr_z_3.py covers them), and SPR-Z.2 did the same for
    /memz/create/ earlier. Nothing left to catalogue as 'coming'."""
    for path in ("/memz/new/", "/memz/join/"):
        assert client.get(path).status_code == 200, path


def test_memz_imports_nothing_from_the_other_apps():
    """Rule 12.1.1: the only allowed import from another app is the moderation
    adapter (SPR-Z.5), and it lives in exactly one file."""
    offenders = []
    for path in sorted(Path("memz").rglob("*.py")):
        if path.name == "moderation.py":
            continue
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*(from|import)\s+(app|matazim|ustrip)(\.|\s|$)", line):
                offenders.append(f"{path}:{line_no}: {line.strip()}")
    assert not offenders, "memz reached into another app:\n  " + "\n  ".join(offenders)


# ------------------------------------------------------ F-Z.1.2 the models


def test_migrations_are_complete_for_memz():
    """A model change without a migration is the deploy that breaks at start."""
    out = io.StringIO()
    call_command("makemigrations", "memz", "--check", "--dry-run", stdout=out)


def test_a_session_code_is_unique_while_active_and_reusable_after(media_tmp):
    """Spec §12.6: unique among sessions not finished or abandoned."""
    from django.db import IntegrityError, transaction

    from memz.models import Session

    Session.objects.create(code="ABCD", status="lobby")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Session.objects.create(code="ABCD", status="playing")
    Session.objects.filter(code="ABCD").update(status="finished")
    Session.objects.create(code="ABCD", status="lobby")   # the code is free again
    assert Session.objects.filter(code="ABCD").count() == 2


def test_nicknames_are_unique_within_a_session_and_tokens_everywhere():
    from django.db import IntegrityError, transaction

    from memz.models import Player, Session

    s1 = Session.objects.create(code="AAAA", status="lobby")
    s2 = Session.objects.create(code="BBBB", status="lobby")
    Player.objects.create(session=s1, nickname="דני", guest_token="t1", seat_order=0)
    Player.objects.create(session=s2, nickname="דני", guest_token="t2", seat_order=0)   # other room, fine
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Player.objects.create(session=s1, nickname="דני", guest_token="t3", seat_order=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Player.objects.create(session=s1, nickname="רוני", guest_token="t1", seat_order=1)


def test_a_meme_is_saved_once_per_person(bank):
    from django.db import IntegrityError, transaction

    from memz.models import SavedMeme

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SavedMeme.objects.create(user=bank["a"], meme=bank["a_meme"])


def test_deleting_a_bank_image_never_blocks_and_never_deletes_the_meme(bank):
    """data_model.md review change 2: the rendered file is what a meme is."""
    from memz.models import Meme

    meme_id = bank["a_meme"].id
    bank["pub"].delete()
    meme = Meme.objects.get(id=meme_id)
    assert meme.image is None
    assert meme.rendered


def test_deleting_an_account_takes_its_private_images_and_leaves_public_ones(bank):
    from memz.models import MemeImage

    bank["a"].delete()
    assert not MemeImage.objects.filter(id=bank["a_img"].id).exists()
    assert MemeImage.objects.filter(id=bank["pub"].id).exists()


# ---------------------------------------------------- F-Z.1.3 conf and tiers


def test_caps_have_the_spec_defaults():
    from memz import conf

    assert conf.cap("MAX_PLAYERS", "guest") == 5
    assert conf.cap("MAX_PLAYERS", "free") == 10
    assert conf.cap("MAX_PLAYERS", "paid") == 50
    assert conf.cap("UPLOAD_LIMIT", "guest") == 0
    assert conf.cap("REMEMBERED_SESSIONS", "paid") is None    # unlimited
    assert conf.get("GUEST_SESSION_TTL_HOURS") == 48
    assert conf.get("HAND_SIZE") == 7
    assert conf.get("ROUNDS") == (3, 10, 5)


def test_a_cap_reads_its_setting_at_call_time(settings):
    """Spec §12.5: a tune is an env var, not a deploy."""
    from memz import conf

    settings.MEMZ_MAX_PLAYERS = {"guest": 6, "free": 12, "paid": 60}
    assert conf.cap("MAX_PLAYERS", "guest") == 6
    settings.MEMZ_GUEST_SESSION_TTL_HOURS = 12
    assert conf.get("GUEST_SESSION_TTL_HOURS") == 12


def test_tier_for_everyone():
    from django.contrib.auth.models import AnonymousUser

    from memz.models import MemzProfile
    from memz.tiers import tier_for

    assert tier_for(AnonymousUser()) == "guest"
    assert tier_for(None) == "guest"
    free = _user("free_person")
    assert tier_for(free) == "free"             # no profile yet is still free
    paid = _user("paid_person")
    MemzProfile.objects.create(user=paid, tier="paid", paid_until=timezone.now() + timezone.timedelta(days=30))
    assert tier_for(paid) == "paid"
    lapsed = _user("lapsed_person")
    MemzProfile.objects.create(user=lapsed, tier="paid", paid_until=timezone.now() - timezone.timedelta(days=1))
    assert tier_for(lapsed) == "free"           # paid_until in the past is free


# ------------------------------------------------------------ F-Z.1.6 auth


def test_signup_is_email_and_password_and_works_immediately(client):
    """Rule 3.3.3: no verification step; Rule 3.3.4: the profile appears now."""
    from memz.models import MemzProfile

    response = client.post("/memz/signup/", {
        "name": "דני", "email": "dani@example.com", "password1": PASSWORD, "password2": PASSWORD,
    })
    assert response.status_code == 302 and response.url == "/memz/"
    user = User.objects.get(email="dani@example.com")
    assert user.is_active
    assert user.username == "dani"          # derived, never typed (same convention as the site)
    assert client.get("/memz/").wsgi_request.user == user
    assert MemzProfile.objects.get(user=user).display_name == "דני"
    assert len(mail.outbox) == 0            # nothing to verify


def test_signup_refuses_a_taken_email(client):
    _user("taken")   # taken@example.com
    response = client.post("/memz/signup/", {
        "email": "taken@example.com", "password1": PASSWORD, "password2": PASSWORD,
    })
    assert response.status_code == 200
    assert User.objects.filter(email="taken@example.com").count() == 1
    assert 'data-screen="signup"' in response.content.decode()


def test_login_accepts_the_email_and_logout_ends_it(client):
    user = _user("carol")
    response = client.post("/memz/login/", {"username": "carol@example.com", "password": PASSWORD})
    assert response.status_code == 302 and response.url == "/memz/"
    assert client.get("/memz/").wsgi_request.user == user

    assert client.get("/memz/logout/").status_code == 405   # POST only, like the rest of the site
    response = client.post("/memz/logout/")
    assert response.status_code == 302
    assert not client.get("/memz/").wsgi_request.user.is_authenticated


def test_login_with_a_wrong_password_stays_on_memz_login(client):
    _user("dave")
    response = client.post("/memz/login/", {"username": "dave@example.com", "password": "nope"})
    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-screen="login"' in html
    assert "babook" not in html.lower()


def test_password_reset_lives_in_memz_and_sends_one_mail(client):
    _user("erin")
    assert client.get("/memz/password/reset/").status_code == 200
    response = client.post("/memz/password/reset/", {"email": "erin@example.com"})
    assert response.status_code == 302
    assert response.url.startswith("/memz/")
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert "/memz/password/reset/" in body     # the link in the mail lands inside memz too
    assert client.get(response.url).status_code == 200


def test_a_babook_user_gets_a_profile_only_when_they_use_memz(client):
    """Rule 3.3.4: never a row for every babook user."""
    from memz.models import MemzProfile

    user = _user("frank")
    assert not MemzProfile.objects.filter(user=user).exists()
    client.force_login(user)
    client.get("/memz/")
    profile = MemzProfile.objects.get(user=user)
    assert profile.tier == "free"
    assert profile.display_name == "frank"


# ------------------------------------------------------------ F-Z.1.7 seed


@pytest.fixture
def seeded(media_tmp):
    call_command("seed_memz", verbosity=0)
    return media_tmp


def test_seed_creates_a_public_approved_bank(seeded):
    from memz.models import MemeImage, Pack

    packs = Pack.objects.filter(owner__isnull=True, is_public=True)
    assert packs.count() >= 4
    images = MemeImage.objects.all()
    assert images.count() >= 16
    assert not images.exclude(owner=None).exists()
    assert not images.exclude(visibility="public").exists()
    assert not images.exclude(moderation_status="approved").exists()
    assert not images.filter(seed_key="").exists()
    for image in images:
        assert Path(image.file.path).exists()
        assert image.packs.exists(), f"{image.seed_key} is in no pack"


def test_seed_is_one_time(seeded):
    """building_an_app.md 'Data': check-before-create; never overwrite, never
    delete, never resurrect what an admin retired."""
    from memz.models import MemeImage, Pack

    before = _fingerprint()
    call_command("seed_memz", verbosity=0)
    assert _fingerprint() == before

    image = MemeImage.objects.first()
    MemeImage.objects.filter(pk=image.pk).update(title="כותרת שמישהו ערך", moderation_status="rejected")
    pack = Pack.objects.filter(owner__isnull=True).first()
    Pack.objects.filter(pk=pack.pk).update(name="שם שמישהו שינה")
    call_command("seed_memz", verbosity=0)
    image.refresh_from_db()
    pack.refresh_from_db()
    assert image.title == "כותרת שמישהו ערך"
    assert image.moderation_status == "rejected"
    assert pack.name == "שם שמישהו שינה"


# ------------------------------------------------- F-Z.1.8 / F-Z.1.9 the API


def _prefixes():
    from memz.urls import router

    return [prefix for prefix, _viewset, _basename in router.registry]


def _detail_pk(bank, prefix):
    row = {
        "images": bank["a_img"], "packs": bank["a_pack"], "pack-images": bank["a_pack"].images.first(),
        "decks": bank["a_deck"], "deck-cards": bank["a_card"], "topics": bank["a_topic"],
        "saved": bank["a_saved"],
    }[prefix]
    return row.pk


def _attempts(bank, prefix):
    pk = _detail_pk(bank, prefix)
    base = f"/memz/api/{prefix}/"
    return [
        ("list", "get", base), ("create", "post", base), ("read", "get", f"{base}{pk}/"),
        ("update", "put", f"{base}{pk}/"), ("patch", "patch", f"{base}{pk}/"),
        ("destroy", "delete", f"{base}{pk}/"),
    ]


def _send(client, method, url, body=None):
    if method in ("post", "put", "patch"):
        return getattr(client, method)(url, json.dumps(body or {"name": "x", "text": "x"}),
                                       content_type="application/json")
    return getattr(client, method)(url)


@pytest.mark.parametrize("prefix", ["images", "packs", "pack-images", "decks", "deck-cards", "topics", "saved"])
def test_the_router_registers_every_bank_resource(prefix):
    assert prefix in _prefixes()


@pytest.mark.parametrize("prefix", ["images", "packs", "pack-images", "decks", "deck-cards", "topics", "saved"])
def test_a_stranger_gets_nowhere(client, bank, prefix):
    """Rule 12.3.3.1: no anonymous CRUD, anywhere. Every verb, every route,
    and the database unchanged afterwards."""
    before = _fingerprint()
    allowed = []
    for label, method, url in _attempts(bank, prefix):
        response = _send(client, method, url)
        if response.status_code not in REFUSED:
            allowed.append(f"{label} {method.upper()} {url} -> {response.status_code}")
    assert not allowed, "an anonymous stranger was let through:\n" + "\n".join(allowed)
    assert _fingerprint() == before
    from memz.models import MemzProfile

    assert MemzProfile.objects.count() == 0, "an anonymous call must never create a profile"


def test_a_signed_in_call_creates_only_the_callers_own_profile(client, bank):
    """Rule 3.3.4, the API half: the first authenticated call creates the
    caller's profile and nobody else's."""
    from memz.models import MemzProfile

    client.force_login(bank["b"])
    assert client.get("/memz/api/packs/").status_code == 200
    assert list(MemzProfile.objects.values_list("user_id", flat=True)) == [bank["b"].id]


def test_a_stranger_gets_no_profile_and_no_schema(client, bank):
    assert client.get("/memz/api/profile/").status_code in REFUSED
    assert client.patch("/memz/api/profile/", json.dumps({"display_name": "x"}),
                        content_type="application/json").status_code in REFUSED
    assert client.get("/memz/api/schema/").status_code in REFUSED
    assert client.get("/memz/api/").status_code in REFUSED


@pytest.mark.parametrize("prefix,a_key,b_key", [
    ("images", "a_img", "b_img"), ("packs", "a_pack", "b_pack"), ("decks", "a_deck", "b_deck"),
    ("deck-cards", "a_card", "b_card"), ("topics", "a_topic", "b_topic"), ("saved", "a_saved", "b_saved"),
])
def test_another_users_things_do_not_exist_as_far_as_you_can_tell(client, bank, prefix, a_key, b_key):
    """Rule 12.3.3.2: filtered in the queryset, so a foreign id is a 404 on
    every verb, never a 403 and never the object."""
    client.force_login(bank["b"])
    before = _fingerprint()
    listed = client.get(f"/memz/api/{prefix}/").json()
    rows = listed["results"] if isinstance(listed, dict) and "results" in listed else listed
    ids = {row["id"] for row in rows}
    assert bank[b_key].pk in ids
    assert bank[a_key].pk not in ids
    url = f"/memz/api/{prefix}/{bank[a_key].pk}/"
    assert client.get(url).status_code == 404
    # `saved` has no update verb at all (nothing on a saved row to edit), so
    # DRF answers 405 before it looks the row up: still a refusal, and it
    # reveals nothing about whether the row exists.
    assert _send(client, "patch", url, {"name": "x", "text": "x", "title": "x"}).status_code in (404, 405)
    assert client.delete(url).status_code == 404
    assert _fingerprint() == before


def test_a_pack_images_row_of_another_user_is_invisible(client, bank):
    client.force_login(bank["b"])
    foreign = bank["a_pack"].images.first().pk
    assert client.get(f"/memz/api/pack-images/{foreign}/").status_code == 404
    assert client.delete(f"/memz/api/pack-images/{foreign}/").status_code == 404
    listed = client.get("/memz/api/pack-images/").json()
    assert foreign not in {row["id"] for row in listed}


def test_pending_and_private_images_never_reach_a_stranger_or_a_list(client, bank):
    """Rule 6.4.1 and Rule 12.3.3.2: only approved public images are listable
    by others; a pending public image is not, and my own pending one is
    visible to me (I need to see its status) and to nobody else."""
    client.force_login(bank["b"])
    ids = {row["id"] for row in client.get("/memz/api/images/").json()}
    assert bank["pub"].pk in ids
    assert bank["pub_pending"].pk not in ids
    assert bank["a_pending"].pk not in ids
    assert bank["a_img"].pk not in ids
    client.force_login(bank["a"])
    ids = {row["id"] for row in client.get("/memz/api/images/").json()}
    assert bank["a_pending"].pk in ids
    assert bank["a_img"].pk in ids
    assert bank["pub_pending"].pk not in ids


@pytest.mark.parametrize("prefix,key", [("packs", "pub_pack"), ("decks", "pub_deck"), ("topics", "pub_topic"),
                                        ("images", "pub"), ("deck-cards", "pub_card")])
def test_public_content_is_readable_by_members_and_writable_by_staff_only(client, bank, prefix, key):
    """Rule 12.3.3.2, second half."""
    url = f"/memz/api/{prefix}/{bank[key].pk}/"
    client.force_login(bank["b"])
    before = _fingerprint()
    assert client.get(url).status_code == 200
    assert _send(client, "patch", url, {"name": "x", "text": "x", "title": "x"}).status_code == 403
    assert client.delete(url).status_code == 403
    assert _fingerprint() == before

    client.force_login(bank["staff"])
    response = _send(client, "patch", url, {"name": "שם חדש", "text": "טקסט חדש", "title": "כותרת חדשה"})
    assert response.status_code == 200, response.content


def test_my_own_pack_is_fully_mine(client, bank):
    """The happy half: a lock where nobody gets in also passes on a broken app."""
    from memz.models import Pack, PackImage

    client.force_login(bank["a"])
    response = _send(client, "post", "/memz/api/packs/", {"name": "טיול לפולין", "slug": "poland"})
    assert response.status_code == 201, response.content
    pack_id = response.json()["id"]
    pack = Pack.objects.get(id=pack_id)
    assert pack.owner == bank["a"] and pack.is_public is False

    # add my image and a public image; refuse somebody else's
    r = _send(client, "post", "/memz/api/pack-images/", {"pack": pack_id, "image": bank["a_img"].pk})
    assert r.status_code == 201, r.content
    r = _send(client, "post", "/memz/api/pack-images/", {"pack": pack_id, "image": bank["pub"].pk})
    assert r.status_code == 201, r.content
    r = _send(client, "post", "/memz/api/pack-images/", {"pack": pack_id, "image": bank["b_img"].pk})
    assert r.status_code in (400, 404), r.content
    assert PackImage.objects.filter(pack=pack).count() == 2

    # reorder, rename, delete
    ids = list(PackImage.objects.filter(pack=pack).order_by("order").values_list("id", flat=True))
    r = _send(client, "post", f"/memz/api/packs/{pack_id}/reorder/", {"pack_image_ids": ids[::-1]})
    assert r.status_code == 200, r.content
    assert list(PackImage.objects.filter(pack=pack).order_by("order").values_list("id", flat=True)) == ids[::-1]
    assert _send(client, "patch", f"/memz/api/packs/{pack_id}/", {"name": "פולין 2026"}).status_code == 200
    assert client.delete(f"/memz/api/packs/{pack_id}/").status_code == 204
    assert not Pack.objects.filter(id=pack_id).exists()


def test_creating_never_takes_the_owner_or_the_verdict_from_the_body(client, bank):
    """Rule 12.3.3.3 in spirit for the bank: identity comes from the caller."""
    from memz.models import MemeImage, Pack

    client.force_login(bank["a"])
    r = _send(client, "post", "/memz/api/packs/", {"name": "x", "slug": "x", "owner": bank["b"].pk, "is_public": True})
    assert r.status_code == 201
    pack = Pack.objects.get(id=r.json()["id"])
    assert pack.owner == bank["a"] and pack.is_public is False

    upload = io.BytesIO(_png_bytes())
    upload.name = "trip.png"
    r = client.post("/memz/api/images/", {
        "file": upload, "title": "מהטיול", "owner": bank["b"].pk,
        # "rejected" specifically: SPR-Z.5 actually runs moderation now, so a
        # body claiming "approved" would be indistinguishable from a real
        # approval and prove nothing. A forced "rejected" that the image
        # does not end up with proves the field was ignored either way.
        "visibility": "public", "moderation_status": "rejected", "seed_key": "hack",
    })
    assert r.status_code == 201, r.content
    image = MemeImage.objects.get(id=r.json()["id"])
    assert image.owner == bank["a"]
    assert image.visibility == "private"
    assert image.moderation_status != "rejected"
    assert image.seed_key == ""


def test_the_profile_is_mine_and_the_tier_is_not_for_me_to_set(client, bank):
    """Rule 12.3.3: the worst case is bounded by what the endpoint can express."""
    from memz.models import MemzProfile

    client.force_login(bank["a"])
    r = client.get("/memz/api/profile/")
    assert r.status_code == 200
    assert r.json()["tier"] == "free"
    r = client.patch("/memz/api/profile/", json.dumps({"display_name": "אליס", "tier": "paid"}),
                     content_type="application/json")
    assert r.status_code == 200, r.content
    profile = MemzProfile.objects.get(user=bank["a"])
    assert profile.display_name == "אליס"
    assert profile.tier == "free"


def test_saving_a_meme_clears_its_expiry_and_unsaving_is_mine_only(client, bank):
    from memz.models import Meme, SavedMeme

    Meme.objects.filter(pk=bank["b_meme"].pk).update(expires_at=timezone.now() + timezone.timedelta(hours=1))
    client.force_login(bank["a"])
    # By share_slug, not the numeric id (SPR-Z.5, spec Rule 12.3.3.6): a
    # meme is addressed externally the same way its share page is.
    r = _send(client, "post", "/memz/api/saved/", {"share_slug": bank["b_meme"].share_slug})
    assert r.status_code == 201, r.content
    assert Meme.objects.get(pk=bank["b_meme"].pk).expires_at is None
    assert client.delete(f"/memz/api/saved/{bank['b_saved'].pk}/").status_code == 404
    assert SavedMeme.objects.filter(pk=bank["b_saved"].pk).exists()


def test_the_browsable_api_and_the_schema_are_for_staff_in_production(client, bank, settings):
    """Rule 12.3.3.9. pytest runs with DEBUG off, which is production's shape."""
    assert settings.DEBUG is False
    client.force_login(bank["b"])
    r = client.get("/memz/api/images/", HTTP_ACCEPT="text/html")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
    assert client.get("/memz/api/schema/").status_code == 403

    client.force_login(bank["staff"])
    r = client.get("/memz/api/images/", HTTP_ACCEPT="text/html")
    assert r["Content-Type"].startswith("text/html")
    r = client.get("/memz/api/schema/")
    assert r.status_code == 200
    schema = r.json()
    prefixes = {resource["prefix"] for resource in schema["resources"]}
    assert {"images", "packs", "decks", "topics", "saved"} <= prefixes
    packs = next(res for res in schema["resources"] if res["prefix"] == "packs")
    assert "reorder" in packs["actions"]
