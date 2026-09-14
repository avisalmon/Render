"""Where the family is in the trip right now (spec §4.6, 2026-09-14).

Home used to show the first item of the first day, forever. On the road
that is useless; what matters is today's day and the stop you're on, or the
next one. `position()` answers that on the trip's own clock
(`Trip.timezone`, New York for this trip — the server's clock is neither
Israel's nor the road's).

Pure: takes `now` so tests can pin it. Three phases:

- before: days to go, and the first day so there's something to open;
- during: today's day, the planned item happening now (or the next one
  today, or tomorrow's first if today is done);
- after: the trip is over.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_timezone

from . import schedule
from .models import ItineraryItem


def now_for(trip):
    try:
        zone = ZoneInfo(trip.timezone)
    except Exception:  # noqa: BLE001 - a bad name in the field should not take Home down
        zone = ZoneInfo("UTC")
    return dj_timezone.now().astimezone(zone)


def _planned(items):
    return [i for i in items if i.tag == ItineraryItem.PLAN and i.start is not None]


def _day_for(trip, today):
    days = list(trip.days.all())
    for day in days:
        if day.covers(today):
            return day
    # A day with no date yet (never backfilled): fall back to the last day
    # that has started, so the page still lands somewhere sensible.
    started = [d for d in days if d.date is not None and d.date <= today]
    return started[-1] if started else (days[0] if days else None)


def _first_planned(day):
    if day is None:
        return None
    planned = _planned(schedule.compute(day))
    return planned[0] if planned else None


def position(trip, now=None):
    if now is None:
        now = now_for(trip)
    today = now.date()

    if today < trip.start_date:
        day = trip.days.first()
        return {
            "phase": "before", "days_to_go": (trip.start_date - today).days,
            "day": day, "item": _first_planned(day), "label": "First up",
        }
    if today > trip.end_date:
        return {"phase": "after", "day": None, "item": None, "label": ""}

    day = _day_for(trip, today)
    if day is None:
        return {"phase": "during", "day": None, "item": None, "label": ""}
    planned = _planned(schedule.compute(day))
    clock = now.time()
    for item in planned:
        wraps = item.end < item.start  # runs past midnight
        if (item.start <= clock < item.end) or (wraps and (clock >= item.start or clock < item.end)):
            return {"phase": "during", "day": day, "item": item, "label": "Now"}
    upcoming = [i for i in planned if i.start > clock]
    if upcoming:
        return {"phase": "during", "day": day, "item": upcoming[0], "label": "Next up"}
    days = list(trip.days.all())
    later = [d for d in days if d.order > day.order]
    if later:
        return {"phase": "during", "day": later[0], "item": _first_planned(later[0]), "label": "Tomorrow"}
    return {"phase": "during", "day": day, "item": None, "label": "Day's done"}
