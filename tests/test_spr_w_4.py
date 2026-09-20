"""SPR-W.4 — memz: the TV as the show (docs/memz/backlog.md, Epic W).

Until this sprint the big screen ran the phone's own renderers at a
slightly bigger font. That is a page, and a page seen from four metres
across a room is both unreadable and undramatic: the meme sat in a column
with a heading above it and fineprint below, taking a third of the wall.

The phone is the controller; the TV is the show. So it gets its own
renderers and its own stylesheet, and this file holds the three things
that could quietly go wrong: the TV must never grow a control (nobody is
standing at it, and it holds no player token), it must never show anything
a player's phone is not allowed to show, and the counts on it have to be
the live ones rather than a snapshot from when the slot began.

The layout itself is held by `tests/test_memz_screens.py`, which now
renders all seven TV phases at 390px — that is where the join code was
caught overflowing a narrow screen.
"""

import io
import re

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import conf, game
from memz.models import MemeImage, Round, Session, Vote
from tests.test_memz_screens import browser  # noqa: F401 -- the shared browser fixture

pytestmark = [pytest.mark.sprw4, pytest.mark.django_db]

TV_VIEW = {"width": 1280, "height": 720}


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEMZ_ROUNDS = (1, 10, 1)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    for i in range(6):
        buf = io.BytesIO()
        Image.new("RGB", (500, 380), (30 * i, 90, 150)).save(buf, format="PNG")
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"w4-{i}.png", ContentFile(buf.getvalue()), save=True)
    yield


def _park_reveal(session, index, hold_seconds=600):
    round_obj = game.current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per = conf.get("REVEAL_SECONDS_PER_MEME")
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now()
        + timezone.timedelta(seconds=per * count - (per * index + per / 2) + hold_seconds)
    )


def _revealing_room():
    session, host = game.create_session(
        host_user=None, round_count=2, round_seconds=60, vote_seconds=20, host_nickname="אבי",
    )
    p2 = game.join_session(session, "מיכל")
    p3 = game.join_session(session, "יונתן")
    game.start_session(session, host)
    for player, text in zip((host, p2, p3), ("כיתוב ראשון", "כיתוב שני", "כיתוב שלישי")):
        game.submit_caption(session, player, 1, caption_text=text)
    _park_reveal(session, 0)
    return session, host, p2, p3


def _tv(browser, live_server, code):
    context = browser.new_context(viewport=TV_VIEW)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{code}/screen/", wait_until="domcontentloaded")
    page.wait_for_timeout(900)
    return context, page


# ------------------------------------------- the TV never grows a control


def test_the_tv_has_no_rating_buttons_and_no_host_controls(browser, live_server):
    """It has no player behind it (spec §4.10) and nobody standing at it.
    A control on the wall is either dead or, worse, a way for whoever walks
    past to end the round."""
    session, _host, _p2, _p3 = _revealing_room()
    context, page = _tv(browser, live_server, session.code)
    try:
        assert page.locator("[data-rate]").count() == 0
        assert page.locator("[data-advance-btn]").count() == 0
        assert page.locator("[data-start-btn]").count() == 0
        assert page.locator("[data-share-card]").count() == 0
        assert page.locator("[data-booth-abandon]").count() == 0
        # Visible ones only: the install tip's dismiss button is in the
        # markup on every page and hidden on all of them.
        visible = page.evaluate(
            "() => [...document.querySelectorAll('button')]"
            ".filter(b => b.getClientRects().length).map(b => b.dataset.muteToggle !== undefined"
            " ? 'mute' : (b.textContent || b.className).trim().slice(0, 30))"
        )
        assert visible == ["mute"], f"the TV grew a control: {visible}"
    finally:
        context.close()


def test_the_tv_shows_the_meme_and_the_live_counts(browser, live_server):
    session, host, p2, p3 = _revealing_room()
    submission = game.reveal_order(game.current_round(session))[0]
    for rater in (host, p2, p3):
        if submission.player_id == rater.id:
            continue
        game.rate_submission(session, rater, 1, submission.id, Vote.LOVE)

    context, page = _tv(browser, live_server, session.code)
    try:
        assert page.locator(".memz-tv-meme").count() == 1
        love = page.locator('[data-tv-count="love"]')
        assert love.count() == 1
        assert love.inner_text().strip() == "2"
        # The meme really is the biggest thing on the wall.
        box = page.locator(".memz-tv-meme").bounding_box()
        assert box["height"] > TV_VIEW["height"] * 0.5, f"the meme is only {box['height']}px tall"
    finally:
        context.close()


def test_the_counts_move_without_the_screen_being_rebuilt(browser, live_server):
    """Patched in place, not re-rendered: rebuilding the strip on every
    poll would restart the bump animation on numbers that did not move, and
    the whole point of a count on the wall is that a *change* is visible."""
    session, host, p2, p3 = _revealing_room()
    submission = game.reveal_order(game.current_round(session))[0]
    first = next(r for r in (host, p2, p3) if r.id != submission.player_id)
    game.rate_submission(session, first, 1, submission.id, Vote.LOVE)

    context, page = _tv(browser, live_server, session.code)
    try:
        el = page.locator('[data-tv-count="love"]')
        assert el.inner_text().strip() == "1"
        # Mark the node, let one more verdict land, and check the same node
        # is still there holding the new number.
        page.evaluate("document.querySelector('[data-tv-count=\"love\"]').dataset.witness = 'yes'")
        second = next(r for r in (host, p2, p3) if r.id not in (submission.player_id, first.id))
        game.rate_submission(session, second, 1, submission.id, Vote.LOVE)
        page.wait_for_timeout(1600)
        assert el.inner_text().strip() == "2"
        assert page.evaluate(
            "document.querySelector('[data-tv-count=\"love\"]').dataset.witness"
        ) == "yes", "the reaction strip was rebuilt instead of updated"
    finally:
        context.close()


