"""SPR-B.2.3 and B.2.4 — recording hands, including the ones played in a tunnel.

**The load-bearing test is `test_the_client_cannot_report_an_accuracy_it_did_not_earn`.**
The chart ships to the browser, which means the browser knows every correct
answer. If the client also decided whether it was right, then every number this
product sells, the accuracy, the mastery grid, the improvement trend, would be
a value the client chose. So the server reads the answer off the chart row and
ignores the client's opinion entirely, and that is swept rather than spot
checked.

Second: `test_hands_played_with_no_signal_arrive_later`. A year of practice must
not depend on the train having reception.

Traces: REQ-B.4.4, B.4.6, B.6.3.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb23

API = "/blackjack/api/attempts/"
PASSWORD = "sprb23-pass-3302"


@pytest.fixture
def person(db):
    from django.contrib.auth.models import User
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="rec@example.com", email="rec@example.com", password=PASSWORD
    )


def _hand(client, kind="hard", player=16, dealer=10, chosen="H", **extra):
    body = {"cell_kind": kind, "cell_player": player, "cell_dealer": dealer,
            "chosen": chosen, "player_cards": [10, 6], "answer_ms": 1500,
            "source": "random"}
    body.update(extra)
    return client.post(API, body, content_type="application/json")


# ------------------------------------------------- the one that matters


def test_the_client_cannot_report_an_accuracy_it_did_not_earn(client, person):
    """Every lie a browser could tell, refused by the server reading the row.

    Swept over a sample of cells rather than one, because the endpoint that
    trusts the client on one shape will be the one nobody checked.
    """
    from blackjack.models import Attempt, Cell, Chart, Player

    client.force_login(person)
    chart = Chart.objects.get(rule_set=Player.for_user(person).rule_set)

    sample = list(Cell.objects.filter(chart=chart).order_by("kind", "player", "dealer")[:60])
    assert sample

    for cell in sample:
        wrong = next(a for a in ("H", "S", "D", "P") if a != cell.action)
        answer = _hand(
            client, kind=cell.kind, player=cell.player, dealer=cell.dealer,
            chosen=wrong,
            # Everything a dishonest client would send:
            is_correct=True, correct=wrong, correct_fallback=wrong,
        )
        assert answer.status_code == 201, answer.content[:200]

        row = Attempt.objects.latest("created_at")
        assert row.is_correct is False, (
            f"{cell}: the client claimed a correct answer and the server believed it"
        )
        assert row.correct == cell.action, "the server took the client's word for the answer"
        assert row.correct_fallback == cell.fallback


def test_a_right_answer_is_recorded_right(client, person):
    """The other half, because a suite that only proves refusals does not prove
    the feature works."""
    from blackjack.models import Attempt, Cell, Chart, Player

    client.force_login(person)
    chart = Chart.objects.get(rule_set=Player.for_user(person).rule_set)
    cell = Cell.objects.filter(chart=chart, kind="hard", player=16, dealer=10).get()

    assert _hand(client, chosen=cell.action).status_code == 201
    row = Attempt.objects.latest("created_at")
    assert row.is_correct is True
    assert row.chosen == cell.action
    assert row.rule_set_id == chart.rule_set_id, "the hand was stored without its rules"


# ------------------------------------------------- whose hand is whose


def test_an_attempt_is_filed_under_whoever_played_it(client, person, db):
    """Ownership from the session, never the body. The site's standing rule."""
    from django.contrib.auth.models import User

    from blackjack.models import Attempt, Player

    other = User.objects.create_user(username="other@e.com", email="other@e.com",
                                     password=PASSWORD)
    theirs = Player.for_user(other)

    client.force_login(person)
    assert _hand(client, player_id=theirs.pk).status_code == 201

    row = Attempt.objects.latest("created_at")
    assert row.player.user_id == person.pk, "a hand was filed under somebody else"


