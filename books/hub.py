"""The hub (spec BK5): finding books near you, asking, meeting, handing over,
lending and returning, swapping and selling, and what happens when it goes
wrong. Every state change is one function here; pages and the API call
these and never change a Deal themselves.

Avi's rules (2026-10-19): notifications in the app only; after approval each
side may open more ways to talk (phone, WhatsApp, email); a loan is lost at
twice its loan time and nobody is blocked for it, the borrower's reliability
goes down instead; during the pilot everyone may ask.
"""

import logging
import math
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import jobs, mail
from .models import (
    Block,
    Copy,
    CopyTransfer,
    Deal,
    Follow,
    Message,
    Notification,
    Offer,
    Profile,
    Wish,
    round_coordinate,
)
from .textnorm import normalize

log = logging.getLogger(__name__)

SHARE_WAYS = ("phone", "whatsapp", "email")
DUE_SOON_DAYS = 3
LOST_FACTOR = 2
FRIENDS_FIRST_HOURS = 48  # an offer is the friends' alone for two days (Avi, 2026-10-23); BOOKS_FRIENDS_FIRST_HOURS
FREE_FRIEND_DEALS = 4  # a free person's transactions with friends on Pro's terms (Avi, 2026-10-23)
TRANSFER_KIND = {Offer.SELL: "sold", Offer.EXCHANGE: "exchanged", Offer.GIVE: "given"}


class DealError(Exception):
    """A refused action; the message is a catalogue key (hub.err.*)."""


# ---- who may ask ------------------------------------------------------------------

def can_start(profile):
    """Starting a request is the 4.99 tier's (books/tiers.py); answering one is free."""
    from .tiers import allows

    return allows(profile, "ask")


def blocked_between(a, b):
    return Block.objects.filter(Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)).exists()


def are_friends(a, b):
    """Accepted, either direction."""
    return Follow.objects.filter(status=Follow.ACCEPTED).filter(
        Q(follower=a, followee=b) | Q(follower=b, followee=a)).exists()


def friend_deals_used(profile):
    """The free person's four: requests they started that reached approval."""
    return Deal.objects.filter(requester=profile).exclude(
        status__in=(Deal.REQUESTED, Deal.DECLINED, Deal.CANCELLED)).count()


def friend_deals_left(profile):
    return max(0, FREE_FRIEND_DEALS - friend_deals_used(profile))


def may_ask(requester, owner):
    """Why this person may not ask this owner, or None. Pro asks anyone; a
    free person asks friends only, four times on Pro's terms."""
    if can_start(requester):
        return None
    if not are_friends(requester, owner):
        return "hub.err.tier"
    if friend_deals_left(requester) <= 0:
        return "hub.err.friends_quota"
    return None


def can_see_copy(viewer, copy):
    """A friend sees everything but "only me"; anyone sees what is public."""
    if copy.status != Copy.WITH_OWNER or copy.display_only or copy.visibility == Copy.HIDDEN:
        return False
    if copy.visibility == Copy.PUBLIC:
        return True
    return are_friends(viewer, copy.owner)


def friends_first_hours():
    return int(getattr(settings, "BOOKS_FRIENDS_FIRST_HOURS", FRIENDS_FIRST_HOURS))


def offer_open_to(viewer, offer, now=None):
    """Friends from the first minute; everyone else after two days."""
    if are_friends(viewer, offer.copy.owner):
        return True
    now = now or timezone.now()
    return offer.created_at <= now - timedelta(hours=friends_first_hours())


def blocked_ids(profile):
    mine = Block.objects.filter(Q(blocker=profile) | Q(blocked=profile)).values_list("blocker_id", "blocked_id")
    return {x for pair in mine for x in pair} - {profile.pk}


# ---- distance --------------------------------------------------------------------------

def km_between(a, b):
    if None in (a.area_lat, a.area_lng, b.area_lat, b.area_lng):
        return None
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), (a.area_lat, a.area_lng, b.area_lat, b.area_lng))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(d))


