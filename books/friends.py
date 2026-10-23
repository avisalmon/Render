"""Friends: inviting, following, and seeing a friend's library (Avi, 2026-10-22).

- Each person has one personal link, /books/i/<code>/. Whoever comes in
  through it and joins, and the inviter, follow each other at once.
- Anyone can ask to follow anyone. The request is accepted at once when the
  person's books are open to everyone; otherwise it waits for them to accept.
- An accepted follower sees all the person's books except the ones marked
  "only me", and their spine photos unless the person turned that off.
  Someone who does not follow sees only books marked for everyone, and only
  when the person's library is public.
- Removing a follower is quiet: the row goes and nobody is told.

Every rule lives here; the pages and the API both call it."""

import re
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Copy, Follow, Invite, Notification, Profile

INVITE_SESSION_KEY = "books_invite"
CHANNELS = ("whatsapp", "copy", "qr", "email", "share", "link")
CODE_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no look-alikes (l, 1, o, 0)


class FriendsError(Exception):
    """A refusal, with a strings.py key as its message."""


# ---- the invite -------------------------------------------------------------------

def invite_for(profile):
    invite = Invite.objects.filter(inviter=profile, is_active=True).order_by("created_at").first()
    if invite:
        return invite
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(7))
        try:
            return Invite.objects.create(inviter=profile, code=code)
        except IntegrityError:
            continue
    raise FriendsError("friends.err.code")


def invite_by_code(code):
    return Invite.objects.filter(code=(code or "").strip().lower()[:16], is_active=True).select_related("inviter").first()


def remember_invite(request, code, channel=""):
    """A visitor came through a link: keep it until they have joined."""
    invite = invite_by_code(code)
    if invite is None:
        return None
    request.session[INVITE_SESSION_KEY] = {"code": invite.code, "via": channel if channel in CHANNELS else "link"}
    return invite


def pending_invite(request):
    data = request.session.get(INVITE_SESSION_KEY) or {}
    return invite_by_code(data.get("code")) if data else None


def join_through_invite(profile, invite, channel="link"):
    """`profile` came in through `invite`: they and the inviter follow each
    other, the inviter hears about it once. Safe to call twice."""
    inviter = invite.inviter
    if inviter.pk == profile.pk:
        return False
    from .hub import blocked_between

    if blocked_between(profile, inviter):
        return False
    with transaction.atomic():
        first = profile.invited_by_id is None
        if first:
            Profile.objects.filter(pk=profile.pk).update(invited_by=inviter, invited_via=(channel or "link")[:20])
            profile.invited_by, profile.invited_via = inviter, channel
        made = False
        for a, b in ((profile, inviter), (inviter, profile)):
            follow, created = Follow.objects.get_or_create(
                follower=a, followee=b, defaults={"status": Follow.ACCEPTED, "source": Follow.INVITE,
                                                  "accepted_at": timezone.now()})
            if not created and follow.status != Follow.ACCEPTED:
                follow.status, follow.accepted_at = Follow.ACCEPTED, timezone.now()
                follow.save(update_fields=["status", "accepted_at"])
            made = made or created
        if first:
            Invite.objects.filter(pk=invite.pk).update(joined=invite.joined + 1)
    if made:
        _notify(inviter, "friends.joined", profile)
    return made


def apply_pending_invite(request, profile):
    """After joining (or on any visit with a remembered link): apply it once."""
    data = request.session.pop(INVITE_SESSION_KEY, None) or {}
    invite = invite_by_code(data.get("code")) if data else None
    if invite is None:
        return None
    join_through_invite(profile, invite, data.get("via", "link"))
    return invite.inviter


# ---- following --------------------------------------------------------------------

def is_open(profile):
    """Books open to everyone: anyone may follow at once."""
    return bool(profile.profile_public or profile.public_library)


def status_between(viewer, other):
    """'self', 'accepted', 'pending' or None: how viewer follows other."""
    if viewer.pk == other.pk:
        return "self"
    f = Follow.objects.filter(follower=viewer, followee=other).values_list("status", flat=True).first()
    return f


def follow(viewer, other):
    if viewer.pk == other.pk:
        raise FriendsError("friends.err.self")
    from .hub import blocked_between

    if blocked_between(viewer, other):
        raise FriendsError("friends.err.blocked")
    existing = Follow.objects.filter(follower=viewer, followee=other).first()
    if existing:
        return existing
    accepted = is_open(other)
    f = Follow.objects.create(follower=viewer, followee=other, status=Follow.ACCEPTED if accepted else Follow.PENDING,
                              source=Follow.OPEN if accepted else Follow.REQUEST,
                              accepted_at=timezone.now() if accepted else None)
    _notify(other, "friends.followed" if accepted else "friends.asked", viewer)
    return f


def accept(me, follow_row):
    if follow_row.followee_id != me.pk:
        raise FriendsError("friends.err.not_yours")
    if follow_row.status != Follow.ACCEPTED:
        follow_row.status, follow_row.accepted_at = Follow.ACCEPTED, timezone.now()
        follow_row.save(update_fields=["status", "accepted_at"])
        _notify(follow_row.follower, "friends.accepted", me)
    return follow_row


def decline(me, follow_row):
    """A request I do not want: gone, and nobody is told."""
    if follow_row.followee_id != me.pk:
        raise FriendsError("friends.err.not_yours")
    follow_row.delete()


def unfollow(me, other):
    Follow.objects.filter(follower=me, followee=other).delete()


