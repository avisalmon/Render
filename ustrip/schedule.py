"""The flow schedule (docs/ustrip/spec.md §4.1, decided 2026-09-14).

Times are computed, never stored. A day has a `start_time`; its items run
back to back in `order`, each taking `duration_minutes`. An item with a
`fixed_start` is an anchor — a flight, a timed ticket — and resets the clock
to that time; everything after it flows from there. So dragging an item to
a new position, or changing one duration, moves every time after it with
no bookkeeping: there is nothing to keep in sync because nothing is saved.

Only *planned* items move the clock. An optional item is a candidate, not
a commitment: it is shown at the time it would take if chosen (its own pin
if it has one, otherwise wherever the clock is) and the planned items after
it are scheduled as if it were skipped — otherwise three "maybe"s in a row
would push dinner past midnight. A dropped (rejected) item gets no time at
all; it is kept for the record, struck through, and the day is scheduled
around it.

**Overflow is reported, never refused and never auto-fixed** (Avi,
2026-09-14). The engine annotates what doesn't fit and the pages show it
where it happens; the family decides what to shorten, move, unpin or make
optional. Three things are measured:

- `overrun_minutes` / `overrun_into` on a planned item: it runs that many
  minutes into the next planned anchor. (The anchor still wins — it is a
  fact about the world — so the overrun is the part that gets cut.)
- `gap_before_minutes` on a planned anchor: free time between the previous
  planned item's end and this pin. A gap is not a conflict; it's where a
  new stop would fit.
- `past_day_end` on any timed item, and `schedule_over_minutes` on the day:
  it ends after the day's `end_time`.

An anchor much earlier than the clock (more than NEXT_DAY_TOLERANCE) is
taken to be the next morning, not a conflict — that is the combined
"Day 14–15" row: a 15:25 departure, then an 08:55 landing.

A *note* (`kind == NOTE`) is outside the schedule altogether (Avi,
2026-09-14): a reminder or a piece of information placed wherever it reads
best in the day's order. No time, no duration, never moves the clock, never
in a conflict or a gap. Any number of them, anywhere.
"""

from datetime import date, datetime, timedelta

from .models import ItineraryItem

NEXT_DAY_TOLERANCE = timedelta(hours=12)
BASE = date(2000, 1, 1)

ITEM_ANNOTATIONS = ("start", "end", "overrun_minutes", "overrun_into", "gap_before_minutes", "past_day_end")


def _minutes(delta):
    return int(delta.total_seconds() // 60)


def compute(day, items=None):
    """Return the day's items, each annotated (see ITEM_ANNOTATIONS), in
    order, and annotate `day` itself with `schedule_ends_at`,
    `schedule_over_minutes` and `schedule_conflicts`. Pass `items` to reuse
    an already-fetched queryset (the day page and the API both do)."""
    if items is None:
        items = day.items.all()
    start_dt = datetime.combine(BASE, day.start_time)
    end_dt = datetime.combine(BASE, day.end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    clock = start_dt
    last_planned = None
    scheduled = []
    for item in items:
        item.start = item.end = None
        item.overrun_minutes = 0
        item.overrun_into = None
        item.gap_before_minutes = 0
        item.past_day_end = False
        if item.tag == ItineraryItem.REJECTED or item.kind == ItineraryItem.NOTE:
            scheduled.append(item)
            continue

        if item.fixed_start is not None:
            anchor = datetime.combine(BASE, item.fixed_start)
            while anchor < clock - NEXT_DAY_TOLERANCE:
                anchor += timedelta(days=1)
            if item.tag == ItineraryItem.PLAN:
                # Both only mean something after a planned stop: before the
                # first one, the time since the day's start is just morning.
                if anchor < clock and last_planned is not None:
                    last_planned.overrun_minutes = _minutes(clock - anchor)
                    last_planned.overrun_into = item
                elif anchor > clock and last_planned is not None:
                    item.gap_before_minutes = _minutes(anchor - clock)
            start = anchor
        else:
            start = clock

        end = start + timedelta(minutes=item.duration_minutes or 0)
        item.start, item.end = start.time(), end.time()
        item.past_day_end = end > end_dt
        if item.tag == ItineraryItem.PLAN:
            clock = end
            last_planned = item
        scheduled.append(item)

    day.schedule_ends_at = clock.time() if last_planned is not None else None
    day.schedule_over_minutes = max(0, _minutes(clock - end_dt)) if last_planned is not None else 0
    day.schedule_conflicts = sum(
        1 for s in scheduled if s.tag == ItineraryItem.PLAN and (s.overrun_minutes or s.past_day_end)
    )
    return scheduled


def annotate(item):
    """Annotate one item in the context of its day (the detail page, the
    home card, a lone API representation)."""
    for scheduled in compute(item.day):
        if scheduled.pk == item.pk:
            for attr in ITEM_ANNOTATIONS:
                setattr(item, attr, getattr(scheduled, attr))
            return item
    for attr in ITEM_ANNOTATIONS:
        setattr(item, attr, None if attr in ("start", "end", "overrun_into") else 0)
    item.past_day_end = False
    return item


def for_item(item):
    """Start/end of one item, computed in the context of its day."""
    annotate(item)
    return item.start, item.end
