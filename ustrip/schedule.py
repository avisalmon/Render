"""The flow schedule (docs/ustrip/spec.md §4.1, decided 2026-09-14).

Times are computed, never stored. A day has a `start_time`; its items run
back to back in `order`, each taking `duration_minutes`. An item with a
`fixed_start` is an anchor — a flight, a timed ticket — and resets the clock
to that time; everything after it flows from there. So dragging an item to
a new position, or changing one duration, moves every time after it with
no bookkeeping: there is nothing to keep in sync because nothing is saved.

An anchor earlier than where the clock currently is wins anyway (it is a
fact about the world, the flow is an estimate), which is also how the
combined "Day 14–15" row can hold a 15:25 departure followed by an 08:55
landing the next morning.

Only *planned* items move the clock. An optional item is a candidate, not
a commitment: it is shown at the time it would take if chosen, but the
planned items after it are scheduled as if it were skipped — otherwise
three "maybe"s in a row would push dinner past midnight. A dropped
(rejected) item gets no time at all; it is kept for the record, struck
through, and the day is scheduled around it.
"""

from datetime import date, datetime, timedelta

from .models import ItineraryItem


def compute(day, items=None):
    """Return the day's items, each annotated with `.start` and `.end`
    (`datetime.time`, or None for a dropped item), in order. Pass `items`
    to reuse an already-fetched queryset (the day page and the API both do)."""
    if items is None:
        items = day.items.all()
    base = date(2000, 1, 1)
    clock = datetime.combine(base, day.start_time)
    scheduled = []
    for item in items:
        if item.tag == ItineraryItem.REJECTED:
            item.start = item.end = None
            scheduled.append(item)
            continue
        if item.fixed_start is not None:
            clock = datetime.combine(base, item.fixed_start)
        start = clock
        end = start + timedelta(minutes=item.duration_minutes or 0)
        item.start = start.time()
        item.end = end.time()
        if item.tag == ItineraryItem.PLAN:
            clock = end
        scheduled.append(item)
    return scheduled


def for_item(item):
    """Start/end of one item, computed in the context of its day."""
    for scheduled in compute(item.day):
        if scheduled.pk == item.pk:
            return scheduled.start, scheduled.end
    return None, None
