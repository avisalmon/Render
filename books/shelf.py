"""From a shelf photo to books on the person's shelf (spec BK3, BK4).

`start_scan` prepares the photo (rotation, no metadata, GPS only rounded) and
queues the reading. The job reads the spines (books/recognition.py), records
the cost, and for every book read finds catalogue candidates: the local
catalogue first, the sources when it is thin, and always a way to keep the
book exactly as read. The person then confirms each one; nothing becomes a
Copy without their accept (data model section 9).
"""

import hashlib
import logging
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import catalog, images, jobs
from .models import (BookDetail, CatalogEntry, Copy, ModelCall, Offer, Profile, ScanCandidate, ScanItem, ShelfScan)
from .recognition import KeyProblem, read_shelf
from .textnorm import normalize, similarity

log = logging.getLogger(__name__)

FREE_CAP = 1000
SCAN_MAX_SIDE = 4000
HIGH_CONFIDENCE = Decimal("0.85")
CANDIDATES = 3
VISIBILITY_CHOICES = ("private", "public")
OFFER_KINDS = ("lend", "exchange", "sell")
DEFAULT_LOAN_DAYS = 30

# Spine colours for the home shelf, from the approved board. A book's colour
# is stable (a hash of its record), so the shelf looks the same every visit.
SPINE_PALETTE = [("#6B2320", "#EFD9A8"), ("#24384A", "#E8DDC7"), ("#2E4A3B", "#E8DDC7"), ("#5A1E1A", "#D8B46A"),
                 ("#A68240", "#1A140E"), ("#3C3C3C", "#EFE6D2"), ("#4A3B5C", "#E8DDC7"), ("#3D2A1E", "#D8B46A"),
                 ("#2B3442", "#E8DDC7"), ("#5C3A4A", "#EFD9A8"), ("#B08A48", "#1A140E"), ("#3A4A2E", "#E8DDC7")]


class CapReached(Exception):
    pass


# ---- the cap -------------------------------------------------------------------

def held_count(profile):
    return Copy.objects.filter(owner=profile, status__in=Copy.HELD).count()


def room_left(profile):
    if profile.tier != Profile.FREE:
        return None
    return max(FREE_CAP - held_count(profile), 0)


# ---- starting a scan -------------------------------------------------------------

def start_scan(profile, uploaded, shelf_label="", default_visibility="private", default_offers=()):
    # Read at up to 4000 px: measured 63/70 found and 3 extra, against 61/70
    # and 5 extra at 2000 px, same cost (books_measure, 2026-10-19).
    prepared = images.prepare(uploaded, max_side=SCAN_MAX_SIDE)
    if prepared.had_gps and profile.area_lat is None:
        # Bonus, never stored precisely (spec BK1 §1.6): only the rounded point.
        profile.area_lat, profile.area_lng = prepared.area_lat, prepared.area_lng
        profile.save(update_fields=["area_lat", "area_lng"])
    offers = [k for k in default_offers if k in OFFER_KINDS]
    visibility = default_visibility if default_visibility in VISIBILITY_CHOICES else "private"
    if offers:
        visibility = "public"
    scan = ShelfScan(owner=profile, shelf_label=shelf_label.strip()[:120], default_visibility=visibility,
                     default_offers=",".join(offers))
    scan.photo.save(f"{profile.pk}-{timezone.now():%Y%m%d%H%M%S}.jpg", ContentFile(prepared.data), save=False)
    scan.save()
    jobs.enqueue("scan.read", ref_id=scan.pk, profile=profile)
    return scan


# ---- the job ---------------------------------------------------------------------

