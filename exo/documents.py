"""Downloading the feature as a document (PDF or Word).

**The whole difficulty here is one thing: who does the bidi.**

Hebrew is stored logically (first letter first) and displayed visually (first
letter rightmost). Something has to reorder it, and doing it twice reverses the
line back to gibberish. memz lost a production day to exactly this, in both
directions, and its `render.py` docstring is the fuller account. The rule that
falls out is short:

- **Word does its own.** A `.docx` carries logical text plus `w:bidi` on the
  paragraph and `w:rtl` on the run, and Word lays it out. Calling
  `get_display` before writing would hand Word an already-reversed string to
  reverse again.
- **ReportLab does none.** It draws glyphs in the order it is given, so the
  text must be reordered here, with `python-bidi`, and drawn right-aligned.

So the two formats need *opposite* treatment of the same string, which is why
`_visual` exists and why it is called in one of these builders and not the
other. The tests assert both directions.

The base direction is pinned to `"R"` rather than auto-detected. Auto-detection
guesses from the first strong character and silently flips a whole paragraph
for anything opening with an English word, a digit or a quote mark, all of
which are ordinary ways for one of these features to begin.

**No new dependency for Word.** A `.docx` is a zip of three small XML parts,
and writing them directly keeps the site's build unchanged and gives exact
control over the RTL attributes, which is the part that matters. The PDF needs
ReportLab, which is pure Python and added to requirements for this.
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape

from bidi.algorithm import get_display
from django.conf import settings

#: Shipped with the repo and already used elsewhere on the site. Covers all 27
#: Hebrew letters plus Latin and digits, checked rather than assumed.
FONT_REGULAR = settings.BASE_DIR / "static" / "fonts" / "Heebo_400Regular.ttf"
FONT_BOLD = settings.BASE_DIR / "static" / "fonts" / "Heebo_700Bold.ttf"

HEBREW = re.compile(r"[֐-׿]")


def is_rtl(text):
    return bool(HEBREW.search(text or ""))


def _visual(text):
    """Logical order to visual order, for a renderer that cannot do it itself.

    Only ReportLab needs this. Handing the result to anything that does its own
    bidi (Word, a browser) reverses it a second time.
    """
    return get_display(text or "", base_dir="R")


def _paragraphs(text):
    """Blank-line separated blocks, which is how every generated feature is
    written and how both formats want it."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "")]
    return [b for b in blocks if b]


def filename_for(release, extension):
    """A filename that says what the file is, safe on every platform.

    Built from the headline, because a folder of `download.pdf` is a folder
    nobody can use. Non-filename characters go, including the Hebrew maqaf and
    the quotes a headline is full of.
    """
    stem = (release.headline or "exo").strip()
    stem = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()[:60].rstrip(". ")
    return f"{stem or 'exo'}.{extension}"


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_paragraph(text, rtl, size_half_points=22, bold=False, space_after=180):
    """One `<w:p>`.

    `w:bidi` sets the paragraph's base direction and `w:rtl` the run's, which
    together are what make Word lay Hebrew out correctly. The text itself stays
    in logical order: Word is doing the reordering, and pre-reordering it here
    is the double-reversal bug this module exists to avoid.
    """
    direction = '<w:bidi/>' if rtl else ""
    align = '<w:jc w:val="right"/>' if rtl else '<w:jc w:val="left"/>'
    run_rtl = "<w:rtl/>" if rtl else ""
    weight = "<w:b/>" if bold else ""
    return (
        f"<w:p><w:pPr>{direction}{align}"
        f'<w:spacing w:after="{space_after}"/>'
        f'<w:rPr><w:rFonts w:ascii="Heebo" w:hAnsi="Heebo" w:cs="Heebo"/>'
        f'<w:sz w:val="{size_half_points}"/><w:szCs w:val="{size_half_points}"/>'
        f"{weight}{run_rtl}</w:rPr></w:pPr>"
        f'<w:r><w:rPr><w:rFonts w:ascii="Heebo" w:hAnsi="Heebo" w:cs="Heebo"/>'
        f'<w:sz w:val="{size_half_points}"/><w:szCs w:val="{size_half_points}"/>'
        f"{weight}{run_rtl}</w:rPr>"
        f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    )


