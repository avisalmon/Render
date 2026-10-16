"""SPR-B.12.4 — the calculated chart, held to the published one.

REQ-B.11.26. A chart worked out in the browser is only worth offering if it can
be checked against something it did not come from. The published chart is that
something: for every rule set it covers, the calculated chart must pick the same
play in nearly every cell, and where it does not, the two plays must be nearly
tied in value. Then it is trusted for the tables the published chart does not
cover, and the tests below hold the plays anybody could check by eye.

Needs `node`; skipped, never passed, without it.
"""

import json
import pathlib
import shutil
import subprocess

import pytest

from blackjack import strategy
from blackjack.models import DEFAULT_RULES

pytestmark = [
    pytest.mark.sprblab,
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
]

HERE = pathlib.Path(__file__).parent / "lab_js"


def _node(payload):
    done = subprocess.run(
        ["node", str(HERE / "best.js")], input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", timeout=300,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _rules(**over):
    rules = dict(DEFAULT_RULES)
    rules.update(over)
    return rules


def _cells(rules):
    return [[k, p, d, a, f] for (k, p, d, a, f, _r) in strategy.every_cell(rules)]


COVERED = [
    {}, {"dealer_hits_soft_17": True}, {"decks": 4}, {"decks": 8},
    {"double_after_split": False}, {"max_splits": 2}, {"blackjack_pays": "6:5"},
    {"decks": 4, "dealer_hits_soft_17": True, "double_after_split": False},
    {"decks": 8, "dealer_hits_soft_17": True},
]


def test_the_calculated_chart_agrees_with_the_published_one():
    """T-F-B.12.4-1: REQ-B.11.26. Nearly every cell the same, and every
    difference a near tie."""
    sets = [{"rules": _rules(**v), "cells": _cells(_rules(**v))} for v in COVERED]
    results = _node({"task": "compare", "sets": sets})
    for variant, result in zip(COVERED, results):
        assert result["total"] == 340
        assert result["same"] >= 338, (variant, result["differ"])
        assert result["worst"] < 0.01, (variant, result["differ"])
        assert result["sameFallback"] >= result["comparable"] - 1, variant


def _plays(**over):
    return _node({"task": "chart", "rules": _rules(**over)})["plays"]


@pytest.mark.parametrize("decks", [1, 2, 3, 4, 5, 6, 7, 8])
def test_the_calculated_chart_plays_what_anyone_can_check_by_eye(decks):
    """T-F-B.12.4-2: every number of decks, including the ones with no
    published chart here."""
    plays = _plays(decks=decks)
    up = range(2, 12)
    assert all(plays[f"hard|{t}|{d}"] == "S" for t in range(17, 21) for d in up)
    assert all(plays[f"hard|{t}|{d}"] in ("H", "D") for t in range(5, 9) for d in up), "hit low totals (a single deck doubles 8 against a 5 or 6)"
    assert all(plays[f"hard|{t}|{d}"] == "H" for t in range(5, 8) for d in up if decks >= 4)
    assert all(plays[f"pair|11|{d}"] == "P" for d in up), "always split aces"
    assert all(plays[f"pair|8|{d}"] == "P" for d in range(2, 11)), "always split eights"
    assert all(plays[f"pair|10|{d}"] == "S" for d in up), "never split tens"
    assert all(plays[f"pair|5|{d}"] == "D" or plays[f"pair|5|{d}"] == "H" for d in up), "never split fives"
    assert all(plays[f"hard|11|{d}"] == "D" for d in range(2, 11)), "double eleven"
    assert plays["hard|16|10"] in ("H", "S") and plays["hard|12|6"] == "S"
    assert all(plays[f"soft|20|{d}"] == "S" for d in up)
    assert all(plays[f"soft|19|{d}"] == "S" for d in up if d != 6), "soft 19 stands (a few tables double it against a 6)"


def test_the_calculated_chart_covers_every_cell_the_game_asks_about():
    """T-F-B.12.4-3: nothing the engine can ask is left without an answer."""
    rules = _rules(decks=2)
    plays = _plays(decks=2)
    assert len(plays) == 340
    assert set(plays.values()) <= {"H", "S", "D", "P"}


def test_a_calculated_chart_beats_a_player_who_never_learned_it():
    """T-F-B.12.4-4: on an uncovered table (two decks), the calculated chart
    loses far less than standing on 12 and over, which is what the table is
    meant to be better than."""
    rules = _rules(decks=2)
    calc = _node({"task": "edge", "rules": rules, "source": "calculated", "rounds": 400000, "seed": 3})
    dumb = []
    for kind, lo, hi in (("hard", 5, 20), ("soft", 13, 20)):
        for player in range(lo, hi + 1):
            for dealer in range(2, 12):
                dumb.append([kind, player, dealer, "S" if player >= 12 else "H", "S" if player >= 12 else "H"])
    for rank in range(2, 12):
        for dealer in range(2, 12):
            dumb.append(["pair", rank, dealer, "S" if rank * 2 >= 12 else "H", "S" if rank * 2 >= 12 else "H"])
    naive = _node({"task": "edge", "rules": rules, "source": "given", "cells": dumb, "rounds": 400000, "seed": 3})
    assert calc["edge"] > naive["edge"] + 0.02, (calc, naive)
    assert calc["edge"] > -0.02, calc


def test_fewer_decks_are_worth_more_to_the_player():
    """T-F-B.12.4-5: a known fact about the game, as a check that the engine and
    the calculated chart together behave like blackjack."""
    edges = {}
    for decks in (1, 6):
        edges[decks] = _node({
            "task": "edge", "rules": _rules(decks=decks), "source": "calculated",
            "rounds": 800000, "seed": 11,
        })["edge"]
    assert edges[1] > edges[6], edges


def test_the_calculated_and_the_published_chart_play_to_the_same_edge():
    """T-F-B.12.4-6: same cells, same shuffles, same money, to the chip."""
    rules = _rules()
    published = _node({"task": "edge", "rules": rules, "source": "given", "cells": _cells(rules), "rounds": 200000, "seed": 5})
    calculated = _node({"task": "edge", "rules": rules, "source": "calculated", "rounds": 200000, "seed": 5})
    assert abs(published["edge"] - calculated["edge"]) < 0.002, (published, calculated)


def test_the_calculation_is_fast_enough_to_do_on_a_phone():
    """T-F-B.12.4-7: it runs every time a calculated run starts."""
    import time

    began = time.time()
    _plays(decks=1)
    assert time.time() - began < 5
