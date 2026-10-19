"""Reading the books off a shelf photo (spec BK3).

The method is the `bookshelf-recognition` skill's best known method, measured
on 2026-10-17 (89% of visible books on 70 labelled, mostly Hebrew books, about
$0.025 a shelf): gpt-6.1-sol, reasoning effort low, image detail high, the
photo cut into two vertical strips with 15% overlap, one call per strip in
parallel, a strict JSON schema, and a merge that only de-duplicates near the
strip edge so sequels survive. Ported from the skill's `bookshelf.py`; change
it only after re-measuring (`manage.py books_measure`).

Differences from the skill, all on purpose:
- the key comes from Django settings (OPENAI_API_KEY), never a .env search;
- the image comes as bytes from Books' storage, already rotated and stripped;
- every call is recorded as a ModelCall with its cost;
- a 401 raises `KeyProblem`, so a job stops instead of retrying (skill pitfall).
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

from django.conf import settings
from PIL import Image, ImageOps

DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "low"
DEFAULT_STRIPS = 2
STRIP_OVERLAP = 0.15
IMAGE_DETAIL = "high"

# USD per 1M tokens (input, output), from the skill, checked 2026-10-16.
PRICES = {
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
    "gpt-6-luna": (0.10, 0.50),
}

PROMPT = """You are looking at a photo of books on a shelf.
List every book whose spine or cover you can read, from left to right.
For each book give the title and author exactly as printed, in the original language
(many books are in Hebrew; keep Hebrew titles in Hebrew, do not translate).
Use your knowledge to complete a title or author only when the visible text clearly identifies the book.
Skip books you cannot read. Do not invent books."""

SCHEMA = {
    "type": "object",
    "properties": {"books": {"type": "array", "items": {
        "type": "object",
        "properties": {"title": {"type": "string"}, "author": {"type": "string"}},
        "required": ["title", "author"], "additionalProperties": False}}},
    "required": ["books"], "additionalProperties": False,
}

MATCH_THRESHOLD = 0.8
DEDUPE_THRESHOLD = 0.9
EDGE_BOOKS = 6
_PUNCT = re.compile(r"[\"'`׳״‘’“”.,:;!?()\[\]\-־–—|/\\]")
_DIGITS = re.compile(r"\d+")


class KeyProblem(Exception):
    """The API key is missing, expired or invalidated: stop, do not retry."""


@dataclass
class Book:
    title: str
    author: str = ""


@dataclass
class Reading:
    model: str
    books: list[Book] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)  # one per strip: tokens, seconds, ok
    strip_books: list[list[Book]] = field(default_factory=list)

    @property
    def input_tokens(self):
        return sum(c["input_tokens"] for c in self.calls)

    @property
    def output_tokens(self):
        return sum(c["output_tokens"] for c in self.calls)

    @property
    def seconds(self):
        return max((c["seconds"] for c in self.calls), default=0.0)

    @property
    def cost_usd(self):
        return sum((c["cost_usd"] for c in self.calls), Decimal(0))


def cost_of(model, input_tokens, output_tokens):
    p_in, p_out = PRICES.get(model, (0, 0))
    return Decimal(str((input_tokens * p_in + output_tokens * p_out) / 1_000_000)).quantize(Decimal("0.00001"))


def get_client():
    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        raise KeyProblem("OPENAI_API_KEY is not set")
    from openai import OpenAI

    return OpenAI(api_key=key)


def _data_url(image):
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def split_strips(image, strips, overlap=STRIP_OVERLAP):
    w, h = image.size
    step = w / strips
    pad = int(step * overlap)
    return [image.crop((max(0, int(i * step) - pad), 0, min(w, int((i + 1) * step) + pad), h)) for i in range(strips)]


def read_strip(client, image, model, effort):
    extra = {"reasoning": {"effort": effort}} if effort else {}
    start = time.perf_counter()
    try:
        response = client.responses.create(
            model=model, **extra,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": _data_url(image), "detail": IMAGE_DETAIL},
            ]}],
            text={"format": {"type": "json_schema", "name": "shelf_books", "schema": SCHEMA, "strict": True}},
        )
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 401 or exc.__class__.__name__ == "AuthenticationError":
            raise KeyProblem(str(exc)[:200]) from exc
        raise
    data = json.loads(response.output_text)
    usage = response.usage
    tin = usage.input_tokens if usage else 0
    tout = usage.output_tokens if usage else 0
    books = [Book(b["title"].strip(), b["author"].strip()) for b in data.get("books", []) if b.get("title", "").strip()]
    return books, {"input_tokens": tin, "output_tokens": tout, "seconds": round(time.perf_counter() - start, 1),
                   "cost_usd": cost_of(model, tin, tout)}


def read_shelf(image_bytes, model=None, effort=None, strips=None, client=None) -> Reading:
    model = model or getattr(settings, "BOOKS_SCAN_MODEL", DEFAULT_MODEL)
    effort = effort or getattr(settings, "BOOKS_SCAN_EFFORT", DEFAULT_EFFORT)
    strips = strips or DEFAULT_STRIPS
    client = client or get_client()
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
    parts = split_strips(image, strips) if strips > 1 else [image]
    with ThreadPoolExecutor(max_workers=len(parts)) as pool:
        results = list(pool.map(lambda part: read_strip(client, part, model, effort), parts))
    strip_books = [r[0] for r in results]
    return Reading(model=model, books=merge_strips(strip_books), calls=[r[1] for r in results], strip_books=strip_books)


# ---- merging, exactly as measured -------------------------------------------------

def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


def similarity(a, b, allow_substring=True):
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    if _DIGITS.findall(a) != _DIGITS.findall(b):
        return 0.0
    wa, wb = a.split(), b.split()
    shared = 0
    while shared < min(len(wa), len(wb)) and wa[shared] == wb[shared]:
        shared += 1
    rest_a, rest_b = " ".join(wa[shared:]), " ".join(wb[shared:])
    if shared and rest_a and rest_b and SequenceMatcher(None, rest_a, rest_b).ratio() < 0.7:
        return 0.0
    if allow_substring and len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def merge_strips(strip_books):
    merged = []
    for books in strip_books:
        tail = merged[-EDGE_BOOKS:]
        for i, book in enumerate(books):
            dup = i < EDGE_BOOKS and any(similarity(book.title, t.title) >= MATCH_THRESHOLD for t in tail)
            if dup:
                for j, t in enumerate(merged):
                    if t in tail and similarity(book.title, t.title) >= MATCH_THRESHOLD:
                        if len(book.title) > len(t.title):
                            merged[j] = book
                        break
            else:
                merged.append(book)
    unique = []
    for book in merged:
        if not any(similarity(book.title, u.title, allow_substring=False) >= DEDUPE_THRESHOLD
                   and similarity(book.author, u.author) >= MATCH_THRESHOLD for u in unique):
            unique.append(book)
    return unique


# ---- scoring (the accuracy gate) ---------------------------------------------------

def load_labels(text):
    books = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "?")):
            continue
        title, _, author = line.partition("|")
        books.append(Book(title.strip(), author.strip()))
    return books


def score(labels, predictions):
    remaining = []
    for p in predictions:
        if not any(similarity(p.title, u.title, allow_substring=False) >= DEDUPE_THRESHOLD for u in remaining):
            remaining.append(p)
    found, missed = [], []
    for label in labels:
        best = max(remaining, key=lambda p: similarity(label.title, p.title), default=None)
        if best is not None and similarity(label.title, best.title) >= MATCH_THRESHOLD:
            found.append(label)
            remaining.remove(best)
        else:
            missed.append(label)
    return {"found": found, "missed": missed, "extra": remaining}
