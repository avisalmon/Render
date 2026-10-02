"""SPR-B.7.1 — days in a row, and what breaks one.

**The load-bearing test is `test_a_streak_survives_a_day_you_have_not_played_yet`.**
Counting naively, somebody who played yesterday and opens the app at nine this
morning has a streak of zero, so the app greets them by telling them they lost
the thing it is asking them to keep. That is the one decision in this module
worth arguing about, and the one a straightforward implementation gets wrong.

Second: `test_a_streak_is_a_read_and_follows_a_hand_recorded_late`. The drill
queues hands in localStorage when the phone is offline, so attempts arrive out
of order by design. A stored counter drifts the first time that happens, and a
number about somebody's own effort that quietly goes wrong is worse than no
number.

Traces: REQ-B.5.8.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

pytestmark = pytest.mark.sprb71

PASSWORD = "sprb71-pass-4409"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="streak@example.com", email="streak@example.com", password=PASSWORD
    )


def _player(user):
    from blackjack.models import Player

    return Player.for_user(user)


def _hand_on(player, day, right=True, hour=20, minute=15):
    """One attempt, recorded at a given local date and time.

    `created_at` is `auto_now_add`, so it is set on insert and moved after.
    That is exactly what an out-of-order arrival looks like, which one of the
    tests below leans on.
    """
    from blackjack.models import Attempt, Cell

    cell = Cell.objects.filter(
        chart__rule_set=player.rule_set, kind="hard", player=16
    ).first()
    attempt = Attempt.objects.create(
        player=player,
        rule_set=player.rule_set,
        cell_kind=cell.kind,
        cell_player=cell.player,
        cell_dealer=cell.dealer,
        chosen=cell.action if right else next(a for a in "HSDP" if a != cell.action),
        correct=cell.action,
        correct_fallback=cell.fallback or cell.action,
        is_correct=right,
    )
    when = timezone.make_aware(
        timezone.datetime(day.year, day.month, day.day, hour, minute),
        timezone.get_current_timezone(),
    )
    Attempt.objects.filter(pk=attempt.pk).update(created_at=when)
    return attempt


def _days_ago(n):
    return timezone.localdate() - timedelta(days=n)


# ------------------------------------------------- the one that matters


def test_a_streak_survives_a_day_you_have_not_played_yet(client, person):
    """Yesterday and the day before, nothing yet today: still two, still alive.

    This is the whole decision. A streak that resets at midnight tells a person
    who has been showing up every evening that they have lost it, before they
    have had any chance to play, which is both untrue and a reason to close the
    app.
    """
    from blackjack import streaks

    player = _player(person)
    _hand_on(player, _days_ago(2))
    _hand_on(player, _days_ago(1))

    streak = streaks.of(player)
    assert streak.current == 2, "yesterday's streak was wiped by midnight"
    assert streak.alive is True
    assert streak.played_today is False
    assert streak.at_risk is True, "today is still open and the app did not say so"

    client.force_login(person)
    page = client.get("/blackjack/history/").content.decode()
    assert "עוד לא שיחקתם היום" in page


def test_a_streak_is_a_read_and_follows_a_hand_recorded_late(client, person):
    """Nothing is stored, so a hand that arrives out of order still counts.

    The offline queue in the drill holds hands on the phone and posts them when
    the network comes back, so yesterday's hand can land after today's. A
    counter incremented at record time gets that wrong forever; a read over
    `Attempt` cannot.
    """
    from blackjack import streaks
    from blackjack.models import Attempt

    player = _player(person)
    _hand_on(player, _days_ago(2))
    _hand_on(player, timezone.localdate())
    assert streaks.of(player).current == 1, "a gap at day one was counted through"

    _hand_on(player, _days_ago(1))          # the queued hand, arriving late
    assert streaks.of(player).current == 3, "a late hand did not join the run"

    assert not [f for f in Attempt._meta.get_fields() if "streak" in f.name], (
        "a streak was stored on the attempt instead of being read from it"
    )
    from blackjack.models import Player

    assert not [f for f in Player._meta.get_fields() if "streak" in f.name], (
        "a streak counter was stored on the player and will drift"
    )


# ------------------------------------------------- the rest of the shape


def test_a_missed_day_breaks_it_and_the_best_is_kept(client, person):
    """Broken is zero now, and the record stands. Losing a run should not erase
    the evidence that you once had one, because that evidence is the argument
    for starting again."""
    from blackjack import streaks

    player = _player(person)
    for day in (9, 8, 7, 6):
        _hand_on(player, _days_ago(day))     # four in a row, long gone
    _hand_on(player, _days_ago(3))           # a lone day, also broken

    streak = streaks.of(player)
    assert streak.alive is False
    assert streak.current == 0
    assert streak.best == 4, "the longest run was forgotten"
    assert streak.at_risk is False, "a broken streak was reported as at risk"

    client.force_login(person)
    page = client.get("/blackjack/history/").content.decode()
    assert "הרצף נקטע" in page


def test_the_count_is_days_not_hands(person):
    """Twelve hands this evening is one day. A streak measures showing up."""
    from blackjack import streaks

    player = _player(person)
    for _ in range(12):
        _hand_on(player, timezone.localdate())

    streak = streaks.of(player)
    assert streak.current == 1
    assert streak.played_today is True
    assert streak.at_risk is False, "the app nagged somebody who already played"


def test_somebody_who_never_played_is_not_told_they_broke_anything(client, person):
    """No hands is no streak, and nothing to lose. The empty state of a
    gamification feature is where it most easily becomes discouraging."""
    from blackjack import streaks

    streak = streaks.of(_player(person))
    assert (streak.current, streak.best) == (0, 0)
    assert streak.alive is False and streak.at_risk is False

    client.force_login(person)
    page = client.get("/blackjack/history/").content.decode()
    assert "הרצף נקטע" not in page, "a brand-new person was told they broke a streak"
    assert "ימים ברצף" not in page


@override_settings(TIME_ZONE="Asia/Jerusalem")
def test_two_hands_on_one_local_date_are_one_day_even_across_utc_midnight(person):
    """Local dates, not UTC. A streak is about somebody's evenings.

    Both hands below are on the same local date: one at half past midnight, one
    at ten at night. In UTC they land on two different dates, so grouping by UTC
    would invent a second day and report a run of two where the person showed up
    once. Shifting every day by the same amount would not catch this, because a
    uniform shift leaves a run consecutive; the dates have to straddle the line.
    """
    from blackjack import streaks

    yesterday = _days_ago(1)
    player = _player(person)
    _hand_on(player, yesterday, hour=0, minute=30)   # 21:30 UTC, the day before
    _hand_on(player, yesterday, hour=22, minute=0)   # 19:00 UTC, the same day

    streak = streaks.of(player)
    assert streak.current == 1, "one evening was counted as two days by UTC"
    assert streak.best == 1
    assert streak.alive is True, "yesterday's hand was pushed out of range"


def test_the_streak_is_free(client, person):
    """Moved out of the paid tier deliberately: the thing that brings somebody
    back on a Tuesday is the engine of the product's own growth, and charging
    for it is charging to grow."""
    from blackjack.models import Player

    player = _player(person)
    _hand_on(player, _days_ago(1))
    _hand_on(player, timezone.localdate())

    # No entitlement, and the thirty free minutes long expired.
    Player.objects.filter(pk=player.pk).update(
        first_used_at=timezone.make_aware(timezone.datetime(2020, 1, 1, 12, 0))
    )

    client.force_login(person)
    page = client.get("/blackjack/drill/").content.decode()
    assert "bj-streak" in page, "the streak was hidden from a free account"
    assert "שיחקתם היום" in page


def test_the_badge_is_absent_rather_than_zero_on_the_drill(client, person):
    """A zero on the practice screen is a scold at the moment somebody is about
    to do the right thing. Nothing is better than nothing-shaped."""
    client.force_login(person)
    page = client.get("/blackjack/drill/").content.decode()
    assert 'class="bj-streak' not in page
