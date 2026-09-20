"""SPR-W.3 — memz: the evening's card (docs/memz/backlog.md, Epic W).

memz's growth loop is one person showing somebody a picture, and the end
of a game had nothing to show: a leaderboard on a phone and a gallery of
memes that each need explaining. So the podium renders two pictures
server-side — the meme of the night, and the final table — each one
WhatsApp tap away.

Two things get most of the tests. The first is that the meme card carries
no author, because Rule 4.7.1's promise ("nobody finds out who wrote
what") is worth more on a card than anywhere else: a card outlives the
evening. The second is that the Hebrew on them is the right way round,
which in this codebase is not a paranoid check — it shipped backwards
twice (ACT-Z.10, ACT-Z.11) and the second time only because production's
Pillow is built differently from the one here.
"""

import io

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import conf, game, share_cards
from memz.models import MemeImage, Round, Session, Vote

pytestmark = [pytest.mark.sprw3, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    for i in range(6):
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), (30 * i, 90, 150)).save(buf, format="PNG")
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"w3-{i}.png", ContentFile(buf.getvalue()), save=True)
    yield


def _show_slot(session, index):
    round_obj = game.current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per = conf.get("REVEAL_SECONDS_PER_MEME")
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() + timezone.timedelta(seconds=per * count - (per * index + per / 2))
    )


def _finished_game(captions=None, rate=True):
    """A real 3-player game played to the podium through the state machine."""
    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=30, vote_seconds=20, host_nickname="אבי",
    )
    p2 = game.join_session(session, "מיכל")
    p3 = game.join_session(session, "יונתן")
    game.start_session(session, host)
    players = [host, p2, p3]
    texts = captions or ["כשאמא אומרת שהיא מסדרת רק קצת", "אני בשבע בבוקר", "מי שם את זה שם"]
    for player, text in zip(players, texts):
        game.submit_caption(session, player, 1, caption_text=text)

    if rate:
        order = game.reveal_order(game.current_round(session))
        for index, submission in enumerate(order):
            _show_slot(session, index)
            for rater in players:
                if submission.player_id == rater.id:
                    continue
                game.rate_submission(session, rater, 1, submission.id, Vote.LOVE if index == 0 else Vote.SOSO)

    game.advance(session, host)
    session.refresh_from_db()
    while session.status != Session.FINISHED:
        game.advance(session, host)
        session.refresh_from_db()
    return session, host, p2, p3


def _open(data):
    return Image.open(io.BytesIO(data))


# ------------------------------------------------------------ they render


def test_both_cards_render_as_real_jpegs():
    session, _host, _p2, _p3 = _finished_game()
    meme, _points = share_cards.meme_of_the_night(session)
    podium = share_cards.podium_card(session)
    for data in (meme, podium):
        image = _open(data)
        assert image.format == "JPEG"
        assert image.width == share_cards.CARD_WIDTH
        assert image.height > 200


def test_the_meme_card_is_the_highest_scoring_meme_of_the_session():
    """Recomputed from Vote rows, not read from a cached total — the same
    rule the podium itself follows (Rule 5.3.1)."""
    session, _host, _p2, _p3 = _finished_game()
    best, points = share_cards.best_submission(session)
    everything = {}
    for round_obj in session.rounds.all():
        from memz.scoring import round_scores

        everything.update(round_scores(round_obj))
    assert points == max(everything.values())
    assert everything[best.id] == points


def test_a_game_nobody_submitted_to_has_a_podium_and_no_meme_card():
    """A card that says nothing is worse than no card, so the meme one is
    allowed not to exist while the podium always does."""
    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=30, vote_seconds=20,
    )
    game.join_session(session, "מיכל")
    game.join_session(session, "יונתן")
    game.start_session(session, host)
    Round.objects.filter(session=session).update(
        caption_deadline=timezone.now() - timezone.timedelta(seconds=1)
    )
    game.sync(session)
    session.refresh_from_db()
    while session.status != Session.FINISHED:
        game.advance(session, host)
        session.refresh_from_db()

    assert share_cards.meme_of_the_night(session)[0] is None
    assert share_cards.podium_card(session)     # the table still exists


# ------------------------------------------------- the Hebrew is not reversed


def test_the_cards_use_the_meme_engines_own_bidi_path():
    """Not a style preference. `shape_for_draw` is the function that picks
    between "this Pillow reorders RTL itself" (production, raqm) and "this
    one has no idea" (Windows), and choosing wrong is precisely how Hebrew
    shipped backwards twice. A card drawing Hebrew any other way would be
    the third time, on the one artifact built to be forwarded."""
    source = (share_cards.__file__ and open(share_cards.__file__, encoding="utf-8").read())
    assert "shape_for_draw" in source
    assert "PIL_HAS_RAQM" in source
    # And no raw draw.text on a Hebrew literal: every Hebrew string on a
    # card goes through _draw_rtl.
    import re

    for line in source.splitlines():
        if "draw.text(" in line and re.search(r"[֐-׿]", line):
            raise AssertionError(f"Hebrew drawn without the bidi path: {line.strip()}")


