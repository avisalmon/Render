"""SPR-B.12.1 — the strategy lab's engine in the browser, held to the server's.

The lab plays its hands in JavaScript (REQ-B.11.23), which means a second copy
of blackjack. REQ-B.11.2 allows that on one condition: the copy is made to agree
with `blackjack/engine.py` to the chip, by a test that cannot be argued with.
Here the same card orders and the same decisions are played through both, over
many rule sets, and every round must come out identical.

Needs `node`. Where it is missing the tests are skipped, never passed.

Traces: REQ-B.11.2, B.11.3, B.11.8, B.11.12, B.11.13 to B.11.19.
"""

import json
import pathlib
import random
import shutil
import subprocess

import pytest

from blackjack import engine, strategy
from blackjack.models import DEFAULT_RULES

pytestmark = [
    pytest.mark.sprblab,
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
]

HERE = pathlib.Path(__file__).parent / "lab_js"

VARIANTS = [
    {},
    {"decks": 4},
    {"decks": 8},
    {"dealer_hits_soft_17": True},
    {"double_after_split": False},
    {"max_splits": 2},
    {"max_splits": 3},
    {"resplit_aces": True},
    {"hit_split_aces": True},
    {"resplit_aces": True, "hit_split_aces": True, "max_splits": 4},
    {"blackjack_pays": "6:5"},
    {"dealer_hits_soft_17": True, "blackjack_pays": "6:5", "double_after_split": False},
]


def _rules(variant):
    rules = dict(DEFAULT_RULES)
    rules.update(variant)
    return rules


def _node(script, payload):
    done = subprocess.run(
        ["node", str(HERE / script)], input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _shoe(rules, rng):
    cards = engine.new_cards(rules["decks"], rng)
    return engine.Shoe(cards, position=0, cut_at=10 ** 9, decks=rules["decks"], rng=rng)


def _room(shoe):
    """Whether a round can be dealt without running the shoe dry."""
    return shoe.left > 70


# ------------------------------------------------------------ the engine


def _random_rounds(rules, seed, rounds=60):
    rng = random.Random(seed)
    shoe = _shoe(rules, rng)
    cards = list(shoe.cards)
    recorded, expected = [], []
    for _ in range(rounds):
        if not _room(shoe):
            break
        bet = rng.choice([5, 10, 15, 25, 50, 100, 500])
        budget = bet * rng.choice([1, 2, 3, 5, 100])
        state = engine.start(shoe, bet, rules)
        take = False
        if state["phase"] == "insurance":
            take = rng.random() < 0.5 and budget - engine.staked(state) >= bet // 2
            engine.decide_insurance(state, shoe, rules, take)
        actions = []
        while state["phase"] == "player":
            chips = budget - engine.staked(state)
            action = rng.choice(engine.legal(state, rules, chips))
            actions.append(action)
            engine.act(state, shoe, rules, action, chips)
        recorded.append({"bet": bet, "budget": budget, "insurance": take, "actions": actions})
        expected.append({
            "net": engine.net(state),
            "dealer": state["dealer"],
            "hands": [
                {"cards": h["cards"], "bet": h["bet"], "result": h["result"], "net": h["net"]}
                for h in state["hands"]
            ],
        })
    return {"rules": rules, "cards": cards, "rounds": recorded}, expected


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: ",".join(f"{k}={v}" for k, v in v.items()) or "default")
def test_the_javascript_engine_matches_the_python_engine_to_the_chip(variant):
    """T-F-B.12.1-1: random but legal play, every rule combination."""
    rules = _rules(variant)
    scenarios, expected = [], []
    for seed in range(40):
        scenario, outcome = _random_rounds(rules, seed)
        scenarios.append(scenario)
        expected.append(outcome)
    got = _node("parity.js", {"mode": "engine", "scenarios": scenarios})
    played = sum(len(e) for e in expected)
    assert played > 800
    assert got == expected


def test_the_random_play_actually_reaches_the_hard_cases():
    """T-F-B.12.1-2: a parity test that never splits proves nothing."""
    seen = {"split": 0, "double": 0, "blackjack": 0, "insurance": 0, "bust": 0}
    rules = _rules({"resplit_aces": True, "hit_split_aces": True})
    for seed in range(40):
        scenario, outcome = _random_rounds(rules, seed)
        for played, result in zip(scenario["rounds"], outcome):
            seen["split"] += len(result["hands"]) > 1
            seen["double"] += "D" in played["actions"]
            seen["blackjack"] += any(h["result"] == "blackjack" for h in result["hands"])
            seen["insurance"] += played["insurance"]
            seen["bust"] += any(h["result"] == "lose" and len(h["cards"]) > 2 for h in result["hands"])
    assert all(count > 5 for count in seen.values()), seen


# ------------------------------------------------------------ the chart player


def _reference_action(state, rules, chips, overrides):
    """What the chart says to do, asked of `strategy` directly and written
    separately from the JavaScript glue so the two can disagree."""
    allowed = engine.legal(state, rules, chips)
    hit = "H" if "H" in allowed else "S"
    spot = engine.situation(state, rules, chips)
    if spot is None:
        return hit
    kind, player = spot
    up = engine.value(state["dealer"][0])
    action, fallback, _why = strategy.decide(kind, player, up, rules)
    wanted = overrides.get(f"{kind}|{player}|{up}", action)
    if wanted in allowed:
        return wanted
    return fallback if fallback in allowed else hit


