"""Draws Books' app icons: a brass lamp over a shelf, on the light ground.

Run once from the repo root (`python books/design_assets/make_icons.py`);
the PNGs are committed. Pillow only, no fonts, so it draws the same on
every machine.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "static" / "books"
GROUND, SURFACE, BRASS, SHADE, BULB, WOOD, INK = (
    "#EFE6D6", "#F8F2E7", "#7A5518", "#A87C34", "#FFE2A0", "#B08A5A", "#241C13")
SPINES = ["#6B2320", "#24384A", "#2E4A3B", "#5A1E1A", "#8A6A2E", "#3C3C3C", "#4A3B5C"]


def draw(size):
    img = Image.new("RGB", (size, size), GROUND)
    d = ImageDraw.Draw(img)
    s = size / 512
    # lamp
    d.line([(256 * s, 40 * s), (256 * s, 110 * s)], fill=SHADE, width=max(2, int(8 * s)))
    d.polygon([(160 * s, 190 * s), (205 * s, 110 * s), (307 * s, 110 * s), (352 * s, 190 * s)], fill=SHADE)
    d.line([(160 * s, 190 * s), (352 * s, 190 * s)], fill=BRASS, width=max(2, int(8 * s)))
    d.ellipse([(206 * s, 180 * s), (306 * s, 212 * s)], fill=BULB)
    # spines on a board
    x = 96 * s
    heights = [150, 170, 140, 180, 130, 165, 155]
    widths = [34, 42, 30, 46, 28, 38, 36]
    for color, h, w in zip(SPINES, heights, widths):
        d.rectangle([(x, 420 * s - h * s), (x + w * s, 420 * s)], fill=color)
        d.line([(x + 4 * s, 440 * s - h * s), (x + w * s - 4 * s, 440 * s - h * s)], fill=BRASS, width=max(1, int(3 * s)))
        x += (w + 6) * s
    d.rectangle([(64 * s, 420 * s), (448 * s, 444 * s)], fill=WOOD)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512, 180):
        draw(size).save(OUT / f"icon-{size}.png", optimize=True)
    # maskable: the same drawing with extra ground around it
    base = draw(400)
    canvas = Image.new("RGB", (512, 512), GROUND)
    canvas.paste(base, (56, 56))
    canvas.save(OUT / "icon-maskable-512.png", optimize=True)


if __name__ == "__main__":
    main()
