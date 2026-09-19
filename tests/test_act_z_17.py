"""ACT-Z.17 — memz: the public bank's own uploader, staff only.

Avi: "another feature that will be only for the admin user. Nobody will
see this feature... it's not a user image bank, it's for the general
bank. You can categorize them as Avi's images, whatever. And I can just
from my phone upload images as many as I want, not as a normal user...
I don't need a link to this view. Just give me the address."

Three properties, and all three get tests: nobody but staff learns the
screen exists, what it writes lands in the *general* bank rather than
anyone's personal one, and no quota applies to it.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image

pytestmark = [pytest.mark.actz17, pytest.mark.django_db]

BANK_URL = "/memz/bank/"
API_URL = "/memz/api/bank/images/"


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEDIA_ROOT = str(tmp_path / "media")
    yield


def _png(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (300, 220), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(name="bank.png", color=(40, 90, 150)):
    return ContentFile(_png(color), name=name)


def _user(name, staff=False):
    return User.objects.create_user(
        name, email=f"{name}@example.com", password="x", is_staff=staff
    )


# ------------------------------------------------- nobody else is here


def test_the_screen_is_a_404_for_everyone_who_is_not_staff(client):
    """A 403 would confirm the page exists. The one property an unlisted
    admin screen must have is that nobody else learns anything at all."""
    assert client.get(BANK_URL).status_code == 404   # signed out

    client.force_login(_user("ordinary"))
    assert client.get(BANK_URL).status_code == 404   # signed in, not staff


def test_the_screen_opens_for_staff(client):
    client.force_login(_user("avi", staff=True))
    r = client.get(BANK_URL)
    assert r.status_code == 200
    assert "data-bank-uploader" in r.content.decode()


def test_nothing_on_the_site_links_to_it(client):
    """"Nobody will see this feature" — so it is reachable only by typing
    the address, even when the admin is the one browsing."""
    client.force_login(_user("avi2", staff=True))
    for page in ("/memz/", "/memz/me/", "/memz/new/", "/memz/create/"):
        body = client.get(page).content.decode()
        assert BANK_URL not in body, f"{page} links to the unlisted bank screen"


def test_the_upload_endpoint_refuses_everyone_but_staff(client):
    assert client.post(API_URL, {"file": _upload()}).status_code in (401, 403)

    client.force_login(_user("nosy"))
    r = client.post(API_URL, {"file": _upload()})
    assert r.status_code == 403

    from memz.models import MemeImage

    assert not MemeImage.objects.exists(), "a non-staff upload reached the bank anyway"


# ------------------------------------------ it writes to the general bank


def test_an_upload_lands_in_the_public_bank_not_in_anybodys_own(client):
    from memz.models import MemeImage

    admin = _user("avi3", staff=True)
    client.force_login(admin)
    r = client.post(API_URL, {"file": _upload()})
    assert r.status_code == 201, r.content

    image = MemeImage.objects.get(pk=r.json()["id"])
    assert image.owner is None, "the bank upload was filed as the admin's personal image"
    assert image.visibility == MemeImage.PUBLIC


def test_what_it_uploads_is_actually_dealt_into_a_stranger_s_game(client):
    """The point of the whole screen: these images reach games nobody
    here opened. Proven through `dealing.pool_for`, the real chooser."""
    from memz import dealing, game

    client.force_login(_user("avi4", staff=True))
    r = client.post(API_URL, {"file": _upload(color=(200, 30, 30))})
    assert r.status_code == 201, r.content

    session, _host = game.create_session(
        host_user=None, round_count=1, round_seconds=60, vote_seconds=20,
    )
    pool_ids = {img.id for img in dealing.pool_for(session)}
    assert r.json()["id"] in pool_ids, "a bank upload never reached a game's pool"


def test_uploads_are_filed_under_a_category_and_a_new_name_opens_one(client):
    from memz.models import Pack

    client.force_login(_user("avi5", staff=True))
    first = client.post(API_URL, {"file": _upload()})
    assert first.status_code == 201, first.content
    assert first.json()["pack"]["name"] == "התמונות של אבי", "no default category"

    named = client.post(API_URL, {"file": _upload("two.png"), "pack": "חתולים"})
    assert named.status_code == 201, named.content
    pack = Pack.objects.get(name="חתולים")
    assert pack.owner is None and pack.is_public
    assert pack.images.count() == 1

    again = client.post(API_URL, {"file": _upload("three.png"), "pack": "חתולים"})
    assert again.status_code == 201
    assert Pack.objects.filter(name="חתולים").count() == 1, "the same name opened a second category"
    assert Pack.objects.get(name="חתולים").images.count() == 2


def test_moderation_still_runs_on_what_goes_into_the_public_bank(client, monkeypatch):
    """Unlimited is not unmoderated. This is the most exposed surface
    memz has — an image here reaches strangers' phones."""
    import app.safety

    monkeypatch.setattr(app.safety, "image_is_safe", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    client.force_login(_user("avi6", staff=True))
    r = client.post(API_URL, {"file": _upload()})
    assert r.status_code == 201, r.content
    assert r.json()["moderation_status"] == "pending", "moderation was skipped for the admin"


# ------------------------------------------------------------ no quota


def test_the_admin_is_not_held_to_the_upload_quota(client, settings):
    """"as many images as I like, not as a normal user." The tier cap is
    set to 1 here, and the bank takes five anyway."""
    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 1, "paid": 1}
    from memz.models import MemeImage

    client.force_login(_user("avi7", staff=True))
    for i in range(5):
        r = client.post(API_URL, {"file": _upload(f"many{i}.png", (10 * i, 90, 150))})
        assert r.status_code == 201, f"upload {i + 1} was refused: {r.content}"
    assert MemeImage.objects.filter(owner__isnull=True, visibility=MemeImage.PUBLIC).count() == 5


