"""SPR-Z.9 — memz: a joining player's own uploads become part of a shared
game (docs/memz/spec.md Rule 6.5.3, Rule 6.2.5, docs/memz/backlog.md).

Every test here plays through `memz.game`/`memz.dealing` directly, same
discipline as every earlier sprint.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import conf, dealing, game
from memz.models import MemeImage, Pack, PackImage, Round, Session

pytestmark = [pytest.mark.sprz9, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")


def _png_bytes(color):
    buf = io.BytesIO()
    Image.new("RGB", (300, 220), color).save(buf, format="PNG")
    return buf.getvalue()


_user_counter = [0]


def _user():
    _user_counter[0] += 1
    return User.objects.create_user(f"z9user{_user_counter[0]}", email=f"z9user{_user_counter[0]}@example.com", password="x")


_image_counter = [0]


def _image(owner, color=(10, 20, 30)):
    _image_counter[0] += 1
    img = MemeImage(
        owner=owner, visibility=MemeImage.PUBLIC if owner is None else MemeImage.PRIVATE,
        moderation_status=MemeImage.APPROVED,
    )
    img.file.save(f"z9-{_image_counter[0]}.png", ContentFile(_png_bytes(color)), save=True)
    return img


def _public_pack(images):
    pack = Pack.objects.create(owner=None, slug=f"z9pack{Pack.objects.count()}", name="z9 pack", is_public=True)
    for i, img in enumerate(images):
        PackImage.objects.create(pack=pack, image=img, order=i)
    return pack


# ------------------------------------------------------------- upload quota


def test_upload_limit_is_thirty_free_fifty_paid_zero_guest():
    """SPR-Z.11 raised the free tier from 5 to 30: the players' own photos
    are now half of what a game deals (Rule 6.5.3), and five of them is a
    sample, not a bank — enough to run out inside a single evening."""
    assert conf.cap("UPLOAD_LIMIT", "guest") == 0
    assert conf.cap("UPLOAD_LIMIT", "free") == 30
    assert conf.cap("UPLOAD_LIMIT", "paid") == 50


def test_profile_page_carries_the_upload_safety_notice(client):
    user = _user()
    client.force_login(user)
    body = client.get("/memz/me/").content.decode()
    assert "לא נוח לכם שאחרים יראו" not in body   # sanity: not asserting on a typo
    assert "סלבריטאים" in body and "ממים קיימים" in body


# --------------------------------------------------------------- the pool


def test_own_only_pool_includes_every_seated_signed_in_players_images():
    host = _user()
    other = _user()
    host_img = _image(host, (5, 5, 5))
    other_img = _image(other, (6, 6, 6))

    session, _host_player = game.create_session(
        host_user=host, round_count=1, round_seconds=30, vote_seconds=15,
        image_source=Session.OWN_ONLY,
    )
    game.join_session(session, "שחקן שני", user=other)

    pool_ids = {img.id for img in dealing.pool_for(session)}
    assert pool_ids == {host_img.id, other_img.id}


def test_own_only_pool_ignores_a_players_images_once_they_have_left_the_session():
    """The pool is who is *seated*, not everyone who ever joined — no
    stale contribution from someone who left."""
    host = _user()
    other = _user()
    _image(host, (7, 7, 7))
    other_img = _image(other, (8, 8, 8))

    session, _host_player = game.create_session(
        host_user=host, round_count=1, round_seconds=30, vote_seconds=15,
        image_source=Session.OWN_ONLY,
    )
    joined = game.join_session(session, "שחקן שני", user=other)
    assert other_img.id in {img.id for img in dealing.pool_for(session)}

    joined.is_active = False
    joined.user = None   # simulate a fully-departed seat (release-style), not just idle
    joined.save()
    assert other_img.id not in {img.id for img in dealing.pool_for(session)}


def test_a_guest_player_contributes_no_images_to_own_only():
    host = _user()
    host_img = _image(host, (9, 9, 9))
    session, _host_player = game.create_session(
        host_user=host, round_count=1, round_seconds=30, vote_seconds=15,
        image_source=Session.OWN_ONLY,
    )
    game.join_session(session, "אורח", user=None)   # a guest, no account

    pool_ids = {img.id for img in dealing.pool_for(session)}
    assert pool_ids == {host_img.id}


# ---------------------------------------------------------------- dealing


def _play_round(session, host_player, all_players):
    """One full round to `done` and on to the next (or the podium),
    nobody voting for anybody in particular -- these tests are about what
    got *dealt*, not who won."""
    round_obj = game.current_round(session)
    for p in all_players:
        game.submit_caption(session, p, round_obj.number, caption_text="x")
    round_obj.refresh_from_db()
    if round_obj.status == Round.CAPTIONING:
        Round.objects.filter(pk=round_obj.pk).update(caption_deadline=timezone.now() - timezone.timedelta(seconds=1))
        game.sync(session)
    round_obj.refresh_from_db()
    if round_obj.status == Round.REVEALED:
        game.advance(session, host_player)
    round_obj.refresh_from_db()
    if round_obj.status == Round.VOTING:
        Round.objects.filter(pk=round_obj.pk).update(vote_deadline=timezone.now() - timezone.timedelta(seconds=1))
        game.sync(session)
    round_obj.refresh_from_db()
    if round_obj.status == Round.DONE:
        game.advance(session, host_player)
    return round_obj


def test_deal_round_never_deals_a_player_their_own_image_when_an_alternative_exists():
    host = _user()
    host_img = _image(host, (1, 0, 0))
    other = _user()
    other_img = _image(other, (0, 1, 0))
    pack = _public_pack([_image(None, (0, 0, 1)) for _ in range(10)])

    session, host_player = game.create_session(
        host_user=host, round_count=4, round_seconds=30, vote_seconds=15,
        scoring_mode=Session.VOTE, image_source=Session.MIX, packs=[pack],
    )
    other_player = game.join_session(session, "אחר", user=other)
    third = game.join_session(session, "שלישי", user=_user())
    game.start_session(session, host_player)
    all_players = [host_player, other_player, third]

    for _ in range(4):
        round_obj = game.current_round(session)
        submissions = {s.player_id: s.image_id for s in round_obj.submissions.all()}
        assert submissions.get(host_player.id) != host_img.id
        assert submissions.get(other_player.id) != other_img.id
        _play_round(session, host_player, all_players)


def test_deal_round_stays_at_or_under_the_thirty_percent_stock_cap():
    host = _user()
    _image(host, (2, 0, 0))
    other = _user()
    _image(other, (0, 2, 0))
    pack = _public_pack([_image(None, (0, 0, c)) for c in range(20)])

    session, host_player = game.create_session(
        host_user=host, round_count=8, round_seconds=30, vote_seconds=15,
        scoring_mode=Session.VOTE, image_source=Session.MIX, packs=[pack],
    )
    other_player = game.join_session(session, "אחר", user=other)
    third = game.join_session(session, "שלישי", user=_user())
    game.start_session(session, host_player)
    all_players = [host_player, other_player, third]

    total = personal = 0
    for _ in range(8):
        round_obj = game.current_round(session)
        for s in round_obj.submissions.all():
            total += 1
            if s.image.owner_id is not None:
                personal += 1
        _play_round(session, host_player, all_players)

    assert total > 0
    assert personal / total <= dealing.PLAYER_STOCK_MAX_SHARE + 1e-9


def test_deal_round_uses_at_least_one_personal_image_in_the_first_round_when_available():
    host = _user()
    _image(host, (3, 0, 0))
    pack = _public_pack([_image(None, (0, 0, c)) for c in range(10)])

    session, host_player = game.create_session(
        host_user=host, round_count=1, round_seconds=30, vote_seconds=15,
        scoring_mode=Session.VOTE, image_source=Session.MIX, packs=[pack],
    )
    game.join_session(session, "שתיים", user=_user())
    game.join_session(session, "שלוש", user=_user())
    game.start_session(session, host_player)

    round_obj = game.current_round(session)
    owners = {s.image.owner_id for s in round_obj.submissions.all()}
    assert host.id in owners   # host's own image landed on *someone else* this round


def test_deal_same_image_can_come_from_a_seated_players_own_stock():
    host = _user()
    personal = _image(host, (4, 0, 0))
    pack = _public_pack([_image(None, (0, 0, c)) for c in range(5)])

    session, host_player = game.create_session(
        host_user=host, round_count=1, round_seconds=30, vote_seconds=15,
        game_mode=Session.SAME_MEME, scoring_mode=Session.VOTE, image_source=Session.MIX, packs=[pack],
    )
    game.join_session(session, "שתיים", user=_user())
    game.join_session(session, "שלוש", user=_user())
    game.start_session(session, host_player)

    round_obj = game.current_round(session)
    image_ids = {s.image_id for s in round_obj.submissions.all()}
    assert image_ids == {personal.id}   # the one shared image, and it's the personal one


def test_own_only_mode_keeps_dealing_personal_images_with_no_public_fallback():
    """own_only has no non-personal images at all -- the 30% cap must never
    starve it; every round still deals real images."""
    host = _user()
    for c in range(20):
        _image(host, (c, 0, 0))

    session, host_player = game.create_session(
        host_user=host, round_count=6, round_seconds=30, vote_seconds=15,
        scoring_mode=Session.VOTE, image_source=Session.OWN_ONLY,
    )
    p2 = game.join_session(session, "שתיים", user=_user())
    p3 = game.join_session(session, "שלוש", user=_user())
    game.start_session(session, host_player)
    all_players = [host_player, p2, p3]

    for _ in range(6):
        round_obj = game.current_round(session)
        submissions = list(round_obj.submissions.all())
        assert len(submissions) == 3
        assert all(s.image_id is not None for s in submissions)
        _play_round(session, host_player, all_players)
