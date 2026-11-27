"""Station 2, the processor: three paper gate machines (AND, NOT, OR). Each
is a sleeve with input windows on its front and an output window on its
back, and a slider folded in two lengthwise: the input columns on the half
that faces front, the output column on the half that faces back. Set the
inputs in the front windows, turn the machine over, read the output.

The sheet prints the truth tables on the sliders (that is what a gate is);
how many times Z comes out 1 over the four runs is on the teacher's page only.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_W, PALETTE, SAFE, SOFT, WHITE

MAIN, LIGHT = PALETTE[2]
DARK = (0.3, 0.3, 0.3)

HALF = 22.0  # one half of the slider, mm
ROW = 18.0  # row pitch on the slider
TAB = 15.0  # the pull tab
SLEEVE_PANEL = 26.0
SLEEVE_H = 30.0
GLUE_TAB = 8.0
WINDOW_W, WINDOW_H = 8.0, 12.0

# name, inputs, output, rows of (inputs..., output)
MACHINES = [
    ("וגם", ("א", "ב"), "X", [((0, 0), 0), ((0, 1), 0), ((1, 0), 0), ((1, 1), 1)]),
    ("לא", ("ג",), "Y", [((0,), 1), ((1,), 0)]),
    ("או", ("X", "Y"), "Z", [((0, 0), 0), ((0, 1), 1), ((1, 0), 1), ((1, 1), 1)]),
]
RUNS = [(1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 0)]


def input_columns(n):
    """Centres of the input columns on the front half, from its left edge."""
    return [HALF / 2] if n == 1 else [HALF * 0.3, HALF * 0.7]


def slider_height(rows):
    return 6 + len(rows) * ROW + TAB


def draw_slider(pen, x, y, machine):
    name, inputs, output, rows = machine
    h = slider_height(rows)
    pen.cut_rect(x, y, 2 * HALF, h)
    pen.fold(x + HALF, y, x + HALF, y + h)
    pen.text(x + HALF - 1, y + 4.5, "כניסות", 6, color=SOFT)
    pen.text(x + 2 * HALF - 1, y + 4.5, f"יציאה {output}", 6, color=SOFT)
    cols = input_columns(len(inputs))
    for r, (ins, out) in enumerate(rows):
        yy = y + 6 + r * ROW
        pen.line(x, yy, x + 2 * HALF, yy, width=0.2, color=SOFT)
        for c, value in zip(cols, ins):
            pen.text(x + c, yy + ROW / 2 + 3.2, str(value), 13, bold=True, color=INK, align="center")
        pen.text(x + HALF + HALF / 2, yy + ROW / 2 + 3.2, str(out), 13, bold=True, color=MAIN, align="center")
    ty = y + 6 + len(rows) * ROW
    pen.rect(x, ty, 2 * HALF, TAB, fill=LIGHT, stroke=None)
    pen.text(x + HALF, ty + 6, f"מחליק: {name}", 7.5, bold=True, color=MAIN, align="center")
    pen.text(x + HALF, ty + 11.5, "מקפלים לאורך הקו המקווקו", 5.8, color=SOFT, align="center")


def draw_sleeve(pen, x, y, machine):
    """The unfolded sleeve: glue tab, back panel, front panel, left to right."""
    name, inputs, output, _rows = machine
    w = GLUE_TAB + 2 * SLEEVE_PANEL
    pen.cut_rect(x, y, w, SLEEVE_H)
    pen.glue(x, y, GLUE_TAB, SLEEVE_H, label="דבק", angle=90)
    bx = x + GLUE_TAB  # back panel
    fx = bx + SLEEVE_PANEL  # front panel
    pen.fold(bx, y, bx, y + SLEEVE_H)
    pen.fold(fx, y, fx, y + SLEEVE_H)
    wy = y + (SLEEVE_H - WINDOW_H) / 2 + 2
    # Front: one window per input, over the slider's input columns (the
    # slider sits 2 mm in from the panel's left edge).
    cols = input_columns(len(inputs))
    for c, label in zip(cols, inputs):
        wx = fx + 2 + c - WINDOW_W / 2
        pen.rect(wx, wy, WINDOW_W, WINDOW_H, fill=DARK, stroke=CUT, width=0.4)
        pen.text(fx + 2 + c, y + 5.5, label, 8, bold=True, color=MAIN, align="center")
    pen.text(fx + SLEEVE_PANEL / 2, y + SLEEVE_H - 2, f"חזית · מכונת {name}", 5.8, bold=True, color=INK, align="center")
    # Back: one window, centred on the folded slider.
    bwx = bx + SLEEVE_PANEL / 2 - WINDOW_W / 2
    pen.rect(bwx, wy, WINDOW_W, WINDOW_H, fill=DARK, stroke=CUT, width=0.4)
    pen.text(bx + SLEEVE_PANEL / 2, y + 5.5, f"יציאה {output}", 7, bold=True, color=MAIN, align="center")
    pen.text(bx + SLEEVE_PANEL / 2, y + SLEEVE_H - 2, "גב", 5.5, color=SOFT, align="center")
    # The helper fold through the windows' middle, for cutting them.
    pen.line(x, wy + WINDOW_H / 2, x + w, wy + WINDOW_H / 2, width=0.25, color=MAIN, dash=(0.6, 1.2))


@register
class ProcessorMachines(Sheet):
    key = "processor_machines"
    title = "שלוש מכונות שערים: שרוולים ומחליקים"
    kind = "cut_out"
    station = 2

    def draw(self, pen, page=0):
        y0 = pen.header(2, "המעבד", "דף עבודה: שלוש מכונות שערים")
        y0 = pen.legend(y0)
        xs = [12, 75, 138]
        for x, machine in zip(xs, MACHINES):
            draw_sleeve(pen, x, y0 + 2, machine)
        pen.text(PAGE_W - SAFE, y0 + 2 + SLEEVE_H + 5, "למעלה: השרוולים. למטה: המחליקים. חלון כהה = גוזרים אותו החוצה.", 7, color=SOFT)
        ys = y0 + 2 + SLEEVE_H + 10
        for x, machine in zip([20, 84, 148], MACHINES):
            draw_slider(pen, x, ys, machine)
        # The run table: the player's worksheet piece.
        ty = ys + slider_height(MACHINES[0][3]) + 10
        self.run_table(pen, ty)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 2 · דף עבודה")

    def run_table(self, pen, y):
        right = PAGE_W - SAFE
        pen.text(right, y + 4, "טבלת ההרצות: ממלאים את X, Y ו-Z מהמכונות", 9, bold=True, color=MAIN)
        y += 8
        heads = ["הרצה", "א", "ב", "ג", "X = א וגם ב", "Y = לא ג", "Z = X או Y"]
        widths = [16, 14, 14, 14, 40, 32, 40]
        x = right
        cells = []
        for head, w in zip(heads, widths):
            cells.append((x - w, w))
            x -= w
        row_h = 11
        for r in range(len(RUNS) + 1):
            yy = y + r * row_h
            for (cx, w), head in zip(cells, heads):
                pen.rect(cx, yy, w, row_h, fill=LIGHT if r == 0 else None, stroke=SOFT, width=0.3)
            if r == 0:
                for (cx, w), head in zip(cells, heads):
                    pen.text(cx + w / 2, yy + 7.2, head, 7.5, bold=True, color=INK, align="center")
            else:
                a, b, c = RUNS[r - 1]
                for (cx, w), value in zip(cells[:4], [str(r), str(a), str(b), str(c)]):
                    pen.text(cx + w / 2, yy + 7.6, value, 10, bold=r == 0, color=INK, align="center")
        pen.text(right, y + (len(RUNS) + 1) * row_h + 6, "בכמה הרצות Z יצא 1? זה המספר שמחפשים בתחנה הזאת.", 8, color=INK)


# ------------------------------------------------------------------ guide


def pic_cut_strip(pen, x, y, w, h):
    pen.rect(x + 7, y + 2, 12, h - 4, fill=WHITE, stroke=CUT, width=0.5)
    pen.fold(x + 13, y + 2, x + 13, y + h - 2)
    for i in range(3):
        pen.text(x + 10, y + 6 + i * 5, "1" if i == 1 else "0", 4.5, align="center")
        pen.text(x + 16, y + 6 + i * 5, "0" if i < 2 else "1", 4.5, color=MAIN, align="center")
    pen.scissors(x + 3, y + h / 2, 4.5, angle=0)


def pic_fold_strip(pen, x, y, w, h):
    pen.polygon([(x + 8, y + 3), (x + 14, y + 3), (x + 14, y + h - 3), (x + 8, y + h - 3)], fill=WHITE, stroke=CUT, width=0.5)
    pen.polygon([(x + 14, y + 3), (x + 18, y + 6), (x + 18, y + h), (x + 14, y + h - 3)], fill=LIGHT, stroke=CUT, width=0.5)
    pen.arrow(x + 22, y + 4, x + 16, y + 8, width=0.4, color=MAIN)


def pic_sleeve(pen, x, y, w, h):
    pen.rect(x + 2, y + 5, 20, 10, fill=WHITE, stroke=CUT, width=0.5)
    pen.fold(x + 5, y + 5, x + 5, y + 15)
    pen.fold(x + 13.5, y + 5, x + 13.5, y + 15)
    pen.rect(x + 7.5, y + 8, 3, 4, fill=DARK, stroke=None)
    pen.rect(x + 16, y + 8, 2.5, 4, fill=DARK, stroke=None)
    pen.rect(x + 19.5, y + 8, 2.5, 4, fill=DARK, stroke=None)
    pen.scissors(x + 11, y + 17.5, 4, angle=90)


def pic_tube(pen, x, y, w, h):
    pen.rect(x + 7, y + 4, 12, 12, fill=WHITE, stroke=CUT, width=0.5)
    pen.polygon([(x + 7, y + 4), (x + 10, y + 1), (x + 22, y + 1), (x + 19, y + 4)], fill=LIGHT, stroke=CUT, width=0.4)
    pen.polygon([(x + 19, y + 4), (x + 22, y + 1), (x + 22, y + 13), (x + 19, y + 16)], fill=LIGHT, stroke=CUT, width=0.4)
    pen.rect(x + 10, y + 8, 2.5, 4, fill=DARK, stroke=None)
    pen.rect(x + 14, y + 8, 2.5, 4, fill=DARK, stroke=None)


def pic_insert(pen, x, y, w, h):
    pen.rect(x + 8, y + 7, 12, 10, fill=WHITE, stroke=CUT, width=0.5)
    pen.rect(x + 11.5, y + 1, 5, 17, fill=LIGHT, stroke=CUT, width=0.4)
    pen.rect(x + 11, y + 10, 2.5, 4, fill=DARK, stroke=None)
    pen.rect(x + 15, y + 10, 2.5, 4, fill=DARK, stroke=None)
    pen.arrow(x + 14, y + 1, x + 14, y + 6, width=0.5, color=MAIN)


def pic_flip(pen, x, y, w, h):
    pen.rect(x + 2, y + 5, 9, 10, fill=WHITE, stroke=CUT, width=0.5)
    pen.text(x + 4.5, y + 11.5, "1", 5, bold=True, align="center")
    pen.text(x + 8.5, y + 11.5, "0", 5, bold=True, align="center")
    pen.rect(x + 15, y + 5, 9, 10, fill=LIGHT, stroke=CUT, width=0.5)
    pen.text(x + 19.5, y + 11.5, "0", 5, bold=True, color=MAIN, align="center")
    pen.arrow(x + 11.5, y + 3, x + 14.5, y + 3, width=0.4, color=MAIN)
    pen.arc(x + 13, y + 10, 2.5, 0, 180, width=0.4, color=MAIN)


@register
class ProcessorGuide(Sheet):
    key = "processor_guide"
    title = "דף הדרכה: המעבד"
    kind = "instructions"
    station = 2

    def draw(self, pen, page=0):
        y = pen.header(2, "המעבד", "דף הדרכה: שלוש מכונות שערים")
        right = PAGE_W - SAFE
        y = pen.legend(y)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=2, title="מה בונים")
        pen.para(right - 4, y + 15, 100, "שלוש מכונות נייר, אחת לכל שער: וגם (AND), לא (NOT), או (OR). לכל מכונה שרוול עם חלונות ומחליק שעובר בתוכו. בחזית מכוונים את הכניסות, הופכים את המכונה, ובגב מופיעה היציאה. המעבד של ביט הוא בדיוק שלוש כאלה, מחוברות.", 8.2)
        self.picture(pen, SAFE + 6, y + 8)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את שלושת המחליקים (הפסים הארוכים).", "על כל מחליק: עמודת כניסות משמאל, עמודת יציאה מימין, ולשונית משיכה צבעונית למטה.", color_key=2, picture=pic_cut_strip)
        y = pen.step(2, right, y, col_w, "מקפלים כל מחליק לאורך הקו המקווקו, כך ששני הצדדים המודפסים פונים החוצה.", "הכניסות מקדימה, היציאה מאחור. לוחצים על הקיפול.", color_key=2, picture=pic_fold_strip)
        y = pen.step(3, right, y, col_w, "גוזרים את שלושת השרוולים, וגוזרים החוצה את החלונות הכהים.", "דרך קלה: מקפלים את השרוול קיפול עדין לאורך הקו הכתום הדק שעובר באמצע החלונות, גוזרים חצי חלון מהקיפול, ומיישרים. או מנקבים בקצה המספריים.", color_key=2, picture=pic_sleeve)
        y = pen.step(4, right, y, col_w, "מקפלים את השרוול לאורך שני הקווים המקווקווים ומדביקים את הלשונית האפורה מאחור.", "מתקבלת טבעת שטוחה: חזית עם חלונות הכניסה, גב עם חלון היציאה.", color_key=2, picture=pic_tube)
        y = pen.step(5, right, y, col_w, "משחילים את המחליק המקופל לתוך השרוול, הלשונית הצבעונית למטה.", "הכניסות צריכות להופיע בחלונות שבחזית. אם רואים את היציאה מקדימה, הופכים את המחליק.", color_key=2, picture=pic_insert)
        y = pen.step(6, right, y, col_w, "מכוונים, הופכים, קוראים.", "מושכים את המחליק עד שבחלונות החזית מופיעות הכניסות שרוצים. הופכים את המכונה: בחלון הגב כתובה היציאה.", color_key=2, picture=pic_flip)
        y += 1
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=2, title="איך משתמשים: מריצים את המעגל ארבע פעמים")
        pen.para(right - 4, y + 15, PAGE_W - 2 * SAFE - 8,
                 "המעגל: X = א וגם ב. Y = לא ג. Z = X או Y. לכל הרצה בטבלה: מכוונים את א ו-ב במכונת וגם וקוראים את X; מכוונים את ג במכונת לא וקוראים את Y; מכוונים את X ו-Y במכונת או וקוראים את Z. רושמים בטבלה.\n"
                 "דוגמה שלא בטבלה: א=0, ב=0, ג=0. מכונת וגם: 0 ו-0 נותנים X=0. מכונת לא: ג=0 נותנת Y=1. מכונת או: 0 ו-1 נותנים Z=1.", 8.2)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 2 · דף הדרכה")

    def picture(self, pen, x, y):
        for i, (name, inputs, output, _rows) in enumerate(MACHINES):
            mx = x + i * 26
            pen.rect(mx + 4, y + 10, 16, 14, fill=WHITE, stroke=CUT, width=0.5)
            pen.rect(mx + 9, y + 2, 6, 26, fill=LIGHT, stroke=CUT, width=0.4)
            for j, _label in enumerate(inputs):
                wx = mx + 12 - (len(inputs) - 1) * 2.5 + j * 5 - 1.5
                pen.rect(wx, y + 14, 3, 5, fill=DARK, stroke=None)
            pen.text(mx + 12, y + 33, name, 7, bold=True, color=MAIN, align="center")
