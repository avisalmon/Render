"""SPR-Z.7 / ACT-Z.1: download the curated Pexels photos listed in
stock_manifest.json into memz/seed_assets/<pack-slug>/, alongside the
AI-illustrated batch. Every URL in the manifest was hand-picked from a
Pexels search of its pack's theme — ordinary, non-famous people, animals
or scenes only (see the sprint's own notes on what was deliberately
excluded: public figures, existing meme templates).

Pexels' license (https://www.pexels.com/license/) is free for commercial
use with no attribution required, so the file itself needs nothing beyond
what's already recorded in stock_manifest.json (the source URL per photo)
for spec F-Z.7.1's "licences recorded."

Restart-safe: a file that already exists is never re-downloaded.

    .\\env\\Scripts\\python.exe memz\\seed_assets\\download_stock_images.py
"""

import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "stock_manifest.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) memz-seed-fetch/1.0"}

# Pexels serves full-resolution originals (several MB each); the render
# pipeline never uses more than RENDER_WIDTH (1080) anyway, so this matches
# the site's own upload ceiling (conf.UPLOAD_MAX_SIDE) rather than
# committing ~165MB of source photography for 64 images.
MAX_SIDE = 1600


def _shrink(data):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    w, h = im.size
    if max(w, h) > MAX_SIDE:
        if w >= h:
            im = im.resize((MAX_SIDE, round(h * MAX_SIDE / w)), Image.LANCZOS)
        else:
            im = im.resize((round(w * MAX_SIDE / h), MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    made = skipped = failed = 0
    for slug, urls in manifest.items():
        if slug.startswith("_"):
            continue
        out_dir = HERE / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, url in enumerate(urls, start=1):
            out_path = out_dir / f"{slug}-stock-{i:02d}.jpg"
            if out_path.exists():
                skipped += 1
                continue
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                out_path.write_bytes(_shrink(data))
                made += 1
                print(f"[{made} made, {skipped} skipped] {out_path.name} ({len(data)//1024} KB)", flush=True)
            except Exception as exc:   # noqa: BLE001 - one bad URL must not kill the batch
                failed += 1
                print(f"FAILED {out_path.name}: {exc}", flush=True)
            time.sleep(0.3)   # a light, polite pace against Pexels' CDN
    print(f"done: {made} downloaded, {skipped} already existed, {failed} failed")


if __name__ == "__main__":
    main()
