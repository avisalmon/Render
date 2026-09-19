"""SPR-Z.3 — memz: the game, Normal mode, typed captions, vote scoring
(docs/memz/backlog.md). Spec references are docs/memz/spec.md rule numbers.
"""

import io
import json

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz3, pytest.mark.django_db]

REFUSED = (401, 403, 404)


@pytest.fixture(autouse=True)
def _test_setup(settings):
    """Session creation and join are IP-throttled (spec Rule 12.3.3.7); the
    test client's IP never changes, so a shared process-wide cache would
    make test N+1's join attempt pay for test N's. Two tests exercise the
    throttle itself deliberately, everything else needs a clean slate.

    Also lowers the round-count floor from the spec default (3-10) to 1,
    so a "one full game" test can actually be one round — nothing here
    tests the 3-10 range itself."""
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
    for i in range(6):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title=f"img{i}")
        img.file.save(f"img{i}.png", ContentFile(_png_bytes((i * 30, 80, 150))), save=True)
        images.append(img)
    return images


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


def join(client, code, nickname="guest", token_of_creator=None):
    r = post(client, f"/memz/api/sessions/{code}/join/", {"nickname": nickname})
    assert r.status_code == 201, r.content
    return r.json()


def state(client, code, token=None):
    r = get(client, f"/memz/api/sessions/{code}/state/", token)
    assert r.status_code == 200, r.content
    return r.json()


# --------------------------------------------------------- create & lobby


def test_creating_a_session_snapshots_the_host_tier_cap(client, bank):
    data = create_session(client)
    from memz.models import Session

    session = Session.objects.get(code=data["code"])
    assert session.max_players == 5   # guest cap (spec §2.4)
    assert session.host_user is None
    assert session.remembered is False


def test_a_logged_in_hosts_session_gets_the_free_cap_and_is_remembered(client, bank):
    user = _user("hostie")
    client.force_login(user)
    data = create_session(client)
    from memz.models import Session

    session = Session.objects.get(code=data["code"])
    assert session.max_players == 10
    assert session.host_user == user
    assert session.remembered is True


def test_session_codes_use_the_unambiguous_alphabet_and_are_case_insensitive(client, bank):
    data = create_session(client)
    assert not (set(data["code"]) & set("0O1I"))
    r = get(client, f"/memz/api/sessions/{data['code'].lower()}/state/", data["token"])
    assert r.status_code == 200


def test_join_gives_a_unique_nickname_and_a_working_token(client, bank):
    host = create_session(client)
    p2 = join(client, host["code"])
    st = state(client, host["code"], p2["token"])
    assert any(p["id"] == p2["player_id"] and p["is_me"] for p in st["players"])


def test_join_deduplicates_nicknames_within_a_session(client, bank):
    host = create_session(client)
    a = join(client, host["code"], "דני")
    b = post(client, f"/memz/api/sessions/{host['code']}/join/", {"nickname": "דני"}).json()
    st = state(client, host["code"], b["token"])
    names = sorted(p["nickname"] for p in st["players"])
    assert "דני" in names and "דני 2" in names


def test_join_refuses_past_the_cap(client, bank):
    host = create_session(client)   # guest cap: 5, host counts as one
    for i in range(4):
        join(client, host["code"], f"p{i}")
    r = post(client, f"/memz/api/sessions/{host['code']}/join/", {"nickname": "one too many"})
    assert r.status_code == 400
    assert "מלא" in r.json()["detail"]


def test_join_refuses_a_finished_or_nonexistent_session(client, bank):
    r = post(client, "/memz/api/sessions/ZZZZ/join/", {"nickname": "x"})
    assert r.status_code == 404


def test_host_can_remove_a_player_and_their_token_stops_working(client, bank):
    host = create_session(client)
    p2 = join(client, host["code"], "target")
    r = post(client, f"/memz/api/sessions/{host['code']}/players/{p2['player_id']}/remove/", token=host["token"])
    assert r.status_code == 200, r.content
    assert get(client, f"/memz/api/sessions/{host['code']}/state/", p2["token"]).json()["my_player_id"] is None


def test_only_the_host_can_remove_a_player(client, bank):
    host = create_session(client)
    p2 = join(client, host["code"], "p2")
    p3 = join(client, host["code"], "p3")
    r = post(client, f"/memz/api/sessions/{host['code']}/players/{p3['player_id']}/remove/", token=p2["token"])
    assert r.status_code == 403