def same_area(a, b):
    return bool(a.area_name) and normalize(a.area_name) == normalize(b.area_name)


@jobs.job("profile.geocode")
def geocode_job(job):
    """The person's area as a rounded point, from OpenStreetMap's Nominatim
    (one request, a contact in the User-Agent, their usage policy). Never
    more precise than two decimals; an address was never asked for."""
    profile = Profile.objects.filter(pk=job.ref_id).first()
    if profile is None or not profile.area_name or profile.area_lat is not None:
        return
    contact = getattr(settings, "BOOKS_CONTACT_EMAIL", "")
    r = requests.get("https://nominatim.openstreetmap.org/search", timeout=10,
                     params={"q": profile.area_name, "format": "json", "limit": 1, "countrycodes": "il"},
                     headers={"User-Agent": f"babook-books/1.0 ({contact})"})
    if r.status_code != 200:
        return
    hits = r.json()
    if not hits:
        return
    profile.area_lat = round_coordinate(hits[0]["lat"])
    profile.area_lng = round_coordinate(hits[0]["lon"])
    profile.save(update_fields=["area_lat", "area_lng"])


def area_changed(profile):
    """Call after the area name changes: forget the old point, find the new one."""
    Profile.objects.filter(pk=profile.pk).update(area_lat=None, area_lng=None)
    profile.area_lat = profile.area_lng = None
    if profile.area_name:
        jobs.enqueue("profile.geocode", ref_id=profile.pk, profile=profile)


# ---- near you ------------------------------------------------------------------------------

def offered_copies(viewer, kind=None, q=None, tag=None, language=None, limit=300, circles_only=False):
    """Public, offered, held copies of other people within the viewer's
    radius (or in the same named area when either has no point), plus every
    circle peer's at any distance (BK6), nearest first. Returns
    [(copy, km or None)]."""
    from .circles import peer_ids

    hidden = blocked_ids(viewer)
    peers = peer_ids(viewer)
    from .friends import friend_ids

    offers = Offer.objects.filter(is_active=True, copy__visibility=Copy.PUBLIC, copy__status=Copy.WITH_OWNER,
                                  copy__display_only=False).exclude(copy__owner=viewer).exclude(copy__owner_id__in=hidden)
    # Friends first (Avi, 2026-10-23): a fresh offer is the owner's friends' alone for two days.
    offers = offers.filter(Q(copy__owner_id__in=friend_ids(viewer)) |
                           Q(created_at__lte=timezone.now() - timedelta(hours=friends_first_hours())))
    if kind:
        offers = offers.filter(kind=kind)
    if q:
        for tok in normalize(q).split()[:6]:
            offers = offers.filter(copy__entry__search_text__contains=tok)
    if tag:
        offers = offers.filter(copy__entry__tags__key=tag)
    if language:
        offers = offers.filter(copy__entry__language=language)
    if circles_only:
        offers = offers.filter(copy__owner_id__in=peers)
    copy_ids = list(offers.values_list("copy_id", flat=True).distinct()[:2000])
    copies = (Copy.objects.filter(pk__in=copy_ids).select_related("entry", "owner")
              .prefetch_related("offers", "entry__creators"))
    out = []
    for c in copies:
        km = km_between(viewer, c.owner)
        if c.owner_id in peers:
            pass  # a circle's books reach its members beyond the radius
        elif km is None:
            if not same_area(viewer, c.owner):
                continue
        elif km > (viewer.radius_km or 10):
            continue
        out.append((c, km))
    out.sort(key=lambda pair: (pair[1] is None, pair[1] or 0, pair[0].entry.title))
    return out[:limit]


# ---- notifications ---------------------------------------------------------------------

def notify(profile, kind, deal=None, entry=None, copy=None, thread=None):
    n = Notification.objects.create(profile=profile, kind=kind, deal=deal, entry=entry, copy=copy, thread=thread)
    mail.notify_later(n)  # every step of a request also by email (Avi, 2026-10-23)
    return n


