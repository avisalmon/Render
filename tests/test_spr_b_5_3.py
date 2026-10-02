"""SPR-B.5.3 — the deeper explanation of one cell.

**The load-bearing test is `test_the_correct_action_is_handed_in_never_looked_up`.**
This is the same promise as the whole product, defended at a new door. The
coach explains a decision it is *told*; the view reads the chart row and passes
it in. Keeping the lookup out of the coach means that even if somebody later
rewrites its prompt badly, it still cannot invent a play: it has no way to know
one.

Second: `test_a_free_account_asking_for_an_explanation_gets_json_not_a_page`.
The drill never reloads, so a free account hitting this gets a refusal it can
render inline rather than an HTML page it would have to ignore.

Traces: REQ-B.8.3, B.8.5, B.8.6, B.6.6.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb53

URL = "/blackjack/advanced/explain/"
PASSWORD = "sprb53-pass-5529"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="deep@example.com", email="deep@example.com", password=PASSWORD
    )


def _pay(user):
    from app.models import Entitlement

    Entitlement.objects.update_or_create(user=user, defaults={"tier": "base"})


def _ask(client, kind="hard", value=16, dealer=10):
    return client.post(URL, {"kind": kind, "player": value, "dealer": dealer},
                       HTTP_ACCEPT="application/json")


# ------------------------------------------------- the one that matters


def test_the_correct_action_is_handed_in_never_looked_up(person, db):
    """The coach is given the play and cannot find one on its own.

    Checked by calling it with a deliberately invented action and asserting
    that is what reaches the prompt. If the coach ever looked the cell up
    itself, it would override what it was handed and this would fail.
    """
    import pathlib
    from unittest.mock import patch

    from blackjack import coach
    from blackjack.models import Player

    _pay(person)
    player = Player.for_user(person)

    with patch("app.ai_chat.call_openai") as fake:
        fake.return_value = {"content": "ok", "prompt_tokens": 1,
                             "completion_tokens": 1, "model": "stub"}
        coach.explain(person, player, {
            "hand": "16 מול 10", "action": "P", "fallback": "P",
            "reason": "סיבה כלשהי", "seen": 3, "correct": 1,
        })
        sent = fake.call_args[0][0][0]["content"]

    assert "לפצל" in sent, "the action the caller handed in did not reach the prompt"

    source = pathlib.Path("blackjack/coach.py").read_text(encoding="utf-8")
    assert "from .strategy" not in source and "import strategy" not in source
    assert "Chart" not in source, "the coach can reach the chart"


def test_a_free_account_asking_for_an_explanation_gets_json_not_a_page(client, person):
    """The drill never reloads, so a refusal has to be something it can render
    inline. Same gate, same 402, different body."""
    import json

    client.force_login(person)
    response = _ask(client)

    assert response.status_code == 402
    assert response["Content-Type"].startswith("application/json")
    body = json.loads(response.content)
    assert body["refused"]
    assert "<html" not in response.content.decode()


def test_the_screen_refusal_is_still_a_page(client, person):
    """The other half of the same decorator: a person who clicked a link still
    gets something to read."""
    client.force_login(person)
    response = client.get("/blackjack/advanced/")
    assert response.status_code == 402
    assert "text/html" in response["Content-Type"]


# ------------------------------------------------- what it answers


def test_a_paying_person_gets_an_explanation(client, person):
    import json

    _pay(person)
    client.force_login(person)
    response = _ask(client)

    assert response.status_code == 200
    assert json.loads(response.content)["text"].strip()


def test_a_cell_that_is_not_in_the_chart_is_refused(client, person):
    _pay(person)
    client.force_login(person)

    assert _ask(client, "hard", 99, 10).status_code == 400
    assert _ask(client, "nonsense", 16, 10).status_code == 400
    assert client.post(URL, {}, HTTP_ACCEPT="application/json").status_code == 400


def test_the_explanation_is_logged_like_every_other_call(client, person):
    from app.models import UsageLog

    _pay(person)
    client.force_login(person)
    before = UsageLog.objects.count()

    _ask(client)
    assert UsageLog.objects.count() == before + 1, "an explanation was not logged"


def test_the_cap_stops_an_explanation_too(client, person, settings):
    from app.models import UsageLog

    _pay(person)
    client.force_login(person)
    settings.OPENAI_MONTHLY_COST_CAP_USD = 0.0

    before = UsageLog.objects.count()
    response = _ask(client)

    assert response.status_code == 402
    assert UsageLog.objects.count() == before


# ------------------------------------------------- the button


def test_the_button_is_only_rendered_for_somebody_paying():
    """An explanation offered and then refused is worse than one never
    offered: it teaches that the app advertises what it will not give."""
    import pathlib

    source = pathlib.Path("static/blackjack/drill_screen.js").read_text(encoding="utf-8")
    assert "if (chart.adaptive)" in source, "the button is not behind the paid flag"


def test_the_rules_engine_still_calls_nothing(client, person):
    """REQ-B.4.5 survives this sprint. The drill answers instantly and offline;
    only the optional explanation touches the network, after the answer and
    behind a press."""
    import pathlib

    rules = pathlib.Path("static/blackjack/drill.js").read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon"):
        assert forbidden not in rules, f"the rules engine calls out: {forbidden}"
