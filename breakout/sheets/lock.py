"""The final lock: a paper combination lock. A board with four columns, two
paper bands taped across it as channels, and four digit strips that slide
under the bands. Each strip carries a quarter of a key below its digits, at
an offset that depends on that column's correct digit, so the four quarters
line up into one whole key only when the board reads the code.

The code itself is nowhere on these sheets; the offsets encode it in
geometry, and a test proves the key is whole at the code and broken off it.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_W, PALETTE, SAFE, SOFT, WHITE

MAIN, LIGHT = PALETTE[0]
CODE = "4326"  # positions 1..4, left to right

BOARD_W, BOARD_H = 95.0, 175.0
COL_W, COL_GAP = 20.0, 2.0
STRIP_W, STRIP_H = 19.0, 170.0
PITCH = 12.0  # digit cells on a strip
DIGIT0 = 10.0  # centre of digit 0 from the strip's top
READ_Y = 60.0  # the read line, from the board's top
KEY_DY = 70.0  # the key zone, below the read line
KEY_H = 16.0
BAND_W, BAND_H = 95.0, 12.0  # as wide as the board; glued only at its two ends
BAND_GLUE = 4.5
BAND_DY = (-30.0, 18.0)  # the two bands, from the read line (their top edges)


def column_x(i):
    """Left edge of column i (0..3) from the board's left edge."""
    inner = 4 * COL_W + 3 * COL_GAP
    return (BOARD_W - inner) / 2 + i * (COL_W + COL_GAP)


def digit_y(d):
    """Centre of digit d from the strip's top."""
    return DIGIT0 + d * PITCH


def key_segment_y(correct_digit):
    """Top of the key quarter on a strip whose correct digit is given: when
    that digit sits on the read line, the quarter sits in the key zone."""
    return digit_y(correct_digit) + KEY_DY - KEY_H / 2


def strip_offset_for(shown_digit):
    """Where the strip's top is, relative to the read line, when the board
    shows `shown_digit` in that column (negative: above the read line)."""
    return -digit_y(shown_digit)


def key_pieces_aligned(shown):
    """True when the four quarters sit at one height. That happens at the
    code, and also when every strip is shifted by the same number of digits
    (the whole key then sits higher or lower than the board's silhouette)."""
    tops = {round(strip_offset_for(int(s)) + key_segment_y(int(c)), 3) for s, c in zip(shown, CODE)}
    return len(tops) == 1


def key_in_frame(shown):
    """True when the four quarters are whole AND fill the key silhouette
    printed on the board: only at the code. The board is the absolute
    reference the strips alone cannot give."""
    if not key_pieces_aligned(shown):
        return False
    top = strip_offset_for(int(shown[0])) + key_segment_y(int(CODE[0]))
    return round(top, 3) == round(KEY_DY - KEY_H / 2, 3)  # relative to the read line


def draw_key_quarter(pen, x, y, i):
    """Quarter i (0..3) of a key, drawn in a STRIP_W x KEY_H box at x, y.
    0: the bow (ring), 1 and 2: the shaft, 3: the bit with two teeth."""
    cy = y + KEY_H / 2
    gold = MAIN
    if i == 0:
        pen.circle(x + STRIP_W / 2, cy, 5.2, fill=LIGHT, stroke=gold, width=1.2)
        pen.circle(x + STRIP_W / 2, cy, 2.0, fill=WHITE, stroke=gold, width=0.6)
        pen.rect(x + STRIP_W / 2 + 5, cy - 1.6, STRIP_W / 2 - 5, 3.2, fill=gold, stroke=None)
    elif i in (1, 2):
        pen.rect(x, cy - 1.6, STRIP_W, 3.2, fill=gold, stroke=None)
        if i == 1:
            pen.rect(x + 4, cy - 2.8, 2, 1.4, fill=gold, stroke=None)
            pen.rect(x + 11, cy - 2.8, 2, 1.4, fill=gold, stroke=None)
    else:
        pen.rect(x, cy - 1.6, 9, 3.2, fill=gold, stroke=None)
        pen.rect(x + 6, cy - 1.6, 3, 6, fill=gold, stroke=None)
        pen.rect(x + 11, cy - 1.6, 3, 5, fill=gold, stroke=None)
        pen.rect(x + 8, cy - 1.6, 7, 3.2, fill=gold, stroke=None)


