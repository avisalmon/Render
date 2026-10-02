"""Who may see what. One function per model, and the API has no other filter.

The same shape as `matazim/access.py` and for the same reason: scope is a
property of the data rather than a rule somebody remembers. An API that derived
its own scope would be a second answer to "who may see this", free to drift
from the one the screens use.

There is less to say here than in the other apps, and that is the design. A
blackjack chart is not private: it is a published table about a card game.
What is private is a person's own play, which arrives in EPIC-B.2 and B.3 and
will be scoped the same way this is.
"""


def visible_rule_sets(user):
    """Every table. Rules are public knowledge, not somebody's secret.

    A person's own named table is visible to others too, which is deliberate:
    the alternative is hiding "6 decks, dealer stands on soft 17" from the
    world, and that is not a secret, it is a casino's advertising.
    """
    from .models import RuleSet

    if not getattr(user, "is_authenticated", False):
        return RuleSet.objects.none()
    return RuleSet.objects.all()


def visible_players(user):
    """Your own row and nobody else's.

    This is the one scoped thing in the app today, and it will be the shape of
    everything in EPIC-B.3: a person's practice is theirs. Following and
    sharing are a paid feature (REQ-B.8.7) and will widen this deliberately,
    through this function, rather than by a filter somewhere else.
    """
    from .models import Player

    if not getattr(user, "is_authenticated", False):
        return Player.objects.none()
    return Player.objects.filter(user=user)


def visible_charts(user):
    from .models import Chart

    if not getattr(user, "is_authenticated", False):
        return Chart.objects.none()
    return Chart.objects.all()


def visible_cells(user):
    from .models import Cell

    if not getattr(user, "is_authenticated", False):
        return Cell.objects.none()
    return Cell.objects.all()


def visible_attempts(user):
    """Your own hands and nobody else's.

    This is the most private table in the app: it is a record of what somebody
    is bad at. Sharing and following are paid features (REQ-B.8.7) and will
    widen this deliberately, through this function, when Avi answers Q2 and Q3.
    """
    from .models import Attempt

    if not getattr(user, "is_authenticated", False):
        return Attempt.objects.none()
    return Attempt.objects.filter(player__user=user)


def visible_sessions(user):
    """Your own runs of practice."""
    from .models import Session

    if not getattr(user, "is_authenticated", False):
        return Session.objects.none()
    return Session.objects.filter(player__user=user)


def visible_notes(user):
    """Your own notes. As private as the attempts they were computed from."""
    from .models import BatchNote

    if not getattr(user, "is_authenticated", False):
        return BatchNote.objects.none()
    return BatchNote.objects.filter(player__user=user)


def visible_mastery(user):
    """Your own grid."""
    from .models import Mastery

    if not getattr(user, "is_authenticated", False):
        return Mastery.objects.none()
    return Mastery.objects.filter(player__user=user)
