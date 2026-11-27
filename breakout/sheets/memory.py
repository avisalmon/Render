"""Station 1, the memory: five bit tents (16, 8, 4, 2, 1 dots) that stand on
the table and face the group with dots (1) or blank (0), four bit tickets,
and a decoder wheel: a base disc with the 32 five-bit patterns, their
numbers and the letters, under a top disc with a wedge window and a pointer.

Nothing here says which word the tickets spell; that is the teacher's page.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_W, PALETTE, SAFE, SOFT, WHITE, polar

MAIN, LIGHT = PALETTE[1]
LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"  # 22 letters, slots 1..22
TICKETS = ["10101", "01100", "00110", "10101"]  # as in the puzzle text
VALUES = [16, 8, 4, 2, 1]
TENT_W, PANEL_H = 50.0, 45.0
EXAMPLE = "01010"  # the guide's worked example: 8 + 2 = 10 = י (not a ticket)


def dot_grid(value):
    """Rows of dots for a value: 16 = 4x4, 8 = 2x4, 4 = 2x2, 2 = 1x2, 1 = 1."""
    return {16: (4, 4), 8: (2, 4), 4: (2, 2), 2: (1, 2), 1: (1, 1)}[value]


def draw_dots(pen, cx, cy, value, pitch, r):
    rows, cols = dot_grid(value)
    gx = cx - (cols - 1) * pitch / 2
    gy = cy - (rows - 1) * pitch / 2
    for i in range(rows):
        for j in range(cols):
            pen.dot(gx + j * pitch, gy + i * pitch, r, MAIN)


def draw_tent(pen, x, y, value):
    """A tent at its top-left: the dots panel over the blank panel, a fold between."""
    w, h = TENT_W, PANEL_H
    pen.cut_rect(x, y, w, 2 * h)
    pen.fold(x, y + h, x + w, y + h)
    draw_dots(pen, x + w / 2, y + h / 2 + 2, value, 8.5, 2.3)
    pen.text(x + w - 3, y + 6.5, str(value), 10, bold=True, color=MAIN)
    pen.text(x + 3, y + 6.5, "1", 8, color=SOFT, align="left")
    pen.text(x + w / 2, y + h + h / 2 + 7, "0", 26, bold=True, color=(0.85, 0.85, 0.85), align="center")
    pen.text(x + w / 2, y + 2 * h - 4, "הצד הריק = 0", 7, color=SOFT, align="center")


def standing_tent(pen, x, y, w, value, facing=True):
    """A tent seen from the front, its top-left at x, y and base width w."""
    h = w * 0.7
    pen.polygon([(x, y + h), (x + w * 0.25, y), (x + w * 0.75, y), (x + w, y + h)], fill=WHITE if facing else LIGHT, stroke=MAIN, width=0.4)
    if facing:
        draw_dots(pen, x + w / 2, y + h * 0.55, value, w * 0.095, w * 0.028)


@register
class MemoryCards(Sheet):
    key = "memory_cards"
    title = "חמישה אוהלי ביטים וארבעה פתקים"
    kind = "cut_out"
    station = 1

    def draw(self, pen, page=0):
        y0 = pen.header(1, "הזיכרון", "דף עבודה 1 מתוך 2: האוהלים והפתקים")
        y0 = pen.legend(y0, with_glue=False)
        xs = [20, 80, 140]
        for x, value in zip(xs, VALUES[:3]):
            draw_tent(pen, x, y0 + 2, value)
        y1 = y0 + 2 + 2 * PANEL_H + 8
        for x, value in zip(xs[:2], VALUES[3:]):
            draw_tent(pen, x, y1, value)
        # Tickets: the four bit patterns, numbered so the order survives a shuffle.
        tx, ty = 140, y1
        pen.text(tx + TENT_W, ty - 2, "פתקי הביטים", 8.5, bold=True, color=MAIN)
        for n, bits in enumerate(TICKETS, 1):
            yy = ty + (n - 1) * 22
            pen.cut_rect(tx, yy, TENT_W, 18, radius=1.5)
            pen.text(tx + 4, yy + 5.5, f"פתק {n}", 7, color=SOFT, align="left")
            pen.text(tx + TENT_W / 2, yy + 13.5, " ".join(bits), 13, bold=True, color=INK, align="center")
        # The order to lay the tents in, as a little picture.
        yb = y1 + 2 * PANEL_H + 12
        pen.box(SAFE, yb, PAGE_W - 2 * SAFE, 34, color_key=1, title="כך מסדרים את האוהלים על השולחן, משמאל לימין")
        for i, value in enumerate(VALUES):
            x = 22 + i * 26
            standing_tent(pen, x, yb + 15, 18, value)
            pen.text(x + 9, yb + 32.5, str(value), 7.5, bold=True, color=MAIN, align="center")
        pen.para(PAGE_W - SAFE - 4, yb + 17, 34, "הביט השמאלי בפתק הוא האוהל השמאלי.", 7.5, color=SOFT)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 1 · דף עבודה 1")


# ------------------------------------------------------------------ wheel

SLOTS = 32
BASE_R = 70.0
RING_PATTERN = (58.0, 70.0)
RING_NUMBER = (47.0, 58.0)
RING_LETTER = (34.0, 47.0)
TOP_R = 48.5
WINDOW_R = 30.0  # the wedge window runs from here to the top disc's edge


def slot_letter(i):
    return LETTERS[i - 1] if 1 <= i <= 22 else ""


def slot_angle(i):
    return i * 360.0 / SLOTS


@register
class MemoryWheel(Sheet):
    key = "memory_wheel"
    title = "גלגל הפענוח: שני דיסקים"
    kind = "cut_out"
    station = 1

    def draw(self, pen, page=0):
        y0 = pen.header(1, "הזיכרון", "דף עבודה 2 מתוך 2: גלגל הפענוח")
        y0 = pen.legend(y0, with_glue=False)
        cx, cy = PAGE_W / 2, y0 + 2 + BASE_R
        self.base(pen, cx, cy)
        ty = cy + BASE_R + 6 + TOP_R
        self.top(pen, cx, ty)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 1 · דף עבודה 2")

    def base(self, pen, cx, cy):
        pen.cut_circle(cx, cy, BASE_R)
        for r0, _r1 in (RING_PATTERN, RING_NUMBER, RING_LETTER):
            pen.circle(cx, cy, r0, stroke=SOFT, width=0.2)
        half = 360.0 / SLOTS / 2
        for i in range(SLOTS):
            a = slot_angle(i)
            pen.line(*polar(cx, cy, RING_LETTER[0], a - half), *polar(cx, cy, BASE_R, a - half), width=0.2, color=SOFT)
            px, py = polar(cx, cy, (RING_PATTERN[0] + RING_PATTERN[1]) / 2 + 1.2, a)
            pen.text(px, py, format(i, "05b"), 6.2, bold=True, color=INK, align="center", angle=-a)
            nx, ny = polar(cx, cy, (RING_NUMBER[0] + RING_NUMBER[1]) / 2 + 1.0, a)
            pen.text(nx, ny, str(i), 7.5, color=MAIN, align="center", angle=-a)
            lx, ly = polar(cx, cy, (RING_LETTER[0] + RING_LETTER[1]) / 2 + 1.3, a)
            letter = slot_letter(i)
            if letter:
                pen.text(lx, ly, letter, 9.5, bold=True, color=INK, align="center", angle=-a)
            else:
                pen.dot(lx, ly - 1.2, 0.7, SOFT)
        pen.circle(cx, cy, 1.4, fill=INK, stroke=None)
        pen.text(cx, cy - 5, "דיסק תחתון", 8, bold=True, color=MAIN, align="center")
        pen.text(cx, cy + 9, "סיכה במרכז", 6.5, color=SOFT, align="center")
        pen.text(cx, cy + 15, "חוץ: ביטים · אמצע: מספר · פנים: אות", 6, color=SOFT, align="center")

    def top(self, pen, cx, cy):
        half = 360.0 / SLOTS / 2
        pen.circle(cx, cy, TOP_R, fill=LIGHT, stroke=None)
        pen.cut_circle(cx, cy, TOP_R)
        # The window: a dark slice from the rim in to WINDOW_R, to be cut out.
        pen.ring_sector(cx, cy, WINDOW_R, TOP_R, -half, 2 * half, fill=(0.3, 0.3, 0.3), stroke=CUT, width=0.5)
        pen.arrow(cx, cy - 12, cx, cy - WINDOW_R + 2.5, width=0.6, color=MAIN)
        pen.text(cx - 3, cy - 18, "החץ אל הביטים", 7.5, bold=True, color=MAIN)
        pen.para(cx + 14, cy + 20, 28, "גזרו את הפרוסה הכהה מהשפה פנימה: זה החלון שמראה את האות.", 6.8, color=SOFT)
        pen.circle(cx, cy, 1.4, fill=INK, stroke=None)
        pen.text(cx, cy + 9, "דיסק עליון", 8, bold=True, color=MAIN, align="center")
        pen.text(cx, cy + 13.5, "סיכה במרכז", 6.5, color=SOFT, align="center")


# ------------------------------------------------------------------ guide


def pic_cut_card(pen, x, y, w, h):
    pen.rect(x + 6, y + 4, w - 12, h - 8, fill=WHITE, stroke=CUT, width=0.5)
    pen.fold(x + 6, y + h / 2, x + w - 6, y + h / 2)
    draw_dots(pen, x + w / 2, y + h * 0.3, 4, 2.6, 0.8)
    pen.scissors(x + w - 5, y + h - 6, 5.5, angle=0)


def pic_fold_tent(pen, x, y, w, h):
    pen.polygon([(x + 4, y + h - 4), (x + w / 2, y + 5), (x + w - 4, y + h - 4)], fill=WHITE, stroke=MAIN, width=0.5)
    pen.line(x + w / 2, y + 5, x + w / 2, y + h - 4, width=0.3, color=SOFT, dash=(1, 1))
    draw_dots(pen, x + w * 0.32, y + h * 0.62, 4, 2.2, 0.7)
    pen.arrow(x + w - 2, y + 4, x + w / 2 + 3, y + 7, width=0.4, color=MAIN)


def pic_tickets(pen, x, y, w, h):
    for i in range(2):
        yy = y + 4 + i * 9
        pen.rect(x + 4, yy, w - 8, 7, fill=WHITE, stroke=CUT, width=0.4, radius=1)
        pen.text(x + w / 2, yy + 5, "0 1 1 0 1" if i else "1 0 0 1 0", 6, bold=True, align="center")
    pen.scissors(x + w - 4, y + h - 4, 4.5, angle=-90)


def pic_discs(pen, x, y, w, h):
    pen.circle(x + w * 0.38, y + h / 2, 8, fill=WHITE, stroke=CUT, width=0.5)
    for a in range(0, 360, 45):
        pen.line(*polar(x + w * 0.38, y + h / 2, 6, a), *polar(x + w * 0.38, y + h / 2, 8, a), width=0.2, color=SOFT)
    pen.circle(x + w * 0.78, y + h / 2, 5, fill=LIGHT, stroke=CUT, width=0.5)
    pen.ring_sector(x + w * 0.78, y + h / 2, 3, 5, -10, 20, fill=(0.3, 0.3, 0.3), stroke=None)


def pic_pin(pen, x, y, w, h):
    cx, cy = x + w / 2, y + h / 2 + 2
    pen.circle(cx, cy, 9, fill=WHITE, stroke=CUT, width=0.5)
    pen.circle(cx, cy, 6, fill=LIGHT, stroke=CUT, width=0.4)
    pen.ring_sector(cx, cy, 3.5, 6, -12, 24, fill=(0.3, 0.3, 0.3), stroke=None)
    pen.circle(cx, cy, 1.2, fill=INK, stroke=None)
    pen.line(cx, cy - 1, cx, y + 2, width=0.6, color=INK)
    pen.circle(cx, y + 2.5, 1.3, fill=INK, stroke=None)


@register
class MemoryGuide(Sheet):
    key = "memory_guide"
    title = "דף הדרכה: הזיכרון"
    kind = "instructions"
    station = 1

    def draw(self, pen, page=0):
        y = pen.header(1, "הזיכרון", "דף הדרכה: מה בונים ואיך משתמשים")
        right = PAGE_W - SAFE
        y = pen.legend(y, with_glue=False)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=1, title="מה בונים")
        pen.para(right - 4, y + 15, 86, "חמישה אוהלי נייר שעומדים על השולחן, כל אחד עם מספר נקודות: 16, 8, 4, 2, 1. אוהל שמראה נקודות הוא 1, אוהל שמראה את הצד הריק הוא 0. וגלגל פענוח משני דיסקים: מסובבים את החץ אל רצף הביטים, ובחלון מופיעה האות.", 8.2)
        self.picture(pen, SAFE + 4, y + 6)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את חמשת האוהלים לאורך הקווים המלאים.", "הקווים המלאים בלבד. את הקו המקווקו באמצע כל כרטיס לא גוזרים: הוא הקיפול.", picture=pic_cut_card)
        y = pen.step(2, right, y, col_w, "מקפלים כל כרטיס לאורך הקו המקווקו, והוא עומד כאוהל.", "צד אחד נקודות, הצד השני ריק. לוחצים טוב על הקיפול כדי שהאוהל יעמוד ישר.", picture=pic_fold_tent)
        y = pen.step(3, right, y, col_w, "גוזרים את ארבעת פתקי הביטים.", "על כל פתק חמש ספרות של 0 ו-1 ומספר הפתק בפינה. שומרים אותם לפי הסדר.", picture=pic_tickets)
        y = pen.step(4, right, y, col_w, "גוזרים את שני הדיסקים של הגלגל.", "בדיסק העליון (הקטן) גוזרים גם את הפרוסה הכהה מהשפה פנימה. זה החלון.", picture=pic_discs)
        y = pen.step(5, right, y, col_w, "מניחים את הדיסק העליון על התחתון ותוקעים סיכת פיצול דרך שני המרכזים.", "אין סיכה? עיפרון שמחזיקים במרכז עובד. העיקר ששני הדיסקים מסתובבים זה על זה.", picture=pic_pin)
        y += 2
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 72, color_key=1, title="איך משתמשים: דוגמה עם הרצף 01010 (שלא מופיע באף פתק)")
        pen.para(right - 4, y + 15, 96,
                 "מסדרים את האוהלים בשורה משמאל לימין: 16, 8, 4, 2, 1. במקום שכתוב בפתק 1 מסובבים את האוהל כך שהנקודות פונות אליכם; במקום שכתוב 0 מסובבים אותו לצד הריק. סופרים את הנקודות שרואים: 8 + 2 = 10.\n"
                 "בגלגל: מסובבים את החץ של הדיסק העליון אל 01010 ברינג החיצוני. באמצע כתוב 10, ובחלון מופיעה האות י.\n"
                 "ככה עם כל פתק: ארבעה פתקים, ארבע אותיות, מילה אחת. המילה היא הספרה של התחנה.", 8.2)
        self.example(pen, SAFE + 6, y + 14)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 1 · דף הדרכה")

    def picture(self, pen, x, y):
        """Five little tents in a row and a wheel beside them."""
        for i, value in enumerate(VALUES):
            standing_tent(pen, x + i * 13, y + 14, 11, value)
            pen.text(x + i * 13 + 5.5, y + 27, str(value), 6, color=MAIN, align="center")
        wx, wy = x + 76, y + 18
        pen.circle(wx, wy, 14, fill=WHITE, stroke=INK, width=0.4)
        pen.circle(wx, wy, 9.5, fill=LIGHT, stroke=INK, width=0.3)
        pen.ring_sector(wx, wy, 6, 9.5, -8, 16, fill=(0.3, 0.3, 0.3), stroke=None)
        pen.arrow(wx, wy - 1, wx, wy - 5, width=0.5, color=MAIN)
        for a in range(0, 360, 30):
            pen.line(*polar(wx, wy, 11.5, a), *polar(wx, wy, 14, a), width=0.2, color=SOFT)
        pen.circle(wx, wy, 0.8, fill=INK, stroke=None)

    def example(self, pen, x, y):
        """The worked example as a picture: tents set to 01010, then the wheel."""
        pen.text(x + 36, y + 5, "0 1 0 1 0", 9, bold=True, align="center")
        for i, value in enumerate(VALUES):
            facing = EXAMPLE[i] == "1"
            standing_tent(pen, x + i * 14, y + 8, 12, value, facing=facing)
            pen.text(x + i * 14 + 6, y + 20.5, "1" if facing else "0", 6.5, bold=True, color=MAIN if facing else SOFT, align="center")
        pen.text(x + 36, y + 28, "8 + 2 = 10", 8, bold=True, color=MAIN, align="center")
        wx, wy = x + 36, y + 44
        pen.circle(wx, wy, 13, fill=WHITE, stroke=INK, width=0.4)
        pen.circle(wx, wy, 8.5, fill=LIGHT, stroke=INK, width=0.3)
        pen.ring_sector(wx, wy, 5, 8.5, 22, 16, fill=WHITE, stroke=INK, width=0.3)
        pen.text(*polar(wx, wy, 7.4, 30), "י", 6.5, bold=True, align="center")
        pen.text(*polar(wx, wy, 11.2, 30), "01010", 4, bold=True, align="center", angle=-30)
        pen.arrow(*polar(wx, wy, 1.5, 30), *polar(wx, wy, 4.5, 30), width=0.5, color=MAIN)
        pen.circle(wx, wy, 0.8, fill=INK, stroke=None)
