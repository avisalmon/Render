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


def test_the_full_bank_reaches_eight_packs_after_the_real_content_seed(seeded_z7):
    from memz.models import Pack

    packs = Pack.objects.filter(owner__isnull=True, is_public=True)
    assert packs.count() == 8
    for slug in ("family", "animals", "work", "school", "friends", "food", "holidays", "sports"):
        assert packs.filter(slug=slug).exists(), f"pack {slug!r} missing"


def test_the_new_bank_images_carry_the_real_content_note_not_placeholder(seeded_z7):
    from memz.models import MemeImage

    real = MemeImage.objects.filter(seed_key__contains="friends/friends-")
    assert real.exists()
    for image in real:
        assert "placeholder" not in image.moderation_note
        assert image.moderation_status == MemeImage.APPROVED


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