def draw_key_silhouette(pen, x, y, i):
    """The outline of quarter i, dashed and faint, printed on the board."""
    cy = y + KEY_H / 2
    faint = (0.75, 0.68, 0.45)
    if i == 0:
        pen.circle(x + STRIP_W / 2, cy, 5.2, fill=None, stroke=faint, width=0.4, dash=(1, 0.8))
        pen.rect(x + STRIP_W / 2 + 5, cy - 1.6, STRIP_W / 2 - 5, 3.2, fill=None, stroke=faint, width=0.3, dash=(1, 0.8))
    elif i in (1, 2):
        pen.rect(x, cy - 1.6, STRIP_W, 3.2, fill=None, stroke=faint, width=0.3, dash=(1, 0.8))
    else:
        pen.rect(x, cy - 1.6, 15, 3.2, fill=None, stroke=faint, width=0.3, dash=(1, 0.8))
        pen.rect(x + 6, cy + 1.6, 3, 2.8, fill=None, stroke=faint, width=0.3, dash=(1, 0.8))
        pen.rect(x + 11, cy + 1.6, 3, 1.8, fill=None, stroke=faint, width=0.3, dash=(1, 0.8))


def draw_strip(pen, x, y, position):
    correct = int(CODE[position])
    pen.cut_rect(x, y, STRIP_W, STRIP_H)
    pen.text(x + STRIP_W / 2, y + 4.5, f"מקום {position + 1}", 6, color=SOFT, align="center")
    for d in range(10):
        cy = y + digit_y(d)
        pen.line(x, cy - PITCH / 2, x + STRIP_W, cy - PITCH / 2, width=0.2, color=SOFT)
        pen.text(x + STRIP_W / 2, cy + 3.8, str(d), 14, bold=True, color=INK, align="center")
    ky = y + key_segment_y(correct)
    draw_key_quarter(pen, x, ky, position)
    pen.text(x + STRIP_W / 2, y + STRIP_H - 3, "משכו", 6, color=SOFT, align="center")


def draw_board(pen, x, y):
    pen.cut_rect(x, y, BOARD_W, BOARD_H)
    pen.rect(x, y, BOARD_W, 14, fill=MAIN, stroke=None)
    pen.text(x + BOARD_W / 2, y + 9.5, "המנעול של ביט", 11, bold=True, color=WHITE, align="center")
    for i in range(4):
        cx = x + column_x(i)
        pen.rect(cx, y + 16, COL_W, BOARD_H - 20, fill=LIGHT, stroke=None, radius=1.5)
        pen.text(cx + COL_W / 2, y + 22, f"מקום {i + 1}", 6.5, bold=True, color=MAIN, align="center")
    # The bands' places.
    for n, dy in enumerate(BAND_DY, 1):
        by = y + READ_Y + dy
        pen.rect(x, by, BAND_W, BAND_H, fill=None, stroke=SOFT, width=0.3, dash=(1, 1))
        pen.rect(x, by, BAND_GLUE, BAND_H, fill=(0.8, 0.8, 0.78), stroke=None)
        pen.rect(x + BAND_W - BAND_GLUE, by, BAND_GLUE, BAND_H, fill=(0.8, 0.8, 0.78), stroke=None)
        pen.text(x + BOARD_W / 2, by + BAND_H / 2 + 2, f"פס {n} כאן, מודבק רק בקצוות האפורים", 5.5, color=SOFT, align="center")
    # The read line.
    ry = y + READ_Y
    pen.line(x, ry, x + BOARD_W, ry, width=0.9, color=(0.8, 0.2, 0.2))
    pen.polygon([(x, ry - 2.5), (x + 4, ry), (x, ry + 2.5)], fill=(0.8, 0.2, 0.2), stroke=None)
    pen.polygon([(x + BOARD_W, ry - 2.5), (x + BOARD_W - 4, ry), (x + BOARD_W, ry + 2.5)], fill=(0.8, 0.2, 0.2), stroke=None)
    pen.text(x + BOARD_W / 2, ry - 2, "הקוד נקרא על הקו האדום", 6, color=(0.8, 0.2, 0.2), align="center")
    # The key zone: a dashed silhouette of the whole key, exactly where the
    # four quarters land at the code (a uniformly shifted key misses it).
    kz = ry + KEY_DY - KEY_H / 2
    pen.rect(x + 3, kz - 1, BOARD_W - 6, KEY_H + 2, fill=None, stroke=MAIN, width=0.5, dash=(1.5, 1))
    for i in range(4):
        draw_key_silhouette(pen, x + column_x(i) + (COL_W - STRIP_W) / 2, kz, i)
    pen.text(x + BOARD_W / 2, kz + KEY_H + 7, "כשהקוד נכון, המפתח ממלא בדיוק את הצללית", 6.5, bold=True, color=MAIN, align="center")
    pen.text(x + BOARD_W / 2, y + BOARD_H - 4, "מראים למורה. המורה פותח את המעטפה.", 6.5, color=SOFT, align="center")


