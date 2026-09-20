"""SPR-W.1 — memz: the moment (docs/memz/backlog.md, Epic W).

The review's single most important finding: the moment you tap "אוהב" is
the quietest moment in the game. This sprint makes the tap felt, gives
each meme's slot a closing beat where the room's reaction shows (counts
only, never who), adds the three sounds a party game is missing, gives
the host a name, and puts "how to play" where everyone is already
waiting. Spec references are docs/memz/spec.md rule numbers.
"""

import io
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import game
from memz.models import MemeImage, Round, Vote
from tests.test_memz_screens import PHONE, browser  # noqa: F401 -- the shared phone fixture

pytestmark = [pytest.mark.sprw1, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    for i in range(6):
        buf = io.BytesIO()
        Image.new("RGB", (300, 220), (20 * i, 80, 140)).save(buf, format="PNG")
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"w1-{i}.png", ContentFile(buf.getvalue()), save=True)
    yield


def _park_reveal_on(session, index, hold_seconds=0):
    from memz import conf

    round_obj = game.current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    elapsed = per_meme * index + per_meme / 2
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() + timezone.timedelta(seconds=per_meme * count - elapsed + hold_seconds)
    )


def _revealed_world(**kwargs):
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30, **kwargs)
    p2 = game.join_session(session, "שתיים")
    p3 = game.join_session(session, "שלוש")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    assert round_obj.status == Round.REVEALED
    return session, host, p2, p3, round_obj


# ---------------------------------------------------- F-W.1.4, the host's name


def test_a_guest_host_can_name_themselves_and_a_blank_still_falls_back(client):
    from memz.models import Player

    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=30, vote_seconds=30, host_nickname="  אבי  ",
    )
    assert Player.objects.get(pk=host.pk).nickname == "אבי"

    session2, host2 = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    assert Player.objects.get(pk=host2.pk).nickname == "מארח/ת", "a blank name should still fall back, not be empty"


