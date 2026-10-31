"""Saying the message instead of typing it (Avi, 2026-10-31).

The browser records a short clip and sends it once; the transcription model
turns it into text, which goes into the message box to be read and fixed
before it is sent. Nothing is kept: not the audio, not the text until the
person sends it. Saying it is not a turn; its cost rides on the message it
becomes (a signed token from here to `send`), so it counts toward the
day's limit like everything else. Clips that never become a message are
capped per day per person.
"""

from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.utils import timezone

from . import llm

DEFAULT_MODEL = "gpt-4o-transcribe"
USD_PER_MINUTE = Decimal("0.006")  # gpt-4o-transcribe list price, as in books/notes.py (checked 2026-10-21)
MAX_SECONDS = 120
MAX_BYTES = 8 * 1024 * 1024
CLIPS_PER_DAY = 60
SALT = "design3d-voice"
TOKEN_AGE = 6 * 3600
AUDIO_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
               "audio/wav": "wav", "audio/x-m4a": "m4a", "audio/aac": "m4a"}
STUB_TEXT = "A box about 80 by 50 mm and 30 mm high, with a lid."


class VoiceError(Exception):
    """A refusal, with the sentence the person sees."""


def _count_key(maker):
    return f"design3d:voice:{maker.pk}:{timezone.localdate().isoformat()}"


def cost(seconds):
    return (USD_PER_MINUTE * Decimal(seconds) / Decimal(60)).quantize(Decimal("0.00001"))


def transcribe(maker, upload, seconds=None, client=None):
    """(text, token) for a short recording. The token carries the cost to
    the message the text becomes."""
    if upload is None or not upload.size:
        raise VoiceError("Nothing was recorded. Try again.")
    if upload.size > MAX_BYTES:
        raise VoiceError("That was too long. Say it in two parts.")
    kind = (upload.content_type or "").split(";")[0].strip().lower()
    ext = AUDIO_TYPES.get(kind)
    if ext is None:
        raise VoiceError("This browser recorded in a format we cannot read. Type it instead.")
    key = _count_key(maker)
    if cache.get(key, 0) >= CLIPS_PER_DAY:
        raise VoiceError("That is enough talking for today. Type it instead.")
    try:
        seconds = min(MAX_SECONDS, max(1, int(float(seconds or 0)))) if seconds else MAX_SECONDS
    except (TypeError, ValueError):
        seconds = MAX_SECONDS
    if llm.stub_mode() and client is None:
        text = STUB_TEXT
    else:
        client = client or llm._openai()
        try:
            # No language given: the model hears Hebrew, English and the two mixed.
            result = client.audio.transcriptions.create(
                model=getattr(settings, "DESIGN3D_VOICE_MODEL", DEFAULT_MODEL),
                file=(f"clip.{ext}", upload.read(), kind))
            text = (getattr(result, "text", None) or (result if isinstance(result, str) else "")).strip()
        except Exception as exc:  # noqa: BLE001
            raise VoiceError("Could not turn it into text. Try again, or type it.") from exc
    cache.set(key, cache.get(key, 0) + 1, 26 * 3600)
    if not text:
        raise VoiceError("I did not hear any words. Try again, closer to the microphone.")
    return text[:4000], signing.dumps({"m": maker.pk, "c": str(cost(seconds))}, salt=SALT)


def cost_of(maker, tokens):
    """The cost carried by the tokens sent with a message (bad, old or
    someone else's are ignored)."""
    total = Decimal("0")
    for t in tokens[:20]:
        try:
            data = signing.loads(t, salt=SALT, max_age=TOKEN_AGE)
        except signing.BadSignature:
            continue
        if data.get("m") == maker.pk:
            total += Decimal(data.get("c") or "0")
    return total
