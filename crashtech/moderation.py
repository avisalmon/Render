"""One of CrashTech's two named adapters (spec Rule 2.1.2, Rule 9.3).

The museum is a permanent public page that anyone signed in may post to,
which is the same thing as saying it is a permanent public page anyone may
post *anything* to. This calls the site's existing image check like an
external service: a function call with an image in and a verdict out, no
shared models, no imports of `app`'s tables.

**Fails closed**, like memz's version and unlike the site's own default.
`app.safety.image_is_safe` fails open because it was built for the chat
gate, where a bad afternoon for the moderation API must never cost
somebody their message. Here it is the other way round: a bad image
sitting on a page that is public forever is worse than one that waits a
day, so anything short of a confident "safe" stays `pending`.
"""

import logging

logger = logging.getLogger(__name__)


def check_image(file_obj):
    """`(status, note)`, where status is one of `MuseumPhoto`'s three."""
    from .models import MuseumPhoto

    try:
        from app.safety import image_is_safe
    except Exception:
        logger.exception("crashtech.moderation: could not reach the site's image check")
        return MuseumPhoto.PENDING, "moderation service unavailable"

    try:
        ok, reason = image_is_safe(file_obj)
    except Exception:
        logger.exception("crashtech.moderation: image_is_safe raised")
        return MuseumPhoto.PENDING, "moderation call failed"
    finally:
        try:
            file_obj.seek(0)
        except Exception:
            pass

    if ok:
        return MuseumPhoto.APPROVED, ""
    if reason == "notimage":
        return MuseumPhoto.REJECTED, "not a decodable image"
    return MuseumPhoto.REJECTED, reason or "rejected by the safety check"