def test_the_count_phrase_places_its_number_rather_than_composing_one_string():
    """A digit at the edge of an RTL string lands wherever the bidi
    algorithm's boundary rules put it, which is not always where the
    sentence means. The two pieces are drawn separately and the number is
    placed to the right, as Hebrew reads."""
    from PIL import ImageDraw

    from memz.render import _font

    canvas = Image.new("RGB", (600, 120), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(40)
    share_cards._draw_count_phrase(draw, 560, 20, 7, "אוהבים מהחדר", font, font, (255, 255, 255))

    # The rightmost ink on the line belongs to the digit: crop the right
    # edge and check something was drawn there.
    right_strip = canvas.crop((520, 0, 570, 120))
    assert right_strip.getextrema()[0][1] > 0, "nothing was drawn where the number should be"


# --------------------------------------------------------------- anonymity


def test_the_meme_card_looks_the_same_whoever_wrote_the_meme():
    """Rule 4.7.1 reaches the card, tested on the pixels rather than on the
    source: rename every player, render again, and the meme card must come
    back **byte for byte identical**. Nothing about who made it can be on
    it if changing all three names changes nothing.

    The podium card is rendered alongside as the control — if renaming
    everyone changed neither card, this test would pass while measuring
    nothing at all."""
    from memz.models import Player

    session, host, p2, p3 = _finished_game()
    meme_before, _ = share_cards.meme_of_the_night(session)
    podium_before = share_cards.podium_card(session)

    for player, name in zip((host, p2, p3), ("זהותאחרת", "שםשונה", "מישהוחדש")):
        Player.objects.filter(pk=player.pk).update(nickname=name)

    meme_after, _ = share_cards.meme_of_the_night(session)
    podium_after = share_cards.podium_card(session)

    assert meme_after == meme_before, "the meme card changed when the authors were renamed"
    assert podium_after != podium_before, "control: the podium card should carry names"


def test_the_payload_points_at_the_card_without_naming_anyone():
    session, host, _p2, _p3 = _finished_game()
    from memz import state

    payload = state.build(session, host)
    assert payload["has_meme_card"] is True
    assert "meme_card_author" not in payload
    assert "meme_card_player_id" not in payload


# ------------------------------------------------------------- the endpoint


def test_the_card_endpoint_serves_a_jpeg_to_anyone(client):
    """Open on purpose, like the meme share page: a card exists to be
    forwarded to people who were never in the room and hold no token."""
    session, _host, _p2, _p3 = _finished_game()
    for kind in ("meme", "podium"):
        response = client.get(f"/memz/s/{session.code}/card/{kind}.jpg")
        assert response.status_code == 200, kind
        assert response["Content-Type"] == "image/jpeg"
        assert _open(response.content).format == "JPEG"


def test_the_card_endpoint_is_a_404_before_the_game_ends(client):
    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=20)
    game.join_session(session, "מיכל")
    game.join_session(session, "יונתן")
    game.start_session(session, host)
    assert client.get(f"/memz/s/{session.code}/card/podium.jpg").status_code == 404


def test_an_unknown_card_kind_is_a_404(client):
    session, _host, _p2, _p3 = _finished_game()
    assert client.get(f"/memz/s/{session.code}/card/scores.jpg").status_code == 404


def test_the_card_is_rendered_once_per_session_version():
    """Cached against `Session.version`, which already changes on every
    mutation — so a card can never go stale and nothing has to remember to
    invalidate it."""
    session, _host, _p2, _p3 = _finished_game()
    first = share_cards.card_bytes(session, "podium")

    calls = []
    real = share_cards.podium_card
    share_cards.podium_card = lambda s: (calls.append(1), real(s))[1]
    try:
        again = share_cards.card_bytes(session, "podium")
        assert calls == [], "a second request re-rendered the card"
        assert again == first

        Session.objects.filter(pk=session.pk).update(version=session.version + 1)
        session.refresh_from_db()
        share_cards.card_bytes(session, "podium")
        assert calls == [1], "a changed session served the old card"
    finally:
        share_cards.podium_card = real


# --------------------------------------------------------------- the screen


def test_the_podium_screen_offers_both_cards_and_one_whatsapp_tap_each():
    js = open("static/memz/game.js", encoding="utf-8").read()
    assert "shareCardsBlock" in js and "data-share-card" in js
    # The good path hands WhatsApp the actual file; the fallback is wa.me
    # with the card's own address, which is what works inside an installed
    # PWA (the ACT-Z.15 lesson).
    assert "navigator.canShare" in js and "files:" in js
    assert "https://wa.me/?text=" in js
    # And the meme card is only offered when there is one.
    assert "has_meme_card" in js


def test_the_big_screen_is_not_offered_share_buttons():
    """The TV has no player, no phone, and nobody standing at it to tap."""
    js = open("static/memz/game.js", encoding="utf-8").read()
    block = js[js.index("function shareCardsBlock"):js.index("async function shareCard")]
    assert "if (screenMode) return \"\";" in block
