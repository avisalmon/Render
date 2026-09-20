"""SPR-W.2 — memz: the photo booth (docs/memz/backlog.md, Epic W).

The review's second finding: memz's images are somebody else's pictures,
and the funniest possible picture at any party is of somebody at that
party. So one game mode turns the thirty seconds after "start" into a
scramble in which everyone photographs everyone, and those photos are the
entire evening. No bank, no prep, every meme about someone in the room.

The rules that matter most here are the ones about where those photos
*cannot* go. A picture of somebody's face, taken at a dinner table, is
not bank stock: it belongs to one session, it is reachable from exactly
one query, and it dies with the session that took it. Half of this file
exists to hold that line. Spec references are docs/memz/spec.md.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import conf, dealing, game
from memz.models import MemeImage, Session
from tests.test_memz_screens import browser  # noqa: F401 -- the shared browser fixture

pytestmark = [pytest.mark.sprw2, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    yield


def _photo_bytes(colour=(200, 120, 40)):
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), colour).save(buf, format="JPEG")
    return buf.getvalue()


def _public_image(i=0):
    """An ordinary bank image, for the tests that check the booth's pool
    does *not* include one."""
    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save(f"bank-{i}.jpg", ContentFile(_photo_bytes((10, 10, 10 * i))), save=True)
    return img


def _booth_room(player_count=3, **kwargs):
    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=30, vote_seconds=30,
        game_mode=Session.PHOTO_BOOTH, **kwargs
    )
    others = [game.join_session(session, f"שחקן {i}") for i in range(2, player_count + 1)]
    game.start_session(session, host)
    return session, host, others


def _shoot(session, player, colour=(200, 120, 40)):
    return game.add_booth_photo(
        session, player, ContentFile(_photo_bytes(colour)),
        verdict=MemeImage.APPROVED, note="",
    )


# ------------------------------------------------------- the booth opens


def test_starting_a_photo_booth_game_opens_the_booth_not_round_one():
    """Rule 5.5.1: every other mode goes straight to captioning. This one
    has nothing to caption yet."""
    session, _host, _others = _booth_room()
    session.refresh_from_db()
    assert session.status == Session.BOOTH
    assert session.rounds.count() == 0, "a round was created before there was anything to deal"
    assert session.booth_deadline is not None


def test_the_booth_deadline_is_booth_seconds_away(settings):
    settings.MEMZ_BOOTH_SECONDS = 45
    session, _host, _others = _booth_room()
    session.refresh_from_db()
    left = (session.booth_deadline - timezone.now()).total_seconds()
    assert 40 < left <= 45


def test_an_ordinary_game_is_untouched_and_starts_at_round_one():
    """The booth is one mode, not a new step in every game."""
    _public_image(1)
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    game.join_session(session, "שתיים")
    game.join_session(session, "שלוש")
    game.start_session(session, host)
    session.refresh_from_db()
    assert session.status == Session.PLAYING
    assert session.booth_deadline is None


# ------------------------------------------------------- taking the photos


def test_a_booth_photo_is_owned_by_nobody_and_bound_to_its_session():
    """Rule 5.5.3, the single most important row in this file. `owner` is
    what every bank query keys on; `session` is what the booth's own pool
    keys on. Those two facts together are the whole privacy design."""
    session, host, _others = _booth_room()
    image = _shoot(session, host)
    assert image.owner_id is None
    assert image.session_id == session.id
    assert image.visibility == MemeImage.PRIVATE
    assert image.booth_taken_by_id == host.id


def test_a_guest_with_no_account_can_shoot():
    """Uploading to a bank needs an account (Rule 6.2.1) because a bank
    upload becomes somebody's stock and counts against somebody's quota. A
    booth photo is neither, so the account rule has nothing to say about
    it — and a mode where the guests at the table cannot take part would be
    pointless."""
    session, host, others = _booth_room()
    assert host.user_id is None and others[0].user_id is None
    _shoot(session, others[0])
    assert dealing.booth_photo_count(session) == 1


def test_one_player_cannot_fill_the_booth_alone(settings):
    settings.MEMZ_BOOTH_PHOTOS_PER_PLAYER = 2
    session, host, _others = _booth_room()
    _shoot(session, host)
    _shoot(session, host)
    with pytest.raises(game.GameError):
        _shoot(session, host)
    # ...while everyone else still has their own allowance.
    _shoot(session, _others[0])
    assert dealing.booth_photo_count(session) == 3


def test_the_booth_refuses_photos_once_it_has_closed():
    session, host, _others = _booth_room()
    _shoot(session, host)
    _shoot(session, host)
    game.close_booth(session, host)
    with pytest.raises(game.GameError):
        _shoot(session, host)


def test_an_ordinary_game_has_no_booth_to_shoot_into():
    _public_image(1)
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    game.join_session(session, "שתיים")
    game.join_session(session, "שלוש")
    game.start_session(session, host)
    with pytest.raises(game.GameError):
        _shoot(session, host)


# ------------------------------------- where those photos can never go


def test_a_booth_photo_is_in_no_bank_and_in_no_other_games_pool():
    """The line this whole mode rests on. A photo of somebody at a table
    must be unreachable from every query in the app except its own
    session's pool."""
    session, host, _others = _booth_room()
    booth_photo = _shoot(session, host)

    # Not the public bank.
    public = MemeImage.objects.filter(owner__isnull=True, visibility=MemeImage.PUBLIC)
    assert booth_photo not in public
    # Not any user's own library.
    for qs in (MemeImage.objects.exclude(owner=None), MemeImage.objects.filter(session=None)):
        assert booth_photo not in qs
    # Not another session's pool, of any image_source.
    _public_image(1)
    for source in (Session.MIX, Session.PUBLIC_RANDOM, Session.OWN_ONLY, Session.PACKS):
        other, other_host = game.create_session(
            host_user=None, round_count=1, round_seconds=30, vote_seconds=30, image_source=source,
        )
        game.join_session(other, "שתיים")
        game.join_session(other, "שלוש")
        assert booth_photo not in dealing.pool_for(other), f"a booth photo leaked into {source} mode"


