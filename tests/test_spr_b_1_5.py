"""SPR-B.1.5 — the API, and the three verbs it refuses.

**The load-bearing test is `test_nobody_can_write_a_correct_play`.** Everything
this product sells rests on one claim: the answer it gives is right, and it is
the same answer everywhere. A writable chart cell would be a second source of
truth for that answer, reachable by anybody with a session, and the person who
discovers the disagreement is a learner who has already been taught the wrong
play. So the refusal is absolute, including for root, and it is swept rather
than spot-checked.

Second: `test_every_model_has_an_endpoint`. Methodology Rule 6. The same guard
in מט״צים caught two models with screens and no API, which is why it exists
here from the first API sprint rather than after somebody notices.

Traces: REQ-B.10.6, REQ-B.2.3, REQ-B.6.1.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb15

API = "/blackjack/api/"
PASSWORD = "sprb15-pass-6640"


@pytest.fixture
def world(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    me = User.objects.create_user(username="me@example.com", email="me@example.com",
                                  password=PASSWORD)
    them = User.objects.create_user(username="them@example.com", email="them@example.com",
                                    password=PASSWORD)
    root = User.objects.create_superuser(username="root@example.com",
                                         email="root@example.com", password=PASSWORD)
    from blackjack.models import Player

    return {"me": me, "them": them, "root": root,
            "mine": Player.for_user(me), "theirs": Player.for_user(them)}


# ------------------------------------------------- the one that matters


def test_nobody_can_write_a_correct_play(client, world):
    """Cells are read-only to everyone, root included.

    Swept across every verb rather than spot-checked, because the one that is
    open will be the one nobody wrote a case for.
    """
    from blackjack.models import Cell

    cell = Cell.objects.filter(kind="hard", player=16, dealer=10).first()
    assert cell and cell.action == "H"

    for who in ("me", "root"):
        client.force_login(world[who])

        created = client.post(f"{API}cells/", {
            "chart": cell.chart_id, "kind": "hard", "player": 16,
            "dealer": 10, "action": "S", "fallback": "S", "reason": "nonsense",
        }, content_type="application/json")
        assert created.status_code in (403, 405), f"{who} could create a cell"

        for verb, send in (("put", client.put), ("patch", client.patch)):
            answer = send(f"{API}cells/{cell.pk}/", {"action": "S"},
                          content_type="application/json")
            assert answer.status_code in (403, 405), f"{who} could {verb} a cell"

        gone = client.delete(f"{API}cells/{cell.pk}/")
        assert gone.status_code in (403, 405), f"{who} could delete a cell"

    cell.refresh_from_db()
    assert cell.action == "H", "the correct play was rewritten through the API"


def test_every_model_has_an_endpoint(db):
    """Rule 6, as a guard rather than a promise. The same test in מט״צים found
    two models with screens and no API."""
    from django.apps import apps

    from blackjack.api import ROUTES

    wired = {model for _prefix, _viewset, model in ROUTES}
    declared = set(apps.get_app_config("blackjack").get_models())
    missing = {m.__name__ for m in declared - wired}
    assert not missing, f"models with no REST endpoint: {sorted(missing)}"


# ------------------------------------------------- the other two refusals


def test_a_rule_set_is_never_edited_in_place(client, world):
    """REQ-B.2.3 through the API, which is the door the screens do not use and
    therefore the one nobody checks."""
    from blackjack.models import RuleSet

    table = world["mine"].rule_set
    client.force_login(world["me"])

    for send in (client.put, client.patch):
        answer = send(f"{API}rule-sets/{table.pk}/", {"decks": 8},
                      content_type="application/json")
        assert answer.status_code == 405, answer.content[:200]

    table.refresh_from_db()
    assert table.decks == 6

    gone = client.delete(f"{API}rule-sets/{table.pk}/")
    assert gone.status_code == 405
    assert RuleSet.objects.filter(pk=table.pk).exists()


def test_asking_for_a_table_somebody_already_plays_returns_that_one(client, world):
    """`for_rules` is the one door, so the API cannot fill the table with
    duplicates of the same rules."""
    from blackjack.models import RuleSet

    before = RuleSet.objects.count()
    client.force_login(world["me"])

    body = {"decks": 6, "dealer_hits_soft_17": False, "double_any_two": True,
            "double_after_split": True, "max_splits": 4, "resplit_aces": False,
            "hit_split_aces": False, "surrender": "none",
            "blackjack_pays": "3:2", "dealer_peeks": True}
    answer = client.post(f"{API}rule-sets/", body, content_type="application/json")

    assert answer.status_code in (200, 201), answer.content[:200]
    assert RuleSet.objects.count() == before, "a duplicate table was created"
    assert answer.json()["id"] == world["mine"].rule_set_id


# ------------------------------------------------- whose row is whose


def test_a_player_sees_only_their_own_row(client, world):
    client.force_login(world["me"])
    rows = client.get(f"{API}players/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [row["id"] for row in rows] == [world["mine"].pk]


def test_a_player_cannot_change_somebody_elses_table(client, world):
    from blackjack.models import Player

    client.force_login(world["me"])
    answer = client.patch(f"{API}players/{world['theirs'].pk}/",
                          {"rule_set": world["mine"].rule_set_id},
                          content_type="application/json")
    assert answer.status_code in (403, 404)
    assert Player.objects.get(pk=world["theirs"].pk).rule_set_id == world["theirs"].rule_set_id


def test_the_trial_clock_cannot_be_set_by_a_client(client, world):
    """`first_used_at` starts somebody's thirty minutes. A client that could
    write it could hand itself a fresh half hour whenever it liked."""
    from django.utils import timezone

    from blackjack.models import Player

    client.force_login(world["me"])
    client.patch(f"{API}players/{world['mine'].pk}/",
                 {"first_used_at": timezone.now().isoformat()},
                 content_type="application/json")
    assert Player.objects.get(pk=world["mine"].pk).first_used_at is None


def test_a_player_row_cannot_be_created_or_deleted_through_the_api(client, world):
    from blackjack.models import Player

    client.force_login(world["me"])
    made = client.post(f"{API}players/", {"rule_set": world["mine"].rule_set_id},
                       content_type="application/json")
    assert made.status_code in (403, 405)

    gone = client.delete(f"{API}players/{world['mine'].pk}/")
    assert gone.status_code in (403, 405)
    assert Player.objects.filter(pk=world["mine"].pk).exists()


# ------------------------------------------------- the floor


def test_no_endpoint_answers_a_stranger(client, db):
    """REQ-B.6.1: there is no anonymous product, so there is no anonymous API.

    Swept from the routes rather than listed, so an endpoint added later is
    covered without anybody remembering to add it here.
    """
    from blackjack.api import ROUTES

    open_to_all = []
    for prefix, _viewset, _model in ROUTES:
        if client.get(f"{API}{prefix}/").status_code == 200:
            open_to_all.append(prefix)
    assert not open_to_all, f"open to anonymous clients: {open_to_all}"
