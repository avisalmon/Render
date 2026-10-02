"""SPR-B.11.2 and B.11.3: the play table through its API, and as a person sees it.

Avi, 2026-10-02: "I want it. And free for all. No ai api needed."

Four promises are held here and none of them is about arithmetic (the engine
tests do that):

**Free.** A signed-in person with no subscription, no coupon and no trial plays
and is judged exactly like anybody else.

**Secret.** The shoe and the dealer's down card are on the server. Neither is in
the page, in the table's JSON, or in the rounds endpoint until the round is over.

**Counted.** A decision at this table is an ordinary `Attempt`, judged against
the chart row for the hand actually held, so the grid, the graph and the note
every twenty hands move with it.

**Safe to tap twice.** A request made against an old picture of the table is
refused with the current table, so a double tap or a second tab cannot play a
decision twice.
"""

import os
import re
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from blackjack import engine

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.playsim

PASSWORD = "play-sim-pass"
CARDS = "A23456789TJQK"
API = "/blackjack/api/play-tables/"


def _card(rank, suit=0):
    return CARDS.index(rank) + 13 * suit


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(username="sim@example.com", email="sim@example.com",
                                    password=PASSWORD)


@pytest.fixture
def other(db):
    return User.objects.create_user(username="two@example.com", email="two@example.com",
                                    password=PASSWORD)


def stack(user, *ranks, chips=None):
    """Put these ranks on top of this person's shoe: player, dealer up, player,
    dealer hole, then whatever the hand draws. A deuce pile follows."""
    from blackjack import play
    from blackjack.models import Player

    player = Player.for_user(user)
    table = play.table_for(player)
    table.rule_set = player.rule_set
    table.cards = [_card(r) for r in ranks] + [_card("2")] * 80
    table.position = 0
    table.cut_at = 10**6
    if chips is not None:
        table.chips = chips
    table.save()
    return table


def post(client, endpoint, **body):
    return client.post(f"{API}{endpoint}/", body, content_type="application/json")


def table_now(client):
    return client.get(f"{API}current/").json()


def deal(client, bet=10):
    step = table_now(client)["step"]
    return post(client, "deal", bet=bet, step=step)


def act(client, move):
    step = table_now(client)["step"]
    return post(client, "act", action=move, step=step)


def insure(client, take):
    step = table_now(client)["step"]
    return post(client, "insurance", take=take, step=step)


# ---------------------------------------------------------------- free for all


def test_a_person_with_nothing_paid_plays_and_is_judged(client, person):
    """No subscription, no coupon, no trial: the simulator does not ask."""
    from datetime import timedelta

    from django.utils import timezone

    from blackjack import gate
    from blackjack.models import Player

    # The thirty free minutes of the coach start at the first hand and are over.
    Player.objects.filter(pk=Player.for_user(person).pk).update(
        first_used_at=timezone.now() - timedelta(hours=3))
    assert not gate.ai_is_open(person), "the fixture person must not have the coach"
    client.force_login(person)
    assert client.get("/blackjack/play/").status_code == 200

    stack(person, "T", "T", "6", "7")
    assert deal(client).status_code == 200
    reply = act(client, "S")
    assert reply.status_code == 200
    assert reply.json()["verdict"]["reason"], "a verdict with no explanation"
    assert not gate.ai_is_open(person), "playing opened the coach"


def test_a_stranger_is_sent_to_sign_in_and_the_api_refuses_them(client, person):
    page = client.get("/blackjack/play/")
    assert page.status_code == 302 and "/login/" in page["Location"]
    assert client.get(f"{API}current/").status_code in (401, 403)
    assert client.post(f"{API}deal/", {"bet": 10, "step": 0},
                       content_type="application/json").status_code in (401, 403)


