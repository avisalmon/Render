"""The National Library of Israel's open API. Needs a key
(BOOKS_NLI_API_KEY; the adapter is skipped without one). The best source for
Hebrew books and for danacodes, which the others do not know. The response
is Dublin Core-ish and arrives with some variation, so every field is read
defensively; a record with no title is dropped."""

import re

from django.conf import settings

from .base import Record, clean_isbns, get_json, year_of

NAME = "nli"
BASE = "https://api.nli.org.il/openlibrary/search"
INTERVAL = 0.3


def _first(value):
    if isinstance(value, list):
        for v in value:
            if isinstance(v, dict) and "@value" in v:
                return str(v["@value"])
            if v:
                return str(v)
        return ""
    if isinstance(value, dict):
        return str(value.get("@value", ""))
    return str(value or "")


def _all(value):
    if isinstance(value, list):
        return [_first([v]) for v in value if _first([v])]
    v = _first(value)
    return [v] if v else []


def _record(item):
    get = lambda k: item.get(f"http://purl.org/dc/elements/1.1/{k}") or item.get(k)  # noqa: E731
    title = _first(get("title"))
    if not title:
        return None
    identifiers = _all(get("identifier"))
    isbns = clean_isbns([i for i in identifiers if "isbn" in i.lower() or i.replace("-", "").isdigit()])
    danacode = ""
    for ident in identifiers:
        if "dana" in ident.lower():
            m = re.search(r"(\d[\d-]*\d)\s*$", ident)
            danacode = m.group(1) if m else ""
            break
    ref = _first(item.get("@id")) or _first(get("recordid"))
    thumb = _first(item.get("http://purl.org/dc/elements/1.1/thumbnail") or item.get("thumbnail"))
    lang = _first(get("language"))
    return Record(
        source=NAME, source_ref=ref, title=title, creators=_all(get("creator"))[:4],
        language={"heb": "he", "eng": "en", "ara": "ar", "rus": "ru"}.get(lang, lang[:2]),
        year=year_of(_first(get("date"))), publisher=_first(get("publisher")), isbns=isbns, danacode=danacode,
        cover_url=thumb, description=_first(get("description"))[:2000],
    )


def _query(q, limit):
    data = get_json(NAME, BASE, {
        "api_key": settings.BOOKS_NLI_API_KEY, "query": q, "output_format": "json",
        "material_type": "books", "result_page": 1, "count": limit,
    }, INTERVAL)
    items = data if isinstance(data, list) else (data or {}).get("items", [])
    return [r for r in (_record(i) for i in items) if r]


def search(query, limit=8):
    return _query(f"any,contains,{query}", limit)


def by_isbn(isbn):
    return _query(f"isbn,contains,{isbn}", 3)
