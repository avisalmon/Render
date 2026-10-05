"""What a player has done, read from the completions: XP, level, and which lessons are open.

Nothing here is stored. A completion is the fact (the player passed an exercise for the first
time); XP is their sum, a level is a function of XP, and a lesson is open, locked or done by
whether the lesson before it has all of its exercises passed. The server makes a completion as
the consequence of a take and takes the XP from the exercise row, so the page can report a take
but cannot award itself anything.
"""

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

from .models import Completion, Exercise, Lesson
from .teaching import TRACK_ORDER

# Level n starts at LEVEL_STEP * (n - 1) * n XP: 0, 50, 150, 300, 500. Each level asks a little
# more than the one before, and the whole curve is this one number and this one cap.
LEVEL_STEP = 25
MAX_LEVEL = 50


def level_floor(level):
    """The XP at which `level` begins."""
    return LEVEL_STEP * (level - 1) * level


def level_for(xp):
    level = 1
    while level < MAX_LEVEL and xp >= level_floor(level + 1):
        level += 1
    return level


def next_level_at(level):
    """The XP the next level begins at, or None at the top."""
    return None if level >= MAX_LEVEL else level_floor(level + 1)


def total_xp(player):
    return Completion.objects.filter(player=player).aggregate(total=Sum("xp_awarded"))["total"] or 0


def done_exercise_ids(player):
    return set(Completion.objects.filter(player=player).values_list("exercise_id", flat=True))


def lesson_states(player, done=None):
    """{lesson id: {"state", "exercises_done", "exercises_total"}} for every lesson, drafts too,
    because a published lesson may follow one.

    done: every exercise passed. open: not done yet, and nothing before it stands in the way.
    locked: its prerequisite still has exercises to pass. A lesson with nothing to play is read,
    never ticked off, and never holds up the one after it.
    """
    done = done_exercise_ids(player) if done is None else done
    totals, passed = {}, {}
    for lesson_id, exercise_id in Exercise.objects.filter(lesson__isnull=False).values_list("lesson_id", "id"):
        totals[lesson_id] = totals.get(lesson_id, 0) + 1
        if exercise_id in done:
            passed[lesson_id] = passed.get(lesson_id, 0) + 1

    prerequisites = dict(Lesson.objects.values_list("id", "prerequisite_id"))
    locked = {}

    def is_locked(lesson_id, seen=()):
        # A lesson with nothing to play is cleared only if it is itself reachable, so a locked
        # reading lesson keeps everything after it locked too.
        if lesson_id not in locked:
            prerequisite_id = prerequisites.get(lesson_id)
            locked[lesson_id] = (
                prerequisite_id is not None
                and prerequisite_id not in seen
                and prerequisite_id in prerequisites
                and (
                    is_locked(prerequisite_id, seen + (lesson_id,))
                    or passed.get(prerequisite_id, 0) < totals.get(prerequisite_id, 0)
                )
            )
        return locked[lesson_id]

    states = {}
    for lesson_id in prerequisites:
        total, count = totals.get(lesson_id, 0), passed.get(lesson_id, 0)
        if is_locked(lesson_id):
            state = "locked"
        elif total and count >= total:
            state = "done"
        else:
            state = "open"
        states[lesson_id] = {"state": state, "exercises_done": count, "exercises_total": total}
    return states


def is_open(player, lesson):
    """May the player's passes in this lesson's exercises count? A challenge has no lesson and
    is always open."""
    if lesson is None:
        return True
    return lesson_states(player)[lesson.pk]["state"] != "locked"


def rank(exercise):
    """Where an exercise sits in the path: the track, the lesson, the exercise. A challenge has no
    lesson and comes after everything in the lessons."""
    lesson = exercise.lesson
    if lesson is None:
        return (len(TRACK_ORDER) + 1, 0, exercise.order, exercise.pk)
    track = TRACK_ORDER.index(lesson.track) if lesson.track in TRACK_ORDER else len(TRACK_ORDER)
    return (track, lesson.order, exercise.order, exercise.pk)


