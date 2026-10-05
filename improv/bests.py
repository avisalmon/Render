"""Personal bests: the best take a player has made of each exercise.

Nothing here is stored. It is a read over takes, and it counts only what a completion counts: a
scored take of exactly what the exercise asks (its progression, from the first bar, for its bars).
Every challenge is listed, played or not, so the screen is a list of things to try; an exercise in
a lesson is listed once there is a take of it. An exercise in a draft lesson is never listed.
"""

from django.db.models import Q

from . import progress
from .models import Exercise, Lesson, Take


def report(player):
    """{"items": [...]}: one row per exercise, in the order of the path, challenges last."""
    exercises = {
        e.pk: e
        for e in Exercise.objects.filter(Q(lesson__isnull=True) | Q(lesson__status=Lesson.Status.PUBLISHED)).select_related("lesson")
    }
    best = {}
    attempts = {}
    takes = Take.objects.filter(player=player, exercise__in=exercises.keys(), score__isnull=False).order_by("started_at", "pk")
    for take in takes:
        exercise = exercises[take.exercise_id]
        if not progress.counts_for(take, exercise):
            continue
        attempts[exercise.pk] = attempts.get(exercise.pk, 0) + 1
        if exercise.pk not in best or take.score > best[exercise.pk].score:
            best[exercise.pk] = take

    items = []
    for exercise in sorted(exercises.values(), key=progress.rank):
        take = best.get(exercise.pk)
        if take is None and exercise.lesson_id is not None:
            continue
        lesson = exercise.lesson
        items.append(
            {
                "exercise": exercise.slug,
                "title": exercise.title,
                "lesson": lesson.slug if lesson else None,
                "lesson_title": lesson.title if lesson else "",
                "scoring_kind": exercise.scoring_kind,
                "pass_score": exercise.pass_score,
                "xp": exercise.xp,
                "is_challenge": lesson is None,
                "best_score": take.score if take else None,
                "best_take": take.pk if take else None,
                "best_at": take.started_at.isoformat() if take else None,
                "attempts": attempts.get(exercise.pk, 0),
                "passed": bool(take) and take.score >= exercise.pass_score,
            }
        )
    return {"items": items}