def test_a_booth_photo_is_not_in_the_signed_in_photographers_library():
    """The photographer has an account and a library of their own. The
    photo they just took of the person opposite them is not in it."""
    user = User.objects.create_user("booth-shooter", password="x")
    session, host = game.create_session(
        host_user=user, round_count=1, round_seconds=30, vote_seconds=30, game_mode=Session.PHOTO_BOOTH,
    )
    game.join_session(session, "שתיים")
    game.join_session(session, "שלוש")
    game.start_session(session, host)
    _shoot(session, host)
    assert MemeImage.objects.filter(owner=user).count() == 0


def test_the_nightly_cleanup_really_removes_a_guest_booths_photos(django_capture_on_commit_callbacks):
    """The end of the promise, run the way production runs it.

    A guest session expires `GUEST_SESSION_TTL_HOURS` after it ends and
    `memz_cleanup` deletes it. The room was told the photos go with it, so
    this plays that whole path — expire the session, run the real command,
    and check the rows *and the JPEGs* are gone. The cascade and the file
    cleanup are each tested on their own above; this is the one that says
    the scheduled job actually joins them up."""
    from django.core.management import call_command

    session, host, others = _booth_room()
    a = _shoot(session, host)
    b = _shoot(session, others[0])
    files = [(img.file.storage, img.file.name) for img in (a, b)]
    for storage, name in files:
        assert storage.exists(name)

    Session.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() - timezone.timedelta(hours=1)
    )
    with django_capture_on_commit_callbacks(execute=True):
        call_command("memz_cleanup")

    assert not MemeImage.objects.filter(pk__in=[a.pk, b.pk]).exists()
    for storage, name in files:
        assert not storage.exists(name), f"{name} outlived the party it was taken at"


def test_a_booth_photo_dies_with_its_session():
    session, host, _others = _booth_room()
    _shoot(session, host)
    _shoot(session, host)
    image_id = MemeImage.objects.filter(session=session).first().id
    session.delete()
    assert not MemeImage.objects.filter(pk=image_id).exists()


