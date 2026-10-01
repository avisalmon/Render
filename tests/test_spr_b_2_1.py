"""SPR-B.2.1 — the practice table: cards, dealt in the right order.

**The load-bearing test is `test_the_cards_always_add_up_to_the_hand_being_asked`.**
It runs the real dealing function in a real browser against every cell in the
chart. A situation whose cards do not make the hand it claims would teach the
right answer to the wrong question, and the learner has no way to notice: they
see two cards, they answer, and they are told they were correct about a hand
they were not looking at. Nothing else in this app can detect that.

It is a browser test because the logic lives in the browser, and logic reachable
only through a click is logic nobody can test.

Traces: REQ-B.4.1, B.4.5, B.4.7, B.4.8.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb21

PASSWORD = "sprb21-pass-7714"


@pytest.fixture
def person(db):
    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="drill@example.com", email="drill@example.com", password=PASSWORD
    )


# ------------------------------------------------- the chart reaches the page


def test_the_page_carries_the_same_cells_the_sheet_renders(client, person):
    """REQ-B.3.5 through the drill, which is the half the sheet's test could
    not reach. One set of rows, two readers, and now both are checked."""
    import json

    from blackjack.models import Cell, Chart, Player

    client.force_login(person)
    html = client.get("/blackjack/drill/").content.decode()

    start = html.index('id="bjChart"')
    payload = html[html.index(">", start) + 1: html.index("</script>", start)]
    shipped = json.loads(payload)

    chart = Chart.objects.get(rule_set=Player.for_user(person).rule_set)
    rows = {(c.kind, c.player, c.dealer): (c.action, c.fallback, c.reason)
            for c in Cell.objects.filter(chart=chart)}

    assert len(shipped["cells"]) == len(rows)
    for cell in shipped["cells"]:
        key = (cell["kind"], cell["player"], cell["dealer"])
        assert key in rows, f"the page ships {key}, which is not a row"
        assert (cell["action"], cell["fallback"], cell["reason"]) == rows[key], (
            f"the page ships a different answer for {key} than the row holds"
        )


def test_the_drill_never_asks_the_server_what_the_right_play_is(client, person):
    """REQ-B.4.5 as a property of the code, not a stopwatch. A fetch for the
    answer is a tutor that stops working in a tunnel."""
    import pathlib

    source = pathlib.Path("static/blackjack/drill.js").read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "navigator.sendBeacon"):
        assert forbidden not in source, f"the drill calls out to the server: {forbidden}"


def test_a_table_with_no_chart_refuses_the_drill_too(client, person):
    from blackjack.models import Player

    Player.for_user(person).play_by(decks=1)
    client.force_login(person)
    body = client.get("/blackjack/drill/").content.decode()
    assert "bjChart" not in body, "a drill was offered with no chart behind it"
    assert "/blackjack/table/" in body


def test_no_sound_anywhere_in_the_app():
    """REQ-B.4.7. A refusal, so it is tested like one: people practise where
    sound is not an option, and an app that chirps is one they cannot open."""
    import pathlib

    for path in pathlib.Path("static/blackjack").glob("*.js"):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("new Audio", "AudioContext", ".play()", "<audio"):
            assert forbidden not in source, f"{path.name} makes a sound"


# ------------------------------------------------- the browser half


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chrome = pw.chromium.launch()
            yield chrome
            chrome.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _signed_in_page(browser, live_server, user, width=390):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()

    context = browser.new_context(viewport={"width": width, "height": 844})
    context.add_cookies([{"name": "sessionid", "value": store.session_key,
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    page.goto(live_server.url + "/blackjack/drill/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    return context, page


@pytest.mark.django_db(transaction=True)
def test_the_cards_always_add_up_to_the_hand_being_asked(browser, live_server):
    """Every cell in the chart, through the real dealing function.

    A hand that does not match its cell teaches the right answer to the wrong
    question, and the learner cannot possibly notice.
    """
    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="cards@e.com", email="cards@e.com",
                                    password=PASSWORD)
    context, page = _signed_in_page(browser, live_server, user)
    try:
        wrong = page.evaluate("""() => {
          const chart = JSON.parse(document.getElementById('bjChart').textContent);
          const bad = [];
          chart.cells.forEach(cell => {
            for (let go = 0; go < 6; go++) {
              const cards = window.BJ.cardsFor(cell.kind, cell.player);
              const total = window.BJ.handTotal(cards);
              const isPair = cards.length === 2 && cards[0] === cards[1];
              const hasAce = cards.indexOf(11) !== -1;
              if (cell.kind === 'pair') {
                if (!isPair || cards[0] !== cell.player)
                  bad.push(cell.kind + ' ' + cell.player + ' -> ' + cards.join('+'));
              } else if (cell.kind === 'soft') {
                if (!hasAce || total !== cell.player)
                  bad.push(cell.kind + ' ' + cell.player + ' -> ' + cards.join('+'));
              } else {
                if (total !== cell.player || hasAce || isPair)
                  bad.push(cell.kind + ' ' + cell.player + ' -> ' + cards.join('+'));
              }
            }
          });
          return [...new Set(bad)].slice(0, 12);
        }""")
        assert not wrong, "cards that do not make the hand being asked:\n" + "\n".join(wrong)
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_the_deal_follows_the_table_player_dealer_player(browser, live_server):
    """Avi changed this deliberately, from dealer-first to casino order, so it
    is pinned rather than left to whoever edits the function next."""
    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="order@e.com", email="order@e.com",
                                    password=PASSWORD)
    context, page = _signed_in_page(browser, live_server, user)
    try:
        assert page.evaluate("() => window.BJ.DEAL_ORDER") == [
            "player", "dealer", "player", "hole"
        ]

        seen = page.evaluate("""() => {
          const order = [];
          document.querySelectorAll('#bjPlayer .bj-card, #bjDealer .bj-card').forEach(el => {
            order.push({
              who: el.closest('#bjPlayer') ? 'player' : 'dealer',
              down: el.classList.contains('is-down'),
              /* animationDelay reads back as "0.16s", and parseInt of that
                 is 0, which made every card look simultaneous and the sort
                 keep DOM order. Seconds, then, not integers. */
              delay: parseFloat(getComputedStyle(el).animationDelay) * 1000
            });
          });
          return order.sort((a, b) => a.delay - b.delay).map(c => c.down ? 'hole' : c.who);
        }""")
        assert seen[:4] == ["player", "dealer", "player", "hole"], seen

        assert page.evaluate(
            "() => document.querySelectorAll('#bjDealer .bj-card.is-down').length"
        ) == 1, "the dealer's hole card is not face down"
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_cards_still_arrive_when_motion_is_turned_off(browser, live_server):
    """REQ-B.4.8. Reduced motion must mean no flying, never no cards: a drill
    that renders nothing for somebody who gets motion sick is not accessible,
    it is broken."""
    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="still@e.com", email="still@e.com",
                                    password=PASSWORD)
    context, page = _signed_in_page(browser, live_server, user)
    try:
        count = page.evaluate("""() => {
          const chart = JSON.parse(document.getElementById('bjChart').textContent);
          const s = window.BJ.nextSituation(chart.cells);
          window.BJ.deal(s, {
            player: document.getElementById('bjPlayer'),
            dealer: document.getElementById('bjDealer')
          }, {stillness: true});
          return {
            cards: document.querySelectorAll('.bj-card').length,
            moving: document.querySelectorAll('.bj-card:not(.is-still)').length
          };
        }""")
        assert count["cards"] >= 3, "no cards were dealt with motion off"
        assert count["moving"] == 0, "cards still animate with motion off"
    finally:
        context.close()
