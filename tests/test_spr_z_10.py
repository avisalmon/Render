"""SPR-Z.10 — memz: the round Avi asked for (docs/memz/backlog.md).

Three images can be thrown back, the reveal *is* the vote (each meme gets
its own slot on screen and three verdict buttons), and no screen ever says
who made which meme again. Spec references are docs/memz/spec.md rule
numbers.
"""

import io
import json

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz10, pytest.mark.django_db]


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


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def bank(media_tmp):
    from memz.models import MemeImage

    images = []
    for i in range(8):
        img = MemeImage(
            owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title=f"img{i}"
        )
        img.file.save(f"img{i}.png", ContentFile(_png_bytes((i * 25, 80, 150))), save=True)
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


def _room(client, **kwargs):
    """A started three-player game, mid-captioning. Returns (code, tokens)."""
    r = post(client, "/memz/api/sessions/", kwargs)
    assert r.status_code == 201, r.content
    host = r.json()
    code = host["code"]
    tokens = [host["token"]]
    for name in ("שחקן ב", "שחקן ג"):
        j = post(client, f"/memz/api/sessions/{code}/join/", {"nickname": name})
        assert j.status_code == 201, j.content
        tokens.append(j.json()["token"])
    s = post(client, f"/memz/api/sessions/{code}/start/", token=tokens[0])
    assert s.status_code == 200, s.content
    return code, tokens


def _state(client, code, token=None):
    r = get(client, f"/memz/api/sessions/{code}/state/", token)
    assert r.status_code == 200, r.content
    return r.json()


def _all_submit(client, code, tokens, number=1):
    for i, token in enumerate(tokens):
        r = post(
            client, f"/memz/api/sessions/{code}/rounds/{number}/submit/",
            {"caption_text": f"כיתוב מספר {i}"}, token=token,
        )
        assert r.status_code == 200, r.content


def _show_meme(code, index):
    """Move the reveal's clock so meme `index` is the one on screen right
    now — the same arithmetic `game.reveal_index` does, run backwards.
    Beats sleeping through ten real seconds a meme."""
    from memz import conf
    from memz.game import current_round
    from memz.models import Session

    session = Session.objects.get(code=code)
    round_obj = current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    # Put "now" in the middle of slot `index`.
    elapsed = per_meme * index + per_meme / 2
    round_obj.reveal_deadline = timezone.now() + timezone.timedelta(seconds=per_meme * count - elapsed)
    round_obj.save(update_fields=["reveal_deadline"])
    return round_obj


# ------------------------------------------------- Rule 4.4.5, image swaps


def test_a_player_can_throw_back_the_dealt_image_three_times_then_no_more(client, bank):
    code, tokens = _room(client)
    seen = [_state(client, code, tokens[0])["round"]["my_submission"]["image_url"]]

    for expected_left in (2, 1, 0):
        r = post(client, f"/memz/api/sessions/{code}/rounds/1/swap-image/", token=tokens[0])
        assert r.status_code == 200, r.content
        round_data = r.json()["round"]
        assert round_data["image_swaps_left"] == expected_left
        seen.append(round_data["my_submission"]["image_url"])

    # Every swap actually changed the picture, never handed back the same one.
    assert len(set(seen)) == len(seen), f"a swap returned an image already held: {seen}"

    refused = post(client, f"/memz/api/sessions/{code}/rounds/1/swap-image/", token=tokens[0])
    assert refused.status_code == 409
    assert "3" in refused.json()["detail"]


def test_swapping_never_takes_an_image_another_player_is_holding_this_round(client, bank):
    code, tokens = _room(client)
    others = {
        _state(client, code, t)["round"]["my_submission"]["image_url"] for t in tokens[1:]
    }
    for _ in range(3):
        r = post(client, f"/memz/api/sessions/{code}/rounds/1/swap-image/", token=tokens[0])
        assert r.status_code == 200, r.content
        mine = r.json()["round"]["my_submission"]["image_url"]
        assert mine not in others, "a swap dealt an image somebody else is already captioning"


def test_the_image_cannot_be_swapped_once_the_caption_is_in(client, bank):
    code, tokens = _room(client)
    r = post(
        client, "/memz/api/sessions/%s/rounds/1/submit/" % code,
        {"caption_text": "שלחתי כבר"}, token=tokens[0],
    )
    assert r.status_code == 200, r.content
    refused = post(client, f"/memz/api/sessions/{code}/rounds/1/swap-image/", token=tokens[0])
    assert refused.status_code == 409


