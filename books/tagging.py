"""Tagging records with the controlled tag list (spec BK9): genre, mood,
audience. A small text model answers in a strict schema whose values
are our own tag keys, so nothing outside the list can come back. Each call
is a ModelCall with its cost. A curator's tags are never overwritten, and an
unsure answer is kept for audit but not applied.

Runs as the `entry.tag` job, started when a record first reaches someone's
library and by the `books_tag_entries` command for what is already there.
"""

import json
import logging
import time
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from . import jobs
from .models import CatalogEntry, EntryTagging, Job, ModelCall, Tag
from .recognition import KeyProblem, cost_of, get_client

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-6-luna"
MIN_CONFIDENCE = Decimal("0.5")
# Form (hardcover, signed, first edition) describes one copy, not the book:
# never guessed by the model.
LIMITS = {"genre": 3, "mood": 2, "audience": 1}


def _vocabulary():
    by_kind = {}
    for t in Tag.objects.filter(kind__in=LIMITS).order_by("kind", "key"):
        by_kind.setdefault(t.kind, []).append(t)
    return by_kind


def schema(vocab):
    def listing(kind):
        return {"type": "array", "items": {"type": "string", "enum": [t.key for t in vocab.get(kind, [])] or ["none"]},
                "maxItems": LIMITS[kind]}

    return {"type": "object", "additionalProperties": False,
            "required": ["genre", "mood", "audience", "confidence"],
            "properties": {"genre": listing("genre"), "mood": listing("mood"), "audience": listing("audience"),
                           "confidence": {"type": "number"}}}


def prompt(entry, vocab):
    lines = [
        "Classify this book with tags from the lists below. Use only keys from the lists. Pick what a librarian "
        "would, from what you know of the book and its author. If you do not know the book, judge from the title "
        "and author and say so with a low confidence (0 to 1). Prefer fewer, surer tags.",
        "",
        f"Title: {entry.title}",
    ]
    if entry.subtitle:
        lines.append(f"Subtitle: {entry.subtitle}")
    if entry.creator_names:
        lines.append(f"Author: {entry.creator_names}")
    if entry.year:
        lines.append(f"Year: {entry.year}")
    if entry.language:
        lines.append(f"Language: {entry.language}")
    if entry.description:
        lines.append(f"About: {entry.description[:600]}")
    for kind, tags in vocab.items():
        lines.append("")
        lines.append(f"{kind} (up to {LIMITS[kind]}): " + "; ".join(f"{t.key} = {t.name_en}" for t in tags))
    return "\n".join(lines)


def classify(entry, client=None, model=None):
    """Ask the model. Returns (answer dict, call dict)."""
    model = model or getattr(settings, "BOOKS_TAG_MODEL", DEFAULT_MODEL)
    client = client or get_client()
    vocab = _vocabulary()
    start = time.perf_counter()
    try:
        response = client.responses.create(
            model=model, input=[{"role": "user", "content": [{"type": "input_text", "text": prompt(entry, vocab)}]}],
            text={"format": {"type": "json_schema", "name": "book_tags", "schema": schema(vocab), "strict": True}},
        )
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "status_code", None) == 401 or exc.__class__.__name__ == "AuthenticationError":
            raise KeyProblem(str(exc)[:200]) from exc
        raise
    answer = json.loads(response.output_text)
    usage = response.usage
    tin = usage.input_tokens if usage else 0
    tout = usage.output_tokens if usage else 0
    return answer, {"model": model, "input_tokens": tin, "output_tokens": tout, "cost_usd": cost_of(model, tin, tout),
                    "seconds": round(time.perf_counter() - start, 1)}


def apply(entry, answer, model_name=""):
    """Write the model's tags unless a curator has tagged this record."""
    tagging = EntryTagging.objects.filter(entry=entry).first()
    if tagging and tagging.source == EntryTagging.CURATOR:
        return tagging
    confidence = Decimal(str(max(0.0, min(1.0, float(answer.get("confidence") or 0))))).quantize(Decimal("0.001"))
    keys = [k for kind in LIMITS for k in (answer.get(kind) or [])][:sum(LIMITS.values())]
    tags = list(Tag.objects.filter(key__in=keys, kind__in=LIMITS))
    tagging, _ = EntryTagging.objects.update_or_create(entry=entry, defaults={
        "source": EntryTagging.MODEL, "model_name": model_name, "confidence": confidence, "raw": answer})
    if confidence >= MIN_CONFIDENCE:
        entry.tags.remove(*entry.tags.filter(kind__in=LIMITS))
        entry.tags.add(*tags)
    return tagging


def curator_tagged(entry):
    """The record's tags were set by hand: the model leaves them alone."""
    EntryTagging.objects.update_or_create(entry=entry, defaults={"source": EntryTagging.CURATOR, "confidence": 1})


@jobs.job("entry.tag")
def tag_job(job):
    entry = CatalogEntry.objects.filter(pk=job.ref_id).first()
    if entry is None or entry.merged_into_id:
        return
    existing = EntryTagging.objects.filter(entry=entry).first()
    if existing and existing.source == EntryTagging.CURATOR:
        return
    answer, call = classify(entry)
    ModelCall.objects.create(profile=job.profile, job=job, provider="openai", model=call["model"], purpose="entry_tag",
                             input_tokens=call["input_tokens"], output_tokens=call["output_tokens"],
                             cost_usd=call["cost_usd"], duration_ms=int(call["seconds"] * 1000))
    apply(entry, answer, call["model"])


def ensure_tagged(entry, profile=None):
    """Start tagging a record that has none, once. Never raises."""
    try:
        if entry is None or EntryTagging.objects.filter(entry=entry).exists() or entry.tags.exists():
            return False
        recent = timezone.now() - timezone.timedelta(days=1)
        if Job.objects.filter(kind="entry.tag", ref_id=entry.pk, created_at__gte=recent).exists():
            return False
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return False
        jobs.enqueue("entry.tag", ref_id=entry.pk, profile=profile)
        return True
    except Exception:  # noqa: BLE001
        log.exception("books: could not start tagging entry %s", getattr(entry, "pk", None))
        return False
