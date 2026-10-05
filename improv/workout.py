"""The daily workout: up to three exercises for today, read from what the player has done.

Nothing here is stored. The picks are a function of the player, the date and what the player had
passed before that day began, so reloading the page does not shuffle them, passing one during the
day does not change the other two, and tomorrow is a different set. The date is the player's own
day (see practice.py).

Slots, in the order shown: a weak spot (an exercise of a kind the weakness report names, as it
stood when the day began), a review (one the player passed before today), the next one in the lessons, and
fresh ones to fill the rest. Only exercises marked for the workout are offered, and never one in a
draft or locked lesson. A challenge has no lesson and is always open.
"""

import datetime as dt
import hashlib

from django.utils import timezone

from . import practice, progress, weakness
from .models import Completion, Take

SIZE = 3


def _day_bounds(player, day):
    zone = practice.zone_of(player)
    start = dt.datetime.combine(day, dt.time.min, tzinfo=zone)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=zone)
    return start, end


def _choose(player, day, slot, candidates):
    """A stable pick: the same player, day and slot over the same candidates always lands on the
    same one."""
    digest = hashlib.sha256(f"{player.pk}|{day.isoformat()}|{slot}".encode("utf-8")).hexdigest()
    return candidates[int(digest, 16) % len(candidates)]


def _passed_today(player, exercise, start, end):
    takes = Take.objects.filter(
        player=player, exercise=exercise, started_at__gte=start, started_at__lt=end, score__gte=exercise.pass_score,
    )
    return any(progress.counts_for(take, exercise) for take in takes)


def pick(player, day=None, weak_kinds=None):
    """The workout for `day` (the player's local today by default): a list of
    {"slot", "exercise", "xp_available", "done_today"}, at most SIZE, none twice.

    weak_kinds: the scoring kinds to work on, most pressing first. None reads them from the
    weakness report as it stood when the day began, so today's takes do not move today's picks;
    an empty list means no weak spot."""
    day = day or timezone.now().astimezone(practice.zone_of(player)).date()
    start, end = _day_bounds(player, day)
    done_before = set(
        Completion.objects.filter(player=player, completed_at__lt=start).values_list("exercise_id", flat=True)
    )
    eligible = progress.open_exercises(player, done=done_before, daily_only=True)
    if weak_kinds is None:
        weak_kinds = weakness.weak_kinds(weakness.report(player, before=start)["claims"])

    chosen = []

    def add(slot, exercise):
        chosen.append((slot, exercise))

    def taken(exercise):
        return any(e.pk == exercise.pk for _, e in chosen)

    for kind in weak_kinds:
        candidates = [e for e in eligible if e.scoring_kind == kind]
        if candidates:
            add("weak", _choose(player, day, "weak", candidates))
            break

    reviews = [e for e in eligible if e.pk in done_before and not taken(e)]
    if reviews:
        add("review", _choose(player, day, "review", reviews))

    upcoming = next((e for e in eligible if e.pk not in done_before and not taken(e)), None)
    if upcoming is not None:
        add("next", upcoming)

    fill = 0
    while len(chosen) < SIZE:
        left = [e for e in eligible if not taken(e)]
        if not left:
            break
        fresh = [e for e in left if e.pk not in done_before] or left
        fill += 1
        add("fresh", _choose(player, day, f"fresh{fill}", fresh))

    return [
        {
            "slot": slot,
            "exercise": exercise,
            "xp_available": 0 if exercise.pk in done_before else exercise.xp,
            "done_today": _passed_today(player, exercise, start, end),
        }
        for slot, exercise in chosen
    ]


def report(player, now=None, weak_kinds=None):
    """What the page needs: the day, the picks in plain fields, and how far through them the player is."""
    zone = practice.zone_of(player)
    now = now or timezone.now()
    day = now.astimezone(zone).date()
    items = []
    for row in pick(player, day, weak_kinds=weak_kinds):
        exercise, lesson = row["exercise"], row["exercise"].lesson
        items.append(
            {
                "slot": row["slot"],
                "exercise": exercise.slug,
                "title": exercise.title,
                "lesson": lesson.slug if lesson else None,
                "lesson_title": lesson.title if lesson else "",
                "scoring_kind": exercise.scoring_kind,
                "xp": exercise.xp,
                "xp_available": row["xp_available"],
                "pass_score": exercise.pass_score,
                "done_today": row["done_today"],
            }
        )
    done = sum(1 for item in items if item["done_today"])
    return {
        "date": day.isoformat(),
        "timezone": getattr(zone, "key", "UTC"),
        "items": items,
        "total": len(items),
        "done_today": done,
        "complete": bool(items) and done == len(items),
    }
