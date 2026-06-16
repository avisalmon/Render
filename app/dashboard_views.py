"""EPIC-8 — Admin / Management Control Dashboard views (superuser-only).

A single hub at ``/admin-dashboard/`` with sections for Users & Training,
Costs, Engagement and System, plus per-section refresh, manual cost entry,
alert config and alert dismissal. All gated by :func:`superuser_required`.
"""

import io
import json

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .dashboard.access import superuser_required
from .dashboard.capture import (
    cost_summary,
    latest_metrics,
    metric_trend,
    run_capture,
)
from .dashboard.cost_adapters import adapter_labels, current_period, set_manual_cost

# Range selector → days (None = all-time)
RANGES = {"today": 1, "7": 7, "30": 30, "90": 90, "all": None}


def _range_days(request):
    key = request.GET.get("range", "30")
    if key not in RANGES:
        key = "30"
    return key, RANGES[key]


@superuser_required
def admin_dashboard(request):
    """The cockpit hub (REQ-8.1.1)."""
    range_key, days = _range_days(request)

    ut, ut_at = latest_metrics("users_training", days)
    eng, eng_at = latest_metrics("engagement", days)
    sys_m, sys_at = latest_metrics("system", days)
    costs = cost_summary(current_period())

    from .models import AlertEvent

    alerts = list(AlertEvent.objects.filter(dismissed_at__isnull=True))

    trends = {
        "users_new": metric_trend("users_training", "users_new"),
        "active_contributors": metric_trend("engagement", "active_contributors"),
        "watch_hours": metric_trend("users_training", "watch_hours"),
    }

    ctx = {
        "range_key": range_key,
        "ranges": list(RANGES.keys()),
        "ut": ut,
        "ut_at": ut_at,
        "eng": eng,
        "eng_at": eng_at,
        "sys": sys_m,
        "sys_at": sys_at,
        "costs": costs,
        "alerts": alerts,
        "cost_labels": adapter_labels(),
        "period": current_period(),
        "trends_json": json.dumps(trends),
    }
    return render(request, "app/dashboard/hub.html", ctx)


@superuser_required
@require_POST
def refresh_section(request, section):
    """Re-run one section's collectors on demand (REQ-8.1.5)."""
    if section not in ("users_training", "engagement", "system", "costs", "all"):
        return redirect("admin_dashboard")
    _key, days = _range_days(request)
    run_capture(scope=section, range_days=days)
    messages.success(request, "המקטע עודכן.")
    return redirect(f"/admin-dashboard/?range={request.GET.get('range', '30')}#{section}")


@superuser_required
@require_POST
def manual_cost(request):
    """Set a manual cost override for a service this period (REQ-8.3.11)."""
    service = request.POST.get("service", "").strip()
    amount = request.POST.get("amount", "0").strip()
    note = request.POST.get("note", "").strip()
    period = request.POST.get("period", current_period()).strip()
    if service:
        try:
            set_manual_cost(service, period, amount, note)
            messages.success(request, f"עלות ידנית נשמרה עבור {service}.")
        except Exception:
            messages.error(request, "סכום לא תקין.")
    return redirect("admin_dashboard")


@superuser_required
def alert_config(request):
    """View/edit alert thresholds (REQ-8.6.3)."""
    from .dashboard.alerts import ensure_default_rules
    from .models import AlertRule

    ensure_default_rules()
    if request.method == "POST":
        for rule in AlertRule.objects.all():
            t = request.POST.get(f"threshold_{rule.key}")
            rule.enabled = bool(request.POST.get(f"enabled_{rule.key}"))
            if t is not None:
                try:
                    rule.threshold = float(t)
                except ValueError:
                    pass
            rule.save()
        messages.success(request, "הגדרות ההתראות נשמרו.")
        return redirect("dashboard_alert_config")
    rules = list(AlertRule.objects.all())
    return render(request, "app/dashboard/alerts_config.html", {"rules": rules})


@superuser_required
@require_POST
def dismiss_alert(request, pk):
    """Dismiss an active alert (REQ-8.6.2)."""
    from .models import AlertEvent

    AlertEvent.objects.filter(pk=pk, dismissed_at__isnull=True).update(dismissed_at=timezone.now())
    return redirect("admin_dashboard")


@csrf_exempt
@require_POST
def run_backup(request):
    """Token-triggered full backup (REQ-1.2.4).

    Called by the weekly GitHub Actions cron with the shared secret in the
    ``X-Backup-Token`` header. Runs ``backup_db`` in-process (so it has the
    SQLite persistent disk, which a separate Render cron container would not),
    and returns the command log so a failed backup turns the Actions run red.
    This is a machine endpoint, not a session/superuser route.
    """
    expected = getattr(settings, "BACKUP_TRIGGER_TOKEN", "")
    provided = request.headers.get("X-Backup-Token", "")
    if not expected or not constant_time_compare(provided, expected):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    out = io.StringIO()
    try:
        call_command("backup_db", stdout=out, stderr=out)
    except Exception as exc:  # noqa: BLE001 — surface failure to the caller
        return JsonResponse(
            {"ok": False, "error": str(exc), "log": out.getvalue()}, status=500)
    return JsonResponse({"ok": True, "log": out.getvalue()})
