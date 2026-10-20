"""The one door for a scheduler: re-run background jobs a restart dropped.

The "key without the house" pattern (building_an_app.md BKM): one job, the
token names nothing, it cannot create or change anything but run Books' own
queued jobs, it fails shut when unset, compares in constant time, and a
signed-in superuser may use it too.
"""

from django.conf import settings
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import jobs


def _allowed(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return True
    expected = getattr(settings, "BOOKS_JOBS_TOKEN", "")
    given = request.headers.get("X-Books-Token", "")
    return bool(expected) and bool(given) and constant_time_compare(expected, given)


@csrf_exempt
@require_POST
def run_jobs(request):
    if not _allowed(request):
        return JsonResponse({"ok": False}, status=403)
    ran = jobs.run_pending(retry_failed=request.GET.get("retry") == "1")
    return JsonResponse({"ok": True, "ran": [{"id": j.pk, "kind": j.kind, "status": j.status} for j in ran]})


def storage_check(request):
    """Superuser only (404 for anyone else): which storage Books is really
    using, and a live round trip when it is the bucket: write a small file,
    read it back through its signed link, confirm the same object is refused
    without the signature, delete it."""
    import requests
    from django.core.files.base import ContentFile
    from django.http import Http404
    from django.utils import timezone

    from . import storage

    if not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404
    out = storage.status()
    if storage.is_bucket():
        st = storage.books_storage()
        name = st.save(f"_check/{timezone.now():%Y%m%d%H%M%S}.txt", ContentFile(b"books storage check"))
        try:
            signed = st.url(name)
            out["write"] = True
            out["signed_read"] = requests.get(signed, timeout=10).status_code
            public = f"https://storage.googleapis.com/{out['bucket']}/books/{name}"
            out["public_read"] = requests.get(public, timeout=10).status_code
            out["ok"] = out["signed_read"] == 200 and out["public_read"] in (401, 403)
        finally:
            st.delete(name)
    else:
        out["ok"] = False
    return JsonResponse(out)


def sources_check(request):
    """Superuser only (404 for anyone else): is each book source configured
    and answering right now? One live search per source, no cache, plus the
    enrichment and web-lookup numbers."""
    from django.conf import settings
    from django.http import Http404

    from . import enrich, weblookup
    from .sources import googlebooks, nli, openlibrary

    if not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404
    tests = {"english": "Harry Potter Rowling", "hebrew": "מיכאל שלי עמוס עוז"}
    out = {}
    for source, key_name in ((googlebooks, "BOOKS_GOOGLE_BOOKS_KEY"), (openlibrary, None), (nli, "BOOKS_NLI_API_KEY")):
        row = {"key_set": bool(getattr(settings, key_name, "")) if key_name else None}
        if key_name == "BOOKS_NLI_API_KEY" and not row["key_set"]:
            row["skipped"] = "no key"
            out[source.NAME] = row
            continue
        for label, query in tests.items():
            try:
                records = source.search(query, limit=3)
                row[label] = {"ok": True, "results": len(records),
                              "first": records[0].title if records else "",
                              "isbn": records[0].isbns[:1] if records else []}
            except Exception as exc:  # noqa: BLE001
                row[label] = {"ok": False, "error": str(exc)[:200]}
        out[source.NAME] = row
    return JsonResponse({"sources": out, "enrichment": enrich.counts(),
                         "web": {"enabled": weblookup.enabled(), "today_usd": float(weblookup.spent_today()),
                                 "cap_usd": float(weblookup.daily_cap())}},
                        json_dumps_params={"ensure_ascii": False})