@jobs.job("scan.read")
def read_job(job):
    scan = ShelfScan.objects.filter(pk=job.ref_id).select_related("owner").first()
    if scan is None or scan.status not in (ShelfScan.UPLOADED, ShelfScan.FAILED):
        return
    scan.status = ShelfScan.READING
    scan.error = ""
    scan.save(update_fields=["status", "error"])
    try:
        with scan.photo.open("rb") as fh:
            data = fh.read()
        reading = read_shelf(data)
    except KeyProblem as exc:
        scan.status, scan.error = ShelfScan.FAILED, "key"
        scan.save(update_fields=["status", "error"])
        log.error("books scan %s: the OpenAI key needs replacing: %s", scan.pk, exc)
        return
    except Exception as exc:  # noqa: BLE001
        scan.status, scan.error = ShelfScan.FAILED, str(exc)[:300]
        scan.save(update_fields=["status", "error"])
        raise
    for call in reading.calls:
        ModelCall.objects.create(profile=scan.owner, job=job, provider="openai", model=reading.model,
                                 purpose="shelf_read", input_tokens=call["input_tokens"],
                                 output_tokens=call["output_tokens"], cost_usd=call["cost_usd"],
                                 duration_ms=int(call["seconds"] * 1000))
    with transaction.atomic():
        scan.items.all().delete()
        for i, book in enumerate(reading.books):
            ScanItem.objects.create(scan=scan, position=i, raw_title=book.title[:300], raw_author=book.author[:200])
        scan.model_name = reading.model
        scan.cost_usd = reading.cost_usd
        scan.seconds = Decimal(str(reading.seconds))
        scan.books_found = len(reading.books)
        scan.save(update_fields=["model_name", "cost_usd", "seconds", "books_found"])
    for item in scan.items.all():
        try:
            find_candidates(item, created_by=scan.owner)
        except Exception:  # noqa: BLE001
            log.exception("books scan %s: candidates for item %s", scan.pk, item.pk)
    scan.status = ShelfScan.REVIEW if scan.books_found else ShelfScan.DONE
    scan.finished_at = timezone.now()
    scan.save(update_fields=["status", "finished_at"])


# ---- candidates ------------------------------------------------------------------

def _score(item, entry):
    title = similarity(item.raw_title, entry.title)
    if not item.raw_author:
        return title * 0.9
    names = [c.name for c in entry.creators.all()]
    author = max((similarity(item.raw_author, n) for n in names), default=0.0)
    if not names:
        return title * 0.85
    return 0.7 * title + 0.3 * author


def find_candidates(item, created_by=None, use_sources=True):
    """Local catalogue first, then the sources when nothing local is strong.
    Writes up to three ScanCandidates and the item's confidence."""
    query = f"{item.raw_title} {item.raw_author}".strip()
    pool = {e.pk: e for e in catalog.search_local(item.raw_title, limit=15)}
    if item.raw_author:
        for e in catalog.search_local(query, limit=10):
            pool.setdefault(e.pk, e)
    best = max((_score(item, e) for e in pool.values()), default=0.0)
    if use_sources and best < float(HIGH_CONFIDENCE):
        for e in catalog.import_lookup(query=query, created_by=created_by, limit=5):
            pool.setdefault(e.pk, e)
    ranked = sorted(pool.values(), key=lambda e: -_score(item, e))[:CANDIDATES]
    ScanCandidate.objects.filter(item=item).delete()
    for rank, e in enumerate(ranked):
        ScanCandidate.objects.create(item=item, entry=e, rank=rank,
                                     confidence=Decimal(str(round(_score(item, e), 3))))
    item.confidence = Decimal(str(round(_score(item, ranked[0]), 3))) if ranked else Decimal(0)
    item.save(update_fields=["confidence"])
    return ranked


# ---- confirming ------------------------------------------------------------------

def entry_from_text(title, author, profile):
    """Keep the book exactly as read or typed: an unverified record of its own,
    or the existing one if the catalogue already has that title and author."""
    from .sources.base import Record

    entry, _ = catalog.upsert_from_record(Record("manual", "", title.strip()[:300],
                                                 creators=[author.strip()] if author.strip() else []),
                                          created_by=profile)
    if entry.source == "":
        entry.source = "manual"
        entry.save(update_fields=["source"])
    BookDetail.objects.get_or_create(entry=entry)
    return entry


def next_position(profile):
    return (Copy.objects.filter(owner=profile).aggregate(m=Max("position"))["m"] or 0) + 1