def draw_band(pen, x, y, n):
    pen.cut_rect(x, y, BAND_W, BAND_H)
    pen.glue(x, y, BAND_GLUE, BAND_H, label="", size=5)
    pen.glue(x + BAND_W - BAND_GLUE, y, BAND_GLUE, BAND_H, label="", size=5)
    pen.text(x + BAND_W / 2, y + BAND_H / 2 + 2.2, f"פס {n}: סרט הדבקה רק על הקצוות האפורים; הרצועות עוברות מתחת", 6.2, color=INK, align="center")


@register
class LockParts(Sheet):
    key = "lock_parts"
    title = "המנעול: לוח, ארבע רצועות ושני פסים"
    kind = "cut_out"
    station = 0

    def draw(self, pen, page=0):
        y0 = pen.header(0, "המנעול הסופי", "דף עבודה: מנעול קומבינציה מנייר")
        y0 = pen.legend(y0)
        bx, by = 12, y0 + 2
        draw_board(pen, bx, by)
        for i in range(4):
            draw_strip(pen, 110 + i * (STRIP_W + 2), by, i)
        band_y = by + BOARD_H + 6
        draw_band(pen, bx, band_y, 1)
        draw_band(pen, bx, band_y + BAND_H + 4, 2)
        pen.para(PAGE_W - SAFE, band_y + 5, 84, "הרצועות ממוספרות לפי המקום בלוח: רצועה של מקום 1 נכנסת לעמודה 1, וכן הלאה.", 7, color=SOFT)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · המנעול הסופי · דף עבודה")


# ------------------------------------------------------------------ guide


def pic_cut_parts(pen, x, y, w, h):
    pen.rect(x + 3, y + 3, 10, 14, fill=WHITE, stroke=CUT, width=0.4)
    for i in range(3):
        pen.rect(x + 15 + i * 3, y + 2, 2, 16, fill=WHITE, stroke=CUT, width=0.3)
    pen.scissors(x + 23, y + 12, 3.5, angle=0)


def pic_bands(pen, x, y, w, h):
    pen.rect(x + 5, y + 2, 14, 16, fill=WHITE, stroke=CUT, width=0.4)
    pen.rect(x + 3, y + 5, 18, 2.5, fill=LIGHT, stroke=CUT, width=0.3)
    pen.rect(x + 3, y + 12, 18, 2.5, fill=LIGHT, stroke=CUT, width=0.3)
    pen.rect(x + 2, y + 4.5, 2, 3.5, fill=(0.75, 0.75, 0.75), stroke=None)
    pen.rect(x + 20, y + 4.5, 2, 3.5, fill=(0.75, 0.75, 0.75), stroke=None)


def pic_slide(pen, x, y, w, h):
    pen.rect(x + 5, y + 2, 14, 16, fill=WHITE, stroke=CUT, width=0.4)
    pen.rect(x + 3, y + 5, 18, 2.5, fill=LIGHT, stroke=CUT, width=0.3)
    pen.rect(x + 3, y + 12, 18, 2.5, fill=LIGHT, stroke=CUT, width=0.3)
    for i in range(4):
        pen.rect(x + 6.5 + i * 3, y + 0, 2, 20, fill=None, stroke=MAIN, width=0.3)
    pen.arrow(x + 23, y + 16, x + 23, y + 10, width=0.4, color=MAIN)


