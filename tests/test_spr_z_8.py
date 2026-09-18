"""SPR-Z.8 — memz: AI players (docs/memz/spec.md §4.11, docs/memz/backlog.md).

Every test here plays through `memz.game` itself, same discipline as
every earlier sprint. `settings.OPENAI_API_KEY` is blanked globally by
the repo's own conftest.py for every test file except `test_spr_m_*.py`
(matazim's own live_ai fixture), so `app.ai_chat.call_openai` is always
in stub mode here — which is exactly the path `memz.ai_players` is
built to fall back from cleanly, not a gap in coverage. What's under
test is that fallback, not the live model.
"""

import io

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import ai_players, cards as cards_module, game
from memz.models import MemeImage, Player, Round, Session

pytestmark = [pytest.mark.sprz8, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    assert not settings.OPENAI_API_KEY, "this file must never hold a live key (see module docstring)"
    yield


def _png_bytes(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (300, 220), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture(autouse=True)
def _seed_images(db, _media_tmp):
    for i in range(6):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"z8-source-{i}.png", ContentFile(_png_bytes((20 * i, 80, 140))), save=True)


_user_counter = [0]


def _signed_in_host():
    """AI players are signed-in-hosts-only (spec Rule 4.11.1, 2026-09-16) —
    every test below that actually wants bots needs a real account, not
    the guest `host_user=None` earlier sprints could use freely."""
    from django.contrib.auth.models import User

    _user_counter[0] += 1
    return User.objects.create_user(
        f"z8host{_user_counter[0]}", email=f"z8host{_user_counter[0]}@example.com", password="x",
    )


def _play_round(session, host, human_players, votes):
    """One full round to `done`. `human_players` submit typed captions;
    AI players (if any) are resolved automatically by game.sync() itself,
    called from inside submit_caption/cast_vote — no separate step here,
    which is the point being tested."""
    round_obj = game.current_round(session)
    for player in human_players:
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    if round_obj.status == Round.CAPTIONING:
        Round.objects.filter(pk=round_obj.pk).update(caption_deadline=timezone.now() - timezone.timedelta(seconds=1))
        game.sync(session)
    round_obj.refresh_from_db()
    if round_obj.status == Round.REVEALED:
        game.advance(session, host)
    round_obj.refresh_from_db()
    if round_obj.status == Round.VOTING:
        for voter, target in votes:
            sub = round_obj.submissions.get(player=target, meme__isnull=False)
            game.cast_vote(session, voter, round_obj.number, sub.id)
        round_obj.refresh_from_db()
        if round_obj.status == Round.VOTING:
            Round.objects.filter(pk=round_obj.pk).update(vote_deadline=timezone.now() - timezone.timedelta(seconds=1))
            game.sync(session)
    round_obj.refresh_from_db()
    assert round_obj.status == Round.DONE
    game.advance(session, host)
    return round_obj


# --------------------------------------------------------------- creation


def test_a_guest_host_is_silently_forced_back_to_zero_ai_players():
    """2026-09-16 (Avi): "only a signed up user can open a game with AI
    participants." Server-side, same as image_source's own guest downgrade
    (spec Rule 4.11.1) — never trust the client's own claim about who is
    asking."""
    session, _host = game.create_session(
        host_user=None, round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=3,
    )
    assert Player.objects.filter(session=session, is_ai=True).count() == 0


def test_create_session_adds_the_requested_number_of_ai_players():
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=2,
    )
    ai = Player.objects.filter(session=session, is_ai=True)
    assert ai.count() == 2
    assert set(ai.values_list("nickname", flat=True)) <= set(ai_players.NICKNAMES)
    assert not any(p.is_host for p in ai)


def test_ai_player_count_is_capped_at_the_configured_maximum(settings):
    settings.MEMZ_AI_PLAYERS_MAX = 3
    session, _host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=99,
    )
    assert Player.objects.filter(session=session, is_ai=True).count() == 3


def test_ai_player_count_never_exceeds_max_players_minus_the_host(settings):
    # A free-tier host's cap is small (spec §2.4); this must still leave
    # the host a seat rather than filling the room entirely with bots.
    from memz import conf

    free_cap = conf.cap("MAX_PLAYERS", "free")
    session, _host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=free_cap,
    )
    assert Player.objects.filter(session=session, is_ai=True).count() < session.max_players
    assert Player.objects.filter(session=session).count() <= session.max_players


def test_ai_players_count_toward_the_minimum_to_start_solo():
    """The stated use case: a host testing alone, filled out by bots."""
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20, ai_player_count=2,
    )
    game.start_session(session, host)   # host + 2 AI = 3, meets vote mode's minimum
    session.refresh_from_db()
    assert session.status == Session.PLAYING


def test_ai_players_are_never_the_host_even_created_first():
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=3,
    )
    assert host.is_host
    assert not Player.objects.filter(session=session, is_ai=True, is_host=True).exists()


# --------------------------------------------------------- playing a round


def test_an_ai_player_submits_a_caption_on_its_own():
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20, ai_player_count=2,
    )
    p2 = game.join_session(session, "בן אדם")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    # Only the two humans submit; sync() (called at the tail of each
    # submit_caption) must have already resolved the AI players' turns.
    game.submit_caption(session, host, round_obj.number, caption_text="כיתוב מארח")
    game.submit_caption(session, p2, round_obj.number, caption_text="כיתוב שני")
    round_obj.refresh_from_db()
    ai_submissions = round_obj.submissions.filter(player__is_ai=True)
    assert ai_submissions.count() == 2
    assert all(s.meme_id is not None for s in ai_submissions)
    assert all(s.meme.caption_text in ai_players.FALLBACK_CAPTIONS for s in ai_submissions)
    # everyone (2 humans + 2 AI) had submitted, so the round should already
    # have moved itself on to revealed without waiting for any deadline.
    assert round_obj.status == Round.REVEALED