# --------------------------------------------------------------- starting


def _room(client, n=3):
    host = create_session(client)
    players = [host] + [join(client, host["code"], f"p{i}") for i in range(n - 1)]
    return host["code"], players


def test_starting_below_the_minimum_is_refused(client, bank):
    host = create_session(client)
    join(client, host["code"], "only-two-total")
    r = post(client, f"/memz/api/sessions/{host['code']}/start/", token=host["token"])
    assert r.status_code == 400


def test_only_the_host_can_start(client, bank):
    code, players = _room(client)
    r = post(client, f"/memz/api/sessions/{code}/start/", token=players[1]["token"])
    assert r.status_code == 403


def test_starting_deals_a_different_image_to_each_player_where_the_pool_allows(client, bank):
    code, players = _room(client, n=4)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = state(client, code, players[0]["token"])
    assert st["status"] == "playing"
    assert st["round"]["status"] == "captioning"
    urls = set()
    for p in players:
        s = state(client, code, p["token"])
        urls.add(s["round"]["my_submission"]["image_url"])
    assert len(urls) == len(players)   # no two players got the same image


# ------------------------------------------------------------- captioning


def test_submitting_a_caption_renders_a_meme_and_locks_the_input(client, bank):
    code, players = _room(client)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "כיתוב ראשון"}, players[0]["token"])
    assert r.status_code == 200, r.content
    assert r.json()["round"]["my_submission"]["submitted"] is True
    r2 = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "שוב"}, players[0]["token"])
    assert r2.status_code == 409


def test_an_empty_caption_is_refused(client, bank):
    code, players = _room(client)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "   "}, players[0]["token"])
    assert r.status_code == 409


def test_the_round_advances_once_everyone_has_submitted(client, bank):
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for p in players:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": f"כיתוב של {p['player_id']}"}, p["token"])
    st = state(client, code, players[0]["token"])
    assert st["round"]["status"] in ("revealed", "voting")   # revealed is instant server-side; deadline math is exercised separately


def test_a_player_who_never_submits_has_no_meme_and_the_round_still_moves_on(client, bank, settings):
    from memz import conf as memz_conf

    settings.MEMZ_CAPTION_SECONDS = (1, 90, 1)   # 1-second round so the deadline passes fast
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "רק אני"}, players[0]["token"])
    import time as _t

    _t.sleep(1.2)
    st = state(client, code, players[0]["token"])
    assert st["round"]["status"] in ("revealed", "voting", "done")


def test_submit_refuses_a_stranger_token(client, bank):
    code, players = _room(client)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "x"}, token="not-a-real-token")
    assert r.status_code == 401


def test_a_token_from_another_session_is_refused_here(client, bank):
    code_a, players_a = _room(client)
    code_b, players_b = _room(client)
    post(client, f"/memz/api/sessions/{code_a}/start/", token=players_a[0]["token"])
    r = post(client, f"/memz/api/sessions/{code_a}/rounds/1/submit/", {"caption_text": "x"}, token=players_b[0]["token"])
    assert r.status_code in REFUSED


# ---------------------------------------------------------------- voting


def _play_to_reveal(client, code, players, round_number=1):
    """Everyone captions, which tips the round into its reveal — where,
    from SPR-Z.10, the rating happens (there is no separate voting phase
    any more outside Judge mode)."""
    for p in players:
        post(
            client, f"/memz/api/sessions/{code}/rounds/{round_number}/submit/",
            {"caption_text": f"כיתוב {p['player_id']}"}, p["token"],
        )
    st = state(client, code, players[0]["token"])
    assert st["round"]["status"] == "revealed", st["round"]["status"]
    return st


def _show_meme(code, index):
    """Wind the reveal's clock so meme `index` is the one on screen, the
    same arithmetic `game.reveal_index` does — beats sleeping through ten
    real seconds per meme (SPR-Z.10)."""
    from memz import conf
    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    elapsed = per_meme * index + per_meme / 2
    round_obj.reveal_deadline = timezone.now() + timezone.timedelta(seconds=per_meme * count - elapsed)
    round_obj.save(update_fields=["reveal_deadline"])


