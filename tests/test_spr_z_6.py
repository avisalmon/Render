"""SPR-Z.6 — memz: delight, and the phone (docs/memz/backlog.md).
Spec references are docs/memz/spec.md rule numbers.

Every game state here is played through `memz.game` itself, round by
round, exactly the way SPR-Z.3's own suite insisted on (the_manager.md
Step 4a lesson #10: "build the state through the door the product uses").
The one deliberate exception is timestamps: `submitted_at` and
`caption_deadline` are nudged directly where a title's rule is *about*
timing (clutch), since waiting out a real countdown in a test would be
slow and flaky for no extra confidence.

Titles are asserted two ways: against `_compute_metrics` directly (so a
rule is checked on its own terms, not only on whichever player a
higher-priority title left it), and against `compute_titles` (so the
priority order and the one-title-per-player rule are checked too).
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from memz import game
from memz.models import MemeImage, Round
from memz.titles import (
    CLUTCH, CROWD_FAVOURITE, DARK_HORSE, JUDGES_FAVOURITE, MINIMALIST,
    PHILOSOPHER, SPEED, STREAK, THE_CROWD, UNANIMOUS,
    _compute_metrics, compute_titles,
)

pytestmark = [pytest.mark.sprz6, pytest.mark.django_db]


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
        img.file.save(f"z6-source-{i}.png", ContentFile(_png_bytes((20 * i, 80, 140))), save=True)


def _new_game(n_players=4, round_count=5, **kwargs):
    session, host = game.create_session(
        host_user=None, round_count=round_count, round_seconds=60, vote_seconds=20, **kwargs
    )
    names = ["שני", "גל", "דנה", "עומר", "יעל"]
    players = [host] + [game.join_session(session, names[i]) for i in range(n_players - 1)]
    game.start_session(session, host)
    return session, players


def _submit(session, player, text):
    round_obj = game.current_round(session)
    game.submit_caption(session, player, round_obj.number, caption_text=text)


def _show_reveal_slot(session, index):
    """Wind a running reveal so meme `index` is the one on screen — the
    same arithmetic `game.reveal_index` does (SPR-Z.10)."""
    from memz import conf

    round_obj = game.current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    elapsed = per_meme * index + per_meme / 2
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() + timezone.timedelta(seconds=per_meme * count - elapsed)
    )


def _love(session, round_obj, voter, target):
    """SPR-Z.10 translation of the old "voter picked target": an אוהב, cast
    in that meme's own slot in the reveal.

    The old model gave each player one pick per round, so anything they
    didn't pick simply went unrated — which is exactly what these title
    tests mean by their (voter, target) pairs, and why translating a pick
    to a LOVE keeps every one of their expectations intact. Crowd
    favourite, unanimous and the-crowd all count loves now (titles.py),
    for the same reason: with everyone rating everything, a raw row count
    would be the same number for everybody."""
    from memz.models import Vote

    order = game.reveal_order(round_obj)
    sub = round_obj.submissions.get(player=target, meme__isnull=False)
    _show_reveal_slot(session, [s.id for s in order].index(sub.id))
    game.rate_submission(session, voter, round_obj.number, sub.id, Vote.LOVE)


def _end_reveal_now(session, round_obj):
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() - timezone.timedelta(seconds=1)
    )
    game.sync(session)


def _play_round(session, host, captions, votes):
    """One full round to `done`: `captions` is [(player, text), ...] for
    everyone who submits (a player left out simply misses the round, spec
    Rule 4.4.3); `votes` is [(voter, target_player), ...]. Whatever the
    engine doesn't finish on its own (not everyone submitted or voted) is
    forced by pushing the relevant deadline into the past and syncing —
    the same "deadline actually firing" technique SPR-Z.3's own suite
    used, not a shortcut around the state machine."""
    for player, text in captions:
        _submit(session, player, text)
    round_obj = game.current_round(session)
    round_obj.refresh_from_db()
    if round_obj.status == Round.CAPTIONING:
        Round.objects.filter(pk=round_obj.pk).update(caption_deadline=timezone.now() - timezone.timedelta(seconds=1))
        game.sync(session)
    round_obj.refresh_from_db()
    if round_obj.status == Round.REVEALED:
        # SPR-Z.10: the verdicts are cast *inside* the reveal, and the
        # reveal ending is what finishes the round -- there is no separate
        # voting phase to advance into any more (outside Judge mode).
        for voter, target in votes:
            _love(session, round_obj, voter, target)
        round_obj.refresh_from_db()
        if round_obj.status == Round.REVEALED:
            _end_reveal_now(session, round_obj)

    round_obj.refresh_from_db()
    assert round_obj.status == Round.DONE
    game.advance(session, host)   # done -> next round, or the podium
    return round_obj


# ---------------------------------------------------------------- titles


def test_crowd_favourite_is_whoever_received_the_most_votes_total():
    session, (host, a, b, c) = _new_game(round_count=2)
    _play_round(session, host, [(host, "א"), (a, "ב"), (b, "ג"), (c, "ד")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "א"), (a, "ב"), (b, "ג"), (c, "ד")], [(a, b), (b, host), (c, host)])
    metrics = _compute_metrics(session)
    assert metrics[CROWD_FAVOURITE][a.id] == 3   # every vote in round 1, none since
    assert compute_titles(session)[a.id] == CROWD_FAVOURITE


def test_unanimous_is_a_round_won_with_every_vote_cast():
    session, (host, a, b, c) = _new_game(round_count=1)
    # a doesn't vote at all this round; every vote that *was* cast agrees.
    _play_round(session, host, [(host, "א"), (a, "ב"), (b, "ג"), (c, "ד")], [(host, a), (b, a), (c, a)])
    metrics = _compute_metrics(session)
    assert metrics[UNANIMOUS] == {a.id: 1}


def test_streak_is_two_or_more_consecutive_wins():
    session, (host, a, b, c) = _new_game(round_count=3)
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, host), (b, host), (c, host)])
    metrics = _compute_metrics(session)
    assert metrics[STREAK] == {a.id: 2}
    assert host.id not in metrics[STREAK]   # one win, not a streak


def test_clutch_is_a_win_submitted_in_the_last_five_seconds():
    session, (host, a, b, c) = _new_game(round_count=1)
    for player, text in [(host, "1"), (a, "2"), (b, "3"), (c, "4")]:
        _submit(session, player, text)
    round_obj = game.current_round(session)
    a_sub = round_obj.submissions.get(player=a)
    # a's submission lands 3 seconds before the deadline — inside the window.
    Round.objects.filter(pk=round_obj.pk).update(caption_deadline=a_sub.submitted_at + timezone.timedelta(seconds=3))
    for voter, target in [(host, a), (b, a), (c, a)]:
        _love(session, round_obj, voter, target)
    # a never rated anyone, so the reveal isn't over on its own — force its
    # deadline, same as a real round ending with one player still silent.
    _end_reveal_now(session, round_obj)
    game.advance(session, host)
    metrics = _compute_metrics(session)
    assert metrics[CLUTCH] == {a.id: 1}


def test_clutch_does_not_credit_a_win_submitted_early():
    session, (host, a, b, c) = _new_game(round_count=1)
    for player, text in [(host, "1"), (a, "2"), (b, "3"), (c, "4")]:
        _submit(session, player, text)
    round_obj = game.current_round(session)
    a_sub = round_obj.submissions.get(player=a)
    # a's submission is nowhere near the deadline this time.
    Round.objects.filter(pk=round_obj.pk).update(caption_deadline=a_sub.submitted_at + timezone.timedelta(minutes=5))
    for voter, target in [(host, a), (b, a), (c, a)]:
        _love(session, round_obj, voter, target)
    _end_reveal_now(session, round_obj)
    game.advance(session, host)
    metrics = _compute_metrics(session)
    assert metrics[CLUTCH] == {}


def test_speed_is_first_to_submit_across_the_most_rounds():
    session, (host, a, b, c) = _new_game(round_count=2)
    # host submits first both rounds (call order sets submitted_at order).
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, b), (b, c), (c, b)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, b), (b, c), (c, b)])
    metrics = _compute_metrics(session)
    assert metrics[SPEED] == {host.id: 2}


def test_dark_horse_is_the_biggest_climb_in_the_final_two_rounds():
    session, (host, a, b, c) = _new_game(round_count=3)
    # a loses round 1 outright, then wins the last two — the climb is real.
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, host), (b, host), (c, host)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    metrics = _compute_metrics(session)
    assert metrics[DARK_HORSE].get(a.id, 0) > metrics[DARK_HORSE].get(host.id, 0)


def test_philosopher_and_minimalist_are_the_longest_and_shortest_scored_captions():
    session, (host, a, b, c) = _new_game(round_count=1)
    long_caption = "כ" * 130
    short_caption = "קצר"
    _play_round(
        session, host,
        [(host, long_caption), (a, short_caption), (b, "משהו באורך בינוני שם"), (c, "עוד משהו באורך בינוני")],
        [(host, a), (b, a), (c, a)],   # a wins, so its short caption also "scored"
    )
    metrics = _compute_metrics(session)
    assert metrics[PHILOSOPHER][host.id] == len(long_caption)   # longest of *all* captions, win or not
    assert metrics[MINIMALIST][a.id] == len(short_caption)      # shortest among captions that scored


def test_the_crowd_is_whoever_agreed_with_the_round_winner_most():
    session, (host, a, b, c) = _new_game(round_count=2)
    # round 1: b wins (2 votes); host and a backed b, c didn't.
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, b), (a, b), (c, host)])
    # round 2: c wins (2 votes); host backed c again, c itself abstains.
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, c), (a, host), (b, c)])
    metrics = _compute_metrics(session)
    assert metrics[THE_CROWD].get(host.id, 0) == 2   # agreed with the winner both rounds
    assert metrics[THE_CROWD].get(c.id, 0) == 0       # never once voted with the round's winner


def test_judges_favourite_only_exists_in_judge_mode():
    session, (host, a, b, c) = _new_game(round_count=2, scoring_mode="judge")
    for _ in (1, 2):
        round_obj = game.current_round(session)
        judge = round_obj.judge
        others = [p for p in (host, a, b, c) if p.id != judge.id]
        target = others[0]
        for player in (host, a, b, c):
            _submit(session, player, f"כיתוב {player.nickname}")
        round_obj.refresh_from_db()
        if round_obj.status == Round.CAPTIONING:
            Round.objects.filter(pk=round_obj.pk).update(caption_deadline=timezone.now() - timezone.timedelta(seconds=1))
            game.sync(session)
        game.advance(session, host)
        sub = round_obj.submissions.get(player=target, meme__isnull=False)
        game.cast_vote(session, judge, round_obj.number, sub.id)
        game.advance(session, host)   # judge's single vote decides it, then done -> next
    metrics = _compute_metrics(session)
    assert metrics[JUDGES_FAVOURITE] == {host.id: 2}   # picked both rounds, by two different judges
    assert metrics[UNANIMOUS] == {}   # a single voter is never a meaningful "unanimous"
    assert metrics[THE_CROWD] == {}   # ...nor a meaningful "crowd"


def test_no_two_players_share_a_title():
    session, (host, a, b, c) = _new_game(round_count=3)
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, host), (b, host), (c, host)])
    titles = compute_titles(session)
    assert len(titles.values()) == len(set(titles.values()))


def test_a_title_with_nobody_qualifying_is_not_forced_on_anyone():
    # Relaxed mode: no votes, no points, so every vote-shaped title has
    # nothing to grab onto — and none of them should appear.
    session, (host, a, b) = _new_game(n_players=3, round_count=1, game_mode="relaxed")
    round_obj = game.current_round(session)
    for player, text in [(host, "1"), (a, "2"), (b, "3")]:
        game.submit_caption(session, player, round_obj.number, caption_text=text)
    game.advance(session, host)   # revealed -> done: relaxed never votes (F-Z.4.3)
    round_obj.refresh_from_db()
    assert round_obj.status == Round.DONE
    titles = compute_titles(session)
    for banned in (CROWD_FAVOURITE, UNANIMOUS, STREAK, CLUTCH, THE_CROWD, DARK_HORSE, JUDGES_FAVOURITE):
        assert banned not in titles.values()


def test_titles_are_recomputed_not_stored():
    """Rule 9.2.1: nothing about a title lives in the database, so calling
    compute_titles twice on the same finished session is deterministic."""
    session, (host, a, b, c) = _new_game(round_count=1)
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    assert compute_titles(session) == compute_titles(session)


def test_titles_with_no_players_is_empty_not_an_error():
    session, _host = game.create_session(host_user=None, round_count=3, round_seconds=60, vote_seconds=20)
    session.players.all().delete()   # an edge case no real game reaches, but compute_titles must not blow up
    assert compute_titles(session) == {}


# ---------------------------------------------------------------- stats


def test_lifetime_stats_count_only_this_users_own_hosted_remembered_games():
    from memz.stats import lifetime_stats

    host_user = User.objects.create_user("z6host", email="z6host@example.com", password="x")
    session, (host, a, b, c) = _new_game(round_count=1)
    # Rehost as a logged-in user so the session is actually "remembered"
    # (spec §2.2: remembered is a property of the host, not the game).
    session.host_user = host_user
    session.remembered = True
    session.save(update_fields=["host_user", "remembered"])
    host.user = host_user
    host.save(update_fields=["user"])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(a, host), (b, host), (c, host)])
    stats = lifetime_stats(host_user)
    assert stats["games"] == 1
    assert stats["wins"] == 1   # host got all 3 votes, nobody else scored
    assert stats["votes_received"] == 3
    assert stats["best_meme"] is not None
    assert stats["best_meme_votes"] == 3


def test_lifetime_stats_for_a_user_with_no_remembered_games_is_all_zero():
    from memz.stats import lifetime_stats

    user = User.objects.create_user("z6empty", email="z6empty@example.com", password="x")
    assert lifetime_stats(user) == {
        "games": 0, "wins": 0, "votes_received": 0, "titles_earned": 0,
        "best_meme": None, "best_meme_votes": 0,
    }


def test_lifetime_stats_ignore_a_session_this_user_only_played_in_not_hosted():
    from memz.stats import lifetime_stats

    guest_user = User.objects.create_user("z6guest", email="z6guest@example.com", password="x")
    session, (host, a, b, c) = _new_game(round_count=1)
    a.user = guest_user   # a played, but the session belongs to no logged-in host
    a.save(update_fields=["user"])
    _play_round(session, host, [(host, "1"), (a, "2"), (b, "3"), (c, "4")], [(host, a), (b, a), (c, a)])
    assert lifetime_stats(guest_user)["games"] == 0


# ---------------------------------------------------------------- the phone
#
# F-Z.6.6's three new guard claims — no native dialog, no reload after an
# action, every control that hits the network disables itself — proved in
# a real browser against a real lobby, not asserted about the markup.
# `browser` is test_memz_screens.py's own fixture, imported rather than
# redefined so there is exactly one Chromium launch policy in this suite.

from tests.test_memz_screens import PHONE, browser  # noqa: E402


def _lobby_world():
    session, host = game.create_session(host_user=None, round_count=3, round_seconds=60, vote_seconds=20)
    game.join_session(session, "שני")
    game.join_session(session, "גל")
    return session, host


_DELAY_NEXT_FETCH_JS = """
(function () {
  var real = window.fetch;
  window.__delayNextFetch = false;
  window.fetch = function () {
    var args = arguments;
    if (window.__delayNextFetch) {
      window.__delayNextFetch = false;   // one-shot: only the request under test is slow
      return new Promise(function (resolve) {
        setTimeout(function () { resolve(real.apply(window, args)); }, 300);
      });
    }
    return real.apply(window, args);
  };
})();
"""


@pytest.fixture
def _phone_page(browser, live_server, db):
    playwright = pytest.importorskip("playwright.sync_api")
    session, host = _lobby_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "window.__memzNav = 0; window.addEventListener('pagehide', () => { window.__memzNav++; });"
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
        + _DELAY_NEXT_FETCH_JS
    )
    dialogs = []
    page = context.new_page()
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    yield page, dialogs
    context.close()


def test_starting_a_game_never_reloads_or_opens_a_native_dialog(_phone_page):
    page, dialogs = _phone_page
    page.click("[data-start-btn]")
    page.wait_for_timeout(600)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-captioning"
    assert page.evaluate("window.__memzNav") == 0, "starting the game navigated the page instead of patching it"
    assert not dialogs, f"a native dialog reached the reader: {dialogs}"


def test_the_start_button_disables_itself_while_the_request_is_in_flight(_phone_page):
    page, _dialogs = _phone_page

    # The fetch behind this one click is held open for 300ms (init script),
    # so the in-flight moment is long enough to actually observe.
    page.evaluate("window.__delayNextFetch = true")
    page.click("[data-start-btn]")
    page.wait_for_timeout(60)
    assert page.eval_on_selector("[data-start-btn]", "el => el.disabled") is True, (
        "the start button still looked tappable while its own request was in flight (spec Rule 11.1)"
    )
    page.wait_for_timeout(600)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-captioning"


def _captioning_world(round_count=3):
    session, host = game.create_session(host_user=None, round_count=round_count, round_seconds=60, vote_seconds=20)
    p2 = game.join_session(session, "שני")
    p3 = game.join_session(session, "גל")
    game.start_session(session, host)
    return session, host, p2, p3


def test_typing_a_caption_survives_the_poll_that_used_to_rebuild_it(browser, live_server, db):
    """2026-09-16 QA fix (Avi, live-testing the real game): captioning
    polls the server every second (spec §12.4); the old renderCaptioning
    rebuilt the whole screen on every single poll, tearing out the
    <textarea> a player might be actively typing in -- on a phone this
    dismisses the keyboard, and the freshly rebuilt (empty) textarea
    grabs no focus back, so whatever was typed is simply gone. Proven
    here across several real poll cycles: type into the textarea, wait
    out multiple 1-second polls, the text and the focus are both still
    there."""
    pytest.importorskip("playwright.sync_api")
    session, host, _p2, _p3 = _captioning_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-captioning"

    textarea = page.locator("[data-caption-input]")
    textarea.click()
    textarea.type("שלום זה מבחן")
    # Outlive several 1-second poll cycles -- this is exactly the window
    # the old bug fired in, every single tick.
    page.wait_for_timeout(3500)
    assert textarea.input_value() == "שלום זה מבחן", "a poll tick wiped out what was typed"
    assert page.evaluate("document.activeElement === document.querySelector('[data-caption-input]')"), (
        "a poll tick stole focus from the textarea (the keyboard-dismiss bug)"
    )


def test_the_captioning_screen_still_updates_once_something_real_changes(browser, live_server, db):
    """The fix above must skip redundant rebuilds, not get stuck: once
    *this* player actually submits, the very next poll has to show it."""
    pytest.importorskip("playwright.sync_api")
    session, host, _p2, _p3 = _captioning_world()
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)

    page.fill("[data-caption-input]", "כיתוב שלי")
    page.click("[data-caption-form] button[type=submit]")
    page.wait_for_timeout(600)
    assert "שלחתם" in page.inner_text("[data-screen]"), "submitting did not make it to the screen"


def _park_reveal_on(session, index, hold_seconds=0):
    """Put meme `index` on screen by driving `reveal_deadline`, rather than
    waiting out real seconds to get there.

    This test used to race the clock: the fixture started the reveal, then
    every assertion had to land inside meme 1's slot before it moved on.
    That held at 4 seconds a meme by luck and at 10 by more luck -- in a
    full-suite run, launching a browser can eat a whole slot, and the first
    assertion then finds meme 2. Nothing here is about elapsed time; it is
    about which meme the arithmetic picks, so the arithmetic is what gets
    set.

    `hold_seconds` pins it *indefinitely* on the first meme, and only the
    first: it works by making the computed elapsed time negative, and the
    index clamps negatives to 0. Use it to survive a slow page load; for
    any later slot pass nothing and rely on that slot's own width."""
    from memz import conf

    round_obj = game.current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    elapsed = per_meme * index + per_meme / 2
    Round.objects.filter(pk=round_obj.pk).update(
        reveal_deadline=timezone.now() + timezone.timedelta(
            seconds=per_meme * count - elapsed + hold_seconds
        )
    )


