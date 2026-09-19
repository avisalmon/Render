"""ACT-Z.8 — memz: a second QA pass on the real game (docs/memz/spec.md,
docs/memz/backlog.md). Avi again: "אתה עדיין הפוך, גם כשאני יוצר את
המים... צריך לעשות שתעשה איזשהו אג'קס שלא צריך לרפרש את כל הדף."

Two unrelated findings this round:

1. The solo creator's live preview canvas never drew *anything* --
   `CreatorForm`'s caption widget never carried the `data-creator-caption`
   attribute `static/memz/creator.js` looks for, so `captionInput` was
   `null` and the very first `.addEventListener` call threw, before the
   canvas was ever drawn on. Once that was fixed and the preview actually
   started rendering, a second, real bug became visible: its hand-rolled
   bidi reshaper pre-reversed each Hebrew run's own letters for a
   PIL-style "no bidi awareness" renderer -- but Canvas `fillText` is not
   PIL, modern browsers already apply real Unicode bidi to canvas text,
   so the pre-reversed text got reversed *again*, scrambling every
   Hebrew word's own letters. Fixed by deleting the reshaper entirely and
   drawing the caption exactly as typed, with `ctx.direction` pinned to
   "rtl" (mirroring `render.py`'s own `base_dir="R"` pin).

2. Voting and the round-result screen both rebuilt their entire DOM on
   every single poll (every 1s while voting, every 2s for results),
   replaying the meme tiles' own pop-in animation -- and the vote-count
   number animation, for results -- the whole time someone was just
   looking at the screen trying to decide or read. Fixed the same way as
   captioning/reveal already were: skip the rebuild once nothing about
   the round has actually changed.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import game
from memz.forms_creator import CreatorForm
from memz.models import MemeImage, Round
from tests.test_memz_screens import PHONE, browser  # noqa: E402, F401 -- the shared phone fixture

pytestmark = [pytest.mark.actz8, pytest.mark.django_db]


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


@pytest.fixture
def public_image(db):
    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    img.file.save("z8-source.png", ContentFile(_png_bytes()), save=True)
    return img


@pytest.fixture(autouse=True)
def _seed_images(db):
    """The voting/result tests deal real rounds through `memz.game`
    itself, which needs a real bank to deal from -- without this every
    player gets no image at all and `submit_caption` refuses immediately."""
    for i in range(6):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"z8-actz8-source-{i}.png", ContentFile(_png_bytes((20 * i, 80, 140))), save=True)


# ------------------------------------------------------- the creator preview


def test_the_caption_widget_carries_the_attribute_the_preview_script_looks_for():
    """The bug in one sentence: `creator.js` reads
    `form.querySelector("[data-creator-caption]")`, and until this fix
    nothing in `CreatorForm` ever put that attribute on the textarea --
    so `captionInput` was `null`, and the next line's own
    `.addEventListener` call threw before the live preview ever drew a
    single frame."""
    form = CreatorForm()
    rendered = str(form["caption_text"])
    assert 'data-creator-caption' in rendered


def test_the_creator_preview_actually_draws_something(public_image, browser, live_server, db):
    """Direct proof the widget fix above is enough: the canvas has real,
    non-blank pixels on it once an image is selected, not just a
    correctly-tagged-but-still-empty box."""
    pytest.importorskip("playwright.sync_api")
    context = browser.new_context(viewport=PHONE)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/create/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    has_ink = page.evaluate("""
        () => {
          var c = document.querySelector('[data-creator-preview]');
          var ctx = c.getContext('2d');
          var data = ctx.getImageData(0, 0, c.width, c.height).data;
          for (var i = 0; i < data.length; i += 4) if (data[i+3] !== 0) return true;
          return false;
        }
    """)
    assert has_ink, "the preview canvas never drew anything at all"
    context.close()


def test_the_creator_preview_no_longer_scrambles_hebrew_letters(public_image, browser, live_server, db):
    """2026-09-16 QA fix, round 2 (Avi: "האותיות יצאו הפוכות", tested
    again after the first fix and still broken -- this time in the
    *live preview*, not the final rendered meme). Proven the same way as
    the render.py fix: no pixel-reading, no eyeballing a screenshot --
    the hand-rolled reshaper and its Hebrew-detector are simply gone from
    the shipped file, and `ctx.direction` is pinned to "rtl" so the
    browser's own (correct) bidi engine is what draws the text."""
    pytest.importorskip("playwright.sync_api")
    context = browser.new_context(viewport=PHONE)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/create/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    source = page.evaluate("""
        () => fetch('/static/memz/creator.js').then(r => r.text())
    """)
    assert "reshape(" not in source, "the double-reversing hand-rolled reshaper is still in the shipped file"
    assert 'direction = "rtl"' in source or "direction = 'rtl'" in source
    context.close()


# --------------------------------------------------- voting / result jankiness


def _voting_world():
    """A round sitting in the `voting` phase.

    SPR-Z.10: that phase only exists in Judge mode now — every other game
    collects its verdicts during the reveal and finishes with it — so this
    world is a judge game. The grid it renders, and the rebuild-every-poll
    bug this file exists to guard against, are the same ones."""
    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=30, vote_seconds=30, scoring_mode="judge",
    )
    p2 = game.join_session(session, "שתיים")
    p3 = game.join_session(session, "שלוש")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    Round.objects.filter(pk=round_obj.pk).update(reveal_deadline=timezone.now() - timezone.timedelta(seconds=1))
    game.sync(session)
    round_obj.refresh_from_db()
    assert round_obj.status == Round.VOTING
    return session, host, p2, p3, round_obj


