"""Circles (spec BK6): a book club, a school, a workplace, a neighbourhood.
Every change to a circle or its members is one function here; pages and the
API call these and never change a CircleMember themselves.

Decisions (2026-10-19, for Avi's ack): a private circle is joined only with
its link or code, an open one is listed and anyone may join; members see each
other's offered books beyond their radius, never a private book; only the
owner names moderators; a moderator may remove members (not the owner or
another moderator); an owner who leaves hands the circle to the longest
serving moderator, else the longest serving member, and the last person out
closes it.
"""

import secrets

from django.db import transaction
from django.db.models import Count, Q

from .models import Circle, CircleMember, Copy, MeetingPlace, Offer

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: read aloud at a scanning evening
CODE_LENGTH = 8


class CircleError(Exception):
    """A refused action; the message is a catalogue key (circle.err.*)."""


def new_code():
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Circle.objects.filter(join_code=code).exists():
            return code


def clean_code(code):
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())[:CODE_LENGTH + 4]


def membership(profile, circle):
    if profile is None:
        return None
    return CircleMember.objects.filter(profile=profile, circle=circle).first()


def with_counts():
    """Annotate before any filter on `members`: a filter on the same relation
    would otherwise shrink the count to the matching rows (one, me)."""
    return Circle.objects.annotate(n_members=Count("members", distinct=True))


def my_circles(profile):
    mine = CircleMember.objects.filter(profile=profile).values("circle_id")
    return with_counts().filter(pk__in=mine).order_by("name")


def open_circles(profile):
    mine = CircleMember.objects.filter(profile=profile).values("circle_id")
    return with_counts().filter(is_private=False).exclude(pk__in=mine).order_by("-n_members", "name")


def peer_ids(profile):
    """Everyone who shares at least one circle with this person."""
    mine = CircleMember.objects.filter(profile=profile).values("circle_id")
    return set(CircleMember.objects.filter(circle_id__in=mine).exclude(profile=profile)
               .values_list("profile_id", flat=True))


def shared_circle_ids(a, b):
    return set(CircleMember.objects.filter(profile=a).values_list("circle_id", flat=True)) & \
        set(CircleMember.objects.filter(profile=b).values_list("circle_id", flat=True))


def can_see(profile, circle):
    """An open circle's page is readable by anyone onboarded; a private one
    only by its members. Neither shows books or names to non-members."""
    return not circle.is_private or membership(profile, circle) is not None


# ---- creating, joining, leaving -------------------------------------------------------------

@transaction.atomic
def create(profile, name, kind="club", area_name="", description="", is_private=True):
    name = (name or "").strip()[:80]
    if not name:
        raise CircleError("circle.err.name")
    circle = Circle.objects.create(name=name, kind=kind if kind in dict(Circle.KINDS) else "other",
                                   area_name=(area_name or "").strip()[:80],
                                   description=(description or "").strip()[:500], join_code=new_code(),
                                   is_private=bool(is_private), created_by=profile)
    CircleMember.objects.create(circle=circle, profile=profile, role=CircleMember.OWNER)
    return circle


def by_code(code):
    return Circle.objects.filter(join_code=clean_code(code)).first()


def join(profile, circle, code=None):
    """Idempotent. A private circle needs its code (the invite link carries it)."""
    existing = membership(profile, circle)
    if existing:
        return existing
    if circle.is_private and clean_code(code) != circle.join_code:
        raise CircleError("circle.err.code")
    member, _ = CircleMember.objects.get_or_create(circle=circle, profile=profile)
    return member


@transaction.atomic
def leave(profile, circle):
    me = membership(profile, circle)
    if me is None:
        raise CircleError("circle.err.not_member")
    was_owner = me.role == CircleMember.OWNER
    me.delete()
    if not was_owner:
        return circle
    heir = (circle.members.filter(role=CircleMember.MODERATOR).order_by("joined_at").first()
            or circle.members.order_by("joined_at").first())
    if heir is None:
        circle.delete()  # the last person out closes it
        return None
    heir.role = CircleMember.OWNER
    heir.save(update_fields=["role"])
    return circle


