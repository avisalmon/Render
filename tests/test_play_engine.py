"""SPR-B.11.1: the engine, to the chip.

The shoe is stacked card by card so every payout is checked against a number a
person could work out on paper, and a long seeded run is played against a
dealer-mimic strategy whose house edge is a published figure, which is the test
that would catch a wrong dealer rule or a wrong payout that no single hand
would.
"""

import random
from collections import Counter

import pytest

from blackjack import engine
from blackjack.models import DEFAULT_RULES

pytestmark = pytest.mark.playsim

CARDS = "A23456789TJQK"


def c(rank, suit=0):
    return CARDS.index(rank) + 13 * suit


def stacked(*ranks, decks=6):
    """A shoe that deals exactly these ranks first, in order."""
    return engine.Shoe([c(r) for r in ranks] + [c("2")] * 60, decks=decks, cut_at=10**6)


def rules(**over):
    return dict(DEFAULT_RULES, **over)


def played(ranks, moves=(), bet=10, chips=1000, **over):
    """Deal and apply each move; returns the state and the chips left."""
    r = rules(**over)
    shoe = stacked(*ranks)
    state = engine.start(shoe, bet, r)
    chips -= bet
    for move in moves:
        if state["phase"] == "insurance":
            assert move in ("insure", "decline"), state
            chips -= engine.decide_insurance(state, shoe, r, move == "insure")
        else:
            chips -= engine.act(state, shoe, r, move, chips)
    return state, chips


# --- cards and totals ---------------------------------------------------------


def test_values_and_totals():
    assert [engine.value(c(r)) for r in "A2T9JQK"] == [11, 2, 10, 9, 10, 10, 10]
    assert engine.total([c("A"), c("K")]) == (21, True)
    assert engine.total([c("A"), c("A")]) == (12, True)
    assert engine.total([c("A"), c("5"), c("K")]) == (16, False)
    assert engine.total([c("A"), c("A"), c("9")]) == (21, True)
    assert engine.total([c("K"), c("Q"), c("5")]) == (25, False)
    assert engine.is_natural([c("A"), c("T")])
    assert not engine.is_natural([c("7"), c("7"), c("7")])


def test_every_card_has_one_rank_and_one_suit():
    seen = {(engine.rank(n), engine.suit(n)) for n in range(52)}
    assert len(seen) == 52


# --- the shoe -----------------------------------------------------------------


@pytest.mark.parametrize("decks", [4, 6, 8])
def test_a_shoe_is_the_right_number_of_real_decks(decks):
    cards = engine.new_cards(decks, random.Random(1))
    assert len(cards) == 52 * decks
    assert set(Counter(cards).values()) == {decks}
    ranks = Counter(engine.rank(n) for n in cards)
    assert set(ranks.values()) == {4 * decks}


def test_a_shoe_is_actually_shuffled():
    cards = engine.new_cards(6, random.Random(1))
    assert cards != sorted(cards)
    # Not merely rotated or reversed.
    assert cards != engine.new_cards(6, random.Random(2))
    # The first fifty-two cards are not a clean deck, which is what an unshuffled
    # or lightly shuffled shoe gives away.
    assert len(set(cards[:52])) < 52


def test_the_same_seed_gives_the_same_shoe_so_a_bug_can_be_replayed():
    assert engine.new_cards(6, random.Random(7)) == engine.new_cards(6, random.Random(7))


def test_the_cut_card_is_between_sixty_five_and_seventy_eight_percent():
    rng = random.Random(3)
    for _ in range(200):
        cut = engine.cut_point(312, rng)
        assert int(0.65 * 312) <= cut <= int(0.78 * 312)


def test_a_shoe_reshuffles_when_it_runs_out_rather_than_crash():
    shoe = engine.Shoe([c("5"), c("6")], decks=4, rng=random.Random(1))
    shoe.draw()
    shoe.draw()
    assert not shoe.reshuffled
    shoe.draw()
    assert shoe.reshuffled and shoe.left == 52 * 4 - 1


def test_the_cut_card_is_a_signal_to_shuffle_before_the_next_round_not_during():
    shoe = engine.Shoe(list(range(52)), position=30, cut_at=30, decks=1)
    assert shoe.needs_shuffle
    assert not engine.Shoe(list(range(52)), position=29, cut_at=30, decks=1).needs_shuffle


