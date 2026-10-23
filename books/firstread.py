"""The first time with a book (Avi, 2026-10-22): before the first sitting,
the book is in my hands, so this is the moment to give it a real cover, its
length, and what its back cover says.

- The cover photo is cropped on the phone to the book's shape (no model,
  nothing spent). It becomes my copy's cover photo, and the catalogue's
  cover when the catalogue has none or only a small one.
- The back cover is read once, on request, by the same vision model that
  reads shelves (about one to two cents): the blurb, the ISBN, publisher,
  year and page count. It only fills what the catalogue lacks; where it
  differs from what is there, it files a correction for the curators.
  Android phones read the barcode themselves for free and send it along.

Every rule lives here; the pages call it."""

import io
import json
import time
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone

from . import images
from .models import BookDetail, CatalogEntry, Copy, CopyPhoto, EntryCorrection, EntryIdentifier, ModelCall, ReadingSession
from .textnorm import normalize_isbn

SMALL_COVER = 400  # px wide: a catalogue cover narrower than this is replaced by a reader's photo
COVER_MAX_SIDE = 1400
MAX_PHOTO_BYTES = 15 * 1024 * 1024
BACK_DAILY_USD_DEFAULT = "1"
BACK_LINE = "מהכריכה האחורית:"


class FirstReadError(Exception):
    """A refusal, with a strings.py key as its message."""


def is_first_time(profile, entry):
    return not ReadingSession.objects.filter(profile=profile, entry=entry).exists()


def my_copy(profile, entry):
    return Copy.objects.filter(owner=profile, entry=entry, status__in=Copy.HELD).first()


def cover_for(profile, entry):
    """What shows as this book's cover for me: my own photo first."""
    copy = my_copy(profile, entry)
    photo = copy.photos.filter(kind="cover").last() if copy else None
    if photo:
        return {"copy_photo": photo, "copy": copy}
    if entry.cover:
        return {"url": entry.cover.url}
    return None


def _cover_is_small(entry):
    if not entry.cover:
        return True
    try:
        from PIL import Image

        with entry.cover.open("rb") as fh:
            return Image.open(fh).size[0] < SMALL_COVER
    except Exception:  # noqa: BLE001
        return True


def _mine(entry, profile):
    """The catalogue's cover is a photo I took (its file name says whose)."""
    return bool(entry.cover) and not entry.cover_source_url and f"{entry.pk}-reader-{profile.pk}-" in entry.cover.name


def save_cover(profile, entry, upload):
    """My photo of the front cover. Returns {"catalogue": bool}."""
    if upload is None or not upload.size:
        raise FirstReadError("first.err.no_photo")
    if upload.size > MAX_PHOTO_BYTES:
        raise FirstReadError("first.err.too_big")
    try:
        prepared = images.prepare(upload, max_side=COVER_MAX_SIDE)
    except Exception as exc:  # noqa: BLE001
        raise FirstReadError("first.err.not_image") from exc
    stamp = f"{timezone.now():%Y%m%d%H%M%S}"
    copy = my_copy(profile, entry)
    if copy is not None:
        copy.photos.filter(kind="cover").delete()
        photo = CopyPhoto(copy=copy, kind="cover")
        photo.image.save(f"{copy.pk}-cover-{stamp}.jpg", ContentFile(prepared.data), save=True)
    # My photo also replaces my own earlier photo (Avi, 2026-10-23: a straightened
    # cover that came out wrong is taken again, or kept as shot); anyone else's good
    # cover stays.
    catalogue = _cover_is_small(entry) or _mine(entry, profile)
    if catalogue:
        entry.cover.save(f"{entry.pk}-reader-{profile.pk}-{stamp}.jpg", ContentFile(prepared.data), save=False)
        entry.cover_source_url = ""
        entry.save(update_fields=["cover", "cover_source_url"])
    return {"catalogue": catalogue, "copy": copy is not None}


# ---- the back cover ----------------------------------------------------------------

BACK_PROMPT = """You are looking at the back cover of a book.
Return, exactly as printed (keep Hebrew in Hebrew, do not translate):
- blurb: the description text on the back cover, joined into plain paragraphs (empty if none);
- isbn: the ISBN printed or under the barcode, digits only (empty if none);
- publisher: the publisher's name if printed (empty if none);
- year: the publication year if printed, else 0;
- pages: the number of pages if printed, else 0.
Do not invent anything that is not on the cover."""

BACK_SCHEMA = {
    "type": "object",
    "properties": {"blurb": {"type": "string"}, "isbn": {"type": "string"}, "publisher": {"type": "string"},
                   "year": {"type": "integer"}, "pages": {"type": "integer"}},
    "required": ["blurb", "isbn", "publisher", "year", "pages"], "additionalProperties": False,
}


def back_enabled():
    return bool(getattr(settings, "OPENAI_API_KEY", "")) and getattr(settings, "BOOKS_BACK_COVER", True)


def _spent_today():
    from .play import day_start, today

    return ModelCall.objects.filter(purpose="back_cover", created_at__gte=day_start(today())).aggregate(
        n=Sum("cost_usd"))["n"] or Decimal(0)


