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
from .models import (
    BookDetail,
    Copy,
    ModelCall,
    Offer,
    Profile,
    ScanCandidate,
    ScanItem,
    ShelfScan,
)
from .recognition import KeyProblem, read_shelf, read_single
from .textnorm import similarity

log = logging.getLogger(__name__)

FREE_CAP = 1000
SCAN_MAX_SIDE = 4000
HIGH_CONFIDENCE = Decimal("0.85")
CANDIDATES = 3
VISIBILITY_CHOICES = ("hidden", "private", "public")
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
    from .tiers import allows

    if allows(profile, "unlimited_library"):
        return None
    return max(FREE_CAP - held_count(profile), 0)


# ---- starting a scan -------------------------------------------------------------

def start_scan(profile, uploaded, shelf_label="", default_visibility="private", default_offers=(), single=False):
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
                     default_offers=",".join(offers), is_single=bool(single))
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
        # A single book is one cover or spine, read whole (never in strips), with where it sits.
        reading = read_single(data) if scan.is_single else read_shelf(data)
    except KeyProblem as exc:
        scan.status, scan.error = ShelfScan.FAILED, "key"
        scan.save(update_fields=["status", "error"])
        _notify_scan(scan, "scan.failed")
        log.error("books scan %s: the OpenAI key needs replacing: %s", scan.pk, exc)
        return
    except Exception as exc:  # noqa: BLE001
        scan.status, scan.error = ShelfScan.FAILED, str(exc)[:300]
        scan.save(update_fields=["status", "error"])
        _notify_scan(scan, "scan.failed")
        raise
    for call in reading.calls:
        ModelCall.objects.create(profile=scan.owner, job=job, provider="openai", model=reading.model,
                                 purpose="shelf_read", input_tokens=call["input_tokens"],
                                 output_tokens=call["output_tokens"], cost_usd=call["cost_usd"],
                                 duration_ms=int(call["seconds"] * 1000))
    with transaction.atomic():
        scan.items.all().delete()
        cut = []
        for i, book in enumerate(reading.books):
            item = ScanItem.objects.create(scan=scan, position=i, raw_title=book.title[:300], raw_author=book.author[:200])
            if getattr(book, "corners", None):
                cut.append((item, book.corners))
        scan.model_name = reading.model
        scan.cost_usd = reading.cost_usd
        scan.seconds = Decimal(str(reading.seconds))
        scan.books_found = len(reading.books)
        scan.cover_box = ",".join(str(v) for v in reading.box) if getattr(reading, "box", None) else ""
        scan.save(update_fields=["model_name", "cost_usd", "seconds", "books_found", "cover_box"])
    try:
        cut_spines(scan, cut)
    except Exception:  # noqa: BLE001
        log.exception("books scan %s: cutting spines", scan.pk)
    for item in scan.items.all():
        try:
            find_candidates(item, created_by=scan.owner)
        except Exception:  # noqa: BLE001
            log.exception("books scan %s: candidates for item %s", scan.pk, item.pk)
    try:
        web_candidates(scan, job=job)
    except KeyProblem:
        log.error("books scan %s: web lookup stopped, the OpenAI key needs replacing", scan.pk)
    except Exception:  # noqa: BLE001
        log.exception("books scan %s: web lookup", scan.pk)
    scan.status = ShelfScan.REVIEW if scan.books_found else ShelfScan.DONE
    scan.finished_at = timezone.now()
    scan.save(update_fields=["status", "finished_at"])
    _notify_scan(scan, "scan.ready" if scan.books_found else "scan.empty")


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


WEB_CEILING = Decimal("0.84")  # a web find is never "sure": the person confirms it


