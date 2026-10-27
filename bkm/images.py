"""A project's photo (REQ-B.31): checked, made small, and stripped.

The photo is re-encoded as a JPEG at most 1600px on its long side, which
also drops its EXIF (a phone photo carries where it was taken). It is then
put through the site's shared safety check, which is free and fails open.
"""

import io

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError

MAX_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600


ROTATIONS = (0, 90, 180, 270)


def clean_rotation(value):
    """Degrees clockwise, one of 0, 90, 180, 270; anything else is 0."""
    try:
        value = int(value or 0) % 360
    except (TypeError, ValueError):
        return 0
    return value if value in ROTATIONS else 0


def prepare(uploaded, user=None, rotate=0):
    """`rotate` turns the photo clockwise by that many degrees, after the
    phone's own orientation is applied (REQ-B.24)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if uploaded.size > MAX_BYTES:
        raise ValidationError("The photo is larger than 10MB.")
    try:
        img = Image.open(uploaded)
        img.draft("RGB", (MAX_SIDE, MAX_SIDE))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("That file is not a photo we can read (JPEG, PNG or WebP).")
    rotate = clean_rotation(rotate)
    if rotate:
        img = img.rotate(-rotate, expand=True)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    img.close()
    data = out.getvalue()
    ok, reason = safe(data, user)
    if not ok:
        raise ValidationError("This photo cannot be shown here. Please choose another one.")
    return ContentFile(data, name="photo.jpg")


def rotate_existing(fieldfile, rotate, user=None):
    """The picture already saved, turned and saved again; no new upload."""
    import io as _io

    fieldfile.open("rb")
    try:
        data = fieldfile.read()
    finally:
        fieldfile.close()
    buf = _io.BytesIO(data)
    buf.size = len(data)
    return prepare(buf, user, rotate)


def safe(data, user=None):
    """The site-wide image moderation (app/safety.py), the one shared check
    every upload on babook goes through. Fails open."""
    try:
        from app.safety import image_is_safe
    except Exception:  # pragma: no cover - the app without the site around it
        return True, ""
    return image_is_safe(io.BytesIO(data), user=user, label="bkm project")
