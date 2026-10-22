"""The shared catalogue: finding, matching, copying in, merging (spec BK2).

Matching order, per spec 12.7: an identifier first (ISBN-13 or danacode),
then title plus creator plus publisher, because many Hebrew books have no
ISBN. Nothing is merged silently: `upsert_from_record` reuses an existing
entry only on an identifier match or an exact normalised title-and-creator
match; near matches are left for a curator (`duplicate_suspects`).
"""

import io
import logging

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import jobs
from .models import (BookDetail, CatalogEntry, CollectionType, Creator, CreatorAlias, EntryCorrection, EntryCreator,
                     EntryIdentifier, Tag)
from .sources import lookup
from .sources.base import Record
from .textnorm import identifier_scheme, normalize, normalize_danacode, normalize_isbn, similarity, tokens

log = logging.getLogger(__name__)


def book_type():
    return CollectionType.objects.get_or_create(key="book", defaults={"name_he": "ספרים", "name_en": "Books"})[0]


def live():
    """Entries a person should see: not merged away."""
    return CatalogEntry.objects.filter(merged_into__isnull=True)


# ---- creators -----------------------------------------------------------------

def creator_for(name, source=""):
    """One Creator per person: by normalised name, then by alias, else new."""
    name = (name or "").strip()
    if not name:
        return None
    key = normalize(name)[:200]
    found = Creator.objects.filter(search_name=key).first()
    if found is None:
        alias = CreatorAlias.objects.filter(search_name=key).select_related("creator").first()
        found = alias.creator if alias else None
    if found is None:
        found = Creator.objects.create(name=name, source=source)
    return found


def set_creators(entry, names, role="author"):
    EntryCreator.objects.filter(entry=entry, role=role).delete()
    for i, name in enumerate(names):
        c = creator_for(name, source=entry.source)
        if c is not None:
            EntryCreator.objects.get_or_create(entry=entry, creator=c, role=role, defaults={"order": i})
    entry.refresh_search_text()


# ---- identifiers ---------------------------------------------------------------

def find_by_identifier(scheme, value):
    ident = EntryIdentifier.objects.filter(scheme=scheme, value=value).select_related("entry").first()
    if ident is None:
        return None
    entry = ident.entry
    return entry.merged_into or entry


def may_edit(user, profile, entry):
    """Who may fix a catalogue record directly (Avi, 2026-10-22: "I found a
    wrong title and could not change it"): staff; whoever added it by hand
    while it is unverified; and anyone who holds a copy of the book. Every
    direct edit is logged as an accepted correction, so curators see it."""
    from .models import Copy

    if user.is_staff:
        return True
    if profile is None:
        return False
    if entry.created_by_id == profile.pk and not entry.is_verified:
        return True
    return Copy.objects.filter(owner=profile, entry=entry).exists()


def add_identifier(entry, scheme, value):
    if not value:
        return
    EntryIdentifier.objects.get_or_create(scheme=scheme, value=value, defaults={"entry": entry})


# ---- copying a source record in ------------------------------------------------

def find_existing(record):
    for isbn in record.isbns:
        hit = find_by_identifier("isbn13", isbn)
        if hit:
            return hit
    if record.danacode:
        hit = find_by_identifier("danacode", record.danacode)
        if hit:
            return hit
    if record.source_ref:
        hit = find_by_identifier(record.source, record.source_ref)
        if hit:
            return hit
    # Exact normalised title and first creator: the same book, no identifier.
    first = normalize(record.creators[0]) if record.creators else ""
    for entry in live().filter(search_text__startswith=normalize(record.title)[:80])[:20]:
        if normalize(entry.title) == normalize(record.title):
            names = [c.search_name for c in entry.creators.all()]
            if not first or first in names:
                return entry
    return None


@transaction.atomic
def upsert_from_record(record: Record, created_by=None):
    """Returns (entry, created). Fills only blanks on an existing entry."""
    entry = find_existing(record)
    created = entry is None
    if created:
        entry = CatalogEntry.objects.create(
            collection_type=book_type(), title=record.title[:300], subtitle=(record.subtitle or "")[:300],
            language=record.language or "", year=record.year, description=record.description or "",
            cover_source_url=record.cover_url or "", source=record.source, source_ref=record.source_ref[:120],
            created_by=created_by,
        )
        set_creators(entry, record.creators)
    else:
        changed = []
        for field, value in (("subtitle", record.subtitle), ("language", record.language), ("year", record.year),
                             ("description", record.description), ("cover_source_url", record.cover_url)):
            if value and not getattr(entry, field):
                setattr(entry, field, value if field != "description" else value[:5000])
                changed.append(field)
        if changed:
            entry.save(update_fields=changed + ["updated_at"])
        if not entry.creators.exists() and record.creators:
            set_creators(entry, record.creators)
    detail, _ = BookDetail.objects.get_or_create(entry=entry)
    detail_changed = []
    for field, value in (("publisher", record.publisher), ("pages", record.pages)):
        if value and not getattr(detail, field):
            setattr(detail, field, value if field != "publisher" else value[:200])
            detail_changed.append(field)
    if detail_changed:
        detail.save(update_fields=detail_changed)
    for isbn in record.isbns:
        add_identifier(entry, "isbn13", isbn)
    if record.danacode:
        add_identifier(entry, "danacode", normalize_danacode(record.danacode))
    if record.source_ref:
        add_identifier(entry, record.source, record.source_ref[:64])
    if entry.cover_source_url and not entry.cover:
        jobs.enqueue("catalog.fetch_cover", ref_id=entry.pk)
    return entry, created


