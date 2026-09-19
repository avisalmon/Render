"""ACT-Z.18 — memz: a player's own image library, with a door on it.

Avi: "every user should be able to go to his image library with his
limited count and be able to, as we said, upload but also see and delete
images if he wants to replace the images with others. So make this view
for every user that is logged in to be able to add and delete images."

Almost all of it already worked — as one section of a seven-section
profile page that the whole app linked to exactly once, from a small
button on the home screen. So this is a screen of its own, the duplicate
implementation removed rather than a third one added, and the doors that
were missing.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image

pytestmark = [pytest.mark.actz18, pytest.mark.django_db]

URL = "/memz/images/"


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


def _user(name="player"):
    return User.objects.create_user(name, email=f"{name}@example.com", password="x")


def _own_image(user, name="mine.png", status=None):
    from memz.models import MemeImage

    img = MemeImage(
        owner=user, visibility=MemeImage.PRIVATE,
        moderation_status=status or MemeImage.APPROVED,
    )
    img.file.save(name, ContentFile(_png()), save=True)
    return img


# ------------------------------------------------------------- the door


def test_a_signed_out_visitor_is_sent_to_sign_in(client):
    r = client.get(URL)
    assert r.status_code == 302
    assert "/login/" in r["Location"]


def test_every_signed_in_user_has_the_screen(client):
    """Not staff-only, not paid-only: "every user that is logged in"."""
    client.force_login(_user("anyone"))
    r = client.get(URL)
    assert r.status_code == 200
    assert "data-library-uploader" in r.content.decode()


def test_the_screen_is_reachable_without_knowing_the_address(client):
    """The whole point of this act. Before it, the library sat inside the
    profile, and the profile was linked from exactly one small button on
    one page — the account name in the header was a plain span."""
    user = _user("finder")
    client.force_login(user)

    home = client.get("/memz/").content.decode()
    assert URL in home, "the home screen offers no way to a player's own photos"

    header_link = f'class="memz-account-name" href="/memz/me/"'
    assert header_link in home, "the account name in the header is still not a link"

    profile = client.get("/memz/me/").content.decode()
    assert URL in profile, "the profile does not lead to the library it used to contain"


# --------------------------------------------------- see, add, and delete


def test_it_shows_this_users_own_images_and_nobody_elses(client):
    me, someone = _user("me"), _user("other")
    mine = _own_image(me, "mine.png")
    theirs = _own_image(someone, "theirs.png")

    client.force_login(me)
    body = client.get(URL).content.decode()
    assert f'data-library-row="{mine.pk}"' in body
    assert f'data-library-row="{theirs.pk}"' not in body, "another player's photo is on this screen"


def test_the_quota_is_on_the_screen_and_says_when_it_is_full(client, settings):
    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 2, "paid": 50}
    user = _user("counter")
    _own_image(user, "one.png")
    client.force_login(user)

    body = client.get(URL).content.decode()
    assert "(1/2)" in body, "the screen does not say how much of the quota is used"
    assert "הגעתם למכסה" not in body

    _own_image(user, "two.png")
    full = client.get(URL).content.decode()
    assert "(2/2)" in full
    assert "הגעתם למכסה" in full, "a full library does not say so, or say what to do about it"


def test_upload_and_delete_both_work_for_an_ordinary_user(client, settings):
    """The two verbs Avi asked for, through the same API the screen uses,
    including the replace-when-full path: delete one, add another."""
    settings.MEMZ_UPLOAD_LIMIT = {"guest": 0, "free": 1, "paid": 50}
    from memz.models import MemeImage

    user = _user("swapper")
    client.force_login(user)

    first = client.post("/memz/api/images/", {"file": ContentFile(_png(), name="a.png")})
    assert first.status_code == 201, first.content
    blocked = client.post("/memz/api/images/", {"file": ContentFile(_png(), name="b.png")})
    assert blocked.status_code == 400, "the quota is not being enforced at all"

    assert client.delete(f"/memz/api/images/{first.json()['id']}/").status_code == 204
    assert not MemeImage.objects.filter(owner=user).exists()

    again = client.post("/memz/api/images/", {"file": ContentFile(_png(), name="c.png")})
    assert again.status_code == 201, "deleting did not free up room for a replacement"


def test_a_player_cannot_delete_somebody_elses_image(client):
    from memz.models import MemeImage

    me, someone = _user("me2"), _user("other2")
    theirs = _own_image(someone, "theirs2.png")
    client.force_login(me)

    assert client.delete(f"/memz/api/images/{theirs.pk}/").status_code == 404
    assert MemeImage.objects.filter(pk=theirs.pk).exists()


# --------------------------------------- one implementation, not several


def test_the_profile_no_longer_carries_a_second_copy_of_the_library(client):
    """It links to the screen instead. Two implementations of upload and
    delete would drift apart, and the profile's copy was the one nobody
    could find."""
    user = _user("tidy")
    _own_image(user, "p.png")
    client.force_login(user)
    body = client.get("/memz/me/").content.decode()

    assert "data-profile-uploader" not in body, "the profile still has its own uploader"
    assert "data-delete-image" not in body, "the profile still has its own delete buttons"
    assert URL in body

    from pathlib import Path

    profile_js = Path("static/memz/profile.js").read_text(encoding="utf-8")
    assert "mountUploader" not in profile_js
    assert "data-delete-image" not in profile_js


def test_both_libraries_run_on_the_same_script(client):
    """The player's screen and the admin's bank screen are the same screen
    with different plumbing, so they share `library.js` rather than
    keeping two copies of upload/show/delete in step by hand."""
    from pathlib import Path

    assert not Path("static/memz/bank.js").exists(), "the bank's own copy of the script is still there"

    client.force_login(_user("scripty"))
    assert "memz/library.js" in client.get(URL).content.decode()

    admin = User.objects.create_user("adm", email="adm@example.com", password="x", is_staff=True)
    client.force_login(admin)
    assert "memz/library.js" in client.get("/memz/bank/").content.decode()
