"""SPR-B.12.5 — every day of a run, hand by hand, with a zoom.

REQ-B.11.28. After a run the person can open any one of its days and see the
money after each hand, the bets, and the points where winnings were frozen, and
zoom into it. None of that is kept: the page plays the chosen day again from the
run's seed. So the checks here are as much about what does *not* happen (no
request to the server, nothing in the database until Save is pressed) as about
what is drawn.

Needs a browser; skipped, never passed, without one.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprblab

PASSWORD = "sprb125-pass-4412"


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


@pytest.fixture
def world(db, transactional_db):
    from django.core.management import call_command

    from tests.test_spr_b_12_3 import _login_cookie

    call_command("seed_blackjack_chart", stdout=StringIO())
    return _login_cookie("days5@example.com")


def _open(browser, live_server, session, width=390):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "domain": "localhost", "path": "/"}])
    page = context.new_page()
    errors, writes = [], []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("request", lambda r: writes.append(r.method + " " + r.url) if r.method != "GET" else None)
    page.goto(live_server.url + "/blackjack/lab/", wait_until="domcontentloaded")
    page.wait_for_selector("#labRun")
    return context, page, errors, writes


def _sideways(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def _window(page):
    return (int(page.get_attribute("#dayPlot", "data-from")), int(page.get_attribute("#dayPlot", "data-to")))


def _run_with_freezes(page, days="20", hands="600"):
    """A policy that freezes small amounts often, so every day has points to see."""
    page.fill("#labStart", "300")
    page.fill("#labMinBet", "10")
    page.fill("#labLimit", "40")
    page.evaluate("""() => {
      const set = (id, i, v) => { const el = document.querySelectorAll('#' + id + ' input')[i]; el.value = v; el.dispatchEvent(new Event('input')); };
      set('labLadder', 0, 10); set('labLadder', 1, 20); set('labLadder', 2, 30); set('labLadder', 3, 40);
      [[20, 20], [20, 20], [30, 30], [50, 50]].forEach((pair, i) => { set('labFreeze', 2 * i, pair[0]); set('labFreeze', 2 * i + 1, pair[1]); });
    }""")
    page.fill("#labDays", days)
    page.fill("#labHands", hands)
    page.fill("#labSeed", "42")
    page.click("#labRun")
    page.wait_for_selector("#daySection #dayView svg", timeout=40000)


@pytest.mark.django_db(transaction=True)
def test_every_day_can_be_opened_and_drawn(browser, live_server, world):
    """T-F-B.12.5-1: REQ-B.11.28."""
    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    _run_with_freezes(page, days="12")
    assert page.locator("#daySelect option").count() == 12
    seen = set()
    for index in range(12):
        page.select_option("#daySelect", str(index))
        facts = page.inner_text("#dayFacts")
        assert facts.startswith(f"יום {index + 1}:")
        assert page.locator("#dayPlot svg path.bj-lab-line-run").count() == 1
        assert page.locator("#dayBets svg").count() == 1
        seen.add(facts)
    assert len(seen) > 6, "the days all read the same"
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_freeze_points_are_marked_and_listed(browser, live_server, world):
    """T-F-B.12.5-2: the points where winnings were set aside."""
    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    _run_with_freezes(page)
    page.click("#dayBest")
    options = page.eval_on_selector_all("#daySelect option", "els => els.map(e => e.textContent)")
    frozen_days = [i for i, text in enumerate(options) if "מוקפא" in text]
    assert frozen_days, "no day froze anything, so nothing was checked"
    page.select_option("#daySelect", str(frozen_days[0]))
    dots = page.locator("#dayPlot .bj-day-freeze-dot").count()
    listed = page.locator("#dayFreezes .bj-day-freeze-go").count()
    assert dots >= 1 and listed >= 1
    assert "הוקפאו" in page.inner_text("#dayPlot")
    assert "הוקפאו" in page.inner_text("#dayFreezes")

    # A day with nothing frozen says so rather than drawing an empty list.
    plain = [i for i, text in enumerate(options) if "מוקפא" not in text]
    if plain:
        page.select_option("#daySelect", str(plain[0]))
        assert "לא הוקפא כסף" in page.inner_text("#dayFreezes")
        assert page.locator("#dayPlot .bj-day-freeze-dot").count() == 0
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_zoom_pan_tap_and_reset(browser, live_server, world):
    """T-F-B.12.5-3: the zoom."""
    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    _run_with_freezes(page, hands="3000")
    page.click("#dayLong")
    whole = _window(page)
    assert whole[0] == 0 and whole[1] > 20

    page.click("#dayIn")
    page.wait_for_function(f"+document.getElementById('dayPlot').dataset.to < {whole[1]}")
    zoomed = _window(page)
    assert zoomed[1] - zoomed[0] < whole[1] - whole[0]
    page.click("#dayIn")
    page.click("#dayIn")
    deep = _window(page)
    assert deep[1] - deep[0] >= 10, "never narrower than ten hands"
    assert "ידיים" in page.inner_text("#dayRange")

    box = page.locator("#dayPlot").bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 0.6, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.2, y, steps=6)
    page.mouse.up()
    panned = _window(page)
    assert panned != deep and panned[1] - panned[0] == pytest.approx(deep[1] - deep[0], abs=1)

    page.mouse.click(box["x"] + box["width"] * 0.5, y)
    page.wait_for_function("document.getElementById('dayReadout').textContent.includes('יד ')")
    assert "הימור" in page.inner_text("#dayReadout")

    page.mouse.move(box["x"] + box["width"] * 0.5, y)
    page.mouse.wheel(0, -300)
    page.wait_for_timeout(150)
    assert _window(page)[1] - _window(page)[0] <= panned[1] - panned[0]

    page.click("#dayReset")
    page.wait_for_function(f"+document.getElementById('dayPlot').dataset.to === {whole[1]}")
    assert _window(page) == whole
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_freeze_in_the_list_takes_you_to_it(browser, live_server, world):
    """T-F-B.12.5-4"""
    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    _run_with_freezes(page, hands="3000")
    options = page.eval_on_selector_all("#daySelect option", "els => els.map(e => e.textContent)")
    page.select_option("#daySelect", str(next(i for i, t in enumerate(options) if "מוקפא" in t)))
    first = page.locator("#dayFreezes .bj-day-freeze-go").first
    text = first.inner_text()
    hand = int(text.split(":")[0].replace("יד", "").replace(",", "").strip())
    first.click()
    page.wait_for_function(f"+document.getElementById('dayPlot').dataset.from <= {hand}")
    low, high = _window(page)
    assert low <= hand <= high
    assert str(hand) in page.inner_text("#dayReadout").replace(",", "")
    context.close()


@pytest.mark.django_db(transaction=True)
def test_viewing_days_sends_nothing_and_stores_nothing(browser, live_server, world):
    """T-F-B.12.5-5: Avi, "it doesn't need to be saved in the database, only in
    real time after a run"."""
    from blackjack.models import LabRun

    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    writes.clear()
    _run_with_freezes(page, days="10")
    before = len(writes)
    for index in range(10):
        page.select_option("#daySelect", str(index))
    page.click("#dayBest")
    page.click("#dayIn")
    page.click("#dayNext")
    assert len(writes) == before == 0, writes
    assert LabRun.objects.count() == 0
    page.click("#labSave")
    page.wait_for_function("document.getElementById('labSaved').textContent.includes('נשמר')", timeout=10000)
    run = LabRun.objects.get()
    blob = str(run.summary) + str(run.settings)
    assert "freezes" not in blob and "playing" not in blob and "bets" not in blob
    assert len(blob) < 4500
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_viewer_fits_a_phone_and_a_desktop(browser, live_server, world):
    """T-F-B.12.5-6: REQ-B.10.2, B.10.3."""
    _user, session = world
    for width in (390, 1280):
        context, page, errors, writes = _open(browser, live_server, session, width=width)
        _run_with_freezes(page)
        assert _sideways(page) <= 1, f"sideways scroll at {width}px"
        for selector in ("#dayIn", "#dayOut", "#dayReset", "#dayPrev", "#dayNext", "#daySelect"):
            assert page.locator(selector).bounding_box()["height"] >= 40, selector
        plot = page.locator("#dayPlot").bounding_box()
        assert plot["width"] <= width and plot["height"] > 120
        assert errors == []
        context.close()


