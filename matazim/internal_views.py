"""The one machine-triggered endpoint this app has (REQ-M.34).

Same shape as babook's `/internal/run-capture/`: a scheduled GitHub Action posts
a shared secret, and the work runs inside the live web service because a
separate cron container cannot see the SQLite file on Render's persistent disk.

Its own endpoint inside `/matazim/` rather than a line added to babook's,
because §2.1 says shared engine and own surfaces, and a job that rings מט״צים's
bell belongs to מט״צים. It reuses `BACKUP_TRIGGER_TOKEN` rather than inventing a
secret, so there is one thing to rotate rather than three.

**It can only send reminders.** Not a general "run a command" endpoint, which is
what this pattern turns into if nobody stops it, and which would be a remote
shell with a password. If a second unattended job is ever wanted, it gets its
own view and its own argument about whether it may run unattended at all.
"""

import io

from django.conf import settings
from django.core.management import call_command
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def run_reminders(request):
    """REQ-M.34 — tell people about tomorrow. Machine endpoint, not a screen."""
    expected = getattr(settings, "BACKUP_TRIGGER_TOKEN", "") or ""
    provided = request.headers.get("X-Matazim-Token", "")

    # An unset token means closed, never open. A deploy that forgets the secret
    # must not leave a public endpoint that can write to every member's bell.
    if not expected or not constant_time_compare(provided, expected):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    out = io.StringIO()
    try:
        call_command("matazim_remind", apply=True, stdout=out, stderr=out)
    except Exception as exc:  # noqa: BLE001 - the caller needs to go red
        return JsonResponse(
            {"ok": False, "error": str(exc), "log": out.getvalue()}, status=500
        )
    return JsonResponse({"ok": True, "log": out.getvalue()})
