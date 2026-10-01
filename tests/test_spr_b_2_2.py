"""SPR-B.2.2 — decide, then learn.

**The load-bearing test is `test_nothing_about_the_answer_is_on_screen_before_you_choose`.**
REQ-B.4.2 is the difference between practice and a lookup table. A drill that
shows the answer first is a cheat sheet with extra steps: the person reads,
agrees, and learns nothing, while their accuracy climbs and the product tells
them they are improving. The failure is invisible in the data, which is why it
needs a test rather than a careful eye.

Second: `test_the_reason_shown_is_the_cell_s_own_reason`. The explanation after
a hand is the whole teaching surface of the free product. If it ever drifts from
the row, a learner is told the right play for the wrong reason.

Traces: REQ-B.4.2, B.4.3.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb22

PASSWORD = "sprb22-pass-9981"


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


def _drill(browser, live_server, name="p"):
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
    return context, page


# ------------------------------------------------- the one that matters


@pytest.mark.django_db(transaction=True)
def test_nothing_about_the_answer_is_on_screen_before_you_choose(browser, live_server):
    """Checked over twenty fresh hands, because a leak on one in twenty is
    still a product that teaches by accident."""
    context, page = _drill(browser, live_server, "hidden")
    try:
        for _ in range(20):
            state = page.evaluate("""() => {
              const v = document.getElementById('bjVerdict');
              return {
                hidden: v.hidden,
                text: (v.textContent || '').trim(),
                nextShown: !document.getElementById('bjNext').hidden,
                marked: document.querySelectorAll('.bj-act.is-answer').length
              };
            }""")
            assert state["hidden"] is True, "the verdict panel is open before a choice"
            assert state["text"] == "", f"the answer is already on screen: {state['text']!r}"
            assert state["nextShown"] is False, "the next-hand button is offered before answering"
            assert state["marked"] == 0, "the correct action is already highlighted"

            page.evaluate("() => window.__bjNextHand()")
            page.wait_for_timeout(20)
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_the_reason_shown_is_the_cell_s_own_reason(browser, live_server):
    """The teaching surface of the whole free product, checked against the row
    rather than against itself."""
    context, page = _drill(browser, live_server, "why")
    try:
        for _ in range(12):
            shown = page.evaluate("""() => {
              const s = window.__bjSituation;
              document.querySelector('.bj-act:not(:disabled)').click();
              const v = document.getElementById('bjVerdict');
              return {
                cellReason: s.cell.reason,
                cellAction: s.cell.action,
                text: v.textContent || ''
              };
            }""")
            assert shown["cellReason"] in shown["text"], (
                "the explanation shown is not the one attached to the cell"
            )
            page.evaluate("() => window.__bjNextHand()")
            page.wait_for_timeout(20)
    finally:
        context.close()


# ------------------------------------------------- judging


@pytest.mark.django_db(transaction=True)
def test_a_right_answer_and_a_wrong_one_both_teach(browser, live_server):
    """A correct hand still shows the reason. Being right by luck and being
    right by understanding look identical in the data, and the reason is the
    only thing that tells them apart for the person."""
    context, page = _drill(browser, live_server, "both")
    try:
        right = page.evaluate("""() => {
          const s = window.__bjSituation;
          const want = s.cell.action;
          document.querySelector('.bj-act[data-act="' + want + '"]').click();
          const v = document.getElementById('bjVerdict');
          return {head: v.querySelector('.bj-verdict-head').className,
                  why: (v.querySelector('.bj-verdict-why') || {}).textContent || ''};
        }""")
        assert "is-right" in right["head"]
        assert right["why"].strip(), "a correct answer was not explained"

        page.evaluate("() => window.__bjNextHand()")
        page.wait_for_timeout(20)

        wrong = page.evaluate("""() => {
          const s = window.__bjSituation;
          const other = ['H', 'S', 'D', 'P'].filter(a => a !== s.cell.action);
          let clicked = null;
          for (const a of other) {
            const b = document.querySelector('.bj-act[data-act="' + a + '"]');
            if (b && !b.disabled) { b.click(); clicked = a; break; }
          }
          const v = document.getElementById('bjVerdict');
          return {clicked: clicked, head: v.querySelector('.bj-verdict-head').className,
                  text: v.textContent || '', correct: s.cell.action};
        }""")
        assert "is-not" in wrong["head"]
        assert wrong["text"].strip(), "a wrong answer was not explained"
        assert wrong["clicked"] != wrong["correct"], "the test clicked the right answer"
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_split_is_only_offered_on_a_pair(browser, live_server):
    """A button that is always wrong teaches that one of the four is
    decoration. Checked across enough hands to meet both kinds."""
    context, page = _drill(browser, live_server, "split")
    try:
        seen_pair = seen_other = False
        for _ in range(40):
            state = page.evaluate("""() => ({
              kind: window.__bjSituation.cell.kind,
              splitEnabled: !document.querySelector('.bj-act[data-act="P"]').disabled
            })""")
            if state["kind"] == "pair":
                seen_pair = True
                assert state["splitEnabled"], "split is not offered on a pair"
            else:
                seen_other = True
                assert not state["splitEnabled"], f"split offered on a {state['kind']} hand"
            page.evaluate("() => window.__bjNextHand()")
            page.wait_for_timeout(10)
        assert seen_pair and seen_other, "the sample never met both kinds of hand"
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_answering_twice_counts_once(browser, live_server):
    """A double tap is one hand. Otherwise a nervous thumb inflates somebody's
    accuracy, and the statistics are the product."""
    context, page = _drill(browser, live_server, "twice")
    try:
        # Through the keyboard, not the buttons. Clicking a disabled button
        # dispatches nothing, so a click-based version of this test proves the
        # `disabled` attribute and never reaches the guard. The keyboard path
        # has no disabled attribute to hide behind, which is exactly why it is
        # the path that could double-count.
        score = page.evaluate("""() => {
          const act = window.__bjSituation.cell.action;
          for (let i = 0; i < 3; i++) {
            document.dispatchEvent(new KeyboardEvent('keydown', {key: act, bubbles: true}));
          }
          return document.getElementById('bjScore').textContent;
        }""")
        assert "מתוך 1" in score, score
    finally:
        context.close()


@pytest.mark.django_db(transaction=True)
def test_it_never_ends(browser, live_server):
    """REQ-B.4.3. No level gate, no lives, no session limit: fifty hands and
    the fifty-first is still there."""
    context, page = _drill(browser, live_server, "forever")
    try:
        for _ in range(50):
            page.evaluate("""() => {
              document.querySelector('.bj-act:not(:disabled)').click();
              window.__bjNextHand();
            }""")
        state = page.evaluate("""() => ({
          cards: document.querySelectorAll('.bj-card').length,
          buttons: document.querySelectorAll('.bj-act:not(:disabled)').length,
          score: document.getElementById('bjScore').textContent
        })""")
        assert state["cards"] >= 3, "the table stopped dealing"
        assert state["buttons"] >= 3, "the actions stopped being offered"
        assert "50" in state["score"], state["score"]
    finally:
        context.close()