def open_exercises(player, done=None, daily_only=False):
    """Every exercise the player can play and have count, in the order of the path: those in a
    published lesson that is not locked, and every challenge. daily_only keeps just the ones marked
    for the daily workout."""
    states = lesson_states(player, done=done)
    rows = Exercise.objects.filter(Q(lesson__isnull=True) | Q(lesson__status=Lesson.Status.PUBLISHED)).select_related("lesson")
    if daily_only:
        rows = rows.filter(daily_eligible=True)
    return sorted((e for e in rows if e.lesson_id is None or states[e.lesson_id]["state"] != "locked"), key=rank)


def counts_for(take, exercise):
    """Is this take a play of exactly what the exercise asks: its progression, from the first
    bar, for as many bars as it says?"""
    return (
        take.progression_id == exercise.progression_id
        and take.loop_from == 0
        and take.bars == exercise.bars
    )


def award(take):
    """Make the completion a take earns, if it earns one. Returns the Completion, or None when
    the take passed nothing new: free play, a score under the bar, other bars than the exercise
    asks for, a lesson not yet open, or an exercise already passed."""
    exercise = take.exercise
    if exercise is None or take.score is None or take.score < exercise.pass_score:
        return None
    if not counts_for(take, exercise) or not is_open(take.player, exercise.lesson):
        return None
    try:
        with transaction.atomic():
            completion, created = Completion.objects.get_or_create(
                player=take.player, exercise=exercise, defaults={"take": take, "xp_awarded": exercise.xp},
            )
    except IntegrityError:
        return None
    return completion if created else None


def continue_lesson(player):
    """Where the Today screen sends the player: the lesson in progress, else the next one to start.

    Only published lessons with something to play count, because a lesson with nothing to play is
    read and never ticked off, so it would sit at the top for ever. A lesson that is open and has
    some of its exercises passed comes before one not yet begun; otherwise the first open lesson
    in the order of the path. `state` is "continue", "start", "finished" (every lesson done) or
    "none" (nothing published to do).
    """
    states = lesson_states(player)
    lessons = sorted(
        Lesson.objects.filter(status=Lesson.Status.PUBLISHED),
        key=lambda lesson: (
            TRACK_ORDER.index(lesson.track) if lesson.track in TRACK_ORDER else len(TRACK_ORDER),
            lesson.order,
            lesson.pk,
        ),
    )
    playable = [lesson for lesson in lessons if states[lesson.pk]["exercises_total"]]
    if not playable:
        return {"state": "none", "lesson": None, "title": "", "track": "", "exercises_done": 0, "exercises_total": 0}
    open_ones = [lesson for lesson in playable if states[lesson.pk]["state"] == "open"]
    if not open_ones:
        return {"state": "finished", "lesson": None, "title": "", "track": "", "exercises_done": 0, "exercises_total": 0}
    begun = [lesson for lesson in open_ones if states[lesson.pk]["exercises_done"]]
    chosen = (begun or open_ones)[0]
    return {
        "state": "continue" if begun else "start",
        "lesson": chosen.slug,
        "title": chosen.title,
        "track": chosen.track,
        "exercises_done": states[chosen.pk]["exercises_done"],
        "exercises_total": states[chosen.pk]["exercises_total"],
    }


def summary(player):
    """Everything the screens show about progress, from the completions alone."""
    xp = total_xp(player)
    level = level_for(xp)
    states = lesson_states(player)
    published = Lesson.objects.filter(status=Lesson.Status.PUBLISHED).values_list("id", flat=True)
    return {
        "xp": xp,
        "level": level,
        "level_floor": level_floor(level),
        "next_level_at": next_level_at(level),
        "exercises_done": Completion.objects.filter(player=player).count(),
        "lessons_done": sum(1 for pk in published if states[pk]["state"] == "done"),
        "lessons_total": len(published),
    }
