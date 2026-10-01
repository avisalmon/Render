"""SPR-B.3.2 — the progress grid, which answers the complaint competitors get.

**The load-bearing test is `test_the_grid_shows_what_was_actually_played`.**
A progress screen that is merely plausible is worse than none: a learner reads
it, believes they are solid on sixteen against ten, and walks into a casino. So
every coloured cell is checked against the mastery rows behind it rather than
spot-checked for a sensible-looking picture.

Traces: REQ-B.5.2.
"""

import re
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb32

API = "/blackjack/api/attempts/"
PASSWORD = "sprb32-pass-7723"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="grid@example.com", email="grid@example.com", password=PASSWORD
    )


def _play(client, kind, value, dealer, right):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    return client.post(API, {
        "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
        "chosen": chosen, "player_cards": [10, 6], "answer_ms": 800, "source": "random",
    }, content_type="application/json")


def _tiles(html):
    """Every grid tile as (state, correct, seen), read from the table body only.

    The body only, because the legend carries the same state classes and a
    `title` attribute carries the same counts. The first version of this test
    matched those instead, so painting every cell solid still passed. A test
    that can be satisfied by the legend is testing the legend.
    """
    body = re.search(r"<tbody>.*?</tbody>", html, re.S).group(0)
    found = []
    for tag in re.finditer(
        r'class="bj-cell bj-state-(\w+)"\s+title="(\d+)/(\d+)">([^<]*)</span>', body
    ):
        state, correct, seen, shown = tag.group(1), int(tag.group(2)), int(tag.group(3)), tag.group(4).strip()
        # The number a person reads must be the number the tile claims. These
        # can drift, and a tile whose title is right and whose face is wrong is
        # worse than either: the screen lies and the tooltip tells the truth.
        expected = f"{correct}/{seen}" if seen else "·"
        assert shown == expected, f"tile shows {shown!r}, title says {correct}/{seen}"
        found.append((state, correct, seen))
    return found


def test_the_grid_shows_what_was_actually_played(client, person):
    """Every tile on the rendered grid, against the mastery row behind it.

    A progress screen that is merely plausible is worse than none: somebody
    reads it, believes they are solid on sixteen against ten, and walks into a
    casino with it.
    """
    from blackjack.mastery import state_of
    from blackjack.models import Mastery, Player

    client.force_login(person)
    for _ in range(4):
        _play(client, "hard", 16, 10, right=False)
    for _ in range(3):
        _play(client, "hard", 13, 5, right=True)
    _play(client, "hard", 12, 4, right=True)

    player = Player.for_user(person)
    rows = {(m.cell_kind, m.cell_player, m.cell_dealer): m
            for m in Mastery.objects.filter(player=player)}

    checked = 0
    for view, kind, dealers in (("strong", "hard", (7, 8, 9, 10, 11)),
                                ("weak", "hard", (2, 3, 4, 5, 6)),
                                ("soft", "soft", range(2, 12)),
                                ("pairs", "pair", range(2, 12))):
        html = client.get(f"/blackjack/progress/?view={view}").content.decode()
        tiles = _tiles(html)
        assert tiles, f"the {view} view rendered no tiles"

        # Every tile that claims to have been played must match a real row.
        for state, correct, seen in tiles:
            if seen == 0:
                assert state == "new", f"an unplayed cell is painted {state}"
                continue
            match = [m for m in rows.values()
                     if m.seen == seen and m.correct == correct
                     and m.cell_kind == kind and m.cell_dealer in dealers]
            assert match, f"{view}: a tile says {correct}/{seen}, no row does"
            assert state == state_of(seen, correct, match[0].streak), (
                f"{view}: tile painted {state} for {correct}/{seen}"
            )
            checked += 1

    assert checked >= 3, f"only {checked} played tiles were compared"


def test_the_summary_is_a_count_not_a_percentage(client, person):
    """A percentage is the number that hides which hands are weak, which is the
    exact complaint users make about the competition."""
    client.force_login(person)
    _play(client, "hard", 16, 10, right=False)

    html = client.get("/blackjack/progress/").content.decode()
    assert "340" in html, "the total number of decisions is not shown"
    assert not re.search(r"\d+(\.\d+)?%", html), "an overall percentage crept in"


def test_the_weakest_cells_are_named(client, person):
    client.force_login(person)
    for _ in range(5):
        _play(client, "soft", 18, 9, right=False)

    html = client.get("/blackjack/progress/").content.decode()
    assert "A,7" in html, "the worst cell is not named in a form a person reads"
    assert "0 מתוך 5" in html


def test_cells_never_met_are_shown_as_not_met(client, person):
    """An absence is not information. A grid that only shows played hands
    cannot tell somebody what is left."""
    client.force_login(person)
    html = client.get("/blackjack/progress/").content.decode()
    assert html.count("bj-state-new") >= 50
    assert "340" in html


def test_a_stranger_sees_no_progress(client, db):
    assert client.get("/blackjack/progress/").status_code == 302


def test_a_table_with_no_chart_says_so(client, person):
    from blackjack.models import Player

    Player.for_user(person).play_by(decks=1)
    client.force_login(person)
    body = client.get("/blackjack/progress/").content.decode()
    assert "<table" not in body
    assert "/blackjack/table/" in body
