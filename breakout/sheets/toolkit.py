"""Vector drawing for the generated sheets: an A4 page in millimetres, origin
at the top-left corner, Hebrew drawn right-to-left through python-bidi, and a
bounds tracker so a test can prove every mark stays inside the printable area.

Everything a sheet draws goes through a `Pen`. A Pen without a canvas records
(texts and bounds) and draws nothing, which is how a sheet's words reach the
kit's leak test and how geometry is checked without a PDF.

Line language, the same on every sheet (the legend repeats it):
- cut: solid dark line, with a little scissors mark;
- fold: dashed line;
- glue / tape: light grey area with its word inside;
- the station's own colour tints headers, step numbers and illustrations.
"""

import math

from bidi.algorithm import get_display
from django.conf import settings

MM = 72 / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
SAFE = 10.0  # printers' margin, mm

FONT_REGULAR = settings.BASE_DIR / "static" / "fonts" / "Heebo_400Regular.ttf"
FONT_BOLD = settings.BASE_DIR / "static" / "fonts" / "Heebo_700Bold.ttf"

INK = (0.16, 0.14, 0.13)
SOFT = (0.40, 0.36, 0.33)
PAPER = (1, 1, 1)
GLUE = (0.88, 0.88, 0.86)
CUT = (0.10, 0.10, 0.10)
FOLD = (0.45, 0.45, 0.45)
WHITE = (1, 1, 1)

# One colour per station, as (main, light tint).
PALETTE = {
    1: ((0.16, 0.44, 0.76), (0.86, 0.92, 0.98)),  # blue
    2: ((0.90, 0.52, 0.12), (0.99, 0.92, 0.82)),  # orange
    3: ((0.80, 0.22, 0.30), (0.98, 0.87, 0.89)),  # red
    4: ((0.18, 0.60, 0.36), (0.86, 0.95, 0.88)),  # green
    5: ((0.50, 0.30, 0.70), (0.92, 0.88, 0.97)),  # purple
    0: ((0.78, 0.60, 0.10), (0.99, 0.95, 0.80)),  # gold, the lock
}


def register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "Heebo" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Heebo", str(FONT_REGULAR)))
        pdfmetrics.registerFont(TTFont("Heebo-Bold", str(FONT_BOLD)))


def has_rtl(text):
    return any("֐" <= ch <= "ࣿ" for ch in text or "")


def visual(text):
    """Logical Hebrew to the visual order ReportLab needs, base direction RTL.
    A string without a Hebrew letter (digits, a bit pattern "0 1 1 0 0") is
    left exactly as written: bidi would lay its number runs right to left."""
    if not has_rtl(text):
        return text or ""
    return get_display(text, base_dir="R")


def string_width(text, size, bold=False):
    from reportlab.pdfbase import pdfmetrics

    register_fonts()
    return pdfmetrics.stringWidth(text, "Heebo-Bold" if bold else "Heebo", size) / MM


