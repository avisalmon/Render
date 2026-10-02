"""The note after every twenty hands, written by arithmetic.

REQ-B.5.3, and free. No model is asked anything here, which is what makes the
rule in spec 1.3 provable rather than enforced: the free product has no path to
a language model at all. The paid tier writes into the same `BatchNote` row
with `is_ai=True` and says things arithmetic cannot (REQ-B.8.1).

**The free note has to be worth reading on its own.** A deterministic note that
exists only to advertise the paid one is a worse product and a worse pitch. So
it says the three things a person actually wants after twenty hands: how they
did, whether that is better or worse than last time, and which hand is costing
them the most.
"""

from .models import BatchNote


def _percent(value):
    return f"{round(value * 100)}%"


def _hand_name(kind, player, dealer):
    face = "A" if dealer == 11 else str(dealer)
    if kind == "pair":
        hand = "A,A" if player == 11 else f"{player},{player}"
    elif kind == "soft":
        hand = f"A,{player - 11}"
    else:
        hand = str(player)
    return f"{hand} מול {face}"


def compose(accuracy, previous, weakest):
    """The sentence itself.

    Deliberately plain. The temptation in a product like this is to cheer, and
    a drill that congratulates somebody for 55 percent is a drill that stops
    being believed, which costs more than the encouragement is worth.
    """
    lines = [f"עשרים ידיים, {_percent(accuracy)} נכונות."]

    if previous is not None:
        change = round((accuracy - previous) * 100)
        if change >= 5:
            lines.append(f"עלייה של {change} נקודות מהעשרים הקודמות.")
        elif change <= -5:
            lines.append(f"ירידה של {abs(change)} נקודות מהעשרים הקודמות.")
        else:
            lines.append("בערך כמו העשרים הקודמות.")

    if weakest:
        names = ", ".join(_hand_name(*key) for key in weakest[:2])
        lines.append(f"הכי מבלבל כרגע: {names}.")
    elif accuracy == 1.0:
        lines.append("עשרים מתוך עשרים. אין כאן מה לתקן.")

    return " ".join(lines)


def maybe_write(player, session):
    """Write a note if this person has just completed a batch of twenty.

    Returns the note, or None. Called once per recorded hand, from the same
    place the hand is recorded, so there is one path through which anything
    happens to an attempt.
    """
    from .models import Attempt

    attempts = Attempt.objects.filter(player=player, session=session).order_by("created_at", "pk")
    total = attempts.count()
    if total == 0 or total % BatchNote.BATCH:
        return None

    batch = list(attempts[total - BatchNote.BATCH: total])
    accuracy = sum(1 for a in batch if a.is_correct) / len(batch)

    earlier = BatchNote.objects.filter(player=player, session=session).order_by("-created_at").first()
    previous = earlier.accuracy if earlier else None

    missed = {}
    for attempt in batch:
        if attempt.is_correct:
            continue
        key = (attempt.cell_kind, attempt.cell_player, attempt.cell_dealer)
        missed[key] = missed.get(key, 0) + 1
    weakest = [list(key) for key, _ in sorted(missed.items(), key=lambda kv: -kv[1])]

    return BatchNote.objects.create(
        player=player,
        session=session,
        accuracy=accuracy,
        previous_accuracy=previous,
        weakest=weakest,
        text=compose(accuracy, previous, [tuple(k) for k in weakest]),
        is_ai=False,
    )