def test_the_admin_is_an_ordinary_user_on_the_ordinary_path(client, settings):
    """Avi, confirming the design: "as an admin, I'm a normal login user,
    so I can upload images through the normal way like everybody else,
    and it will count for me as a user. And the view that you just made
    is for me as an admin to upload to the bank for all users ever."

    Both paths, same person, same session — the ordinary one is owned,
    private and *counted*; the bank one is unowned, public and unlimited.
    Staff gets no tier privilege at all (`tiers.tier_for` doesn't look at
    `is_staff`), which is exactly what "it will count for me" means."""
    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 2, "paid": 2}
    from memz.models import MemeImage
    from memz.tiers import tier_for

    admin = _user("avi_both", staff=True)
    client.force_login(admin)
    assert tier_for(admin) == "free", "staff was given a tier of its own"

    # The ordinary way: his own bank, and it counts against his quota.
    for i in range(2):
        r = client.post("/memz/api/images/", {"file": _upload(f"mine{i}.png", (20 * i, 90, 150))})
        assert r.status_code == 201, r.content
        assert MemeImage.objects.get(pk=r.json()["id"]).owner == admin
    over = client.post("/memz/api/images/", {"file": _upload("third.png")})
    assert over.status_code == 400, "the admin was let past the ordinary quota"
    assert MemeImage.objects.filter(owner=admin).count() == 2

    # The bank screen, same person, same moment: unowned, public, and the
    # quota he just hit has nothing to say about it.
    for i in range(3):
        r = client.post(API_URL, {"file": _upload(f"bank{i}.png", (150, 30 * i, 60))})
        assert r.status_code == 201, r.content
        image = MemeImage.objects.get(pk=r.json()["id"])
        assert image.owner is None and image.visibility == MemeImage.PUBLIC

    assert MemeImage.objects.filter(owner=admin).count() == 2, "a bank upload was charged to him"
    assert MemeImage.objects.filter(owner__isnull=True, visibility=MemeImage.PUBLIC).count() == 3


def test_the_ordinary_uploader_still_cannot_reach_the_public_bank(client, settings):
    """The two paths are separate endpoints on purpose: no request to the
    normal one can be talked into writing a public, unowned image."""
    from memz.models import MemeImage

    admin = _user("avi8", staff=True)
    client.force_login(admin)
    r = client.post("/memz/api/images/", {
        "file": _upload(), "owner": "", "visibility": MemeImage.PUBLIC,
    })
    assert r.status_code == 201, r.content
    image = MemeImage.objects.get(pk=r.json()["id"])
    assert image.owner == admin and image.visibility == MemeImage.PRIVATE


# --------------------------------------------------------- taking one back


def test_a_mistake_can_be_deleted_but_only_from_the_public_bank(client):
    from memz.models import MemeImage

    admin = _user("avi9", staff=True)
    client.force_login(admin)
    mine = client.post(API_URL, {"file": _upload()}).json()["id"]

    someone = _user("victim")
    private = MemeImage(owner=someone, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED)
    private.file.save("private.png", ContentFile(_png()), save=True)

    assert client.delete(f"{API_URL}{mine}/").status_code == 204
    assert not MemeImage.objects.filter(pk=mine).exists()

    refused = client.delete(f"{API_URL}{private.pk}/")
    assert refused.status_code == 404, "the bank screen reached into somebody's private bank"
    assert MemeImage.objects.filter(pk=private.pk).exists()