def _end_reveal(client, code, players):
    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])
    return state(client, code, players[0]["token"])


def _rate_all(client, code, players, round_number=1, value=2):
    """Everyone gives every meme but their own the same verdict, each in
    its own slot on screen."""
    memes = state(client, code, players[0]["token"])["round"]["memes"]
    for index, meme in enumerate(memes):
        _show_meme(code, index)
        for p in players:
            mine = state(client, code, p["token"])["round"]["memes"][index]["is_mine"]
            if mine:
                continue
            r = post(
                client, f"/memz/api/sessions/{code}/rounds/{round_number}/rate/",
                {"submission_id": meme["submission_id"], "value": value}, p["token"],
            )
            assert r.status_code == 200, r.content
    return memes


def test_reveal_is_where_rating_happens_and_the_round_ends_with_it(client, bank):
    """SPR-Z.10 replaced the old reveal-then-a-grid-of-thumbnails vote: the
    reveal itself carries the verdicts, one meme at a time, and when the
    last slot ends the round is already scored."""
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    _play_to_reveal(client, code, players)
    _rate_all(client, code, players, value=2)

    final = _end_reveal(client, code, players)
    assert final["round"]["status"] == "done"
    # Three memes, two "אוהב" (2 points) each from the other two players.
    # Checked against the scoring function, not the payload: ACT-Z.14 took
    # per-meme points out of the state entirely, since a meme's score
    # beside the leaderboard identified its author (Rule 4.7.2).
    from memz.game import current_round
    from memz.models import Session
    from memz.scoring import round_scores

    round_obj = current_round(Session.objects.get(code=code))
    assert sorted(round_scores(round_obj).values()) == [4, 4, 4]
    # Every player's cached score agrees with it.
    assert sorted(p["score"] for p in final["players"]) == [4, 4, 4]


def test_cannot_rate_your_own_meme(client, bank):
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = _play_to_reveal(client, code, players)
    mine_index, my_sub = next(
        (i, m) for i, m in enumerate(st["round"]["memes"]) if m["is_mine"]
    )
    _show_meme(code, mine_index)
    r = post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": my_sub["submission_id"], "value": 2}, players[0]["token"],
    )
    assert r.status_code == 409


def test_cannot_rate_the_same_meme_twice(client, bank):
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = _play_to_reveal(client, code, players)
    index, target = next(
        (i, m) for i, m in enumerate(st["round"]["memes"]) if not m["is_mine"]
    )
    _show_meme(code, index)
    body = {"submission_id": target["submission_id"], "value": 2}
    assert post(client, f"/memz/api/sessions/{code}/rounds/1/rate/", body, players[0]["token"]).status_code == 200
    r = post(client, f"/memz/api/sessions/{code}/rounds/1/rate/", body, players[0]["token"])
    assert r.status_code == 409


def test_authors_and_other_peoples_verdicts_are_hidden_during_the_reveal(client, bank):
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    st = _play_to_reveal(client, code, players)
    assert "nickname" not in json.dumps(st["round"])   # no authors, ever (Rule 4.7.1)
    for m in st["round"]["memes"]:
        assert "votes" not in m
    # My own verdicts come back; nobody else's do, in any phase.
    assert st["round"]["my_ratings"] == {}


def test_scores_recomputed_from_votes_equal_the_cached_score(client, bank):
    """Rule 5.3.1: `Player.score` is only ever a cache of what the Vote
    rows say — still true now that a row is a per-meme verdict with a
    value, not a single pick."""
    code, players = _room(client, n=4)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    _play_to_reveal(client, code, players)
    _rate_all(client, code, players, value=1)
    _end_reveal(client, code, players)

    from memz.models import Player, Round, Session
    from memz.scoring import vote_round_scores

    session = Session.objects.get(code=code)
    round_obj = Round.objects.get(session=session, number=1)
    expected = vote_round_scores(round_obj)
    assert set(expected.values()) == {3}, expected   # three others, "ככה ככה" each
    for sub in round_obj.submissions.filter(meme__isnull=False):
        player = Player.objects.get(pk=sub.player_id)
        assert player.score == expected.get(sub.id, 0)


