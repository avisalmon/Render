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