def unread_count(profile):
    return Notification.objects.filter(profile=profile, read_at__isnull=True).count()


# ---- asking ---------------------------------------------------------------------------------

def open_deal(requester, copy):
    return Deal.objects.filter(requester=requester, copy=copy, status__in=Deal.OPEN).first()


@transaction.atomic
def ask(requester, copy, kind, message="", swap_copy=None):
    """One tap: "I want to receive / borrow / buy / swap for this" (Avi,
    2026-10-23). On an offer the owner made, when it is open to me (friends
    at once, everyone after two days); or, as a friend, on any book I can
    see, offered or not: the owner answers."""
    if copy.owner_id == requester.pk:
        raise DealError("hub.err.own")
    if kind not in dict(Offer.KINDS):
        raise DealError("hub.err.not_offered")
    why = may_ask(requester, copy.owner)
    if why:
        raise DealError(why)
    if blocked_between(requester, copy.owner):
        raise DealError("hub.err.blocked")
    if not can_see_copy(requester, copy):
        raise DealError("hub.err.not_offered")
    offer = copy.offers.filter(kind=kind, is_active=True).first()
    if offer is not None and not offer_open_to(requester, offer):
        offer = None
    if offer is None and not are_friends(requester, copy.owner):
        raise DealError("hub.err.not_offered")
    if open_deal(requester, copy):
        raise DealError("hub.err.already")
    if kind == Offer.EXCHANGE and swap_copy is not None:
        if swap_copy.owner_id != requester.pk or swap_copy.status != Copy.WITH_OWNER:
            raise DealError("hub.err.swap_copy")
    if kind != Offer.EXCHANGE:
        swap_copy = None
    deal = Deal.objects.create(offer=offer, copy=copy, owner=copy.owner, requester=requester, kind=kind,
                               swap_copy=swap_copy,
                               loan_days=(offer.loan_days if offer else None) if kind == Offer.LEND else None,
                               price_amount=(offer.price_amount if offer else None) if kind == Offer.SELL else None)
    if message.strip():
        Message.objects.create(deal=deal, sender=requester, body=message.strip()[:2000])
    notify(copy.owner, "deal.requested", deal=deal)
    return deal


def askers(copy):
    """Everyone waiting for this copy, in the order they asked (Avi,
    2026-10-23: the owner sees who came first and chooses)."""
    return list(Deal.objects.filter(copy=copy, status=Deal.REQUESTED).select_related("requester")
                .order_by("created_at"))


def place_in_line(deal):
    """1 for the first to ask; None once the request is not waiting."""
    if deal.status != Deal.REQUESTED:
        return None
    return Deal.objects.filter(copy=deal.copy, status=Deal.REQUESTED, created_at__lt=deal.created_at).count() + 1


TAKEN = "taken"


def went_elsewhere(deal):
    """The book went to someone else (declined because another asker was chosen)."""
    return deal.status == Deal.DECLINED and deal.closed_note == TAKEN


def elsewhere(viewer, entry, exclude_copy=None, limit=6):
    """Where else this book may be had: friends' copies I can see (offered or
    not), then copies offered near me. For the asker whose request lost."""
    from .friends import friend_ids

    out, seen = [], {exclude_copy.pk} if exclude_copy else set()
    fids = friend_ids(viewer)
    for c in (Copy.objects.filter(entry=entry, owner_id__in=fids, status=Copy.WITH_OWNER, display_only=False)
              .exclude(visibility=Copy.HIDDEN).exclude(owner_id__in=blocked_ids(viewer))
              .select_related("owner").prefetch_related("offers")[:limit]):
        if c.pk not in seen:
            seen.add(c.pk)
            out.append({"copy": c, "friend": True, "kinds": [o.kind for o in c.offers.all() if o.is_active]})
    for c, km in offered_copies(viewer, limit=200):
        if c.entry_id == entry.pk and c.pk not in seen and len(out) < limit:
            seen.add(c.pk)
            out.append({"copy": c, "friend": False, "km": km, "kinds": [o.kind for o in c.offers.all() if o.is_active]})
    return out


