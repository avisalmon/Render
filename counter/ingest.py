"""Turning one incoming hit into rows. Lenient on purpose (spec section 3):
sites are small and a flood of junk is not a concern, so the only work here
is keeping strings short and paths tidy."""

import hashlib
import json
from urllib.parse import urlsplit

from django.conf import settings

from .models import Event, Page, Promo, Site

KINDS = {k for k, _ in Event.KINDS}


def clean_path(raw):
    path = urlsplit(str(raw or "/")).path or "/"
    if not path.startswith("/"):
        path = "/" + path
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    return path[:300]


def ip_hash(request):
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "")).strip()
    if not ip:
        return ""
    return hashlib.sha256(f"{settings.SECRET_KEY}|{ip}".encode()).hexdigest()


def parse_body(request):
    """text/plain or application/json; both are JSON. Returns {} on junk."""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record(request, data):
    """Returns (site, path), or (None, None) when the key is unknown or inactive."""
    site = Site.objects.filter(key=str(data.get("key", ""))[:32], is_active=True).first()
    if site is None:
        return None, None
    path = clean_path(data.get("path"))
    page, _ = Page.objects.get_or_create(site=site, path=path)
    title = str(data.get("title") or "")[:200]
    if title and page.title != title:
        page.title = title
        page.save(update_fields=["title", "last_seen"])
    else:
        page.save(update_fields=["last_seen"])
    kind = data.get("kind") if data.get("kind") in KINDS else Event.VIEW
    promo = None
    promo_id = str(data.get("promo") or "")
    if promo_id.isdigit():
        promo = Promo.objects.filter(pk=int(promo_id), owner=site.owner).first()
    Event.objects.create(
        site=site,
        page=page,
        kind=kind,
        name=str(data.get("name") or "")[:80],
        visitor_id=str(data.get("visitor") or "")[:64],
        ip_hash=ip_hash(request),
        referrer=str(data.get("referrer") or "")[:300],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:200],
        promo=promo,
    )
    return site, path
