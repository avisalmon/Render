"""Classic meme templates via Imgflip's own API (memz ACT-Z.5, spec §7.3,
§14 item 6). memz calls Imgflip's own captioning service rather than
downloading and re-hosting their template library itself the way the
folder Avi handed over would have -- see docs/memz/backlog.md's ACT-Z.5
sprint notes for the fuller story. Their own API docs describe the
returned image as one callers "can link, embed, or even download and host
yourself"; the underlying template photograph's original copyright is
still theirs to carry, not memz's to clear, same as every other meme bot
built on this API.

Two calls: `list_templates()` is public (no credentials, cached — Imgflip's
own top-100 barely moves) so the picker works even before Imgflip
credentials exist. `caption()` needs `IMGFLIP_USERNAME`/`IMGFLIP_PASSWORD`
and raises `ImgflipUnavailable` for anything short of a clean captioned
image back — no credentials, a network failure, Imgflip's own refusal —
fail closed, the same posture as `memz/moderation.py`, because there is no
meaningful stub image to fall back to the way `call_openai` falls back to
stub text.

v1 only fills a template's first two text boxes (top/bottom, `text0`/
`text1` — Imgflip's simplest, best-supported form); a template with more
than two boxes just leaves the rest blank rather than reaching for their
premium-gated `boxes[]` form.
"""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TEMPLATES_URL = "https://api.imgflip.com/get_memes"
CAPTION_URL = "https://api.imgflip.com/caption_image"
_CACHE_KEY = "memz:imgflip:templates"
_CACHE_TTL = 60 * 60   # an hour; Imgflip's top-100 list barely moves
_TIMEOUT = 10
_MAX_TEXT_LEN = 80


class ImgflipUnavailable(Exception):
    """Anything short of a clean captioned image back. A message safe to
    show the user."""


def is_configured():
    return bool(settings.IMGFLIP_USERNAME and settings.IMGFLIP_PASSWORD)


def list_templates():
    """The ~100 templates Imgflip's free endpoint returns, cached. Needs no
    credentials, so the picker itself is never empty just because
    captioning isn't configured yet."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    try:
        resp = requests.get(TEMPLATES_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("memz.imgflip_templates: could not reach Imgflip's template list")
        return []
    if not data.get("success"):
        return []
    templates = data.get("data", {}).get("memes", [])
    cache.set(_CACHE_KEY, templates, _CACHE_TTL)
    return templates


def _template_by_id(template_id):
    for t in list_templates():
        if str(t.get("id")) == str(template_id):
            return t
    return None


def caption(template_id, top_text="", bottom_text=""):
    """Returns `(jpeg_bytes, template_name)`. Raises `ImgflipUnavailable`
    for anything short of a clean success."""
    if not is_configured():
        raise ImgflipUnavailable("תבניות קלאסיות לא זמינות כרגע.")

    template = _template_by_id(template_id)
    if template is None:
        raise ImgflipUnavailable("לא מצאנו את התבנית הזו.")

    top = (top_text or "").strip()[:_MAX_TEXT_LEN]
    bottom = (bottom_text or "").strip()[:_MAX_TEXT_LEN]
    if not top and not bottom:
        raise ImgflipUnavailable("צריך לכתוב לפחות משפט אחד.")

    payload = {
        "template_id": template_id,
        "username": settings.IMGFLIP_USERNAME,
        "password": settings.IMGFLIP_PASSWORD,
        "text0": top,
        "text1": bottom,
    }
    try:
        resp = requests.post(CAPTION_URL, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("memz.imgflip_templates: caption_image call failed")
        raise ImgflipUnavailable("לא הצלחנו ליצור את המם הזה, נסו שוב.")

    if not data.get("success"):
        raise ImgflipUnavailable(data.get("error_message") or "לא הצלחנו ליצור את המם הזה.")

    image_url = data["data"]["url"]
    try:
        img_resp = requests.get(image_url, timeout=_TIMEOUT)
        img_resp.raise_for_status()
    except Exception:
        logger.exception("memz.imgflip_templates: could not download the captioned image")
        raise ImgflipUnavailable("לא הצלחנו להוריד את המם, נסו שוב.")

    return img_resp.content, template.get("name", "")
