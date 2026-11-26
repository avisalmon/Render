"""Text out of submitted files (spec 4.7, backlog D2.3), for the committee's
"text beside the file" view and, in Epic G, the document index.

PDF goes through PyMuPDF: measured on four real submitted PDFs (2026-11-26),
pypdf returned one of them with every Hebrew word reversed, PyMuPDF read all
four in reading order, five to ten times faster. DOCX is read from its own
XML and XLSX through `xlsx.py`, so neither needs a library.

The extraction runs where the files are (the server holds them; the PC that
replicated them does not ship text), through `extract_missing`, called by
the token endpoint `api/admin/extract/` and by the API on upload. It never
raises for a bad file: the note says what happened and the row stays.
"""

import io
import re
import zipfile
from xml.etree import ElementTree as ET

from django.utils import timezone

MAX_CHARS = 400_000
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _clean(text):
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CHARS]


def pdf_text(data):
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [page.get_text() for page in doc]
    text = _clean("\n\n".join(pages))
    return text, f"pdf: {len(pages)} pages" + ("" if text else ", no text (a scan?)")


def docx_text(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paragraphs = []
    for p in root.iter(WORD_NS + "p"):
        runs = []
        for node in p.iter():
            if node.tag == WORD_NS + "t":
                runs.append(node.text or "")
            elif node.tag == WORD_NS + "tab":
                runs.append("\t")
            elif node.tag == WORD_NS + "br":
                runs.append("\n")
        paragraphs.append("".join(runs))
    text = _clean("\n".join(paragraphs))
    return text, f"docx: {len(paragraphs)} paragraphs" + ("" if text else ", no text")


def xlsx_text(data):
    from . import xlsx

    sheets = xlsx.sheets(io.BytesIO(data))
    parts = []
    for name, rows in sheets.items():
        lines = []
        for row in rows:
            cells = ["" if v is None else (f"{v:g}" if isinstance(v, float) else str(v)).strip() for v in row]
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                lines.append(" | ".join(cells))
        parts.append(f"## {name}\n" + "\n".join(lines))
    text = _clean("\n\n".join(parts))
    return text, f"xlsx: {len(sheets)} sheets" + ("" if text else ", no text")


READERS = {"pdf": pdf_text, "docx": docx_text, "xlsx": xlsx_text}


def extract_bytes(data, name):
    """(text, note) for a file's bytes by its name's extension. Never raises."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    reader = READERS.get(ext)
    if reader is None:
        return "", f"unsupported .{ext or '?'}"
    try:
        return reader(data)
    except Exception as exc:  # noqa: BLE001  a broken file is a note on its row, not a crash
        return "", f"error: {exc.__class__.__name__}: {str(exc)[:120]}"


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