def test_no_ai_is_called_anywhere_in_the_simulator():
    """The explanation is the chart's own sentence. This is the file-level
    guard: none of the simulator's modules reaches for a model."""
    import pathlib

    for name in ("play.py", "engine.py", "recording.py"):
        text = pathlib.Path("blackjack", name).read_text(encoding="utf-8")
        assert not re.search(r"openai|anthropic|llm|chat\.completions|ai_is_open|paid_only",
                             text, re.I), f"{name} reaches for a model or the gate"


# ---------------------------------------------------------------- the secret


def test_the_hole_card_is_not_sent_until_the_round_is_over(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "9")     # dealer has 10 up and a 9 down
    body = deal(client).json()

    cards = body["round"]["dealer"]["cards"]
    assert cards[0]["r"] == "10" and cards[1] == {"down": True}
    assert body["round"]["dealer"]["total"] == 10, "the total gave the hole card away"
    import json

    assert '"r": "9"' not in json.dumps(body), "the 9 in the hole is in the reply"
    assert "position" not in body and "cards_left" not in body

    # The other doors into the same data are shut the same way.
    listed = client.get("/blackjack/api/play-rounds/").json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert rows[0]["dealer"]["cards"][1] == {"down": True}
    seat = client.get(API).json()
    seat = seat["results"][0] if isinstance(seat, dict) else seat[0]
    assert "cards" not in seat and "position" not in seat and "cut_at" not in seat
    assert "cards" not in client.get(f"{API}{seat['id']}/").json()

    done = act(client, "S").json()
    assert done["round"]["phase"] == "settled"
    assert done["round"]["dealer"]["cards"][1]["r"] == "9", "settled, and still hidden"


def test_the_page_itself_carries_no_shoe_and_no_hole_card(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "K")
    deal(client)
    html = client.get("/blackjack/play/").content.decode("utf-8")
    payload = re.search(r'id="bjTable" type="application/json">(.*?)</script>', html, re.S)
    assert payload, "the page has no table payload"
    import json

    data = json.loads(payload.group(1))
    assert data["round"]["dealer"]["cards"][1] == {"down": True}
    assert "position" not in data and "cut_at" not in data
    assert len(json.dumps(data)) < 4000, "something as big as a shoe went down with the page"


def test_nobody_reads_or_plays_another_persons_table(client, person, other):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")
    deal(client)

    client.force_login(other)
    mine = table_now(client)
    assert mine["round"] is None, "a second person was handed somebody else's round"
    seats = client.get(API).json()
    assert (seats["results"] if isinstance(seats, dict) else seats) != []  # their own, made on sight
    rounds = client.get("/blackjack/api/play-rounds/").json()
    assert (rounds["results"] if isinstance(rounds, dict) else rounds) == []


def test_chips_cannot_be_written(client, person):
    client.force_login(person)
    seat = table_now(client)
    pk = client.get(API).json()
    pk = (pk["results"][0] if isinstance(pk, dict) else pk[0])["id"]
    for verb in (client.put, client.patch):
        assert verb(f"{API}{pk}/", {"chips": 999999}, content_type="application/json").status_code in (
            403, 405)
    assert client.delete(f"{API}{pk}/").status_code in (403, 405)
    assert client.post(API, {"chips": 999999}, content_type="application/json").status_code in (403, 405)
    assert table_now(client)["chips"] == seat["chips"]


# ---------------------------------------------------------------- the bet


@pytest.mark.parametrize("bad", [0, 5, 15, 505, 510, -10, "10", 10.5, True, None])
def test_a_bad_bet_is_refused_and_costs_nothing(client, person, bad):
    client.force_login(person)
    before = table_now(client)
    reply = post(client, "deal", bet=bad, step=before["step"])
    assert reply.status_code == 400, (bad, reply.content)
    after = table_now(client)
    assert after["chips"] == before["chips"] and after["round"] is None


