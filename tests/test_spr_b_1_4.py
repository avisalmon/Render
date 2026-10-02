"""SPR-B.1.4 — the cheat sheet, which is the chart made visible.

**The load-bearing test is `test_every_letter_on_screen_is_the_row_behind_it`.**
This is REQ-B.3.5 and the promise in spec 1.5, and it is the one claim this
product makes that competitors cannot: users of other trainers report the drill
disagreeing with the app's own strategy card. Here the screen renders rows and
the drill will serialise the same rows, so the two cannot drift. A test that
reads the rendered HTML back and compares it to the database is what turns that
from an architecture diagram into a fact.

Second: `test_a_table_with_no_chart_says_so_instead_of_drawing_nothing`. An
empty grid looks like a bug. A sentence looks like an answer.

Traces: REQ-B.3.1 to B.3.5, REQ-B.2.5.
"""

import re

import pytest

pytestmark = pytest.mark.sprb14

PASSWORD = "sprb14-pass-5517"


@pytest.fixture
def person(db):
    from io import StringIO

    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="sheet@example.com", email="sheet@example.com", password=PASSWORD
    )


def _cells_on_screen(html):
    """Every rendered cell, as (hand label, dealer, action)."""
    found = []
    for tag in re.findall(r"<button[^>]*class=\"bj-cell[^\"]*\"[^>]*>", html):
        action = re.search(r'data-action="([^"]+)"', tag)
        hand = re.search(r'data-hand="([^"]+)"', tag)
        dealer = re.search(r'data-dealer="([^"]+)"', tag)
        if action and hand and dealer:
            found.append((hand.group(1), dealer.group(1), action.group(1)))
    return found


# ------------------------------------------------- the one that matters


def test_every_letter_on_screen_is_the_row_behind_it(client, person):
    """Read the rendered sheet back and compare it, cell by cell, to the rows.

    Not a spot check: every cell on every view, because the one that drifts
    will be the one nobody thought to check.
    """
    from blackjack.models import Cell, Chart, Player

    client.force_login(person)
    chart = Chart.objects.get(rule_set=Player.for_user(person).rule_set)

    def label(cell):
        if cell.kind == "pair":
            return "A,A" if cell.player == 11 else f"{cell.player},{cell.player}"
        if cell.kind == "soft":
            return f"A,{cell.player - 11}"
        return str(cell.player)

    checked = 0
    for view in ("weak", "strong", "soft", "pairs", "doubles"):
        html = client.get(f"/blackjack/sheet/?view={view}").content.decode()
        on_screen = _cells_on_screen(html)
        assert on_screen, f"the {view} view rendered no cells"

        for hand, dealer, action in on_screen:
            dealer_value = 11 if dealer == "A" else int(dealer)
            rows = [
                c for c in Cell.objects.filter(chart=chart, dealer=dealer_value)
                if label(c) == hand and c.action == action
            ]
            assert rows, (
                f"{view}: the screen shows {hand} vs {dealer} = {action}, "
                f"which is not what the row says"
            )
            checked += 1

    assert checked > 200, f"only {checked} cells were actually compared"


def test_the_sheet_never_computes_a_play_of_its_own():
    """The structural half of the same promise. A view that decides anything
    is a second opinion waiting to drift from the first."""
    import pathlib

    source = pathlib.Path("blackjack/views.py").read_text(encoding="utf-8")
    sheet = source[source.index("def sheet("):]
    sheet = sheet[: sheet.index("def _as_rows")]
    assert "decide(" not in sheet, "the sheet view computes a play instead of reading one"


# ------------------------------------------------- refusing rather than guessing


def test_a_table_with_no_chart_says_so_instead_of_drawing_nothing(client, person):
    """REQ-B.2.5 on screen. Single deck is a different chart, not this one with
    a smaller number on it."""
    from blackjack.models import Player

    player = Player.for_user(person)
    player.play_by(decks=1)

    client.force_login(person)
    response = client.get("/blackjack/sheet/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "<table" not in body, "an empty grid was drawn for a table we cannot chart"
    assert "4, 6" in body or "חפיסות" in body, "it does not say why"
    assert "/blackjack/table/" in body, "no way back to change the table"


# ------------------------------------------------- the splits


@pytest.mark.parametrize("view,expected_tables", [
    ("weak", 1),
    ("strong", 1),
    ("soft", 2),
    ("pairs", 2),
    ("doubles", 2),
])
def test_the_dealer_is_split_so_the_table_fits_a_hand(client, person, view, expected_tables):
    """REQ-B.3.3: five columns is a thumb, on every view.

    First written for the hard table alone, with soft and pairs allowed ten
    columns. The review pass of 2026-10-02 found those views clipped on a
    390px phone with the 8, 9, 10 and A columns off the edge behind a hidden
    scrollbar. So now every table on the sheet is at most five dealers wide,
    and a wide view arrives as two tables.
    """
    client.force_login(person)
    html = client.get(f"/blackjack/sheet/?view={view}").content.decode()
    headers = re.findall(r"<thead>.*?</thead>", html, re.S)
    assert len(headers) == expected_tables
    for header in headers:
        columns = len(re.findall(r"<th scope=\"col\">", header)) - 1  # minus the corner
        assert 1 <= columns <= 5, f"{view}: a table {columns} dealers wide"


def test_the_doubles_view_holds_only_doubles(client, person):
    """Avi asked for it by name, and the research says doubles are what
    beginners miss most."""
    client.force_login(person)
    html = client.get("/blackjack/sheet/?view=doubles").content.decode()
    actions = {action for _hand, _dealer, action in _cells_on_screen(html)}
    assert actions == {"D"}, f"the doubles sheet shows {actions}"


def test_an_invented_view_falls_back_rather_than_breaking(client, person):
    client.force_login(person)
    assert client.get("/blackjack/sheet/?view=nonsense").status_code == 200


# ------------------------------------------------- the reason is the product


def test_every_cell_carries_its_reason(client, person):
    """REQ-B.3.4. A reason a person cannot reach is a reason that does not
    exist, and the reason is what separates this from a picture of a chart."""
    client.force_login(person)
    html = client.get("/blackjack/sheet/?view=weak").content.decode()

    buttons = re.findall(r"<button[^>]*class=\"bj-cell[^\"]*\"[^>]*>", html)
    assert buttons
    without = [b for b in buttons if 'data-reason=""' in b or "data-reason" not in b]
    assert not without, f"{len(without)} cells have no explanation"


def test_a_stranger_sees_no_sheet(client, db):
    response = client.get("/blackjack/sheet/")
    assert response.status_code == 302
    assert "login" in response["Location"]