def test_an_ai_player_rates_on_its_own_and_never_its_own_meme():
    """SPR-Z.10: a bot rates each meme as it comes up in the reveal, the
    same slot a human in the room can rate it in — never running ahead of
    the screen, and never its own."""
    from memz import conf
    from memz.models import Vote

    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20, ai_player_count=1,
    )
    p2 = game.join_session(session, "שחקן")
    p3 = game.join_session(session, "שחקנית")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    ai_player = Player.objects.get(session=session, is_ai=True)

    order = game.reveal_order(round_obj)
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    for index, submission in enumerate(order):
        # Wind the reveal to this meme's slot, then let sync() run: that is
        # the bot's own cue, exactly as it is on a real poll.
        Round.objects.filter(pk=round_obj.pk).update(
            reveal_deadline=timezone.now() + timezone.timedelta(
                seconds=per_meme * len(order) - (per_meme * index + per_meme / 2)
            )
        )
        game.sync(session)
        cast = Vote.objects.filter(round=round_obj, voter=ai_player, submission=submission)
        if submission.player_id == ai_player.id:
            assert not cast.exists(), "the bot rated its own meme"
        else:
            assert cast.count() == 1, "the bot didn't rate the meme that was on screen"
            assert cast.first().value in {Vote.LOVE, Vote.SOSO, Vote.MEH}

    # It never ran ahead of the slideshow: one row per meme it could rate,
    # and no more.
    assert Vote.objects.filter(round=round_obj, voter=ai_player).count() == len(
        [s for s in order if s.player_id != ai_player.id]
    )


def test_an_ai_player_plays_a_card_in_cards_mode():
    from memz.models import CaptionCard, CaptionDeck

    deck = CaptionDeck.objects.create(name="חפיסת בדיקה", owner=None, is_public=True)
    # A signed-in host's own tier cap (free: 10) is bigger than a guest's,
    # so the deck-size-at-create check (7 x max_players + rounds) needs
    # more cards than the guest-host version of this test did.
    CaptionCard.objects.bulk_create([CaptionCard(deck=deck, text=f"קלף {i}", order=i) for i in range(90)])
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20, ai_player_count=2,
        caption_mode=Session.CARDS, deck=deck,
    )
    p2 = game.join_session(session, "אדם")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for ai in Player.objects.filter(session=session, is_ai=True):
        assert cards_module.hand_for(ai)   # dealt a hand same as any player
    game.submit_caption(session, host, round_obj.number, hand_card_id=cards_module.hand_for(host)[0].id)
    game.submit_caption(session, p2, round_obj.number, hand_card_id=cards_module.hand_for(p2)[0].id)
    round_obj.refresh_from_db()
    ai_subs = round_obj.submissions.filter(player__is_ai=True, meme__isnull=False)
    assert ai_subs.count() == 2
    for s in ai_subs:
        assert s.meme.caption_card_id is not None   # played a real card, not typed text


def test_an_ai_judge_casts_the_deciding_vote():
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20,
        ai_player_count=1, scoring_mode=Session.JUDGE,
    )
    p2 = game.join_session(session, "שחקן")
    p3 = game.join_session(session, "שחקנית")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    ai_player = Player.objects.get(session=session, is_ai=True)
    # Only the humans submit explicitly — the AI player's turn is resolved
    # automatically by sync() during one of these calls, same as the
    # earlier captioning test proves; submitting for it here too would be
    # submitting twice.
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    game.advance(session, host)   # revealed -> voting
    round_obj.refresh_from_db()
    if round_obj.judge_id != ai_player.id:
        pytest.skip("rotation didn't land on the AI player this round; covered by the fairness tests elsewhere")
    from memz.models import Vote

    assert Vote.objects.filter(round=round_obj, voter=ai_player).exists()
    assert round_obj.status == Round.DONE


# ------------------------------------------------------------- presence


def test_ai_players_are_never_marked_inactive_by_staleness(settings):
    settings.MEMZ_INACTIVE_AFTER_SECONDS = 0   # would mark everyone stale except for the is_ai guard
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=1, round_seconds=60, vote_seconds=20, ai_player_count=1,
    )
    ai_player = Player.objects.get(session=session, is_ai=True)
    game.sync(session)
    ai_player.refresh_from_db()
    assert ai_player.is_active


def test_host_handoff_never_lands_on_an_ai_player():
    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=1,
    )
    p2 = game.join_session(session, "בן אדם")
    game.start_session(session, host)
    Player.objects.filter(pk=host.pk).update(is_active=False)   # host "disconnects"
    game.sync(session)
    p2.refresh_from_db()
    host.refresh_from_db()
    assert p2.is_host
    assert not host.is_host
    assert not Player.objects.filter(session=session, is_ai=True, is_host=True).exists()


def test_ai_presence_always_reads_as_active_in_state():
    from memz.state import build

    session, host = game.create_session(
        host_user=_signed_in_host(), round_count=3, round_seconds=60, vote_seconds=20, ai_player_count=1,
    )
    payload = build(session, host)
    ai_row = next(p for p in payload["players"] if p["is_ai"])
    assert ai_row["presence"] == "active"
