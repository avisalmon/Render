"""SPR-W.5 — memz: small wins (docs/memz/backlog.md, Epic W).

Three gaps the review left, each small and each a real one:

1. **"תן לי רעיון"** — a blank box under a 60-second clock is the hardest
   thing in the app, and hardest for exactly the people memz is for: the
   shy one at the table, the twelve-year-old, the slow typist. They are
   the ones who submit nothing and get told "לא הספקת, קורה".
2. **The result screen moves on by itself** — spec'd since SPR-Z.3
   (`RESULT_AUTO_ADVANCE_SECONDS`) and never built, which left the one
   screen in the game that could sit there forever with nothing saying
   why: the host puts their phone down and the room waits.
3. **Titles explained** — "הסוס השחור" told a player only that the app had
   decided something about them.
"""

import io

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import conf, game, ideas
from memz.models import MemeImage, Round, Session, Vote
from memz.titles import EXPLANATIONS, LABELS, TITLE_ORDER

pytestmark = [pytest.mark.sprw5, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 2)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    for i in range(8):
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), (25 * i, 90, 150)).save(buf, format="PNG")
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"w5-{i}.png", ContentFile(buf.getvalue()), save=True)
    yield


def _room(round_count=2, **kwargs):
    session, host = game.create_session(
        host_user=None, round_count=round_count, round_seconds=60, vote_seconds=20,
        host_nickname="אבי", **kwargs
    )
    p2 = game.join_session(session, "מיכל")
    p3 = game.join_session(session, "יונתן")
    game.start_session(session, host)
    return session, host, p2, p3


def _play_round_to_result(session, players, number=1):
    for player, text in zip(players, ("כיתוב א", "כיתוב ב", "כיתוב ג")):
        game.submit_caption(session, player, number, caption_text=text)
    round_obj = game.current_round(session)
    per = conf.get("REVEAL_SECONDS_PER_MEME")
    count = round_obj.submissions.filter(meme__isnull=False).count()
    for index, submission in enumerate(game.reveal_order(round_obj)):
        Round.objects.filter(pk=round_obj.pk).update(
            reveal_deadline=timezone.now()
            + timezone.timedelta(seconds=per * count - (per * index + per / 2))
        )
        for rater in players:
            if submission.player_id == rater.id:
                continue
            game.rate_submission(session, rater, number, submission.id, Vote.LOVE if index == 0 else Vote.SOSO)
    game.advance(session, players[0])   # ends the reveal -> the round is done
    return game.current_round(session)


# --------------------------------------------------- 1. "תן לי רעיון"


def test_three_starters_come_back_even_with_no_model():
    """Rule 4.4.6's hardest requirement is not the ideas, it is that there
    is never a wait and never an error. The tests run in stub mode, which
    is the same path a production outage takes."""
    session, host, p2, p3 = _room()
    round_obj = game.current_round(session)
    submission = round_obj.submissions.get(player=host)

    got = ideas.starters_for(round_obj, submission)
    assert len(got) == ideas.IDEAS_PER_ASK
    assert all(isinstance(line, str) and line.strip() for line in got)
    assert len(set(got)) == len(got), "the same starter twice is one idea, not three"


def test_starters_fit_a_caption_box():
    session, host, _p2, _p3 = _room()
    round_obj = game.current_round(session)
    submission = round_obj.submissions.get(player=host)
    limit = conf.get("CAPTION_MAX_CHARS")
    for line in ideas.starters_for(round_obj, submission):
        assert len(line) <= limit
        assert "\n" not in line


def test_asking_twice_costs_one_call():
    """Cached on the submission: the button is free to tap again, and a
    room of ten does not make ten calls a round."""
    session, host, _p2, _p3 = _room()
    round_obj = game.current_round(session)
    submission = round_obj.submissions.get(player=host)

    calls = []
    real = ideas._ask_model
    ideas._ask_model = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
    try:
        first = ideas.starters_for(round_obj, submission)
        second = ideas.starters_for(round_obj, submission)
    finally:
        ideas._ask_model = real
    assert first == second
    assert len(calls) == 1, f"the model was asked {len(calls)} times"


