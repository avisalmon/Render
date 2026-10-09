"""What a player has done, read from the completions: XP, level, and where they stand in the path.

A completion is the fact (the player passed an exercise for the first time); XP is their sum, a level
is a function of XP, and a lesson is open, ahead or done by whether the lesson before it has all of its
exercises passed. Nothing is locked (Avi, 2026-10-09): anyone may start from the lesson that is their
level, a take there counts like any other, and the path carries on from there. The one stored thing is
`Player.current_lesson`, the pointer that says where the player chose to be; everything else is a read.
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


def _track_rank(track):
    return TRACK_ORDER.index(track) if track in TRACK_ORDER else len(TRACK_ORDER)


def path_key(lesson):
    """Where a lesson sits in the path: its `path_order` when it has one, else after every numbered
    lesson by level, track and position."""
    if lesson.path_order is not None:
        return (0, lesson.path_order, lesson.pk)
    return (1, lesson.level, _track_rank(lesson.track), lesson.order, lesson.pk)


def lesson_states(player, done=None):
    """{lesson id: {"state", "exercises_done", "exercises_total", "current"}} for every lesson, drafts
    too, because a published lesson may follow one.

    done: every exercise passed. ahead: the lesson it builds on still has exercises to pass, and the
    player has not chosen to start here or past here. open: everything else. A lesson with nothing to
    play is read, never ticked off, and never holds up the one after it. The pointer opens everything
    up to itself in the path, because a person who starts at lesson twelve may go back to any of the
    eleven before it.
    """
    done = done_exercise_ids(player) if done is None else done
    totals, passed = {}, {}
    for lesson_id, exercise_id in Exercise.objects.filter(lesson__isnull=False).values_list("lesson_id", "id"):
        totals[lesson_id] = totals.get(lesson_id, 0) + 1
        if exercise_id in done:
            passed[lesson_id] = passed.get(lesson_id, 0) + 1

    lessons = {lesson.pk: lesson for lesson in Lesson.objects.all()}
    prerequisites = {pk: lesson.prerequisite_id for pk, lesson in lessons.items()}
    held = {}

    def held_back(lesson_id, seen=()):
        # A lesson with nothing to play is cleared only if it is itself reachable, so an unfinished
        # reading lesson keeps everything after it waiting too.
        if lesson_id not in held:
            prerequisite_id = prerequisites.get(lesson_id)
            held[lesson_id] = (
                prerequisite_id is not None
                and prerequisite_id not in seen
                and prerequisite_id in prerequisites
                and (
                    held_back(prerequisite_id, seen + (lesson_id,))
                    or passed.get(prerequisite_id, 0) < totals.get(prerequisite_id, 0)
                )
            )
        return held[lesson_id]

    pointer = player.current_lesson_id if player.current_lesson_id in lessons else None
    pointer_key = path_key(lessons[pointer]) if pointer else None

    states = {}
    for lesson_id, lesson in lessons.items():
        total, count = totals.get(lesson_id, 0), passed.get(lesson_id, 0)
        reached = pointer_key is not None and path_key(lesson) <= pointer_key
        if total and count >= total:
            state = "done"
        elif held_back(lesson_id) and not reached:
            state = "ahead"
        else:
            state = "open"
        states[lesson_id] = {"state": state, "exercises_done": count, "exercises_total": total, "current": lesson_id == pointer}
    return states


def rank(exercise):
    """Where an exercise sits in the path: the lesson's place, then the exercise. A challenge has no
    lesson and comes after everything in the lessons."""
    lesson = exercise.lesson
    if lesson is None:
        return ((2,), exercise.order, exercise.pk)
    return (path_key(lesson), exercise.order, exercise.pk)


def open_exercises(player, done=None, daily_only=False):
    """Every exercise the workout may offer, in the order of the path: those in a published lesson
    the player has reached, and every challenge. A lesson ahead of the player is playable, but the
    workout does not push them into it. daily_only keeps just the ones marked for the daily workout."""
    states = lesson_states(player, done=done)
    rows = Exercise.objects.filter(Q(lesson__isnull=True) | Q(lesson__status=Lesson.Status.PUBLISHED)).select_related("lesson")
    if daily_only:
        rows = rows.filter(daily_eligible=True)
    return sorted((e for e in rows if e.lesson_id is None or states[e.lesson_id]["state"] != "ahead"), key=rank)


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
    asks for, or an exercise already passed. A lesson ahead of the player counts like any other."""
    exercise = take.exercise
    if exercise is None or take.score is None or take.score < exercise.pass_score:
        return None
    if not counts_for(take, exercise):
        return None
    try:
        with transaction.atomic():
            completion, created = Completion.objects.get_or_create(
                player=take.player, exercise=exercise, defaults={"take": take, "xp_awarded": exercise.xp},
            )
    except IntegrityError:
        return None
    return completion if created else None


def move_to(player, lesson):
    """Point the player at a lesson: Today and Continue follow from here. Playing an exercise of a
    lesson moves the pointer there, and so does Start here on the lesson page."""
    if lesson is None or player.current_lesson_id == lesson.pk:
        return
    player.current_lesson = lesson
    player.save(update_fields=["current_lesson"])


def _nothing(state):
    return {"state": state, "lesson": None, "title": "", "track": "", "exercises_done": 0, "exercises_total": 0}


def _payload(lesson, states):
    row = states[lesson.pk]
    return {
        "state": "continue" if row["exercises_done"] else "start",
        "lesson": lesson.slug,
        "title": lesson.title,
        "track": lesson.track,
        "exercises_done": row["exercises_done"],
        "exercises_total": row["exercises_total"],
    }


def continue_lesson(player):
    """Where the Today screen sends the player.

    With a pointer: that lesson while it has exercises to pass, then the next unfinished lesson after
    it in the path, then whatever is left before it. Without one: the open lesson with some exercises
    passed, else the first open lesson in the order of the path; a lesson ahead is never offered
    before the player goes there. Only published lessons with something to play count, because a
    lesson with nothing to play is read and never ticked off, so it would sit at the top for ever.
    `state` is "continue", "start", "finished" (every lesson done) or "none" (nothing published to do).
    """
    states = lesson_states(player)
    lessons = sorted(Lesson.objects.filter(status=Lesson.Status.PUBLISHED), key=path_key)
    playable = [lesson for lesson in lessons if states[lesson.pk]["exercises_total"]]
    if not playable:
        return _nothing("none")
    left = [lesson for lesson in playable if states[lesson.pk]["state"] != "done"]
    if not left:
        return _nothing("finished")

    pointer = next((lesson for lesson in playable if lesson.pk == player.current_lesson_id), None)
    if pointer is not None:
        if states[pointer.pk]["state"] != "done":
            return _payload(pointer, states)
        after = [lesson for lesson in left if path_key(lesson) > path_key(pointer)]
        return _payload((after or left)[0], states)

    open_ones = [lesson for lesson in left if states[lesson.pk]["state"] == "open"]
    if not open_ones:
        return _nothing("finished")
    begun = [lesson for lesson in open_ones if states[lesson.pk]["exercises_done"]]
    return _payload((begun or open_ones)[0], states)


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