def test_same_meme_mode_refuses_image_swaps_outright(client, bank):
    code, tokens = _room(client, game_mode="same_meme")
    refused = post(client, f"/memz/api/sessions/{code}/rounds/1/swap-image/", token=tokens[0])
    assert refused.status_code == 409
    # And the button is never offered there either.
    assert "image_swaps_left" not in _state(client, code, tokens[0])["round"]


# --------------------------------------------- Rule 4.6.1, rating a reveal


def test_everyone_rates_every_meme_but_their_own_and_the_round_scores_the_sum(client, bank):
    from memz.models import Vote

    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    state = _state(client, code, tokens[0])
    assert state["round"]["status"] == "revealed"
    memes = state["round"]["memes"]
    assert len(memes) == 3

    # Everyone rates every meme that isn't theirs, each as it comes up.
    values = {0: Vote.LOVE, 1: Vote.SOSO, 2: Vote.MEH}
    for index, meme in enumerate(memes):
        _show_meme(code, index)
        for token in tokens:
            mine = _state(client, code, token)["round"]["memes"][index]["is_mine"]
            r = post(
                client, f"/memz/api/sessions/{code}/rounds/1/rate/",
                {"submission_id": meme["submission_id"], "value": values[index]}, token=token,
            )
            if mine:
                assert r.status_code == 409, "the author was allowed to rate their own meme"
                assert "תמים" in r.json()["detail"]
            else:
                assert r.status_code == 200, r.content

    # Two other players rated each meme, so: love 2+2=4, so-so 1+1=2, meh 0.
    from memz.game import current_round
    from memz.models import Session
    from memz.scoring import round_scores

    round_obj = current_round(Session.objects.get(code=code))
    points = round_scores(round_obj)
    assert sorted(points.values()) == [0, 2, 4]


def test_a_meme_can_only_be_rated_while_it_is_the_one_on_screen(client, bank):
    """Rule 4.5.4: without this, one client could rate the whole round the
    second the reveal opened, before anybody had read a single joke."""
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)

    later = next(m for m in memes[1:] if not m["is_mine"])
    refused = post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": later["submission_id"], "value": 2}, token=tokens[0],
    )
    assert refused.status_code == 409
    assert "על המסך" in refused.json()["detail"]


def test_a_verdict_is_final_and_only_ever_counts_once(client, bank):
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)
    voter = next(t for t in tokens if not _state(client, code, t)["round"]["memes"][0]["is_mine"])
    body = {"submission_id": memes[0]["submission_id"], "value": 2}

    first = post(client, f"/memz/api/sessions/{code}/rounds/1/rate/", body, token=voter)
    assert first.status_code == 200, first.content
    again = post(client, f"/memz/api/sessions/{code}/rounds/1/rate/", {**body, "value": 0}, token=voter)
    assert again.status_code == 409

    from memz.models import Vote

    assert Vote.objects.filter(submission_id=memes[0]["submission_id"], value=2).count() == 1


def test_my_own_ratings_come_back_in_the_state_and_nobody_elses_do(client, bank):
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)
    rater = next(t for t in tokens if not _state(client, code, t)["round"]["memes"][0]["is_mine"])
    post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": memes[0]["submission_id"], "value": 1}, token=rater,
    )

    mine = _state(client, code, rater)["round"]
    assert mine["my_ratings"] == {str(memes[0]["submission_id"]): 1}

    for other in tokens:
        if other == rater:
            continue
        theirs = _state(client, code, other)["round"]
        assert theirs["my_ratings"] == {}, "one player's state leaked another player's verdict"


def test_the_reveal_ending_finishes_the_round_outright_with_no_voting_phase(client, bank):
    """SPR-Z.10's central change: the old separate grid where everyone
    picked one favourite is gone. When the last meme's slot ends, the
    round is already decided."""
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)
    rater = next(t for t in tokens if not _state(client, code, t)["round"]["memes"][0]["is_mine"])
    post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": memes[0]["submission_id"], "value": 2}, token=rater,
    )

    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])

    after = _state(client, code, tokens[0])["round"]
    assert after["status"] == "done", "the round went somewhere other than straight to its result"
    assert after["vote_deadline"] is None


def test_judge_mode_still_gets_its_own_voting_phase_after_the_reveal(client, bank):
    """The one mode the merge doesn't apply to: a judge picks one winner
    out of the whole round, which can only happen once they've seen it."""
    code, tokens = _room(client, scoring_mode="judge")
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)

    refused = post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": memes[0]["submission_id"], "value": 2}, token=tokens[0],
    )
    assert refused.status_code == 409, "judge mode should not take per-meme ratings"

    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])
    assert _state(client, code, tokens[0])["round"]["status"] == "voting"