def _actor(profile, circle, *roles):
    me = membership(profile, circle)
    if me is None or me.role not in roles:
        raise CircleError("circle.err.not_allowed")
    return me


def set_role(actor, member, role):
    """Only the owner names or removes moderators; ownership is not given
    away here (leaving hands it on)."""
    _actor(actor, member.circle, CircleMember.OWNER)
    if member.role == CircleMember.OWNER or role not in (CircleMember.MEMBER, CircleMember.MODERATOR):
        raise CircleError("circle.err.not_allowed")
    member.role = role
    member.save(update_fields=["role"])
    return member


def remove(actor, member):
    me = _actor(actor, member.circle, CircleMember.OWNER, CircleMember.MODERATOR)
    if member.role == CircleMember.OWNER or (member.role == CircleMember.MODERATOR and me.role != CircleMember.OWNER):
        raise CircleError("circle.err.not_allowed")
    if member.profile_id == actor.pk:
        raise CircleError("circle.err.not_allowed")
    member.delete()


def edit(actor, circle, **fields):
    _actor(actor, circle, CircleMember.OWNER, CircleMember.MODERATOR)
    name = (fields.get("name") or circle.name).strip()[:80]
    if not name:
        raise CircleError("circle.err.name")
    circle.name = name
    if fields.get("kind") in dict(Circle.KINDS):
        circle.kind = fields["kind"]
    circle.area_name = (fields.get("area_name", circle.area_name) or "").strip()[:80]
    circle.description = (fields.get("description", circle.description) or "").strip()[:500]
    if "is_private" in fields:
        circle.is_private = bool(fields["is_private"])
    circle.save()
    return circle


def new_join_code(actor, circle):
    """A leaked link stops working; members already in stay in."""
    _actor(actor, circle, CircleMember.OWNER, CircleMember.MODERATOR)
    circle.join_code = new_code()
    circle.save(update_fields=["join_code"])
    return circle.join_code


# ---- the circle's books and places -------------------------------------------------------------

def books(circle, viewer):
    """Members' public, offered, held books, as [(copy, km)] like near you."""
    from . import hub

    if membership(viewer, circle) is None:
        return []
    hidden = hub.blocked_ids(viewer)
    member_ids = circle.members.exclude(profile=viewer).exclude(profile_id__in=hidden).values("profile_id")
    copies = (Copy.objects.filter(owner_id__in=member_ids, visibility=Copy.PUBLIC, status=Copy.WITH_OWNER,
                                  display_only=False, offers__is_active=True)
              .distinct().select_related("entry", "owner").prefetch_related("offers", "entry__creators")
              .order_by("entry__title")[:500])
    return [(c, hub.km_between(viewer, c.owner)) for c in copies]


def book_count(circle):
    return (Offer.objects.filter(is_active=True, copy__owner__circle_memberships__circle=circle,
                                 copy__visibility=Copy.PUBLIC, copy__status=Copy.WITH_OWNER)
            .values("copy_id").distinct().count())


def add_place(actor, circle, name, area_name="", kind="other", notes="", is_partner=False):
    _actor(actor, circle, CircleMember.OWNER, CircleMember.MODERATOR)
    name = (name or "").strip()[:120]
    if not name:
        raise CircleError("circle.err.name")
    return MeetingPlace.objects.create(circle=circle, name=name, area_name=(area_name or "").strip()[:80],
                                       kind=kind if kind in dict(MeetingPlace.KINDS) else "other",
                                       notes=(notes or "").strip()[:300], is_partner=bool(is_partner))


def remove_place(actor, place):
    if place.circle_id is None:
        raise CircleError("circle.err.not_allowed")
    _actor(actor, place.circle, CircleMember.OWNER, CircleMember.MODERATOR)
    place.delete()


def places_for(a, b):
    """Meeting places two people may pick: everyone's, plus their shared circles'."""
    return MeetingPlace.objects.filter(Q(circle__isnull=True) | Q(circle_id__in=shared_circle_ids(a, b)),
                                       is_active=True)
