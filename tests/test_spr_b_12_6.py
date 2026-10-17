"""SPR-B.12.6 — the recommender: a trained model that fills in the policy.

REQ-B.11.29. The network is trained offline (blackjack_model/, not part of the
site). What the site carries is its weights, a decoder shared with the training
code, and a button. The browser half is held to the trained network by
`tests/lab_js/cases.js` (check vectors, and 2,000 random tables that must give a
valid policy that never runs away). Here: the file the page loads, the server
accepting what the model proposes, and the button in a real browser.
"""

import json
import os
import pathlib
import shutil
import subprocess
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprblab

MODEL = pathlib.Path("static/blackjack/lab/recommend_model.json")


def test_the_model_file_is_small_and_says_what_it_is():
    """T-F-B.12.6-1"""
    assert MODEL.stat().st_size < 400 * 1024
    m = json.loads(MODEL.read_text(encoding="utf-8"))
    assert m["kind"] == "mlp" and m["chart"] == "classic"
    assert m["layers"][-1]["W"] and len(m["layers"][-1]["W"]) == 13
    assert len(m["scaler"]["mean"]) == len(m["layers"][0]["W"][0]) == 8
    measured = m["measured"]
    assert measured["ahead_pct"] > measured["default_ahead_pct"] > 0
    assert measured["held_out"] >= 1000


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_server_accepts_every_policy_the_model_proposes(db):
    """T-F-B.12.6-2: what the button fills in can always be saved."""
    from blackjack import lab

    script = """
    const R = require('./static/blackjack/lab/lab_recommend.js');
    const m = require('./static/blackjack/lab/recommend_model.json');
    const out = [];
    for (const start of [100, 350, 1000, 2500, 8000, 20000])
      for (const minBet of [5, 15, 25, 100])
        for (const ratio of [10, 33, 200])
          for (const hands of [100, 800])
            out.push(R.recommend(m, {start, minBet, limit: minBet * ratio, handsPerDay: hands, decks: 6, h17: false, das: true, pays: '3:2'}).policy);
    process.stdout.write(JSON.stringify(out));
    """
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    policies = json.loads(done.stdout)
    assert len(policies) == 6 * 4 * 3 * 2
    for policy in policies:
        if policy["start"] < policy["minBet"]:
            continue
        cleaned = lab.clean_policy(policy)
        assert cleaned["ladder"] == policy["ladder"] and cleaned["freeze"] == policy["freeze"]


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
    return _login_cookie("advice@example.com")


def _open(browser, live_server, session, width=390):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "domain": "localhost", "path": "/"}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url + "/blackjack/lab/", wait_until="domcontentloaded")
    page.wait_for_selector("#labRecommend")
    return context, page, errors


@pytest.mark.django_db(transaction=True)
def test_the_button_fills_in_the_policy_and_says_how_good_it_is(browser, live_server, world):
    """T-F-B.12.6-3: REQ-B.11.29."""
    _user, session = world
    context, page, errors = _open(browser, live_server, session)
    page.fill("#labHands", "400")
    before = page.eval_on_selector_all("#labLadder input", "els => els.map(e => e.value)")
    page.click("#labRecommend")
    page.wait_for_selector("#labAdviceNote:not([hidden])")
    page.wait_for_function("document.getElementById('labAdviceNote').textContent.includes('מולא')", timeout=10000)
    note = page.inner_text("#labAdviceNote")
    assert "מהימים" in note and "היתרון של הקזינו" in note
    assert "ניחוש" not in note
    after = page.eval_on_selector_all("#labLadder input", "els => els.map(e => e.value)")
    assert after and after != before
    rows = page.eval_on_selector_all("#labFreeze .bj-lab-row", "els => els.map(r => [...r.querySelectorAll('input')].map(i => +i.value))")
    start = int(page.input_value("#labStart"))
    base = start
    for gain, take in rows:
        assert base + gain - take >= start, "the recommended freeze runs away"
        base = base + gain - take

    page.fill("#labDays", "10")
    page.click("#labRun")
    page.wait_for_selector("#labResults:not([hidden]) svg", timeout=40000)
    assert errors == []
    context.close()


@pytest.mark.django_db(transaction=True)
def test_the_button_warns_outside_what_it_learned(browser, live_server, world):
    """T-F-B.12.6-4"""
    _user, session = world
    context, page, errors = _open(browser, live_server, session)
    page.fill("#labStart", "90000")
    page.fill("#labHands", "400")
    page.click("#labRecommend")
    page.wait_for_function("document.getElementById('labAdviceNote').textContent.includes('ניחוש')", timeout=10000)
    page.fill("#labStart", "1000")
    page.check('input[name="chart"][value="calculated"]')
    page.click("#labRecommend")
    page.wait_for_function("document.getElementById('labAdviceNote').textContent.includes('הטבלה הקלאסית')", timeout=10000)
    page.fill("#labStart", "-5")
    page.click("#labRecommend")
    page.wait_for_function("document.getElementById('labAdviceNote').textContent.includes('כסף להתחלה')", timeout=10000)
    assert errors == []
    context.close()
