"""SPR-B.1.3 — the chart: every correct play, and why.

**The load-bearing test is `test_the_cells_that_strategy_charts_are_judged_on`.**
Everything else in this product is scaffolding around being right. A trainer
whose chart is subtly wrong is worse than no trainer, because the learner
cannot tell which hands they were taught badly, and they will carry it to a
real table. So the cells that experienced players use to check a chart are
asserted one by one, by hand, against values that do not come from this
codebase.

Second in weight is `test_seeding_twice_changes_nothing`. The methodology's
costliest recorded mistake was a seed command that deleted and recreated rows
on every deploy. This command checks first and says what it left alone.

Traces: REQ-B.2.5, B.3.4, B.3.5.
"""

import pytest

pytestmark = pytest.mark.sprb13


@pytest.fixture
def rules(db):
    from blackjack.models import RuleSet

    return RuleSet.default().rules


# ------------------------------------------------- the one that matters


def test_the_cells_that_strategy_charts_are_judged_on(rules):
    """Hand-checked cells, 6 decks, dealer stands on soft 17, DAS allowed.

    These are the lines players argue about and the ones a wrong chart gets
    wrong. They are written out rather than generated, because a generated
    expectation would be the same function checking itself.
    """
    from blackjack.strategy import decide

    cases = [
        # the famous counter-intuitive stands
        ("hard", 12, 2, "H"), ("hard", 12, 3, "H"), ("hard", 12, 4, "S"),
        ("hard", 16, 6, "S"), ("hard", 16, 7, "H"), ("hard", 16, 10, "H"),
        ("hard", 13, 2, "S"), ("hard", 17, 11, "S"),
        # doubles
        ("hard", 9, 2, "H"), ("hard", 9, 3, "D"), ("hard", 9, 7, "H"),
        ("hard", 10, 9, "D"), ("hard", 10, 10, "H"),
        ("hard", 11, 10, "D"), ("hard", 11, 11, "H"),   # S17: hit 11 vs ace
        # soft hands, where most charts go wrong
        ("soft", 18, 2, "S"), ("soft", 18, 3, "D"), ("soft", 18, 6, "D"),
        ("soft", 18, 7, "S"), ("soft", 18, 8, "S"), ("soft", 18, 9, "H"),
        ("soft", 18, 10, "H"), ("soft", 18, 11, "H"),
        ("soft", 13, 5, "D"), ("soft", 13, 4, "H"),
        ("soft", 15, 4, "D"), ("soft", 17, 3, "D"), ("soft", 17, 2, "H"),
        ("soft", 19, 6, "S"),                           # S17: no double
        ("soft", 20, 6, "S"),
        # pairs
        ("pair", 11, 10, "P"), ("pair", 8, 10, "P"),
        ("pair", 10, 6, "S"), ("pair", 5, 6, "D"), ("pair", 5, 10, "H"),
        ("pair", 9, 7, "S"), ("pair", 9, 6, "P"), ("pair", 9, 11, "S"),
        ("pair", 7, 7, "P"), ("pair", 7, 8, "H"),
        ("pair", 6, 2, "P"), ("pair", 4, 5, "P"), ("pair", 4, 4, "H"),
        ("pair", 3, 2, "P"), ("pair", 2, 8, "H"),
    ]

    wrong = []
    for kind, player, dealer, expected in cases:
        action, _fallback, _reason = decide(kind, player, dealer, rules)
        if action != expected:
            wrong.append(f"{kind} {player} vs {dealer}: expected {expected}, got {action}")
    assert not wrong, "the chart is wrong:\n" + "\n".join(wrong)


def test_the_h17_differences_are_real(db):
    """A chart that ignores dealer-hits-soft-17 is the single most common way
    to be confidently wrong. These three cells are where it shows."""
    from blackjack.models import RuleSet
    from blackjack.strategy import decide

    h17 = RuleSet.for_rules(dealer_hits_soft_17=True).rules
    s17 = RuleSet.default().rules

    assert decide("hard", 11, 11, h17)[0] == "D"
    assert decide("hard", 11, 11, s17)[0] == "H"
    assert decide("soft", 19, 6, h17)[0] == "D"
    assert decide("soft", 19, 6, s17)[0] == "S"
    assert decide("soft", 18, 2, h17)[0] == "D"
    assert decide("soft", 18, 2, s17)[0] == "S"


