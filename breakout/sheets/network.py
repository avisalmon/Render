"""Station 4, the network: the message as seven packet strips. Each strip
becomes a ring, each ring passes through the one before it, and the chain,
in packet order, reads the message. One packet never arrived; the sheet
does not say which.
"""

from . import Sheet, register
from .toolkit import CUT, INK, PAGE_W, PALETTE, SAFE, SOFT, WHITE

MAIN, LIGHT = PALETTE[4]
STRIP_W, STRIP_H, GLUE_W, HEAD_W = 180.0, 22.0, 14.0, 24.0

# Packet number -> its words. Packet 6 ("היחידה") was lost on the way.
PACKETS = {
    1: "מהנדסים,",
    2: "החבילות שלי",
    3: "לא כולן הגיעו.",
    4: "הספרה שאתם מחפשים",
    5: "היא מספר החבילה",
    7: "שאבדה",
    8: "בדרך.",
}
PRINT_ORDER = [3, 7, 1, 5, 8, 2, 4]
BANDS = [(0.95, 0.55, 0.20), (0.20, 0.55, 0.85), (0.85, 0.30, 0.40), (0.55, 0.40, 0.80), (0.20, 0.65, 0.60), (0.90, 0.75, 0.15), (0.45, 0.60, 0.25)]


def draw_strip(pen, x, y, number, text, band):
    pen.cut_rect(x, y, STRIP_W, STRIP_H)
    # Right end: the glue tab, then the packet header.
    pen.glue(x + STRIP_W - GLUE_W, y, GLUE_W, STRIP_H, label="דבק", angle=90)
    hx = x + STRIP_W - GLUE_W - HEAD_W
    pen.rect(hx, y, HEAD_W, STRIP_H, fill=LIGHT, stroke=None)
    pen.line(hx, y, hx, y + STRIP_H, width=0.3, color=SOFT)
    pen.text(hx + HEAD_W / 2, y + 7, "חבילה", 6.5, color=SOFT, align="center")
    pen.text(hx + HEAD_W / 2, y + 18, str(number), 15, bold=True, color=MAIN, align="center")
    # Left end: a colour band, so a photo of the chain is colourful.
    pen.rect(x, y, 8, STRIP_H, fill=band, stroke=None)
    # The words, big, in the middle.
    pen.text(x + 8 + (hx - x - 8) / 2, y + STRIP_H / 2 + 4.5, text, 16, bold=True, color=INK, align="center")


@register
class NetworkStrips(Sheet):
    key = "network_strips"
    title = "שבע חבילות: הפסים לשרשרת"
    kind = "cut_out"
    station = 4

    def draw(self, pen, page=0):
        y0 = pen.header(4, "הרשת", "דף עבודה: החבילות שהגיעו")
        y0 = pen.legend(y0)
        x = (PAGE_W - STRIP_W) / 2
        for i, number in enumerate(PRINT_ORDER):
            draw_strip(pen, x, y0 + 2 + i * (STRIP_H + 4), number, PACKETS[number], BANDS[i])
        y = y0 + 2 + len(PRINT_ORDER) * (STRIP_H + 4) + 4
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 46, color_key=4, title="מפס לטבעת, מטבעת לשרשרת")
        pen.para(PAGE_W - SAFE - 4, y + 15, 110,
                 "כל פס נהיה טבעת: מכופפים אותו, הקצה הצבעוני נדבק על הלשונית האפורה, המילים בחוץ. הטבעת של החבילה הבאה עוברת דרך הטבעת שלפניה ורק אז נסגרת. מסדרים לפי מספרי החבילות, 1 ראשונה, ואז קוראים את השרשרת טבעת אחרי טבעת.", 8)
        self.chain(pen, SAFE + 8, y + 14)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 4 · דף עבודה")

    def chain(self, pen, x, y):
        for i in range(4):
            cx = x + 8 + i * 13
            pen.circle(cx, y + 14, 8, fill=None, stroke=BANDS[i], width=1.6)
            pen.text(cx, y + 15.5, str(i + 1), 5.5, bold=True, color=SOFT, align="center")


# ------------------------------------------------------------------ guide


def pic_cut_strips(pen, x, y, w, h):
    for i in range(3):
        pen.rect(x + 3, y + 3 + i * 5.5, 20, 4, fill=WHITE, stroke=CUT, width=0.4)
        pen.rect(x + 3, y + 3 + i * 5.5, 1.5, 4, fill=BANDS[i], stroke=None)
    pen.scissors(x + 24, y + 10, 4, angle=0)


