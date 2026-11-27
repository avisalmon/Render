"""The readers of submitted files, pure Python, no Django: they run in a child
process (extract.py) so a file that crashes a library or eats the memory
takes the child down and not the web worker. `read(ext, data)` returns
(text, note) and never raises for a bad file.

PDF goes through PyMuPDF (measured 2026-11-26 against pypdf, which reversed
the Hebrew of one real file); DOCX is read from its own XML; XLSX through
xlsx.py, streaming.
"""

import io
import re
import zipfile
from xml.etree import ElementTree as ET

MAX_CHARS = 400_000
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def clean(text):
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CHARS]


def pdf_text(data):
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [page.get_text() for page in doc]
    text = clean("\n\n".join(pages))
    return text, f"pdf: {len(pages)} pages" + ("" if text else ", no text (a scan?)")


def docx_text(data):
    paragraphs = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        with z.open("word/document.xml") as fh:
            for _event, node in ET.iterparse(fh, events=("end",)):
                if node.tag != WORD_NS + "p":
                    continue
                runs = []
                for child in node.iter():
                    if child.tag == WORD_NS + "t":
                        runs.append(child.text or "")
                    elif child.tag == WORD_NS + "tab":
                        runs.append("\t")
                    elif child.tag == WORD_NS + "br":
                        runs.append("\n")
                paragraphs.append("".join(runs))
                node.clear()
    text = clean("\n".join(paragraphs))
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
    text = clean("\n\n".join(parts))
    return text, f"xlsx: {len(sheets)} sheets" + ("" if text else ", no text")


READERS = {"pdf": pdf_text, "docx": docx_text, "xlsx": xlsx_text}


def read(ext, data):
    """(text, note) for a file's bytes by its extension. Never raises."""
    reader = READERS.get(ext)
    if reader is None:
        return "", f"unsupported .{ext or '?'}"
    try:
        return reader(data)
    except Exception as exc:  # noqa: BLE001  a broken file is a note on its row, not a crash
        return "", f"error: {exc.__class__.__name__}: {str(exc)[:120]}"
