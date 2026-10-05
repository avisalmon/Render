"""The practice log and the streak, read from the sittings a player has had.

Nothing here is stored. A PracticeSession is the fact (a sitting at the piano and the seconds the
band ran or a note was played); the day's minutes, whether the goal was met, the streak and the
log are reads over them. A day is the player's own day, in `Player.timezone`, because a streak
that breaks at midnight in a country the player is not in is a streak nobody can trust. A sitting
belongs to the day it started on.

The goal is whatever `Player.daily_goal_minutes` is now, for every day in the log: change it and
the past is read against the new number. Today is pending until the goal is met, and does not
break the streak until the day has ended.
"""

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from .models import PracticeSession

LOG_DAYS = 30
MOST_LOG_DAYS = 366


def zone_of(player):
    """The player's own zone. A name the machine does not know reads as UTC: a page that cannot
    open because of a setting is worse than a day that starts a few hours off."""
    try:
        return ZoneInfo(player.timezone)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("UTC")


def seconds_by_day(player):
    """{local date: active seconds} over every sitting, in the player's own zone."""
    zone = zone_of(player)
    days = {}
    for started, seconds in PracticeSession.objects.filter(player=player).values_list("started_at", "active_seconds"):
        day = started.astimezone(zone).date()
        days[day] = days.get(day, 0) + seconds
    return days


def sittings_by_day(player):
    zone = zone_of(player)
    counts = {}
    for (started,) in PracticeSession.objects.filter(player=player, active_seconds__gt=0).values_list("started_at"):
        day = started.astimezone(zone).date()
        counts[day] = counts.get(day, 0) + 1
    return counts


def streaks(day_seconds, goal_seconds, today):
    """(current, best): the run of goal days that ends today, or yesterday while today is still
    pending, and the longest run there has ever been."""

    def met(day):
        return day_seconds.get(day, 0) >= goal_seconds

    last = today if met(today) else today - dt.timedelta(days=1)
    current = 0
    while met(last - dt.timedelta(days=current)):
        current += 1

    best = run = 0
    previous = None
    for day in sorted(d for d in day_seconds if met(d)):
        run = run + 1 if previous is not None and day - previous == dt.timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return current, max(best, current)


def report(player, now=None, days=LOG_DAYS):
    """Where the player stands today, the streak, and a log of the days they practised."""
    zone = zone_of(player)
    now = now or timezone.now()
    today = now.astimezone(zone).date()
    goal_seconds = player.daily_goal_minutes * 60
    by_day = seconds_by_day(player)
    sittings = sittings_by_day(player)
    current, best = streaks(by_day, goal_seconds, today)

    earliest = today - dt.timedelta(days=days - 1)
    shown = sorted({d for d, s in by_day.items() if s > 0 and earliest <= d <= today} | {today}, reverse=True)
    today_seconds = by_day.get(today, 0)
    return {
        "timezone": getattr(zone, "key", "UTC"),
        "today": today.isoformat(),
        "goal_minutes": player.daily_goal_minutes,
        "today_seconds": today_seconds,
        "today_minutes": today_seconds // 60,
        "goal_met": today_seconds >= goal_seconds,
        "streak": current,
        "best_streak": best,
        "log": [
            {
                "date": d.isoformat(),
                "seconds": by_day.get(d, 0),
                "minutes": by_day.get(d, 0) // 60,
                "goal_met": by_day.get(d, 0) >= goal_seconds,
                "sessions": sittings.get(d, 0),
            }
            for d in shown
        ],
    }
