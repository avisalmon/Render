"""Who may play (spec ch. 7).

A person is in the `improv_players` group, or they see nothing. A superuser is
let in too, so the site admin never has to put himself in the group; that
exception is written down on the portal entry, which is where the rule lives.
"""

GROUP = "improv_players"
PREFIX = "/improv"


def is_player(user):
    """The one rule. `app.portal` decides, so the card and the door cannot drift."""
    from app.portal import may_enter

    if user is None:
        return False
    return may_enter(user, "improv")


def is_improv_path(path):
    """True for /improv and anything under /improv/, and for nothing that merely
    starts with the same letters (/improvement/)."""
    return path == PREFIX or path.startswith(PREFIX + "/")


def profile_for(user):
    """The player's own profile, made on first visit.

    Not a post_save signal on User: the people who matter here were added to the
    group long after their account existed, and a signal would also fire for every
    account on a site where almost nobody plays the piano.
    """
    from .models import Player

    profile, _ = Player.objects.get_or_create(user=user)
    return profile