def friends_holding(viewer, entry, limit=12):
    """Friends who hold this book and let me see it, with what they offered,
    and my open request on each if any (Avi, 2026-10-23: the book's page
    shows who has it and lets me ask in one tap)."""
    from .friends import friend_ids

    out = []
    copies = (Copy.objects.filter(entry=entry, owner_id__in=friend_ids(viewer), status=Copy.WITH_OWNER,
                                  display_only=False).exclude(visibility=Copy.HIDDEN)
              .exclude(owner_id__in=blocked_ids(viewer)).select_related("owner").prefetch_related("offers")
              .order_by("owner__display_name")[:limit])
    for c in copies:
        out.append({"copy": c, "kinds": [o.kind for o in c.offers.all() if o.is_active],
                    "open": open_deal(viewer, c)})
    return out


def _need(deal, profile, role, *statuses):
    if deal.role(profile) != role and role != "either":
        raise DealError("hub.err.not_yours")
    if role == "either" and deal.role(profile) is None:
        raise DealError("hub.err.not_yours")
    if statuses and deal.status not in statuses:
        raise DealError("hub.err.wrong_state")


def approve(deal, profile):
    _need(deal, profile, "owner", Deal.REQUESTED)
    if deal.copy.status != Copy.WITH_OWNER:
        raise DealError("hub.err.not_offered")
    deal.status = Deal.APPROVED
    deal.save(update_fields=["status", "updated_at"])
    notify(deal.requester, "deal.approved", deal=deal)
    # One copy, one taker: other open requests for it are declined.
    for other in Deal.objects.filter(copy=deal.copy, status=Deal.REQUESTED).exclude(pk=deal.pk):
        other.status = Deal.DECLINED
        other.closed_note = TAKEN
        other.save(update_fields=["status", "closed_note", "updated_at"])
        notify(other.requester, "deal.declined", deal=other)
    return deal


def decline(deal, profile):
    _need(deal, profile, "owner", Deal.REQUESTED)
    deal.status = Deal.DECLINED
    deal.save(update_fields=["status", "updated_at"])
    notify(deal.requester, "deal.declined", deal=deal)
    return deal


def cancel(deal, profile, note=""):
    _need(deal, profile, "either", Deal.REQUESTED, Deal.APPROVED)
    deal.status = Deal.CANCELLED
    deal.closed_note = note[:300]
    deal.save(update_fields=["status", "closed_note", "updated_at"])
    notify(deal.other(profile), "deal.cancelled", deal=deal)
    return deal


def set_meeting(deal, profile, place=None, note=""):
    _need(deal, profile, "either", Deal.APPROVED)
    deal.meeting_place = place
    deal.meeting_note = note.strip()[:300]
    deal.save(update_fields=["meeting_place", "meeting_note", "updated_at"])
    notify(deal.other(profile), "deal.meeting", deal=deal)
    return deal


# ---- handover, return, transfer -----------------------------------------------------------

def _next_position(profile):
    from .shelf import next_position

    return next_position(profile)


def transfer(copy, to_profile, deal, kind):
    """The same row moves to its new owner, private and unoffered on their
    shelf, with a record of the move (data model decision)."""
    from_profile = copy.owner
    CopyTransfer.objects.create(copy=copy, from_profile=from_profile, to_profile=to_profile, deal=deal, kind=kind)
    copy.offers.all().delete()
    copy.owner = to_profile
    copy.visibility = Copy.PRIVATE
    copy.status = Copy.WITH_OWNER
    copy.location_note = ""
    copy.added_via = "received"
    copy.position = _next_position(to_profile)
    copy.save()
    Wish.objects.filter(profile=to_profile, entry=copy.entry).delete()
    return copy


