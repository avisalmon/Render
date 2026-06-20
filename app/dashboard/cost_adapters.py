"""Pluggable per-service cost adapters (REQ-8.3.*).

Each adapter knows how to report one service's spend for a month. It declares
whether its number is ``live`` (provider API), ``estimate`` (computed on-site)
or ``manual`` (admin-maintained), and degrades gracefully when its key is
absent - a service with no usable billing API still appears (estimate/manual +
deep link) and can be upgraded to live later without touching the UI
(REQ-8.3.1, DEC-63).

``run_all_adapters(period)`` runs every adapter and upserts a ``CostRecord``
per (service, period) - but never overwrites a ``manual`` override the admin
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
    default_source = "estimate"

    def _account_cost(self, admin_key, period):
        """Real org-wide spend for the month via OpenAI's Costs API. Needs an
        Admin key (sk-admin-…) with the api.usage.read scope. Returns USD float."""
        import json
        import urllib.request

        start, end = _month_bounds(period)
        url = ("https://api.openai.com/v1/organization/costs"
               f"?start_time={int(start.timestamp())}&end_time={int(end.timestamp())}"
               "&bucket_width=1d&limit=31")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {admin_key}"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        total = 0.0
        for bucket in data.get("data", []):
            for res in bucket.get("results", []):
                total += float((res.get("amount") or {}).get("value") or 0)
        return round(total, 2)

    def fetch(self, period):
        from ..models import UsageLog

        cap = getattr(settings, "OPENAI_MONTHLY_COST_CAP_USD", None)
        cap_note = f" · cap ${cap:g}" if cap else ""

        # Preferred: real account-wide spend (every key/tool on the org), live.
        admin_key = getattr(settings, "OPENAI_ADMIN_KEY", "")
        if admin_key:
            try:
                usd = self._account_cost(admin_key, period)
                return (Decimal(str(usd)), "live",
                        f"${usd:g} account spend this month{cap_note}",
                        {"account_usd": usd, "cap": cap})
            except Exception:  # noqa: BLE001 - fall back to app-only usage below
                pass

        # Fallback: only what the babook APP itself logged (UsageLog) - NOT the
        # whole account. Other tools on the same key won't show here.
        start, end = _month_bounds(period)
        logs = UsageLog.objects.filter(created_at__gte=start, created_at__lt=end)
        total = round(sum(lg.cost_usd for lg in logs), 2)
        tokens = sum(lg.prompt_tokens + lg.completion_tokens for lg in logs)
        note = (f"app usage only: {tokens:,} tokens / ${total:g} - "
                f"set OPENAI_ADMIN_KEY for full account spend{cap_note}")
        return Decimal(str(total)), "estimate", note, {"tokens": tokens, "cap": cap, "app_only": True}


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
        (REQ-8.3 live). Returns (gb, None) or (None, reason) - never raises here;
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
        except Exception as exc:  # noqa: BLE001 - API hiccup falls back to estimate
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
    FREE_LIMIT = 3000  # Resend free tier: 3,000 emails/month

    def fetch(self, period):
        if not getattr(settings, "RESEND_API_KEY", ""):
            return Decimal("0"), "manual", "set a manual figure (no API key)", {}
        # Count real sends this month from our own log - EmailSendLog rows are
        # written by the anymail post_send signal (app/apps.py). Resend has no
        # public usage endpoint, so this is the reliable source; it counts from
        # when tracking shipped (so an early month can read low).
        from django.db.models import Sum

        from ..models import EmailSendLog

        start, end = _month_bounds(period)
        sent = EmailSendLog.objects.filter(
            sent_at__gte=start, sent_at__lt=end).aggregate(n=Sum("recipients"))["n"] or 0
        pct = round(sent / self.FREE_LIMIT * 100, 1) if self.FREE_LIMIT else 0.0
        over = max(0, sent - self.FREE_LIMIT)
        if over:
            note = f"{sent:,} / {self.FREE_LIMIT:,} emails - OVER free tier by {over:,}"
        else:
            note = (f"{sent:,} / {self.FREE_LIMIT:,} emails this month "
                    f"({pct:g}% of free tier; {self.FREE_LIMIT - sent:,} left)")
        return (Decimal("0"), "live", note,
                {"emails_sent": sent, "free_limit": self.FREE_LIMIT, "free_tier_pct": pct})


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
        return Decimal("0"), "manual", "plan-based - set a manual figure (ACT-24/25)", {}


class DomainCostAdapter(CostAdapter):
    service = "domain"
    label = "Domain (babook.co.il)"
    deep_link = "https://dash.cloudflare.com"  # DNS site (refined from WHOIS nameservers)
    default_source = "manual"
    DOMAIN = "babook.co.il"
    WHOIS_SERVER = "whois.isoc.org.il"  # ISOC-IL registry for .il
    # Where each known DNS provider's records are managed.
    DNS_DASHBOARDS = {
        "cloudflare": ("Cloudflare", "https://dash.cloudflare.com"),
        "googledomains": ("Google", "https://domains.google.com"),
        "awsdns": ("AWS Route 53", "https://console.aws.amazon.com/route53/"),
    }

    def _whois(self):
        import socket

        s = socket.create_connection((self.WHOIS_SERVER, 43), timeout=12)
        try:
            s.settimeout(12)
            s.sendall((self.DOMAIN + "\r\n").encode())
            data = b""
            while True:
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
        finally:
            s.close()
        return data.decode(errors="replace")

    def fetch(self, period):
        import re
        from datetime import datetime

        try:
            txt = self._whois()
        except Exception as exc:  # noqa: BLE001 - WHOIS down → keep the manual note
            return (Decimal("0"), "manual",
                    f"annual registrar fee - set a manual figure (WHOIS unavailable: {exc})", {})

        validity = registrar = registrar_url = ""
        nameservers = []
        for line in txt.splitlines():
            l = line.strip()
            if m := re.match(r"(?i)validity:\s*(.+)", l):
                validity = m.group(1).strip()
            elif m := re.match(r"(?i)registrar name:\s*(.+)", l):
                registrar = m.group(1).strip()
            elif m := re.match(r"(?i)registrar info:\s*(\S+)", l):
                registrar_url = m.group(1).strip()
            elif m := re.match(r"(?i)nserver:\s*(\S+)", l):
                nameservers.append(m.group(1).strip().lower())

        # Expiry date (WHOIS gives dd-mm-yyyy) + days remaining.
        expiry_iso, days_left = validity, None
        try:
            d = datetime.strptime(validity, "%d-%m-%Y").date()
            expiry_iso = d.isoformat()
            days_left = (d - timezone.now().date()).days
        except ValueError:
            pass

        # Identify the DNS provider from the nameservers → its management dashboard.
        ns_blob = " ".join(nameservers)
        dns_host, dns_link = None, None
        for token, (name, url) in self.DNS_DASHBOARDS.items():
            if token in ns_blob:
                dns_host, dns_link = name, url
                break
        if dns_link:
            self.deep_link = dns_link  # persisted by run_all_adapters

        parts = []
        if expiry_iso:
            parts.append(f"expires {expiry_iso}"
                         + (f" ({days_left} days left)" if days_left is not None else ""))
        if dns_host:
            parts.append(f"DNS at {dns_host}")
        if registrar:
            parts.append(f"renew at {registrar}"
                         + (f" ({registrar_url})" if registrar_url else ""))
        note = "; ".join(parts) or "annual registrar fee - set a manual figure"

        return (Decimal("0"), "live", note, {
            "expiry": expiry_iso, "days_left": days_left, "nameservers": nameservers,
            "dns_host": dns_host, "dns_link": dns_link,
            "registrar": registrar, "registrar_url": registrar_url,
        })


class BackupCostAdapter(CostAdapter):
    service = "backups"
    label = "Backups (Google Cloud Storage)"
    deep_link = "https://console.cloud.google.com/storage/browser"
    default_source = "estimate"
    GCS_FREE_GB = 5.0  # GCS "Always Free" Standard storage (US regions)

    def _bucket_usage(self):
        """(total_gb, object_count, error) - real backup-bucket size via the GCS
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
        except Exception as exc:  # noqa: BLE001 - API hiccup degrades to estimate
            gb, count, err = None, 0, f"GCS API error: {exc}"
        if gb is None:
            return (Decimal("0"), "estimate",
                    f"{self.GCS_FREE_GB:g} GB-months free (GCS); live needs GCS creds ({err})", {})
        rate = getattr(settings, "GCS_STORAGE_USD_PER_GB", 0.020)
        cost = round(max(0.0, gb - self.GCS_FREE_GB) * rate, 2)
        # How much of the free tier is used + how far from paying.
        pct = round(gb / self.GCS_FREE_GB * 100, 1) if self.GCS_FREE_GB else 0.0
        headroom = round(max(0.0, self.GCS_FREE_GB - gb), 2)
        tail = f" → ${cost}" if cost else f" ({headroom:g} GB before paid)"
        return (Decimal(str(cost)), "live",
                f"{gb:.2f} GB in {count} objects; {pct:g}% of {self.GCS_FREE_GB:g} GB free tier{tail}",
                {"storage_gb": round(gb, 2), "object_count": count,
                 "free_limit_gb": self.GCS_FREE_GB, "free_tier_pct": pct,
                 "free_tier_headroom_gb": headroom})


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
        return Decimal("0"), "estimate", "dormant - billing deferred", {"dormant": True}


# Registry - adding a service is a one-line addition (REQ-8.3.1).
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
        if existing and existing.admin_set:
            continue  # never clobber a figure the admin typed in
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
            "admin_set": True,
            "deep_link": label_link,
            "note": note or "manual entry",
            "fetched_at": timezone.now(),
        },
    )
    return record


def adapter_labels():
    """service -> human label, for the UI and manual-entry form."""
    return {a.service: a.label for a in ADAPTERS}
