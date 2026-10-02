"""How well somebody knows each decision, and when to ask it again.

One row per person per cell, at most 340 each. It is two things at once and
both are deliberate:

1. **Counts**, so the grid renders in one query rather than 340. These are a
   named denormalisation of `Attempt`, which stays the only truth.
2. **Scheduling state**, `due_at` and `strength`, which is what makes a cell
   come back sooner when it is missed. Free gets the weak form, recently missed
   cells returning; paid gets the real scheduler (REQ-B.5.7, REQ-B.8.2).

**Correcting the data model as written.** It said scheduling state cannot be
rebuilt from `Attempt` because it depends on the order things happened. That
was half right: it cannot be recomputed from *counts*, but it can be rebuilt
exactly by replaying the attempts in order through this same function, which is
what `rebuild` does. So nothing here is unrecoverable, and the rebuild is a
test rather than a promise.

The schedule itself is deliberately simple. Spaced repetition is the one piece
of real learning science in this field, and the evidence is for the shape, wrong
answers return sooner and right ones recede, not for any particular curve. A
curve nobody can explain is a curve nobody can debug.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

# A missed cell comes back almost immediately; a known one recedes. The first
# interval is short because the point of the drill is repetition inside one
# sitting, not revision across weeks.
FIRST_INTERVAL = timedelta(minutes=2)
GROWTH = 2.2
CEILING = 60 * 24 * 14      # two weeks, in minutes


def _key(attempt):
    return {
        "cell_kind": attempt.cell_kind,
        "cell_player": attempt.cell_player,
        "cell_dealer": attempt.cell_dealer,
    }


def record(attempt):
    """Fold one attempt into the mastery row for its cell.

    Called once per recorded hand. Idempotent it is not, and must not be: two
    attempts at the same cell are two data points, which is the whole idea.
    """
    from .models import Mastery

    row, _ = Mastery.objects.get_or_create(player=attempt.player, **_key(attempt))

    row.seen += 1
    when = attempt.created_at or timezone.now()
    row.last_seen_at = when

    if attempt.is_correct:
        row.correct += 1
        row.streak += 1
        row.strength = min(row.strength * GROWTH if row.strength else 1.0, CEILING)
        row.due_at = when + FIRST_INTERVAL * row.strength
    else:
        # A miss collapses the interval rather than nudging it. Somebody who
        # has just got a cell wrong should meet it again in this sitting, not
        # next week, which is the entire argument for spaced repetition.
        row.streak = 0
        row.strength = 1.0
        row.due_at = when

    row.save()
    return row


@transaction.atomic
def rebuild(player):
    """Recompute every mastery row for one person from their attempts.

    By replaying in order through `record`, so the result is identical to what
    live play produced rather than an approximation of it. That is what makes
    `Attempt` the only truth: everything here can be thrown away and restored.
    """
    from .models import Attempt, Mastery

    Mastery.objects.filter(player=player).delete()
    for attempt in Attempt.objects.filter(player=player).order_by("created_at", "pk"):
        record(attempt)
    return Mastery.objects.filter(player=player).count()


def grid(player):
    """Every cell of this person's chart with what they know about it.

    Returns rows shaped for the screen: the cell, the counts, and a `state` the
    template can colour by. Cells never seen are included, because "you have not
    met this yet" is information a learner wants and an absence is not.
    """
    from .models import Chart, Mastery

    chart = Chart.objects.filter(rule_set=player.rule_set).first()
    if chart is None:
        return []

    known = {
        (row.cell_kind, row.cell_player, row.cell_dealer): row
        for row in Mastery.objects.filter(player=player)
    }

    out = []
    for cell in chart.cells.all():
        row = known.get((cell.kind, cell.player, cell.dealer))
        seen = row.seen if row else 0
        correct = row.correct if row else 0
        out.append({
            "cell": cell,
            "seen": seen,
            "correct": correct,
            "streak": row.streak if row else 0,
            "state": state_of(seen, correct, row.streak if row else 0),
        })
    return out


def state_of(seen, correct, streak):
    """What to call this cell on the grid.

    Four states, not a percentage. A percentage over three attempts is noise
    dressed as precision, and the question a learner actually has is "which of
    these do I still not know".
    """
    if seen == 0:
        return "new"
    if streak >= 3 and correct >= 3:
        return "solid"
    if correct == seen:
        return "learning"
    return "shaky"


def summary(player):
    """The sentence the research says competitors do not give anybody: how many
    are solid, and which ones are costing the most."""
    rows = grid(player)
    solid = [r for r in rows if r["state"] == "solid"]
    shaky = [r for r in rows if r["state"] == "shaky"]
    shaky.sort(key=lambda r: (r["correct"] - r["seen"], -r["seen"]))
    return {
        "total": len(rows),
        "solid": len(solid),
        # Right every time so far, but fewer than three in a row. On day one
        # this is the only count that moves, and a summary without it reads
        # as "nothing yet" to somebody who has just done an hour's work.
        "learning": len([r for r in rows if r["state"] == "learning"]),
        "shaky": len(shaky),
        "new": len([r for r in rows if r["state"] == "new"]),
        "worst": shaky[:5],
    }


def due_cells(player, limit=40):
    """Cells the scheduler says are ready to be asked again (REQ-B.8.2).

    This is the paid half of spaced repetition, and it is **arithmetic, not a
    model call**. A language model choosing the next flashcard would cost money
    and latency on every hand to do worse than a sort by date, and the paid
    tier is better spent on the things only a model can do.

    Overdue first, because somebody returning after a week should meet what
    they were about to forget before they meet what they nearly know.
    """
    from django.utils import timezone

    from .models import Mastery

    rows = (
        Mastery.objects.filter(player=player, due_at__lte=timezone.now())
        .order_by("due_at")[:limit]
    )
    return [
        {"kind": row.cell_kind, "player": row.cell_player, "dealer": row.cell_dealer}
        for row in rows
    ]
