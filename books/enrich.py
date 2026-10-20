"""Filling in what a record is missing, once per record (Avi, 2026-10-20):
"scan books that were not enriched, use the APIs or your ways to fill in
information, and mark the book done so it is never enriched twice."

The order is the cost order:
1. the free sources (Google Books with its key, Open Library, the National
   Library when its key is set), by ISBN when the record has one, else by
   title and author;
2. the web (books/weblookup.py), only when the ISBN or the cover is still
   missing, cached per book site-wide and inside the day's cap.

A source's answer is used only when it is the same book: the title close
and, when both sides name an author, the author close too. Only blanks are
filled; nothing a person or a curator wrote is overwritten. Every pass ends
in an EntryEnrichment row (done / partial / not found), and a record with a
row is never enriched again.

It runs by itself: when a record first reaches a library (the
`entry.enrich` job), and a few at a time from ordinary page views for the
records already there (`sweep_lazily`, no scheduler needed). The
`books_enrich` command does a batch on request.
"""

import logging
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from . import jobs
from .models import BookDetail, CatalogEntry, Copy, EntryEnrichment, Job
from .textnorm import normalize_isbn, similarity, valid_isbn13

log = logging.getLogger(__name__)

TITLE_MATCH = 0.82
AUTHOR_MATCH = 0.7
WEB_TITLE_MATCH = 0.6     # a spine misread is common; the author anchors it
SWEEP_EVERY = 600         # seconds between lazy sweeps
SWEEP_BATCH = 8


def _isbn(entry):
    row = entry.identifiers.filter(scheme="isbn13").first()
    return row.value if row else ""


def missing(entry):
    """What is still blank on the record, by name."""
    detail = BookDetail.objects.filter(entry=entry).first()
    out = []
    if not _isbn(entry):
        out.append("isbn")
    if not entry.cover and not entry.cover_source_url:
        out.append("cover")
    if not entry.year:
        out.append("year")
    if not (detail and detail.publisher):
        out.append("publisher")
    if not entry.description:
        out.append("description")
    if not entry.language:
        out.append("language")
    return out


def same_book(entry, record, title_match=TITLE_MATCH):
    """Is this record the same book as this entry? Title close, and author
    close whenever both sides name one."""
    if similarity(entry.title, record.title) < title_match:
        return False
    names = [c.name for c in entry.creators.all()]
    if names and record.creators:
        best = max(similarity(a, b) for a in names for b in record.creators)
        if best < AUTHOR_MATCH:
            return False
    return True


def fill_blanks(entry, record):
    """Copy the record's values into the entry's blanks. Returns the names
    of the fields filled."""
    from . import catalog

    filled = []
    changed = []
    for field, value in (("subtitle", record.subtitle), ("language", record.language), ("year", record.year),
                         ("description", record.description), ("cover_source_url", record.cover_url)):
        if value and not getattr(entry, field):
            setattr(entry, field, value if field != "description" else value[:5000])
            changed.append(field)
            filled.append("cover" if field == "cover_source_url" else field)
    if changed:
        entry.save(update_fields=changed + ["updated_at"])
    if not entry.creators.exists() and record.creators:
        catalog.set_creators(entry, record.creators)
        filled.append("authors")
    detail, _ = BookDetail.objects.get_or_create(entry=entry)
    detail_changed = []
    for field, value in (("publisher", record.publisher), ("pages", record.pages)):
        if value and not getattr(detail, field):
            setattr(detail, field, value if field != "publisher" else value[:200])
            detail_changed.append(field)
            filled.append(field)
    if detail_changed:
        detail.save(update_fields=detail_changed)
    if not _isbn(entry):
        for isbn in record.isbns:
            isbn = normalize_isbn(isbn)
            if isbn and valid_isbn13(isbn):
                catalog.add_identifier(entry, "isbn13", isbn)
                filled.append("isbn")
                break
    if "cover" in filled and not entry.cover:
        jobs.enqueue("catalog.fetch_cover", ref_id=entry.pk)
    return filled