def pic_ring(pen, x, y, w, h):
    pen.rect(x + 2, y + 7, 10, 3, fill=WHITE, stroke=CUT, width=0.4)
    pen.arrow(x + 12.5, y + 5, x + 16, y + 5, width=0.4, color=MAIN)
    pen.circle(x + 20, y + 10, 4.5, fill=None, stroke=CUT, width=0.8)


def pic_link(pen, x, y, w, h):
    pen.circle(x + 8, y + 10, 4.5, fill=None, stroke=BANDS[0], width=1.2)
    pen.circle(x + 14, y + 10, 4.5, fill=None, stroke=BANDS[1], width=1.2)
    pen.circle(x + 20, y + 10, 4.5, fill=None, stroke=BANDS[2], width=1.2)


def pic_read(pen, x, y, w, h):
    for i in range(3):
        pen.circle(x + 7 + i * 6, y + 9, 4, fill=None, stroke=CUT, width=0.6)
        pen.text(x + 7 + i * 6, y + 10.3, str(i + 1), 4, bold=True, color=MAIN, align="center")
    pen.arrow(x + 22, y + 16, x + 4, y + 16, width=0.4, color=MAIN)


@register
class NetworkGuide(Sheet):
    key = "network_guide"
    title = "דף הדרכה: הרשת"
    kind = "instructions"
    station = 4

    def draw(self, pen, page=0):
        y = pen.header(4, "הרשת", "דף הדרכה: שרשרת החבילות")
        right = PAGE_W - SAFE
        y = pen.legend(y)
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 44, color_key=4, title="מה בונים")
        pen.para(right - 4, y + 15, 108, "שרשרת נייר. ברשת, הודעה נחתכת לחבילות ממוספרות, וכל אחת מגיעה בדרך אחרת ובזמן אחר. אצלכם כל חבילה היא פס נייר שנהיה טבעת, והטבעות משתרשרות לפי המספרים. כשהשרשרת מסודרת, ההודעה של ביט נקראת עליה טבעת אחרי טבעת.", 9.2)
        self.picture(pen, SAFE + 8, y + 12)
        y += 49
        col_w = PAGE_W - 2 * SAFE
        y = pen.step(1, right, y, col_w, "גוזרים את שבעת הפסים לאורך הקווים המלאים.", "על כל פס: פס צבע בקצה אחד, לשונית דבק אפורה בקצה השני, ומספר החבילה ליד הלשונית.", color_key=4, size=10.5, picture=pic_cut_strips)
        y = pen.step(2, right, y, col_w, "מסדרים את הפסים לפי מספרי החבילות, מהקטן לגדול.", "קוראים את המספרים לפני שמדביקים משהו. שימו לב אם משהו חסר בספירה.", color_key=4, size=10.5, picture=pic_read)
        y = pen.step(3, right, y, col_w, "את הפס הראשון סוגרים לטבעת: הקצה הצבעוני על הלשונית האפורה, המילים בחוץ.", "דבק סטיק או סרט הדבקה, שניהם טובים. מחזיקים כמה שניות.", color_key=4, size=10.5, picture=pic_ring)
        y = pen.step(4, right, y, col_w, "כל פס הבא משחילים דרך הטבעת הקודמת, ורק אז סוגרים אותו לטבעת.", "ככה נבנית שרשרת: 1, ודרכה 2, ודרכה 3, וכן הלאה. אם קפצתם על מספר, זה יורגש.", color_key=4, size=10.5, picture=pic_link)
        y += 1
        pen.box(SAFE, y, PAGE_W - 2 * SAFE, 46, color_key=4, title="איך קוראים את ההודעה")
        pen.para(right - 4, y + 15, PAGE_W - 2 * SAFE - 8,
                 "מותחים את השרשרת על השולחן, החבילה 1 מימין, וקוראים את המילים טבעת אחרי טבעת. ההודעה של ביט אומרת לכם בעצמה איך למצוא את הספרה של התחנה.\n"
                 "ככה עובדת רשת אמיתית: המחשב שמקבל חבילות מסדר אותן לפי המספרים, ואם מספר חסר, הוא יודע בדיוק מה לבקש שוב.", 9.2)
        pen.footer("חדרי בריחה מנייר · המחשב שנכבה · תחנה 4 · דף הדרכה")

    def picture(self, pen, x, y):
        for i in range(5):
            cx = x + 8 + i * 13
            pen.circle(cx, y + 10, 7.5, fill=None, stroke=BANDS[i], width=1.6)
            pen.text(cx, y + 11.5, str(i + 1), 5.5, bold=True, color=SOFT, align="center")
