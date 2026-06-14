"""Pluggable per-service cost adapters (REQ-8.3.*).

Each adapter knows how to report one service's spend for a month. It declares
whether its number is ``live`` (provider API), ``estimate`` (computed on-site)
or ``manual`` (admin-maintained), and degrades gracefully when its key is
absent — a service with no usable billing API still appears (estimate/manual +
deep link) and can be upgraded to live later without touching the UI
(REQ-8.3.1, DEC-63).

``run_all_adapters(period)`` runs every adapter and upserts a ``CostRecord``
per (service, period) — but never overwrites a ``manual`` override the admin
has set (REQ-8.3.11).
"""

from decimal import Decimal

from django.conf import settings
from django.utils import timezone


def current_period():
    """Month key ``YYYY-MM`` for now."""
    return timezone.now().strftime("%Y-%m")


def _month_bounds(period):
    from datetime import datetime

    y, mo = (int(x) for x in period.split("-"))
    start = timezone.make_aware(datetime(y, mo, 1))
    end = timezone.make_aware(datetime(y + (mo == 12), (mo % 12) + 1, 1))
    return start, end


class CostAdapter:
    """Base adapter. Subclasses set ``service``/``label``/``deep_link`` and
    implement :meth:`fetch`, returning ``(amount_usd, source, note, raw)``."""

    service = ""
    label = ""
    deep_link = ""
    default_source = "estimate"

    def fetch(self, period):  # pragma: no cover - overridden
        return Decimal("0"), self.default_source, "", {}

    def safe_fetch(self, period):
        """Run :meth:`fetch` without ever raising (REQ-8.1.7)."""
        try:
            amount, source, note, raw = self.fetch(period)
            return Decimal(str(amount or 0)), source, note, (raw or {})
        except Exception as exc:  # noqa: BLE001 - one weak adapter must not break the rest
            return Decimal("0"), "estimate", f"unavailable: {exc}", {}


class OpenAICostAdapter(CostAdapter):
    service = "openai"
    label = "OpenAI"
    deep_link = "https://platform.openai.com/usage"
    default_source = "live"

    def fetch(self, period):
        from ..models import UsageLog

        start, end = _month_bounds(period)
        logs = UsageLog.objects.filter(created_at__gte=start, created_at__lt=end)
        total = sum(lg.cost_usd for lg in logs)
        tokens = sum(lg.prompt_tokens + lg.completion_tokens for lg in logs)
        cap = getattr(settings, "OPENAI_MONTHLY_COST_CAP_USD", None)
        note = f"{tokens:,} tokens"
        if cap:
            note += f" · cap ${cap:g}"
        return Decimal(str(round(total, 2))), "live", note, {"tokens": tokens, "cap": cap}


class CopilotCostAdapter(CostAdapter):
    service = "copilot"
    label = "GitHub Copilot"
    deep_link = "https://github.com/organizations"
    default_source = "live"
    SEAT_PRICE = 19

    def fetch(self, period):
        from ..models import CopilotSeat

        active = CopilotSeat.objects.filter(status="active").count()
        amount = active * self.SEAT_PRICE
        return (
            Decimal(str(amount)),
            "live",
            f"{active} seat(s) × ${self.SEAT_PRICE}",
            {"active_seats": active, "seat_price": self.SEAT_PRICE},
        )


class BunnyCostAdapter(CostAdapter):
    service = "bunny"
    label = "Bunny Stream"
    deep_link = "https://dash.bunny.net/stream"
    default_source = "estimate"

    def fetch(self, period):
        # Storage estimate from stored video minutes; bandwidth needs the Bunny
        # statistics API (existing BUNNY_API_KEY) — wired as live later.
        from ..models import Video

        if not getattr(settings, "BUNNY_API_KEY", ""):
            return Decimal("0"), "manual", "set a manual figure (no API key)", {}
        secs = sum(v.duration_seconds or 0 for v in Video.objects.all())
        minutes = secs / 60.0
        # ~$0.01/GB stored is dominated by bandwidth; show a conservative storage
        # estimate and flag that bandwidth comes from the statistics API.
        est = round(minutes * 0.0005, 2)
        return (
            Decimal(str(est)),
            "estimate",
            f"~{minutes:,.0f} min stored; bandwidth via statistics API (ACT pending)",
            {"stored_minutes": round(minutes)},
        )


