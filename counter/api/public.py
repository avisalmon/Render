"""The public, key-based endpoints a static page calls (spec section 2).

Open on purpose: a site key is an identifier, not a secret (spec section 3),
and abuse is not a concern. They are called cross-origin from other domains,
so every answer carries permissive CORS headers. The snippet sends the hit as
text/plain so the browser needs no preflight; the OPTIONS answer is here for
any client that does one anyway.
"""

import random

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .. import ingest, stats
from ..models import PromoPlacement, Site

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
}


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    for k, v in CORS.items():
        response[k] = v
    return response


def _unknown():
    return _json({"ok": False, "error": "unknown site key"}, status=404)


HITS_PER_MINUTE = 60


def _too_many(request):
    """One address, one minute, sixty hits: a script cannot fill the table (security review, 2026-10-24)."""
    from django.core.cache import cache

    key = "counter:hits:" + ingest.ip_hash(request)[:24]
    n = cache.get(key, 0)
    if n >= HITS_PER_MINUTE:
        return True
    cache.set(key, n + 1, 60)
    return False


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def hit(request):
    if request.method == "OPTIONS":
        return _json({})
    if _too_many(request):
        return _json({"ok": False, "error": "too many"}, status=429)
    site, path = ingest.record(request, ingest.parse_body(request))
    if site is None:
        return _unknown()
    return _json({"ok": True, "path": path, **stats.totals(site, path)})


@require_http_methods(["GET", "OPTIONS"])
def site_stats(request, key):
    """Counts for a whole site, or for one page with ?path=/x/."""
    if request.method == "OPTIONS":
        return _json({})
    site = Site.objects.filter(key=key, is_active=True).first()
    if site is None:
        return _unknown()
    path = request.GET.get("path")
    path = ingest.clean_path(path) if path is not None else None
    return _json({"ok": True, "path": path, **stats.totals(site, path)})


@require_http_methods(["GET", "OPTIONS"])
def promo_for(request, key):
    """One promo for this site and page, picked by weight (phase 2)."""
    if request.method == "OPTIONS":
        return _json({})
    site = Site.objects.filter(key=key, is_active=True).first()
    if site is None:
        return _unknown()
    path = ingest.clean_path(request.GET.get("path"))
    placements = [
        p for p in PromoPlacement.objects.filter(site=site, is_active=True, promo__is_active=True)
        .select_related("promo")
        if path.startswith(p.path_prefix)
    ]
    if not placements:
        return _json({"ok": True, "promo": None})
    chosen = random.choices(placements, weights=[max(p.weight, 1) for p in placements])[0].promo
    return _json({"ok": True, "promo": {"id": chosen.pk, "title": chosen.title, "text": chosen.text,
                                        "url": chosen.url, "image_url": chosen.image_url}})
