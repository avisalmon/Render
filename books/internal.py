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
    from django.http import Http404
    from django.utils import timezone

    import requests
    from django.core.files.base import ContentFile

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
