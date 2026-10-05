"""The weakness report: what the last thirty days of takes say about where to work.

Nothing here is stored. It is a read over takes, and it is careful about what it claims: a number
is only worth naming when there are enough notes behind it, so each area waits for twenty notes of
its own, and until the player has played that many the report says how many more it needs rather
than guessing. It names at most three things, the furthest from fine first, and gives each an
exercise to work on it.

The numbers come from the judge's metrics on each take (static/improv/judge.js): the share of
notes on chord tones, the share that went outside, the share close to the beat, and the same
counts per kind of chord, which this module joins to the chord's family (minor, dominant and so
on). A take's metrics are free-form, so anything that is not a sensible number is ignored.
"""

import datetime as dt
import math

from django.utils import timezone

from . import progress
from .models import ChordQuality, Take

DAYS = 30
FLOOR = 20
MOST_CLAIMS = 3

# Where each area stops being fine.
TIMING_FLOOR_PCT = 60
CHORD_TONES_FLOOR_PCT = 30
OUTSIDE_CEILING_PCT = 25

# What to work on for each area, best first.
KINDS = {
    "timing": ["rhythm_motif"],
    "chord_tones": ["chord_tones_on_beats", "guide_tones"],
    "outside": ["scale_only", "chord_tones_on_beats"],
    "family": ["chord_tones_on_beats", "guide_tones"],
}
PRIORITY = {"timing": 0, "chord_tones": 1, "outside": 2, "family": 3}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _count(value):
    return value if _number(value) and value > 0 else 0


def _percent(value):
    return value if _number(value) and 0 <= value <= 100 else None


def family_label(family):
    return family.replace("_", "-")


class _Mean:
    """A mean weighted by how many notes each take had."""

    def __init__(self):
        self.notes = 0
        self.total = 0.0

    def add(self, notes, value):
        if value is not None:
            self.notes += notes
            self.total += notes * value

    @property
    def value(self):
        return self.total / self.notes


def _exercise_for(kinds, open_rows, done):
    """The first open exercise of the first kind that has one not yet passed; failing that, the
    first open one of any of the kinds; None when nothing is open."""
    for kind in kinds:
        for row in open_rows:
            if row.scoring_kind == kind and row.pk not in done:
                return row
    for kind in kinds:
        for row in open_rows:
            if row.scoring_kind == kind:
                return row
    return None


def report(player, now=None, before=None):
    """{days, floor, notes, enough, notes_needed, claims} for the thirty days before `before`
    (or up to now)."""
    now = now or timezone.now()
    end = before or now
    takes = Take.objects.filter(player=player, started_at__gte=end - dt.timedelta(days=DAYS))
    if before is not None:
        takes = takes.filter(started_at__lt=before)

    timing, chord_tones, outside = _Mean(), _Mean(), _Mean()
    families = {}
    family_of = dict(ChordQuality.objects.values_list("symbol", "family"))
    total = 0

    for metrics in takes.values_list("metrics", flat=True):
        if not isinstance(metrics, dict):
            continue
        notes = _count(metrics.get("notes"))
        if not notes:
            continue
        total += notes
        timing.add(notes, _percent(metrics.get("withinPct")))
        chord_tones.add(notes, _percent(metrics.get("chordTonePct")))
        outside.add(notes, _percent(metrics.get("outsidePct")))
        by_quality = metrics.get("byQuality")
        if not isinstance(by_quality, dict):
            continue
        for symbol, row in by_quality.items():
            family = family_of.get(symbol)
            if family is None or not isinstance(row, dict):
                continue
            there, away = _count(row.get("notes")), row.get("outside")
            if there and _number(away) and 0 <= away <= there:
                seen = families.setdefault(family, [0, 0])
                seen[0] += there
                seen[1] += away

    found = []  # (gap, area, family, percent, notes)
    if timing.notes >= FLOOR and timing.value < TIMING_FLOOR_PCT:
        found.append((TIMING_FLOOR_PCT - timing.value, "timing", "", timing.value, timing.notes))
    if chord_tones.notes >= FLOOR and chord_tones.value < CHORD_TONES_FLOOR_PCT:
        found.append((CHORD_TONES_FLOOR_PCT - chord_tones.value, "chord_tones", "", chord_tones.value, chord_tones.notes))
    if outside.notes >= FLOOR and outside.value > OUTSIDE_CEILING_PCT:
        found.append((outside.value - OUTSIDE_CEILING_PCT, "outside", "", outside.value, outside.notes))
    for family, (there, away) in families.items():
        share = 100 * away / there
        if there >= FLOOR and share > OUTSIDE_CEILING_PCT:
            found.append((share - OUTSIDE_CEILING_PCT, "family", family, share, there))
    found.sort(key=lambda f: (-f[0], PRIORITY[f[1]], f[2]))

    open_rows = progress.open_exercises(player) if found else []
    done = progress.done_exercise_ids(player) if found else set()
    claims = []
    for _gap, area, family, percent, notes in found[:MOST_CLAIMS]:
        row = _exercise_for(KINDS[area], open_rows, done)
        claims.append(
            {
                "area": area,
                "family": family,
                "family_label": family_label(family),
                "percent": round(percent),
                "notes": notes,
                "kinds": list(KINDS[area]),
                "exercise": row.slug if row else None,
                "exercise_title": row.title if row else "",
                "lesson_title": row.lesson.title if row and row.lesson else "",
            }
        )
    return {
        "days": DAYS,
        "floor": FLOOR,
        "notes": total,
        "enough": total >= FLOOR,
        "notes_needed": max(0, FLOOR - total),
        "claims": claims,
    }


def weak_kinds(claims):
    """The scoring kinds the claims point at, most pressing first, each once."""
    kinds = []
    for claim in claims:
        for kind in claim["kinds"]:
            if kind not in kinds:
                kinds.append(kind)
    return kinds