def _rated_done_world():
    """A finished round, reached the SPR-Z.10 way: everyone rates each meme
    in its own slot in the reveal, then the reveal runs out."""
    from memz import conf
    from memz.models import Vote

    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    p2 = game.join_session(session, "שתיים")
    p3 = game.join_session(session, "שלוש")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()

    order = game.reveal_order(round_obj)
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    for index, submission in enumerate(order):
        Round.objects.filter(pk=round_obj.pk).update(
            reveal_deadline=timezone.now() + timezone.timedelta(
                seconds=per_meme * len(order) - (per_meme * index + per_meme / 2)
            )
        )
        for rater in (host, p2, p3):
            if submission.player_id == rater.id:
                continue
            game.rate_submission(session, rater, round_obj.number, submission.id, Vote.LOVE)

    Round.objects.filter(pk=round_obj.pk).update(reveal_deadline=timezone.now() - timezone.timedelta(seconds=1))
    game.sync(session)
    round_obj.refresh_from_db()
    assert round_obj.status == Round.DONE
    return session, host, p2, p3, round_obj


def test_the_voting_screen_stops_rebuilding_itself_every_poll(browser, live_server, db):
    """2026-09-16 QA fix, round 2: "בסוף שרואים את כולם ובוחרים איזה
    הכי מצחיקה, זה עושה רפרש כל הזמן" -- voting polls every second and
    used to rebuild the whole meme grid on every single one, replaying
    the tiles' pop-in animation the entire time someone was looking at
    them. Proven here by marking one real DOM node and confirming it
    survives a poll cycle -- a full rebuild would have destroyed and
    recreated it, wiping the marker out."""
    pytest.importorskip("playwright.sync_api")
    session, host, _p2, _p3, _round_obj = _voting_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-voting"

    page.evaluate("document.querySelector('.memz-meme-tile').dataset.testMarker = 'still-here'")
    page.wait_for_timeout(1300)   # outlives a real 1-second poll
    survived = page.evaluate("""
        () => { var t = document.querySelector('.memz-meme-tile'); return t && t.dataset.testMarker; }
    """)
    assert survived == "still-here", "the voting grid was rebuilt from scratch by a poll that changed nothing"


def test_the_result_screen_stops_rebuilding_itself_every_poll(browser, live_server, db):
    """Same fix, the round-result screen (score tallies are already
    final the moment `done` is reached, so nothing here should ever need
    a poll-driven rebuild)."""
    pytest.importorskip("playwright.sync_api")
    session, host, _p2, _p3, _round_obj = _rated_done_world()

    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-result"

    # ACT-Z.14: a scoring round's result is the leaderboard and nothing
    # else -- the meme tiles this used to mark are gone, because their
    # scores beside the table identified their authors (Rule 4.7.2). The
    # rebuild-every-poll risk is the same, so the marker moves to a row.
    page.evaluate("document.querySelector('.memz-player-row').dataset.testMarker = 'still-here'")
    page.wait_for_timeout(2300)   # outlives a real 2-second poll (the "done" status's own interval)
    survived = page.evaluate("""
        () => { var t = document.querySelector('.memz-player-row'); return t && t.dataset.testMarker; }
    """)
    assert survived == "still-here", "the result screen was rebuilt from scratch by a poll that changed nothing"
    assert page.locator(".memz-meme-tile").count() == 0, "a scoring round's result still shows the memes"
    assert "נקודות" not in page.inner_text("[data-screen]"), "a per-meme score is still on the result screen"


def test_the_big_screen_voting_view_also_stops_rebuilding_itself(browser, live_server, db):
    pytest.importorskip("playwright.sync_api")
    session, _host, _p2, _p3, _round_obj = _voting_world()
    context = browser.new_context(viewport=PHONE)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/screen/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-voting"

    page.evaluate("document.querySelector('.memz-meme-tile').dataset.testMarker = 'still-here'")
    page.wait_for_timeout(1300)
    survived = page.evaluate("""
        () => { var t = document.querySelector('.memz-meme-tile'); return t && t.dataset.testMarker; }
    """)
    assert survived == "still-here"


def test_the_rating_screen_does_not_rebuild_itself_under_a_thumb(browser, live_server, db):
    """SPR-Z.10 inherits this whole file's risk: the reveal is now where
    everyone taps, and it polls every second. A rebuild mid-slot would
    move the buttons out from under a thumb that is already on its way
    down — the same class of bug as the captioning keyboard (ACT-Z.7) and
    the voting grid above, on the screen that replaced them both."""
    pytest.importorskip("playwright.sync_api")
    from memz import conf
    from memz.models import Session

    session, host = game.create_session(host_user=None, round_count=1, round_seconds=30, vote_seconds=30)
    p2 = game.join_session(session, "שתיים")
    p3 = game.join_session(session, "שלוש")
    game.start_session(session, host)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    # Park the reveal on meme 1 of 3 for two minutes: a negative elapsed
    # time clamps the index to 0, so the slideshow can't move on under the
    # browser mid-test and turn a real rebuild into a false pass.
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() + timezone.timedelta(seconds=per_meme * 3 + 120)
    )
    assert Session.objects.get(pk=session.pk).status == "playing"

    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", p2.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-revealed"
    assert page.locator("[data-rate]").count() == 3, "the three verdict buttons aren't there"

    page.evaluate("document.querySelector('[data-rate]').dataset.testMarker = 'still-here'")
    page.wait_for_timeout(2300)   # outlives two real 1-second polls
    survived = page.evaluate("""
        () => { var b = document.querySelector('[data-rate]'); return b && b.dataset.testMarker; }
    """)
    assert survived == "still-here", "the rating screen was rebuilt by a poll that changed nothing"
