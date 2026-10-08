"""Who may play (spec ch. 7).

Anyone who is signed in, on any account. `app.portal` holds the rule (audience
EVERYONE), so the door and the portal cannot drift. Until 2026-10-08 this was the
`improv_players` group, and the group is still created by migration 0001 though
nothing reads it now.
"""

from urllib.parse import urlsplit

PREFIX = "/improv"
HOME = "/improv/"
LOGIN = "/improv/login/"
SIGNUP = "/improv/signup/"
LOGOUT = "/improv/logout/"
# What a visitor who is not signed in may open. Everything else asks them to sign in first.
PUBLIC_PATHS = frozenset({HOME, LOGIN, SIGNUP, LOGOUT})
API_PREFIX = "/improv/api/"


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


def safe_next(raw):
    """Where to send a person after they sign in: a page inside improv, or the front page.

    A person is never sent outside the app by a link someone else made, and never back to the
    sign-in pages themselves."""
    if not raw or not raw.startswith(HOME) or "\\" in raw or "//" in raw or any(c in raw for c in "\r\n\t "):
        return HOME
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.path in (LOGIN, SIGNUP, LOGOUT):
        return HOME
    return raw


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def profile_for(user):
    """The player's own profile, made on first visit.

    Not a post_save signal on User: most accounts on the site never open this app, and a
    signal would make a profile for every one of them.
    """
    from .models import Player

    profile, _ = Player.objects.get_or_create(user=user)
    return profile