def test_a_bet_larger_than_the_stack_is_refused(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7", chips=40)
    assert deal(client, 50).status_code == 400
    assert deal(client, 40).status_code == 200


def test_dealing_takes_the_bet_and_a_loss_is_gone(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")           # 16 against 17
    assert deal(client, 100).json()["chips"] == 900
    done = act(client, "S").json()
    assert done["round"]["net"] == -100 and done["chips"] == 900


def test_a_win_pays_even_money_and_a_natural_pays_three_to_two(client, person):
    client.force_login(person)
    stack(person, "T", "T", "9", "7")           # 19 against 17
    deal(client, 100)
    assert act(client, "S").json()["chips"] == 1100

    stack(person, "A", "T", "K", "7", chips=1000)   # natural, dealer 17
    reply = deal(client, 100).json()
    assert reply["round"]["phase"] == "settled" and reply["chips"] == 1150


def test_a_dealer_natural_ends_the_round_before_a_double_can_be_lost(client, person):
    client.force_login(person)
    stack(person, "5", "K", "6", "A", chips=1000)   # 11 against a king and an ace: peek
    reply = deal(client, 100).json()
    assert reply["round"]["phase"] == "settled" and reply["chips"] == 900
    assert reply["round"]["dealer"]["natural"] is True


# ---------------------------------------------------------------- safe to tap twice


def test_a_stale_step_is_refused_with_the_table_as_it_now_is(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")
    first = table_now(client)
    assert post(client, "deal", bet=10, step=first["step"]).status_code == 200
    again = post(client, "deal", bet=10, step=first["step"])
    assert again.status_code == 409
    assert again.json()["table"]["step"] == first["step"] + 1
    assert again.json()["table"]["chips"] == 990, "the bet was taken twice"
    # A missing or nonsense step is the same refusal and not a crash.
    assert post(client, "act", action="S").status_code == 409
    assert post(client, "act", action="S", step="abc").status_code == 409


def test_a_decision_cannot_be_replayed(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")
    deal(client)
    step = table_now(client)["step"]
    assert post(client, "act", action="S", step=step).status_code == 200
    assert post(client, "act", action="S", step=step).status_code == 409

    from blackjack.models import Attempt

    assert Attempt.objects.filter(source="simulator").count() == 1


def test_dealing_over_an_open_round_and_acting_with_none_are_refused(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")
    assert act(client, "S").status_code == 409
    deal(client)
    assert deal(client).status_code == 409
    assert table_now(client)["chips"] == 990


def test_an_action_the_table_does_not_allow_is_refused(client, person):
    client.force_login(person)
    stack(person, "T", "T", "6", "7")           # not a pair
    deal(client)
    before = table_now(client)
    assert act(client, "P").status_code == 400
    assert act(client, "X").status_code == 400
    assert table_now(client)["step"] == before["step"]


# ---------------------------------------------------------------- the judging


def test_a_right_decision_and_a_wrong_one_are_recorded_as_attempts(client, person):
    from blackjack.models import Attempt, Chart

    client.force_login(person)
    stack(person, "8", "6", "8", "T")          # 8,8 against a 6
    deal(client)
    cell = Chart.objects.first().cells.get(kind="pair", player=8, dealer=6)
    assert cell.action == "P"

    wrong = act(client, "S").json()["verdict"]
    assert wrong["right"] is False and wrong["correct"] == "P"
    assert wrong["reason"] == cell.reason, "the explanation is the chart's own sentence"

    row = Attempt.objects.get(source="simulator")
    assert (row.cell_kind, row.cell_player, row.cell_dealer) == ("pair", 8, 6)
    assert row.chosen == "S" and row.correct == "P" and row.is_correct is False

    stack(person, "8", "6", "8", "T")
    deal(client)
    right = act(client, "P").json()
    assert right["verdict"]["right"] is True
    assert Attempt.objects.filter(source="simulator", is_correct=True).count() == 1
    assert len(right["round"]["hands"]) == 2, "the pair did not split"


def test_a_double_the_table_forbids_is_judged_by_its_fallback(client, person):
    from blackjack.models import Chart

    client.force_login(person)
    stack(person, "2", "6", "3", "T", "4")     # 2,3 then a 4 against a 6
    deal(client)
    assert act(client, "H").status_code == 200
    now = table_now(client)["round"]
    assert now["legal"] == ["H", "S"], "a double is not allowed on three cards"

    cell = Chart.objects.first().cells.get(kind="hard", player=9, dealer=6)
    assert cell.action == "D"
    verdict = act(client, "H").json()["verdict"]
    assert verdict["correct"] == cell.fallback
    assert verdict["fallback_used"] is True and verdict["right"] is True


def test_a_pair_that_cannot_be_split_is_judged_by_its_total(client, person):
    from blackjack.models import Attempt

    client.force_login(person)
    stack(person, "8", "6", "8", "T", chips=10)    # nothing left to split with
    deal(client, 10)
    assert table_now(client)["round"]["legal"] == ["H", "S"]
    verdict = act(client, "S").json()["verdict"]
    assert verdict["right"] is True                 # 16 against 6: stand
    row = Attempt.objects.get(source="simulator")
    assert (row.cell_kind, row.cell_player) == ("hard", 16)


def test_a_hand_the_chart_does_not_contain_is_played_and_not_scored(client, person):
    from blackjack.models import Attempt

    client.force_login(person)
    stack(person, "2", "T", "2", "7", "5", chips=10)    # 2,2 with nothing to split with: hard 4
    deal(client, 10)
    reply = act(client, "H").json()
    assert reply["verdict"] is None
    assert Attempt.objects.filter(source="simulator").count() == 0


def test_a_decision_here_moves_the_same_counters_as_the_drill(client, person):
    from blackjack.models import Attempt, Player

    client.force_login(person)
    before = table_now(client)["in_batch"]
    stack(person, "T", "T", "6", "7")
    deal(client)
    after = act(client, "S").json()
    assert after["in_batch"] == before + 1
    player = Player.for_user(person)
    assert Attempt.objects.filter(player=player).count() == 1
    assert Attempt.objects.get(player=player).source == "simulator"


def test_twenty_decisions_write_the_note_and_it_comes_back_in_the_reply(client, person):
    from blackjack.models import BatchNote

    client.force_login(person)
    notes = []
    for _ in range(20):
        stack(person, "T", "T", "6", "7")
        deal(client)
        notes.append(act(client, "S").json().get("note"))
    assert BatchNote.objects.count() == 1
    assert notes[-1] and not any(notes[:-1])


# ---------------------------------------------------------------- insurance


def test_insurance_is_offered_on_an_ace_and_is_not_an_attempt(client, person):
    from blackjack.models import Attempt

    client.force_login(person)
    stack(person, "T", "A", "6", "9")
    body = deal(client, 10).json()
    assert body["round"]["phase"] == "insurance" and body["round"]["legal"] == []
    assert act(client, "S").status_code == 409, "played a hand before answering the ace"

    declined = insure(client, False).json()
    assert declined["round"]["phase"] == "player"
    entry = declined["round"]["log"][-1]
    assert entry["kind"] == "insurance" and entry["right"] is True and entry["counted"] is False
    assert Attempt.objects.count() == 0


def test_insurance_pays_two_to_one_and_loses_five_otherwise(client, person):
    client.force_login(person)
    stack(person, "T", "A", "6", "K")            # dealer natural
    deal(client, 10)
    taken = insure(client, True).json()
    assert taken["round"]["phase"] == "settled"
    assert taken["chips"] == 1000, "the side bet did not pay 2 to 1 against the lost hand"

    stack(person, "T", "A", "6", "5", chips=1000)    # no natural
    deal(client, 10)
    taken = insure(client, True).json()
    assert taken["round"]["phase"] == "player" and taken["chips"] == 985


def test_insurance_needs_chips_and_a_boolean(client, person):
    client.force_login(person)
    stack(person, "T", "A", "6", "5", chips=10)
    deal(client, 10)
    assert insure(client, True).status_code == 400, "took a side bet with no chips left"
    step = table_now(client)["step"]
    assert post(client, "insurance", take="yes", step=step).status_code == 400
    assert insure(client, False).status_code == 200


# ---------------------------------------------------------------- the bankroll


def test_the_refill_is_free_only_when_broke_and_between_rounds(client, person):
    from blackjack.models import START_CHIPS

    client.force_login(person)
    step = table_now(client)["step"]
    assert post(client, "refill", step=step).status_code == 400, "refilled a full stack"

    stack(person, "T", "T", "6", "7", chips=10)
    deal(client, 10)
    assert table_now(client)["broke"] is False, "called broke in the middle of a hand"
    assert post(client, "refill", step=table_now(client)["step"]).status_code == 409
    act(client, "S")
    broke = table_now(client)
    assert broke["chips"] == 0 and broke["broke"] is True

    back = post(client, "refill", step=broke["step"]).json()
    assert back["chips"] == START_CHIPS and back["refills"] == 1 and back["broke"] is False


def test_the_shoe_reshuffles_between_rounds_at_the_cut_card(client, person):
    from blackjack import play
    from blackjack.models import Player

    client.force_login(person)
    table = stack(person, "T", "T", "9", "7")
    table.position, table.cut_at = 200, 150
    table.save()
    before = table_now(client)["shoe"]["shuffles"]
    deal(client)
    after = table_now(client)
    assert after["shoe"]["shuffles"] == before + 1
    assert after["shoe"]["of"] == 6 * 52
    assert play.table_for(Player.for_user(person)).position < 20, "dealt from the old shoe"


# ---------------------------------------------------------------- docs and guards


def test_the_two_new_models_have_their_endpoints():
    from blackjack.api import ROUTES
    from blackjack.models import PlayRound, PlayTable

    models = {model for _prefix, _view, model in ROUTES}
    assert {PlayTable, PlayRound} <= models


def test_the_engine_has_no_django_and_no_randomness_of_its_own():
    import pathlib

    text = pathlib.Path("blackjack/engine.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+django", text, re.M)
    assert not re.search(r"^import random|^from random", text, re.M)
    assert engine.RANKS[0] == "A"


# ---------------------------------------------------------------- the real screen


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chrome = pw.chromium.launch()
            yield chrome
            chrome.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")


def _session_for(user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return store.session_key


def _open(browser, live_server, user, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": _session_for(user),
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/blackjack/play/", wait_until="domcontentloaded")
    page.wait_for_selector("#bjChips")
    return context, page, errors


def _no_sideways(page):
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), (
        "the page scrolls sideways"
    )


def _big_enough(page, selector):
    for box in page.locator(selector).evaluate_all(
        "els => els.filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect();"
        " return {h: r.height, w: r.width, t: e.textContent.trim()}; })"
    ):
        assert box["h"] >= 44 and box["w"] >= 44, f"too small to tap: {box}"


def _shot(page, name):
    shots = os.environ.get("BJ_SHOT_DIR")
    if shots:
        page.screenshot(path=f"{shots}/{name}.png", full_page=True)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", [390, 1280])
def test_a_round_from_the_bet_to_the_result(browser, live_server, width):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username=f"ui{width}@e.com", email=f"ui{width}@e.com",
                                    password=PASSWORD)
    stack(user, "T", "T", "9", "7")             # 19 against 17: a win
    context, page, errors = _open(browser, live_server, user, width)

    assert page.locator("#bjChips").inner_text().strip() == "1,000"
    assert page.locator("#bjBetPanel").is_visible()
    assert not page.locator("#bjActPanel").is_visible()
    _no_sideways(page)
    _big_enough(page, "#bjBetPanel button")
    _shot(page, f"play_bet_{width}")

    page.locator('[data-bet="100"]').click()
    assert page.locator("#bjBet").inner_text().strip() == "100"
    page.locator("#bjDeal").click()
    page.wait_for_selector("#bjActPanel:not([hidden])")

    assert page.locator("#bjChips").inner_text().strip() == "900"
    assert page.locator("#bjDealer .bj-card").count() == 2
    assert page.locator("#bjDealer .bj-card.is-down").count() == 1
    assert page.locator("#bjHands .bj-card").count() == 2
    assert page.locator('[data-act="P"]').is_disabled(), "split offered on a hand that is no pair"
    _no_sideways(page)
    _big_enough(page, "#bjActions button")
    _shot(page, f"play_hand_{width}")

    page.locator('[data-act="S"]').click()
    page.wait_for_selector("#bjOutcome:not([hidden])")
    assert page.locator("#bjChips").inner_text().strip() == "1,100"
    assert page.locator("#bjDealer .bj-card.is-down").count() == 0, "the hole card stayed down"
    assert "זכיתם" in page.locator("#bjOutcome").inner_text()
    assert page.locator("#bjVerdict").is_visible()
    assert page.locator("#bjBetPanel").is_visible(), "no way to deal the next hand"
    _no_sideways(page)
    _shot(page, f"play_result_{width}")
    assert not errors, errors
    context.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", [390, 1280])
def test_a_split_shows_two_hands_and_insurance_is_asked_first(browser, live_server, width):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username=f"sp{width}@e.com", email=f"sp{width}@e.com",
                                    password=PASSWORD)
    stack(user, "8", "A", "8", "5", "3", "9", "T", "T")   # ace up: insurance first
    context, page, errors = _open(browser, live_server, user, width)

    page.locator("#bjDeal").click()
    page.wait_for_selector("#bjInsurancePanel:not([hidden])")
    assert not page.locator("#bjActPanel").is_visible(), "could act before answering the ace"
    _big_enough(page, "#bjInsurancePanel button")
    _shot(page, f"play_insurance_{width}")
    page.locator("#bjInsureNo").click()
    page.wait_for_selector("#bjActPanel:not([hidden])")
    assert page.locator("#bjVerdict").is_visible()
    assert "ביטוח" in page.locator("#bjVerdict").inner_text()

    page.locator('[data-act="P"]').click()
    page.wait_for_function("document.querySelectorAll('.bj-sim-hand').length === 2")
    assert page.locator(".bj-sim-hand.is-active").count() == 1
    _no_sideways(page)
    _shot(page, f"play_split_{width}")
    assert not errors, errors
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_reload_in_the_middle_of_a_hand_shows_the_same_hand(browser, live_server):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="reload@e.com", email="reload@e.com",
                                    password=PASSWORD)
    stack(user, "T", "T", "6", "9")
    context, page, errors = _open(browser, live_server, user, 390)
    page.locator("#bjDeal").click()
    page.wait_for_selector("#bjActPanel:not([hidden])")
    before = page.locator("#bjHands").inner_text()

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#bjActPanel:not([hidden])")
    assert page.locator("#bjHands").inner_text() == before
    assert page.locator("#bjDealer .bj-card.is-down").count() == 1
    assert page.locator("#bjChips").inner_text().strip() == "980"      # the default bet is 20
    assert not errors, errors
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_broke_person_is_offered_the_refill_and_not_a_bet(browser, live_server):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="broke@e.com", email="broke@e.com", password=PASSWORD)
    stack(user, "T", "T", "6", "7", chips=0)
    context, page, errors = _open(browser, live_server, user, 390)
    assert page.locator("#bjBrokePanel").is_visible()
    assert not page.locator("#bjBetPanel").is_visible()
    page.locator("#bjRefill").click()
    page.wait_for_selector("#bjBetPanel:not([hidden])")
    assert page.locator("#bjChips").inner_text().strip() == "1,000"
    assert not errors, errors
    context.close()
