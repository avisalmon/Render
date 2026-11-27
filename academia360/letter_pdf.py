"""The letter as an A4 PDF (spec 4.7, backlog E.5), drawn from
`letters.compose`: header, date, addressee, subject, the sections, the
closing, and the pilot line on every page.

Bidi once: Hebrew is stored logically and ReportLab draws glyphs in the
order it is given, so every line is wrapped on the logical text and then
reordered with python-bidi (base direction right-to-left) and drawn
right-aligned. The breakout kit does the same (a reference, not an import;
rule 2). Fonts: Heebo from static/fonts, registered once per process.
"""

import io

from bidi.algorithm import get_display
from django.conf import settings

FONT_REGULAR = settings.BASE_DIR / "static" / "fonts" / "Heebo_400Regular.ttf"
FONT_BOLD = settings.BASE_DIR / "static" / "fonts" / "Heebo_700Bold.ttf"

PILOT = "אתר פיילוט שנבנה על ידי אבי סלמון · אינו אתר רשמי של הממשלה, מל״ג/ות״ת, אינטל או כל מוסד"

# kind: (font, size, leading, space after)
_STYLES = {
    "header": ("Heebo-Bold", 13, 18, 2),
    "date": ("Heebo", 10.5, 15, 14),
    "to": ("Heebo", 11.5, 16, 0),
    "subject": ("Heebo-Bold", 12.5, 18, 10),
    "h": ("Heebo-Bold", 12, 17, 2),
    "p": ("Heebo", 11, 16.5, 0),
    "gap": ("Heebo", 6, 8, 0),
    "sign": ("Heebo", 11.5, 16, 0),
}
_BEFORE = {"h": 10, "subject": 12, "sign": 14, "to": 0}
_INK = (0.11, 0.11, 0.12)
_SOFT = (0.42, 0.44, 0.44)
_TEAL = (0.12, 0.45, 0.49)


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "Heebo" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Heebo", str(FONT_REGULAR)))
        pdfmetrics.registerFont(TTFont("Heebo-Bold", str(FONT_BOLD)))


def _visual(text):
    return get_display(text or "", base_dir="R")


class _Page:
    def __init__(self, canvas):
        from reportlab.lib.pagesizes import A4

        self.c = canvas
        self.width, self.height = A4
        self.margin = 56
        self.y = None
        self.number = 0

    @property
    def right(self):
        return self.width - self.margin

    @property
    def line_width(self):
        return self.width - 2 * self.margin

    def begin(self):
        if self.number:
            self.c.showPage()
        self.number += 1
        self.y = self.height - self.margin
        c = self.c
        c.setStrokeColorRGB(*_TEAL)
        c.setLineWidth(3)
        c.line(self.margin, self.height - self.margin + 16, self.right, self.height - self.margin + 16)
        c.setFillColorRGB(*_SOFT)
        c.setFont("Heebo", 8)
        c.drawRightString(self.right, self.margin - 24, _visual(PILOT))
        c.drawString(self.margin, self.margin - 24, str(self.number))
        c.setFillColorRGB(*_INK)

    def need(self, height):
        if self.y - height < self.margin:
            self.begin()

    def wrap(self, text, font, size, width):
        from reportlab.pdfbase import pdfmetrics

        words = text.split(" ")
        lines, current = [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font, size) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def block(self, kind, text):
        font, size, leading, after = _STYLES[kind]
        self.y -= _BEFORE.get(kind, 0)
        if kind == "gap" or not text:
            self.y -= leading
            return
        bullet = text.startswith("- ")
        body = text[2:] if bullet else text
        indent = 14 if bullet else 0
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*(_SOFT if kind in ("date", "header") else _INK))
        for n, line in enumerate(self.wrap(body, font, size, self.line_width - indent)):
            self.need(leading)
            if bullet and n == 0:
                self.c.drawRightString(self.right - 2, self.y, "•")
            self.c.drawRightString(self.right - indent, self.y, _visual(line))
            self.y -= leading
        self.y -= after
        self.c.setFillColorRGB(*_INK)


def render_blocks(blocks):
    """The PDF bytes of composed blocks."""
    from reportlab.pdfgen import canvas as rl_canvas

    _register_fonts()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(595.27, 841.89))
    c.setTitle("Academia 360 letter")
    page = _Page(c)
    page.begin()
    for kind, text in blocks:
        page.block(kind, text)
    c.save()
    return buf.getvalue()


def render(letter):
    from . import letters

    return render_blocks(letters.compose(letter))
