"""The printable kit (spec chapter 4): one A4 PDF, built from the rows every
time, in three parts.

1. **The teacher's guide**: everything, including every solution.
2. **The player pages**: for each group, one page per station with the
   station's story and puzzle and nothing else. One stack per group, so the
   teacher tears the kit into N piles.
3. **The attached printables**: the author's uploaded pages, each behind a
   cover line saying which station it serves and how many copies to make.

The kit is composed first (`compose`) into plain blocks of text, and drawn
second (`Kit.pdf`). The split is what makes the spec's promise testable: a
test reads the player part's text and proves no solution, hint, code or
explanation is in it, without parsing a PDF.

**Bidi, once.** Hebrew is stored logically and ReportLab draws glyphs in the
order it is given, so every line is reordered here with python-bidi (base
direction pinned to right-to-left) and drawn right-aligned, exactly as exo's
download does it (`exo/documents.py` is the reference, not an import; Rule 2).
Lines are wrapped on the logical text, where a word is a word whichever way
the line finally runs, and single line breaks are kept: a six-line program
is six lines on paper too.
"""

import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

from bidi.algorithm import get_display
from django.conf import settings
from django.utils import timezone

FONT_REGULAR = settings.BASE_DIR / "static" / "fonts" / "Heebo_400Regular.ttf"
FONT_BOLD = settings.BASE_DIR / "static" / "fonts" / "Heebo_700Bold.ttf"

MIN_GROUPS, MAX_GROUPS, DEFAULT_GROUPS = 1, 30, 4

TEACHER, PLAYERS, PRINTABLES = "teacher", "players", "printables"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def groups_from(raw, default=DEFAULT_GROUPS):
    """The one question the kit asks, read defensively: junk is the default,
    anything else is clamped to what a classroom can hold."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(MIN_GROUPS, min(MAX_GROUPS, n))


def _lines(text):
    """The text's own lines, blank ones included (they become a gap)."""
    return [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]


def _qty(value):
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value.normalize():f}"


# ------------------------------------------------------------------ blocks


@dataclass
class Block:
    """One thing to draw. `kind` picks the style; `text` is logical Hebrew."""

    kind: str
    text: str = ""
    path: str = ""  # an image file, for kind "image"


@dataclass
class Part:
    key: str
    title: str
    blocks: list = field(default_factory=list)

    def add(self, kind, text="", **extra):
        self.blocks.append(Block(kind, text, **extra))

    def paragraphs(self, text, kind="p"):
        for line in _lines(text):
            self.add(kind if line else "gap", line)

    def text(self):
        """Every string this part prints, for the tests to read."""
        return "\n".join(b.text for b in self.blocks if b.text)


@dataclass
class Kit:
    experience: object
    groups: int
    parts: list

    def part(self, key):
        return next(p for p in self.parts if p.key == key)

    def player_text(self):
        return self.part(PLAYERS).text()

    def pdf(self):
        return render(self)


# ----------------------------------------------------------------- compose


def compose(experience, groups):
    """The kit as blocks, in reading order."""
    groups = groups_from(groups)
    stations = list(experience.stations.prefetch_related("hints", "materials__material", "printables").order_by("order"))
    lock = getattr(experience, "final_lock", None)
    parts = [
        _teacher_part(experience, stations, lock, groups),
        _players_part(experience, stations, groups),
        _printables_part(experience, stations, groups),
    ]
    return Kit(experience, groups, parts)


def _author_name(experience):
    profile = getattr(experience.author, "breakout_profile", None)
    return profile.name if profile else (experience.author.first_name or experience.author.get_username())


def shopping_rows(stations):
    """Every material once, summed over the stations, for one group."""
    rows = {}
    for station in stations:
        for use in station.materials.all():
            row = rows.setdefault(use.material_id, {"material": use.material, "quantity": Decimal(0), "stations": []})
            row["quantity"] += use.quantity
            row["stations"].append(station.name)
    return list(rows.values())


