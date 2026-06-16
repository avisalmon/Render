"""Live Bunny bandwidth costing (REQ-8.3) — option 1: pull real GB delivered
from Bunny's account statistics API and cost it, with graceful fallback."""
from decimal import Decimal

import pytest
from django.test import override_settings


@pytest.mark.django_db
def test_bunny_live_bandwidth_costed(monkeypatch):
    from app.dashboard.cost_adapters import BunnyCostAdapter
    a = BunnyCostAdapter()
    # 120 GB delivered this period (mock the API call)
    monkeypatch.setattr(a, "_bandwidth_gb", lambda period: (120.0, None))
    monkeypatch.setattr(a, "_stored_minutes", lambda: 600.0)
    with override_settings(BUNNY_BANDWIDTH_USD_PER_GB=0.03):
        amount, source, note, raw = a.fetch("2026-06")
    assert source == "live"
    # 120 GB * $0.03 = $3.60 bandwidth + 600 min * 0.0005 = $0.30 storage = $3.90
    assert amount == Decimal("3.9")
    assert raw["bandwidth_gb"] == 120.0 and raw["bandwidth_cost"] == 3.6
    assert "120.0 GB" in note


@pytest.mark.django_db
def test_bunny_falls_back_to_estimate_without_account_key(monkeypatch):
    from app.dashboard.cost_adapters import BunnyCostAdapter
    a = BunnyCostAdapter()
    monkeypatch.setattr(a, "_stored_minutes", lambda: 200.0)
    with override_settings(BUNNY_ACCOUNT_API_KEY=""):
        amount, source, note, raw = a.fetch("2026-06")
    assert source == "estimate"
    assert amount == Decimal("0.1")  # 200 * 0.0005
    assert "BUNNY_ACCOUNT_API_KEY" in note


@pytest.mark.django_db
def test_bunny_api_error_degrades_not_crashes(monkeypatch):
    from app.dashboard.cost_adapters import BunnyCostAdapter
    a = BunnyCostAdapter()
    monkeypatch.setattr(a, "_stored_minutes", lambda: 100.0)

    def boom(period):
        raise RuntimeError("timeout")
    monkeypatch.setattr(a, "_bandwidth_gb", boom)
    amount, source, note, raw = a.fetch("2026-06")
    assert source == "estimate" and "stats API error" in note


@pytest.mark.django_db
def test_bunny_bandwidth_parses_total_bytes(monkeypatch):
    """Parses TotalBandwidthUsed (bytes) → GB from the statistics endpoint."""
    import io
    import json

    from app.dashboard import cost_adapters

    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    payload = json.dumps({"TotalBandwidthUsed": 5 * 1024 ** 3}).encode()  # 5 GB
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=15: FakeResp(payload))
    with override_settings(BUNNY_ACCOUNT_API_KEY="acct-key"):
        gb, reason = cost_adapters.BunnyCostAdapter()._bandwidth_gb("2026-06")
    assert reason is None and round(gb) == 5
