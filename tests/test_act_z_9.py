"""ACT-Z.9 — memz: a third QA pass, clock-skew-proof timers
(docs/memz/spec.md, docs/memz/backlog.md). Avi: "הזמנים לא מתמהגים
נכון" -- the timings don't sync/behave correctly.
"""

import io

import pytest
from django.core.files.base import ContentFile
from PIL import Image

from memz import game
from memz.models import MemeImage, Round
from tests.test_memz_screens import PHONE, browser  # noqa: E402, F401 -- the shared phone fixture

pytestmark = [pytest.mark.actz9, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _test_setup(settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    yield


def _png_bytes(color=(40, 90, 150)):
    buf = io.BytesIO()
    Image.new("RGB", (300, 220), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _seed_images(db):
    for i in range(6):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"z9actz9-source-{i}.png", ContentFile(_png_bytes((20 * i, 80, 140))), save=True)


# A skewed clock two hours *ahead* of real time -- the old, unfixed code
# compared a server deadline directly against this, which would already
# look expired the instant the page loaded (or, for the reveal index,
# would clamp straight to the last meme). Only Date.now is touched; the
# server's own ISO timestamps are still parsed correctly by `new Date(...)`
# since that doesn't call Date.now at all.
_SKEW_CLOCK_JS = """
(function () {
  var real = Date.now.bind(Date);
  Date.now = function () { return real() + 2 * 60 * 60 * 1000; };
})();
"""


def _captioning_world(round_count=3, round_seconds=30):
    session, host = game.create_session(host_user=None, round_count=round_count, round_seconds=round_seconds, vote_seconds=30)
    p2 = game.join_session(session, "שתיים")
    p3 = game.join_session(session, "שלוש")
    game.start_session(session, host)
    return session, host, p2, p3


def test_the_captioning_countdown_is_correct_even_with_a_badly_skewed_client_clock(browser, live_server, db):
    """A client whose own clock is two hours off from the server's would,
    under the old code (deadline - Date.now()), show a countdown that's
    already wildly wrong (a caption_deadline about 30 seconds out reads
    as expired, negative, the instant the page loads). The fix reads
    `state.server_time` on every poll and corrects for the browser's own
    measured offset, so the countdown is still right regardless of what
    the device's clock says."""
    pytest.importorskip("playwright.sync_api")
    session, host, _p2, _p3 = _captioning_world(round_seconds=30)
    context = browser.new_context(viewport=PHONE)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
        + _SKEW_CLOCK_JS
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    left = page.locator("[data-timer]").inner_text()
    assert left.strip().isdigit(), f"expected a real countdown number, got {left!r}"
    assert 20 <= int(left) <= 30, f"a 2-hour-skewed clock threw the countdown off: showed {left!r} for a 30s deadline"
    context.close()


def _revealed_world():
    session, host, p2, p3 = _captioning_world(round_count=1)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    assert round_obj.status == Round.REVEALED
    return session, host, round_obj


def test_the_reveal_slideshow_shows_the_right_meme_even_with_a_badly_skewed_client_clock(browser, live_server, db):
    """Same fix, the reveal slideshow's own index math (reveal_deadline
    minus the per-meme budget, times elapsed time) -- proven by loading
    the very first moment of reveal on a 2-hours-skewed client and
    confirming it's still showing meme 1 of 3, not clamped to the last
    one the way the unfixed math would (serverNow() light-years past a
    startedAt computed from the *real* deadline)."""
    pytest.importorskip("playwright.sync_api")
    session, host, _round_obj = _revealed_world()
    context = browser.new_context(viewport=PHONE)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
        + _SKEW_CLOCK_JS
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-revealed"
    assert "1 מתוך 3" in page.inner_text("[data-reveal-progress]"), (
        "a skewed client clock knocked the slideshow onto the wrong meme"
    )
    context.close()