class ResendCostAdapter(CostAdapter):
    service = "resend"
    label = "Resend (email)"
    deep_link = "https://resend.com/overview"
    default_source = "estimate"

    def fetch(self, period):
        if not getattr(settings, "RESEND_API_KEY", ""):
            return Decimal("0"), "manual", "set a manual figure (no API key)", {}
        # Free tier covers 3k/mo; show $0 within tier, flag for live upgrade.
        return Decimal("0"), "estimate", "within free tier (3k/mo)", {}


class RenderCostAdapter(CostAdapter):
    service = "render"
    label = "Render (hosting)"
    deep_link = "https://dashboard.render.com"
    default_source = "manual"

    def fetch(self, period):
        token = getattr(settings, "RENDER_API_TOKEN", "")
        if not token:
            return Decimal("0"), "manual", "set a manual hosting figure (ACT-23)", {}
        return Decimal("0"), "estimate", "Render API token present", {}


class PlausibleCostAdapter(CostAdapter):
    service = "plausible"
    label = "Plausible"
    deep_link = "https://plausible.io/sites"
    default_source = "manual"

    def fetch(self, period):
        return Decimal("0"), "manual", "plan-based — set a manual figure (ACT-24/25)", {}


class DomainCostAdapter(CostAdapter):
    service = "domain"
    label = "Domain (babook.co.il)"
    deep_link = ""
    default_source = "manual"

    def fetch(self, period):
        return Decimal("0"), "manual", "annual registrar fee — set a manual figure", {}


class BackupCostAdapter(CostAdapter):
    service = "backups"
    label = "Backups (Google Drive)"
    deep_link = "https://drive.google.com"
    default_source = "estimate"

    def fetch(self, period):
        return Decimal("0"), "estimate", "free tier (15GB)", {}


class ScreenshotCostAdapter(CostAdapter):
    service = "screenshot"
    label = "Site screenshots"
    deep_link = ""
    default_source = "estimate"

    def fetch(self, period):
        return Decimal("0"), "estimate", "free service (REQ-6.3.17)", {}


class StripeCostAdapter(CostAdapter):
    service = "stripe"
    label = "Stripe + Green Invoice"
    deep_link = "https://dashboard.stripe.com"
    default_source = "estimate"

    def fetch(self, period):
        # Dormant while billing is DEFERRED (Ch 1.4 / REQ-8.3.10).
        return Decimal("0"), "estimate", "dormant — billing deferred", {"dormant": True}


# Registry — adding a service is a one-line addition (REQ-8.3.1).
ADAPTERS = [
    OpenAICostAdapter(),
    CopilotCostAdapter(),
    BunnyCostAdapter(),
    ResendCostAdapter(),
    RenderCostAdapter(),
    PlausibleCostAdapter(),
    DomainCostAdapter(),
    BackupCostAdapter(),
    ScreenshotCostAdapter(),
    StripeCostAdapter(),
]


def run_all_adapters(period=None):
    """Run every adapter and upsert a CostRecord per (service, period).

    A ``manual`` override the admin has set is preserved (REQ-8.3.11).
    Returns the list of CostRecord rows for the period (ordered by service).
    """
    from ..models import CostRecord

    period = period or current_period()
    for adapter in ADAPTERS:
        existing = CostRecord.objects.filter(service=adapter.service, period=period).first()
        if existing and existing.source == "manual":
            continue  # never clobber a manual override
        amount, source, note, raw = adapter.safe_fetch(period)
        CostRecord.objects.update_or_create(
            service=adapter.service,
            period=period,
            defaults={
                "amount_usd": amount,
                "source": source,
                "deep_link": adapter.deep_link,
                "note": note,
                "raw": raw,
                "fetched_at": timezone.now(),
            },
        )
    return list(CostRecord.objects.filter(period=period).order_by("service"))


def set_manual_cost(service, period, amount, note=""):
    """Admin manual override for a (service, period) (REQ-8.3.11)."""
    from ..models import CostRecord

    label_link = next((a.deep_link for a in ADAPTERS if a.service == service), "")
    record, _ = CostRecord.objects.update_or_create(
        service=service,
        period=period,
        defaults={
            "amount_usd": Decimal(str(amount or 0)),
            "source": "manual",
            "deep_link": label_link,
            "note": note or "manual entry",
            "fetched_at": timezone.now(),
        },
    )
    return record


def adapter_labels():
    """service -> human label, for the UI and manual-entry form."""
    return {a.service: a.label for a in ADAPTERS}
