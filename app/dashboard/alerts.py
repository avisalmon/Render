"""Threshold alerts for the admin dashboard (REQ-8.6.*).

Evaluates admin-editable :class:`AlertRule` thresholds against the latest
metrics and spend, raising a dismissible :class:`AlertEvent` (deduped against
still-active alerts for the same rule) and notifying every superuser via the
existing ``notify()`` helper + email. Reuses the OpenAI cost-cap idea rather
than duplicating it.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone

# key -> (label, default threshold, section)
DEFAULT_RULES = {
    "spend_total": ("Total monthly spend (USD)", 100.0, "costs"),
    "free_tier_usage_pct": ("Free-tier usage (% of limit)", 80.0, "costs"),
    "domain_expiry_days": ("Domain expiry (days left)", 14.0, "system"),
    "report_queue": ("Open moderation reports", 10.0, "engagement"),
    "unanswered_age_hours": ("Oldest unanswered question (hours)", 48.0, "engagement"),
    "backup_stale_hours": ("Backup age (hours)", 48.0, "system"),
}

# Rules where a LOW value is the problem (fire when value <= threshold), the
# inverse of the default "fire when value >= threshold".
LOWER_IS_WORSE = {"domain_expiry_days"}


def ensure_default_rules():
    """Create any missing default rules (idempotent) — REQ-8.6.3."""
    from ..models import AlertRule

    for key, (label, threshold, section) in DEFAULT_RULES.items():
        AlertRule.objects.get_or_create(
            key=key,
            defaults={"label": label, "threshold": threshold, "section": section},
        )


def _oldest_unanswered_age_hours():
    from ..models import ForumThread

    now = timezone.now()
    oldest = 0.0
    for t in ForumThread.objects.filter(kind="question", is_hidden=False).prefetch_related("posts"):
        if not t.posts.exists():
            age = (now - t.created_at).total_seconds() / 3600
            oldest = max(oldest, age)
    return round(oldest, 1)


def _backup_age_hours():
    from .metrics import _last_backup_marker

    marker = _last_backup_marker()
    if not marker:
        return None
    try:
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(marker)
        if dt is None:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return round((timezone.now() - dt).total_seconds() / 3600, 1)
    except Exception:
        return None


def evaluate_alerts(spend_total=None, engagement=None, notify_admins=True):
    """Check every enabled rule; raise + notify on fresh breaches.

    Returns the list of AlertEvent rows created in this run.
    """
    from ..models import AlertEvent, AlertRule, CostRecord

    ensure_default_rules()

    period = timezone.now().strftime("%Y-%m")
    period_records = list(CostRecord.objects.filter(period=period))
    if spend_total is None:
        spend_total = float(sum(r.amount_usd for r in period_records))
    if engagement is None:
        from .metrics import collect_engagement

        engagement = collect_engagement(7)

    # Worst free-tier consumption across services that report a `free_tier_pct`
    # in their cost-adapter raw (GCS backups, Resend) — "how close to paying".
    free_worst_svc, free_worst_pct = None, 0.0
    domain_days, domain_renew_url = None, ""
    for r in period_records:
        pct = (r.raw or {}).get("free_tier_pct")
        if pct is not None and float(pct) > free_worst_pct:
            free_worst_pct, free_worst_svc = float(pct), r.service
        if r.service == "domain":
            domain_days = (r.raw or {}).get("days_left")
            domain_renew_url = (r.raw or {}).get("registrar_url") or ""

    measured = {
        "spend_total": float(spend_total),
        "free_tier_usage_pct": free_worst_pct,
        "domain_expiry_days": float(domain_days) if domain_days is not None else None,
        "report_queue": float(engagement.get("open_reports", 0)),
        "unanswered_age_hours": _oldest_unanswered_age_hours(),
        "backup_stale_hours": _backup_age_hours(),
    }

    created = []
    for rule in AlertRule.objects.filter(enabled=True):
        value = measured.get(rule.key)
        if value is None:
            continue
        # Direction: most rules fire when value >= threshold; "lower is worse"
        # rules (domain expiry) fire when value <= threshold.
        if rule.key in LOWER_IS_WORSE:
            if value > rule.threshold:
                continue
        elif value < rule.threshold:
            continue
        # dedupe: skip if an active alert for this rule already exists
        if AlertEvent.objects.filter(rule_key=rule.key, dismissed_at__isnull=True).exists():
            continue
        level = "critical" if value >= rule.threshold * 1.5 else "warning"
        message = f"{rule.label}: {value:g} ≥ {rule.threshold:g}"
        if rule.key == "free_tier_usage_pct" and free_worst_svc:
            message = (f"{free_worst_svc} is at {value:g}% of its free tier "
                       f"(≥ {rule.threshold:g}%) — approaching paid usage")
        elif rule.key == "domain_expiry_days":
            level = "critical" if value <= 3 else "warning"
            renew = f" — renew at {domain_renew_url}" if domain_renew_url else ""
            message = f"Domain babook.co.il expires in {value:g} days{renew}"
        event = AlertEvent.objects.create(
            rule_key=rule.key,
            section=rule.section,
            level=level,
            message=message,
            value=value,
            threshold=rule.threshold,
        )
        created.append(event)
        if notify_admins:
            _notify_superusers(event)
    return created


def _notify_superusers(event):
    from ..community import notify

    admins = User.objects.filter(is_superuser=True)
    for admin in admins:
        notify(
            admin,
            verb="dashboard_alert",
            text=event.message,
            url="/admin-dashboard/#alerts",
        )
        if admin.email:
            try:
                send_mail(
                    subject=f"[babook] התראת לוח בקרה: {event.message}",
                    message=event.message,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
                    recipient_list=[admin.email],
                    fail_silently=True,
                )
            except Exception:
                pass
    event.notified = True
    event.save(update_fields=["notified"])


def active_alerts():
    from ..models import AlertEvent

    return list(AlertEvent.objects.filter(dismissed_at__isnull=True))