def web_candidates(scan, job=None):
    """The books the free sources did not match well go to the web together
    (books/weblookup.py: cached per book site-wide, capped per day). A find
    joins the item's candidates, just below "sure"."""
    from . import weblookup
    from .tiers import allows

    weak = [i for i in scan.items.filter(review_status=ScanItem.PENDING) if i.confidence < HIGH_CONFIDENCE]
    if not weak or not weblookup.enabled() or not allows(scan.owner, "web_lookup"):
        return 0
    found = weblookup.lookup_many([(i.raw_title, i.raw_author) for i in weak], profile=scan.owner, job=job)
    added = 0
    for item in weak:
        row = found.get((item.raw_title, item.raw_author))
        if row is None or not row.found or row.entry_id is None:
            continue
        entry = row.entry.merged_into or row.entry
        sure = Decimal(str(max(0.0, min(1.0, float((row.result or {}).get("confidence") or 0)))))
        conf = min(WEB_CEILING, max(Decimal(str(round(_score(item, entry), 3))), (sure * Decimal("0.85")).quantize(
            Decimal("0.001"))))
        existing = ScanCandidate.objects.filter(item=item, entry=entry).first()
        if existing:
            existing.confidence = max(existing.confidence, conf)
            existing.save(update_fields=["confidence"])
        else:
            ScanCandidate.objects.create(item=item, entry=entry, rank=99, confidence=conf)
        ranked = sorted(item.candidates.all(), key=lambda c: -c.confidence)[:CANDIDATES]
        item.candidates.exclude(pk__in=[c.pk for c in ranked]).delete()
        for rank, c in enumerate(ranked):
            if c.rank != rank:
                c.rank = rank
                c.save(update_fields=["rank"])
        item.confidence = ranked[0].confidence
        item.save(update_fields=["confidence"])
        added += 1
    return added


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
    first_time = item.review_status == ScanItem.PENDING
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
    # The first place typed in a batch becomes the batch's default for the
    # books still waiting (Avi, 2026-10-19): one shelf, one place.
    if copy.location_note and copy.location_note != item.scan.shelf_label:
        set_label(item.scan, copy.location_note)
    copy.offers.exclude(kind__in=offer_kinds).delete()
    for kind in offer_kinds:
        Offer.objects.get_or_create(copy=copy, kind=kind,
                                    defaults={"loan_days": DEFAULT_LOAN_DAYS if kind == Offer.LEND else None})
    item.copy = copy
    item.review_status = ScanItem.EDITED if edited else ScanItem.ACCEPTED
    item.save(update_fields=["copy", "review_status"])
    if first_time and item.scan.is_single and item.scan.cover_box:
        try:
            use_photo_as_cover(item.scan, copy)
        except Exception:  # noqa: BLE001
            log.exception("books scan %s: the cover crop", item.scan.pk)
    _refresh_scan(item.scan)
    if first_time:
        from . import play, tagging

        play.book_confirmed(profile, entry)
        tagging.ensure_tagged(entry, profile)
        from . import enrich

        enrich.start(entry, profile)
    return copy


# ---- real spines on my shelf (Avi, 2026-10-22) ----------------------------------------
#
# The call that reads a shelf also gives each spine's four corners; the spine
# is cut out and straightened here (Pillow, nothing spent) and my shelf shows
# it instead of the drawn one. Old scans are read again once, in the
# background, the first time their owner opens the shelf.

SPINE_MAX_HEIGHT = 640
SPINES_PER_SWEEP = 25
SPINE_SWEEP_EVERY = 600  # seconds


def cut_spines(scan, pairs):
    """pairs: [(ScanItem, corners as photo fractions)]. Marks the scan done."""
    from io import BytesIO

    from PIL import Image

    if pairs:
        with scan.photo.open("rb") as fh:
            img = Image.open(BytesIO(fh.read()))
            img.load()
        img = img.convert("RGB")
        w, h = img.size
        for item, (tl, tr, ty, bl, br, by) in pairs:
            width = int(((tr - tl) + (br - bl)) / 2 * w)
            height = int((by - ty) * h)
            if width < 4 or height < 20:
                continue
            # QUAD: the source's upper-left, lower-left, lower-right, upper-right corners.
            spine = img.transform((width, height), Image.QUAD,
                                  (tl * w, ty * h, bl * w, by * h, br * w, by * h, tr * w, ty * h), Image.BICUBIC)
            spine.thumbnail((SPINE_MAX_HEIGHT, SPINE_MAX_HEIGHT))
            buf = BytesIO()
            spine.save(buf, format="JPEG", quality=84, optimize=True)
            if item.spine:
                item.spine.delete(save=False)
            item.spine.save(f"{scan.pk}-{item.pk}.jpg", ContentFile(buf.getvalue()), save=False)
            item.spine_height = height
            item.spine_w, item.spine_h = spine.size
            item.save(update_fields=["spine", "spine_height", "spine_w", "spine_h"])
    scan.spines_done = True
    scan.save(update_fields=["spines_done"])