class Pen:
    """Draws in millimetres from the top-left; records what it draws."""

    def __init__(self, canvas=None):
        self.c = canvas
        self.texts = []
        self.bounds = [math.inf, math.inf, -math.inf, -math.inf]
        if canvas is not None:
            register_fonts()

    # ----------------------------------------------------------- recording

    def _touch(self, x, y, pad=0.0):
        b = self.bounds
        b[0], b[1] = min(b[0], x - pad), min(b[1], y - pad)
        b[2], b[3] = max(b[2], x + pad), max(b[3], y + pad)

    def inside(self, margin=SAFE - 2.5):
        """True when every mark is on the page, inside the printers' margin."""
        x0, y0, x1, y1 = self.bounds
        if x0 is math.inf:
            return True
        return x0 >= margin and y0 >= margin and x1 <= PAGE_W - margin and y1 <= PAGE_H - margin

    def _pt(self, x, y):
        return x * MM, (PAGE_H - y) * MM

    def _color(self, rgb, stroke=False):
        if self.c is None:
            return
        if stroke:
            self.c.setStrokeColorRGB(*rgb)
        else:
            self.c.setFillColorRGB(*rgb)

    # ------------------------------------------------------------- shapes

    def line(self, x1, y1, x2, y2, width=0.4, color=INK, dash=None):
        self._touch(x1, y1, width / 2)
        self._touch(x2, y2, width / 2)
        if self.c is None:
            return
        self._color(color, stroke=True)
        self.c.setLineWidth(width * MM)
        self.c.setDash(*(d * MM for d in dash)) if dash else self.c.setDash()
        self.c.setLineCap(1)
        self.c.line(*self._pt(x1, y1), *self._pt(x2, y2))
        self.c.setDash()

    def polyline(self, points, width=0.4, color=INK, dash=None):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            self.line(x1, y1, x2, y2, width, color, dash)

    def rect(self, x, y, w, h, fill=None, stroke=INK, width=0.4, dash=None, radius=0.0):
        self._touch(x, y, width / 2)
        self._touch(x + w, y + h, width / 2)
        if self.c is None:
            return
        if fill is not None:
            self._color(fill)
        if stroke is not None:
            self._color(stroke, stroke=True)
            self.c.setLineWidth(width * MM)
            self.c.setDash(*(d * MM for d in dash)) if dash else self.c.setDash()
        px, py = self._pt(x, y + h)
        if radius:
            self.c.roundRect(px, py, w * MM, h * MM, radius * MM, stroke=stroke is not None, fill=fill is not None)
        else:
            self.c.rect(px, py, w * MM, h * MM, stroke=stroke is not None, fill=fill is not None)
        self.c.setDash()

    def circle(self, cx, cy, r, fill=None, stroke=INK, width=0.4, dash=None):
        self._touch(cx - r, cy - r, width / 2)
        self._touch(cx + r, cy + r, width / 2)
        if self.c is None:
            return
        if fill is not None:
            self._color(fill)
        if stroke is not None:
            self._color(stroke, stroke=True)
            self.c.setLineWidth(width * MM)
            self.c.setDash(*(d * MM for d in dash)) if dash else self.c.setDash()
        px, py = self._pt(cx, cy)
        self.c.circle(px, py, r * MM, stroke=stroke is not None, fill=fill is not None)
        self.c.setDash()

    def arc(self, cx, cy, r, start_deg, extent_deg, width=0.4, color=INK, dash=None):
        """An arc; angles are compass-like from the top, clockwise, on paper."""
        for a in (start_deg, start_deg + extent_deg):
            self._touch(*polar(cx, cy, r, a), width / 2)
        if self.c is None:
            return
        self._color(color, stroke=True)
        self.c.setLineWidth(width * MM)
        self.c.setDash(*(d * MM for d in dash)) if dash else self.c.setDash()
        px, py = self._pt(cx, cy)
        # ReportLab arcs run counter-clockwise from the x axis; convert.
        rl_start = 90 - start_deg - extent_deg
        self.c.arc(px - r * MM, py - r * MM, px + r * MM, py + r * MM, rl_start, extent_deg)
        self.c.setDash()

    def polygon(self, points, fill=None, stroke=INK, width=0.4, dash=None):
        for x, y in points:
            self._touch(x, y, width / 2)
        if self.c is None:
            return
        if fill is not None:
            self._color(fill)
        if stroke is not None:
            self._color(stroke, stroke=True)
            self.c.setLineWidth(width * MM)
            self.c.setDash(*(d * MM for d in dash)) if dash else self.c.setDash()
        path = self.c.beginPath()
        path.moveTo(*self._pt(*points[0]))
        for p in points[1:]:
            path.lineTo(*self._pt(*p))
        path.close()
        self.c.drawPath(path, stroke=stroke is not None, fill=fill is not None)
        self.c.setDash()

    def wedge(self, cx, cy, r, start_deg, extent_deg, fill=None, stroke=INK, width=0.4):
        """A pie slice, compass angles clockwise from the top."""
        pts = [(cx, cy)]
        steps = max(2, int(abs(extent_deg) / 6) + 1)
        for i in range(steps + 1):
            pts.append(polar(cx, cy, r, start_deg + extent_deg * i / steps))
        self.polygon(pts, fill=fill, stroke=stroke, width=width)

    # --------------------------------------------------------------- text

    def text(self, x, y, s, size=10, bold=False, color=INK, align="right", angle=0):
        """One line of logical Hebrew (or digits) with its right edge (default),
        centre or left edge at x, baseline at y, in millimetres."""
        if not s:
            return
        self.texts.append(s)
        w = string_width(s, size, bold)
        h = size / MM
        if align == "right":
            x0 = x - w
        elif align == "center":
            x0 = x - w / 2
        else:
            x0 = x
        if angle == 0:
            self._touch(x0, y - h * 0.75)
            self._touch(x0 + w, y + h * 0.25)
        else:
            self._touch(x, y, max(w, h))
        if self.c is None:
            return
        self.c.setFont("Heebo-Bold" if bold else "Heebo", size)
        self._color(color)
        if angle:
            self.c.saveState()
            self.c.translate(*self._pt(x, y))
            self.c.rotate(angle)
            self.c.drawString(-w * MM if align == "right" else (-w / 2 * MM if align == "center" else 0), 0, visual(s))
            self.c.restoreState()
        else:
            self.c.drawString(x0 * MM, self._pt(0, y)[1], visual(s))

    def wrap(self, s, size, width, bold=False):
        words, lines, current = s.split(" "), [], ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if string_width(candidate, size, bold) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def para(self, x, y, width, s, size=10, leading=None, bold=False, color=INK, align="right"):
        """A paragraph of logical Hebrew, right edge at x (right-aligned),
        wrapped to `width` mm. Returns the y under the last line."""
        leading = leading or size * 1.35 / MM
        for raw in (s or "").split("\n"):
            if not raw.strip():
                y += leading * 0.6
                continue
            for line in self.wrap(raw, size, width, bold):
                self.text(x if align == "right" else (x - width / 2 if align == "center" else x - width), y, line, size, bold, color, align)
                y += leading
        return y

    # ------------------------------------------------------- the language

    def cut(self, points, closed=False):
        pts = list(points) + ([points[0]] if closed else [])
        self.polyline(pts, width=0.5, color=CUT)

    def cut_rect(self, x, y, w, h, radius=0.0):
        self.rect(x, y, w, h, fill=None, stroke=CUT, width=0.5, radius=radius)

    def cut_circle(self, cx, cy, r):
        self.circle(cx, cy, r, fill=None, stroke=CUT, width=0.5)

    def fold(self, x1, y1, x2, y2):
        self.line(x1, y1, x2, y2, width=0.35, color=FOLD, dash=(1.6, 1.2))

    def glue(self, x, y, w, h, label="דבק", size=6.5, angle=0):
        self.rect(x, y, w, h, fill=GLUE, stroke=FOLD, width=0.25, dash=(0.8, 0.8))
        if label:
            if angle:
                self.text(x + w / 2, y + h / 2, label, size, color=SOFT, align="center", angle=angle)
            else:
                self.text(x + w / 2, y + h / 2 + size / MM * 0.35, label, size, color=SOFT, align="center")

    def scissors(self, x, y, size=5.0, angle=0.0, color=CUT):
        """A small scissors glyph: two rings and two blades, centred at x, y,
        pointing along `angle` (compass degrees, 0 = up)."""
        s = size / 2
        a = math.radians(angle)

        def p(dx, dy):  # local coords: dy forward along the blades
            return (x + dx * math.cos(a) + dy * math.sin(a), y - dx * math.sin(a) + dy * math.cos(a))

        self.circle(*p(-s * 0.45, -s * 0.55), s * 0.38, fill=None, stroke=color, width=0.35)
        self.circle(*p(s * 0.45, -s * 0.55), s * 0.38, fill=None, stroke=color, width=0.35)
        self.line(*p(-s * 0.3, -s * 0.2), *p(s * 0.35, s * 1.0), width=0.5, color=color)
        self.line(*p(s * 0.3, -s * 0.2), *p(-s * 0.35, s * 1.0), width=0.5, color=color)

    def arrow(self, x1, y1, x2, y2, width=0.5, color=INK, head=2.2):
        self.line(x1, y1, x2, y2, width, color)
        a = math.atan2(y2 - y1, x2 - x1)
        for side in (-1, 1):
            b = a + math.pi + side * math.radians(28)
            self.line(x2, y2, x2 + head * math.cos(b), y2 + head * math.sin(b), width, color)

    def dot(self, cx, cy, r=1.6, color=INK):
        self.circle(cx, cy, r, fill=color, stroke=None)

    # ------------------------------------------------------- page furniture

    def header(self, station, name, kind_label, color_key=None):
        """The coloured band on top: station number in a disc, the name, and
        what this sheet is (a guide or a worksheet)."""
        main, light = PALETTE[color_key if color_key is not None else station]
        self.rect(SAFE, SAFE, PAGE_W - 2 * SAFE, 20, fill=main, stroke=None, radius=2.5)
        right = PAGE_W - SAFE
        self.circle(right - 11, SAFE + 10, 7.2, fill=WHITE, stroke=None)
        if station:
            self.text(right - 11, SAFE + 13.2, str(station), 15, bold=True, color=main, align="center")
        else:  # the final lock: a little key
            self.circle(right - 13.5, SAFE + 10, 2.2, fill=None, stroke=main, width=1.0)
            self.rect(right - 11.5, SAFE + 9.3, 6, 1.4, fill=main, stroke=None)
            self.rect(right - 7.5, SAFE + 9.3, 1.2, 3, fill=main, stroke=None)
            self.rect(right - 9.5, SAFE + 9.3, 1.2, 2.4, fill=main, stroke=None)
        self.text(right - 22, SAFE + 9.2, name, 15, bold=True, color=WHITE)
        self.text(right - 22, SAFE + 16.4, kind_label, 8.5, color=WHITE)
        self.text(SAFE + 4, SAFE + 16.4, "חדרי בריחה מנייר", 7.5, color=WHITE, align="left")
        return SAFE + 24

    def legend(self, y, with_glue=True):
        """The line language, in one row, on the right."""
        right = PAGE_W - SAFE
        x = right
        self.line(x - 10, y, x, y, width=0.5, color=CUT)
        self.scissors(x - 5, y - 2.6, 4, angle=90)
        self.text(x - 12, y + 1.2, "גוזרים", 7.5, color=SOFT)
        x -= 30
        self.fold(x - 10, y, x, y)
        self.text(x - 12, y + 1.2, "מקפלים", 7.5, color=SOFT)
        if with_glue:
            x -= 30
            self.glue(x - 10, y - 2.2, 10, 4.4, label="")
            self.text(x - 12, y + 1.2, "דבק או סרט הדבקה", 7.5, color=SOFT)
        return y + 6

    def footer(self, text):
        self.text(PAGE_W - SAFE, PAGE_H - SAFE + 0.5, text, 7, color=SOFT)

    def step(self, n, x_right, y, width, title, body="", color_key=1, size=9.5, picture=None, picture_w=26.0):
        """A numbered step: a coloured disc with the number, a bold first line,
        an optional body, and on the left a little picture of the action
        (`picture(pen, x, y, w, h)` draws into that box). Returns the y under it."""
        main, light = PALETTE[color_key]
        box_h = 20.0 if picture else 0.0
        text_w = width - 11 - (picture_w + 6 if picture else 0)
        self.circle(x_right - 4, y + 1.2, 4, fill=main, stroke=None)
        self.text(x_right - 4, y + 3.0, str(n), 9.5, bold=True, color=WHITE, align="center")
        text_right = x_right - 11
        y_text = y + 3.6
        y_text = self.para(text_right, y_text, text_w, title, size, bold=True)
        if body:
            y_text = self.para(text_right, y_text - 0.6, text_w, body, size - 0.5, color=INK)
        if picture:
            px = x_right - width
            self.rect(px, y - 2, picture_w, box_h, fill=light, stroke=None, radius=2)
            picture(self, px, y - 2, picture_w, box_h)
        return max(y_text, y + box_h) + 2.5

    def ring_sector(self, cx, cy, r0, r1, start_deg, extent_deg, fill=None, stroke=INK, width=0.4):
        """The part of a ring between two radii and two compass angles."""
        steps = max(2, int(abs(extent_deg) / 6) + 1)
        outer = [polar(cx, cy, r1, start_deg + extent_deg * i / steps) for i in range(steps + 1)]
        inner = [polar(cx, cy, r0, start_deg + extent_deg * i / steps) for i in range(steps, -1, -1)]
        self.polygon(outer + inner, fill=fill, stroke=stroke, width=width)

    def box(self, x, y, w, h, color_key=1, title="", radius=2.0):
        main, light = PALETTE[color_key]
        self.rect(x, y, w, h, fill=light, stroke=None, radius=radius)
        if title:
            self.text(x + w - 4, y + 6.5, title, 9.5, bold=True, color=main)
            return y + 10
        return y + 3


def polar(cx, cy, r, deg):
    """A point on a circle, compass-style: 0 at the top, clockwise, on paper."""
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)