def _teacher_part(exp, stations, lock, groups):
    part = Part(TEACHER, "המדריך למורה")
    part.add("title", exp.title)
    if exp.tagline:
        part.add("lede", exp.tagline)
    part.add("kv", f"ערכה ל-{groups} קבוצות · {exp.grades()} · קבוצות של {exp.group_size_min} עד {exp.group_size_max}")
    part.add("kv", f"{exp.duration_minutes} דקות משחק · {exp.prep_minutes} דקות הכנה · {exp.get_difficulty_display()}")
    part.add("kv", f"מאת {_author_name(exp)} · גרסה {exp.version} · הודפס {timezone.localdate():%d.%m.%Y}")
    part.add("rule")
    part.add("warn", "דף למורה: הפתרונות, הרמזים והקוד נמצאים כאן. לא לחלק לקבוצות.")

    part.add("h2", "הסיפור")
    part.add("note", "מקריאים בקול לכל הכיתה לפני שמתחילים.")
    part.paragraphs(exp.story)

    part.add("h2", "הכנה")
    if exp.teacher_notes:
        part.paragraphs(exp.teacher_notes)
    for station in stations:
        if station.setup_notes:
            part.add("h3", f"תחנה {station.order}: {station.name}")
            part.paragraphs(station.setup_notes)
    if lock and lock.setup_notes:
        part.add("h3", "המנעול הסופי")
        part.paragraphs(lock.setup_notes)

    part.add("h2", f"רשימת קניות ל-{groups} קבוצות")
    rows = shopping_rows(stations)
    if not rows:
        part.add("p", "עוד לא נרשמו חומרים.")
    for row in rows:
        total = row["quantity"] * groups
        part.add("item", f"{row['material'].name}: {_qty(total)} {row['material'].unit} ({_qty(row['quantity'])} לקבוצה; {', '.join(row['stations'])})")
    part.add("note", "הכל נקנה בזול בחנות צרכי משרד או נמצא בבית הספר.")

    part.add("h2", "שרשרת התחנות, עם הפתרונות")
    for station in stations:
        part.add("h3", f"תחנה {station.order}: {station.name}")
        meta = f"{station.get_mechanic_display()} · כ-{station.estimated_minutes} דקות"
        if station.contribution:
            meta += f" · תורמת למנעול: {station.contribution}"
        part.add("kv", meta)
        if station.story_text:
            part.add("h4", "מה הקבוצה קוראת")
            part.paragraphs(station.story_text)
        if station.puzzle_text:
            part.add("h4", "החידה")
            part.paragraphs(station.puzzle_text, kind="mono")
        part.add("h4", "הפתרון")
        part.add("solution", station.solution or "(לא נרשם)")
        if station.solution_explained:
            part.paragraphs(station.solution_explained)
        hints = list(station.hints.all())
        if hints:
            part.add("h4", "רמזים, מהעדין לברור")
            for n, hint in enumerate(hints, 1):
                part.add("item", f"רמז {n}: {hint.text}")
        uses = list(station.materials.all())
        if uses:
            part.add("h4", "חומרים לתחנה, לקבוצה אחת")
            for use in uses:
                note = f" ({use.note})" if use.note else ""
                part.add("item", f"{use.material.name} × {_qty(use.quantity)} {use.material.unit}{note}")

    if lock:
        part.add("h2", "המנעול הסופי")
        if lock.description:
            part.paragraphs(lock.description)
        if lock.code_rule:
            part.add("h4", "איך הקוד מתחבר")
            part.paragraphs(lock.code_rule)
        if lock.final_code:
            part.add("h4", "הקוד")
            part.add("code", lock.final_code)
        if lock.final_message:
            part.add("h4", "ההודעה שבמעטפה")
            part.paragraphs(lock.final_message)

    part.add("rule")
    part.add("note", f"מכאן והלאה: דפי השחקנים, ערימה לכל קבוצה ({groups} ערימות), ואחריהם הדפים המצורפים.")
    return part


def _players_part(exp, stations, groups):
    part = Part(PLAYERS, "דפי השחקנים")
    for g in range(1, groups + 1):
        for station in stations:
            part.add("break")
            part.add("header", exp.title)
            part.add("stamp", f"קבוצה {g} מתוך {groups}")
            part.add("title", f"תחנה {station.order}: {station.name}")
            if station.story_text:
                part.paragraphs(station.story_text, kind="kids")
            if station.puzzle_text:
                part.add("gap")
                part.paragraphs(station.puzzle_text, kind="kidsmono")
    return part