def test_relaxed_mode_still_has_no_rating_at_all(client, bank):
    code, tokens = _room(client, game_mode="relaxed")
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)
    refused = post(
        client, f"/memz/api/sessions/{code}/rounds/1/rate/",
        {"submission_id": memes[0]["submission_id"], "value": 2}, token=tokens[0],
    )
    assert refused.status_code == 409


def test_an_invalid_verdict_value_is_refused(client, bank):
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]
    _show_meme(code, 0)
    rater = next(t for t in tokens if not _state(client, code, t)["round"]["memes"][0]["is_mine"])
    for bad in (5, -1, "אוהב", None):
        r = post(
            client, f"/memz/api/sessions/{code}/rounds/1/rate/",
            {"submission_id": memes[0]["submission_id"], "value": bad}, token=rater,
        )
        assert r.status_code == 409, f"value {bad!r} was accepted"


# ------------------------------------------- Rule 4.7.1, nobody is named


def test_the_round_result_never_says_who_made_which_meme(client, bank):
    code, tokens = _room(client)
    _all_submit(client, code, tokens)

    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])

    results = _state(client, code, tokens[0])["round"]["results"]
    assert results, "no results came back"
    for row in results:
        assert "nickname" not in row, "the round result named a meme's author"
        assert "player_id" not in row, "the round result carried the author's id"
    assert sum(1 for row in results if row["is_mine"]) == 1, "a player can still find their own"

    # The leaderboard is still by name -- that is the whole point of the
    # split: names on the scoreboard, never on a meme.
    assert all(p["nickname"] for p in _state(client, code, tokens[0])["players"])


def test_the_round_result_never_shows_what_a_single_meme_scored(client, bank):
    """Rule 4.7.2 (ACT-Z.14). Avi, seeing SPR-Z.10 live: "בסוף הראת גם את
    רשימת המובילים אבל גם כמה כל מים קיבל. וזה עושה קשר" — and he's right.
    Hiding the author while publishing the meme's score is not anonymity:
    a meme worth 4, beside a leaderboard where exactly one player just
    rose by 4, is signed. The numbers are gone from the payload, not just
    from the screen, so a hand-written client can't read them either."""
    code, tokens = _room(client)
    _all_submit(client, code, tokens)
    memes = _state(client, code, tokens[0])["round"]["memes"]

    # One meme is loved by everyone, the others get nothing, so if a score
    # were exposed anywhere the correlation would be trivial.
    _show_meme(code, 0)
    for token in tokens:
        if _state(client, code, token)["round"]["memes"][0]["is_mine"]:
            continue
        post(
            client, f"/memz/api/sessions/{code}/rounds/1/rate/",
            {"submission_id": memes[0]["submission_id"], "value": 2}, token=token,
        )

    from memz.game import current_round
    from memz.models import Session

    round_obj = current_round(Session.objects.get(code=code))
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])

    round_state = _state(client, code, tokens[0])["round"]
    for row in round_state["results"]:
        assert "points" not in row, "the round result published a single meme's score"
        assert "votes" not in row, "the round result published a single meme's vote count"
        assert "round_winner" not in row, "the round result flagged which meme won"

    # The scoring itself still happened -- it just lives in the aggregate.
    from memz.scoring import round_scores

    assert sorted(round_scores(round_obj).values()) == [0, 0, 4]
    assert sorted(p["score"] for p in _state(client, code, tokens[0])["players"]) == [0, 0, 4]


def test_the_end_of_game_gallery_is_anonymous_too(client, bank):
    code, tokens = _room(client)
    _all_submit(client, code, tokens)

    from memz.game import current_round
    from memz.models import Session

    session = Session.objects.get(code=code)
    round_obj = current_round(session)
    round_obj.reveal_deadline = timezone.now() - timezone.timedelta(seconds=1)
    round_obj.save(update_fields=["reveal_deadline"])
    _state(client, code, tokens[0])
    post(client, f"/memz/api/sessions/{code}/advance/", token=tokens[0])

    final = _state(client, code, tokens[0])
    assert final["status"] == "finished"
    assert final["gallery"], "no gallery came back"
    for row in final["gallery"]:
        assert "nickname" not in row, "the podium gallery named a meme's author"
    assert sum(1 for row in final["gallery"] if row["is_mine"]) == 1
    # The podium itself is by name, as it always was.
    assert all(row["nickname"] for row in final["podium"])