def feature_docx(release):
    """The feature as a Word document, as bytes."""
    headline = release.headline or ""
    rtl = is_rtl(headline + " " + (release.body or ""))

    paper = getattr(release.newspaper_style, "name_he" if rtl else "name_en", "") or ""
    dateline = release.dateline.strftime("%d/%m/%Y")

    parts = [
        _docx_paragraph(f"{paper} · {dateline}".strip(" ·"), rtl,
                        size_half_points=18, space_after=240),
        _docx_paragraph(headline, rtl, size_half_points=36, bold=True,
                        space_after=280),
    ]
    for block in _paragraphs(release.body):
        parts.append(_docx_paragraph(block, rtl))

    if release.exponential_score is not None:
        parts.append(_docx_paragraph(
            f"Exponential score: {release.exponential_score}/100", rtl,
            size_half_points=18, space_after=120))

    body_xml = "".join(parts)
    # `w:bidi` in the section properties makes the *page* right-to-left, so
    # Word puts the text block where a Hebrew reader expects it.
    section = f'<w:sectPr>{"<w:bidi/>" if rtl else ""}</w:sectPr>'
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>{body_xml}{section}</w:body></w:document>'
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def feature_pdf(release):
    """The feature as a PDF, as bytes.

    Laid out by hand rather than with a flowable framework: one column of
    wrapped text is all this needs, and doing it directly keeps the right-to-
    left case honest, since every line is reordered and then right-aligned at
    the moment it is drawn.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas as pdf_canvas

    pdfmetrics.registerFont(TTFont("Heebo", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Heebo-Bold", str(FONT_BOLD)))

    headline = release.headline or ""
    rtl = is_rtl(headline + " " + (release.body or ""))

    width, height = A4
    margin = 56
    line_width = width - margin * 2

    buffer = io.BytesIO()
    pdf = pdf_canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(headline or "exo")
    y = height - margin

    def wrap(text, font, size):
        """Greedy wrap on the *logical* text: a word is a word whichever
        direction the line will finally run."""
        words, lines, current = text.split(), [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font, size) <= line_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def draw(text, font, size, leading, gap=0):
        nonlocal y
        pdf.setFont(font, size)
        for line in wrap(text, font, size):
            if y < margin + leading:
                pdf.showPage()
                pdf.setFont(font, size)
                y = height - margin
            # Reordered here and nowhere else: ReportLab has no bidi of its
            # own, so what is handed to it is what gets drawn.
            shaped = _visual(line) if rtl else line
            if rtl:
                pdf.drawRightString(width - margin, y, shaped)
            else:
                pdf.drawString(margin, y, shaped)
            y -= leading
        y -= gap

    paper = getattr(release.newspaper_style, "name_he" if rtl else "name_en", "") or ""
    draw(f"{paper} · {release.dateline.strftime('%d/%m/%Y')}".strip(" ·"),
         "Heebo", 9, 14, gap=6)

    pdf.setStrokeColorRGB(0.08, 0.07, 0.06)
    pdf.setLineWidth(1.5)
    pdf.line(margin, y + 6, width - margin, y + 6)
    y -= 14

    draw(headline, "Heebo-Bold", 19, 25, gap=10)
    for block in _paragraphs(release.body):
        draw(block, "Heebo", 11, 17, gap=7)

    if release.exponential_score is not None:
        draw(f"Exponential score: {release.exponential_score}/100", "Heebo", 9, 14)

    pdf.save()
    return buffer.getvalue()


BUILDERS = {
    "pdf": (feature_pdf, "application/pdf"),
    "docx": (feature_docx,
             "application/vnd.openxmlformats-officedocument."
             "wordprocessingml.document"),
}
