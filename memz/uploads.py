"""Processing a user's own upload into the bank (spec §6.2.1, §6.2.2).

Format/size checked, EXIF orientation applied then discarded (along with
every other metadata field — location, device), resized so the longest
side is at most `UPLOAD_MAX_SIDE`, re-encoded. The original bytes are
never kept.
"""

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from . import conf

# ACT-Z.15 (2026-09-19, Avi: "it needs to allow images from phone, real
# camera and files"): an iPhone's camera roll is HEIC, and Pillow cannot
# open HEIC on its own -- every such upload used to die at `image.load()`
# below with "choose JPEG in the share sheet", which is the one thing a
# person picking a photo at a party will not do. `pillow-heif` teaches
# Pillow the format. Guarded so a build without the wheel still serves
# JPEG/PNG/WebP and refuses HEIC with the old message, rather than 500.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:   # pragma: no cover - only on a build missing the wheel
    HEIF_SUPPORTED = False

ACCEPTED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


class UploadError(Exception):
    """A refused upload, with a message safe to show the user."""


def process_upload(file_obj):
    """Returns a `ContentFile` of a clean JPEG, ready to attach to
    `MemeImage.file`. Raises `UploadError` for anything that doesn't
    qualify (spec Rule 6.2.1)."""
    max_bytes = conf.get("UPLOAD_MAX_BYTES")
    size = getattr(file_obj, "size", None)
    if size is not None and size > max_bytes:
        raise UploadError(f"הקובץ גדול מדי (עד {max_bytes // (1024 * 1024)}MB).")

    try:
        file_obj.seek(0)
        image = Image.open(file_obj)
        image.load()   # HEIC/HEIF without a plugin fails here, not at .load() time later
    except UnidentifiedImageError:
        raise UploadError("זה לא נראה כמו תמונה. נסו JPEG, PNG או WebP.")
    except Exception:
        raise UploadError("בחרו JPEG בתפריט השיתוף ונסו שוב.")   # the common HEIC-with-no-plugin case
    finally:
        try:
            file_obj.seek(0)
        except Exception:
            pass

    # Orientation from EXIF, then every metadata field (EXIF included) is
    # dropped by re-encoding through a fresh RGB image with no info dict.
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    max_side = conf.get("UPLOAD_MAX_SIDE")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)

    buf_bytes = _encode_jpeg(image)
    return ContentFile(buf_bytes)


def _encode_jpeg(image):
    import io

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=conf.get("UPLOAD_JPEG_QUALITY"), optimize=True)
    return buf.getvalue()
