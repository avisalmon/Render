"""SPR-B.3.1 — mastery per decision, and the rebuild that keeps it honest.

**The load-bearing test is `test_mastery_can_be_thrown_away_and_rebuilt_exactly`.**
This app claims `Attempt` is the only truth and everything else is a view over
it. Mastery is the first thing that could make that a lie, because it holds
state nothing else does. The test deletes every mastery row, replays the
attempts, and compares field by field. If that ever fails, the claim at the top
of the data model is false and the numbers shown to a learner cannot be
reconstructed or defended.

Second: `test_a_miss_brings_the_cell_back_and_a_run_pushes_it_away`, which is
the whole mechanism behind the only piece of real learning science in this
field.

Traces: REQ-B.5.2, B.5.7.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb31

API = "/blackjack/api/attempts/"
PASSWORD = "sprb31-pass-2205"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="mastery@example.com", email="mastery@example.com", password=PASSWORD
    )


def _play(client, kind="hard", player=16, dealer=10, right=True):
    """Play one hand, correctly or not, through the real endpoint."""
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=player, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    return client.post(API, {
        "cell_kind": kind, "cell_player": player, "cell_dealer": dealer,
        "chosen": chosen, "player_cards": [10, 6], "answer_ms": 900,
        "source": "random",
    }, content_type="application/json")


# ------------------------------------------------- the one that matters


def test_mastery_can_be_thrown_away_and_rebuilt_exactly(client, person):
    """Field by field, not row-count by row-count.

    The data model says `Attempt` is the only truth. This is where that is
    either true or a sentence somebody wrote once.
    """
    from blackjack.mastery import rebuild
    from blackjack.models import Mastery, Player

    client.force_login(person)
    for kind, value, dealer, right in [
        ("hard", 16, 10, False), ("hard", 16, 10, True), ("hard", 16, 10, True),
        ("soft", 18, 3, True), ("soft", 18, 9, False), ("pair", 8, 10, True),
        ("hard", 12, 4, False), ("hard", 12, 4, False), ("soft", 18, 3, True),
    ]:
        assert _play(client, kind, value, dealer, right).status_code == 201

    player = Player.for_user(person)
    fields = ["cell_kind", "cell_player", "cell_dealer", "seen", "correct",
              "streak", "last_seen_at", "due_at", "strength"]
    before = sorted(Mastery.objects.filter(player=player).values_list(*fields))
    assert before

    Mastery.objects.filter(player=player).delete()
    rebuild(player)

    after = sorted(Mastery.objects.filter(player=player).values_list(*fields))
    assert after == before, "a rebuilt mastery row differs from the one live play produced"


def test_the_rebuild_command_runs_over_everybody(client, person, db):
    from blackjack.mastery import rebuild  # noqa: F401  (the command's own import)
    from blackjack.models import Mastery, Player

    client.force_login(person)
    _play(client)
    player = Player.for_user(person)
    Mastery.objects.filter(player=player).delete()

    out = StringIO()
    call_command("rebuild_blackjack_mastery", stdout=out)
    assert Mastery.objects.filter(player=player).exists()
    assert "rebuilt" in out.getvalue()


# ------------------------------------------------- the schedule


def test_a_miss_brings_the_cell_back_and_a_run_pushes_it_away(client, person):
    """The mechanism behind spaced repetition, which is the only piece of real
    learning science in this field: wrong answers return sooner, right ones
    recede."""
    from blackjack.models import Mastery, Player

    client.force_login(person)
    player = Player.for_user(person)

    _play(client, right=False)
    missed = Mastery.objects.get(player=player, cell_kind="hard", cell_player=16)
    assert missed.streak == 0
    assert missed.strength == 1.0
    assert missed.due_at == missed.last_seen_at, "a missed cell is not due immediately"

    for _ in range(3):
        _play(client, right=True)
    known = Mastery.objects.get(player=player, cell_kind="hard", cell_player=16)
    assert known.streak == 3
    assert known.strength > missed.strength
    assert known.due_at > known.last_seen_at, "a known cell is still due immediately"


def test_one_miss_collapses_a_long_run(client, person):
    """A nudge would be wrong. Somebody who has just got a cell wrong should
    meet it again in this sitting, not next week."""
    from blackjack.models import Mastery, Player

    client.force_login(person)
    for _ in range(5):
        _play(client, right=True)
    player = Player.for_user(person)
    strong = Mastery.objects.get(player=player, cell_kind="hard", cell_player=16)
    assert strong.strength > 2

    _play(client, right=False)
    now = Mastery.objects.get(player=player, cell_kind="hard", cell_player=16)
    assert now.strength == 1.0
    assert now.streak == 0
    assert now.due_at == now.last_seen_at


# ------------------------------------------------- what a person is told


def test_the_grid_counts_every_decision_including_the_untouched(client, person):
    """REQ-B.5.2. "You have not met this yet" is information, and an absence is
    not: a grid that only shows what somebody has played cannot tell them what
    is left."""
    from blackjack.mastery import grid
    from blackjack.models import Cell, Chart, Player

    client.force_login(person)
    _play(client)

    player = Player.for_user(person)
    rows = grid(player)
    chart = Chart.objects.get(rule_set=player.rule_set)

    assert len(rows) == Cell.objects.filter(chart=chart).count() == 340
    assert len([r for r in rows if r["state"] == "new"]) == 339


def test_the_summary_names_the_cells_that_cost_the_most(client, person):
    """The complaint competitors get, answered: a person cannot tell which
    hands are their weak ones."""
    from blackjack.mastery import summary
    from blackjack.models import Player

    client.force_login(person)
    for _ in range(4):
        _play(client, "hard", 12, 4, right=False)
    for _ in range(4):
        _play(client, "soft", 18, 9, right=True)

    found = summary(Player.for_user(person))
    assert found["total"] == 340
    assert found["solid"] >= 1
    assert found["worst"], "nothing was named as weak after four straight misses"
    worst = found["worst"][0]["cell"]
    assert (worst.kind, worst.player, worst.dealer) == ("hard", 12, 4)


def test_a_cell_is_only_solid_after_a_run(client, person):
    """One lucky answer is not knowledge. Three in a row is the line, and it is
    arbitrary, which is why it is in one function rather than scattered."""
    from blackjack.mastery import state_of

    assert state_of(0, 0, 0) == "new"
    assert state_of(1, 1, 1) == "learning"
    assert state_of(4, 2, 0) == "shaky"
    assert state_of(3, 3, 3) == "solid"
