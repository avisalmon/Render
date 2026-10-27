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


def prepare(uploaded, user=None):
    from PIL import Image, ImageOps, UnidentifiedImageError

    if uploaded.size > MAX_BYTES:
        raise ValidationError("The photo is larger than 10MB.")
    try:
        img = Image.open(uploaded)
        img.draft("RGB", (MAX_SIDE, MAX_SIDE))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("That file is not a photo we can read (JPEG, PNG or WebP).")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    img.close()
    data = out.getvalue()
    ok, reason = safe(data, user)
    if not ok:
        raise ValidationError("This photo cannot be shown here. Please choose another one.")
    return ContentFile(data, name="photo.jpg")


def safe(data, user=None):
    """The site-wide image moderation (app/safety.py), the one shared check
    every upload on babook goes through. Fails open."""
    try:
        from app.safety import image_is_safe
    except Exception:  # pragma: no cover - the app without the site around it
        return True, ""
    return image_is_safe(io.BytesIO(data), user=user, label="bkm project")
