"""SPR-Z.4 — memz: the other ways to play (docs/memz/backlog.md).
Topics, Same Meme, Relaxed, Judge scoring, Cards. Spec references are
docs/memz/spec.md rule numbers.
"""

import io
import json

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz4, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


def _png_bytes(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), color).save(buf, format="PNG")
    return buf.getvalue()


def _user(name):
    return User.objects.create_user(name, email=f"{name}@example.com", password="x")


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def bank(media_tmp):
    from memz.models import MemeImage

    images = []
    for i in range(8):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title=f"img{i}")
        img.file.save(f"img{i}.png", ContentFile(_png_bytes((i * 20, 80, 150))), save=True)
        images.append(img)
    return images


@pytest.fixture
def topics(media_tmp):
    from memz.models import Topic

    return [Topic.objects.create(text=f"נושא {i}", owner=None, is_public=True) for i in range(5)]


@pytest.fixture
def deck(media_tmp):
    from memz.models import CaptionCard, CaptionDeck

    deck = CaptionDeck.objects.create(name="חפיסת בדיקה", owner=None, is_public=True)
    # Rule 5.2.1: needs >= HAND_SIZE(7) * max_players(guest cap 5) + round_count
    # to be selectable at all; comfortably over that for any round_count a
    # test here uses.
    for i in range(60):
        CaptionCard.objects.create(deck=deck, text=f"כרטיס {i}", order=i)
    return deck


def post(client, url, body=None, token=None):
    headers = {"content_type": "application/json"}
    if token:
        headers["HTTP_X_MEMZ_PLAYER"] = token
    return client.post(url, json.dumps(body or {}), **headers)


def get(client, url, token=None):
    headers = {}
    if token:
        headers["HTTP_X_MEMZ_PLAYER"] = token
    return client.get(url, **headers)


def create_session(client, **kwargs):
    r = post(client, "/memz/api/sessions/", kwargs)
    assert r.status_code == 201, r.content
    return r.json()


def join(client, code, nickname="guest"):
    r = post(client, f"/memz/api/sessions/{code}/join/", {"nickname": nickname})
    assert r.status_code == 201, r.content
    return r.json()


def state(client, code, token=None):
    r = get(client, f"/memz/api/sessions/{code}/state/", token)
    assert r.status_code == 200, r.content
    return r.json()


def room(client, n=3, **kwargs):
    host = create_session(client, **kwargs)
    players = [host] + [join(client, host["code"], f"p{i}") for i in range(n - 1)]
    return host["code"], players


# ------------------------------------------------------------------ topics


def test_topics_mode_deals_a_topic_and_does_not_repeat_within_a_session(client, bank, topics):
    code, players = room(client, n=3, game_mode="topics", round_count=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    seen = []
    for round_number in range(1, 4):
        st = state(client, code, players[0]["token"])
        seen.append(st["round"]["topic"])
        assert st["round"]["topic"] is not None
        for p in players:
            post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/submit/", {"caption_text": "x"}, token=p["token"])
        post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
        for p in players:
            stp = state(client, code, p["token"])
            if stp["round"]["status"] != "voting":
                continue
            my_sub = next(m for m in stp["round"]["memes"] if m["is_mine"])
            target = next(m["submission_id"] for m in stp["round"]["memes"] if m["submission_id"] != my_sub["submission_id"])
            post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/vote/", {"submission_id": target}, token=p["token"])
        post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
    assert len(set(seen)) == len(seen)   # no topic repeated across the 3 rounds


# --------------------------------------------------------------- same meme


def test_same_meme_mode_deals_the_identical_image_to_everyone(client, bank):
    code, players = room(client, n=4, game_mode="same_meme")
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    urls = set()
    for p in players:
        st = state(client, code, p["token"])
        urls.add(st["round"]["my_submission"]["image_url"])
    assert len(urls) == 1   # unlike Normal mode, everyone got the same one


# ---------------------------------------------------------------- relaxed


def test_relaxed_mode_has_no_voting_and_no_scoring(client, bank):
    code, players = room(client, n=2, game_mode="relaxed")   # Relaxed's minimum is 2, not 3
    r = post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    assert r.status_code == 200, r.content
    for p in players:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": f"c{p['player_id']}"}, token=p["token"])
    st = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"]).json()
    # reveal -> the host's advance skips voting entirely for Relaxed
    assert st["round"]["status"] == "done"

    from memz.models import Player

    for p in players:
        assert Player.objects.get(pk=p["player_id"]).score == 0


def test_relaxed_mode_can_start_with_only_two_players(client, bank):
    code, players = room(client, n=2, game_mode="relaxed")
    r = post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    assert r.status_code == 200, r.content


# ------------------------------------------------------------------ judge


def test_judge_mode_only_the_judge_can_vote(client, bank):
    code, players = room(client, n=3, scoring_mode="judge")
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for p in players:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": f"c{p['player_id']}"}, token=p["token"])
    st = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"]).json()
    assert st["round"]["status"] == "voting"
    judge_id = st["round"]["judge"]["player_id"]
    non_judge = next(p for p in players if p["player_id"] != judge_id)
    a_submission = st["round"]["memes"][0]["submission_id"]

    r = post(client, f"/memz/api/sessions/{code}/rounds/1/vote/", {"submission_id": a_submission}, token=non_judge["token"])
    assert r.status_code == 409

    judge_token = next(p["token"] for p in players if p["player_id"] == judge_id)
    r2 = post(client, f"/memz/api/sessions/{code}/rounds/1/vote/", {"submission_id": a_submission}, token=judge_token)
    assert r2.status_code == 200, r2.content
    assert r2.json()["round"]["status"] == "done"


def test_judge_pick_is_worth_three_points_and_nothing_else_scores(client, bank):
    code, players = room(client, n=3, scoring_mode="judge")
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for p in players:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": f"c{p['player_id']}"}, token=p["token"])
    st = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"]).json()
    judge_id = st["round"]["judge"]["player_id"]
    judge_token = next(p["token"] for p in players if p["player_id"] == judge_id)
    winner_sub = next(m for m in st["round"]["memes"] if m["submission_id"] and st["round"]["judge"]["player_id"] != judge_id or True)
    picked = st["round"]["memes"][0]
    post(client, f"/memz/api/sessions/{code}/rounds/1/vote/", {"submission_id": picked["submission_id"]}, token=judge_token)

    from memz.models import Player, Submission

    winning_player_id = Submission.objects.get(pk=picked["submission_id"]).player_id
    total = sum(Player.objects.get(pk=p["player_id"]).score for p in players)
    assert Player.objects.get(pk=winning_player_id).score == 3
    assert total == 3   # nobody else scored anything


def test_judge_rotation_does_not_repeat_before_everyone_has_judged(client, bank):
    code, players = room(client, n=3, scoring_mode="judge", round_count=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    judges = []
    for round_number in range(1, 4):
        st = state(client, code, players[0]["token"])
        judges.append(st["round"]["judge"]["player_id"])
        for p in players:
            post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/submit/", {"caption_text": "x"}, token=p["token"])
        st2 = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"]).json()
        judge_token = next(p["token"] for p in players if p["player_id"] == st2["round"]["judge"]["player_id"])
        post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/vote/",
             {"submission_id": st2["round"]["memes"][0]["submission_id"]}, token=judge_token)
        post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
    assert sorted(judges) == sorted(p["player_id"] for p in players)   # each judged exactly once


def test_judge_timeout_means_nobody_scores(client, bank, settings):
    settings.MEMZ_VOTE_SECONDS = (1, 90, 1)
    code, players = room(client, n=3, scoring_mode="judge", vote_seconds=1)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for p in players:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "x"}, token=p["token"])
    post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])   # revealed -> voting (judge, x2 timer)

    import time as _t

    _t.sleep(2.5)   # past the doubled judge timer
    st = state(client, code, players[0]["token"])
    assert st["round"]["status"] == "done"

    from memz.models import Player

    for p in players:
        assert Player.objects.get(pk=p["player_id"]).score == 0


