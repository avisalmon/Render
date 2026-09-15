"""Generate SPR-Z.1's placeholder assets: the public bank's stand-in pictures
and memz's PWA icons. A dev tool, run by hand, its output committed.

    .\\env\\Scripts\\python.exe memz\\seed_assets\\make_assets.py

The pictures are deliberately abstract (flat colours and shapes): they were
here so the bank, the seed, the creator and the game had something to deal
before real content arrived. SPR-Z.7 (ACT-Z.1) replaces them with the
AI-illustrated batch from `generate_bank_images.py`, retired (not deleted)
by `manage.py retire_placeholder_images` — this script is no longer run for
the placeholder images, only for the PWA icons it also makes.
Deterministic, so re-running produces the same files.
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
STATIC = HERE.parents[1] / "static" / "memz"

PALETTES = {
    "family": [("#FFF1D6", "#FF8A5B", "#2B2D42"), ("#E8F4F8", "#2E86AB", "#F6AE2D"), ("#FDE2E4", "#E4572E", "#17BEBB")],
    "animals": [("#E9F5DB", "#588157", "#DAD7CD"), ("#FFF3B0", "#E09F3E", "#335C67"), ("#EDE7F6", "#6A4C93", "#FFCA3A")],
    "work": [("#E0E1DD", "#415A77", "#F4A261"), ("#F7F7F2", "#2A9D8F", "#E76F51"), ("#F1F0EA", "#264653", "#E9C46A")],
    "school": [("#FDF0D5", "#C1121F", "#003049"), ("#E8F1F2", "#13315C", "#EE964B"), ("#F0FFF1", "#3A7D44", "#F9C74F")],
}

# (rounded corners aside) each scene is a few big shapes: enough to give a
# caption something to sit on, nothing that reads as a specific person.
SCENES = ["sun", "hills", "window", "bubble", "stack", "eye"]


def scene(draw, kind, w, h, colors, rng):
    bg, a, b = colors
    draw.rectangle([0, 0, w, h], fill=bg)
    if kind == "sun":
        r = rng.randint(120, 170)
        cx, cy = rng.randint(r, w - r), rng.randint(r, h // 2)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
        draw.rectangle([0, h * 0.68, w, h], fill=b)
    elif kind == "hills":
        for i, col in enumerate((b, a, b)):
            cx = rng.randint(0, w)
            r = rng.randint(260, 420)
            draw.ellipse([cx - r, h * 0.55 + i * 60 - r // 6, cx + r, h * 0.55 + i * 60 + r], fill=col)
    elif kind == "window":
        m = 70
        draw.rectangle([m, m, w - m, h - m], fill=a)
        draw.rectangle([m + 30, m + 30, w // 2 - 15, h // 2 - 15], fill=bg)
        draw.rectangle([w // 2 + 15, m + 30, w - m - 30, h // 2 - 15], fill=bg)
        draw.rectangle([m + 30, h // 2 + 15, w // 2 - 15, h - m - 30], fill=bg)
        draw.rectangle([w // 2 + 15, h // 2 + 15, w - m - 30, h - m - 30], fill=b)
    elif kind == "bubble":
        draw.rounded_rectangle([90, 110, w - 90, h - 200], radius=80, fill=a)
        draw.polygon([(w * 0.3, h - 200), (w * 0.42, h - 200), (w * 0.28, h - 110)], fill=a)
        for i in range(3):
            y = 200 + i * 70
            draw.rounded_rectangle([160, y, w - 160 - i * 90, y + 32], radius=16, fill=bg)
        draw.ellipse([w - 220, 40, w - 60, 200], fill=b)
    elif kind == "stack":
        for i in range(4):
            x0 = 120 + rng.randint(-40, 40)
            y = h - 90 - i * 110
            draw.rounded_rectangle([x0, y - 90, x0 + 440 - i * 30, y], radius=28, fill=(a if i % 2 else b))
    elif kind == "eye":
        draw.ellipse([w * 0.15, h * 0.28, w * 0.85, h * 0.72], fill=a)
        draw.ellipse([w * 0.40, h * 0.38, w * 0.60, h * 0.62], fill=b)
        draw.ellipse([w * 0.47, h * 0.44, w * 0.53, h * 0.50], fill=bg)


def make_bank(per_pack=5, size=(800, 600)):
    rng = random.Random(2026)
    for slug, palettes in PALETTES.items():
        folder = HERE / slug
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(per_pack):
            img = Image.new("RGB", size, "white")
            draw = ImageDraw.Draw(img)
            scene(draw, SCENES[(i + len(slug)) % len(SCENES)], size[0], size[1], palettes[i % len(palettes)], rng)
            out = folder / f"placeholder-{i + 1:02d}.png"
            img.quantize(colors=32).save(out, optimize=True)
            print("wrote", out.relative_to(HERE.parents[1]))


def make_icons():
    STATIC.mkdir(parents=True, exist_ok=True)
    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "icon-180.png")):
        img = Image.new("RGB", (size, size), "#1E1B2E")
        draw = ImageDraw.Draw(img)
        pad = size * 0.14
        # a speech bubble, the shape of a caption
        draw.rounded_rectangle([pad, pad * 1.2, size - pad, size - pad * 1.9], radius=size * 0.16, fill="#FFD23F")
        draw.polygon([(size * 0.32, size - pad * 1.9), (size * 0.48, size - pad * 1.9), (size * 0.30, size - pad * 0.9)],
                     fill="#FFD23F")
        # three "lines of text"
        for i in range(3):
            y = size * 0.34 + i * size * 0.13
            draw.rounded_rectangle([size * 0.26, y, size * 0.74 - i * size * 0.10, y + size * 0.07],
                                   radius=size * 0.035, fill="#1E1B2E")
        img.save(STATIC / name, optimize=True)
        print("wrote", (STATIC / name).relative_to(HERE.parents[1]))


if __name__ == "__main__":
    make_bank()
    make_icons()