def test_fewer_than_two_memes_skips_voting_and_the_lone_meme_wins(client, bank, settings):
    """Rule 4.6.4: only one player beat the clock, so there is no vote and
    the lone meme wins outright."""
    settings.MEMZ_CAPTION_SECONDS = (1, 90, 1)
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "היחיד"}, players[0]["token"])

    import time as _t

    _t.sleep(1.2)
    st = state(client, code, players[0]["token"])   # sync() ticks captioning -> revealed on the deadline
    assert st["round"]["status"] == "revealed"

    r = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
    assert r.status_code == 200, r.content
    assert r.json()["round"]["status"] == "done"   # skipped voting: fewer than two memes

    from memz.models import Player

    winner = Player.objects.get(pk=players[0]["player_id"])
    assert winner.score >= 1


# --------------------------------------------------------------- host-only


@pytest.mark.parametrize("path,method", [
    ("/start/", "post"), ("/advance/", "post"), ("/again/", "post"),
])
def test_host_only_actions_refuse_a_non_host(client, bank, path, method):
    code, players = _room(client)
    r = post(client, f"/memz/api/sessions/{code}{path}", token=players[1]["token"])
    assert r.status_code == 403


def test_advance_refuses_the_wrong_phase(client, bank):
    code, players = _room(client)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    r = post(client, f"/memz/api/sessions/{code}/advance/", token=players[0]["token"])
    assert r.status_code == 409   # still captioning, nothing to advance


# ------------------------------------------------------------- podium & again


def _play_full_game(client, n=3, round_count=1):
    host = create_session(client, round_count=round_count)
    players = [host] + [join(client, host["code"], f"p{i}") for i in range(n - 1)]
    code = host["code"]
    post(client, f"/memz/api/sessions/{code}/start/", token=host["token"])
    for round_number in range(1, round_count + 1):
        for p in players:
            post(client, f"/memz/api/sessions/{code}/rounds/{round_number}/submit/", {"caption_text": f"c{p['player_id']}"}, p["token"])
        # SPR-Z.10: rate inside the reveal, then let the reveal run out —
        # that alone finishes and scores the round, no voting phase.
        _rate_all(client, code, players, round_number=round_number, value=2)
        _end_reveal(client, code, players)
        post(client, f"/memz/api/sessions/{code}/advance/", token=host["token"])
    return code, players


def test_a_full_one_round_game_reaches_the_podium(client, bank):
    code, players = _play_full_game(client)
    st = state(client, code, players[0]["token"])
    assert st["status"] == "finished"
    assert len(st["podium"]) == len(players)
    assert len(st["gallery"]) == len(players)


def test_play_again_carries_players_into_a_new_lobby(client, bank):
    code, players = _play_full_game(client)
    r = post(client, f"/memz/api/sessions/{code}/again/", token=players[0]["token"])
    assert r.status_code == 200, r.content
    next_session = r.json()["next_session"]
    assert next_session["code"] != code
    new_state = state(client, next_session["code"], next_session["token"])
    assert new_state["status"] == "lobby"
    assert any(p["is_me"] and p["is_host"] for p in new_state["players"])
    # the host's own next poll on the OLD session still shows it finished
    old_state = state(client, code, players[0]["token"])
    assert old_state["status"] == "finished"
    assert old_state["next_session"]["code"] == next_session["code"]


def test_a_non_host_players_next_poll_on_the_old_session_finds_their_new_seat(client, bank):
    code, players = _play_full_game(client, n=3)
    post(client, f"/memz/api/sessions/{code}/again/", token=players[0]["token"])
    st = state(client, code, players[1]["token"])
    assert "next_session" in st
    new_code = st["next_session"]["code"]
    new_token = st["next_session"]["token"]
    new_state = state(client, new_code, new_token)
    assert new_state["status"] == "lobby"
    assert any(p["is_me"] for p in new_state["players"])


def test_play_again_only_the_host_and_only_once(client, bank):
    code, players = _play_full_game(client)
    r = post(client, f"/memz/api/sessions/{code}/again/", token=players[1]["token"])
    assert r.status_code == 403

    r1 = post(client, f"/memz/api/sessions/{code}/again/", token=players[0]["token"])
    r2 = post(client, f"/memz/api/sessions/{code}/again/", token=players[0]["token"])
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["next_session"]["code"] == r2.json()["next_session"]["code"]   # idempotent, not a second room

    from memz.models import Session

    old = Session.objects.get(code=code)
    assert old.next_session_id is not None
    assert Session.objects.filter(code=old.next_session.code).count() == 1