def test_deleting_an_image_row_deletes_its_file(django_capture_on_commit_callbacks):
    """Rule 6.8.1. The booth promises the room its photos are deleted, and
    a promise kept only in the database is not kept: on a 1 GB disk shared
    with the whole site, every party's photos would otherwise stay on it
    forever."""
    session, host, _others = _booth_room()
    image = _shoot(session, host)
    storage, name = image.file.storage, image.file.name
    assert storage.exists(name)
    # The cleanup runs `on_commit`, so a row rolled back never loses its
    # bytes -- which also means a test inside the usual wrapping
    # transaction has to run the callbacks itself.
    with django_capture_on_commit_callbacks(execute=True):
        image.delete()
    assert not storage.exists(name), "the row went and the JPEG stayed"


def test_a_booth_photo_is_never_offered_to_the_public_bank_by_the_pool():
    """The booth's pool is its own photos *instead of* the bank, not as
    well as it (Rule 5.5.3) — otherwise the mode's premise ("every meme
    tonight is about someone here") is only sometimes true."""
    _public_image(1)
    _public_image(2)
    session, host, _others = _booth_room()
    mine = _shoot(session, host)
    pool = list(dealing.pool_for(session))
    assert pool == [mine]


def test_a_rejected_booth_photo_is_not_dealt():
    """Rule 5.5.5: moderated like every other upload path. These pictures
    are never published, but they go up on a screen in front of a room
    that is sometimes strangers."""
    session, host, _others = _booth_room()
    game.add_booth_photo(
        session, host, ContentFile(_photo_bytes()),
        verdict=MemeImage.REJECTED, note="nope",
    )
    assert dealing.pool_for(session).count() == 0
    assert dealing.booth_photo_count(session) == 1, "it should still count against the photographer's share"


# ------------------------------------------------------- the booth closes


def test_closing_the_booth_starts_the_game_with_the_rooms_own_photos():
    session, host, others = _booth_room()
    a = _shoot(session, host, (10, 200, 10))
    b = _shoot(session, others[0], (200, 10, 10))
    game.close_booth(session, host)
    session.refresh_from_db()
    assert session.status == Session.PLAYING
    round_obj = game.current_round(session)
    dealt = set(round_obj.submissions.values_list("image_id", flat=True))
    assert dealt and dealt <= {a.id, b.id}


def test_only_the_host_can_close_the_booth():
    session, host, others = _booth_room()
    _shoot(session, host)
    _shoot(session, host)
    with pytest.raises(game.GameError):
        game.close_booth(session, others[0])


def test_the_booth_refuses_to_start_a_game_it_has_nothing_to_deal_to(settings):
    """Rule 5.5.4. A host who presses the button too early is told to keep
    shooting rather than dropped into a round with an empty pool."""
    settings.MEMZ_BOOTH_MIN_PHOTOS = 3
    session, host, _others = _booth_room()
    _shoot(session, host)
    with pytest.raises(game.GameError):
        game.close_booth(session, host)
    session.refresh_from_db()
    assert session.status == Session.BOOTH


def test_the_host_pressing_too_early_does_not_reset_the_rooms_clock(settings):
    """The refusal a host gets and the reprieve a timer gets are not the
    same event (Rule 5.5.4). A host who presses at second three and is told
    "keep shooting" still has twenty-seven seconds, not a fresh thirty --
    and their impatience must not unlock the way out (Rule 5.5.6), which
    exists for a booth that genuinely could not fill itself."""
    settings.MEMZ_BOOTH_MIN_PHOTOS = 3
    session, host, _others = _booth_room()
    _shoot(session, host)
    session.refresh_from_db()
    deadline_before = session.booth_deadline

    for _ in range(3):
        with pytest.raises(game.GameError):
            game.close_booth(session, host)
    session.refresh_from_db()
    assert session.booth_deadline == deadline_before, "an impatient host bought the room more time"
    assert session.booth_extensions == 0
    assert game.booth_was_extended(session) is False

    # Two separate things hold that, and this checks the inner one. The
    # outer one is `close_booth`'s own atomic block: it raises, so anything
    # written inside it rolls back anyway. Which means a test that only
    # went through `close_booth` would pass with `extend_if_short` wired
    # wrong -- it did, when this test was first written -- and the
    # parameter would look like dead weight right up until somebody caught
    # that GameError instead of letting it out.
    from memz.game import _end_booth, locked

    with locked(session):
        session.refresh_from_db()
        assert _end_booth(session, extend_if_short=False) is False
    session.refresh_from_db()
    assert session.booth_deadline == deadline_before
    assert session.booth_extensions == 0