def enrich(entry, profile=None, job=None, use_web=True):
    """One pass. Always ends with the record marked, so it is never done twice."""
    # Through catalog.lookup, the one door to the sources (and the one the
    # tests close, so no test reaches the network).
    from . import catalog, weblookup

    existing = EntryEnrichment.objects.filter(entry=entry).first()
    if existing:
        return existing
    filled, used, cost, web = [], [], Decimal(0), False
    names = [c.name for c in entry.creators.all()]
    query = f"{entry.title} {names[0] if names else ''}".strip()
    isbn = _isbn(entry)
    try:
        records = catalog.lookup(isbn=isbn or None, query=None if isbn else query, limit=8)
    except Exception:  # noqa: BLE001
        log.exception("books enrich %s: free sources", entry.pk)
        records = []
    for record in records:
        if not missing(entry):
            break
        by_isbn = isbn and isbn in [normalize_isbn(i) for i in record.isbns]
        if by_isbn or same_book(entry, record):
            got = fill_blanks(entry, record)
            if got:
                filled += got
                used.append(record.source)
    still = missing(entry)
    if use_web and ("isbn" in still or "cover" in still) and weblookup.enabled():
        try:
            found = weblookup.lookup_many([(entry.title, names[0] if names else "")], profile=profile, job=job,
                                          save_entries=False)
        except Exception:  # noqa: BLE001
            log.exception("books enrich %s: web", entry.pk)
            found = {}
        row = found.get((entry.title, names[0] if names else ""))
        if row is not None:
            web = True
            cost += row.cost_usd
            record = weblookup.to_record(row.result or {})
            if record is not None and same_book(entry, record, title_match=WEB_TITLE_MATCH):
                got = fill_blanks(entry, record)
                if got:
                    filled += got
                    used.append("web")
    left = missing(entry)
    if not filled:
        status = EntryEnrichment.NOT_FOUND
    elif "isbn" in left or "cover" in left:
        status = EntryEnrichment.PARTIAL
    else:
        status = EntryEnrichment.DONE
    row, _ = EntryEnrichment.objects.get_or_create(entry=entry, defaults={
        "status": status, "filled": sorted(set(filled)), "sources": sorted(set(used)), "used_web": web,
        "cost_usd": cost, "note": ("still missing: " + ", ".join(left))[:300] if left else ""})
    return row


@jobs.job("entry.enrich")
def enrich_job(job):
    entry = CatalogEntry.objects.filter(pk=job.ref_id, merged_into__isnull=True).first()
    if entry is not None:
        enrich(entry, profile=job.profile, job=job)


def waiting(limit=None):
    """Records in someone's library, never enriched, oldest first."""
    qs = (CatalogEntry.objects.filter(merged_into__isnull=True, enrichment__isnull=True,
                                      pk__in=Copy.objects.values("entry_id"))
          .order_by("created_at"))
    return qs[:limit] if limit else qs


def start(entry, profile=None):
    """Enrich a record in the background, once. Never raises."""
    try:
        if entry is None or EntryEnrichment.objects.filter(entry=entry).exists():
            return False
        recent = timezone.now() - timezone.timedelta(hours=1)
        if Job.objects.filter(kind="entry.enrich", ref_id=entry.pk, created_at__gte=recent).exists():
            return False
        jobs.enqueue("entry.enrich", ref_id=entry.pk, profile=profile)
        return True
    except Exception:  # noqa: BLE001
        log.exception("books: could not start enriching entry %s", getattr(entry, "pk", None))
        return False


@jobs.job("entries.enrich_batch")
def batch_job(job):
    for entry in list(waiting(SWEEP_BATCH)):
        try:
            enrich(entry, job=job)
        except Exception:  # noqa: BLE001
            log.exception("books enrich batch: entry %s", entry.pk)


def sweep_lazily():
    """From ordinary page views, at most every ten minutes: a few waiting
    records in the background (lesson 30: no scheduler to forget)."""
    try:
        if not waiting().exists():
            return False
        if cache.add("books:enrich-sweep", True, SWEEP_EVERY):
            jobs.enqueue("entries.enrich_batch")
            return True
    except Exception:  # noqa: BLE001
        log.exception("books: enrich sweep")
    return False


def counts():
    from django.db.models import Count

    by = dict(EntryEnrichment.objects.values_list("status").annotate(n=Count("id")))
    return {"done": by.get(EntryEnrichment.DONE, 0), "partial": by.get(EntryEnrichment.PARTIAL, 0),
            "not_found": by.get(EntryEnrichment.NOT_FOUND, 0), "waiting": waiting().count()}