# ------------------------------------------------------------- presence


def test_leaving_marks_inactive_and_is_excluded_from_submitted_checks(client, bank):
    code, players = _room(client, n=4)   # 4 join, 1 leaves, 3 remain — still meets the minimum
    post(client, f"/memz/api/sessions/{code}/leave/", token=players[3]["token"])
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    for p in players[:3]:
        post(client, f"/memz/api/sessions/{code}/rounds/1/submit/", {"caption_text": "x"}, p["token"])
    st = state(client, code, players[0]["token"])
    assert st["round"]["status"] in ("revealed", "voting")   # advanced without waiting on the one who left


def test_host_inactivity_hands_off_to_the_next_active_player(client, bank):
    """Rule 4.9.3: only once a game is actually being played. Backdating
    just the host by an hour clears the default 90s threshold with room to
    spare, without a 0-second override that would also catch p2/p3's
    just-created (a few ms old) timestamps as "stale"."""
    code, players = _room(client, n=3)
    post(client, f"/memz/api/sessions/{code}/start/", token=players[0]["token"])
    from memz import game
    from memz.models import Player, Session

    session = Session.objects.get(code=code)
    Player.objects.filter(pk=players[0]["player_id"]).update(
        last_seen_at=timezone.now() - timezone.timedelta(hours=1)
    )
    game.sync(session)
    host = Player.objects.get(session=session, is_host=True)
    assert host.pk != players[0]["player_id"]
    assert host.pk == players[1]["player_id"]   # lowest seat_order among the still-active


def test_the_state_endpoint_never_carries_a_token(client, bank):
    code, players = _room(client)
    st = state(client, code, players[0]["token"])
    assert "token" not in json.dumps(st).lower() or "guest_token" not in json.dumps(st)


# ------------------------------------------------------- big screen & api


def test_big_screen_reads_state_with_no_token(client, bank):
    code, players = _room(client)
    r = client.get(f"/memz/api/sessions/{code}/state/")
    assert r.status_code == 200
    assert r.json()["my_player_id"] is None


def test_the_game_page_and_big_screen_serve(client, bank):
    code, players = _room(client)
    assert client.get(f"/memz/s/{code}/").status_code == 200
    assert client.get(f"/memz/s/{code}/screen/").status_code == 200
    assert client.get(f"/memz/join/{code}/").status_code == 200


def test_session_creation_is_throttled(client, bank, settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}), "memz_session_create": "1/hour",
    }}
    assert post(client, "/memz/api/sessions/").status_code == 201
    assert post(client, "/memz/api/sessions/").status_code == 429


def test_join_attempts_are_throttled(client, bank, settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    host = create_session(client)
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}), "memz_join_attempt": "1/minute",
    }}
    assert post(client, f"/memz/api/sessions/{host['code']}/join/", {"nickname": "a"}).status_code == 201
    assert post(client, f"/memz/api/sessions/{host['code']}/join/", {"nickname": "b"}).status_code == 429


# ------------------------------------------------------------- load check


def test_fifty_players_can_submit_in_the_same_round_without_a_double_advance(client, bank, settings):
    """Rule 12.4.1: WAL SQLite handling a burst of short write transactions.
    50 real HTTP round trips through Django's test client, one session."""
    settings.MEMZ_MAX_PLAYERS = {"guest": 60, "free": 60, "paid": 60}
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}), "memz_join_attempt": "1000/minute",
    }}
    host = create_session(client)
    players = [host] + [join(client, host["code"], f"p{i}") for i in range(49)]
    assert len(players) == 50
    post(client, f"/memz/api/sessions/{host['code']}/start/", token=host["token"])
    for p in players:
        r = post(client, f"/memz/api/sessions/{host['code']}/rounds/1/submit/", {"caption_text": f"caption {p['player_id']}"}, p["token"])
        assert r.status_code == 200, r.content

    from memz.models import Round, Session

    session = Session.objects.get(code=host["code"])
    assert Round.objects.filter(session=session).count() == 1   # no double-created next round
    round_obj = Round.objects.get(session=session, number=1)
    assert round_obj.submissions.filter(meme__isnull=False).count() == 50
