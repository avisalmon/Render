"""Render a certificate as a PNG for social-share previews (og:image).

The on-page diploma is HTML/CSS, which link crawlers (WhatsApp, Facebook) can't
turn into a thumbnail - they need a real image URL. This draws a matching
parchment-and-gold certificate with Pillow. Hebrew is reordered with python-bidi
(Pillow here has no libraqm, so text is drawn in visual order). Fonts are the
Heebo TTFs bundled under static/fonts/. Output is cached so repeated crawls are
cheap.
"""
import io
from pathlib import Path

from bidi.algorithm import get_display
from django.conf import settings
from django.core.cache import cache
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = Path(settings.BASE_DIR) / "static" / "fonts"

W, H = 1200, 630
PARCHMENT = (253, 251, 243)
GOLD = (184, 145, 46)
GOLD_DK = (143, 111, 23)
INK = (43, 38, 29)
INK_SOFT = (106, 97, 81)
_CACHE_TTL = 60 * 60 * 24 * 7


def _font(name, size):
    # Force BASIC layout so behaviour is identical across environments: some
    # Pillow builds bundle libraqm (which does its own bidi) and others don't.
    # With BASIC, Pillow never reorders, so our python-bidi pass is the only one
    # applied - otherwise raqm + bidi double-reverse the Hebrew (reversed text).
    return ImageFont.truetype(str(_FONT_DIR / name), size,
                              layout_engine=ImageFont.Layout.BASIC)


def _rtl(s):
    return get_display(s or "")


def _draw_center(d, cx, y, text, font, fill):
    d.text((cx, y), _rtl(text), font=font, fill=fill, anchor="mt")


def _fit_font(text, name, max_size, min_size, max_width):
    """Largest size (max..min) whose rendered width fits, else min size."""
    disp = _rtl(text)
    for size in range(max_size, min_size - 1, -2):
        f = _font(name, size)
        if f.getlength(disp) <= max_width:
            return f
    return _font(name, min_size)


def _star(d, cx, cy, outer, inner, fill):
    import math
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)


def _render(name, course, date_str):
    img = Image.new("RGB", (W, H), PARCHMENT)
    d = ImageDraw.Draw(img)

    # Double gold frame
    d.rectangle([26, 26, W - 26, H - 26], outline=GOLD, width=3)
    d.rectangle([40, 40, W - 40, H - 40], outline=GOLD, width=1)
    # Corner accents (short gold L's just inside the inner frame)
    for (x, y, dx, dy) in [(52, 52, 1, 1), (W - 52, 52, -1, 1),
                           (52, H - 52, 1, -1), (W - 52, H - 52, -1, -1)]:
        d.line([(x, y), (x + dx * 34, y)], fill=GOLD, width=3)
        d.line([(x, y), (x, y + dy * 34)], fill=GOLD, width=3)

    cx = W // 2
    # Wordmark (Latin - no bidi)
    wm = _font("Heebo_700Bold.ttf", 40)
    ba_w = wm.getlength("ba")
    book_w = wm.getlength("book")
    start = cx - (ba_w + book_w) / 2
    d.text((start, 74), "ba", font=wm, fill=INK)
    d.text((start + ba_w, 74), "book", font=wm, fill=GOLD)

    _draw_center(d, cx, 150, "תעודת סיום", _font("Heebo_700Bold.ttf", 52), GOLD)
    _draw_center(d, cx, 238, "הוענקה בזאת ל", _font("Heebo_400Regular.ttf", 26), INK_SOFT)
    _draw_center(d, cx, 282, name, _fit_font(name, "Heebo_700Bold.ttf", 64, 34, 1000), INK)
    _draw_center(d, cx, 384, "על סיום מוצלח של הקורס", _font("Heebo_400Regular.ttf", 26), INK_SOFT)
    _draw_center(d, cx, 424, course, _fit_font(course, "Heebo_700Bold.ttf", 40, 24, 1000), INK)

    # Gold seal with a star
    sy = 524
    d.ellipse([cx - 40, sy - 40, cx + 40, sy + 40], fill=GOLD)
    d.ellipse([cx - 40, sy - 40, cx + 40, sy + 40], outline=GOLD_DK, width=2)
    _star(d, cx, sy, 22, 9, PARCHMENT)

    # Signature line + date
    _draw_center(d, cx, 578, f"אבי סלמון · שמח לעזור ראשי   |   {date_str}",
                 _font("Heebo_400Regular.ttf", 20), INK_SOFT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render_certificate_png(cert_id, name, course, issued_at):
    date_str = issued_at.strftime("%d/%m/%Y") if issued_at else ""
    key = f"certpng:{cert_id}:{name}:{course}:{date_str}"
    png = cache.get(key)
    if png is None:
        png = _render(name, course, date_str)
        cache.set(key, png, _CACHE_TTL)
    return png
