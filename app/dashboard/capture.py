"""Capture orchestration + read helpers for the admin dashboard.

``run_capture`` collects metrics (and optionally costs + alerts) into a
:class:`DashboardSnapshot` so the hub loads instantly from history; the read
helpers expose the latest snapshot per section and build trend series for the
Chart.js charts (REQ-8.1.3 / 8.1.4 / 8.1.6).
"""

from django.utils import timezone

from . import metrics
from .cost_adapters import current_period, run_all_adapters

SECTION_COLLECTORS = {
    "users_training": lambda days: metrics.collect_users_training(days),
    "engagement": lambda days: metrics.collect_engagement(min(days or 7, 30) if days else 7),
    "system": lambda _days: metrics.collect_system(),
}


def run_capture(scope="all", range_days=30, run_costs=True, run_alerts=True):
    """Collect ``scope`` into a snapshot. ``scope='all'`` captures every section
    (one snapshot each) plus a combined ``all`` snapshot, and — when asked —
    runs the cost adapters and evaluates alerts. Returns a summary dict.
    """
    from ..models import DashboardSnapshot

    created = {}
    scopes = list(SECTION_COLLECTORS) if scope == "all" else [scope]
    combined = {}
    for sc in scopes:
        collector = SECTION_COLLECTORS.get(sc)
        if not collector:
            continue
        data = collector(range_days)
        combined[sc] = data
        snap = DashboardSnapshot.objects.create(scope=sc, metrics=data)
        created[sc] = snap.id

    if scope == "all":
        DashboardSnapshot.objects.create(scope="all", metrics=combined)

    cost_rows = None
    if run_costs and scope in ("all", "costs"):
        cost_rows = run_all_adapters(current_period())

    alerts_raised = None
    if run_alerts and scope in ("all", "costs", "engagement"):
        from .alerts import evaluate_alerts

        alerts_raised = evaluate_alerts()

    return {
        "captured_at": timezone.now().isoformat(),
        "snapshots": created,
        "cost_rows": len(cost_rows) if cost_rows is not None else None,
        "alerts": len(alerts_raised) if alerts_raised is not None else None,
    }


def latest_metrics(scope, range_days=30):
    """Latest snapshot metrics for ``scope`` — captures live on the fly if none
    exists yet, so the dashboard is never empty (REQ-8.1.7)."""
    from ..models import DashboardSnapshot

    snap = DashboardSnapshot.objects.filter(scope=scope).order_by("-captured_at").first()
    if snap:
        return snap.metrics, snap.captured_at
    collector = SECTION_COLLECTORS.get(scope)
    if collector:
        data = collector(range_days)
        DashboardSnapshot.objects.create(scope=scope, metrics=data)
        return data, timezone.now()
    return {}, None


def metric_trend(scope, key, points=12):
    """A small (label, value) series for a numeric metric from snapshot history,
    oldest→newest, for the trend charts (REQ-8.1.6)."""
    from ..models import DashboardSnapshot

    rows = DashboardSnapshot.objects.filter(scope=scope).order_by("-captured_at")[:points]
    series = []
    for snap in reversed(list(rows)):
        val = snap.metrics.get(key)
        if isinstance(val, (int, float)):
            series.append({"t": snap.captured_at.strftime("%m-%d"), "v": val})
    return series


def cost_summary(period=None):
    """Per-service spend for ``period`` + a total and month-over-month delta."""
    from ..models import CostRecord

    period = period or current_period()
    rows = list(CostRecord.objects.filter(period=period).order_by("service"))
    total = float(sum(r.amount_usd for r in rows))

    # previous month total for the MoM trend
    y, mo = (int(x) for x in period.split("-"))
    prev = f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"
    prev_total = float(sum(r.amount_usd for r in CostRecord.objects.filter(period=prev)))
    delta = total - prev_total
    return {
        "period": period,
        "rows": rows,
        "total": round(total, 2),
        "prev_total": round(prev_total, 2),
        "delta": round(delta, 2),
    }
