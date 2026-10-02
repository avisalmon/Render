"""The review pass of 2026-10-02: what a person sees, screen by screen.

Avi: "pause and review everything we did by now for correctness, UX,
gamification, adapt to phone and PC, bugs, human flawless understanding of
what's going on. Fix it to perfection."

Each test here is one thing the walk-through found wrong, with the screen it
was found on. The two that carry the most weight:

**`test_the_note_at_the_twentieth_hand_is_shown_at_the_table`.** The spec
promised a note every twenty hands. The note was written, and shown on the
history page, which nobody opens mid-drill, so the thing promised at the table
never appeared at the table.

**`test_no_sheet_or_progress_view_hides_a_column_off_the_phone`.** The soft,
pairs and doubles views were ten dealer columns wide. At 390px the 8, 9, 10 and
A columns sat off the left edge behind a scrollbar hidden on purpose. The
sheet's own rule, five columns is a thumb, had been applied to the hard table
and to nothing else.

Then the explanations: every reason that named the dealer's ace called it "11",
which is how the code counts it and how nobody at a table has ever said it.
"""

import os
import re
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.review1002

PASSWORD = "review-pass-1002"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(username="rev@example.com", email="rev@example.com",
                                    password=PASSWORD, first_name="רות")


def _play(client, times=1, right=True, kind="hard", value=16):
    from blackjack.models import Cell

    cell = Cell.objects.filter(kind=kind, player=value).first()
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    last = None
    for _ in range(times):
        last = client.post("/blackjack/api/attempts/", {
            "cell_kind": cell.kind, "cell_player": cell.player,
            "cell_dealer": cell.dealer, "chosen": chosen,
            "player_cards": [10, 6], "answer_ms": 700, "source": "random",
        }, content_type="application/json")
    return last