# --- one round, paid to the chip ----------------------------------------------


def test_the_deal_order_is_player_dealer_player_dealer_down():
    state = engine.start(stacked("2", "3", "4", "5", "9"), 10, rules())
    assert [engine.rank(x) for x in state["hands"][0]["cards"]] == ["2", "4"]
    assert [engine.rank(x) for x in state["dealer"]] == ["3", "5"]


def test_a_win_pays_even_money_and_the_stake_comes_back():
    # player 10+10, dealer 10+8, stand
    state, chips = played(["T", "T", "K", "8"], ["S"])
    assert state["phase"] == "settled"
    assert state["hands"][0]["result"] == "win"
    assert engine.net(state) == 10
    assert chips + state["returned"] == 1010


def test_a_loss_loses_the_bet_and_a_push_returns_it():
    lost, chips = played(["T", "T", "9", "K"], ["S"])
    assert engine.net(lost) == -10 and chips + lost["returned"] == 990
    push, chips = played(["T", "T", "T", "K"], ["S"])
    assert engine.net(push) == 0 and chips + push["returned"] == 1000


def test_the_dealer_draws_to_seventeen_and_busts():
    # player 9+10 stands; dealer 6+10 must draw, and draws a 9 to bust on 25
    state, _ = played(["T", "6", "9", "T", "9"], ["S"])
    assert [engine.rank(x) for x in state["dealer"]] == ["6", "10", "9"]
    assert state["hands"][0]["result"] == "win"


def test_the_dealer_stands_on_soft_17_unless_the_table_says_otherwise():
    # dealer A+6. S17: stands on 17, player 18 wins. H17: draws a 4 -> 21, player loses.
    stand, _ = played(["T", "A", "8", "6", "4"], ["decline", "S"])
    assert len(stand["dealer"]) == 2 and stand["hands"][0]["result"] == "win"
    hit, _ = played(["T", "A", "8", "6", "4"], ["decline", "S"], dealer_hits_soft_17=True)
    assert len(hit["dealer"]) == 3 and hit["hands"][0]["result"] == "lose"


def test_a_player_who_busts_loses_and_the_dealer_does_not_play_on():
    state, _ = played(["T", "6", "6", "5", "K"], ["H"])      # 16 hits a king
    assert state["hands"][0]["state"] == "bust"
    assert state["hands"][0]["result"] == "lose"
    assert len(state["dealer"]) == 2


def test_blackjack_pays_three_to_two_or_six_to_five_by_the_rules():
    three, chips = played(["A", "6", "K", "9"])
    assert three["hands"][0]["result"] == "blackjack"
    assert engine.net(three) == 15 and chips + three["returned"] == 1015
    six, _ = played(["A", "6", "K", "9"], blackjack_pays="6:5")
    assert engine.net(six) == 12


def test_dealer_blackjack_is_found_before_the_player_can_put_more_in():
    state, chips = played(["T", "K", "9", "A"])
    assert state["phase"] == "settled" and state["dealer_natural"]
    assert state["hands"][0]["result"] == "lose"
    assert engine.net(state) == -10


def test_both_with_blackjack_is_a_push():
    state, _ = played(["A", "K", "K", "A"])
    assert state["hands"][0]["result"] == "push" and engine.net(state) == 0


def test_an_ace_up_asks_about_insurance_first():
    state, _ = played(["T", "A", "8", "5"])
    assert state["phase"] == "insurance"
    assert engine.legal(state, rules(), 990) == []


def test_insurance_pays_two_to_one_and_cost_half_the_bet():
    state, chips = played(["T", "A", "8", "K"], ["insure"])
    assert state["phase"] == "settled" and state["dealer_natural"]
    assert state["insurance"] == 5
    assert engine.net(state) == 0                    # lost 10 on the hand, won 10 on 5
    assert chips + state["returned"] == 1000


def test_losing_insurance_costs_the_side_bet_and_the_round_goes_on():
    state, chips = played(["T", "A", "8", "5"], ["insure"])
    assert state["phase"] == "player" and state["insurance"] == 5
    assert chips == 985


