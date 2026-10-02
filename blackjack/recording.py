"""What happens to a decision once somebody has made it.

Two things record decisions: the drill, through `AttemptViewSet`, and the play
simulator. Both must do exactly the same afterwards, because the mastery grid,
the note every twenty hands, the streak and the history graph are all reads
over `Attempt`, and a decision that reached one but skipped another would make
the product disagree with itself.

This module is the one place those steps live. It does not decide what is
correct: the drill reads that off the chart row, and the simulator reads it off
the same row after working out which row the hand is.
"""

from django.utils import timezone


def touch(player):
    """REQ-B.6.3: the thirty minutes start at the first hand, not at signup.
    Set once, here, because this is the first moment the app can honestly say
    somebody has used it."""
    if player.first_used_at is None:
        player.first_used_at = timezone.now()
        player.save(update_fields=["first_used_at"])


def after(player, attempt):
    """Fold a recorded attempt into everything derived from it.

    Returns what the screen needs to say about it: the note written at the
    twentieth hand, if there was one, and how far into the next twenty this
    leaves the person.
    """
    from . import mastery, notes
    from .models import Attempt

    mastery.record(attempt)
    note = notes.maybe_write(player, attempt.session)
    return {
        "note": note.text if note else None,
        "in_batch": Attempt.objects.filter(
            player=player, session=attempt.session
        ).count() % notes.BatchNote.BATCH,
    }