def _printables_part(exp, stations, groups):
    part = Part(PRINTABLES, "דפים מצורפים")
    by_station = {s.pk: s for s in stations}
    printables = list(exp.printables.select_related("station").order_by("station__order", "order", "pk"))
    for p in printables:
        part.add("break")
        part.add("header", exp.title)
        part.add("title", f"דף מצורף: {p.title}")
        station = by_station.get(p.station_id) or p.station
        where = f"לתחנה {station.order}: {station.name}" if station else "לכל החוויה"
        copies = 1 if p.kind == "teacher_page" else groups
        how_many = "עותק אחד" if copies == 1 else f"להדפיס {copies} עותקים, אחד לכל קבוצה"
        part.add("kv", f"{p.get_kind_display()} · {where} · {how_many}")
        name = (p.file.name or "").lower()
        if name.endswith(IMAGE_EXTENSIONS):
            part.add("image", path=p.file.name)
        else:
            part.add("note", "הקובץ הזה אינו תמונה, לכן הוא לא מודפס כאן. מורידים אותו מעמוד החוויה ומדפיסים בנפרד.")
    return part


# ------------------------------------------------------------------ render

_STYLES = {
    # kind: (font, size, leading, gap after)
    "title": ("Heebo-Bold", 22, 28, 6),
    "lede": ("Heebo", 12, 17, 4),
    "kv": ("Heebo", 9.5, 14, 2),
    "header": ("Heebo", 9, 13, 2),
    "stamp": ("Heebo-Bold", 9, 13, 10),
    "h2": ("Heebo-Bold", 15, 22, 4),
    "h3": ("Heebo-Bold", 12.5, 18, 2),
    "h4": ("Heebo-Bold", 10.5, 15, 1),
    "p": ("Heebo", 10.5, 15.5, 0),
    "mono": ("Heebo", 10.5, 15.5, 0),
    "kids": ("Heebo", 13, 19, 0),
    "kidsmono": ("Heebo", 13, 19, 0),
    "item": ("Heebo", 10.5, 15.5, 1),
    "solution": ("Heebo-Bold", 11, 16, 2),
    "code": ("Heebo-Bold", 26, 32, 6),
    "note": ("Heebo", 9.5, 14, 4),
    "warn": ("Heebo-Bold", 10, 15, 6),
}
_BEFORE = {"h2": 14, "h3": 9, "h4": 6, "title": 0, "code": 4}
_INDENT = {"item": 14, "mono": 8, "kidsmono": 8}
_INK = (0.165, 0.141, 0.125)
_RED = (0.72, 0.196, 0.122)
_SOFT = (0.37, 0.32, 0.28)


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "Heebo" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Heebo", str(FONT_REGULAR)))
        pdfmetrics.registerFont(TTFont("Heebo-Bold", str(FONT_BOLD)))


def _visual(text):
    """Logical to visual, for the one renderer that cannot do it itself."""
    return get_display(text or "", base_dir="R")