@transaction.atomic
def confirm_handover(deal, profile):
    _need(deal, profile, "either", Deal.APPROVED)
    now = timezone.now()
    if deal.role(profile) == "owner":
        deal.owner_confirmed_handover_at = deal.owner_confirmed_handover_at or now
    else:
        deal.requester_confirmed_handover_at = deal.requester_confirmed_handover_at or now
    deal.save(update_fields=["owner_confirmed_handover_at", "requester_confirmed_handover_at", "updated_at"])
    if not (deal.owner_confirmed_handover_at and deal.requester_confirmed_handover_at):
        notify(deal.other(profile), "deal.handover_waiting", deal=deal)
        return deal
    # Both sides confirmed: the book changed hands.
    if deal.kind == Offer.LEND:
        deal.status = Deal.HANDED_OVER
        deal.due_date = (now + timedelta(days=deal.loan_days or 30)).date()
        deal.copy.status = Copy.ON_LOAN_OUT
        deal.copy.save(update_fields=["status"])
    elif deal.kind == Offer.EXCHANGE:
        deal.status = Deal.COMPLETED
        transfer(deal.copy, deal.requester, deal, "exchanged")
        if deal.swap_copy_id:
            transfer(deal.swap_copy, deal.owner, deal, "exchanged")
    else:
        # Sold or given: the book stands on the receiver's shelf now (Avi, 2026-10-23).
        deal.status = Deal.COMPLETED
        transfer(deal.copy, deal.requester, deal, TRANSFER_KIND[deal.kind])
    deal.save(update_fields=["status", "due_date", "updated_at"])
    for p in (deal.owner, deal.requester):
        notify(p, "deal.handed_over", deal=deal)
    from . import play

    play.deal_handed_over(deal)
    return deal


def mark_returned(deal, profile):
    _need(deal, profile, "requester", Deal.HANDED_OVER, Deal.LOST, Deal.DISPUTED)
    if deal.kind != Offer.LEND:
        raise DealError("hub.err.wrong_state")
    deal.requester_marked_returned_at = timezone.now()
    deal.save(update_fields=["requester_marked_returned_at", "updated_at"])
    notify(deal.owner, "deal.returned_marked", deal=deal)
    return deal


@transaction.atomic
def confirm_returned(deal, profile):
    _need(deal, profile, "owner", Deal.HANDED_OVER, Deal.LOST, Deal.DISPUTED)
    if deal.kind != Offer.LEND:
        raise DealError("hub.err.wrong_state")
    today = timezone.now().date()
    deal.returned_confirmed_at = timezone.now()
    deal.returned_late = bool(deal.due_date and today > deal.due_date)
    deal.status = Deal.RETURNED
    deal.save(update_fields=["returned_confirmed_at", "returned_late", "status", "updated_at"])
    deal.copy.status = Copy.WITH_OWNER
    deal.copy.save(update_fields=["status"])
    notify(deal.requester, "deal.returned", deal=deal)
    from . import play

    play.deal_returned(deal)
    return deal


def dispute(deal, profile, note):
    """A flag on the request and a message to the other side. Books does not
    decide between them (Avi, 2026-10-19: it is between the two people)."""
    _need(deal, profile, "either", Deal.APPROVED, Deal.HANDED_OVER, Deal.LOST)
    deal.status = Deal.DISPUTED
    deal.closed_note = (note or "").strip()[:300]
    deal.save(update_fields=["status", "closed_note", "updated_at"])
    notify(deal.other(profile), "deal.disputed", deal=deal)
    return deal


# ---- messages and ways to talk ---------------------------------------------------------------