def test_the_timer_running_out_too_early_extends_the_booth_instead_of_starting(settings):
    """The same refusal, but nobody pressed anything — so it is a reprieve,
    not an error: the room gets another BOOTH_SECONDS."""
    settings.MEMZ_BOOTH_MIN_PHOTOS = 3
    session, host, _others = _booth_room()
    _shoot(session, host)
    Session.objects.filter(pk=session.pk).update(booth_deadline=timezone.now() - timezone.timedelta(seconds=1))

    game.sync(session.refresh_from_db() or Session.objects.get(pk=session.pk))
    session.refresh_from_db()
    assert session.status == Session.BOOTH
    assert session.booth_deadline > timezone.now()


def test_the_timer_running_out_with_enough_photos_starts_the_game():
    session, host, others = _booth_room()
    _shoot(session, host)
    _shoot(session, others[0])
    Session.objects.filter(pk=session.pk).update(booth_deadline=timezone.now() - timezone.timedelta(seconds=1))

    game.sync(Session.objects.get(pk=session.pk))
    session.refresh_from_db()
    assert session.status == Session.PLAYING
    assert session.booth_deadline is None
    assert game.current_round(session).number == 1


# ------------------------------------------------- the way out (Rule 5.5.6)


def test_a_fresh_booth_offers_no_escape_and_an_extended_one_does(settings):
    """The escape must not be on screen from the first second — it would
    undercut the mode before the room has tried it."""
    settings.MEMZ_BOOTH_MIN_PHOTOS = 3
    session, host, _others = _booth_room()
    assert game.booth_was_extended(session) is False

    _shoot(session, host)
    Session.objects.filter(pk=session.pk).update(booth_deadline=timezone.now() - timezone.timedelta(seconds=1))
    game.sync(Session.objects.get(pk=session.pk))
    session.refresh_from_db()
    assert game.booth_was_extended(session) is True


def test_abandoning_the_booth_plays_an_ordinary_game_and_deletes_the_photos(django_capture_on_commit_callbacks):
    """Rule 5.5.6. Without this a room with no working camera sits in front
    of a disabled button and a clock that keeps restarting. The photos go:
    they were taken under "these stay in this game and are deleted at the
    end of it", and this is that end."""
    _public_image(1)
    _public_image(2)
    session, host, _others = _booth_room()
    taken = _shoot(session, host)
    storage, name = taken.file.storage, taken.file.name

    with django_capture_on_commit_callbacks(execute=True):
        game.abandon_booth(session, host)
    session.refresh_from_db()
    assert session.status == Session.PLAYING
    assert session.game_mode == Session.NORMAL
    assert not MemeImage.objects.filter(pk=taken.pk).exists()
    assert not storage.exists(name)
    dealt = set(game.current_round(session).submissions.values_list("image_id", flat=True))
    assert dealt and taken.id not in dealt, "the game must be playable from the ordinary pool"


def test_only_the_host_can_abandon_the_booth():
    _public_image(1)
    session, host, others = _booth_room()
    with pytest.raises(game.GameError):
        game.abandon_booth(session, others[0])


# ------------------------------------------------------------- the screens


def test_the_state_payload_carries_what_the_booth_screen_needs(settings):
    settings.MEMZ_BOOTH_PHOTOS_PER_PLAYER = 3
    session, host, others = _booth_room()
    _shoot(session, host)
    _shoot(session, others[0])

    from memz import state

    payload = state.build(session, host)
    assert payload["status"] == Session.BOOTH
    booth = payload["booth"]
    assert booth["total_photos"] == 2
    assert booth["my_photos"] == 1
    assert booth["per_player"] == 3
    assert booth["is_host"] is True
    assert booth["deadline"]

    # The big screen has no player, so it has no "my photos" and no button.
    tv = state.build(session, None)
    assert tv["booth"]["my_photos"] == 0
    assert tv["booth"]["is_host"] is False


