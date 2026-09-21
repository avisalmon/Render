"""F-14.3 — the main page must not drag sideways.

Found on 2026-09-21 while measuring the portal cards, and it was not the cards:
with them removed the numbers were identical. Signed in at a 1280px viewport,
`/` scrolled to 1522px, because `A.training-hero` rendered **1440px wide inside
a 1116px section**. Logged out the same page measured 1280 and was fine, which
is why nobody had noticed: the page looks correct until you sign in, and then
it looks like a rendering glitch rather than a layout bug.

The hero sizes itself from its contents (a 604px video plus the body's
max-content) instead of from its column. `width: auto` does not change it and
neither does `min-width: 0` on the flex children, which is the usual cause and
was the first thing tried; both were tested in the live page and measured.
`max-width: 100%` is what fixes it.

**This test exists because nothing in the suite could see the bug.** 220 tests
render this page and all of them read HTML, where a box 324px too wide looks
exactly like a box that fits. Only a browser with a viewport can tell, so this
is a browser test or it is nothing.

Traces: F-14.3, main_spec §0.1.
"""

import os

import pytest

# Playwright's sync API runs an event loop in this thread and Django refuses
# synchronous ORM calls from such a thread. `live_server` serves the app on its
# own thread, so nothing is actually racing; this is the documented escape.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.spr143

WIDTHS = [
    ("desktop", 1280, 900),
    ("laptop", 1024, 800),
    ("phone", 390, 844),
]

SIDEWAYS = """() => ({
  scrollW: document.documentElement.scrollWidth,
  innerW: window.innerWidth,
  widest: (() => {
    let worst = null;
    document.querySelectorAll('.home-main *').forEach(el => {
      const r = el.getBoundingClientRect();
      const over = Math.max(r.right - window.innerWidth, -r.left);
      if (over > 2 && (!worst || over > worst.over)) {
        worst = {over: Math.round(over), w: Math.round(r.width),
                 el: el.tagName + '.' + el.className.toString().slice(0, 30)};
      }
    });
    return worst;
  })(),
})"""


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


def _session_cookie(user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return store.session_key


@pytest.mark.django_db(transaction=True)
def test_the_home_page_never_scrolls_sideways(browser, live_server):
    """Signed in and signed out, at three widths.

    Signed in matters most and is the case that was broken: the page a
    returning person lands on every time. Both states are checked because the
    bug lived in the difference between them.
    """
    from django.contrib.auth.models import User

    person = User.objects.create_user(
        username="wide@example.com", email="wide@example.com", password="f143-pass-4410"
    )
    cookie = _session_cookie(person)

    broken = []
    for label, w, h in WIDTHS:
        for state in ("signed out", "signed in"):
            ctx = browser.new_context(viewport={"width": w, "height": h})
            if state == "signed in":
                ctx.add_cookies([{"name": "sessionid", "value": cookie,
                                  "domain": "localhost", "path": "/"}])
            page = ctx.new_page()
            page.goto(live_server.url + "/", wait_until="domcontentloaded")
            page.wait_for_timeout(350)
            seen = page.evaluate(SIDEWAYS)
            ctx.close()
            if seen["scrollW"] > seen["innerW"]:
                broken.append(
                    f"{label} {w}px, {state}: document is {seen['scrollW']}px wide, "
                    f"widest offender {seen['widest']}"
                )

    assert not broken, "the home page scrolls sideways:\n" + "\n".join(broken)