# ------------------------------------------------- the D ambiguity


def test_double_falls_back_to_hitting_on_hard_and_standing_on_soft():
    """The reason `fallback` exists at all. Same letter on screen, opposite
    meaning when you cannot double, and the case arrives after a split."""
    from blackjack.models import DEFAULT_RULES
    from blackjack.strategy import decide

    rules = DEFAULT_RULES

    action, fallback, _ = decide("hard", 9, 4, rules)
    assert (action, fallback) == ("D", "H")

    action, fallback, _ = decide("soft", 18, 4, rules)
    assert (action, fallback) == ("D", "S"), (
        "soft 18 that cannot double must stand, not hit"
    )


# ------------------------------------------------- refusing rather than guessing


def test_an_unsupported_rule_set_is_refused_in_words(db):
    """REQ-B.2.5. A near-enough chart is how a trainer teaches a losing play."""
    from blackjack.models import RuleSet
    from blackjack.strategy import Unsupported, decide, supports

    single = RuleSet.for_rules(decks=1).rules
    ok, why = supports(single)
    assert ok is False and why, "single deck quietly got the multi-deck chart"
    with pytest.raises(Unsupported):
        decide("hard", 16, 10, single)

    with_surrender = RuleSet.for_rules(surrender="late").rules
    assert supports(with_surrender)[0] is False


# ------------------------------------------------- every cell, and the seeding


def test_a_chart_covers_every_decision_exactly_once(rules):
    from blackjack.strategy import every_cell

    cells = list(every_cell(rules))
    keys = {(kind, player, dealer) for kind, player, dealer, *_ in cells}
    assert len(keys) == len(cells), "a decision appears twice"
    assert len(cells) == 340, f"the chart has {len(cells)} cells"

    for _kind, _player, _dealer, action, fallback, reason in cells:
        assert action in ("H", "S", "D", "P")
        assert fallback in ("H", "S", "D", "P")
        assert reason.strip(), "a cell has no explanation"


def test_seeding_twice_changes_nothing(db):
    """The methodology's costliest recorded mistake, held by a test that calls
    the real command twice rather than a fixture standing in for it."""
    from io import StringIO

    from django.core.management import call_command

    from blackjack.models import Cell

    call_command("seed_blackjack_chart", stdout=StringIO())
    first = list(Cell.objects.values_list("pk", "action").order_by("pk"))
    assert first, "nothing was seeded"

    out = StringIO()
    call_command("seed_blackjack_chart", stdout=out)
    assert "left alone" in out.getvalue()

    second = list(Cell.objects.values_list("pk", "action").order_by("pk"))
    assert second == first, "the second run rewrote rows it should have left"


def test_seeding_refuses_rules_it_cannot_chart(db):
    from io import StringIO

    from django.core.management import call_command

    from blackjack.models import Cell, Chart

    err = StringIO()
    call_command("seed_blackjack_chart", decks=1, stderr=err, stdout=StringIO())
    assert "no chart" in err.getvalue()
    assert not Cell.objects.exists(), "cells were written for an unsupported table"

    # And no empty chart either, which the first version of this test missed.
    # An empty chart is worse than no chart: the screen would find one, render
    # nothing, and look broken instead of saying this table is not supported.
    assert not Chart.objects.exists(), "an empty chart was left behind"


def test_the_stored_chart_says_what_the_strategy_module_says(db):
    """REQ-B.3.5's foundation: the rows and the function cannot disagree.

    The screen and the drill both read rows, so this is the test that makes
    the promise on the front page true rather than hopeful.
    """
    from io import StringIO

    from django.core.management import call_command

    from blackjack.models import Chart, RuleSet
    from blackjack.strategy import decide

    call_command("seed_blackjack_chart", stdout=StringIO())
    chart = Chart.objects.get(rule_set=RuleSet.default())
    rules = chart.rule_set.rules

    wrong = []
    for cell in chart.cells.all():
        action, fallback, reason = decide(cell.kind, cell.player, cell.dealer, rules)
        if (cell.action, cell.fallback, cell.reason) != (action, fallback, reason):
            wrong.append(f"{cell}: stored {cell.action}, computed {action}")
    assert not wrong, "stored chart disagrees with the strategy module:\n" + "\n".join(wrong[:10])