def test_a_model_that_answers_badly_falls_through_to_the_canned_set():
    """Every failure path there is, one at a time: an exception, an empty
    reply, and a reply with too few usable lines."""
    session, host, _p2, _p3 = _room()
    round_obj = game.current_round(session)
    submission = round_obj.submissions.get(player=host)

    import app.ai_chat as ai_chat
    from django.core.cache import cache as django_cache

    real = ai_chat.call_openai
    bad_replies = [
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
        lambda *a, **k: {"content": ""},
        lambda *a, **k: {"content": "רק רעיון אחד"},
        lambda *a, **k: {},
    ]
    try:
        for reply in bad_replies:
            django_cache.delete(ideas._cache_key(submission))
            ai_chat.call_openai = reply
            got = ideas.starters_for(round_obj, submission)
            assert len(got) == ideas.IDEAS_PER_ASK
            assert all(line in ideas.FALLBACK_IDEAS for line in got)
    finally:
        ai_chat.call_openai = real


def test_a_numbered_model_reply_is_cleaned_up():
    """Models number their lists however firmly they are told not to."""
    session, host, _p2, _p3 = _room()
    round_obj = game.current_round(session)
    submission = round_obj.submissions.get(player=host)

    import app.ai_chat as ai_chat

    real = ai_chat.call_openai
    ai_chat.call_openai = lambda *a, **k: {
        "content": '1. "רעיון ראשון"\n2. רעיון שני\n3) רעיון שלישי'
    }
    try:
        got = ideas.starters_for(round_obj, submission)
    finally:
        ai_chat.call_openai = real
    assert got == ["רעיון ראשון", "רעיון שני", "רעיון שלישי"]


def test_the_endpoint_gives_ideas_while_writing(client):
    session, host, _p2, _p3 = _room()
    response = client.post(
        f"/memz/api/sessions/{session.code}/rounds/1/ideas/",
        HTTP_X_MEMZ_PLAYER=host.guest_token,
    )
    assert response.status_code == 200, response.content
    assert len(response.json()["ideas"]) == ideas.IDEAS_PER_ASK


def test_the_endpoint_refuses_once_the_caption_is_in(client):
    """Nothing to help with, and an endpoint that answers in every phase is
    one somebody can bill us for in every phase."""
    session, host, _p2, _p3 = _room()
    game.submit_caption(session, host, 1, caption_text="כבר כתבתי")
    response = client.post(
        f"/memz/api/sessions/{session.code}/rounds/1/ideas/",
        HTTP_X_MEMZ_PLAYER=host.guest_token,
    )
    assert response.status_code == 409


def test_the_endpoint_needs_a_player_in_this_session(client):
    session, _host, _p2, _p3 = _room()
    assert client.post(f"/memz/api/sessions/{session.code}/rounds/1/ideas/").status_code in (401, 403)


def test_an_idea_is_offered_but_never_submitted():
    """The joke has to stay the player's, or the game stops being worth
    playing: tapping a starter fills the box and nothing else."""
    js = open("static/memz/game.js", encoding="utf-8").read()
    block = js[js.index('var ideasBtn = root.querySelector("[data-ideas-btn]");'):js.index('var swapImageBtn')]
    assert "input.value = chip.textContent" in block
    assert "/submit/" not in block, "tapping an idea must not submit it"
    assert "input.focus()" in block, "the box should be ready to edit"


# ---------------------------------------- 2. the result screen moves on


def test_a_finished_round_gets_a_result_deadline(settings):
    settings.MEMZ_RESULT_AUTO_ADVANCE_SECONDS = 20
    session, host, p2, p3 = _room()
    round_obj = _play_round_to_result(session, [host, p2, p3])
    round_obj.refresh_from_db()
    assert round_obj.status == Round.DONE
    left = (round_obj.result_deadline - timezone.now()).total_seconds()
    assert 15 < left <= 20


