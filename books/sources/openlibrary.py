"""Open Library: free, no key, 1 request a second (3 with a contact in the
User-Agent, which we send). https://openlibrary.org/developers/api"""

from .base import Record, clean_isbns, get_json, year_of

NAME = "openlibrary"
BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b"
INTERVAL = 0.4


def _cover(doc):
    if doc.get("cover_i"):
        return f"{COVERS}/id/{doc['cover_i']}-L.jpg"
    for isbn in doc.get("isbn", [])[:1]:
        return f"{COVERS}/isbn/{isbn}-L.jpg"
    return ""


def search(query, limit=8):
    data = get_json(NAME, f"{BASE}/search.json", {
        "q": query, "limit": limit,
        "fields": "key,title,subtitle,author_name,first_publish_year,isbn,language,publisher,cover_i,number_of_pages_median",
    }, INTERVAL)
    out = []
    for doc in (data or {}).get("docs", []):
        if not doc.get("title"):
            continue
        langs = doc.get("language") or []
        out.append(Record(
            source=NAME, source_ref=doc.get("key", ""), title=doc["title"], subtitle=doc.get("subtitle", "") or "",
            creators=list(doc.get("author_name") or [])[:4], language=_lang(langs[0]) if langs else "",
            year=doc.get("first_publish_year"), publisher=(doc.get("publisher") or [""])[0],
            pages=doc.get("number_of_pages_median"), isbns=clean_isbns(doc.get("isbn") or [])[:5], cover_url=_cover(doc),
        ))
    return out


def by_isbn(isbn):
    data = get_json(NAME, f"{BASE}/isbn/{isbn}.json", None, INTERVAL)
    if not data:
        return []
    authors = []
    for ref in data.get("authors", [])[:3]:
        key = ref.get("key") if isinstance(ref, dict) else None
        if key:
            a = get_json(NAME, f"{BASE}{key}.json", None, INTERVAL)
            if a and a.get("name"):
                authors.append(a["name"])
    langs = [l.get("key", "").rsplit("/", 1)[-1] for l in data.get("languages", []) if isinstance(l, dict)]
    covers = data.get("covers") or []
    return [Record(
        source=NAME, source_ref=data.get("key", ""), title=data.get("title", ""), subtitle=data.get("subtitle", "") or "",
        creators=authors, language=_lang(langs[0]) if langs else "", year=year_of(data.get("publish_date")),
        publisher=(data.get("publishers") or [""])[0], pages=data.get("number_of_pages"),
        isbns=clean_isbns((data.get("isbn_13") or []) + (data.get("isbn_10") or []) + [isbn]),
        cover_url=f"{COVERS}/id/{covers[0]}-L.jpg" if covers else f"{COVERS}/isbn/{isbn}-L.jpg",
    )]


def _lang(code):
    return {"heb": "he", "eng": "en", "rus": "ru", "ara": "ar", "fre": "fr", "ger": "de", "spa": "es"}.get(code, code[:2] if code else "")
