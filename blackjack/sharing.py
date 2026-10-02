"""What a shared link says, and what it will never say.

REQ-B.5.8, and free: sharing is how the app spreads, and charging for it would
be charging to grow.

**One function decides what leaves the account.** `snapshot` builds a plain
dict of numbers, and the public page renders that dict and nothing else. The
alternative, a template reading `share.player` and reaching for whatever it
needs, is how a field added next month ends up on a link shared last month.

**The name is the only personal thing here, and it is opt-in by being blank.**
Accounts on this site are keyed by email address, so a page that printed the
username would publish somebody's email to a group chat. It prints the first
name babook holds, and nothing when there is not one.
"""

from django.utils import timezone


def display_name(user):
    """What to call somebody on a page strangers can open.

    First name only. Not the username, which is an email address here, and not
    the last name, because a result posted to a group does not need to identify
    a person to people who were not meant to see it.
    """
    return (getattr(user, "first_name", "") or "").strip()[:40]


def snapshot(player):
    """The numbers, frozen. Nothing that is not in this dict can be published.

    Lifetime accuracy rather than a best-ever run: a shared result that quietly
    picks somebody's luckiest twenty hands is a number nobody should trust,
    including the person sharing it.
    """
    from . import streaks
    from .models import Attempt

    hands = Attempt.objects.filter(player=player)
    total = hands.count()
    right = hands.filter(is_correct=True).count()
    streak = streaks.of(player)

    return {
        "name": display_name(player.user),
        "hands": total,
        "right": right,
        "accuracy": round(right * 100 / total) if total else 0,
        "streak": streak.current,
        "best_streak": streak.best,
        "rules": player.rule_set.describe() if player.rule_set_id else "",
        "shared_on": timezone.localdate().isoformat(),
    }


def headline(data):
    """One sentence, because that is what a group chat shows."""
    if not data["hands"]:
        return "התחלתי ללמוד בלקג'ק בסיסי."
    return f"{data['accuracy']}% נכון ב-{data['hands']} ידיים."


def make(player):
    """Freeze this moment behind a new link."""
    from .models import Share

    data = snapshot(player)
    return Share.objects.create(
        token=Share.new_token(),
        player=player,
        headline=headline(data),
        snapshot=data,
    )


def revoke(player, token):
    """Close one of your own links. Somebody else's is not yours to close."""
    from .models import Share

    share = Share.objects.filter(player=player, token=token, revoked_at=None).first()
    if share is None:
        return False
    share.revoked_at = timezone.now()
    share.save(update_fields=["revoked_at"])
    return True


def live(token):
    """The share behind a link, or nothing. A revoked link is nothing."""
    from .models import Share

    return Share.objects.filter(token=token, revoked_at=None).first()
