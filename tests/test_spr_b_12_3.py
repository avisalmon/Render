"""SPR-B.12.3 — the lab in a real browser.

The engine is held to the server's by `test_spr_b_12_1` and the storage by
`test_spr_b_12_2`. What neither can see is the screen: the form that reads
itself, the worker that plays, the graphs that are drawn, the button that
saves. So this drives a real page the way a person does, on a phone-sized
screen and a desktop one, and checks that nothing scrolls sideways and nothing
is too small to tap (REQ-B.10.1 to B.10.3).

Traces: REQ-B.11.1, B.11.3, B.11.6, B.11.10, B.11.21, B.11.22, B.10.2, B.10.3.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprblab

PASSWORD = "sprb123-pass-3391"


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


def _login_cookie(email="lab3@example.com"):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return user, store.session_key


def _page(browser, live_server, width, session):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "domain": "localhost", "path": "/"}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/blackjack/lab/", wait_until="domcontentloaded")
    page.wait_for_selector("#labRun")
    return context, page, errors


def _sideways(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


@pytest.fixture
def world(db, transactional_db):
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    return _login_cookie()


@pytest.mark.django_db(transaction=True)
def test_the_form_opens_with_the_defaults_and_fits_a_phone(browser, live_server, world):
    """T-F-B.12.3-1: REQ-B.11.18, B.10.2, B.10.3."""
    _user, session = world
    for width in (390, 1280):
        context, page, errors = _page(browser, live_server, width, session)
        assert page.input_value("#labStart") == "1000"
        assert page.input_value("#labMinBet") == "15"
        assert page.input_value("#labLimit") == "500"
        assert page.eval_on_selector_all("#labLadder input", "els => els.map(e => e.value)") == ["15", "50", "150", "500"]
        assert page.eval_on_selector_all("#labFreeze input", "els => els.map(e => e.value)") == ["500", "500", "1000", "2000"]
        assert page.input_value("#labAfterWin") == "reset"
        assert _sideways(page) <= 1, f"the lab scrolls sideways at {width}px"
        for selector in ("#labRun", "#labLadderAdd", "#labFreezeAdd", "#labOvAdd"):
            assert page.locator(selector).bounding_box()["height"] >= 40, selector
        assert errors == []
        context.close()


@pytest.mark.django_db(transaction=True)
def test_many_days_runs_draws_and_saves_a_small_summary(browser, live_server, world):
    """T-F-B.12.3-2: REQ-B.11.21, B.11.6, B.11.7, B.11.23."""
    from blackjack.models import LabRun

    user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.fill("#labDays", "12")
    page.fill("#labHands", "400")
    page.fill("#labSeed", "42")
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=30000)
    text = page.inner_text("#labResults")
    assert "מתוך 12" in text
    assert page.locator("#labResults figure svg").count() == 3
    assert _sideways(page) <= 1
    assert page.locator("#labResults figure path.bj-lab-day").count() == 12

    page.fill("#labName", "הריצה הראשונה")
    page.click("#labSave")
    page.wait_for_function("document.getElementById('labSaved').textContent.includes('נשמר')", timeout=10000)

    run = LabRun.objects.get()
    assert run.player.user == user and run.name == "הריצה הראשונה"
    assert run.summary["days"] == 12 and run.settings["seed"] == 42
    assert len(str(run.summary)) < 3500, "the saved summary is not small"
    assert "temp" not in run.summary and "curves" not in run.summary

    page.click("#labSaved a")
    page.wait_for_selector("#runResults svg")
    assert "הריצה הראשונה" in page.inner_text("h1")
    assert _sideways(page) <= 1
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_same_seed_draws_the_same_answer(browser, live_server, world):
    """T-F-B.12.3-3: REQ-B.11.8."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 1280, session)
    answers = []
    for _ in range(2):
        page.fill("#labDays", "8")
        page.fill("#labHands", "300")
        page.fill("#labSeed", "7")
        page.click("#labRun")
        page.wait_for_selector("#labResults:not([hidden]) svg", timeout=30000)
        answers.append(page.inner_text("#labResults .bj-lab-sentence"))
        page.wait_for_selector("#labRun:not([hidden])")
    assert answers[0] == answers[1]
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_change_to_the_table_is_compared_with_the_classic(browser, live_server, world):
    """T-F-B.12.3-4: REQ-B.11.3, B.11.12."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.fill("#labDays", "20")
    page.fill("#labHands", "300")

    page.select_option("#labOvKind", "pair")
    page.select_option("#labOvPlayer", "8")
    page.select_option("#labOvDealer", "*")
    page.select_option("#labOvAction", "H")
    page.click("#labOvAdd")
    assert "מול הכול" in page.inner_text("#labOverrides")

    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=30000)
    text = page.inner_text("#labResults")
    assert "לעומת הטבלה הקלאסית" in text and "עזר ב-" in text
    assert page.locator("#labResults figure path.bj-lab-line-classic").count() == 1
    assert errors == []

    page.click("#labOverrides .bj-lab-chip-x")
    assert "אין שינויים" in page.inner_text("#labOverrides")
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_lists_are_free_to_edit(browser, live_server, world):
    """T-F-B.12.3-5: REQ-B.11.13, B.11.16."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.click("#labLadderAdd")
    page.click("#labFreezeAdd")
    assert page.locator("#labLadder input").count() == 5
    assert page.locator("#labFreeze input").count() == 5
    page.locator("#labFreeze .bj-lab-row button").first.click()
    assert page.locator("#labFreeze input").count() == 4
    for _ in range(3):
        page.locator("#labFreeze .bj-lab-row button").first.click()
    assert page.locator("#labFreeze input").count() == 1
    page.locator("#labFreeze .bj-lab-row button").first.click()
    assert page.locator("#labFreeze input").count() == 0
    page.fill("#labDays", "5")
    page.fill("#labHands", "100")
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=30000)
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_bad_form_says_what_is_wrong_and_runs_nothing(browser, live_server, world):
    """T-F-B.12.3-6"""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.fill("#labLimit", "5")
    page.click("#labRun")
    page.wait_for_selector("#labError:not([hidden])")
    assert "מגבלת השולחן" in page.inner_text("#labError")
    assert page.locator("#labResults").is_hidden()
    page.fill("#labLimit", "500")
    page.fill("#labHands", "100001")
    page.click("#labRun")
    assert "ידיים ביום" in page.inner_text("#labError")
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_search_reports_a_policy_and_what_it_scored_on_new_cards(browser, live_server, world):
    """T-F-B.12.3-7: REQ-B.11.22."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.check('input[name="mode"][value="search"]')
    assert page.locator("#labGoal").is_visible() and page.locator("#labDays").is_hidden()
    page.fill("#labHands", "300")
    page.fill("#labSearchDays", "10")
    page.fill("#labHoldout", "20")
    page.fill("#labBudget", "2")
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) .bj-lab-tiles", timeout=40000)
    text = page.inner_text("#labResults")
    assert "מה נמצא" in text and "הקלפים החדשים" in text
    assert "היתרון של הקזינו" in text
    assert _sideways(page) <= 1
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_run_can_be_stopped(browser, live_server, world):
    """T-F-B.12.3-8: REQ-B.11.10. A long search is cancelled between slices."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.check('input[name="mode"][value="search"]')
    page.fill("#labHands", "5000")
    page.fill("#labSearchDays", "40")
    page.fill("#labBudget", "300")
    page.click("#labRun")
    page.wait_for_selector("#labStop:not([hidden])")
    page.wait_for_timeout(600)
    page.click("#labStop")
    page.wait_for_function("document.getElementById('labStatus').textContent.includes('נעצר')", timeout=10000)
    assert page.locator("#labRun").is_visible()
    assert page.locator("#labResults").is_hidden()
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_hundred_thousand_hands_a_day_for_thirty_days_finishes(browser, live_server, world):
    """T-F-B.12.3-9: Avi's defaults, at full size, on a page that must stay alive."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=60000)
    assert "מתוך 30" in page.inner_text("#labResults")
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_stop_button_and_the_other_modes_fields_are_really_hidden(browser, live_server, world):
    """T-F-B.12.3-10: `hidden` is overridden by any class that sets `display`,
    which is how the other mode's fields stayed on screen."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    assert page.locator("#labStop").is_hidden()
    assert page.locator("#labProgress").is_hidden()
    assert page.locator("#labGoal").is_hidden() and page.locator("#labBudget").is_hidden()
    assert page.locator("#labDays").is_visible()
    page.check('input[name="mode"][value="search"]')
    assert page.locator("#labGoal").is_visible() and page.locator("#labDays").is_hidden()
    context.close()

