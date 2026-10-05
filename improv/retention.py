"""How long a take keeps its notes (SPR-I.6.2).

A take that was not kept loses its events after RETENTION_DAYS and keeps everything else: the
score, the metrics, the chart and the key it was played in. The weakness report and the bests read
those and never the events, so nothing the app says about the player changes.

Pruning runs when the same player saves their next take. Render's scheduled jobs cannot see the
SQLite disk, and a prune that needed a scheduler would simply not run.
"""

import datetime as dt

from django.utils import timezone

from .models import Take

RETENTION_DAYS = 30


def cutoff(now=None):
    return (now or timezone.now()) - dt.timedelta(days=RETENTION_DAYS)


def prune(player, now=None):
    """Clear the events of this player's unkept takes older than the cutoff. Returns how many
    takes were cleared. A take already cleared is left alone, so a second run does nothing."""
    old = Take.objects.filter(player=player, is_kept=False, started_at__lt=cutoff(now)).exclude(events=[])
    return old.update(events=[])


def is_cleared(take):
    return not take.events