@pytest.mark.django_db(transaction=True)
def test_a_very_long_day_is_drawn_and_zoomed(browser, live_server, world):
    """T-F-B.12.5-7: a hundred thousand hands in one day."""
    import time

    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    page.fill("#labStart", "1000000")
    page.fill("#labMinBet", "15")
    page.fill("#labLimit", "15")
    page.evaluate("""() => {
      const el = document.querySelectorAll('#labLadder input'); el[0].value = 15;
      for (let i = el.length - 1; i > 0; i--) document.querySelectorAll('#labLadder .bj-lab-row button')[i].click();
      const f = document.querySelectorAll('#labFreeze .bj-lab-row button');
      for (let i = f.length - 1; i >= 0; i--) document.querySelectorAll('#labFreeze .bj-lab-row button')[i].click();
    }""")
    page.fill("#labDays", "2")
    page.fill("#labHands", "100000")
    began = time.time()
    page.click("#labRun")
    page.wait_for_selector("#daySection #dayView svg", timeout=60000)
    assert "100,000" in page.inner_text("#dayRange")
    for _ in range(6):
        page.click("#dayIn")
    assert _window(page)[1] - _window(page)[0] < 3000
    page.click("#dayReset")
    assert time.time() - began < 45
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_a_step_that_sends_home_more_than_it_earned_leaves_the_rest_on_the_table(browser, live_server, world):
    """T-F-B.12.5-8: REQ-B.11.16. Two numbers to a step, seen on a real day."""
    _user, session = world
    context, page, errors, writes = _open(browser, live_server, session)
    page.fill("#labStart", "300")
    page.fill("#labMinBet", "10")
    page.fill("#labLimit", "40")
    page.evaluate("""() => {
      const set = (id, i, v) => { const el = document.querySelectorAll('#' + id + ' input')[i]; el.value = v; el.dispatchEvent(new Event('input')); };
      [[20, 100], [20, 15]].forEach((pair, i) => { set('labFreeze', 2 * i, pair[0]); set('labFreeze', 2 * i + 1, pair[1]); });
      const rows = document.querySelectorAll('#labFreeze .bj-lab-row button');
      rows[3].click(); rows[2].click();
    }""")
    page.fill("#labDays", "15")
    page.fill("#labHands", "800")
    page.fill("#labSeed", "9")
    page.click("#labRun")
    page.wait_for_selector("#daySection #dayView svg", timeout=40000)
    options = page.eval_on_selector_all("#daySelect option", "els => els.map(e => e.textContent)")
    index = next(i for i, text in enumerate(options) if "מוקפא" in text)
    page.select_option("#daySelect", str(index))
    listed = page.inner_text("#dayFreezes")
    assert "נשארו" in listed
    first = page.locator("#dayFreezes .bj-day-freeze-go").first.inner_text()
    assert "הוקפאו 100" in first, first
    assert errors == []
    context.close()
