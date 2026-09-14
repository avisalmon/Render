"""REQ-M.34's other half: telling somebody a day is tomorrow.

Announcing an event has rung the bell since SPR-M.31. Reminding somebody it is
tomorrow needs something running without a person in front of it, which this
product has one standing rule about, and the rule is narrower than it looks.

**What REQ-M.87 actually forbids is unattended destruction.** "The machine
proposes, a person decides" was written about deletion, because deletion is the
one action here where a bug is irreversible: a purge that runs wrong at 04:00
has destroyed a teenager's work by the time anybody reads the log.

A reminder is the opposite shape. It creates nothing a person did not already
decide, destroys nothing, and its worst failure is a duplicate bell. So
reminders may run unattended and deletions still may not, and that line is
recorded here rather than left to be re-argued (Avi, 2026-09-14, "continue with
all of these", on a list that named this as the open decision).

**Once per event, and the row remembers.** `Event.reminded_at` is the guard
rather than a window calculation, because a job that runs twice, or a deploy
that shifts the schedule, must not ring the same bell again. A member who is
told twice about the same day stops reading the bell, and the bell is how they
hear about everything else.
"""

from datetime import timedelta

from django.utils import timezone

# How far ahead counts as "tomorrow". A day and a half rather than a day,
# because the job runs once daily and an event at 09:00 must not fall into the
# gap between two runs and be reminded about by nobody.
AHEAD = timedelta(hours=36)


def due_events():
    """Events happening soon that nobody has been reminded about yet."""
    from .models import Event

    now = timezone.now()
    return Event.objects.filter(
        cancelled_at__isnull=True,
        reminded_at__isnull=True,
        starts_at__gte=now,
        starts_at__lte=now + AHEAD,
    )


def send_reminders(*, apply=False):
    """Ring the bell for every event that is nearly here.

    Report-only unless `apply`, the same shape as `retention.purge_*`, because a
    job you cannot rehearse is a job people avoid running.

    Returns (events, people) so the caller can say what happened rather than
    just that it finished.
    """
    from .event_views import _audience
    from .models import Notification
    from .notify import notify

    events = list(due_events())
    if not apply:
        return len(events), sum(_audience(e).count() for e in events)

    told = 0
    for event in events:
        for student in _audience(event).select_related("user"):
            made = notify(
                student.user,
                Notification.EVENT,
                f"מחר: {event.title} · {event.starts_at:%H:%M}"
                + (f" · {event.place}" if event.place else ""),
                url="/matazim/calendar/",
            )
            if made is not None:
                told += 1

        # Stamped after the sending rather than before, so a crash halfway
        # through leaves the event un-stamped and the next run finishes it. The
        # cost of that choice is a possible duplicate for the people already
        # told, which is the right way round: somebody hearing twice is a
        # nuisance, somebody never hearing is the failure this exists to stop.
        event.reminded_at = timezone.now()
        event.save(update_fields=["reminded_at"])

    return len(events), told