def spines_for_old_scan(scan, job=None):
    """Read an old shelf photo again for its spines, and give each confirmed
    book the spine that matches its title. Its books stay as they are."""
    from .recognition import similarity

    if scan.is_single:
        scan.spines_done = True
        scan.save(update_fields=["spines_done"])
        return 0
    with scan.photo.open("rb") as fh:
        data = fh.read()
    reading = read_shelf(data)
    for call in reading.calls:
        ModelCall.objects.create(profile=scan.owner, job=job, provider="openai", model=reading.model,
                                 purpose="spine_backfill", input_tokens=call["input_tokens"],
                                 output_tokens=call["output_tokens"], cost_usd=call["cost_usd"],
                                 duration_ms=int(call["seconds"] * 1000))
    found = [b for b in reading.books if b.corners]
    used, pairs = set(), []
    for item in scan.items.order_by("position"):
        best, score = None, 0.0
        for i, book in enumerate(found):
            if i in used:
                continue
            s = similarity(item.raw_title, book.title)
            if s > score:
                best, score = i, s
        if best is not None and score >= 0.6:
            used.add(best)
            pairs.append((item, found[best].corners))
    cut_spines(scan, pairs)
    return len(pairs)


@jobs.job("scan.spines_batch")
def spines_batch_job(job):
    profile = Profile.objects.filter(pk=job.profile_id).first() if job.profile_id else None
    scans = ShelfScan.objects.filter(spines_done=False, status__in=(ShelfScan.REVIEW, ShelfScan.DONE))
    if profile is not None:
        scans = scans.filter(owner=profile)
    for scan in scans.order_by("created_at")[:SPINES_PER_SWEEP]:
        try:
            spines_for_old_scan(scan, job=job)
        except KeyProblem:
            log.error("books spines: the OpenAI key needs replacing")
            return
        except Exception:  # noqa: BLE001
            log.exception("books spines: scan %s", scan.pk)
            scan.spines_done = True  # one try per scan: never a loop of paid calls
            scan.save(update_fields=["spines_done"])


def sweep_spines(profile):
    """From my own shelf page, at most every ten minutes: old scans get their spines."""
    from django.conf import settings
    from django.core.cache import cache

    if not getattr(settings, "BOOKS_SPINE_SWEEP", True) or not getattr(settings, "OPENAI_API_KEY", ""):
        return False
    try:
        waiting = ShelfScan.objects.filter(owner=profile, spines_done=False, is_single=False,
                                           status__in=(ShelfScan.REVIEW, ShelfScan.DONE))
        if waiting.exists() and cache.add(f"books:spines:{profile.pk}", True, SPINE_SWEEP_EVERY):
            jobs.enqueue("scan.spines_batch", profile=profile)
            return True
    except Exception:  # noqa: BLE001
        log.exception("books: spine sweep")
    return False


def spines_waiting(profile):
    """Old shelf photos still to be cut into spines: (waiting, all)."""
    scans = ShelfScan.objects.filter(owner=profile, is_single=False, status__in=(ShelfScan.REVIEW, ShelfScan.DONE))
    return scans.filter(spines_done=False).count(), scans.count()


