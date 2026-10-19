"""Where book data comes from (spec BK2, 12.14).

Several sources, each an adapter returning the same `Record`, every result
**copied into our own CatalogEntry** by books/catalog.py and never read live
again. One source going away (Lendle died when Amazon cut its API) costs us
new look-ups, not our catalogue.

Open Library needs no key but wants a contact in the User-Agent. Google Books
takes an optional key. The National Library of Israel needs a key
(BOOKS_NLI_API_KEY) and is skipped without one. Results are cached for a day
so a confirmation screen that asks twice costs one call.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

from . import googlebooks, nli, openlibrary
from .base import Record, SourceError  # noqa: F401

log = logging.getLogger(__name__)
CACHE_SECONDS = 24 * 3600


PAUSE_SECONDS = 600


def _paused(source):
    return bool(cache.get(f"books:source-paused:{source.NAME}"))


def pause(source):
    """A source that says 429 (over quota) is left alone for ten minutes,
    instead of being asked again for every book on the shelf."""
    cache.set(f"books:source-paused:{source.NAME}", True, PAUSE_SECONDS)


def enabled():
    out = [openlibrary, googlebooks]
    if getattr(settings, "BOOKS_NLI_API_KEY", ""):
        out.append(nli)
    return [s for s in out if not _paused(s)]


def lookup(query=None, isbn=None, limit=8):
    """Records from every enabled source, best first, identifier look-ups
    before title look-ups. Never raises: a source that fails is logged and
    skipped, so one outage does not break the confirmation screen."""
    raw = f"{isbn or ''}:{(query or '').strip().lower()}"
    key = "books:lookup:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    records = []
    for source in enabled():
        try:
            if isbn:
                records.extend(source.by_isbn(isbn))
            if query:
                records.extend(source.search(query, limit=limit))
        except SourceError as exc:
            log.warning("books source %s failed: %s", source.NAME, exc)
            if "429" in str(exc):
                pause(source)
        except Exception:  # noqa: BLE001
            log.exception("books source %s crashed", source.NAME)
    # Every source's record is kept: the same book from two sources lands on
    # one entry in catalog.upsert_from_record, and the second fills the
    # first's blanks (a description, a publisher). Deduping here would lose that.
    cache.set(key, records, CACHE_SECONDS)
    return records
