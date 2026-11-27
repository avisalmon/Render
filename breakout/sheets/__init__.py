"""Generated sheets: the illustrated guide and the cut-out worksheets of a
station, drawn by code (vector, exact, printable at any scale) instead of
uploaded as a picture.

A `Printable` row with a `generator` key points at one of these; the kit draws
it into the group's stack right after the station's page, and the experience
page serves it alone as a PDF. The row is the data (which sheet, for which
station, in which order); the drawing is code, like a template.

Every sheet declares its words through the same Pen it draws with, so the
kit's leak test reads them (toolkit.Pen without a canvas records only), and
every sheet is checked to stay inside the printable area of an A4 page.
"""

import io

from .toolkit import MM, PAGE_H, PAGE_W, Pen, register_fonts


class Sheet:
    """One generated printable. Subclasses set the fields and draw pages."""

    key = ""
    title = ""
    kind = "cut_out"  # or "instructions" (see Printable.KINDS)
    station = 1  # the station's order, for the colour and the header; 0 = the final lock
    pages = 1

    def draw(self, pen, page=0):  # pragma: no cover - abstract
        raise NotImplementedError

    def texts(self):
        pen = Pen()
        for page in range(self.pages):
            self.draw(pen, page)
        return pen.texts

    def text(self):
        return "\n".join(self.texts())

    def fits(self):
        """True when every page stays inside the printers' margin."""
        for page in range(self.pages):
            pen = Pen()
            self.draw(pen, page)
            if not pen.inside():
                return False
        return True

    def bounds(self, page=0):
        pen = Pen()
        self.draw(pen, page)
        return pen.bounds


REGISTRY = {}


def register(cls):
    REGISTRY[cls.key] = cls
    return cls


def get(key):
    cls = REGISTRY.get(key)
    return cls() if cls else None


def keys():
    return list(REGISTRY)


def draw_into(canvas, key):
    """Draw every page of the sheet on the given canvas (one showPage between
    pages, none after the last: the caller owns the page sequence)."""
    sheet = get(key)
    if sheet is None:
        return 0
    for page in range(sheet.pages):
        if page:
            canvas.showPage()
        sheet.draw(Pen(canvas), page)
    return sheet.pages


def render_pdf(key, title=""):
    """The sheet alone, as PDF bytes (the experience page's download)."""
    from reportlab.pdfgen import canvas as pdf_canvas

    register_fonts()
    sheet = get(key)
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=(PAGE_W * MM, PAGE_H * MM))
    c.setTitle(title or (sheet.title if sheet else key))
    c.setAuthor("חדרי בריחה מנייר")
    if sheet is not None:
        draw_into(c, key)
    c.showPage()
    c.save()
    return buffer.getvalue()


# The stations' sheets register themselves on import.
from . import algorithm, bug, lock, memory, network, processor  # noqa: E402,F401