@transaction.atomic
def accept(item, entry, visibility, offer_kinds, location_note, edited=False):
    profile = item.scan.owner
    left = room_left(profile)
    if left is not None and left <= 0:
        raise CapReached()
    offer_kinds = [k for k in offer_kinds if k in OFFER_KINDS]
    if offer_kinds:
        visibility = Copy.PUBLIC
    if visibility not in VISIBILITY_CHOICES:
        visibility = Copy.PRIVATE
    copy = item.copy or Copy(owner=profile, added_via="scan", position=next_position(profile))
    copy.entry = entry
    copy.visibility = visibility
    copy.location_note = (location_note or "").strip()[:120]
    copy.save()
    copy.offers.exclude(kind__in=offer_kinds).delete()
    for kind in offer_kinds:
        Offer.objects.get_or_create(copy=copy, kind=kind,
                                    defaults={"loan_days": DEFAULT_LOAN_DAYS if kind == Offer.LEND else None})
    item.copy = copy
    item.review_status = ScanItem.EDITED if edited else ScanItem.ACCEPTED
    item.save(update_fields=["copy", "review_status"])
    _refresh_scan(item.scan)
    return copy


def skip(item):
    item.review_status = ScanItem.SKIPPED
    item.save(update_fields=["review_status"])
    _refresh_scan(item.scan)


def add_missed(scan, title, author):
    pos = (scan.items.aggregate(m=Max("position"))["m"] or 0) + 1
    item = ScanItem.objects.create(scan=scan, position=pos, raw_title=title.strip()[:300],
                                   raw_author=author.strip()[:200], added_by_hand=True)
    find_candidates(item, created_by=scan.owner)
    scan.books_found = scan.items.count()
    scan.save(update_fields=["books_found"])
    if scan.status == ShelfScan.DONE:
        scan.status = ShelfScan.REVIEW
        scan.save(update_fields=["status"])
    return item


def accept_all_confident(scan):
    """One tap for every pending book the system is sure of, with the scan's
    default choices. Returns how many were accepted."""
    n = 0
    offers = [k for k in scan.default_offers.split(",") if k]
    for item in scan.items.filter(review_status=ScanItem.PENDING, confidence__gte=HIGH_CONFIDENCE):
        top = item.candidates.first()
        if top is None:
            continue
        try:
            accept(item, top.entry, scan.default_visibility, offers, scan.shelf_label)
        except CapReached:
            break
        n += 1
    return n


def _refresh_scan(scan):
    scan.books_accepted = scan.items.filter(review_status__in=[ScanItem.ACCEPTED, ScanItem.EDITED]).count()
    pending = scan.items.filter(review_status=ScanItem.PENDING).exists()
    scan.status = ShelfScan.REVIEW if pending else ShelfScan.DONE
    scan.save(update_fields=["books_accepted", "status"])


# ---- the home shelf ------------------------------------------------------------------

def spine_for(entry_id, title):
    digest = hashlib.sha1(f"{entry_id}:{title}".encode("utf-8")).digest()
    color, ink = SPINE_PALETTE[digest[0] % len(SPINE_PALETTE)]
    w = 24 + digest[1] % 18
    h = 150 + digest[2] % 50
    lean = 0
    if digest[3] % 11 == 0:
        lean = 8 + digest[4] % 5
    elif digest[3] % 5 == 0:
        lean = [-1, -0.6, 0.5, 0.8][digest[4] % 4]
    return {"color": color, "ink": ink, "w": w, "h": h, "lean": lean}


def shelf_books(profile, limit=400):
    """The person's held copies as the shelf component's JSON rows."""
    rows = []
    copies = (Copy.objects.filter(owner=profile, status__in=Copy.HELD)
              .select_related("entry").prefetch_related("entry__creators", "offers").order_by("position", "created_at")[:limit])
    for c in copies:
        kinds = [o.kind for o in c.offers.all() if o.is_active]
        status = kinds[0] if kinds else ("public" if c.visibility == Copy.PUBLIC else "private")
        row = {"id": c.pk, "title": c.entry.title, "author": c.entry.creator_names, "status": status,
               "rare": c.is_rare_candidate, "url": f"/books/copy/{c.pk}/"}
        row.update(spine_for(c.entry_id, c.entry.title))
        rows.append(row)
    return rows


def reorder(profile, copy_ids):
    """The living shelf's drag: positions follow the given order."""
    mine = {c.pk: c for c in Copy.objects.filter(owner=profile, pk__in=copy_ids)}
    for pos, pk in enumerate(copy_ids, start=1):
        c = mine.get(pk)
        if c and c.position != pos:
            c.position = pos
            c.save(update_fields=["position"])
    return len(mine)