def _chart_play(rules, seed, overrides, rounds=80):
    rng = random.Random(seed)
    shoe = _shoe(rules, rng)
    cards = list(shoe.cards)
    recorded, nets = [], []
    for _ in range(rounds):
        if not _room(shoe):
            break
        bet = rng.choice([15, 50, 150, 500])
        budget = bet * rng.choice([1, 2, 4, 100])
        state = engine.start(shoe, bet, rules)
        if state["phase"] == "insurance":
            engine.decide_insurance(state, shoe, rules, False)
        while state["phase"] == "player":
            chips = budget - engine.staked(state)
            engine.act(state, shoe, rules, _reference_action(state, rules, chips, overrides), chips)
        recorded.append({"bet": bet, "budget": budget})
        nets.append(engine.net(state))
    return {"rules": rules, "cards": cards, "rounds": recorded, "overrides": overrides}, nets


def _cells(rules):
    return [[k, p, d, a, f] for (k, p, d, a, f, _r) in strategy.every_cell(rules)]


CHART_VARIANTS = [{}, {"dealer_hits_soft_17": True}, {"decks": 4}, {"double_after_split": False},
                  {"max_splits": 2}, {"blackjack_pays": "6:5"}]


@pytest.mark.parametrize("variant", CHART_VARIANTS, ids=lambda v: ",".join(f"{k}={x}" for k, x in v.items()) or "default")
def test_the_chart_player_agrees_with_the_charts_own_answers(variant):
    """T-F-B.12.1-3: the table the browser is sent, and the glue that reads it
    (the pair rule, the fallback, the hand the chart has no cell for), play the
    same rounds as `strategy.decide` asked directly."""
    rules = _rules(variant)
    scenarios, expected = [], []
    for seed in range(40):
        scenario, nets = _chart_play(rules, seed, {})
        scenario["cellsKey"] = "c"
        scenarios.append(scenario)
        expected.append(nets)
    got = _node("parity.js", {"mode": "chart", "scenarios": scenarios, "cells": {"c": _cells(rules)}})
    assert [[r["net"] for r in run if "net" in r] for run in got] == expected


def test_chart_changes_play_the_same_way_in_both():
    """T-F-B.12.1-4: REQ-B.11.3. Overrides, including ones the table forbids."""
    rules = _rules({})
    overrides = {}
    for dealer in range(2, 12):
        overrides[f"pair|8|{dealer}"] = "H"        # never split eights
        overrides[f"hard|16|{dealer}"] = "P"       # a split that can never happen
        overrides[f"soft|18|{dealer}"] = "D"
    scenarios, expected = [], []
    for seed in range(40):
        scenario, nets = _chart_play(rules, seed, overrides)
        scenario["cellsKey"] = "c"
        scenarios.append(scenario)
        expected.append(nets)
    got = _node("parity.js", {"mode": "chart", "scenarios": scenarios, "cells": {"c": _cells(rules)}})
    assert [[r["net"] for r in run if "net" in r] for run in got] == expected
    assert any(run[-1]["fallbacks"] > 0 for run in got), "the forbidden override was never counted"


def test_an_override_really_changes_the_money():
    """T-F-B.12.1-5: the previous test would pass if overrides did nothing."""
    rules = _rules({})
    never_split_eights = {f"pair|8|{d}": "H" for d in range(2, 12)}
    plain, changed = [], []
    for seed in range(60):
        plain.append(sum(_chart_play(rules, seed, {})[1]))
        changed.append(sum(_chart_play(rules, seed, never_split_eights)[1]))
    assert plain != changed


# ------------------------------------------------------------ the rules of the policy


def _cases():
    done = subprocess.run(["node", str(HERE / "cases.js"), "--list"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.split()


@pytest.fixture(scope="module")
def chart_file(tmp_path_factory):
    rules = _rules({})
    path = tmp_path_factory.mktemp("lab") / "chart.json"
    path.write_text(json.dumps({"rules": rules, "cells": _cells(rules)}), encoding="utf-8")
    return path


@pytest.mark.parametrize("case", _cases() if shutil.which("node") else [])
def test_the_policy_and_the_runner_keep_their_promises(case, chart_file):
    """T-F-B.12.1-6: REQ-B.11.8, B.11.12 to B.11.19, one named case each."""
    done = subprocess.run(
        ["node", str(HERE / "cases.js"), case, str(chart_file)],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert done.returncode == 0, done.stderr[-1500:]


def test_there_are_policy_cases_at_all():
    assert len(_cases()) >= 25


# ------------------------------------------------------------ how fast


def test_a_hundred_thousand_hands_is_a_matter_of_a_second_or_two(chart_file):
    """T-F-B.12.1-7: REQ-B.11.10. The reason the lab runs in the browser is that
    the work is small; this holds that claim to a number."""
    import time

    script = (
        "const L=require(" + json.dumps(str(HERE.parent.parent / "static/blackjack/lab/lab_core.js")) + ");"
        "const d=JSON.parse(require('fs').readFileSync(" + json.dumps(str(chart_file)) + ",'utf8'));"
        "const chart=L.makeChart(d.cells);"
        "const shoe=L.makeShoe(L.seededSource(1,0,6));"
        "for(let i=0;i<100000;i++){if(L.needsShuffle(shoe))L.shuffle(shoe);"
        "L.playRound(shoe,15,d.rules,1e9,chart,{},{overrideFallbacks:0});}"
    )
    began = time.time()
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert time.time() - began < 10
