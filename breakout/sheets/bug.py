"""Station 3, the bug: the program as six flowchart pieces that only fit
together one way (a tab under each piece, a notch over the next, a matching
shape on both), ten number chips to walk through the loop by hand, and a
trace table. The loop's return arrow is printed in pieces along the left
margin and only joins up when the chain is assembled right.

The pieces reproduce the program as written, bug included. Which line is
wrong is on the teacher's page only.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_W, PALETTE, SAFE, SOFT, WHITE

MAIN, LIGHT = PALETTE[3]
PIECE_W, PIECE_H, TAB_W, TAB_H = 84.0, 26.0, 14.0, 5.0

# (line number, shape, text, mark under it)
LINES = [
    (1, "round", "סכום = 0", "circle"),
    (2, "hex", "עבור כל מספר מ-1 עד 10:", "square"),
    (3, "diamond", "המספר מתחלק ב-2 בלי שארית?", "triangle"),
    (4, "rect", "סכום = סכום + 1", "diamond"),
    (5, "para", 'הדפס "סכום הזוגיים הוא:"', "pentagon"),
    (6, "para", "הדפס סכום", ""),
]
PRINT_ORDER = [4, 1, 5, 3, 6, 2]  # shuffled on the sheet, so assembling is a task


def mark(pen, cx, cy, kind, r=2.2, color=INK):
    if kind == "circle":
        pen.circle(cx, cy, r, fill=color, stroke=None)
    elif kind == "square":
        pen.rect(cx - r, cy - r, 2 * r, 2 * r, fill=color, stroke=None)
    elif kind == "triangle":
        pen.polygon([(cx, cy - r * 1.1), (cx + r * 1.1, cy + r * 0.9), (cx - r * 1.1, cy + r * 0.9)], fill=color, stroke=None)
    elif kind == "diamond":
        pen.polygon([(cx, cy - r * 1.2), (cx + r * 1.2, cy), (cx, cy + r * 1.2), (cx - r * 1.2, cy)], fill=color, stroke=None)
    elif kind == "pentagon":
        import math

        pts = [(cx + r * 1.2 * math.sin(math.radians(a)), cy - r * 1.2 * math.cos(math.radians(a))) for a in range(0, 360, 72)]
        pen.polygon(pts, fill=color, stroke=None)


def piece_outline(x, y, line_no):
    """The cut outline: a box with a notch on top (except the first piece)
    and a tab underneath (except the last), both trapezoids, same size."""
    w, h, tw, th = PIECE_W, PIECE_H, TAB_W, TAB_H
    cx = x + w / 2
    pts = [(x, y)]
    if line_no > 1:  # notch in the top edge
        pts += [(cx - tw / 2, y), (cx - tw / 2 + 1.5, y + th), (cx + tw / 2 - 1.5, y + th), (cx + tw / 2, y)]
    pts += [(x + w, y), (x + w, y + h)]
    if line_no < 6:  # tab under the bottom edge
        pts += [(cx + tw / 2, y + h), (cx + tw / 2 - 1.5, y + h + th), (cx - tw / 2 + 1.5, y + h + th), (cx - tw / 2, y + h)]
    pts += [(x, y + h)]
    return pts


def draw_piece(pen, x, y, line_no):
    _n, shape, text, under_mark = LINES[line_no - 1]
    pen.polygon(piece_outline(x, y, line_no), fill=WHITE, stroke=CUT, width=0.5)
    cx, cy = x + PIECE_W / 2 + 6, y + PIECE_H / 2
    # The flowchart symbol with the line's text inside.
    sw, sh = 56.0, 16.0
    if shape == "round":
        pen.rect(cx - sw / 2, cy - sh / 2, sw, sh, fill=LIGHT, stroke=MAIN, width=0.5, radius=8)
    elif shape == "rect":
        pen.rect(cx - sw / 2, cy - sh / 2, sw, sh, fill=LIGHT, stroke=MAIN, width=0.5)
    elif shape == "hex":
        pen.polygon([(cx - sw / 2, cy), (cx - sw / 2 + 5, cy - sh / 2), (cx + sw / 2 - 5, cy - sh / 2), (cx + sw / 2, cy), (cx + sw / 2 - 5, cy + sh / 2), (cx - sw / 2 + 5, cy + sh / 2)], fill=LIGHT, stroke=MAIN, width=0.5)
    elif shape == "diamond":
        pen.polygon([(cx - sw / 2 - 4, cy), (cx, cy - sh / 2 - 3), (cx + sw / 2 + 4, cy), (cx, cy + sh / 2 + 3)], fill=LIGHT, stroke=MAIN, width=0.5)
    elif shape == "para":
        pen.polygon([(cx - sw / 2 + 4, cy - sh / 2), (cx + sw / 2 + 4, cy - sh / 2), (cx + sw / 2 - 4, cy + sh / 2), (cx - sw / 2 - 4, cy + sh / 2)], fill=LIGHT, stroke=MAIN, width=0.5)
    pen.text(cx, cy + 2.6, text, 8.2, bold=True, color=INK, align="center")
    # The line number, big, in the right margin.
    pen.text(x + PIECE_W - 3, cy + 3.5, str(line_no), 12, bold=True, color=MAIN)
    # Marks: this piece's mark on its tab, the previous piece's mark by its notch.
    if under_mark:
        mark(pen, x + PIECE_W / 2, y + PIECE_H + 2.6, under_mark, 1.6)
    if line_no > 1:
        prev_mark = LINES[line_no - 2][3]
        mark(pen, x + PIECE_W / 2 + TAB_W / 2 + 4, y + 3.2, prev_mark, 1.6, color=SOFT)
    # The loop's return arrow, in pieces along the left margin.
    lx = x + 5
    if line_no == 2:
        pen.line(lx, y + PIECE_H, lx, cy, width=0.6, color=MAIN)
        pen.arrow(lx, cy, cx - sw / 2 - 1, cy, width=0.6, color=MAIN)
    elif line_no == 3:
        pen.line(lx, y, lx, y + PIECE_H, width=0.6, color=MAIN)
        pen.arrow(cx, cy + sh / 2 + 3, cx, y + PIECE_H, width=0.5, color=INK)
        pen.text(cx + 2, y + PIECE_H - 1.2, "כן", 6, color=SOFT, align="left")
        pen.text(x + 12, cy - 2, "לא", 6, color=SOFT, align="left")
        pen.arrow(cx - sw / 2 - 4, cy, lx + 0.5, cy, width=0.5, color=INK)
    elif line_no == 4:
        pen.line(lx, y, lx, cy, width=0.6, color=MAIN)
        pen.arrow(cx - sw / 2, cy, lx + 0.5, cy, width=0.6, color=MAIN)
        pen.text(x + 8, y + PIECE_H - 2, "חזרה למספר הבא", 5.5, color=MAIN, align="left")
    if line_no in (1, 2, 5):
        pen.arrow(cx, cy + sh / 2, cx, y + PIECE_H, width=0.5, color=INK)
    if line_no == 2:
        pen.text(cx + 2, y + PIECE_H - 1.5, "כשנגמרו המספרים: למטה", 5.2, color=SOFT, align="left")


@register
class BugPieces(Sheet):
    key = "bug_pieces"
    title = "חלקי התוכנית, אסימוני המספרים וטבלת המעקב"
    kind = "cut_out"
    station = 3

    def draw(self, pen, page=0):
        y0 = pen.header(3, "הבאג", "דף עבודה: התוכנית בחלקים")
        y0 = pen.legend(y0, with_glue=False)
        pitch = PIECE_H + TAB_H + 5
        for i, line_no in enumerate(PRINT_ORDER):
            col, row = i % 2, i // 2
            x = 14 + col * (PIECE_W + 10)
            draw_piece(pen, x, y0 + 2 + row * pitch, line_no)
        y = y0 + 2 + 3 * pitch + 4
        # Ten number chips.
        pen.text(PAGE_W - SAFE, y + 4, "אסימוני המספרים: אחד אחד דרך הלולאה", 8.5, bold=True, color=MAIN)
        y += 8
        for n in range(1, 11):
            cx = PAGE_W - SAFE - 8 - (n - 1) * 18
            pen.cut_circle(cx, y + 8, 7.5)
            pen.text(cx, y + 11.5, str(n), 12, bold=True, color=INK, align="center")
        y += 22
        self.trace_table(pen, y)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 3 · דף עבודה")

    def trace_table(self, pen, y):
        right = PAGE_W - SAFE
        pen.text(right, y + 4, "טבלת מעקב: מה קורה לסכום אחרי כל מספר", 8.5, bold=True, color=MAIN)
        y += 8
        heads = ["מספר", "זוגי?", "סכום אחרי"]
        widths = [24, 24, 40]
        row_h = 7.4
        x = right
        cells = []
        for w in widths:
            cells.append((x - w, w))
            x -= w
        for r in range(11):
            yy = y + r * row_h
            for (cx, w) in cells:
                pen.rect(cx, yy, w, row_h, fill=LIGHT if r == 0 else None, stroke=SOFT, width=0.3)
            if r == 0:
                for (cx, w), head in zip(cells, heads):
                    pen.text(cx + w / 2, yy + 5.2, head, 7.5, bold=True, align="center")
            else:
                pen.text(cells[0][0] + cells[0][1] / 2, yy + 5.4, str(r), 8.5, align="center")
        # To the left of the table: what the program should do, in words.
        left_right = right - sum(widths) - 8
        pen.box(SAFE, y, left_right - SAFE, 11 * row_h, color_key=3, title="מה ביט אמור לעשות")
        pen.para(left_right - 4, y + 16, left_right - SAFE - 8,
                 "לחבר את כל המספרים הזוגיים מ-1 עד 10. התשובה הנכונה היא 30, אבל ביט מדפיס 5.\n"
                 "מרכיבים את התוכנית, ואז מעבירים אסימון אחרי אסימון דרך הלולאה: בכל מספר שואלים את שאלת המעוין, עושים מה שכתוב, ורושמים את הסכום. איפה הוא מתרחק מ-30? מספר השורה הזאת הוא מה שמחפשים.", 7.6)


# ------------------------------------------------------------------ guide


def pic_cut_pieces(pen, x, y, w, h):
    for i in range(2):
        yy = y + 3 + i * 8
        pen.polygon([(x + 3, yy), (x + 20, yy), (x + 20, yy + 5), (x + 13.5, yy + 5), (x + 13, yy + 6.5), (x + 10, yy + 6.5), (x + 9.5, yy + 5), (x + 3, yy + 5)], fill=WHITE, stroke=CUT, width=0.4)
    pen.scissors(x + 22, y + 12, 4, angle=0)


def pic_assemble(pen, x, y, w, h):
    for i in range(3):
        yy = y + 2 + i * 5.6
        pen.rect(x + 5, yy, 14, 4.6, fill=WHITE, stroke=CUT, width=0.4)
        if i < 2:
            pen.polygon([(x + 10, yy + 4.6), (x + 14, yy + 4.6), (x + 13.5, yy + 5.8), (x + 10.5, yy + 5.8)], fill=LIGHT, stroke=None)
    pen.line(x + 3, y + 7, x + 3, y + 16, width=0.5, color=MAIN)
    pen.arrow(x + 3, y + 7, x + 5, y + 7, width=0.5, color=MAIN)


def pic_chips(pen, x, y, w, h):
    for i in range(3):
        pen.circle(x + 6 + i * 6.5, y + 10, 3, fill=WHITE, stroke=CUT, width=0.4)
        pen.text(x + 6 + i * 6.5, y + 11.3, str(i + 1), 4, bold=True, align="center")
    pen.arrow(x + 12, y + 15, x + 12, y + 18.5, width=0.4, color=MAIN)


def pic_table(pen, x, y, w, h):
    for r in range(4):
        pen.rect(x + 4, y + 3 + r * 4, 18, 4, fill=LIGHT if r == 0 else WHITE, stroke=SOFT, width=0.3)
        pen.line(x + 10, y + 3 + r * 4, x + 10, y + 7 + r * 4, width=0.3, color=SOFT)
    pen.text(x + 7, y + 10, "1", 3.5, align="center")
    pen.text(x + 16, y + 10, "0", 3.5, align="center")


@register
class BugGuide(Sheet):
    key = "bug_guide"
    title = "דף הדרכה: הבאג"
    kind = "instructions"
    station = 3

    def draw(self, pen, page=0):
        y = pen.header(3, "הבאג", "דף הדרכה: מרכיבים את התוכנית ומריצים אותה ביד")
        right = PAGE_W - SAFE
        y = pen.legend(y, with_glue=False)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=3, title="מה בונים")
        pen.para(right - 4, y + 15, 104, "את התוכנית של ביט כתרשים זרימה: שישה חלקים שמתחברים זה לזה כמו פאזל, לשונית לתוך חריץ, צורה מול אותה צורה. כשהשרשרת מורכבת נכון, חץ החזרה של הלולאה בצד שמאל מתחבר לקו אחד רצוף. אחר כך מריצים את התוכנית ביד, עם אסימוני המספרים.", 9.2)
        self.picture(pen, SAFE + 8, y + 8)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את ששת החלקים, כולל הלשוניות והחריצים.", "הלשונית בתחתית חלק אחד נכנסת לחריץ שבראש החלק הבא. הצורה הקטנה ליד הלשונית צריכה להתאים לצורה שליד החריץ.", color_key=3, size=10.5, picture=pic_cut_pieces)
        y = pen.step(2, right, y, col_w, "מרכיבים את השרשרת מלמעלה למטה.", "התחלה למעלה, הדפסה למטה. סימן שהצלחתם: הקו האדום בשוליים השמאליים נהיה חץ אחד רצוף שחוזר למעלה, ומספרי השורות עולים מ-1 עד 6.", color_key=3, size=10.5, picture=pic_assemble)
        y = pen.step(3, right, y, col_w, "גוזרים את עשרת אסימוני המספרים.", "זה מה שהתוכנית מקבלת: המספרים 1 עד 10, אחד אחד.", color_key=3, size=10.5, picture=pic_chips)
        y = pen.step(4, right, y, col_w, "מריצים ביד: אסימון אחרי אסימון דרך הלולאה.", "מניחים את האסימון על החלק של הלולאה, שואלים את שאלת המעוין, הולכים בחץ המתאים, עושים מה שכתוב, וממלאים שורה בטבלת המעקב. ואז האסימון הבא.", color_key=3, size=10.5, picture=pic_table)
        y += 1
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 52, color_key=3, title="איך מוצאים את הבאג")
        pen.para(right - 4, y + 15, PAGE_W - 2 * SAFE - 8,
                 "ביט אמור להדפיס 30, שהוא 2 + 4 + 6 + 8 + 10. במקום זה הוא מדפיס 5. בטבלת המעקב רואים מה הסכום אחרי כל מספר. באיזו שורה בתוכנית קורה משהו אחר ממה שצריך לקרות? מספר השורה הזאת הוא מה שהתחנה נותנת.\n"
                 "טיפ של מהנדסים: לא מנחשים. עוקבים אחרי הערכים שורה אחרי שורה, כמו שמחשב עושה, ומשווים למה שהיה צריך להיות.", 9.2)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 3 · דף הדרכה")

    def picture(self, pen, x, y):
        shapes = ["round", "hex", "diamond", "rect", "para"]
        for i, shape in enumerate(shapes):
            yy = y + i * 6.2
            cx = x + 40
            if shape == "diamond":
                pen.polygon([(cx - 14, yy + 2.5), (cx, yy), (cx + 14, yy + 2.5), (cx, yy + 5)], fill=LIGHT, stroke=MAIN, width=0.3)
            elif shape == "hex":
                pen.polygon([(cx - 14, yy + 2.5), (cx - 12, yy), (cx + 12, yy), (cx + 14, yy + 2.5), (cx + 12, yy + 5), (cx - 12, yy + 5)], fill=LIGHT, stroke=MAIN, width=0.3)
            elif shape == "para":
                pen.polygon([(cx - 12, yy), (cx + 14, yy), (cx + 12, yy + 5), (cx - 14, yy + 5)], fill=LIGHT, stroke=MAIN, width=0.3)
            else:
                pen.rect(cx - 13, yy, 26, 5, fill=LIGHT, stroke=MAIN, width=0.3, radius=2.5 if shape == "round" else 0)
        pen.line(x + 22, y + 9, x + 22, y + 21, width=0.5, color=MAIN)
        pen.arrow(x + 22, y + 9, x + 26, y + 9, width=0.5, color=MAIN)
        pen.line(x + 26, y + 21, x + 22, y + 21, width=0.5, color=MAIN)