def test_insurance_on_a_player_blackjack_is_even_money():
    state, chips = played(["A", "A", "K", "K"], ["insure"])
    assert state["hands"][0]["result"] == "push"
    assert engine.net(state) == 10                    # the natural pushed, the side bet paid 10
    taken, _ = played(["A", "A", "K", "5", "9"], ["insure"])
    assert engine.net(taken) == 15 - 5                # natural pays 15, side bet lost 5
    # which is the same ten chips either way: that is what "even money" means


# --- doubling, splitting ------------------------------------------------------


def test_double_takes_one_card_stakes_twice_and_pays_twice():
    # 5+6=11, dealer 10+7, double draws a 9 -> 20, wins
    state, chips = played(["5", "T", "6", "7", "9"], ["D"])
    hand = state["hands"][0]
    assert hand["doubled"] and hand["bet"] == 20 and len(hand["cards"]) == 3
    assert engine.net(state) == 20 and chips + state["returned"] == 1020


def test_double_is_not_offered_on_a_third_card_or_without_the_chips():
    state, _ = played(["2", "T", "3", "7"])
    assert "D" in engine.legal(state, rules(), 990)
    assert "D" not in engine.legal(state, rules(), 9)
    shoe = stacked("4")
    engine.act(state, shoe, rules(), "H", 990)
    assert "D" not in engine.legal(state, rules(), 990)


def test_splitting_makes_two_hands_each_with_its_own_bet_and_result():
    # 8,8 vs dealer 10+7; split. First 8 gets a 3 (11), second gets a K (18)
    # stack: p1=8 d=T p2=8 d=7 | split draws: hand1 gets 3, hand2 gets K | then hit 3 -> 8+3+3=14.. stand
    state, chips = played(["8", "T", "8", "7", "3", "K"], ["P"])
    assert len(state["hands"]) == 2
    assert [engine.rank(x) for x in state["hands"][0]["cards"]] == ["8", "3"]
    assert [engine.rank(x) for x in state["hands"][1]["cards"]] == ["8", "K"]
    assert chips == 980
    engine.act(state, stacked("K"), rules(), "D", chips)          # 11 doubles into a king
    engine.act(state, stacked("2"), rules(), "S", 960)
    assert state["phase"] == "settled"
    assert [h["result"] for h in state["hands"]] == ["win", "win"]
    assert engine.net(state) == 20 + 10


def test_a_split_pair_may_be_two_different_ten_cards():
    state, _ = played(["K", "T", "Q", "7"])
    assert "P" in engine.legal(state, rules(), 990)


def test_split_aces_take_one_card_each_and_stop():
    state, _ = played(["A", "T", "A", "7", "5", "K"], ["P"])
    assert state["phase"] == "settled"
    assert [len(h["cards"]) for h in state["hands"]] == [2, 2]


def test_twenty_one_after_a_split_is_not_a_blackjack():
    state, _ = played(["A", "T", "A", "7", "K", "9"], ["P"])
    first = state["hands"][0]
    assert engine.total(first["cards"])[0] == 21
    assert first["result"] == "win" and first["net"] == 10          # 1:1, not 3:2


def test_resplit_aces_only_when_the_table_allows_it():
    off, _ = played(["A", "T", "A", "7", "A", "5"], ["P"])
    assert len(off["hands"]) == 2
    on, _ = played(["A", "T", "A", "7", "A", "5", "6"], ["P"], resplit_aces=True)
    assert on["phase"] == "player"
    assert "P" in engine.legal(on, rules(resplit_aces=True), 900)


def test_hit_split_aces_when_the_table_allows_it():
    state, _ = played(["A", "T", "A", "7", "5", "K"], ["P"], hit_split_aces=True)
    assert state["phase"] == "player"
    assert "H" in engine.legal(state, rules(hit_split_aces=True), 900)


def test_the_split_limit_counts_hands():
    over = dict(max_splits=2)
    state, chips = played(["8", "T", "8", "7", "8", "8"], ["P"], **over)
    assert len(state["hands"]) == 2
    assert "P" not in engine.legal(state, rules(**over), chips)
    assert engine.can_split(state, rules(**over), chips) is False


def test_double_after_split_follows_the_rules_and_a_split_needs_chips():
    state, chips = played(["8", "T", "8", "7", "3", "2"], ["P"])
    assert "D" in engine.legal(state, rules(), chips)
    assert "D" not in engine.legal(state, rules(double_after_split=False), chips)
    assert "P" not in engine.legal(state, rules(), 5)


