"""EPIC-8 — Admin / Management Control Dashboard models.

Persistence for the superuser-only cockpit at ``/admin-dashboard/``:

* :class:`DashboardSnapshot` — a nightly (or on-demand) capture of internal
  metrics, so the dashboard loads instantly and trends derive from history.
* :class:`CostRecord` — one row per service per period; the value may be
  ``live`` (provider API), ``estimate`` (computed on-site) or ``manual``
  (admin-maintained). REQ-8.1.3 / REQ-8.3.*.
* :class:`AlertRule` — admin-editable thresholds (REQ-8.6.3).
* :class:`AlertEvent` — a raised, dismissible alert surfaced on the hub
  (REQ-8.6.2).
"""

from django.db import models
from django.utils import timezone

# Dashboard sections — used as the ``scope`` of a snapshot and the ``section``
# an alert links back to.
SECTION_CHOICES = [
    ("users_training", "Users & Training"),
    ("costs", "Costs"),
    ("engagement", "Engagement"),
    ("system", "System"),
    ("all", "All"),
]

COST_SOURCE_CHOICES = [
    ("live", "Live (API)"),
    ("estimate", "Estimate (computed)"),
    ("manual", "Manual (admin)"),
]


class DashboardSnapshot(models.Model):
    """A point-in-time capture of dashboard metrics (REQ-8.1.3).

    ``metrics`` holds the section payload as JSON so adding a metric never
    needs a migration; ``scope`` records which section (or ``all``) it covers.
    """

    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    scope = models.CharField(max_length=20, choices=SECTION_CHOICES, default="all")
    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [models.Index(fields=["scope", "-captured_at"])]

    def __str__(self):
        return f"snapshot[{self.scope}] @ {self.captured_at:%Y-%m-%d %H:%M}"


class CostRecord(models.Model):
    """Spend for one service in one period (REQ-8.1.3 / REQ-8.3.*).

    ``period`` is a month key like ``2026-06`` so month-over-month trends are a
    simple group-by. ``source`` distinguishes live / estimate / manual so the
    UI can badge each figure honestly. A manual override for a (service, period)
    wins over an adapter-produced row.
    """

    service = models.CharField(max_length=40, db_index=True)
    period = models.CharField(max_length=7, db_index=True, help_text="YYYY-MM")
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.CharField(max_length=10, choices=COST_SOURCE_CHOICES, default="estimate")
    deep_link = models.URLField(blank=True, default="")
    note = models.CharField(max_length=300, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    # True only when an admin typed a manual figure (set_manual_cost). Adapters
    # never set this, so an adapter that returns source="manual" (e.g. domain,
    # render) is still refreshed each capture — only a real override is frozen.
    admin_set = models.BooleanField(default=False)

    class Meta:
        ordering = ["service", "-period"]
        indexes = [models.Index(fields=["service", "period"])]

    def __str__(self):
        return f"{self.service} {self.period}: ${self.amount_usd} ({self.source})"


class AlertRule(models.Model):
    """An admin-editable alerting threshold (REQ-8.6.3).

    ``key`` identifies the metric the rule watches (e.g. ``spend_total``,
    ``report_queue``, ``unanswered_age_hours``, ``backup_stale_hours``).
    Disabled rules never fire.
    """

    key = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=120)
    threshold = models.FloatField(default=0)
    enabled = models.BooleanField(default=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default="all")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} ≥ {self.threshold} ({'on' if self.enabled else 'off'})"


class AlertEvent(models.Model):
    """A raised alert, surfaced on the hub until dismissed (REQ-8.6.2)."""

    LEVELS = [("warning", "Warning"), ("critical", "Critical")]

    rule_key = models.CharField(max_length=40, db_index=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default="all")
    level = models.CharField(max_length=10, choices=LEVELS, default="warning")
    message = models.CharField(max_length=300)
    value = models.FloatField(default=0)
    threshold = models.FloatField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        state = "dismissed" if self.dismissed_at else "active"
        return f"alert[{self.rule_key}] {self.level} ({state})"

    @property
    def is_active(self):
        return self.dismissed_at is None
