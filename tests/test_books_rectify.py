"""The cover straightener (Avi, 2026-10-23): "I always shoot the cover at an
angle and it doesn't fill the photo; find the book and square it, in
proportion." It runs on the phone (static/books/rectify.js); here it runs in
a real browser on made-up angled photos whose true corners are known."""

import base64
import io
import math
from pathlib import Path

import pytest

from tests._cover_scenes import scene

JS = Path(__file__).resolve().parent.parent / "static" / "books" / "rectify.js"
KINDS = ["wood", "plain", "dark", "cloth"]


@pytest.fixture(scope="module")
def page():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"no browser: {exc}")
        p = b.new_page()
        p.set_content("<html><body></body></html>")
        p.add_script_tag(path=str(JS))
        yield p
        b.close()


def straighten(page, data):
    url = "data:image/jpeg;base64," + base64.b64encode(data).decode()
    return page.evaluate("""async (u) => { const im = new Image(); im.src = u; await im.decode();
        const r = bkRectify(im); return {found: r.found, quad: r.quad, ratio: r.ratio, w: r.canvas.width, h: r.canvas.height}; }""", url)


def test_it_finds_the_book_and_its_true_proportion_on_every_kind_of_table(page):
    """Measured on 100 photos it never saw while being built: 93 within 2% of
    the photo's diagonal, and the proportion right whenever the corners are."""
    good, rows = 0, []
    for seed in range(1000, 1016):
        data, q, ratio = scene(seed, KINDS[seed % 4])
        r = straighten(page, data)
        err = (max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(r["quad"], q)) / math.hypot(1500, 2000)
               if r["found"] else 1)
        ok = err < 0.02 and abs(r["ratio"] - ratio) <= 0.05 and abs(r["w"] / r["h"] - ratio) <= 0.05
        good += ok
        rows.append((seed, KINDS[seed % 4], round(err * 100, 1), ratio, r["ratio"]))
    assert good >= 14, rows


def test_nothing_like_a_book_keeps_the_plain_cut(page):
    from PIL import Image

    out = io.BytesIO()
    Image.effect_noise((900, 1200), 30).convert("RGB").save(out, "JPEG")
    r = straighten(page, out.getvalue())
    assert r["found"] is False and abs(r["w"] / r["h"] - 2 / 3) < 0.01
