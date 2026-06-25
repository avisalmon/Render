"""Site-wide content safety + correctness gates.

A cheap-first funnel so we spend (almost) nothing on moderation:

  1. Structural validation (LOCAL, free): is the upload actually the kind of
     artifact we asked for? A real, decodable image / a real STL mesh. Catches
     junk and wrong-file mistakes before any API call.
  2. Safety moderation (OpenAI omni-moderation, FREE): sexual, violence, hate,
     harassment, self-harm, illicit - for BOTH text and images. Reuses the
     existing ModerationLog + check_moderation spine in ai_chat.py.
  3. Relevance / topicality (cheapest chat model, ~pennies): the categories the
     free moderation API does NOT cover - political content and off-topic
     chatter (e.g. a pizza recipe in a coding channel). Cached by content hash,
     gated by CONTENT_RELEVANCE_ENABLED, and fails OPEN.

Every gate FAILS OPEN: if the AI/network is down the site keeps working.
Anything flagged is logged to ModerationLog for the staff review queue.

Public helpers:
  validate_image(uploaded)            -> (ok, reason)        [local]
  validate_stl(uploaded)              -> (ok, reason)        [local]
  image_is_safe(source, user, label)  -> (ok, reason)        [local + free API]
  text_relevance_ok(text, ctx, user)  -> (ok, detail)        [cheap API, cached]
"""
import hashlib
import io
import logging
import struct

from django.conf import settings

logger = logging.getLogger(__name__)

# Sanity caps (defense in depth - views may also cap).
IMAGE_MAX_BYTES = 15 * 1024 * 1024
STL_MAX_BYTES = 40 * 1024 * 1024
# Image downscaled to at most this before being sent for moderation - keeps the
# (free) API payload small and fast. The stored file is untouched.
MODERATION_MAX_PX = 1024


# ---------------------------------------------------------------------------
# 1. Structural validation (local, free)
# ---------------------------------------------------------------------------

def validate_image(uploaded):
    """(ok, reason) - confirm `uploaded` is a real, decodable image within size.
    reason in {"", "bigimage", "notimage"}. Resets the file pointer when done."""
    try:
        size = getattr(uploaded, "size", None)
        if size is not None and size > IMAGE_MAX_BYTES:
            return False, "bigimage"
        from PIL import Image
        uploaded.seek(0)
        Image.open(uploaded).verify()   # raises if not a real image
        return True, ""
    except Exception:
        return False, "notimage"
    finally:
        try:
            uploaded.seek(0)
        except Exception:
            pass


def validate_stl(uploaded):
    """(ok, reason) - confirm `uploaded` is a real STL mesh (not just a .stl
    name). Handles both ASCII ("solid ... facet normal ...") and binary STL
    (80-byte header + uint32 triangle count + 50 bytes/triangle).
    reason in {"", "bigstl", "emptystl", "badstl"}. Resets the file pointer."""
    try:
        size = getattr(uploaded, "size", None)
        if size is not None and size > STL_MAX_BYTES:
            return False, "bigstl"
        uploaded.seek(0)
        head = uploaded.read(512)
        if not head:
            return False, "emptystl"

        # ASCII STL: starts with "solid" and contains mesh keywords.
        stripped = head.lstrip()
        if stripped[:5].lower() == b"solid":
            uploaded.seek(0)
            blob = uploaded.read(200_000).lower()   # sample is enough
            if b"facet normal" in blob and b"vertex" in blob:
                return True, ""
            # Some binary STLs also begin with "solid" in the header - fall
            # through to the binary check rather than rejecting.

        # Binary STL: header(80) + uint32 count + count * 50 bytes.
        uploaded.seek(0)
        header = uploaded.read(84)
        if len(header) < 84:
            return False, "badstl"
        (count,) = struct.unpack("<I", header[80:84])
        if count <= 0:
            return False, "emptystl"
        expected = 84 + count * 50
        if size is not None and abs(size - expected) > 4:
            return False, "badstl"
        return True, ""
    except Exception:
        return False, "badstl"
    finally:
        try:
            uploaded.seek(0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2. Image safety moderation (local downscale + FREE omni-moderation)
# ---------------------------------------------------------------------------

def _moderation_jpeg(source, max_px=MODERATION_MAX_PX):
    """Return small JPEG bytes for moderation, or None if `source` is not a
    decodable image. Always resets the source pointer afterwards."""
    try:
        from PIL import Image, ImageOps
        source.seek(0)
        img = Image.open(source)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return None
    finally:
        try:
            source.seek(0)
        except Exception:
            pass


def image_is_safe(source, user=None, label=""):
    """(ok, reason) - structural + safety check for an image upload.
    `source` is anything PIL can open (an UploadedFile, ContentFile, BytesIO).
    reason in {"", "notimage", "flagged"}. Fails OPEN on API/network error.
    Disable entirely with settings.IMAGE_MODERATION_ENABLED = False."""
    jpeg = _moderation_jpeg(source)
    if jpeg is None:
        return False, "notimage"
    if not getattr(settings, "IMAGE_MODERATION_ENABLED", True):
        return True, ""
    try:
        from .ai_chat import check_image_moderation
        ok, _ = check_image_moderation(jpeg, mime="image/jpeg", user=user, label=label)
        return (True, "") if ok else (False, "flagged")
    except Exception:
        logger.exception("image_is_safe failed open")
        return True, ""


# ---------------------------------------------------------------------------
# 3. Relevance / topicality (cheap LLM, cached, gated, fails open)
# ---------------------------------------------------------------------------

def text_relevance_ok(text, context_label="", user=None):
    """(ok, detail) - block political/off-topic/abusive chatter the free
    moderation API does not catch. Cached by content hash (24h), gated by
    settings.CONTENT_RELEVANCE_ENABLED (default on), fails OPEN.
    Flagged content is logged to ModerationLog."""
    text = (text or "").strip()
    if not text or not getattr(settings, "CONTENT_RELEVANCE_ENABLED", True):
        return True, {}

    from django.core.cache import cache
    key = "relv:" + hashlib.sha256(
        (context_label + "|" + text).encode("utf-8")).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached.get("allowed", True), cached

    try:
        from .ai_chat import classify_relevance
        data = classify_relevance(text, context_label)
    except Exception:
        logger.exception("text_relevance_ok failed open")
        return True, {}

    cache.set(key, data, 86400)
    if not data.get("allowed", True):
        try:
            from .models import ModerationLog
            cats = data.get("categories") or ["off_topic"]
            ModerationLog.objects.create(
                user=user,
                content=text[:500],
                flagged_categories={c: True for c in cats},
            )
        except Exception:
            logger.exception("ModerationLog write failed (relevance)")
    return data.get("allowed", True), data