def pic_key(pen, x, y, w, h):
    cy = y + 10
    pen.circle(x + 6, cy, 3, fill=LIGHT, stroke=MAIN, width=0.8)
    pen.rect(x + 9, cy - 1, 12, 2, fill=MAIN, stroke=None)
    pen.rect(x + 17, cy - 1, 1.6, 4, fill=MAIN, stroke=None)
    pen.rect(x + 20, cy - 1, 1.6, 3.2, fill=MAIN, stroke=None)


@register
class LockGuide(Sheet):
    key = "lock_guide"
    title = "דף הדרכה: המנעול הסופי"
    kind = "instructions"
    station = 0

    def draw(self, pen, page=0):
        y = pen.header(0, "המנעול הסופי", "דף הדרכה: בונים מנעול קומבינציה מנייר")
        right = PAGE_W - SAFE
        y = pen.legend(y)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=0, title="מה בונים")
        pen.para(right - 4, y + 15, 108, "מנעול עם ארבע רצועות ספרות שמחליקות על לוח, מתחת לשני פסי נייר. מכוונים ספרה בכל מקום על הקו האדום. רק כשארבע הספרות נכונות, ארבעת חלקי המפתח שעל הרצועות מתיישרים למפתח אחד שלם. זה הרגע לקרוא למורה.", 9.2)
        self.picture(pen, SAFE + 10, y + 10)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את הלוח, את ארבע הרצועות ואת שני הפסים.", "על כל רצועה כתוב לאיזה מקום היא שייכת. הרצועות ארוכות; גוזרים לאט ולאורך הקו.", color_key=0, size=10.5, picture=pic_cut_parts)
        y = pen.step(2, right, y, col_w, "מדביקים את שני הפסים על הלוח, במקומות המסומנים, רק בקצוות.", "פיסת סרט הדבקה בכל קצה, על השוליים מחוץ לעמודות. האמצע של הפס נשאר חופשי: מתחתיו הרצועות יעברו.", color_key=0, size=10.5, picture=pic_bands)
        y = pen.step(3, right, y, col_w, "משחילים כל רצועה מתחת לשני הפסים, בעמודה שלה, הספרות כלפי מעלה.", "רצועה של מקום 1 בעמודה 1, וכן הלאה. הרצועה צריכה להחליק בחופשיות למעלה ולמטה.", color_key=0, size=10.5, picture=pic_slide)
        y = pen.step(4, right, y, col_w, "מכוונים את הקוד: בכל מקום, הספרה הנכונה בדיוק על הקו האדום.", "ארבע ספרות, אחת מכל תחנה 1 עד 4, בסדר שתחנה 5 נתנה. כשהמפתח שלם, קוראים למורה.", color_key=0, size=10.5, picture=pic_key)
        y += 1
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 50, color_key=0, title="איך יודעים שהקוד נכון")
        pen.para(right - 4, y + 15, PAGE_W - 2 * SAFE - 8,
                 "מתחת לספרות, בתוך המסגרת המקווקוות, יש על כל רצועה חלק של מפתח: טבעת, שני חלקי גוף, ושיניים. כשארבע הספרות הנכונות על הקו האדום, ארבעת החלקים באותו גובה, והמפתח שלם. אם חלק אחד גבוה או נמוך מהאחרים, הספרה באותו מקום לא נכונה.\n"
                 "לא מנסים את כל האפשרויות: עשרת אלפים קודים זה הרבה. עובדים כמו מהנדסים, ספרה מכל תחנה.", 9.2)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · המנעול הסופי · דף הדרכה")

    def picture(self, pen, x, y):
        pen.rect(x + 10, y, 36, 30, fill=WHITE, stroke=CUT, width=0.5)
        for i in range(4):
            sx = x + 14 + i * 8
            pen.rect(sx, y - 3, 5, 36, fill=LIGHT, stroke=MAIN, width=0.3)
            pen.text(sx + 2.5, y + 12, str((7 + i * 3) % 10), 5, bold=True, align="center")
        pen.line(x + 8, y + 10.5, x + 48, y + 10.5, width=0.7, color=(0.8, 0.2, 0.2))
        pen.rect(x + 8, y + 4, 40, 2.5, fill=(0.93, 0.93, 0.93), stroke=SOFT, width=0.3)
        pen.rect(x + 8, y + 16, 40, 2.5, fill=(0.93, 0.93, 0.93), stroke=SOFT, width=0.3)
        pic_key(pen, x + 15, y + 14, 26, 20)
