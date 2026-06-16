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

    def _stored_minutes(self):
        from ..models import Video
        secs = sum(v.duration_seconds or 0 for v in Video.objects.all())
        return secs / 60.0

    def _bandwidth_gb(self, period):
        """Real GB delivered this period from Bunny's account statistics API
        (REQ-8.3 live). Returns (gb, None) or (None, reason) — never raises here;
        safe_fetch + the caller handle fallback to the estimate."""
        key = getattr(settings, "BUNNY_ACCOUNT_API_KEY", "")
        if not key:
            return None, "no BUNNY_ACCOUNT_API_KEY"
        import json
        import urllib.request

        start, end = _month_bounds(period)
        url = (f"https://api.bunny.net/statistics?dateFrom={start:%Y-%m-%d}"
               f"&dateTo={end:%Y-%m-%d}")
        req = urllib.request.Request(
            url, headers={"AccessKey": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        bytes_used = data.get("TotalBandwidthUsed") or 0
        return bytes_used / (1024 ** 3), None

    def fetch(self, period):
        minutes = self._stored_minutes()
        storage_cost = round(minutes * 0.0005, 2)  # conservative storage estimate
        rate = getattr(settings, "BUNNY_BANDWIDTH_USD_PER_GB", 0.01)

        try:
            gb, reason = self._bandwidth_gb(period)
        except Exception as exc:  # noqa: BLE001 — API hiccup falls back to estimate
            gb, reason = None, f"stats API error: {exc}"

        if gb is not None:
            bw_cost = round(gb * rate, 2)
            total = round(storage_cost + bw_cost, 2)
            note = (f"{gb:,.1f} GB delivered × ${rate}/GB = ${bw_cost} "
                    f"+ ~{minutes:,.0f} min stored")
            return (Decimal(str(total)), "live", note, {
                "bandwidth_gb": round(gb, 1), "bandwidth_cost": bw_cost,
                "storage_cost": storage_cost, "stored_minutes": round(minutes),
            })
        # No account key / API down → keep the storage-only estimate.
        return (
            Decimal(str(storage_cost)),
            "estimate",
            f"~{minutes:,.0f} min stored; live bandwidth needs BUNNY_ACCOUNT_API_KEY ({reason})",
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
    label = "Backups (Google Cloud Storage)"
    deep_link = "https://console.cloud.google.com/storage/browser"
    default_source = "estimate"
    GCS_FREE_GB = 5.0  # GCS "Always Free" Standard storage (US regions)

    def _bucket_usage(self):
        """(total_gb, object_count, error) — real backup-bucket size via the GCS
        JSON API, reusing the backup command's auth. error is None on success."""
        import base64
        import json
        import os

        creds_b64 = os.environ.get("GCS_SERVICE_ACCOUNT", "")
        bucket = os.environ.get("GCS_BUCKET", "")
        if not (creds_b64 and bucket):
            return None, 0, "no GCS_SERVICE_ACCOUNT / GCS_BUCKET"
        from app.management.commands.backup_db import GCS_API, _get_gcs_session

        session = _get_gcs_session(json.loads(base64.b64decode(creds_b64)))
        total_bytes, count, token = 0, 0, None
        while True:
            params = {"fields": "items(size),nextPageToken", "maxResults": 1000}
            if token:
                params["pageToken"] = token
            resp = session.get(f"{GCS_API}/b/{bucket}/o", params=params)
            resp.raise_for_status()
            data = resp.json()
            for it in data.get("items", []):
                total_bytes += int(it.get("size") or 0)
                count += 1
            token = data.get("nextPageToken")
            if not token:
                break
        return total_bytes / (1024 ** 3), count, None

    def fetch(self, period):
        try:
            gb, count, err = self._bucket_usage()
        except Exception as exc:  # noqa: BLE001 — API hiccup degrades to estimate
            gb, count, err = None, 0, f"GCS API error: {exc}"
        if gb is None:
            return (Decimal("0"), "estimate",
                    f"{self.GCS_FREE_GB:g} GB-months free (GCS); live needs GCS creds ({err})", {})
        rate = getattr(settings, "GCS_STORAGE_USD_PER_GB", 0.020)
        cost = round(max(0.0, gb - self.GCS_FREE_GB) * rate, 2)
        tail = f" → ${cost}" if cost else " (within free tier)"
        return (Decimal(str(cost)), "live",
                f"{gb:.2f} GB in {count} backups; first {self.GCS_FREE_GB:g} GB free{tail}",
                {"storage_gb": round(gb, 2), "object_count": count})


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
