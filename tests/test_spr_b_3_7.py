"""SPR-B.3.7 — cells you missed come back.

REQ-B.5.7, the free half of spaced repetition. The evidence in this field is
for the shape, wrong answers return sooner and right ones recede, and it is the
one thing that separates a drill that teaches from a drill that measures.

**The load-bearing test is `test_a_missed_cell_comes_back_and_a_corrected_one_stops`.**
Both halves matter and the second is the one that would be missed: a review
list that never forgets turns into a punishment loop, asking somebody forever
about a hand they fixed twenty minutes ago.

Traces: REQ-B.5.7.
"""

import os
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb37

API = "/blackjack/api/attempts/"
PASSWORD = "sprb37-pass-6612"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="review@example.com", email="review@example.com", password=PASSWORD
    )


def _play(client, kind, value, dealer, right):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    return client.post(API, {
        "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
        "chosen": chosen, "player_cards": [10, 6], "answer_ms": 700, "source": "random",
    }, content_type="application/json")


def test_a_missed_cell_comes_back_and_a_corrected_one_stops(client, person):
    """The two halves. A list that never forgets is a punishment loop."""
    from blackjack.models import Player
    from blackjack.views import recent_misses

    client.force_login(person)
    player = Player.for_user(person)

    _play(client, "hard", 16, 10, right=False)
    _play(client, "soft", 18, 9, right=False)
    waiting = recent_misses(player)
    keys = {(row["kind"], row["player"], row["dealer"]) for row in waiting}
    assert ("hard", 16, 10) in keys
    assert ("soft", 18, 9) in keys

    _play(client, "hard", 16, 10, right=True)
    keys = {(r["kind"], r["player"], r["dealer"]) for r in recent_misses(player)}
    assert ("hard", 16, 10) not in keys, "a cell put right is still being punished"
    assert ("soft", 18, 9) in keys, "a cell still wrong fell off the list"


def test_an_old_mistake_falls_out_of_the_window(client, person):
    """"Lately" means the last few dozen hands, not forever. Somebody who
    missed a cell four hundred hands ago has moved on."""
    from blackjack.models import Player
    from blackjack.views import recent_misses

    client.force_login(person)
    _play(client, "hard", 12, 4, right=False)
    for _ in range(45):
        _play(client, "hard", 13, 5, right=True)

    keys = {(r["kind"], r["player"], r["dealer"]) for r in recent_misses(Player.for_user(person))}
    assert ("hard", 12, 4) not in keys


def test_the_page_carries_the_review_list(client, person):
    import json

    client.force_login(person)
    _play(client, "pair", 8, 10, right=False)

    html = client.get("/blackjack/drill/").content.decode()
    start = html.index('id="bjChart"')
    payload = json.loads(html[html.index(">", start) + 1: html.index("</script>", start)])

    assert payload["review"], "the drill was handed no review list"
    assert {"kind": "pair", "player": 8, "dealer": 10} in payload["review"]


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
def test_a_review_cell_is_asked_more_often_than_chance_but_not_always(browser, live_server):
    """The share, measured by running the real selection two thousand times.

    The first version of this test mirrored the contract in Python and counted
    `random.random()` calls, which measured Python's random number generator
    and nothing of mine. A test that cannot fail when the code is wrong is
    worse than no test, because it reads like coverage.

    A share and not a rule: a drill that only ever asks what you are bad at is
    demoralising, and it stops checking the things you already knew.
    """
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="share@e.com", email="share@e.com",
                                    password=PASSWORD)
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
          const review = [{kind: 'hard', player: 16, dealer: 10}];
          let hits = 0, kinds = new Set();
          for (let i = 0; i < 2000; i++) {
            const s = window.BJ.nextSituation(chart.cells, review);
            const key = s.cell.kind + s.cell.player + 'v' + s.cell.dealer;
            kinds.add(key);
            if (key === 'hard16v10') hits++;
          }
          return {share: hits / 2000, distinct: kinds.size};
        }""")
        assert 0.3 < seen["share"] < 0.5, (
            f"the review cell came up {seen['share']:.0%} of the time"
        )
        assert seen["distinct"] > 100, (
            f"the drill only asked {seen['distinct']} different cells; a review "
            "list that crowds out everything else stops checking what you knew"
        )

        with_nothing = page.evaluate("""() => {
          const chart = JSON.parse(document.getElementById('bjChart').textContent);
          const kinds = new Set();
          for (let i = 0; i < 400; i++) {
            const s = window.BJ.nextSituation(chart.cells, []);
            kinds.add(s.cell.kind + s.cell.player + 'v' + s.cell.dealer);
          }
          return kinds.size;
        }""")
        assert with_nothing > 100, "with nothing to review the drill stopped varying"
    finally:
        context.close()
