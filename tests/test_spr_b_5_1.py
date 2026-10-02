"""SPR-B.5.1 — adaptive drilling, which is the first thing people pay for.

**The load-bearing test is `test_a_free_account_is_never_handed_the_schedule`.**
The chart ships to the browser, so anything else put in that payload ships too.
The schedule is the paid feature; putting it in the page for everybody and
hiding it in JavaScript would be giving it away to anyone who opens the view
source, while the product claimed to sell it.

Second: `test_the_schedule_is_arithmetic_and_never_a_model`. REQ-B.8.2 says
adaptive selection is deterministic. A model choosing the next flashcard costs
money and latency on every hand to do worse than a sort by date, and the paid
budget is better spent on what only a model can do.

Traces: REQ-B.8.2, B.5.7, B.6.2.
"""

import os
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb51

PASSWORD = "sprb51-pass-3318"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="sched@example.com", email="sched@example.com", password=PASSWORD
    )


def _play(client, kind="hard", value=16, dealer=10, right=True):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    return client.post("/blackjack/api/attempts/", {
        "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
        "chosen": chosen, "player_cards": [10, 6], "answer_ms": 700, "source": "random",
    }, content_type="application/json")


def _payload(client):
    import json

    html = client.get("/blackjack/drill/").content.decode()
    start = html.index('id="bjChart"')
    return json.loads(html[html.index(">", start) + 1: html.index("</script>", start)])


def _pay(person):
    from app.models import Entitlement

    Entitlement.objects.update_or_create(user=person, defaults={"tier": "base"})


# ------------------------------------------------- the one that matters


def test_a_free_account_is_never_handed_the_schedule(client, person):
    """Anything in the payload ships to the browser. A paid feature hidden in
    JavaScript is a paid feature given away to anybody who views source."""
    from blackjack.models import Player

    client.force_login(person)
    _play(client, right=False)

    # Burn the trial first. Somebody who has just played a hand is *inside*
    # their thirty minutes and is not a free account at all, which the first
    # version of this test missed: it asserted the schedule was withheld from
    # an account that was legitimately paying-equivalent at that moment.
    player = Player.objects.get(user=person)
    player.first_used_at = timezone.now() - timedelta(minutes=31)
    player.save(update_fields=["first_used_at"])

    free = _payload(client)
    assert free["adaptive"] is False
    assert free["due"] == [], "the schedule was shipped to a free account"

    _pay(person)
    paid = _payload(client)
    assert paid["adaptive"] is True
    assert paid["due"], "a paying account was not given the schedule"


def test_the_schedule_is_arithmetic_and_never_a_model():
    """REQ-B.8.2. The paid budget goes on what only a model can do."""
    import pathlib

    source = pathlib.Path("blackjack/mastery.py").read_text(encoding="utf-8")
    due = source[source.index("def due_cells"):]
    for forbidden in ("openai", "ai_chat", "chat_completion", "prompt"):
        assert forbidden not in due.lower(), f"the scheduler calls {forbidden}"


# ------------------------------------------------- what the schedule says


def test_overdue_cells_come_first(client, person):
    """Somebody back after a week meets what they were about to forget before
    what they nearly know."""
    from blackjack.mastery import due_cells
    from blackjack.models import Mastery, Player

    client.force_login(person)
    for kind, value, dealer in (("hard", 16, 10), ("soft", 18, 9), ("pair", 8, 10)):
        _play(client, kind, value, dealer, right=False)

    player = Player.for_user(person)
    stale = Mastery.objects.get(player=player, cell_kind="soft")
    stale.due_at = timezone.now() - timedelta(days=9)
    stale.save(update_fields=["due_at"])

    order = due_cells(player)
    assert order[0] == {"kind": "soft", "player": 18, "dealer": 9}, order[:2]


def test_a_cell_not_yet_due_is_not_offered(client, person):
    from blackjack.mastery import due_cells
    from blackjack.models import Mastery, Player

    client.force_login(person)
    _play(client, right=True)

    player = Player.for_user(person)
    Mastery.objects.filter(player=player).update(due_at=timezone.now() + timedelta(days=1))
    assert due_cells(player) == []


def test_a_hand_the_schedule_chose_is_recorded_as_adaptive(client, person):
    """So the history can later say which practice was guided and which was
    not, and so the free and paid numbers are told apart."""
    from blackjack.models import Attempt

    client.force_login(person)
    response = client.post("/blackjack/api/attempts/", {
        "cell_kind": "hard", "cell_player": 16, "cell_dealer": 10,
        "chosen": "S", "player_cards": [10, 6], "answer_ms": 600, "source": "adaptive",
    }, content_type="application/json")
    assert response.status_code == 201
    assert Attempt.objects.latest("created_at").source == "adaptive"


# ------------------------------------------------- in the browser


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


@pytest.mark.django_db(transaction=True)
def test_the_drill_leans_on_the_schedule_without_abandoning_the_rest(browser, live_server):
    """A share, not a rule, measured by running the real selection.

    A drill that only ever asks what is due stops checking what you already
    knew, and a learner who never sees a hand they are good at has no evidence
    they are improving.
    """
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="sh@e.com", email="sh@e.com", password=PASSWORD)
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()

    context = browser.new_context(viewport={"width": 390, "height": 844})
    context.add_cookies([{"name": "sessionid", "value": store.session_key,
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    page.goto(live_server.url + "/blackjack/drill/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    try:
        seen = page.evaluate("""() => {
          const chart = JSON.parse(document.getElementById('bjChart').textContent);
          const due = [{kind: 'hard', player: 16, dealer: 10}];
          let hits = 0, adaptive = 0;
          const kinds = new Set();
          for (let i = 0; i < 2000; i++) {
            const s = window.BJ.nextSituation(chart.cells, [], due);
            const key = s.cell.kind + s.cell.player + 'v' + s.cell.dealer;
            kinds.add(key);
            if (key === 'hard16v10') hits++;
            if (s.source === 'adaptive') adaptive++;
          }
          return {share: hits / 2000, adaptive: adaptive / 2000, distinct: kinds.size};
        }""")
        assert 0.5 < seen["share"] < 0.7, f"due cells came up {seen['share']:.0%} of the time"
        assert 0.5 < seen["adaptive"] < 0.7, "hands from the schedule are not marked adaptive"
        assert seen["distinct"] > 80, (
            f"only {seen['distinct']} different cells; the schedule crowded out everything else"
        )

        nothing_due = page.evaluate("""() => {
          const chart = JSON.parse(document.getElementById('bjChart').textContent);
          let adaptive = 0;
          for (let i = 0; i < 300; i++) {
            if (window.BJ.nextSituation(chart.cells, [], []).source === 'adaptive') adaptive++;
          }
          return adaptive;
        }""")
        assert nothing_due == 0, "hands were marked adaptive with nothing due"
    finally:
        context.close()
