"""Image processing helpers (REQ-6.1.13).

Avatars are downscaled + recompressed server-side on upload, so members never
hit a "too large" wall - any reasonable photo (incl. straight off a phone) is
accepted and stored as a small, web-friendly JPEG.
"""
import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

AVATAR_MAX_PX = 512      # avatars render as small circles; 512 is plenty
AVATAR_QUALITY = 85
MAX_INPUT_BYTES = 15 * 1024 * 1024  # sanity cap before we even open the file


def process_avatar(uploaded, max_px=AVATAR_MAX_PX, quality=AVATAR_QUALITY):
    """Return (ContentFile, filename) for a downscaled JPEG of `uploaded`.

    Raises ValueError if the file is not a decodable image.
    """
    try:
        img = Image.open(uploaded)
        img = ImageOps.exif_transpose(img)  # honor phone orientation
    except Exception as exc:  # noqa: BLE001 - any decode failure = not an image
        raise ValueError("not an image") from exc

    # Flatten transparency (PNG/RGBA) onto white so the JPEG looks right.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg.convert("RGB")
    else:
        img = img.convert("RGB")

    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read()), "avatar.jpg"