def remove_follower(me, other):
    """Quietly: they stop seeing my books and are not told."""
    Follow.objects.filter(follower=other, followee=me).delete()


def following(profile):
    return (Profile.objects.filter(followers__follower=profile, followers__status=Follow.ACCEPTED)
            .order_by("display_name"))


def followers(profile):
    return (Profile.objects.filter(following__followee=profile, following__status=Follow.ACCEPTED)
            .order_by("display_name"))


def requests_for(profile):
    return Follow.objects.filter(followee=profile, status=Follow.PENDING).select_related("follower").order_by("-created_at")


def find_people(viewer, q):
    """Anyone, by name: everybody may ask to follow everybody."""
    from .hub import blocked_ids

    q = (q or "").strip()[:60]
    if len(q) < 2:
        return Profile.objects.none()
    return (Profile.objects.filter(display_name__icontains=q).exclude(pk=viewer.pk)
            .exclude(pk__in=blocked_ids(viewer)).order_by("display_name")[:40])


# ---- the friends page (Avi, 2026-10-23) -----------------------------------------------
# A search at the top that answers from the second letter; when not searching, one
# "invite" button and only what needs me: requests, people who asked for my books,
# and new friends. The full list is one link away.

FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
NEW_DAYS = 30


def name_pattern(q):
    """A search anywhere in the name ("מו" finds "סלמון"), with a final letter and
    its ordinary form the same ("סלמונ" finds "סלמון")."""
    out = []
    for ch in q:
        base = FINALS.get(ch, ch)
        final = next((k for k, v in FINALS.items() if v == base), None)
        out.append(f"[{base}{final}]" if final else re.escape(ch))
    return "".join(out)


def friend_ids(profile):
    """Everyone I follow or who follows me, accepted."""
    rows = Follow.objects.filter(status=Follow.ACCEPTED).filter(Q(follower=profile) | Q(followee=profile))
    return {r.followee_id if r.follower_id == profile.pk else r.follower_id
            for r in rows.only("follower_id", "followee_id")}


def search(viewer, q):
    """My friends first, then everyone else on Books by that name (anyone may ask)."""
    from .hub import blocked_ids

    q = (q or "").strip()[:60]
    if len(q) < 2:
        return {"q": q, "friends": [], "others": []}
    found = (Profile.objects.filter(display_name__iregex=name_pattern(q)).exclude(pk=viewer.pk)
             .exclude(pk__in=blocked_ids(viewer)))
    ids = friend_ids(viewer)
    status = dict(Follow.objects.filter(follower=viewer).values_list("followee_id", "status"))
    return {
        "q": q,
        "friends": list(found.filter(pk__in=ids).order_by("display_name")[:30]),
        "others": [{"p": p, "status": status.get(p.pk)} for p in found.exclude(pk__in=ids).order_by("display_name")[:20]],
    }


def new_friends(profile, days=NEW_DAYS, limit=12):
    """People who became my friends in the last month, newest first, and whether I
    follow them back."""
    since = timezone.now() - timedelta(days=days)
    rows = (Follow.objects.filter(status=Follow.ACCEPTED).filter(Q(follower=profile) | Q(followee=profile))
            .filter(Q(accepted_at__gte=since) | Q(accepted_at__isnull=True, created_at__gte=since))
            .select_related("follower", "followee"))
    i_follow = set(Follow.objects.filter(follower=profile, status=Follow.ACCEPTED).values_list("followee_id", flat=True))
    people = {}
    for r in rows:
        other = r.follower if r.followee_id == profile.pk else r.followee
        when = r.accepted_at or r.created_at
        if other.pk not in people or when > people[other.pk]["when"]:
            people[other.pk] = {"p": other, "when": when, "i_follow": other.pk in i_follow,
                                "invite": r.source == Follow.INVITE}
    return sorted(people.values(), key=lambda x: x["when"], reverse=True)[:limit]


def want_my_books(profile, limit=12):
    """People who asked for one of my books and wait for my answer. (A friend's
    wishlist stays private: it is not shown here.)"""
    from .models import Deal

    return list(Deal.objects.filter(owner=profile, status=Deal.REQUESTED)
                .select_related("requester", "copy__entry").order_by("-created_at")[:limit])


# ---- seeing a friend's library ------------------------------------------------------

def library_level(viewer, owner):
    """'all' (me, or an accepted follower: everything but 'only me'),
    'public' (only books marked for everyone, on a public library), or None."""
    if viewer.pk == owner.pk:
        return "all"
    from .hub import blocked_between

    if blocked_between(viewer, owner):
        return None
    if Follow.objects.filter(follower=viewer, followee=owner, status=Follow.ACCEPTED).exists():
        return "all"
    if owner.public_library or owner.profile_public:
        return "public"
    return None


def visible_copies(viewer, owner):
    level = library_level(viewer, owner)
    qs = Copy.objects.filter(owner=owner, status__in=Copy.HELD)
    if level == "all":
        return qs if viewer.pk == owner.pk else qs.exclude(visibility=Copy.HIDDEN)
    if level == "public":
        return qs.filter(visibility=Copy.PUBLIC)
    return qs.none()


def can_see_spines(viewer, owner):
    if viewer.pk == owner.pk:
        return True
    return owner.followers_see_spines and Follow.objects.filter(
        follower=viewer, followee=owner, status=Follow.ACCEPTED).exists()


def counts(profile):
    return {"following": following(profile).count(), "followers": followers(profile).count(),
            "requests": requests_for(profile).count()}


def _notify(profile, kind, person):
    Notification.objects.create(profile=profile, kind=kind, person=person)
