"""The meme engine (spec §8.1). One function, `render`, used by the solo
creator (SPR-Z.2) and, from SPR-Z.3, by every game submission.

Layout: a caption bar above the image — a solid band, bold black text,
centred, wrapped to the width, shrunk from `RENDER_FONT_MAX` to
`RENDER_FONT_MIN` to fit `CAPTION_MAX_LINES`. Chosen over classic
top/bottom Impact-with-outline for the reasons spec §8.1 gives: readable
on any image at phone size, no Hebrew Impact tradition to honour, and no
stroke rendering needed.

Text is laid out with `python-bidi`'s `get_display` before drawing, so a
Hebrew caption with an embedded English word or a number renders in the
right visual order — PIL's `ImageDraw.text` has no bidi awareness of its
own and draws whatever string it is handed strictly left to right, so the
string it is handed must already be in visual order. The base direction is
always pinned to RTL (`base_dir="R"`, 2026-09-16 QA fix) rather than left
to `get_display`'s own auto-detection, which guesses from the first
*strong* character and silently flips the whole line backwards for
anything starting with an English word, a digit, an emoji or a quote mark
-- ordinary things to type, and always wrong here, since memz captions are
never anything but a Hebrew-first RTL paragraph. Wrapping happens
*before* that reordering, on the logical text: a word's rendered width is
the same regardless of which direction the line reads, so greedy wrapping
on the logical (typed) word order is correct and simpler than wrapping the
reordered string.
"""

import io

from bidi.algorithm import get_display
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from . import conf

FONT_PATH = settings.BASE_DIR / "static" / "memz" / "fonts" / "Heebo-Black.ttf"

BAR_BG = (255, 255, 255)
BAR_INK = (17, 17, 17)
BAR_PAD_X = 36
BAR_PAD_Y = 28
LINE_SPACING = 1.18
WATERMARK_TEXT = "memz"
WATERMARK_OPACITY = 102  # 40% of 255 (spec §8.1)


def _font(size):
    return ImageFont.truetype(str(FONT_PATH), size)


def _line_width(font, line):
    # Bidi reordering doesn't change glyph widths, only their order, so the
    # *logical* string's width is what a wrap decision needs.
    return font.getlength(line)


def wrap_caption(text, font, max_width):
    """Greedy word-wrap on the logical (typed) text. Returns logical-order
    lines; bidi reordering happens per line at draw time, not here."""
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _line_width(font, candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_caption(text, max_width, max_lines=None):
    """The largest size (in `RENDER_FONT_MAX`..`RENDER_FONT_MIN`, step 2)
    that wraps `text` into at most `max_lines` lines within `max_width`.
    Falls back to the floor size, truncating the last line with an
    ellipsis, if nothing fits — the caption input is meant to prevent
    this (spec §5.2), so this is a safety net, not the normal path."""
    max_lines = max_lines or conf.get("CAPTION_MAX_LINES")
    hi, lo = conf.get("RENDER_FONT_MAX"), conf.get("RENDER_FONT_MIN")
    for size in range(hi, lo - 1, -2):
        font = _font(size)
        lines = wrap_caption(text, font, max_width)
        # A line count within budget isn't enough: a single word longer
        # than `max_width` (no space to break on) still comes back as one
        # "line" from wrap_caption at every size, so the width itself has
        # to be checked too, or an overlong word would never shrink.
        if len(lines) <= max_lines and all(_line_width(font, line) <= max_width for line in lines):
            return size, lines

    font = _font(lo)
    lines = wrap_caption(text, font, max_width)[:max_lines]
    last = lines[-1]
    while last and _line_width(font, last + "…") > max_width:
        last = last[:-1]
    lines[-1] = (last + "…") if last != lines[-1] else last
    return lo, lines


def shape_for_draw(line):
    """Logical (typed) order -> visual (drawn) order, for PIL's own
    bidi-blind `ImageDraw.text`.

    `base_dir="R"` is pinned deliberately, not left to `get_display`'s own
    auto-detection (2026-09-16 QA fix): with no `base_dir`, it guesses the
    paragraph's direction from its *first strong character*, so a caption
    starting with an English word, a digit, an emoji or a quote mark --
    all ordinary things to type -- got silently treated as an LTR
    paragraph with an embedded Hebrew run, which reordered the whole line
    backwards. memz captions are always a Hebrew-first RTL product; the
    base direction is never actually in question, so it should never be
    guessed."""
    return get_display(line, base_dir="R")


def _draw_caption_bar(width, text):
    """The white band: measured first (to know its height), drawn second."""
    max_width = width - 2 * BAR_PAD_X
    size, lines = fit_caption(text, max_width)
    font = _font(size)
    line_height = int(size * LINE_SPACING)
    bar_height = 2 * BAR_PAD_Y + line_height * len(lines)

    bar = Image.new("RGB", (width, bar_height), BAR_BG)
    draw = ImageDraw.Draw(bar)
    y = BAR_PAD_Y
    for line in lines:
        draw.text((width / 2, y), shape_for_draw(line), font=font, fill=BAR_INK, anchor="ma")
        y += line_height
    return bar


def _fit_image(image, width):
    """Scale the source image to the render width, preserving aspect ratio."""
    w, h = image.size
    if w == width:
        return image
    height = round(h * (width / w))
    return image.resize((width, height), Image.LANCZOS)


def _apply_watermark(canvas):
    """A small 'memz' mark, bottom corner, 40% opacity — guest memes only
    (spec §8.1, the one place the free tier shows in the output)."""
    size = max(20, canvas.width // 28)
    font = _font(size)
    mark = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(mark)
    margin = size // 2
    draw.text(
        (canvas.width - margin, canvas.height - margin), WATERMARK_TEXT,
        font=font, fill=(255, 255, 255, WATERMARK_OPACITY), anchor="rs",
        stroke_width=max(1, size // 20), stroke_fill=(0, 0, 0, WATERMARK_OPACITY),
    )
    return Image.alpha_composite(canvas.convert("RGBA"), mark).convert("RGB")


def render(source_file, caption_text, *, watermark=False):
    """Compose a meme from an open image file and a caption. Returns
    (jpeg_bytes, width, height). `source_file` is anything Pillow's
    `Image.open` accepts (a Django `FieldFile`, a path, a stream)."""
    width = conf.get("RENDER_WIDTH")
    with Image.open(source_file) as src:
        src.load()
        image = _fit_image(src.convert("RGB"), width)

    bar = _draw_caption_bar(width, caption_text or "")
    canvas = Image.new("RGB", (width, bar.height + image.height), BAR_BG)
    canvas.paste(bar, (0, 0))
    canvas.paste(image, (0, bar.height))

    if watermark:
        canvas = _apply_watermark(canvas)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue(), canvas.width, canvas.height