# --- which chart cell a hand is -----------------------------------------------


def test_the_situation_names_the_cell_the_chart_would_answer():
    def situ(ranks, chips=1000, **over):
        state = engine.start(stacked(*ranks), 10, rules(**over))
        return engine.situation(state, rules(**over), chips)

    assert situ(["8", "T", "8", "7"]) == ("pair", 8)
    assert situ(["K", "T", "Q", "7"]) == ("pair", 10)
    assert situ(["A", "T", "A", "7"]) == ("pair", 11)
    assert situ(["6", "T", "5", "7"]) == ("hard", 11)
    assert situ(["A", "T", "6", "7"]) == ("soft", 17)
    # a pair that cannot be split is played by its total
    assert situ(["8", "T", "8", "7"], chips=5) == ("hard", 16)
    assert situ(["8", "T", "8", "7"], max_splits=1) == ("hard", 16)
    # aces that cannot be split are a soft 12, which the chart does not contain
    assert situ(["A", "T", "A", "7"], chips=5) is None


# --- the long run -------------------------------------------------------------


def _round(shoe, r, strategy, rng):
    bet = 10
    state = engine.start(shoe, bet, r)
    chips = 10**6
    spent = bet
    while state["phase"] != "settled":
        if state["phase"] == "insurance":
            spent += engine.decide_insurance(state, shoe, r, False)
            continue
        options = engine.legal(state, r, chips)
        spent += engine.act(state, shoe, r, strategy(state, options, rng), chips)
    return state, spent


def _mimic(state, options, rng):
    points, _soft = engine.total(state["hands"][state["active"]]["cards"])
    return "H" if points < 17 else "S"


def _wander(state, options, rng):
    return rng.choice(options)


@pytest.mark.parametrize("over", [{}, {"dealer_hits_soft_17": True}, {"blackjack_pays": "6:5"},
                                  {"decks": 8, "max_splits": 2, "resplit_aces": True,
                                   "hit_split_aces": True, "double_after_split": False}])
def test_ten_thousand_random_rounds_keep_the_books(over):
    """Whatever is played, chips are conserved: what comes back minus what went
    on the felt is the net, nothing is created, no hand outgrows the limit, and
    the dealer finishes on 17 or more whenever there was a hand to beat."""
    rng = random.Random(11)
    r = rules(**over)
    shoe = engine.Shoe([], decks=r["decks"], rng=rng)
    for _ in range(10000):
        if shoe.needs_shuffle:
            shoe.shuffle()
        state, spent = _round(shoe, r, _wander, rng)
        assert engine.staked(state) == spent
        assert engine.net(state) == state["returned"] - spent
        assert len(state["hands"]) <= max(1, r["max_splits"])
        for hand in state["hands"]:
            assert hand["result"] in ("win", "lose", "push", "blackjack")
            assert hand["net"] in (-hand["bet"], 0, hand["bet"], engine._pays(hand["bet"], r))
        if any(h["state"] == "stand" for h in state["hands"]) and not state["dealer_natural"]:
            points, soft = engine.total(state["dealer"])
            assert points >= 17
            if points == 17 and soft:
                assert not r["dealer_hits_soft_17"]


def test_the_house_edge_of_copying_the_dealer_is_where_it_should_be():
    """Hitting to 17 and standing, no doubles, splits or insurance, is a
    well-known strategy with an edge of roughly minus five and a half percent
    at 3:2. A wrong dealer rule, payout or shuffle moves this by whole points,
    which is why it is the one test that would catch what a single hand
    cannot."""
    rng = random.Random(2026)
    r = rules()
    shoe = engine.Shoe([], decks=6, rng=rng)
    wagered = won = naturals = rounds = 0
    for _ in range(60000):
        if shoe.needs_shuffle:
            shoe.shuffle()
        state, spent = _round(shoe, r, _mimic, rng)
        wagered += spent
        won += engine.net(state)
        rounds += 1
        naturals += state["hands"][0]["result"] == "blackjack"
    edge = won / wagered
    assert -0.085 < edge < -0.035, edge
    assert 0.040 < naturals / rounds < 0.055, naturals / rounds
