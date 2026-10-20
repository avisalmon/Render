"""Finding a book on the web when the free sources could not (Avi,
2026-10-20): its real title, authors, publisher, year, ISBN and cover.

The order is the cost order. Open Library, Google Books and the National
Library are free and asked first (books/catalog.py); this runs only for a
book none of them matched well. OpenAI's web search costs about one cent a
search on any model, so the model is the cheapest (gpt-6-luna), every book
is searched once for the whole site (WebLookup is the cache, found or not),
and a day's spend is capped (BOOKS_WEB_DAILY_USD, $2 by Avi). Nothing is saved silently: what
comes back becomes a candidate the person confirms on the review screen.

Measured 2026-10-20 on five spines (four Hebrew): four found with ISBN,
publisher, year and cover; about $0.036 a book with three searches each,
almost all of it the search fee. With the real call: `max_tool_calls=2` did
not limit web searches (three ran), and asking for one search in the prompt
was obeyed once in three and then lost the ISBN. So: about $0.03 a book,
which a $2 day allows for about 50 new books.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum

from .models import ModelCall, WebLookup
from .recognition import KeyProblem, cost_of, get_client
from .textnorm import normalize, normalize_isbn, valid_isbn13

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-6-luna"
SEARCH_FEE = Decimal("0.01")      # per web search call, any model
MAX_SEARCHES = 2                  # asked per book; not enforced by the API for web search (measured)
RESERVE_PER_BOOK = Decimal("0.04")  # what one book may cost, so the day's cap is never overshot
WORKERS = 6

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["found", "title", "authors", "publisher", "year", "isbn", "cover_url", "source_url",
                       "confidence"],
          "properties": {"found": {"type": "boolean"}, "title": {"type": "string"},
                         "authors": {"type": "array", "items": {"type": "string"}},
                         "publisher": {"type": "string"}, "year": {"type": "string"}, "isbn": {"type": "string"},
                         "cover_url": {"type": "string"}, "source_url": {"type": "string"},
                         "confidence": {"type": "number"}}}

PROMPT = ("Find this exact book on the web (a bookshop, a library catalogue or a publisher's page). The title was "
          "read from a book spine and may be slightly wrong; the author is usually right. Return its real title, "
          "authors, publisher, year, ISBN (13 digits if you can), a direct URL of its cover image, and the page you "
          "found it on. If you cannot find this book, found=false. Never invent a value: leave it empty.\n\n"
          "Title as read: {title}\nAuthor as read: {author}")


def key_for(title, author):
    return f"{normalize(title)}|{normalize(author)}"[:300]


def enabled():
    return bool(getattr(settings, "OPENAI_API_KEY", "")) and getattr(settings, "BOOKS_WEB_LOOKUP", True)


def spent_today():
    from .play import day_start, today

    return ModelCall.objects.filter(purpose="web_lookup", created_at__gte=day_start(today())).aggregate(
        n=Sum("cost_usd"))["n"] or Decimal(0)


def daily_cap():
    return Decimal(str(getattr(settings, "BOOKS_WEB_DAILY_USD", "2")))


def room_today():
    """How many more books today's budget allows."""
    left = daily_cap() - spent_today()
    return max(0, int(left / RESERVE_PER_BOOK))


def ask(title, author, client=None, model=None):
    """One book, one request: pure network, no database (runs in a thread)."""
    model = model or getattr(settings, "BOOKS_WEB_MODEL", DEFAULT_MODEL)
    client = client or get_client()
    start = time.perf_counter()
    try:
        response = client.responses.create(
            model=model, tools=[{"type": "web_search"}], max_tool_calls=MAX_SEARCHES,
            input=PROMPT.format(title=title, author=author or "(unknown)"),
            text={"format": {"type": "json_schema", "name": "book", "schema": SCHEMA, "strict": True}},
        )
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 401 or exc.__class__.__name__ == "AuthenticationError":
            raise KeyProblem(str(exc)[:200]) from exc
        raise
    searches = sum(1 for item in (response.output or []) if getattr(item, "type", "") == "web_search_call")
    usage = response.usage
    tin = usage.input_tokens if usage else 0
    tout = usage.output_tokens if usage else 0
    cost = cost_of(model, tin, tout) + SEARCH_FEE * searches
    try:
        answer = json.loads(response.output_text)
    except (TypeError, ValueError):
        answer = {"found": False}
    return answer, {"model": model, "input_tokens": tin, "output_tokens": tout, "searches": searches,
                    "cost_usd": cost, "seconds": round(time.perf_counter() - start, 1)}


def to_record(answer):
    """The answer as a catalogue Record, with only what can be trusted: an
    ISBN must pass its checksum, a year must be a year, URLs must be web."""
    from .sources.base import Record

    if not answer.get("found") or not (answer.get("title") or "").strip():
        return None
    isbn = normalize_isbn(answer.get("isbn") or "")
    isbns = [isbn] if isbn and valid_isbn13(isbn) else []
    year = None
    digits = "".join(ch for ch in str(answer.get("year") or "") if ch.isdigit())[:4]
    if len(digits) == 4 and 1450 <= int(digits) <= 2100:
        year = int(digits)
    cover = (answer.get("cover_url") or "").strip()
    if not cover.startswith("https://"):
        cover = ""
    return Record("web", "", answer["title"].strip()[:300],
                  creators=[a.strip() for a in (answer.get("authors") or []) if a and a.strip()][:4],
                  year=year, publisher=(answer.get("publisher") or "").strip()[:200], isbns=isbns, cover_url=cover)


def lookup_many(items, profile=None, job=None, client=None):
    """Look up books the free sources missed: [(title, author)] in, a dict
    {(title, author): WebLookup} out. Cached ones cost nothing; new ones run
    in parallel within today's budget; the rest wait for tomorrow's scan."""
    from . import catalog

    out, todo = {}, []
    for title, author in items:
        cached = WebLookup.objects.filter(key=key_for(title, author)).first()
        if cached:
            out[(title, author)] = cached
        elif (title, author) not in todo:
            todo.append((title, author))
    if not todo or not enabled():
        return out
    todo = todo[:room_today()]
    if not todo:
        log.info("books web lookup: today's budget is spent")
        return out
    client = client or get_client()

    def one(pair):
        try:
            return pair, ask(pair[0], pair[1], client=client), None
        except KeyProblem:
            raise
        except Exception as exc:  # noqa: BLE001
            return pair, None, exc

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, todo))
    for (title, author), got, error in results:
        if error is not None or got is None:
            log.warning("books web lookup failed for %r: %s", title, error)
            continue
        answer, call = got
        ModelCall.objects.create(profile=profile, job=job, provider="openai", model=call["model"], purpose="web_lookup",
                                 input_tokens=call["input_tokens"], output_tokens=call["output_tokens"],
                                 cost_usd=call["cost_usd"], duration_ms=int(call["seconds"] * 1000))
        entry = None
        record = to_record(answer)
        if record is not None:
            try:
                entry, _ = catalog.upsert_from_record(record, created_by=profile)
            except Exception:  # noqa: BLE001
                log.exception("books web lookup: could not save %r", record.title)
        row, _ = WebLookup.objects.update_or_create(key=key_for(title, author), defaults={
            "title": title[:300], "author": (author or "")[:200], "found": entry is not None, "result": answer,
            "source_url": (answer.get("source_url") or "")[:500] if (answer.get("source_url") or "").startswith(
                "http") else "", "entry": entry, "searches": call["searches"], "cost_usd": call["cost_usd"]})
        out[(title, author)] = row
    return out
