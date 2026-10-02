"""The front page's tiles are tiles, not playing cards.

**This test exists because the front page was broken for four sprints and no
test could see it.** `.bj-card` was both the drill's playing card (64 by 90,
fixed) and the front page's section card. The playing-card rule is later in the
stylesheet, so it won, and the tiles rendered 64px wide with their text spilling
across the hero.

The measurement pass could not see it: a 64px box overflows nothing and has no
tap target under 44px. Every other test reads HTML, where a collapsed tile and a
correct one are the same markup. Only a browser, asking how wide things actually
are, can tell.

So the check is the general one rather than the specific one: **on every screen
that uses tiles, each tile is a reasonable share of its container and its own
text fits inside it.** That catches this collision and the next one, whatever
class names are involved.
"""

import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprb52layout

PASSWORD = "layout-pass-3391"

SCREENS = ["/blackjack/", "/blackjack/advanced/"]

MEASURE = """() => {
  const out = [];
  document.querySelectorAll('.bj-tile').forEach(tile => {
    const box = tile.getBoundingClientRect();
    const parent = tile.parentElement.getBoundingClientRect();
    let spill = 0;
    tile.querySelectorAll('h2, p, a, span').forEach(child => {
      const c = child.getBoundingClientRect();
      if (c.width === 0 && c.height === 0) return;
      spill = Math.max(spill, c.right - box.right, box.left - c.left,
                              c.bottom - box.bottom);
    });
    out.push({
      text: (tile.querySelector('h2') || {}).textContent || '?',
      w: Math.round(box.width),
      h: Math.round(box.height),
      parentW: Math.round(parent.width),
      spill: Math.round(spill)
    });
  });
  return out;
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


@pytest.mark.django_db(transaction=True)
def test_a_tile_fills_its_column_and_holds_its_own_text(browser, live_server):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore
    from django.core.management import call_command

    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="tile@e.com", email="tile@e.com",
                                    password=PASSWORD)
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()

    broken = []
    for width in (390, 1280):
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": "sessionid", "value": store.session_key,
                              "domain": "localhost", "path": "/"}])
        page = context.new_page()
        for path in SCREENS:
            page.goto(live_server.url + path, wait_until="domcontentloaded")
            page.wait_for_timeout(250)
            tiles = page.evaluate(MEASURE)
            if not tiles:
                broken.append(f"{path} at {width}px has no tiles at all")
                continue
            for tile in tiles:
                # A tile is a column of a grid, so it should be a real share of
                # its container. 64px wide is the signature of the collision.
                if tile["w"] < min(220, tile["parentW"] * 0.3):
                    broken.append(
                        f"{path} at {width}px: tile {tile['text']!r} is {tile['w']}px "
                        f"wide inside {tile['parentW']}px"
                    )
                if tile["spill"] > 2:
                    broken.append(
                        f"{path} at {width}px: tile {tile['text']!r} spills its own "
                        f"content by {tile['spill']}px"
                    )
        context.close()

    assert not broken, "collapsed tiles:\n" + "\n".join(broken)


def test_the_playing_card_and_the_tile_are_different_classes():
    """The structural half, so the collision cannot come back under a new
    name. A playing card is a fixed 64 by 90; a tile is a column that grows
    with its text. One class cannot be both."""
    import pathlib

    css = pathlib.Path("static/blackjack/blackjack.css").read_text(encoding="utf-8")
    assert ".bj-tile {" in css
    assert ".bj-card {" in css

    for template in ("home.html", "advanced.html", "locked.html"):
        markup = pathlib.Path(f"templates/blackjack/{template}").read_text(encoding="utf-8")
        assert 'class="bj-card"' not in markup, (
            f"{template} styles a section as a playing card"
        )