def test_the_booth_payload_never_names_the_photographer():
    """Rule 4.7.1 reaches the booth too: who took the picture is as
    anonymous as who wrote the caption. `booth_taken_by` exists to hold one
    player to their share, and for nothing else."""
    session, host, _others = _booth_room()
    _shoot(session, host)

    from memz import state

    body = str(state.build(session, host))
    assert "booth_taken_by" not in body
    assert "photographer" not in body


def test_the_booth_photo_endpoint_needs_a_player_in_this_session(client):
    session, _host, _others = _booth_room()
    response = client.post(
        f"/memz/api/sessions/{session.code}/booth/photo/",
        {"file": ContentFile(_photo_bytes(), name="p.jpg")},
    )
    assert response.status_code in (401, 403)
    assert dealing.booth_photo_count(session) == 0


def test_the_booth_photo_endpoint_accepts_a_photo_and_returns_the_new_state(client):
    session, host, _others = _booth_room()
    response = client.post(
        f"/memz/api/sessions/{session.code}/booth/photo/",
        {"file": ContentFile(_photo_bytes(), name="p.jpg")},
        HTTP_X_MEMZ_PLAYER=host.guest_token,
    )
    assert response.status_code == 201, response.content
    assert response.json()["booth"]["my_photos"] == 1
    # And it went through the ordinary upload processing: no 400KB camera
    # original sitting on the disk (ACT-Z.16).
    image = MemeImage.objects.get(session=session)
    assert image.file.name.endswith(".jpg")


def test_the_create_screen_offers_the_mode_and_hides_the_pool_picker(client):
    """The image-source picker would be a control that appears to choose
    something and doesn't, so the create screen hides it in this mode and
    says what happens instead."""
    user = User.objects.create_user("booth-host", password="x")
    client.force_login(user)
    body = client.get("/memz/new/").content.decode()
    assert 'value="photo_booth"' in body
    assert "data-booth-note" in body
    assert "data-image-source-field" in body

    js = (Session.__module__ and open("static/memz/game_new.js", encoding="utf-8").read())
    assert "photo_booth" in js and "imageSourceParts" in js


def test_the_booth_camera_lives_outside_the_poll_driven_game_root(client):
    """Same defect the lobby uploader was moved out for (SPR-Z.11): the
    booth polls every second, and a photo being chosen or uploaded must
    survive that."""
    session, host, _others = _booth_room()
    body = client.get(f"/memz/s/{session.code}/").content.decode()
    root_at = body.index("data-game-root")
    booth_at = body.index("data-booth-upload")
    assert booth_at > root_at
    # And no login gate on it: guests at the table shoot too.
    before = body[:booth_at]
    assert before.count("{% if") == 0
    assert "data-booth-uploader" in body


def test_the_escape_is_on_the_extended_booth_and_not_the_fresh_one(browser, live_server, settings):
    """The contract file renders both booths and checks their layout; this
    checks the thing that distinguishes them, which is a control that must
    be absent until the room has actually failed (Rule 5.5.6)."""
    settings.MEMZ_BOOTH_MIN_PHOTOS = 3
    session, host, _others = _booth_room()
    _shoot(session, host)

    def escape_visible():
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        context.add_init_script(
            "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
        )
        page = context.new_page()
        page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
        page.wait_for_timeout(700)
        found = page.locator("[data-booth-abandon]").count() > 0
        shooting = page.locator("[data-uploader-take]").count() > 0
        context.close()
        return found, shooting

    fresh, camera = escape_visible()
    assert fresh is False, "the way out was offered before the room had a chance"
    assert camera is True, "sanity: the booth's camera should be on screen"

    Session.objects.filter(pk=session.pk).update(booth_extensions=1)
    extended, _ = escape_visible()
    assert extended is True, "a booth that ran out of time left its host with no way out"


def test_an_anonymous_guest_sees_the_booth_camera(client):
    """The lobby's own uploader is behind `user.is_authenticated`, because
    it writes to a bank. This one must not be."""
    session, _host, _others = _booth_room()
    body = client.get(f"/memz/s/{session.code}/").content.decode()
    assert "data-booth-uploader" in body
    assert "data-lobby-uploader" not in body, "sanity: the bank uploader IS gated, so this test can tell them apart"