def _session_for(user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return store.session_key


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


# ------------------------------------------------- correctness: what the reasons say


def test_no_explanation_calls_the_dealers_ace_eleven(person):
    """11 is how the code counts an ace. A person reads "מול אס"."""
    from blackjack.models import Cell

    offenders = [
        (c.kind, c.player, c.dealer, c.reason)
        for c in Cell.objects.all()
        if re.search(r"מול 11\b", c.reason)
    ]
    assert not offenders, f"{len(offenders)} reasons say 'מול 11', e.g. {offenders[0]}"

    # And the fix is exercised: ace cells do say "מול אס", so the first
    # assertion is not passing against reasons that never name the dealer.
    aces = Cell.objects.filter(dealer=11)
    assert sum("מול אס" in c.reason for c in aces) >= 10, (
        "almost no ace cell names the dealer, so the check above proves little"
    )


def test_a_chart_built_by_an_older_strategy_is_rebuilt_on_the_next_seed(db):
    """Production had a chart built before the ace wording was fixed, and the
    seed left it alone because cells existed. Cells are produced by code and
    never edited by a person, so a stale chart is a bug being served, and the
    seed may replace it on its own."""
    from blackjack.models import Cell, Chart

    call_command("seed_blackjack_chart", stdout=StringIO())
    chart = Chart.objects.get()
    assert "@" in chart.source, "the chart does not record which strategy built it"

    # Age it: pretend it came from the version before, with the old wording.
    Chart.objects.filter(pk=chart.pk).update(source="blackjack.strategy@1")
    Cell.objects.filter(chart=chart, dealer=11).update(reason="12 מול 11 בדיקה")

    out = StringIO()
    call_command("seed_blackjack_chart", stdout=out)
    chart.refresh_from_db()
    assert "moved on" in out.getvalue(), "a stale chart was left alone"
    assert not Cell.objects.filter(reason__contains="מול 11").exists()

    # Same version: left alone, which is the methodology's rule for seeds.
    out = StringIO()
    call_command("seed_blackjack_chart", stdout=out)
    assert "left alone" in out.getvalue()


# ------------------------------------------------- the note, at the table


def test_the_twentieth_hand_comes_back_with_the_note(client, person):
    client.force_login(person)
    for i in range(19):
        answer = _play(client).json()
        assert answer["note"] is None, f"a note arrived at hand {i + 1}"
        assert answer["in_batch"] == i + 1

    twentieth = _play(client).json()
    assert twentieth["note"], "the twentieth hand came back without its note"
    assert "עשרים ידיים" in twentieth["note"]
    assert twentieth["in_batch"] == 0, "the count did not roll over at twenty"


@pytest.mark.django_db(transaction=True)
def test_the_note_at_the_twentieth_hand_is_shown_at_the_table(browser, live_server):
    """The load-bearing one. Twenty hands through the real screen, and the
    note is on the screen where the twenty were played."""
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="tbl@e.com", email="tbl@e.com", password=PASSWORD)

    context = browser.new_context(viewport={"width": 390, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": _session_for(user),
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    page.goto(live_server.url + "/blackjack/drill/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)

    assert "20" in page.evaluate("() => document.getElementById('bjBatch').textContent"), (
        "the drill does not say how far the next note is"
    )

    for hand in range(20):
        if hand:
            page.keyboard.press("Enter")
            page.wait_for_timeout(100)
        action = page.evaluate("() => window.__bjSituation.cell.action")
        page.keyboard.press(action)
        page.wait_for_timeout(100)
        if hand < 19:
            shown = page.evaluate("() => !document.getElementById('bjNote').hidden")
            assert not shown, f"a note appeared at hand {hand + 1}"

    page.wait_for_timeout(1500)      # the server's reply to the twentieth
    note = page.evaluate("""() => {
      const n = document.getElementById('bjNote');
      return {hidden: n.hidden, text: n.textContent};
    }""")
    assert not note["hidden"], "the twentieth hand was recorded and the table stayed silent"
    assert "עשרים ידיים" in note["text"]

    # And it clears with the next deal, so it is read once rather than nagging.
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    assert page.evaluate("() => document.getElementById('bjNote').hidden")
    context.close()


# ------------------------------------------------- nothing off the edge of a phone


@pytest.mark.django_db(transaction=True)
def test_no_sheet_or_progress_view_hides_a_column_off_the_phone(browser, live_server):
    """Every cell of every view is inside a 390px viewport, and so is every
    nav link. A column you have to know to scroll to is a column you never
    learn; a link you cannot see is not in the menu."""
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="edge@e.com", email="edge@e.com", password=PASSWORD)

    context = browser.new_context(viewport={"width": 390, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": _session_for(user),
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()

    screens = ["/blackjack/sheet/?view=" + v for v in ("weak", "strong", "soft", "pairs", "doubles")]
    screens += ["/blackjack/progress/?view=" + v for v in ("weak", "strong", "soft", "pairs")]
    screens += ["/blackjack/", "/blackjack/drill/", "/blackjack/history/"]

    outside = []
    for path in screens:
        page.goto(live_server.url + path, wait_until="domcontentloaded")
        page.wait_for_timeout(250)
        found = page.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.bj-cell, .bj-nav-link').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0) return;
            if (r.left < -1 || r.right > window.innerWidth + 1)
              out.push(el.textContent.trim().slice(0, 10) + '@' + Math.round(r.left));
          });
          return out;
        }""")
        for item in found[:3]:
            outside.append(f"{path}: {item}")
        # Sanity: the sheet views actually drew cells, or the check is empty.
        if "sheet" in path or "progress" in path:
            assert page.evaluate("() => document.querySelectorAll('.bj-cell').length") > 20

    context.close()
    assert not outside, "off the edge of a phone:\n" + "\n".join(outside)


def test_a_wide_view_arrives_as_two_tables_of_at_most_five_dealers(client, person):
    client.force_login(person)
    for screen in ("/blackjack/sheet/?view=pairs", "/blackjack/progress/?view=soft"):
        html = client.get(screen).content.decode()
        heads = re.findall(r"<thead>.*?</thead>", html, re.S)
        assert len(heads) == 2, f"{screen}: {len(heads)} tables"
        for head in heads:
            assert len(re.findall(r'<th scope="col">', head)) - 1 <= 5
        assert "דילר חלש" in html and "דילר חזק" in html, "the halves are not named"


# ------------------------------------------------- the person knows where they stand


def test_the_front_page_tells_a_returning_player_where_they_stand(client, person):
    client.force_login(person)
    before = client.get("/blackjack/").content.decode()
    assert "להתחיל לתרגל" in before
    assert "bj-standing" not in before, "a strip of zeros for somebody who never played"

    _play(client, times=4, right=True)
    _play(client, times=1, right=False)
    after = client.get("/blackjack/").content.decode()
    assert "להמשיך לתרגל" in after, "a returning player is told to start"
    strip = after[after.find('class="bj-standing"'):][:600]
    assert "80%" in strip and "5 ידיים" in strip
    assert "bj-streak" in strip, "the streak is missing from the strip"


def test_progress_counts_what_is_on_the_way_not_only_what_is_solid(client, person):
    """After an hour, "0 of 340 solid" is true and reads as "nothing". The
    number that moves on day one is the cells answered right so far."""
    client.force_login(person)
    empty = client.get("/blackjack/progress/").content.decode()
    assert "340" in empty
    assert "/blackjack/drill/" in empty, "no door to the drill from an empty grid"

    _play(client, times=1, right=True, kind="hard", value=12)
    _play(client, times=1, right=True, kind="soft", value=18)
    body = client.get("/blackjack/progress/").content.decode()
    sentence = body[body.find('class="bj-progress-sum"'):][:500]
    assert "2 בדרך" in sentence, "cells answered right so far are not counted anywhere"


def test_history_says_a_miss_in_words(client, person):
    client.force_login(person)
    assert "לשתף" not in client.get("/blackjack/history/").content.decode(), (
        "a share button for somebody with nothing to share"
    )
    _play(client, times=1, right=False)
    body = client.get("/blackjack/history/").content.decode()
    row = body[body.find('class="bj-hand-row'):][:600]
    assert "במקום" in row, "the miss is still an arrow a reader has to decode"
    assert "←" not in row
    assert "לשתף" in body


def test_the_locked_page_offers_the_first_hand_to_somebody_who_never_played(client, person):
    """It says the thirty minutes start at the first hand, so it must offer one."""
    client.force_login(person)
    response = client.get("/blackjack/advanced/")
    body = response.content.decode()
    assert response.status_code == 402

    # Scoped to the page's own content. The nav links to the drill on every
    # screen, so searching the whole page passed with the door removed:
    # methodology entry 1, with the nav as the innocent place this time.
    main = body[body.find("<main"):body.find("</main>")]
    assert 'href="/blackjack/drill/"' in main, "the locked page promises a door and offers none"
    assert "<title>המאמן" in body, "the tab says something other than the heading"


def test_the_drill_shows_the_trial_clock_only_while_the_trial_runs(client, person):
    from django.utils import timezone

    from blackjack.models import Player

    client.force_login(person)
    assert "המאמן פתוח עד" not in client.get("/blackjack/drill/").content.decode(), (
        "a clock for a trial that has not started"
    )
    _play(client)
    assert "המאמן פתוח עד" in client.get("/blackjack/drill/").content.decode()

    Player.objects.filter(user=person).update(
        first_used_at=timezone.now().replace(year=2020)
    )
    assert "המאמן פתוח עד" not in client.get("/blackjack/drill/").content.decode(), (
        "a clock for a trial that ended"
    )


def test_the_table_is_reached_from_the_sheet_and_the_nav_fits_a_phone(client, person):
    client.force_login(person)
    body = client.get("/blackjack/sheet/").content.decode()
    nav = body[body.find("<nav"):body.find("</nav>")]
    assert "/blackjack/table/" not in nav, "seven links put the seventh off a phone"
    assert nav.count("bj-nav-link") == 6
    rules = body[body.find('class="bj-sheet-rules"'):][:400]
    assert "/blackjack/table/" in rules, "the rules are shown with no way to change them"


def test_the_wrong_choice_looks_wrong():
    """The structural half: a rule exists for the chosen-but-not-answer
    button, and it is not just a border. The browser half is below."""
    import pathlib

    css = pathlib.Path("static/blackjack/blackjack.css").read_text(encoding="utf-8")
    start = css.find(".bj-act.is-chosen:not(.is-answer)")
    assert start != -1
    rule = css[start:css.find("}", start)]
    assert "line-through" in rule and "background" in rule


@pytest.mark.django_db(transaction=True)
def test_the_chosen_and_the_answer_are_told_apart_on_screen(browser, live_server):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="clr@e.com", email="clr@e.com", password=PASSWORD)
    context = browser.new_context(viewport={"width": 390, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": _session_for(user),
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    page.goto(live_server.url + "/blackjack/drill/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    wrong = page.evaluate(
        "() => { const s = window.__bjSituation; "
        "return window.BJ.legalActions(s).find(a => a !== s.cell.action); }"
    )
    page.keyboard.press(wrong)
    page.wait_for_timeout(300)
    styles = page.evaluate("""() => {
      const pick = sel => { const el = document.querySelector(sel); const c = getComputedStyle(el);
        return {border: c.borderColor, bg: c.backgroundColor, deco: c.textDecorationLine, op: c.opacity}; };
      return {chosen: pick('.bj-act.is-chosen'), answer: pick('.bj-act.is-answer'),
              other: pick('.bj-act:not(.is-chosen):not(.is-answer)')};
    }""")
    context.close()
    assert styles["chosen"]["border"] != styles["other"]["border"], "the choice looks unselected"
    assert styles["chosen"]["bg"] != styles["answer"]["bg"], "the choice looks like the answer"
    assert "line-through" in styles["chosen"]["deco"]
    assert float(styles["chosen"]["op"]) == 1.0, "the choice is faded like a disabled button"
