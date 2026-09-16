"""Turn an image + a caption into a stored `Meme` (spec §7, §8). One
function used by the solo creator now and, from SPR-Z.3, by every game
submission — the "one engine" half of spec §1's "one engine, two front
doors"."""

from django.core.files.base import ContentFile
from django.utils import timezone

from . import conf, imgflip_templates, render
from .models import Meme


def make_meme(*, image, caption_text, source, user=None, caption_card=None):
    """Render and save a `Meme`. `user=None` means a guest: the result gets
    a watermark and an expiry (spec §8.1, §8.5); a logged-in user's does
    not. Caller decides `source` (`Meme.GAME` / `Meme.SOLO`)."""
    caption_text = (caption_text or "").strip()
    is_guest = user is None or not getattr(user, "is_authenticated", False)

    jpeg_bytes, _w, _h = render.render(image.file, caption_text, watermark=is_guest)

    meme = Meme(
        image=image, caption_text=caption_text, caption_card=caption_card,
        source=source, created_by_user=user if not is_guest else None,
    )
    if is_guest:
        meme.expires_at = timezone.now() + timezone.timedelta(hours=conf.get("GUEST_MEME_TTL_HOURS"))
    meme.rendered.save(f"{meme.share_slug}.jpg", ContentFile(jpeg_bytes), save=False)
    meme.save()
    return meme


def make_meme_from_template(*, template_id, top_text, bottom_text, user=None):
    """A `Meme` from a classic Imgflip template rather than a bank image
    (ACT-Z.5, spec §7.3): Imgflip does the actual rendering, memz just
    downloads and stores the result and records where it came from
    (`source_credit`). Raises `imgflip_templates.ImgflipUnavailable` for
    anything short of a clean captioned image back — the caller turns that
    into an HTTP response, the same shape as every other memz error."""
    is_guest = user is None or not getattr(user, "is_authenticated", False)
    jpeg_bytes, template_name = imgflip_templates.caption(template_id, top_text, bottom_text)

    caption_text = " / ".join(t for t in ((top_text or "").strip(), (bottom_text or "").strip()) if t)
    meme = Meme(
        image=None, caption_text=caption_text, source=Meme.SOLO,
        created_by_user=user if not is_guest else None,
        source_credit=f"Imgflip: {template_name}" if template_name else "Imgflip",
    )
    if is_guest:
        meme.expires_at = timezone.now() + timezone.timedelta(hours=conf.get("GUEST_MEME_TTL_HOURS"))
    meme.rendered.save(f"{meme.share_slug}.jpg", ContentFile(jpeg_bytes), save=False)
    meme.save()
    return meme