def send_message(deal, profile, body):
    _need(deal, profile, "either")
    if deal.status in (Deal.DECLINED, Deal.CANCELLED):
        raise DealError("hub.err.wrong_state")
    if blocked_between(deal.owner, deal.requester):
        raise DealError("hub.err.blocked")
    body = (body or "").strip()[:2000]
    if not body:
        raise DealError("hub.err.empty")
    msg = Message.objects.create(deal=deal, sender=profile, body=body)
    mail.message_later(msg)  # every message also by email (Avi, 2026-10-23)
    other = deal.other(profile)
    # One unread "new message" per deal is enough; more is noise.
    if not Notification.objects.filter(profile=other, deal=deal, kind="deal.message", read_at__isnull=True).exists():
        notify(other, "deal.message", deal=deal)
    return msg


def read_messages(deal, profile):
    Message.objects.filter(deal=deal, read_at__isnull=True).exclude(sender=profile).update(read_at=timezone.now())
    Notification.objects.filter(profile=profile, deal=deal, read_at__isnull=True).update(read_at=timezone.now())


def set_shares(deal, profile, ways):
    _need(deal, profile, "either", Deal.APPROVED, Deal.HANDED_OVER, Deal.RETURNED, Deal.COMPLETED, Deal.LOST,
          Deal.DISPUTED)
    ways = [w for w in ways if w in SHARE_WAYS]
    if deal.role(profile) == "owner":
        deal.owner_shares = ",".join(ways)
    else:
        deal.requester_shares = ",".join(ways)
    deal.save(update_fields=["owner_shares", "requester_shares", "updated_at"])
    if ways:
        notify(deal.other(profile), "deal.shared", deal=deal)
    return deal


def whatsapp_link(phone):
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "972" + digits[1:]  # an Israeli local number
    return f"https://wa.me/{digits}" if len(digits) >= 9 else ""


def contact_for(deal, viewer):
    """What the other side chose to show the viewer, and only after approval."""
    if deal.status in (Deal.REQUESTED, Deal.DECLINED, Deal.CANCELLED) or deal.role(viewer) is None:
        return {}
    other = deal.other(viewer)
    shared = (deal.owner_shares if other.pk == deal.owner_id else deal.requester_shares).split(",")
    out = {}
    if "phone" in shared and other.phone:
        out["phone"] = other.phone
    if "whatsapp" in shared and other.phone:
        link = whatsapp_link(other.phone)
        if link:
            out["whatsapp"] = link
    if "email" in shared and other.user.email:
        out["email"] = other.user.email
    return out


# ---- blocking ------------------------------------------------------------------------------

@transaction.atomic
def block(blocker, blocked):
    if blocker.pk == blocked.pk:
        raise DealError("hub.err.own")
    Block.objects.get_or_create(blocker=blocker, blocked=blocked)
    # Open asks between them stop; a book already handed over stays on record.
    for deal in Deal.objects.filter(Q(owner=blocker, requester=blocked) | Q(owner=blocked, requester=blocker),
                                    status__in=[Deal.REQUESTED, Deal.APPROVED]):
        deal.status = Deal.CANCELLED
        deal.closed_note = "blocked"
        deal.save(update_fields=["status", "closed_note", "updated_at"])


def unblock(blocker, blocked):
    Block.objects.filter(blocker=blocker, blocked=blocked).delete()


# ---- reputation, as counts --------------------------------------------------------------------