def _revealed_world(settings):
    """Three real submissions, all captioned, so the round has already
    moved itself into `revealed` by the time the page loads -- same
    server-authoritative path as a real game, just driven directly
    instead of through three browsers."""
    session, host, p2, p3 = _captioning_world(round_count=1)
    round_obj = game.current_round(session)
    for player in (host, p2, p3):
        game.submit_caption(session, player, round_obj.number, caption_text=f"כיתוב {player.nickname}")
    round_obj.refresh_from_db()
    assert round_obj.status == Round.REVEALED
    return session, host, round_obj


def test_the_reveal_screen_shows_one_meme_at_a_time_not_a_grid(browser, live_server, db, settings):
    """2026-09-16 QA fix (Avi, live-testing the real game): "אני רוצה
    חוויה שבעצם כל המשתתפים רואים את הבדיחות אחת אחת... ולא את כולם
    ביחד" -- one joke at a time, not a grid everyone sees at once
    (F-Z.3.9, tracked since SPR-Z.3, never built until now)."""
    pytest.importorskip("playwright.sync_api")
    session, host, round_obj = _revealed_world(settings)
    _park_reveal_on(session, 0, hold_seconds=180)
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    context.add_init_script(
        "localStorage.setItem(%r, %r);" % (f"memz.player.{session.code}", host.guest_token)
    )
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/", wait_until="domcontentloaded")
    page.wait_for_timeout(300)

    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-revealed"
    assert page.locator(".memz-reveal-image").count() == 1, "more than one meme showing at once"
    assert page.locator(".memz-meme-grid").count() == 0, "the old all-at-once grid is still there"
    assert "1 מתוך 3" in page.inner_text("[data-reveal-progress]")
    first_src = page.locator(".memz-reveal-image").get_attribute("src")

    # Move the reveal on to the next meme and let one poll carry it to the
    # screen: still one at a time, and a different one, proven against the
    # rendered_url values already known server-side (never pixels).
    _park_reveal_on(session, 1)
    page.wait_for_timeout(1500)   # outlives a real 1-second poll on `revealed`
    assert page.locator(".memz-reveal-image").count() == 1
    progress = page.inner_text("[data-reveal-progress]")
    assert "2 מתוך 3" in progress, f"the slideshow never advanced to the next meme ({progress})"
    second_src = page.locator(".memz-reveal-image").get_attribute("src")
    assert second_src != first_src, "the slideshow never actually advanced to the next meme"

    expected = [s.meme.rendered.url for s in round_obj.submissions.select_related("meme").order_by("id")]
    assert first_src == expected[0]
    assert second_src == expected[1]


