"""Live backups (Google Cloud Storage) cost (REQ-8.3): pull real bucket size +
fix the label/free-tier that wrongly said 'Google Drive / 15GB'."""
from decimal import Decimal

import pytest
from django.test import override_settings


def test_label_is_gcs_not_drive():
    from app.dashboard.cost_adapters import BackupCostAdapter
    a = BackupCostAdapter()
    assert a.label == "Backups (Google Cloud Storage)"
    assert "drive" not in a.label.lower()


@pytest.mark.django_db
def test_backup_live_storage_costed(monkeypatch):
    from app.dashboard.cost_adapters import BackupCostAdapter
    a = BackupCostAdapter()
    monkeypatch.setattr(a, "_bucket_usage", lambda: (12.0, 30, None))  # 12 GB, 30 objs
    with override_settings(GCS_STORAGE_USD_PER_GB=0.020):
        amount, source, note, raw = a.fetch("2026-06")
    assert source == "live"
    # (12 - 5 free) * 0.020 = 0.14
    assert amount == Decimal("0.14")
    assert raw == {"storage_gb": 12.0, "object_count": 30}
    assert "12.00 GB in 30 backups" in note


@pytest.mark.django_db
def test_backup_within_free_tier_is_zero(monkeypatch):
    from app.dashboard.cost_adapters import BackupCostAdapter
    a = BackupCostAdapter()
    monkeypatch.setattr(a, "_bucket_usage", lambda: (3.2, 8, None))  # under 5 GB
    amount, source, note, raw = a.fetch("2026-06")
    assert source == "live" and amount == Decimal("0")
    assert "within free tier" in note


@pytest.mark.django_db
def test_backup_falls_back_without_creds(monkeypatch):
    import os

    from app.dashboard.cost_adapters import BackupCostAdapter
    monkeypatch.delenv("GCS_SERVICE_ACCOUNT", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    assert "GCS_SERVICE_ACCOUNT" not in os.environ
    amount, source, note, raw = BackupCostAdapter().fetch("2026-06")
    assert source == "estimate" and amount == Decimal("0")
    assert "free" in note and "GCS creds" in note


@pytest.mark.django_db
def test_backup_api_error_degrades(monkeypatch):
    from app.dashboard.cost_adapters import BackupCostAdapter
    a = BackupCostAdapter()

    def boom():
        raise RuntimeError("403")
    monkeypatch.setattr(a, "_bucket_usage", boom)
    amount, source, note, raw = a.fetch("2026-06")
    assert source == "estimate" and "GCS API error" in note


@pytest.mark.django_db
def test_bucket_usage_sums_sizes_and_paginates(monkeypatch):
    import base64
    import json

    from app.dashboard import cost_adapters

    monkeypatch.setenv("GCS_SERVICE_ACCOUNT", base64.b64encode(b"{}").decode())
    monkeypatch.setenv("GCS_BUCKET", "babook-backups")

    pages = [
        {"items": [{"size": str(2 * 1024 ** 3)}, {"size": str(1 * 1024 ** 3)}],
         "nextPageToken": "p2"},
        {"items": [{"size": str(1 * 1024 ** 3)}]},  # no token → stop
    ]

    class FakeResp:
        def __init__(self, d): self._d = d
        def raise_for_status(self): pass
        def json(self): return self._d

    class FakeSession:
        def __init__(self): self.calls = 0
        def get(self, url, params=None):
            d = pages[self.calls]; self.calls += 1
            return FakeResp(d)

    monkeypatch.setattr(
        "app.management.commands.backup_db._get_gcs_session", lambda creds: FakeSession())
    gb, count, err = cost_adapters.BackupCostAdapter()._bucket_usage()
    assert err is None and count == 3 and round(gb) == 4  # 2+1+1 GB
