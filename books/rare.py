"""Rare books and the museum (spec BK10, 12.8). Kept modest: a spine photo
cannot show a printing line or a signature, so Books only suggests, the
owner decides, a curator looks, and nothing is ever valued.

- Hints: a copy may be special when its record is old (before 1966), its
  title mentions a first edition, or the owner's notes mention a signature
  or an inscription. A hint is shown to the owner only; marking is theirs.
- Review: the owner sends a copy to the curators with its photos; sending is
  consent for curators to see those photos. The curator answers in words.
- Provenance: the copy's history of changing hands (CopyTransfer), with
  other people's names only when their profile is public.
- The museum: curators (staff) build exhibitions; an item is shown only
  after its owner accepted, with their name only if they chose, and its
  photos only if they allowed.

Decisions (2026-10-20, for Avi's ack): the 1966 line from spec 12.8; staff
are the curators until a curator role exists; the museum is for signed-in
members like the rest of Books.
"""

import re

from django.db import transaction
from django.utils import timezone

from .hub import notify
from .models import Copy, CopyTransfer, Exhibit, ExhibitItem, RareReview

OLD_BEFORE = 1966
FIRST_EDITION = re.compile(r"מהדורה\s+ראשונה|דפוס\s+ראשון|first\s+edition|1st\s+ed", re.IGNORECASE)
SIGNED = re.compile(r"חתום|חתימ|הקדשה|מוקדש|signed|inscri|autograph|dedicat", re.IGNORECASE)
DEFAULT_RIGHTS = {"he": "צילום של בעל/ת העותק, מוצג ברשותו/ה.", "en": "Photographed by the copy's owner, shown with their permission."}


class RareError(Exception):
    """A refused action; the message is a catalogue key (rare.err.*)."""


# ---- hints ----------------------------------------------------------------------------------

def hints(copy):
    """Why this copy may be special: catalogue keys, for the owner only."""
    out = []
    entry = copy.entry
    if entry.year and entry.year < OLD_BEFORE:
        out.append("rare.why_old")
    if FIRST_EDITION.search(f"{entry.title} {entry.subtitle} {copy.notes} {copy.rarity_note}"):
        out.append("rare.why_first")
    if SIGNED.search(f"{copy.notes} {copy.rarity_note}"):
        out.append("rare.why_signed")
    return out


def maybe_rare(profile):
    """The owner's copies with a hint and not yet marked."""
    rows = []
    for copy in Copy.objects.filter(owner=profile, status__in=Copy.HELD, is_rare_candidate=False).select_related("entry"):
        if hints(copy):
            rows.append(copy)
    return rows


# ---- review -------------------------------------------------------------------------------------

def send_for_review(owner, copy, note=""):
    if copy.owner_id != owner.pk:
        raise RareError("rare.err.not_yours")
    if not copy.photos.filter(kind__in=["copyright_page", "signed"]).exists():
        raise RareError("rare.err.photo")
    copy.is_rare_candidate = True
    copy.save(update_fields=["is_rare_candidate"])
    review, created = RareReview.objects.get_or_create(copy=copy, defaults={"owner_note": (note or "")[:500]})
    if not created and review.status != RareReview.PENDING:
        review.status, review.curator_note, review.reviewed_at = RareReview.PENDING, "", None
        review.owner_note = (note or review.owner_note)[:500]
        review.save()
    return review


def withdraw(owner, copy):
    if copy.owner_id != owner.pk:
        raise RareError("rare.err.not_yours")
    RareReview.objects.filter(copy=copy).delete()
    ExhibitItem.objects.filter(copy=copy).delete()


def decide(curator, review, confirmed, note=""):
    if not curator.user.is_staff:
        raise RareError("rare.err.not_allowed")
    review.status = RareReview.CONFIRMED if confirmed else RareReview.NOT_RARE
    review.curator_note = (note or "")[:500]
    review.reviewed_by = curator
    review.reviewed_at = timezone.now()
    review.save()
    notify(review.copy.owner, "rare.reviewed", copy=review.copy)
    return review


# ---- who may see a copy's photos -------------------------------------------------------------------

def can_see_photo(viewer, photo):
    copy = photo.copy
    if viewer is None:
        return False
    if copy.owner_id == viewer.pk:
        return True
    if viewer.user.is_staff and RareReview.objects.filter(copy=copy).exists():
        return True  # sent for review: consent for curators
    return ExhibitItem.objects.filter(copy=copy, consent=ExhibitItem.ACCEPTED, show_photos=True,
                                      exhibit__is_published=True).exists()


# ---- provenance ------------------------------------------------------------------------------------

def provenance(copy, viewer=None):
    """The copy's changes of hands, oldest first; names only of people whose
    profile is public (or the viewer themselves)."""
    rows = []
    for t in CopyTransfer.objects.filter(copy=copy).select_related("from_profile", "to_profile").order_by("transferred_at"):
        def name(p):
            if p is None:
                return ""
            return p.display_name if (p.profile_public or (viewer is not None and p.pk == viewer.pk)) else ""
        rows.append({"when": t.transferred_at, "kind": t.kind, "from": name(t.from_profile), "to": name(t.to_profile)})
    return rows


# ---- the museum ------------------------------------------------------------------------------------

def _staff(profile):
    if not profile.user.is_staff:
        raise RareError("rare.err.not_allowed")


def new_exhibit(curator, title_he, title_en="", text_he="", text_en=""):
    _staff(curator)
    if not (title_he or "").strip():
        raise RareError("rare.err.title")
    return Exhibit.objects.create(curator=curator, title_he=title_he.strip()[:160], title_en=(title_en or "").strip()[:160],
                                  text_he=text_he or "", text_en=text_en or "")


@transaction.atomic
def invite(curator, exhibit, copy, note="", rights=""):
    """Ask the owner whether their copy may be shown. Only copies a curator
    confirmed as special can be invited."""
    _staff(curator)
    review = RareReview.objects.filter(copy=copy, status=RareReview.CONFIRMED).first()
    if review is None:
        raise RareError("rare.err.not_confirmed")
    item, created = ExhibitItem.objects.get_or_create(exhibit=exhibit, copy=copy, defaults={
        "entry": copy.entry, "note": note or "", "rights_statement": (rights or "")[:300],
        "position": exhibit.items.count()})
    if created:  # the owner is told; nothing shows until they answer
        from .models import Notification

        Notification.objects.create(profile=copy.owner, kind="rare.invited", exhibit_item=item, copy=copy)
    return item


def answer(owner, item, accept, show_name=False, show_photos=True):
    if item.copy is None or item.copy.owner_id != owner.pk:
        raise RareError("rare.err.not_yours")
    item.consent = ExhibitItem.ACCEPTED if accept else ExhibitItem.DECLINED
    item.show_owner_name = bool(show_name) and accept
    item.show_photos = bool(show_photos) and accept
    item.answered_at = timezone.now()
    item.save()
    return item


def publish(curator, exhibit, published=True):
    _staff(curator)
    exhibit.is_published = published
    exhibit.published_at = timezone.now() if published else None
    exhibit.save(update_fields=["is_published", "published_at"])
    return exhibit


def shown_items(exhibit):
    """What visitors see: accepted items only."""
    return (exhibit.items.filter(consent=ExhibitItem.ACCEPTED)
            .select_related("copy__owner", "entry").prefetch_related("copy__photos"))


def public_photos(item):
    if not item.show_photos or item.copy is None:
        return []
    return list(item.copy.photos.all())


def default_rights(lang):
    return DEFAULT_RIGHTS["he" if lang == "he" else "en"]

