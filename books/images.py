"""Preparing an uploaded photo for Books (spec BK1 §1.6, 12.9).

One pass does three things, in this order, and a test pins each:
1. reads the GPS point from the EXIF, if any, and keeps it only rounded to a
   neighbourhood (the same two decimals Profile uses);
2. turns the image the right way up and shrinks it to a sane size;
3. writes a fresh JPEG with **no metadata at all**, so the precise point, the
   camera, the timestamp and everything else never reach storage.

iPhone HEIC opens through pillow-heif when it is installed (it is, for memz).
"""

import io
from dataclasses import dataclass
from decimal import Decimal

from PIL import Image, ImageOps

from .models import round_coordinate

try:  # pragma: no cover - depends on the wheel being present
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    pass

MAX_SIDE = 2000
JPEG_QUALITY = 85
GPS_IFD = 0x8825


@dataclass
class Prepared:
    data: bytes
    width: int
    height: int
    area_lat: Decimal | None
    area_lng: Decimal | None
    had_gps: bool

    @property
    def content_type(self):
        return "image/jpeg"


def _to_degrees(value):
    d, m, s = (float(v) for v in value)
    return d + m / 60 + s / 3600


def read_gps(img):
    """(lat, lng) as floats, or None. Never raises on a strange EXIF."""
    try:
        gps = img.getexif().get_ifd(GPS_IFD)
        if not gps:
            return None
        lat = _to_degrees(gps[2])
        lng = _to_degrees(gps[4])
        if str(gps.get(1, "N")).upper().startswith("S"):
            lat = -lat
        if str(gps.get(3, "E")).upper().startswith("W"):
            lng = -lng
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None
        return lat, lng
    except Exception:  # noqa: BLE001
        return None


def prepare(uploaded, max_side=MAX_SIDE):
    """Takes a file-like or bytes. Returns Prepared."""
    raw = uploaded.read() if hasattr(uploaded, "read") else uploaded
    img = Image.open(io.BytesIO(raw))
    point = read_gps(img)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    # No exif= argument: nothing from the original travels into the copy.
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    lat = lng = None
    if point is not None:
        lat, lng = round_coordinate(point[0]), round_coordinate(point[1])
    return Prepared(out.getvalue(), img.width, img.height, lat, lng, point is not None)
