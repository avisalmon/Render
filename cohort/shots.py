"""Pictures of the participants' sites (REQ-C.11, C.12).

Measured on 2026-10-21 before choosing: WordPress mShots answers with a real
JPEG when the request carries a browser User-Agent, and Microlink answers with a
PNG; neither needs a key, and neither needs a browser installed on Render. The
sites are public already, so asking a public service to look at one gives away
nothing.

mShots answers "still generating" the first time it sees an address, so a
picture can take a few tries. Nothing runs in the background: a try happens
when the owner hangs or retakes a site, and again, quietly, when somebody opens
the exhibition while a picture is still on its way (methodology 22: work a
person waits for heals from their own visits and always says where it is).
"""

import io
import logging
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import Exhibit

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
MAX_TRIES = 6
RETRY_AFTER = 20          # seconds between quiet tries from page visits
SMALLEST = 12_000         # bytes; the "generating" placeholder is far smaller


def _get(url, timeout):
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed hosts)
        return r.headers.get("Content-Type", ""), r.read()


def _mshots(site):
    return f"https://s.wordpress.com/mshots/v1/{quote(site, safe='')}?w=1200&h=750"


def _microlink(site):
    return f"https://api.microlink.io/?url={quote(site, safe='')}&screenshot=true&meta=false&embed=screenshot.url"


def fetch(site, timeout=12):
    """The picture's bytes, or None. Replaced by a fake in tests."""
    for build in (_mshots, _microlink):
        try:
            kind, data = _get(build(site), timeout)
        except Exception as exc:  # network, timeout, HTTP error
            log.info("cohort shot: %s failed for %s: %s", build.__name__, site, exc)
            continue
        if kind.startswith("image/") and "gif" not in kind and len(data) >= SMALLEST:
            return data
    return None


def _as_jpeg(data):
    """Small enough for a card: 1200 wide at most, saved as JPEG."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((1200, 900))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=82)
        return out.getvalue()
    except Exception:
        return data


def take(exhibit, timeout=12):
    """One try. Returns True when the card now has a picture."""
    if not getattr(settings, "COHORT_SHOTS_ENABLED", True):
        return False
    exhibit.shot_tried_at = timezone.now()
    exhibit.shot_tries += 1
    data = fetch(exhibit.url, timeout=timeout)
    if data:
        if exhibit.shot:
            exhibit.shot.delete(save=False)
        exhibit.shot.save("shot.jpg", ContentFile(_as_jpeg(data)), save=False)
        exhibit.shot_source = Exhibit.AUTO
        exhibit.shot_status = Exhibit.OK
        exhibit.shot_taken_at = timezone.now()
    elif exhibit.shot_tries >= MAX_TRIES:
        exhibit.shot_status = Exhibit.FAILED
    exhibit.save()
    return bool(data)


def heal(limit=2):
    """Quiet tries for pictures still on their way, from a page visit."""
    now = timezone.now()
    due = Exhibit.objects.filter(shot_status=Exhibit.WAITING)
    done = 0
    for exhibit in due[:10]:
        if done >= limit:
            break
        if exhibit.shot_tried_at and (now - exhibit.shot_tried_at).total_seconds() < RETRY_AFTER:
            continue
        take(exhibit, timeout=6)
        done += 1
    return done