class _Page:
    """A4 with a margin; knows where the pen is and turns the page itself."""

    def __init__(self, canvas, kit):
        from reportlab.lib.pagesizes import A4

        self.c = canvas
        self.kit = kit
        self.width, self.height = A4
        self.margin = 50
        self.y = None
        self.part = None
        self.number = 0

    @property
    def right(self):
        return self.width - self.margin

    @property
    def line_width(self):
        return self.width - 2 * self.margin

    def begin(self, part):
        if self.number:
            self.c.showPage()
        self.number += 1
        self.part = part
        self.y = self.height - self.margin
        self._frame()

    def _frame(self):
        c = self.c
        title = self.kit.experience.title
        c.setFont("Heebo", 8)
        c.setFillColorRGB(*_SOFT)
        foot = _visual(f"חדרי בריחה מנייר · {title} · עמוד {self.number}")
        c.drawRightString(self.right, self.margin - 22, foot)
        if self.part == TEACHER:
            c.setStrokeColorRGB(*_RED)
            c.setLineWidth(3)
            c.line(self.margin, self.height - self.margin + 18, self.right, self.height - self.margin + 18)
            c.setFillColorRGB(*_RED)
            c.setFont("Heebo-Bold", 8)
            c.drawRightString(self.right, self.height - self.margin + 24, _visual("למורה בלבד"))
        elif self.part == PLAYERS:
            c.setStrokeColorRGB(*_INK)
            c.setLineWidth(2)
            c.rect(self.margin - 16, self.margin - 8, self.line_width + 32, self.height - 2 * self.margin + 20)
        c.setFillColorRGB(*_INK)

    def need(self, height):
        if self.y - height < self.margin:
            self.begin(self.part)

    def wrap(self, text, font, size, width):
        from reportlab.pdfbase import pdfmetrics

        words, lines, current = text.split(" "), [], ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if pdfmetrics.stringWidth(candidate, font, size) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def text(self, block):
        font, size, leading, after = _STYLES[block.kind]
        indent = _INDENT.get(block.kind, 0)
        raw = block.text
        # Leading spaces are indentation the author meant (a program's lines).
        lead = len(raw) - len(raw.lstrip(" "))
        indent += lead * 2.6 * size / 10
        self.y -= _BEFORE.get(block.kind, 0)
        self.c.setFont(font, size)
        color = _RED if block.kind in ("warn", "solution", "code", "stamp") else (_SOFT if block.kind in ("kv", "note", "header") else _INK)
        self.c.setFillColorRGB(*color)
        bullet = block.kind == "item"
        for n, line in enumerate(self.wrap(raw.strip(" "), font, size, self.line_width - indent)):
            self.need(leading)
            self.c.setFont(font, size)
            self.c.setFillColorRGB(*color)
            x = self.right - indent
            if bullet and n == 0:
                self.c.drawRightString(self.right - 2, self.y, "•")
            self.c.drawRightString(x, self.y, _visual(line))
            self.y -= leading
        self.y -= after
        self.c.setFillColorRGB(*_INK)

    def gap(self, height=7):
        self.y -= height

    def rule(self):
        self.need(14)
        self.c.setStrokeColorRGB(*_SOFT)
        self.c.setLineWidth(0.8)
        self.c.line(self.margin, self.y - 4, self.right, self.y - 4)
        self.y -= 14

    def image(self, path):
        from reportlab.lib.utils import ImageReader

        from .models import private_storage

        try:
            with private_storage().open(path, "rb") as handle:
                reader = ImageReader(io.BytesIO(handle.read()))
            iw, ih = reader.getSize()
        except Exception:  # a missing or unreadable file must not break the kit
            self.text(Block("note", "התמונה לא נמצאה; מורידים אותה מעמוד החוויה."))
            return
        # Fill the page (an A4 scan is pixels, not points); keep the shape.
        box_w = self.line_width
        box_h = self.y - self.margin - 10
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        self.c.drawImage(reader, self.right - w, self.y - h, width=w, height=h, preserveAspectRatio=True, mask="auto")
        self.y -= h + 6


def render(kit):
    """The kit as PDF bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas

    _register_fonts()
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"{kit.experience.title} · ערכה ל-{kit.groups} קבוצות")
    c.setAuthor("חדרי בריחה מנייר")
    page = _Page(c, kit)
    for part in kit.parts:
        if not part.blocks:
            continue
        if part.blocks[0].kind != "break":
            page.begin(part.key)  # otherwise the first "break" opens the page
        for block in part.blocks:
            if block.kind == "break":
                page.begin(part.key)
            elif block.kind == "gap":
                page.gap()
            elif block.kind == "rule":
                page.rule()
            elif block.kind == "image":
                page.image(block.path)
            else:
                page.text(block)
    c.showPage()
    c.save()
    return buffer.getvalue()


def filename_for(experience, groups):
    """A name that says what the file is, safe on every platform."""
    stem = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", experience.title or "breakout")
    stem = re.sub(r"\s+", " ", stem).strip()[:60].rstrip(". ")
    return f"{stem or 'breakout'} - ערכה ל-{groups} קבוצות.pdf"


def page_count(pdf_bytes):
    """How many pages a PDF has, read from its own objects (no parser needed)."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