def spine_rows(copies):
    """For my shelf: each copy's real spine (url, width over height, height
    against the other books in its photo), where it has one."""
    items = (ScanItem.objects.filter(copy__in=copies).exclude(spine="")
             .only("pk", "copy_id", "scan_id", "spine", "spine_height", "spine_w", "spine_h"))
    by_scan, out = {}, {}
    for it in items:
        by_scan.setdefault(it.scan_id, []).append(it)
    for scan_items in by_scan.values():
        heights = sorted(i.spine_height for i in scan_items if i.spine_height)
        median = heights[len(heights) // 2] if heights else 0
        for it in scan_items:
            w, h = it.spine_w, it.spine_h
            if not (w and h):
                # Cut before its size was kept: measured once, then never again.
                try:
                    w, h = it.spine.width, it.spine.height
                    ScanItem.objects.filter(pk=it.pk).update(spine_w=w, spine_h=h)
                except Exception:  # noqa: BLE001
                    continue
            if not h:
                continue
            rel = (it.spine_height / median) if median and it.spine_height else 1.0
            out[it.copy_id] = {"url": f"/books/copy/{it.copy_id}/spine.jpg?v={it.pk}", "ratio": w / h,
                               "rel": max(0.75, min(1.25, rel))}
    return out


COVER_MARGIN = 0.02
COVER_MAX_SIDE = 1400


def crop_cover(scan):
    """The book cut out of a single-book photo, as JPEG bytes, or None."""
    try:
        x0, y0, x1, y1 = (float(v) for v in scan.cover_box.split(","))
    except ValueError:
        return None
    from io import BytesIO

    from PIL import Image

    with scan.photo.open("rb") as fh:
        img = Image.open(BytesIO(fh.read()))
        img.load()
    w, h = img.size
    box = (max(0, int((x0 - COVER_MARGIN) * w)), max(0, int((y0 - COVER_MARGIN) * h)),
           min(w, int((x1 + COVER_MARGIN) * w)), min(h, int((y1 + COVER_MARGIN) * h)))
    if box[2] - box[0] < 80 or box[3] - box[1] < 80:
        return None
    out = img.crop(box).convert("RGB")
    out.thumbnail((COVER_MAX_SIDE, COVER_MAX_SIDE))
    buf = BytesIO()
    out.save(buf, format="JPEG", quality=86, optimize=True)
    return buf.getvalue()


def use_photo_as_cover(scan, copy):
    """Avi, 2026-10-21: a photo of the book itself is its picture. Always my
    copy's cover photo; the catalogue's cover too, when it has none."""
    from .models import CopyPhoto

    data = crop_cover(scan)
    if not data:
        return None
    name = f"{copy.pk}-cover-{timezone.now():%Y%m%d%H%M%S}.jpg"
    if not copy.photos.filter(kind="cover").exists():
        photo = CopyPhoto(copy=copy, kind="cover")
        photo.image.save(name, ContentFile(data), save=True)
    entry = copy.entry
    if not entry.cover:
        entry.cover.save(f"{entry.pk}-from-photo.jpg", ContentFile(data), save=False)
        entry.save(update_fields=["cover"])
    return data


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


PAGE_MM = 0.08      # one leaf of ordinary book paper is about 0.08mm per page
COVERS_MM = 3.0
BOOK_HEIGHT_MM = 215


def drawn_width(pages, h):
    """A drawn spine as thick as its page count makes it, at least wide
    enough for its title (Avi, 2026-10-22: keep the book's proportions)."""
    ratio = (pages * PAGE_MM + COVERS_MM) / BOOK_HEIGHT_MM
    return int(max(24, min(70, round(h * ratio))))


def shelf_books(profile, limit=400, photos=False, viewer=None):
    """The person's held copies as the shelf component's JSON rows. With
    `photos`, each book with a real spine shows it. With a `viewer` who is
    not the owner (a friend), only what they may see, linking to the books'
    catalogue pages instead of the owner's copies."""
    from .models import BookDetail, ReadingLog

    rows = []
    other = viewer is not None and viewer.pk != profile.pk
    if other:
        from . import friends

        base = friends.visible_copies(viewer, profile)
    else:
        base = Copy.objects.filter(owner=profile, status__in=Copy.HELD)
    copies = list(base.select_related("entry").prefetch_related("entry__creators", "offers")
                  .order_by("position", "created_at")[:limit])
    spines = spine_rows(copies) if photos else {}
    ids = [c.entry_id for c in copies]
    pages = dict(BookDetail.objects.filter(entry_id__in=ids, pages__isnull=False).values_list("entry_id", "pages"))
    pages.update(ReadingLog.objects.filter(profile=profile, entry_id__in=ids, pages__isnull=False)
                 .values_list("entry_id", "pages"))
    for c in copies:
        kinds = [o.kind for o in c.offers.all() if o.is_active]
        status = kinds[0] if kinds else ("public" if c.visibility == Copy.PUBLIC else "private")
        row = {"id": c.pk, "title": c.entry.title, "author": c.entry.creator_names, "status": status,
               "rare": c.is_rare_candidate,
               "url": f"/books/catalog/{c.entry_id}/" if other else f"/books/copy/{c.pk}/"}
        row.update(spine_for(c.entry_id, c.entry.title))
        if pages.get(c.entry_id):
            row["w"] = drawn_width(pages[c.entry_id], row["h"])
        real = spines.get(c.pk)
        if real:
            # The real book: its own proportions, its height against its neighbours in the photo.
            # A thin one stays thin; its tap area is widened around it instead (books.css).
            row["h"] = int(max(130, min(215, 172 * real["rel"])))
            row["w"] = int(max(8, min(90, round(row["h"] * real["ratio"]))))
            row["photo"] = real["url"]
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


# ---- the batch's place, and the queue of shelves (Avi, 2026-10-19) -------------------

STUCK_AFTER_MINUTES = 5
MAX_READ_ATTEMPTS = 3


def set_label(scan, label):
    """The place for this batch: the default for every book still waiting,
    and filled in on books of this batch already shelved without one."""
    label = (label or "").strip()[:120]
    scan.shelf_label = label
    scan.save(update_fields=["shelf_label"])
    if label:
        Copy.objects.filter(scan_items__scan=scan, location_note="").update(location_note=label)
    return scan


def _notify_scan(scan, kind):
    from .models import Notification

    Notification.objects.create(profile=scan.owner, kind=kind, scan=scan)


def _read_jobs(scan):
    from .models import Job

    return Job.objects.filter(kind="scan.read", ref_id=scan.pk).order_by("-created_at")


def heal(scan, now=None):
    """A scan whose reading thread died (a deploy, a restart) is read again,
    up to three tries; after that it is marked failed so it never just sits.
    Returns True when it restarted the reading."""
    from .models import Job

    if scan.status not in (ShelfScan.UPLOADED, ShelfScan.READING):
        return False
    now = now or timezone.now()
    cutoff = now - timezone.timedelta(minutes=STUCK_AFTER_MINUTES)
    last = _read_jobs(scan).first()
    started = (last.started_at or last.created_at) if last else scan.created_at
    if last is not None and last.status in (Job.QUEUED, Job.RUNNING) and started > cutoff:
        return False  # still within its time
    if last is None and scan.created_at > cutoff:
        return False
    if last is not None and last.status in (Job.QUEUED, Job.RUNNING):
        last.status, last.error = Job.FAILED, "abandoned: no progress, read again"
        last.finished_at = now
        last.save(update_fields=["status", "error", "finished_at"])
    if _read_jobs(scan).count() >= MAX_READ_ATTEMPTS:
        scan.status, scan.error = ShelfScan.FAILED, "stuck"
        scan.save(update_fields=["status", "error"])
        _notify_scan(scan, "scan.failed")
        return False
    scan.status = ShelfScan.UPLOADED
    scan.save(update_fields=["status"])
    jobs.enqueue("scan.read", ref_id=scan.pk, profile=scan.owner)
    return True


def heal_all(profile):
    return sum(1 for scan in ShelfScan.objects.filter(owner=profile, status__in=[ShelfScan.UPLOADED,
                                                                               ShelfScan.READING]) if heal(scan))


def retry(scan):
    """Read the same photo again after a failure (not after a key problem:
    that needs the site's key replaced first)."""
    if scan.status != ShelfScan.FAILED:
        return False
    if scan.error == "key":
        return False
    scan.status, scan.error = ShelfScan.UPLOADED, ""
    scan.save(update_fields=["status", "error"])
    jobs.enqueue("scan.read", ref_id=scan.pk, profile=scan.owner)
    return True


def remove(scan):
    """Forget a scan and its photo. Books already shelved from it stay."""
    try:
        scan.photo.delete(save=False)
    except Exception:  # noqa: BLE001
        log.exception("books scan %s: photo delete", scan.pk)
    scan.delete()


def queue(profile):
    """The person's open shelves: reading, waiting for them, or failed."""
    rows = []
    for scan in ShelfScan.objects.filter(owner=profile, status__in=[ShelfScan.UPLOADED, ShelfScan.READING,
                                                                    ShelfScan.REVIEW, ShelfScan.FAILED]):
        pending = scan.items.filter(review_status=ScanItem.PENDING).count() if scan.status == ShelfScan.REVIEW else 0
        rows.append({"scan": scan, "pending": pending})
    return rows


def queue_summary(profile):
    rows = queue(profile)
    reading = sum(1 for r in rows if r["scan"].status in (ShelfScan.UPLOADED, ShelfScan.READING))
    waiting = [r for r in rows if r["scan"].status == ShelfScan.REVIEW and r["pending"]]
    failed = sum(1 for r in rows if r["scan"].status == ShelfScan.FAILED)
    return {"reading": reading, "books": sum(r["pending"] for r in waiting), "shelves": len(waiting),
            "failed": failed, "any": bool(reading or waiting or failed),
            "first": waiting[0]["scan"] if len(waiting) == 1 else None}
