"""Station 5, the algorithm: four cube nets, one per part of the robot, each
face telling the part's name, its station and its weight. The group folds
the cubes and stacks them by the sorting rule; the station numbers read
down the tower are the order of the code. The order itself is on the
teacher's page only.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_H, PAGE_W, PALETTE, SAFE, SOFT, WHITE

MAIN, LIGHT = PALETTE[5]
CUBE = 29.0

# name, station, weight text, a second line
PARTS = [
    ("זיכרון", 1, "300 גרם", "זוכר הכל"),
    ("מעבד", 2, "800 גרם", "חושב מהר"),
    ("תוכנה", 3, "אין משקל", "תוכנה היא רק מידע"),
    ("רשת", 4, "1200 גרם", "מדבר עם העולם"),
]
PRINT_ORDER = [2, 4, 1, 3]


def net_cells(x, y):
    """The 1-4-1 cross: a column of four squares, wings on the second."""
    s = CUBE
    return {
        "top": (x + s, y),
        "front": (x + s, y + s),
        "left": (x, y + s),
        "right": (x + 2 * s, y + s),
        "bottom": (x + s, y + 2 * s),
        "back": (x + s, y + 3 * s),
    }


def draw_net(pen, x, y, part):
    name, station, weight, line2 = part
    s = CUBE
    cells = net_cells(x, y)
    # The outline of the cross, as one cut line.
    pen.cut([
        (x + s, y), (x + 2 * s, y), (x + 2 * s, y + s), (x + 3 * s, y + s), (x + 3 * s, y + 2 * s),
        (x + 2 * s, y + 2 * s), (x + 2 * s, y + 4 * s), (x + s, y + 4 * s), (x + s, y + 2 * s),
        (x, y + 2 * s), (x, y + s), (x + s, y + s),
    ], closed=True)
    # Folds between the squares.
    pen.fold(x + s, y + s, x + 2 * s, y + s)
    pen.fold(x + s, y + 2 * s, x + 2 * s, y + 2 * s)
    pen.fold(x + s, y + 3 * s, x + 2 * s, y + 3 * s)
    pen.fold(x + s, y + s, x + s, y + 2 * s)
    pen.fold(x + 2 * s, y + s, x + 2 * s, y + 2 * s)
    for key, (cx, cy) in cells.items():
        pen.rect(cx, cy, s, s, fill=LIGHT if key in ("front", "back") else None, stroke=None)
    # Faces.
    fx, fy = cells["front"]
    pen.text(fx + s / 2, fy + s / 2 - 1, name, 14, bold=True, color=MAIN, align="center")
    pen.text(fx + s / 2, fy + s / 2 + 6, f"תחנה {station}", 8, color=INK, align="center")
    lx, ly = cells["left"]
    pen.text(lx + s / 2, ly + s / 2 + 1.5, weight, 9.5, bold=True, color=INK, align="center")
    pen.text(lx + s / 2, ly + s / 2 + 7, "משקל", 6.5, color=SOFT, align="center")
    rx, ry = cells["right"]
    pen.para(rx + s - 2, ry + 10, s - 4, line2, 7, color=INK)
    tx, ty = cells["top"]
    pen.text(tx + s / 2, ty + s / 2 + 2.5, str(station), 20, bold=True, color=MAIN, align="center")
    pen.text(tx + s / 2, ty + s - 3, "תחנה", 6, color=SOFT, align="center")
    bx, by = cells["bottom"]
    pen.text(bx + s / 2, by + s / 2 + 1.5, name, 9, bold=True, color=INK, align="center")
    pen.text(bx + s / 2, by + s / 2 + 7, weight, 7, color=SOFT, align="center")
    kx, ky = cells["back"]
    pen.text(kx + s / 2, ky + s / 2 - 1, "ביט", 9, bold=True, color=MAIN, align="center")
    pen.text(kx + s / 2, ky + s / 2 + 5, "המחשב שנכבה", 6, color=SOFT, align="center")


@register
class AlgorithmCubes(Sheet):
    key = "algorithm_cubes"
    title = "ארבע קוביות: חלקי הרובוט"
    kind = "cut_out"
    station = 5

    def draw(self, pen, page=0):
        y0 = pen.header(5, "האלגוריתם", "דף עבודה: ארבע קוביות לקיפול")
        y0 = pen.legend(y0)
        positions = [(16, y0 + 2), (106, y0 + 2), (16, y0 + 2 + 4 * CUBE + 6), (106, y0 + 2 + 4 * CUBE + 6)]
        for (x, y), idx in zip(positions, PRINT_ORDER):
            draw_net(pen, x, y, PARTS[idx - 1])
        pen.text(SAFE, PAGE_H - SAFE + 0.5, "סוגרים כל קובייה בסרט הדבקה; אין צורך בלשוניות.", 7, color=SOFT, align="left")
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 5 · דף עבודה")


# ------------------------------------------------------------------ guide


def pic_cut_net(pen, x, y, w, h):
    s = 3.2
    ox, oy = x + 7, y + 2
    pen.cut([(ox + s, oy), (ox + 2 * s, oy), (ox + 2 * s, oy + s), (ox + 3 * s, oy + s), (ox + 3 * s, oy + 2 * s), (ox + 2 * s, oy + 2 * s), (ox + 2 * s, oy + 4 * s), (ox + s, oy + 4 * s), (ox + s, oy + 2 * s), (ox, oy + 2 * s), (ox, oy + s), (ox + s, oy + s)], closed=True)
    pen.scissors(x + 21, y + 14, 4, angle=0)


def pic_fold_cube(pen, x, y, w, h):
    cx, cy = x + 13, y + 11
    pen.polygon([(cx - 5, cy - 2), (cx, cy - 5), (cx + 6, cy - 2), (cx + 1, cy + 1)], fill=LIGHT, stroke=CUT, width=0.4)
    pen.polygon([(cx - 5, cy - 2), (cx + 1, cy + 1), (cx + 1, cy + 7), (cx - 5, cy + 4)], fill=WHITE, stroke=CUT, width=0.4)
    pen.polygon([(cx + 1, cy + 1), (cx + 6, cy - 2), (cx + 6, cy + 4), (cx + 1, cy + 7)], fill=(0.85, 0.80, 0.92), stroke=CUT, width=0.4)
    pen.arrow(cx + 10, cy - 7, cx + 6, cy - 3, width=0.4, color=MAIN)


def pic_tower(pen, x, y, w, h):
    for i, s in enumerate([6, 5.2, 4.4, 3.6]):
        cy = y + 18 - sum([6, 5.2, 4.4, 3.6][: i + 1]) + s
        pen.rect(x + 13 - s / 2, cy - s, s, s, fill=LIGHT if i % 2 else WHITE, stroke=CUT, width=0.4)
    pen.arrow(x + 4, y + 2, x + 4, y + 17, width=0.4, color=MAIN)


@register
class AlgorithmGuide(Sheet):
    key = "algorithm_guide"
    title = "דף הדרכה: האלגוריתם"
    kind = "instructions"
    station = 5

    def draw(self, pen, page=0):
        y = pen.header(5, "האלגוריתם", "דף הדרכה: ארבע קוביות ומגדל אחד")
        right = PAGE_W - SAFE
        y = pen.legend(y)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=5, title="מה בונים")
        pen.para(right - 4, y + 15, 108, "ארבע קוביות נייר, אחת לכל חלק של ביט: זיכרון, מעבד, תוכנה ורשת. על כל קובייה כתוב מה היא, איזו תחנה תיקנה אותה, וכמה היא שוקלת. בסוף בונים מהן מגדל לפי כלל מיון, וקוראים אותו מלמעלה למטה.", 9.2)
        self.picture(pen, SAFE + 10, y + 10)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את ארבע הפריסות לאורך הקו המלא.", "כל פריסה היא צלב של שישה ריבועים. לא חותכים בין הריבועים: שם מקפלים.", color_key=5, size=10.5, picture=pic_cut_net)
        y = pen.step(2, right, y, col_w, "מקפלים לאורך כל הקווים המקווקווים, הכתוב כלפי חוץ.", "מקפלים קודם את כל הקווים כשהפריסה שטוחה, ואז מרימים את הריבועים לקובייה.", color_key=5, size=10.5, picture=pic_fold_cube)
        y = pen.step(3, right, y, col_w, "סוגרים כל קובייה בסרט הדבקה.", "פיסה קטנה על כל מפגש של שני ריבועים. ארבע קוביות, ארבעה חלקים של ביט.", color_key=5, size=10.5, picture=pic_fold_cube)
        y = pen.step(4, right, y, col_w, "בונים מגדל לפי כלל המיון, וקוראים את מספרי התחנות מלמעלה למטה.", "הסדר שמתקבל הוא הסדר שבו מקלידים את הספרות שארבע התחנות נתנו.", color_key=5, size=10.5, picture=pic_tower)
        y += 1
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 56, color_key=5, title="כלל המיון של ביט")
        pen.para(right - 4, y + 15, PAGE_W - 2 * SAFE - 8,
                 "ביט מורכב מהקל לכבד: הקובייה הקלה ביותר למעלה, הכבדה ביותר למטה.\n"
                 "כלל 1: קל לפני כבד.\n"
                 "כלל 2: מה שאין לו משקל בא לפני כל מה שיש לו משקל.\n"
                 "כשהמגדל עומד, קוראים את מספרי התחנות מהקובייה העליונה לתחתונה. הספרה של התחנה הראשונה שקראתם היא הראשונה בקוד, וכן הלאה. זהו אלגוריתם מיון: כללים ברורים, ותוצאה אחת.", 9.2)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 5 · דף הדרכה")

    def picture(self, pen, x, y):
        for i, size in enumerate([9, 11, 13, 15]):
            cx = x + 12 + i * 20
            pen.rect(cx - size / 2, y + 22 - size, size, size, fill=LIGHT if i % 2 else WHITE, stroke=CUT, width=0.4)
        pen.text(x + 42, y + 29, "ארבע קוביות, ארבעה משקלים", 6.5, color=SOFT, align="center")
