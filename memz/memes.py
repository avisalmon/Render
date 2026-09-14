"""Turn an image + a caption into a stored `Meme` (spec §7, §8). One
function used by the solo creator now and, from SPR-Z.3, by every game
submission — the "one engine" half of spec §1's "one engine, two front
doors"."""

from django.core.files.base import ContentFile
from django.utils import timezone

from . import conf, render
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
