"""The shape every source returns, and the one HTTP helper they share."""

import time
from dataclasses import dataclass, field

import requests
from django.conf import settings

from ..textnorm import normalize, normalize_isbn

TIMEOUT = 8
_last_call = {}


class SourceError(Exception):
    pass


@dataclass
class Record:
    source: str
    source_ref: str
    title: str
    subtitle: str = ""
    creators: list = field(default_factory=list)
    language: str = ""
    year: int | None = None
    publisher: str = ""
    pages: int | None = None
    isbns: list = field(default_factory=list)
    danacode: str = ""
    cover_url: str = ""
    description: str = ""

    def dedupe_key(self):
        for isbn in self.isbns:
            if isbn:
                return ("isbn", isbn)
        return ("title", normalize(self.title), normalize(self.creators[0]) if self.creators else "")

    def as_dict(self):
        return {
            "source": self.source, "source_ref": self.source_ref, "title": self.title, "subtitle": self.subtitle,
            "creators": list(self.creators), "language": self.language, "year": self.year, "publisher": self.publisher,
            "pages": self.pages, "isbns": list(self.isbns), "danacode": self.danacode, "cover_url": self.cover_url,
            "description": self.description[:2000],
        }


def user_agent():
    contact = getattr(settings, "BOOKS_CONTACT_EMAIL", "")
    return f"babook-books/1.0 (+https://babook.co.il/books/; {contact})"


def get_json(name, url, params=None, min_interval=0.0):
    """One GET with a polite User-Agent and a per-source minimum interval."""
    last = _last_call.get(name, 0.0)
    wait = min_interval - (time.monotonic() - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[name] = time.monotonic()
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": user_agent()})
    except requests.RequestException as exc:
        raise SourceError(f"{name}: {exc}") from exc
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise SourceError(f"{name}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError(f"{name}: not JSON") from exc


def clean_isbns(values):
    out = []
    for v in values or []:
        isbn = normalize_isbn(v)
        if isbn and isbn not in out:
            out.append(isbn)
    return out


def year_of(text):
    import re

    m = re.search(r"(1[5-9]\d\d|20\d\d)", str(text or ""))
    return int(m.group(1)) if m else None