def test_the_result_deadline_starts_the_next_round_on_its_own():
    """Rule 4.7.3. On the server, on the first request after the deadline
    (Rule 5.4.3) — never from a client's own countdown, which would have
    been every phone in the room racing to advance the round."""
    session, host, p2, p3 = _room(round_count=2)
    round_obj = _play_round_to_result(session, [host, p2, p3])
    Round.objects.filter(pk=round_obj.pk).update(
        result_deadline=timezone.now() - timezone.timedelta(seconds=1)
    )

    game.sync(session)
    session.refresh_from_db()
    assert session.status == Session.PLAYING
    current = game.current_round(session)
    assert current.number == 2 and current.status == Round.CAPTIONING


def test_the_last_rounds_result_deadline_ends_the_game():
    session, host, p2, p3 = _room(round_count=1)
    round_obj = _play_round_to_result(session, [host, p2, p3])
    Round.objects.filter(pk=round_obj.pk).update(
        result_deadline=timezone.now() - timezone.timedelta(seconds=1)
    )
    game.sync(session)
    session.refresh_from_db()
    assert session.status == Session.FINISHED


def test_the_host_can_still_move_on_early_and_that_still_wins():
    """The floor under the host's button, not a replacement for it."""
    session, host, p2, p3 = _room(round_count=2)
    _play_round_to_result(session, [host, p2, p3])
    game.advance(session, host)
    session.refresh_from_db()
    assert game.current_round(session).number == 2


def test_syncing_a_stale_result_twice_does_not_skip_a_round():
    """`sync` loops until nothing changes, so a condition that stays true
    after it fires is how that loop stops terminating — and how a room
    would find round 2 gone before anybody saw it."""
    session, host, p2, p3 = _room(round_count=3)
    round_obj = _play_round_to_result(session, [host, p2, p3])
    Round.objects.filter(pk=round_obj.pk).update(
        result_deadline=timezone.now() - timezone.timedelta(seconds=30)
    )
    game.sync(session)
    game.sync(session)
    session.refresh_from_db()
    assert game.current_round(session).number == 2, "the auto-advance ran more than once"
    assert session.rounds.count() == 2


def test_the_deadline_reaches_the_client_so_the_wait_is_visible():
    session, host, p2, p3 = _room()
    _play_round_to_result(session, [host, p2, p3])
    from memz import state

    payload = state.build(session, host)
    assert payload["round"]["status"] == Round.DONE
    assert payload["round"]["result_deadline"]

    js = open("static/memz/game.js", encoding="utf-8").read()
    assert "data-result-timer" in js
    assert "result_deadline" in js


# --------------------------------------------------- 3. titles explained


def test_every_title_has_a_label_and_an_explanation():
    for key in TITLE_ORDER:
        assert LABELS.get(key), f"{key} has no label"
        note = EXPLANATIONS.get(key)
        assert note, f"{key} has no explanation"
        assert note != LABELS[key], f"{key}'s explanation just repeats its name"
        assert len(note) <= 40, f"{key}'s explanation is too long to sit under a name"


def test_the_explanation_reaches_the_podium_payload():
    session, host, p2, p3 = _room(round_count=1)
    _play_round_to_result(session, [host, p2, p3])
    game.advance(session, host)
    session.refresh_from_db()
    assert session.status == Session.FINISHED

    from memz import state

    podium = state.build(session, host)["podium"]
    titled = [row for row in podium if row["title"]]
    assert titled, "a played game should hand out at least one title"
    for row in titled:
        assert row["title_note"], f"{row['title']} reached the podium with nothing explaining it"


def test_the_explanation_is_on_both_podiums_and_on_the_card():
    js = open("static/memz/game.js", encoding="utf-8").read()
    assert "memz-title-note" in js, "the phone podium does not show it"
    assert "row.title_note" in js
    cards = open("memz/share_cards.py", encoding="utf-8").read()
    assert "TITLE_NOTES" in cards, "the forwarded card does not show it"


def test_the_podium_row_no_longer_crowds_the_badge_against_the_score():
    """The review's "badges overlapping names and scores": the podium was
    an inline-flow list, so a badge sat in the text stream beside both."""
    js = open("static/memz/game.js", encoding="utf-8").read()
    assert "memz-podium-place" in js and "memz-podium-who" in js and "memz-podium-score" in js
    css = open("static/memz/memz.css", encoding="utf-8").read()
    block = css[css.index(".memz-podium {"):css.index(".memz-title-note")]
    assert "display: flex" in block