def test_the_big_screen_reveal_is_also_one_at_a_time(browser, live_server, db, settings):
    """spec §4.10: the shared TV gets the same slideshow, not its own
    grid -- if anything, one-at-a-time matters more there."""
    pytest.importorskip("playwright.sync_api")
    session, _host, _round_obj = _revealed_world(settings)
    _park_reveal_on(session, 0, hold_seconds=180)   # don't race the slot: see _park_reveal_on
    context = browser.new_context(viewport=PHONE)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/s/{session.code}/screen/", wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    assert page.locator("[data-screen]").get_attribute("data-screen") == "game-revealed"
    assert page.locator(".memz-reveal-image").count() == 1
    assert page.locator(".memz-meme-grid").count() == 0


def test_mute_toggle_persists_across_a_reload(browser, live_server, db):
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(f"{live_server.url}/memz/", wait_until="domcontentloaded")
    assert page.eval_on_selector("[data-mute-toggle]", "el => el.textContent") == "🔊"
    page.click("[data-mute-toggle]")
    assert page.evaluate("localStorage.getItem('memz.muted')") == "1"
    assert page.eval_on_selector("[data-mute-toggle]", "el => el.textContent") == "🔇"

    page.reload(wait_until="domcontentloaded")
    assert page.evaluate("localStorage.getItem('memz.muted')") == "1"
    assert page.eval_on_selector("[data-mute-toggle]", "el => el.textContent") == "🔇"

    page.click("[data-mute-toggle]")
    assert page.evaluate("localStorage.getItem('memz.muted')") == "0"
    context.close()
