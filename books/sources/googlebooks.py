"""Google Books volumes API. A key is optional at low volume. Its terms bar
charging users for an application built on it without permission (spec
12.11, ACT-BK.5): this adapter is one source of several on purpose."""

from django.conf import settings

from .base import Record, clean_isbns, get_json, year_of

NAME = "googlebooks"
BASE = "https://www.googleapis.com/books/v1/volumes"
INTERVAL = 0.2


def _params(q, limit):
    p = {"q": q, "maxResults": min(limit, 20), "printType": "books"}
    key = getattr(settings, "BOOKS_GOOGLE_BOOKS_KEY", "")
    if key:
        p["key"] = key
    return p


def _record(item):
    info = item.get("volumeInfo", {})
    if not info.get("title"):
        return None
    ids = [i.get("identifier") for i in info.get("industryIdentifiers", []) if i.get("type", "").startswith("ISBN")]
    links = info.get("imageLinks", {})
    cover = links.get("large") or links.get("medium") or links.get("thumbnail") or ""
    return Record(
        source=NAME, source_ref=item.get("id", ""), title=info["title"], subtitle=info.get("subtitle", "") or "",
        creators=list(info.get("authors") or [])[:4], language=(info.get("language") or "")[:2],
        year=year_of(info.get("publishedDate")), publisher=info.get("publisher", "") or "",
        pages=info.get("pageCount"), isbns=clean_isbns(ids), cover_url=cover.replace("http://", "https://").replace("&edge=curl", ""),
        description=info.get("description", "") or "",
    )


def search(query, limit=8):
    data = get_json(NAME, BASE, _params(query, limit), INTERVAL)
    return [r for r in (_record(i) for i in (data or {}).get("items", [])) if r]


def by_isbn(isbn):
    data = get_json(NAME, BASE, _params(f"isbn:{isbn}", 3), INTERVAL)
    return [r for r in (_record(i) for i in (data or {}).get("items", [])) if r]
