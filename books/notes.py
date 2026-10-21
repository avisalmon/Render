"""My thoughts on a book while I read it (Avi, 2026-10-21).

While the timer runs, a note can be typed or said out loud; notes on a book
add up, in order, so when the book is done every thought from the reading is
in one place. A spoken note is recorded in the browser, sent once, turned
into text by the transcription model and handed back to be read and fixed
before it is saved: the audio itself is never stored.

Every rule lives here; the pages and the API both call it."""

import time
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum

from .models import ModelCall, ReadingNote

MAX_NOTE = 2000
MAX_CLIP_SECONDS = 120
MAX_CLIP_BYTES = 8 * 1024 * 1024
DEFAULT_VOICE_MODEL = "gpt-4o-transcribe"
USD_PER_MINUTE = Decimal("0.006")   # gpt-4o-transcribe list price, checked 2026-10-21
CLIPS_PER_DAY = 60                  # per person
AUDIO_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
               "audio/wav": "wav", "audio/x-m4a": "m4a", "audio/aac": "m4a"}


class NoteError(Exception):
    """A refusal, with a strings.py key as its message."""


def for_book(profile, entry):
    return list(ReadingNote.objects.filter(profile=profile, entry=entry).order_by("created_at"))


def add(profile, entry, body, source=ReadingNote.TYPED, session=None, page=None):
    body = (body or "").strip()
    if not body:
        raise NoteError("notes.err.empty")
    if len(body) > MAX_NOTE:
        raise NoteError("notes.err.long")
    if session is not None and (session.profile_id != profile.pk or session.entry_id != entry.pk):
        session = None
    try:
        page = int(page) if page not in (None, "") else None
    except (TypeError, ValueError):
        page = None
    if page is not None and not 0 <= page <= 100000:
        page = None
    if source not in (ReadingNote.TYPED, ReadingNote.VOICE):
        source = ReadingNote.TYPED
    return ReadingNote.objects.create(profile=profile, entry=entry, session=session, page=page, body=body,
                                      source=source)


def edit(profile, note, body):
    if note.profile_id != profile.pk:
        raise NoteError("notes.err.not_yours")
    body = (body or "").strip()
    if not body:
        raise NoteError("notes.err.empty")
    note.body = body[:MAX_NOTE]
    note.save(update_fields=["body", "updated_at"])
    return note


def remove(profile, note):
    if note.profile_id != profile.pk:
        raise NoteError("notes.err.not_yours")
    note.delete()


# ---- a spoken note ------------------------------------------------------------------

def voice_enabled():
    return bool(getattr(settings, "OPENAI_API_KEY", "")) and getattr(settings, "BOOKS_VOICE_NOTES", True)


def clips_today(profile):
    from .play import day_start, today

    return ModelCall.objects.filter(profile=profile, purpose="voice_note", created_at__gte=day_start(today())).count()


def spent_today():
    from .play import day_start, today

    return ModelCall.objects.filter(purpose="voice_note", created_at__gte=day_start(today())).aggregate(
        n=Sum("cost_usd"))["n"] or Decimal(0)


def transcribe(profile, upload, seconds=None, lang="he", client=None):
    """The words in a short recording, or a NoteError. Nothing is kept but
    the cost of the call."""
    if not voice_enabled():
        raise NoteError("notes.err.no_voice")
    if upload is None or not upload.size:
        raise NoteError("notes.err.no_audio")
    if upload.size > MAX_CLIP_BYTES:
        raise NoteError("notes.err.too_long")
    if clips_today(profile) >= CLIPS_PER_DAY:
        raise NoteError("notes.err.cap")
    if spent_today() >= Decimal(str(getattr(settings, "BOOKS_VOICE_DAILY_USD", "1"))):
        raise NoteError("notes.err.cap")
    kind = (upload.content_type or "").split(";")[0].strip().lower()
    ext = AUDIO_TYPES.get(kind)
    if ext is None:
        raise NoteError("notes.err.format")
    try:
        seconds = min(MAX_CLIP_SECONDS, max(1, int(float(seconds or 0)))) if seconds else MAX_CLIP_SECONDS
    except (TypeError, ValueError):
        seconds = MAX_CLIP_SECONDS
    model = getattr(settings, "BOOKS_VOICE_MODEL", DEFAULT_VOICE_MODEL)
    if client is None:
        from .recognition import get_client

        client = get_client()
    started = time.perf_counter()
    ok, text = True, ""
    try:
        result = client.audio.transcriptions.create(
            model=model, file=(f"note.{ext}", upload.read(), kind), language="he" if lang == "he" else "en")
        text = (getattr(result, "text", None) or (result if isinstance(result, str) else "")).strip()
    except Exception:  # noqa: BLE001
        ok = False
    ModelCall.objects.create(
        profile=profile, provider="openai", model=model, purpose="voice_note", ok=ok,
        cost_usd=(USD_PER_MINUTE * Decimal(seconds) / Decimal(60)).quantize(Decimal("0.00001")),
        duration_ms=int((time.perf_counter() - started) * 1000))
    if not ok:
        raise NoteError("notes.err.voice_failed")
    if not text:
        raise NoteError("notes.err.heard_nothing")
    return text[:MAX_NOTE]