# ------------------------------------------------------------------- cards


def test_cards_mode_deals_a_hand_and_playing_a_card_uses_its_text(client, bank, deck):
    code, players = room(client, n=3, caption_mode="cards", deck=deck.pk)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = state(client, code, players[0]["token"])
    hand = st["round"]["my_hand"]
    assert len(hand) == 7   # HAND_SIZE default

    card = hand[0]
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"hand_card_id": card["hand_card_id"]}, token=players[0]["token"])
    assert r.status_code == 200, r.content

    from memz.models import Meme

    meme = Meme.objects.get(submission__round__session__code=code, submission__player_id=players[0]["player_id"])
    assert meme.caption_text == card["text"]
    assert meme.caption_card_id is not None


def test_cards_mode_refuses_a_deck_too_small_for_the_room(client, bank):
    from memz.models import CaptionCard, CaptionDeck

    tiny = CaptionDeck.objects.create(name="חפיסה קטנה", owner=None, is_public=True)
    CaptionCard.objects.create(deck=tiny, text="רק אחד", order=0)
    r = post(client, "/memz/api/sessions/", {"caption_mode": "cards", "deck": tiny.pk})
    assert r.status_code == 400


def test_a_played_card_leaves_the_hand_and_cannot_be_played_twice(client, bank, deck):
    code, players = room(client, n=3, caption_mode="cards", deck=deck.pk)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = state(client, code, players[0]["token"])
    card = st["round"]["my_hand"][0]
    post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"hand_card_id": card["hand_card_id"]}, token=players[0]["token"])
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"hand_card_id": card["hand_card_id"]}, token=players[0]["token"])
    assert r.status_code == 409


def test_card_swap_works_once_per_game(client, bank, deck):
    code, players = room(client, n=3, caption_mode="cards", deck=deck.pk)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = state(client, code, players[0]["token"])
    first_card_id = st["round"]["my_hand"][0]["hand_card_id"]

    r1 = post(client, f"/memz/api/sessions/{code}/cards/swap/", {"hand_card_id": first_card_id}, token=players[0]["token"])
    assert r1.status_code == 200, r1.content
    assert r1.json()["round"]["can_swap_card"] is False

    r2 = post(client, f"/memz/api/sessions/{code}/cards/swap/", {"hand_card_id": first_card_id}, token=players[0]["token"])
    assert r2.status_code == 409


def test_hand_tops_up_each_round(client, bank, deck):
    code, players = room(client, n=3, caption_mode="cards", deck=deck.pk, round_count=2)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for round_number in (1,):
        st = state(client, code, players[0]["token"])
        card = st["round"]["my_hand"][0]
        for p in players:
            stp = state(client, code, p["token"])
            post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/submit/",
                 {"hand_card_id": stp["round"]["my_hand"][0]["hand_card_id"]}, token=p["token"])
    # SPR-Z.10: no separate voting phase — the reveal running out is what
    # ends the round. Nothing here is about rating, so it just needs to get
    # past round 1 to check the hand tops back up.
    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])
    state(client, code, players[0]["token"])
    post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
    st3 = state(client, code, players[0]["token"])
    assert st3["round"]["number"] == 2
    assert len(st3["round"]["my_hand"]) == 7   # topped back up, one card short after playing one last round