def import_lookup(query=None, isbn=None, created_by=None, limit=8):
    """Ask the sources and copy every result in. Returns the entries."""
    entries = []
    for record in lookup(query=query, isbn=isbn, limit=limit):
        try:
            entry, _ = upsert_from_record(record, created_by=created_by)
        except Exception:  # noqa: BLE001
            log.exception("books: could not import %s %s", record.source, record.source_ref)
            continue
        if entry not in entries:
            entries.append(entry)
    return entries


# ---- the cover job ---------------------------------------------------------------

@jobs.job("catalog.fetch_cover")
def fetch_cover(job):
    entry = CatalogEntry.objects.filter(pk=job.ref_id).first()
    if entry is None or entry.cover or not entry.cover_source_url:
        return
    response = requests.get(entry.cover_source_url, timeout=12, headers={"User-Agent": "babook-books/1.0"})
    if response.status_code != 200 or len(response.content) < 2000:
        return  # Open Library answers a 1x1 gif for a missing cover
    from .images import prepare

    prepared = prepare(io.BytesIO(response.content), max_side=800)
    entry.cover.save(f"{entry.pk}.jpg", ContentFile(prepared.data), save=True)


# ---- search ------------------------------------------------------------------------

def search_local(query, limit=20):
    """Title, subtitle and creators, tolerant of spelling and vowel marks:
    every token must appear in the normalised text; results ranked by
    similarity to the whole query. An identifier typed in goes straight to
    the record."""
    query = (query or "").strip()
    if not query:
        return []
    ident = identifier_scheme(query)
    if ident:
        hit = find_by_identifier(*ident)
        return [hit] if hit else []
    toks = tokens(query)
    if not toks:
        return []
    qs = live()
    for tok in toks[:6]:
        qs = qs.filter(search_text__contains=tok)
    candidates = list(qs.prefetch_related("creators")[:200])
    if len(candidates) < 5 and len(toks) == 1 and len(toks[0]) >= 4:
        # One misspelt word: fall back to a prefix of it.
        extra = live().filter(search_text__contains=toks[0][:4]).exclude(pk__in=[c.pk for c in candidates])
        candidates += list(extra.prefetch_related("creators")[:100])
    ranked = sorted(candidates, key=lambda e: -similarity(query, f"{e.title} {e.creator_names}"))
    return ranked[:limit]


# ---- curation ----------------------------------------------------------------------

def verify(entry, by=None):
    entry.is_verified = True
    entry.save(update_fields=["is_verified", "updated_at"])
    return entry


@transaction.atomic
def merge(loser, winner):
    """Everything on `loser` moves to `winner`; `loser` points at `winner`
    so old links still resolve. Never silent: called by a curator."""
    if loser.pk == winner.pk:
        return winner
    EntryIdentifier.objects.filter(entry=loser).update(entry=winner)
    for ec in EntryCreator.objects.filter(entry=loser):
        EntryCreator.objects.get_or_create(entry=winner, creator=ec.creator, role=ec.role, defaults={"order": ec.order})
    winner.tags.add(*loser.tags.all())
    CatalogEntry.objects.filter(parent=loser).update(parent=winner)
    CatalogEntry.objects.filter(merged_into=loser).update(merged_into=winner)
    EntryCorrection.objects.filter(entry=loser).update(entry=winner)
    if not winner.cover and loser.cover:
        winner.cover = loser.cover
    for field in ("subtitle", "language", "year", "description", "cover_source_url"):
        if not getattr(winner, field) and getattr(loser, field):
            setattr(winner, field, getattr(loser, field))
    winner.save()
    winner.refresh_search_text()
    loser.merged_into = winner
    loser.save(update_fields=["merged_into", "updated_at"])
    return winner


def duplicate_suspects(limit=50):
    """Pairs of live entries with the same normalised title and a shared
    creator, for a curator to look at. Not merged by anyone but a person."""
    seen, pairs = {}, []
    for entry in live().prefetch_related("creators").order_by("title")[:2000]:
        key = normalize(entry.title)
        names = {c.search_name for c in entry.creators.all()}
        for other in seen.get(key, []):
            other_names = {c.search_name for c in other.creators.all()}
            if not names or not other_names or names & other_names:
                pairs.append((other, entry))
        seen.setdefault(key, []).append(entry)
        if len(pairs) >= limit:
            break
    return pairs


def accept_correction(correction, by):
    entry = correction.entry
    field, value = correction.field, correction.value.strip()
    if field in ("title", "subtitle", "language") and value:
        setattr(entry, field, value[:300])
        entry.save(update_fields=[field, "updated_at"])
        entry.refresh_search_text()
    elif field == "year" and value.isdigit():
        entry.year = int(value)
        entry.save(update_fields=["year", "updated_at"])
    elif field == "publisher" and value:
        detail, _ = BookDetail.objects.get_or_create(entry=entry)
        detail.publisher = value[:200]
        detail.save(update_fields=["publisher"])
    elif field == "creators" and value:
        set_creators(entry, [n.strip() for n in value.split(",") if n.strip()])
    correction.status = EntryCorrection.ACCEPTED
    correction.handled_by = by
    correction.handled_at = timezone.now()
    correction.save(update_fields=["status", "handled_by", "handled_at"])
    return correction


def decline_correction(correction, by):
    correction.status = EntryCorrection.DECLINED
    correction.handled_by = by
    correction.handled_at = timezone.now()
    correction.save(update_fields=["status", "handled_by", "handled_at"])
    return correction


def tags_for(lang):
    return [(t, t.tr(lang)) for t in Tag.objects.select_related("parent").order_by("kind", "name_en")]
