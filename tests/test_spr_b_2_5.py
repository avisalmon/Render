"""SPR-B.2.5 — the measurement pass: a phone, a thumb, and a battery.

The spec says phone first and measured rather than audited later (REQ-B.10.1 to
B.10.4). Every screen in the app is checked here in a real browser at three
widths, because at 390px a box 20px too wide looks exactly like a box that fits
when you read the HTML.

**The load-bearing test is `test_the_drill_does_no_work_while_it_waits`.** A
trainer that drains a battery is a trainer nobody opens twice, and it is the one
defect in this list that a person will never report: they will simply stop using
it. It is also invisible to every other test, since an idle animation frame loop
breaks nothing and renders correctly.

Traces: REQ-B.10.1 to B.10.4.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb25

PASSWORD = "sprb25-pass-4418"

SCREENS = ["/blackjack/", "/blackjack/table/", "/blackjack/sheet/", "/blackjack/drill/"]
WIDTHS = [("phone", 390, 844), ("laptop", 1024, 800), ("desktop", 1280, 900)]

SIDEWAYS = """() => {
  const out = {scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth};
  out.offenders = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    const over = Math.max(r.right - window.innerWidth, -r.left);
    /* The chart table is the documented exception: squeezing a grid is how it
       becomes unreadable, so it scrolls inside its own box. */
    if (over > 2 && !el.closest('.bj-sheet-wrap')) {
      out.offenders.push(el.tagName + '.' + el.className.toString().slice(0, 30) +
                         ' over=' + Math.round(over));
    }
  });
  out.offenders = [...new Set(out.offenders)].slice(0, 6);
  return out;
}"""

TAPS = """() => {
  const small = [];
  document.querySelectorAll('a, button, select, input').forEach(el => {
    /* The honest measure is the area a thumb can hit, not the control's own
       box. A 22px checkbox inside a 48px label is a 48px target, and the first
       version of this test reported it as a failure, which would have pushed a
       pointless change to a control that was already fine. */
    const target = el.closest('label') || el;
    const r = target.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.height < 44) {
      small.push((el.textContent || el.tagName).trim().slice(0, 18) +
                 ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    }
  });
  return [...new Set(small)];
}"""


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


def _context(browser, live_server, name, width, height):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore

    user = User.objects.filter(username=f"{name}@e.com").first() or \
        User.objects.create_user(username=f"{name}@e.com", email=f"{name}@e.com",
                                 password=PASSWORD)
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()

    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_cookies([{"name": "sessionid", "value": store.session_key,
                          "domain": "localhost", "path": "/"}])
    return context


@pytest.mark.django_db(transaction=True)
def test_no_screen_scrolls_sideways_at_any_width(browser, live_server):
    """One pass over every screen at every width: it is cheaper than one test
    each, and a failure names every broken page at once rather than the first
    one alphabetically."""
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())

    broken = []
    for label, width, height in WIDTHS:
        context = _context(browser, live_server, "wide", width, height)
        page = context.new_page()
        for path in SCREENS:
            page.goto(live_server.url + path, wait_until="domcontentloaded")
            page.wait_for_timeout(250)
            seen = page.evaluate(SIDEWAYS)
            if seen["scrollW"] > seen["innerW"]:
                broken.append(f"{path} at {label} {width}px: document is "
                              f"{seen['scrollW']}px, offenders {seen['offenders']}")
        context.close()

    assert not broken, "screens that drag sideways:\n" + "\n".join(broken)


@pytest.mark.django_db(transaction=True)
def test_everything_tappable_is_big_enough_for_a_thumb(browser, live_server):
    """REQ-B.10.3. The four action buttons are tapped hundreds of times in a
    session; the rest matter less and are held to the same line anyway, because
    the exceptions are what grow."""
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())

    small = []
    context = _context(browser, live_server, "thumb", 390, 844)
    page = context.new_page()
    for path in SCREENS:
        page.goto(live_server.url + path, wait_until="domcontentloaded")
        page.wait_for_timeout(250)
        found = page.evaluate(TAPS)
        if found:
            small.append(f"{path}: {found}")
    context.close()

    assert not small, "tap targets under 44px:\n" + "\n".join(small)


@pytest.mark.django_db(transaction=True)
def test_the_drill_does_no_work_while_it_waits(browser, live_server):
    """REQ-B.10.4, and the defect nobody will ever report.

    A person will not write in to say the app drains their battery; they will
    just stop opening it. An idle animation loop breaks nothing and renders
    correctly, so no other test in this suite can see it. This one counts
    animation frames over a second of the drill sitting there waiting for an
    answer, which is where a trainer spends most of its life.
    """
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())

    context = _context(browser, live_server, "idle", 390, 844)
    page = context.new_page()
    page.goto(live_server.url + "/blackjack/drill/", wait_until="domcontentloaded")
    page.wait_for_timeout(900)      # let the deal animation finish

    frames = page.evaluate("""() => new Promise(resolve => {
      let count = 0;
      let stop = false;
      const tick = () => { if (!stop) { count++; requestAnimationFrame(tick); } };
      const original = window.requestAnimationFrame;
      let appFrames = 0;
      window.requestAnimationFrame = function (fn) {
        appFrames++;
        return original.call(window, fn);
      };
      requestAnimationFrame(tick);
      setTimeout(() => {
        stop = true;
        window.requestAnimationFrame = original;
        resolve(appFrames - count);
      }, 1000);
    })""")
    context.close()

    assert frames <= 2, (
        f"the drill asked for {frames} animation frames while waiting for an "
        "answer. A trainer that works while it sits there is a trainer that "
        "drains a battery, and nobody reports that, they just stop opening it."
    )