def reputation(profile):
    """Counts, never stars (spec 12.4). Reliability is the share of borrowed
    books returned on time out of loans that ended; a lost book counts
    against it (Avi: lower the rating, do not block)."""
    as_borrower = Deal.objects.filter(requester=profile, kind=Offer.LEND)
    returned = as_borrower.filter(status=Deal.RETURNED)
    on_time = returned.filter(returned_late=False).count()
    late = returned.filter(returned_late=True).count()
    lost = as_borrower.filter(status=Deal.LOST).count()
    ended = on_time + late + lost
    lent = Deal.objects.filter(owner=profile, kind=Offer.LEND,
                               status__in=[Deal.HANDED_OVER, Deal.RETURNED, Deal.LOST]).count()
    moved = [Offer.EXCHANGE, Offer.SELL, Offer.GIVE]
    passed_on = Deal.objects.filter(owner=profile, kind__in=moved, status=Deal.COMPLETED).count()
    received = Deal.objects.filter(requester=profile, kind__in=moved, status=Deal.COMPLETED).count()
    given = Deal.objects.filter(owner=profile, kind=Offer.GIVE, status=Deal.COMPLETED).count()
    return {"lent": lent, "passed_on": passed_on, "received": received, "given": given, "borrowed_on_time": on_time,
            "borrowed_late": late, "lost": lost, "ended": ended,
            "reliability": round(100 * on_time / ended) if ended else None}


# ---- reminders and lost loans -------------------------------------------------------------------

def sweep(today=None):
    """Due soon, overdue, and lost at twice the loan time. Idempotent: each
    reminder is sent once (Deal.reminded). Run by a job, the token endpoint,
    and lazily when someone opens their deals."""
    today = today or timezone.now().date()
    changed = 0
    for deal in Deal.objects.filter(kind=Offer.LEND, status=Deal.HANDED_OVER, due_date__isnull=False):
        sent = set(filter(None, deal.reminded.split(",")))
        before = set(sent)
        days_left = (deal.due_date - today).days
        if 0 <= days_left <= DUE_SOON_DAYS and "soon" not in sent:
            notify(deal.requester, "deal.due_soon", deal=deal)
            sent.add("soon")
        if days_left < 0 and "due" not in sent:
            notify(deal.requester, "deal.overdue", deal=deal)
            notify(deal.owner, "deal.overdue_owner", deal=deal)
            sent.add("due")
        handed = (deal.requester_confirmed_handover_at or deal.owner_confirmed_handover_at or timezone.now()).date()
        lost_on = handed + timedelta(days=LOST_FACTOR * (deal.loan_days or 30))
        if today >= lost_on:
            deal.status = Deal.LOST
            deal.copy.status = Copy.LOST
            deal.copy.save(update_fields=["status"])
            for p in (deal.owner, deal.requester):
                notify(p, "deal.lost", deal=deal)
            sent.add("lost")
        if sent == before:
            continue
        deal.reminded = ",".join(sorted(sent))
        deal.save(update_fields=["status", "reminded", "updated_at"])
        changed += 1
    return changed


@jobs.job("deals.sweep")
def sweep_job(job):
    sweep()


def sweep_lazily():
    """At most every ten minutes, from a page view: no scheduler needed."""
    from django.core.cache import cache

    if cache.add("books:deals-swept", True, 600):
        try:
            sweep()
        except Exception:  # noqa: BLE001
            log.exception("books: deal sweep failed")


# ---- wishlist alerts ------------------------------------------------------------------------------

def alert_wishers(offer):
    """A book someone wants is now offered near them: tell them, once."""
    copy = offer.copy
    if not offer.is_active or copy.visibility != Copy.PUBLIC or copy.display_only:
        return 0
    from .circles import peer_ids

    n = 0
    peers = peer_ids(copy.owner)
    for wish in Wish.objects.filter(entry=copy.entry, notify_when_available=True).exclude(profile=copy.owner) \
            .select_related("profile"):
        p = wish.profile
        if blocked_between(p, copy.owner):
            continue
        if p.pk in peers:
            if not Notification.objects.filter(profile=p, kind="wish.available", copy=copy).exists():
                notify(p, "wish.available", entry=copy.entry, copy=copy)
                n += 1
            continue
        km = km_between(p, copy.owner)
        if km is None and not same_area(p, copy.owner):
            continue
        if km is not None and km > (p.radius_km or 10):
            continue
        if Notification.objects.filter(profile=p, kind="wish.available", copy=copy).exists():
            continue
        notify(p, "wish.available", entry=copy.entry, copy=copy)
        n += 1
    return n
