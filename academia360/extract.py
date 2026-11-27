"""Text out of submitted files (spec 4.7, backlog D2.3), for the committee's
"text beside the file" view and, in Epic G, the document index.

The readers live in readers.py (pure Python). Each file is read in a child
process with a time limit and, where the platform allows, a memory cap:
the first production run of the extraction (2026-11-27) answered 502 again
and again on one 2.8 MB spreadsheet, because the reader ate the starter
instance's memory inside the one web worker, and with one worker that is the
whole site (PM-108). A child that crashes or runs too long is a note on the
row; the server stays up and the queue moves on.

The extraction runs where the files are (the server holds them; the PC that
replicated them does not ship text), through `extract_missing`, called by
the token endpoint `api/admin/extract/` and by the API on upload. It never
raises for a bad file: the note says what happened and the row stays.
"""

import json
import subprocess
import sys

from django.conf import settings
from django.utils import timezone

from .readers import READERS, clean  # noqa: F401  (the tests and D2 callers import them from here)

MAX_CHARS = 400_000


def _timeout():
    return int(getattr(settings, "ACADEMIA360_READER_TIMEOUT", 60))


def _memory_mb():
    return int(getattr(settings, "ACADEMIA360_READER_MEMORY_MB", 300))


def _script(ext):
    """The child's program: cap its memory where the platform can (Linux),
    read the bytes from stdin, answer with JSON on stdout."""
    base = str(settings.BASE_DIR).replace("\\", "/")
    return (
        "import sys, json\n"
        "try:\n"
        "    import resource\n"
        f"    cap = {_memory_mb()} * 1024 * 1024\n"
        "    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))\n"
        "except Exception:\n"
        "    pass\n"
        f"sys.path.insert(0, {base!r})\n"
        "from academia360 import readers\n"
        f"text, note = readers.read({ext!r}, sys.stdin.buffer.read())\n"
        "sys.stdout.write(json.dumps({'text': text, 'note': note}))\n"
    )


def _in_child(script, data, timeout):
    """Run a reader in its own process. Returns (stdout, None) or (None, why)."""
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", script], input=data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s (a heavy scan?)"
    except OSError as exc:
        return None, f"cannot start the reader: {str(exc)[:80]}"
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, f"the reader crashed (exit {proc.returncode})" + (f": {tail[-1][:80]}" if tail else "")
    return proc.stdout.decode("utf-8", "replace"), None


def extract_bytes(data, name):
    """(text, note) for a file's bytes by its name's extension. Never raises."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in READERS:
        return "", f"unsupported .{ext or '?'}"
    out, why = _in_child(_script(ext), data, _timeout())
    if why is not None:
        return "", f"error: {why}"
    try:
        answer = json.loads(out)
    except ValueError:
        return "", "error: the reader answered nothing readable"
    return answer.get("text", "")[:MAX_CHARS], answer.get("note", "")[:200]


def extract_row(row, save=True):
    """Read a SubmittedFile's text into its row. Returns the note."""
    try:
        with row.file.storage.open(row.file.name, "rb") as fh:
            data = fh.read()
    except Exception as exc:  # noqa: BLE001
        text, note = "", f"error: cannot open: {str(exc)[:120]}"
    else:
        text, note = extract_bytes(data, row.original_name or row.file.name)
    row.extracted_text = text
    row.extraction_note = note
    row.extracted_at = timezone.now()
    if save:
        row.save(update_fields=["extracted_text", "extraction_note", "extracted_at", "updated_at"])
    return note


def missing():
    from .models import SubmittedFile

    return SubmittedFile.objects.filter(extracted_at__isnull=True).order_by("pk")


def extract_missing(limit=10):
    """A few files per call, so a request never runs long. Returns counts and
    the notes, for the endpoint's answer and the CLI."""
    done, with_text, notes = 0, 0, []
    for row in missing()[:limit]:
        note = extract_row(row)
        done += 1
        with_text += bool(row.extracted_text)
        notes.append({"file": row.pk, "name": row.original_name, "note": note, "chars": len(row.extracted_text)})
    return {"extracted": done, "with_text": with_text, "left": missing().count(), "notes": notes}