@pytest.mark.django_db(transaction=True)
def test_a_calculated_chart_plays_one_deck(browser, live_server, world):
    """T-F-B.12.3-11: REQ-B.11.26. A table the published chart does not cover."""
    from blackjack.models import LabRun

    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.select_option("#labDecks", "1")
    page.fill("#labDays", "10")
    page.fill("#labHands", "300")
    page.click("#labRun")
    page.wait_for_selector("#labError:not([hidden])")
    assert "טבלה מחושבת" in page.inner_text("#labError")
    assert page.locator("#labResults").is_hidden()

    page.check('input[name="chart"][value="calculated"]')
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=30000)
    assert "מתוך 10" in page.inner_text("#labResults")
    page.click("#labSave")
    page.wait_for_function("document.getElementById('labSaved').textContent.includes('נשמר')", timeout=10000)
    run = LabRun.objects.get()
    assert run.rule_set.decks == 1 and run.settings["chart"] == "calculated"
    assert run.summary["chart"] == "calculated"
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_mixed_goal_asks_for_weights_and_searches(browser, live_server, world):
    """T-F-B.12.3-12: REQ-B.11.27."""
    _user, session = world
    context, page, errors = _page(browser, live_server, 390, session)
    page.check('input[name="mode"][value="search"]')
    assert page.locator("#labMixBox").is_hidden()
    page.select_option("#labGoal", "mix")
    assert page.locator("#labMixBox").is_visible()
    page.fill("#labMixAhead", "0")
    page.fill("#labMixAvg", "0")
    page.fill("#labMixSurvive", "0")
    page.fill("#labHands", "200")
    page.fill("#labSearchDays", "8")
    page.fill("#labHoldout", "10")
    page.fill("#labBudget", "2")
    page.click("#labRun")
    page.wait_for_selector("#labError:not([hidden])")
    assert "משקל" in page.inner_text("#labError")
    page.fill("#labMixAhead", "5")
    page.fill("#labMixAvg", "3")
    page.fill("#labMixSurvive", "2")
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) .bj-lab-tiles", timeout=40000)
    assert "מה נמצא" in page.inner_text("#labResults")
    assert _sideways(page) <= 1
    assert errors == []
    context.close()
