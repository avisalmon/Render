"""Following, on babook's graph, and never a second one.

REQ-B.5.8, Q2. Following a person is about identity, and identity is babook's
job (main spec, chapter 0). A `BlackjackFollow` table would be a second answer
to "who does this person follow", free to disagree with the first, and the day
they disagree somebody is unfollowed in one place and still followed in the
other.

**This module is the only thing in the app that touches `app.models.Follow`.**
Reading it is plainly fine. Writing it is the part worth defending: blackjack
has to be able to create a follow, because Rule 3 forbids a link back to the
main site, so a person who finds a friend here would otherwise have nowhere to
press. It writes rows in babook's table rather than keeping its own, which is
"consume, do not copy" doing exactly what it says.

**You follow a person through a result they shared with you.** There is no
directory and no search. A search box over the member list would mean typing
part of somebody's email address and being told whether it exists, which is a
thing this app has no business offering.
"""


def _graph():
    from app.models import Follow

    return Follow


def following(user):
    """The people this person follows. Babook's answer, not ours."""
    from django.contrib.auth.models import User

    ids = _graph().objects.filter(follower=user).values_list("followed_id", flat=True)
    return User.objects.filter(pk__in=list(ids))


def follows(user, other):
    return _graph().objects.filter(follower=user, followed=other).exists()


def follow(user, other):
    """Start following somebody. Idempotent, and never yourself.

    `get_or_create` rather than `create`: two taps on a slow phone are one
    intention, and the unique constraint would otherwise turn the second into
    a server error.
    """
    if other is None or other.pk == user.pk:
        return False
    _graph().objects.get_or_create(follower=user, followed=other)
    return True


def unfollow(user, other):
    """Stop. Removes the row from babook's graph, because there is only one."""
    _graph().objects.filter(follower=user, followed=other).delete()


def follow_by_share(user, token):
    """Follow the person behind a result you were shown.

    A live link only. A revoked one is a door somebody closed, and it does not
    stay open as a way to attach yourself to them.
    """
    from . import sharing

    share = sharing.live(token)
    if share is None:
        return None
    other = share.player.user
    return other if follow(user, other) else None


def card(user):
    """What one person in your circle shows you.

    A whitelist, like the share snapshot and for the same reason: a page that
    reached through to the player would publish whatever field was added next.
    Numbers appear only if they left the switch on; the name appears either
    way, so unfollowing somebody you can no longer see is still possible.
    """
    from . import sharing, streaks
    from .models import Attempt, Player

    player = Player.objects.filter(user=user).first()
    row = {
        "user_id": user.pk,
        "name": sharing.display_name(user),
        "plays": player is not None,
        "shows": bool(player and player.show_to_followers),
        "hands": 0,
        "accuracy": 0,
        "streak": 0,
    }
    if not row["shows"] or player is None:
        return row

    hands = Attempt.objects.filter(player=player)
    total = hands.count()
    row["hands"] = total
    row["accuracy"] = round(hands.filter(is_correct=True).count() * 100 / total) if total else 0
    row["streak"] = streaks.of(player).current
    return row


def circle(user):
    """Everybody you follow, the ones who play first.

    Sorted by accuracy among those who show it, because the screen's job is a
    standing to compare yourself against. The people who do not play or do not
    show are listed after, rather than hidden, so the list matches who you
    actually follow.
    """
    rows = [card(other) for other in following(user)]
    rows.sort(key=lambda r: (not (r["plays"] and r["shows"]), -r["accuracy"], r["name"]))
    return rows