def test_a_person_reads_only_their_own_hands(client, person, db):
    from django.contrib.auth.models import User

    from blackjack.models import Attempt

    other = User.objects.create_user(username="nosy@e.com", email="nosy@e.com",
                                     password=PASSWORD)
    client.force_login(person)
    _hand(client)
    mine = Attempt.objects.latest("created_at")

    client.force_login(other)
    rows = client.get(API).json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert mine.pk not in [row["id"] for row in rows], "somebody else's practice was readable"


def test_history_is_never_edited_or_deleted(client, person):
    """An attempt records something that happened. Editing one rewrites
    history; deleting one lets a person quietly erase the hands they got wrong,
    which would make every number in the product meaningless."""
    from blackjack.models import Attempt

    client.force_login(person)
    _hand(client, chosen="S")
    row = Attempt.objects.latest("created_at")

    for send in (client.put, client.patch):
        answer = send(f"{API}{row.pk}/", {"chosen": "H"}, content_type="application/json")
        assert answer.status_code in (403, 405)

    assert client.delete(f"{API}{row.pk}/").status_code in (403, 405)
    row.refresh_from_db()
    assert row.chosen == "S"


# ------------------------------------------------- the trial clock


def test_the_thirty_minutes_start_at_the_first_hand(client, person):
    """REQ-B.6.3. Not at signup, so somebody who joins on Monday and comes back
    on Thursday still has their half hour."""
    from blackjack.models import Player

    assert Player.for_user(person).first_used_at is None

    client.force_login(person)
    _hand(client)
    started = Player.objects.get(user=person).first_used_at
    assert started is not None

    _hand(client)
    assert Player.objects.get(user=person).first_used_at == started, (
        "the clock restarted on a later hand"
    )


def test_a_hand_from_a_table_with_no_chart_is_refused(client, person):
    from blackjack.models import Attempt, Player

    Player.for_user(person).play_by(decks=1)
    client.force_login(person)
    assert _hand(client).status_code == 400
    assert not Attempt.objects.exists()


# ------------------------------------------------- the tunnel


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


def _drill(browser, live_server, name):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username=f"{name}@e.com", email=f"{name}@e.com",
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
    return context, page, user


@pytest.mark.django_db(transaction=True)
def test_playing_a_hand_records_it(browser, live_server):
    from blackjack.models import Attempt

    context, page, user = _drill(browser, live_server, "live")
    try:
        page.evaluate("() => document.querySelector('.bj-act:not(:disabled)').click()")
        page.wait_for_timeout(700)
        assert Attempt.objects.filter(player__user=user).count() == 1
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_hands_played_with_no_signal_arrive_later(browser, live_server):
    """The tunnel. Five hands played offline, then the connection returns.

    Nothing is lost and nothing is sent twice, which is the pair of failures
    this queue exists to avoid.
    """
    from blackjack.models import Attempt

    context, page, user = _drill(browser, live_server, "tunnel")
    try:
        context.set_offline(True)
        for _ in range(5):
            page.evaluate("""() => {
              document.querySelector('.bj-act:not(:disabled)').click();
              window.__bjNextHand();
            }""")
            page.wait_for_timeout(60)

        page.wait_for_timeout(400)
        assert Attempt.objects.filter(player__user=user).count() == 0, (
            "something reached the server while offline"
        )
        queued = page.evaluate("() => window.BJRecord.readQueue().length")
        assert queued == 5, f"the tunnel lost hands: {queued} of 5 queued"

        context.set_offline(False)
        page.evaluate("() => window.BJRecord.flush()")
        page.wait_for_timeout(1200)

        assert Attempt.objects.filter(player__user=user).count() == 5, "hands were lost"
        assert page.evaluate("() => window.BJRecord.readQueue().length") == 0

        page.evaluate("() => window.BJRecord.flush()")
        page.wait_for_timeout(500)
        assert Attempt.objects.filter(player__user=user).count() == 5, "hands were sent twice"
    finally:
        context.close()
