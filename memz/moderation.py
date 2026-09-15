"""The one place memz reaches outside itself (spec Rule 6.4.2, Rule
12.1.1; building_an_app.md Rule 2). Calls the site's existing image
safety check like an external service — a function call with an image in
and a verdict out, no shared models, no imports of `app`'s tables.

Deliberately **fails closed**, the opposite of `app.safety.image_is_safe`'s
own fail-open default: that function is built for the site's chat gate,
where a bad afternoon for the moderation API must never cost someone their
message. Here it's the reverse — a bad image sitting in a room full of
players is worse than a delayed one, so anything that isn't a clean,
confident "safe" leaves the image `pending`, never silently `approved`.
"""

import logging

logger = logging.getLogger(__name__)


def check_image(file_obj):
    """(status, note) — `status` is `MemeImage.APPROVED`, `MemeImage.REJECTED`,
    or `MemeImage.PENDING` (fail closed: the check itself broke, or the
    file isn't decodable in a way worth a hard rejection)."""
    from .models import MemeImage

    try:
        from app.safety import image_is_safe
    except Exception:
        logger.exception("memz.moderation: could not reach the site's image check")
        return MemeImage.PENDING, "moderation service unavailable"

    try:
        ok, reason = image_is_safe(file_obj)
    except Exception:
        logger.exception("memz.moderation: image_is_safe raised")
        return MemeImage.PENDING, "moderation call failed"
    finally:
        try:
            file_obj.seek(0)
        except Exception:
            pass

    if ok:
        return MemeImage.APPROVED, ""
    if reason == "notimage":
        return MemeImage.REJECTED, "not a decodable image"
    return MemeImage.REJECTED, "flagged by moderation"