# ----------------------------------------------- it shows nothing extra


def test_the_tv_never_names_who_made_the_meme_on_screen(browser, live_server):
    """Rule 4.7.1 is not weakened by the screen being shared. If anything
    the wall is the worst place to break it: everyone is looking at it."""
    session, _host, _p2, _p3 = _revealing_room()
    context, page = _tv(browser, live_server, session.code)
    try:
        text = page.evaluate("() => document.body.innerText")
        for nickname in ("אבי", "מיכל", "יונתן"):
            assert nickname not in text, f"the reveal screen named {nickname}"
    finally:
        context.close()


def test_the_tv_lobby_shows_the_code_the_qr_and_who_is_in(browser, live_server):
    session, _host = game.create_session(
        host_user=None, round_count=1, round_seconds=60, vote_seconds=20, host_nickname="אבי",
    )
    game.join_session(session, "מיכל")
    context, page = _tv(browser, live_server, session.code)
    try:
        text = page.evaluate("() => document.body.innerText")
        assert session.code in text
        assert "מיכל" in text and "אבי" in text
        assert page.locator(".memz-tv-qr").count() == 1
        # The code is the single biggest thing in the room.
        code_box = page.locator(".memz-tv-code").bounding_box()
        assert code_box["height"] > 70, f"the join code is only {code_box['height']}px tall"
    finally:
        context.close()


# ------------------------------------------------- the standings move


def test_the_standings_are_keyed_by_player_so_they_can_be_animated():
    """FLIP needs a stable identity per row: measure where each row is,
    rebuild, measure again, play the difference backwards. Without
    `data-rank-id` the rows are anonymous and the reorder can only be a
    list that suddenly appears in a new order."""
    js = open("static/memz/game.js", encoding="utf-8").read()
    assert "data-rank-id" in js
    block = js[js.index("function flipStandings"):js.index("function renderTvResult")]
    assert "getBoundingClientRect" in block
    assert "requestAnimationFrame" in block
    assert "prefers-reduced-motion" in block, "the reorder must be skippable"


def test_the_tv_result_lists_every_player_with_a_score(browser, live_server):
    session, host, p2, p3 = _revealing_room()
    order = game.reveal_order(game.current_round(session))
    for index, submission in enumerate(order):
        _park_reveal(session, index, hold_seconds=0)
        for rater in (host, p2, p3):
            if submission.player_id == rater.id:
                continue
            game.rate_submission(session, rater, 1, submission.id, Vote.LOVE if index == 0 else Vote.MEH)
    game.advance(session, host)
    session.refresh_from_db()

    context, page = _tv(browser, live_server, session.code)
    try:
        rows = page.locator("[data-rank-id]")
        assert rows.count() == 3
        text = page.evaluate("() => document.body.innerText")
        for nickname in ("אבי", "מיכל", "יונתן"):
            assert nickname in text
        # The leader is marked, so a glance across a room finds the top.
        assert page.locator(".memz-tv-rank.is-leader").count() == 1
    finally:
        context.close()


# ------------------------------------------------------- the phone is not the TV


def test_the_phone_did_not_inherit_the_tv_layout(browser, live_server):
    """`memz-tvmode` releases the 560px phone column, so it must go on
    only for the screen view. A phone that picked it up would lose the
    whole layout the app is built around."""
    session, host, _p2, _p3 = _revealing_room()
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    try:
        assert page.evaluate("() => document.documentElement.classList.contains('memz-tvmode')") is False
        assert page.locator(".memz-tv").count() == 0
        # ...and the phone still has its own reveal screen: either the
        # three verdict buttons, or the line the meme's own author gets
        # instead of them (Rule 4.6.1). Which of the two depends on whose
        # meme the slideshow happens to be on.
        assert page.locator("[data-rate]").count() >= 1 or             page.locator("[data-innocent-face]").count() == 1
    finally:
        context.close()


def test_the_tv_stylesheet_is_scoped_and_cannot_leak_onto_a_phone():
    css = open("static/memz/memz.css", encoding="utf-8").read()
    start = css.index("/* ---- SPR-W.4: the TV show")
    # Bounded to the TV section itself. The first version read to the end
    # of the file, so the next sprint's unrelated rules appended below it
    # were read as TV rules and failed this — the test was describing
    # "everything after this point", not "the TV stylesheet".
    end = css.index("/* SPR-W.5:", start)
    block = css[start:end]
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("/*", "*", "}", "@", "to ", "from ")) or ":" in stripped.split("{")[0] and "{" not in stripped:
            continue
        if stripped.endswith("{") and not stripped.startswith("."):
            continue
        if stripped.endswith("{"):
            selector = stripped[:-1].strip()
            assert re.match(r"^\.memz-tv", selector) or ".memz-tv" in selector, \
                f"a TV rule that is not scoped to the TV: {selector}"
