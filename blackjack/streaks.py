"""Days in a row, and what breaks one.

REQ-B.5.8, and free. Avi moved this out of the paid tier on 2026-10-02: a
streak is what brings somebody back on a Tuesday, and charging for the thing
that brings people back is charging for the engine of your own growth.

Derived from `Attempt`, never stored. Everything in this app is a read over
that one table, and a stored streak is a number that goes wrong quietly: it
drifts the first time a hand is recorded out of order, which the offline queue
does by design.

**The decision worth arguing about is when a streak is still alive.** Counted
naively, somebody who opens the app at nine in the morning before playing has a
streak of zero, which is both wrong and a reason to stop opening it. A streak
runs up to the last day played, and is alive if that day is today or yesterday.
Today is a day you still have.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone


@dataclass(frozen=True)
class Streak:
    """What to say about somebody's run of days."""

    current: int          # days in a row up to the last one played
    best: int             # the longest run they have ever had
    played_today: bool
    alive: bool           # today or yesterday, so today can still be saved

    @property
    def at_risk(self):
        """Alive, but today has not been played yet. The only state worth
        nudging about, and the app does not nag about any other."""
        return self.alive and not self.played_today


def _days(player):
    """Every local date this person played a hand, newest first.

    Local, not UTC: a streak is about somebody's evenings, and a person who
    plays at eleven at night should not have it counted as tomorrow.
    """
    from .models import Attempt

    seen = {
        timezone.localtime(when).date()
        for when in Attempt.objects.filter(player=player).values_list("created_at", flat=True)
    }
    return sorted(seen, reverse=True)


def _runs(days):
    """Lengths of every consecutive run in a descending list of dates."""
    if not days:
        return []
    runs, length = [], 1
    for earlier, later in zip(days[1:], days, strict=False):
        if later - earlier == timedelta(days=1):
            length += 1
        else:
            runs.append(length)
            length = 1
    runs.append(length)
    return runs


def of(player):
    """This person's streak, computed fresh."""
    days = _days(player)
    if not days:
        return Streak(current=0, best=0, played_today=False, alive=False)

    runs = _runs(days)
    today = timezone.localdate()
    last = days[0]

    alive = last in (today, today - timedelta(days=1))
    return Streak(
        current=runs[0] if alive else 0,
        best=max(runs),
        played_today=last == today,
        alive=alive,
    )