def ask_back(image_bytes, client=None, model=None):
    """One call: what the back cover says. Pure network, no database."""
    from PIL import Image, ImageOps

    from . import recognition

    model = model or getattr(settings, "BOOKS_SCAN_MODEL", recognition.DEFAULT_MODEL)
    client = client or recognition.get_client()
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
    start = time.perf_counter()
    try:
        response = client.responses.create(
            model=model, reasoning={"effort": "low"},
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": BACK_PROMPT},
                {"type": "input_image", "image_url": recognition._data_url(image), "detail": "high"},
            ]}],
            text={"format": {"type": "json_schema", "name": "back_cover", "schema": BACK_SCHEMA, "strict": True}},
        )
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 401 or exc.__class__.__name__ == "AuthenticationError":
            raise recognition.KeyProblem(str(exc)[:200]) from exc
        raise
    usage = response.usage
    tin = usage.input_tokens if usage else 0
    tout = usage.output_tokens if usage else 0
    return json.loads(response.output_text), {"model": model, "input_tokens": tin, "output_tokens": tout,
                                              "cost_usd": recognition.cost_of(model, tin, tout),
                                              "seconds": time.perf_counter() - start}


def _suggest(profile, entry, field, value, why):
    if not EntryCorrection.objects.filter(entry=entry, field=field, value=value, status=EntryCorrection.OPEN).exists():
        EntryCorrection.objects.create(entry=entry, profile=profile, field=field, value=str(value)[:300], note=why)


def read_back(profile, entry, upload, isbn_hint="", client=None):
    """Read my photo of the back cover and fill what the catalogue lacks.
    Returns what changed: {"filled": [...], "suggested": [...], "pages": n or None}."""
    if not back_enabled():
        raise FirstReadError("first.err.no_back")
    if upload is None or not upload.size:
        raise FirstReadError("first.err.no_photo")
    if upload.size > MAX_PHOTO_BYTES:
        raise FirstReadError("first.err.too_big")
    if _spent_today() >= Decimal(str(getattr(settings, "BOOKS_BACK_DAILY_USD", BACK_DAILY_USD_DEFAULT))):
        raise FirstReadError("first.err.cap")
    try:
        prepared = images.prepare(upload, max_side=2400)
    except Exception as exc:  # noqa: BLE001
        raise FirstReadError("first.err.not_image") from exc
    ok, data, call = True, {}, {"model": "", "input_tokens": 0, "output_tokens": 0, "cost_usd": Decimal(0), "seconds": 0}
    try:
        data, call = ask_back(prepared.data, client=client)
    except Exception:  # noqa: BLE001
        ok = False
    ModelCall.objects.create(profile=profile, provider="openai", model=call["model"] or "back-cover", purpose="back_cover",
                             input_tokens=call["input_tokens"], output_tokens=call["output_tokens"],
                             cost_usd=call["cost_usd"], duration_ms=int(call["seconds"] * 1000), ok=ok)
    if not ok:
        raise FirstReadError("first.err.back_failed")
    return apply_back(profile, entry, data, isbn_hint)


def apply_back(profile, entry, data, isbn_hint=""):
    filled, suggested = [], []
    entry = CatalogEntry.objects.get(pk=entry.pk)
    detail, _ = BookDetail.objects.get_or_create(entry=entry)
    blurb = (data.get("blurb") or "").strip()
    if blurb and blurb[:80] not in entry.description:
        # Avi, 2026-10-23: the back cover's words go into the description; an existing
        # description stays first, the blurb joins it under its own line.
        if entry.description.strip():
            entry.description = (entry.description.rstrip() + "\n\n" + BACK_LINE + "\n" + blurb)[:4000]
        else:
            entry.description = blurb[:4000]
        entry.save(update_fields=["description"])
        filled.append("description")
    isbn = normalize_isbn(data.get("isbn") or "") or normalize_isbn(isbn_hint or "")
    if isbn and not EntryIdentifier.objects.filter(entry=entry, value=isbn).exists():
        EntryIdentifier.objects.create(entry=entry, scheme="isbn13", value=isbn)
        filled.append("isbn")
    publisher = (data.get("publisher") or "").strip()[:200]
    if publisher:
        if not detail.publisher:
            detail.publisher = publisher
            detail.save(update_fields=["publisher"])
            filled.append("publisher")
        elif detail.publisher.strip() != publisher:
            _suggest(profile, entry, "publisher", publisher, "from the back cover")
            suggested.append("publisher")
    year = data.get("year") or 0
    if 1450 <= int(year) <= timezone.now().year + 1:
        if not entry.year:
            entry.year = int(year)
            entry.save(update_fields=["year"])
            filled.append("year")
        elif entry.year != int(year):
            _suggest(profile, entry, "year", year, "from the back cover")
            suggested.append("year")
    pages = data.get("pages") or 0
    pages = int(pages) if 10 <= int(pages) <= 5000 else None
    if pages and not detail.pages:
        detail.pages = pages
        detail.save(update_fields=["pages"])
        filled.append("pages")
    return {"filled": filled, "suggested": suggested, "pages": pages or detail.pages}