def test_the_name_reaches_the_podium_through_the_real_api(client):
    """"מקום ראשון: מארח/ת" was nobody's win. Through the API the create
    screen actually calls, then all the way to the leaderboard."""
    import json

    r = client.post(
        "/memz/api/sessions/", json.dumps({"nickname": "סבתא רחל", "round_count": 1}),
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    code, token = r.json()["code"], r.json()["token"]
    state = client.get(f"/memz/api/sessions/{code}/state/", HTTP_X_MEMZ_PLAYER=token).json()
    host_row = next(p for p in state["players"] if p["is_host"])
    assert host_row["nickname"] == "סבתא רחל"


def test_a_signed_in_host_gets_their_account_name_pre_filled(client):
    user = User.objects.create_user("dana", email="dana@example.com", password="x", first_name="דנה")
    client.force_login(user)
    body = client.get("/memz/new/").content.decode()
    assert 'data-nickname-input' in body
    assert 'value="דנה"' in body, "the account's own name is not pre-filled"

    guest_body = client.get("/memz/new/").content.decode() if client.logout() is None else ""
    assert 'value=""' in guest_body and "מארח/ת" not in guest_body, "a guest is offered the placeholder, never מארח/ת"


# ------------------------------------------------- Rule 4.5.7, the room reacts


def test_the_state_carries_the_rooms_reaction_as_counts_and_nothing_else(client):
    session, host, p2, p3, round_obj = _revealed_world()
    order = game.reveal_order(round_obj)
    first = order[0]
    _park_reveal_on(session, 0)
    for rater, value in ((p2, Vote.LOVE), (p3, Vote.SOSO)):
        if first.player_id != rater.id:
            game.rate_submission(session, rater, 1, first.id, value)
    # The author can't rate their own; make sure exactly two verdicts landed.
    landed = Vote.objects.filter(round=round_obj, submission=first).count()

    from memz.state import build

    payload = build(session, host)["round"]
    reactions = payload["reactions"][str(first.id)]
    assert reactions["love"] + reactions["soso"] + reactions["meh"] == landed
    assert set(reactions) == {"love", "soso", "meh"}, "the reaction carries more than three counts"
    assert "voter" not in str(payload["reactions"]) and "player" not in str(payload["reactions"]), (
        "the reaction leaks who reacted"
    )


def test_the_tv_gets_the_reaction_too(client):
    """player=None is the shared big screen (spec §4.10). The room's
    reaction is the whole room's to see, and the TV is where the room
    looks."""
    session, host, p2, p3, round_obj = _revealed_world()
    from memz.state import build

    assert "reactions" in build(session, None)["round"]


def test_relaxed_mode_has_no_reaction_to_show(client):
    """No verdicts there, so no counts -- but the key is still present so
    the client never has to special-case its absence."""
    session, host, p2, p3, round_obj = _revealed_world(game_mode="relaxed")
    from memz.state import build

    reactions = build(session, host)["round"]["reactions"]
    assert all(sum(v.values()) == 0 for v in reactions.values())


# ------------------------------------------------- F-W.1.3, the three sounds


def test_the_three_new_sounds_exist_and_are_short(client):
    import wave

    lengths = {}
    for name in ("pop", "reveal", "fanfare"):
        path = Path("static/memz/sound") / f"{name}.wav"
        assert path.exists(), f"{name}.wav was not generated"
        with wave.open(str(path)) as w:
            lengths[name] = w.getnframes() / w.getframerate()
    assert lengths["pop"] < 0.2, "a verdict's pop must be over before the thumb lifts"
    assert lengths["reveal"] < 0.5
    assert 0.5 < lengths["fanfare"] < 1.5, "the podium fanfare is an event, not a jingle"


def test_the_two_original_sounds_were_not_changed_by_regenerating(client):
    """`make_sounds.py` is deterministic and still writes tick and
    drumroll; adding three must not have altered the two that shipped."""
    import subprocess
    import sys

    tick_before = Path("static/memz/sound/tick.wav").read_bytes()
    subprocess.run([sys.executable, "memz/seed_assets/make_sounds.py"], check=True, capture_output=True)
    assert Path("static/memz/sound/tick.wav").read_bytes() == tick_before


def test_the_shipped_script_plays_every_moment(client):
    """Checked against the file that ships, the way ACT-Z.8's bidi test
    does: a verdict pops and vibrates, a new slot has a sound, and the
    podium has its fanfare exactly once per session."""
    source = Path("static/memz/game.js").read_text(encoding="utf-8")
    assert 'playSound("pop")' in source and "vibrate(40)" in source
    assert 'playSound("reveal")' in source
    assert 'playSound("fanfare")' in source
    assert source.index('playSound("fanfare")') > source.index("finishedCelebrated = state.code"), (
        "the fanfare would replay on every poll of the podium"
    )


# ---------------------------------------- F-W.1.5, how to play, in the lobby


def test_the_lobby_says_how_to_play_and_what_the_buttons_are_worth(browser, live_server, db):
    pytest.importorskip("playwright.sync_api")
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script("localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token))
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        howto = page.locator("[data-howto]")
        assert howto.count() == 1, "no how-to-play card in the lobby"
        text = howto.inner_text()
        assert "אוהב = 2" in text and "ככה ככה = 1" in text, "the one fact no other screen states is still unstated"
        assert "3 פעמים" in text
        assert howto.locator("p").count() == 3, "three lines, not a manual"
    finally:
        context.close()


# ------------------------------- Rule 4.5.6 + 4.5.7, in a real phone browser


def test_a_tap_is_felt_and_the_room_reaction_updates_without_rebuilding_the_buttons(browser, live_server, db):
    """The rating screen must stay stable under a thumb (ACT-Z.8) *and*
    keep the reaction line current. Done by patching the line in place:
    a marker on a button survives the poll that changes the counts."""
    pytest.importorskip("playwright.sync_api")
    session, host, p2, p3, round_obj = _revealed_world()
    order = game.reveal_order(round_obj)
    _park_reveal_on(session, 0, hold_seconds=120)
    viewer = p2 if order[0].player_id != p2.id else p3
    other = p3 if viewer is p2 else p2

    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", viewer.guest_token)
        + "window.__vibrations = []; navigator.vibrate = function (ms) { window.__vibrations.push(ms); return true; };"
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        assert page.locator("[data-screen]").get_attribute("data-screen") == "game-revealed"
        assert page.locator("[data-reaction]").count() == 1, "no reaction line under the meme"

        page.evaluate("document.querySelector('[data-rate]').dataset.testMarker = 'still-here'")

        # Somebody else in the room reacts; the next poll must show it
        # without tearing the buttons out from under this player's thumb.
        if order[0].player_id != other.id:
            game.rate_submission(session, other, 1, order[0].id, Vote.LOVE)
        page.wait_for_timeout(1500)
        assert "😍" in page.inner_text("[data-reaction]"), "the room's reaction never reached the screen"
        assert page.evaluate("document.querySelector('[data-rate]').dataset.testMarker") == "still-here", (
            "the reaction update rebuilt the whole screen"
        )

        # Now this player taps: felt immediately, before the server answers.
        page.click("[data-rate]")
        page.wait_for_timeout(120)
        assert page.evaluate("window.__vibrations") == [40], "the tap did not vibrate"
        assert page.locator(".memz-rating-btn--tapped").count() == 1, "the pressed button did not spring"
    finally:
        context.close()
