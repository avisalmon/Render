"""Token-triggered backup endpoint + success marker (REQ-1.2.4).

The weekly GitHub Actions cron POSTs to /internal/run-backup/ with the shared
secret in the X-Backup-Token header; the backup runs in-process so it has the
SQLite persistent disk. The command also drops a `.last_backup` marker so the
admin dashboard's "backup age" stops showing 'unknown'.
"""
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="s3cret")
def test_requires_token(client):
    resp = client.post(reverse("run_backup"))
    assert resp.status_code == 403
    assert resp.json()["ok"] is False


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="s3cret")
def test_rejects_wrong_token(client):
    resp = client.post(reverse("run_backup"), HTTP_X_BACKUP_TOKEN="nope")
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="s3cret")
def test_get_not_allowed(client):
    resp = client.get(reverse("run_backup"), HTTP_X_BACKUP_TOKEN="s3cret")
    assert resp.status_code == 405


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="")
def test_disabled_when_no_token_configured(client):
    # An unset token must never run a backup, even if the caller also sends "".
    resp = client.post(reverse("run_backup"), HTTP_X_BACKUP_TOKEN="")
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="s3cret")
def test_valid_token_runs_backup(client):
    with patch("app.dashboard_views.call_command") as mock_cmd:
        resp = client.post(reverse("run_backup"), HTTP_X_BACKUP_TOKEN="s3cret")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_cmd.assert_called_once()
    assert mock_cmd.call_args[0][0] == "backup_db"


@pytest.mark.django_db
@override_settings(BACKUP_TRIGGER_TOKEN="s3cret")
def test_failure_is_reported(client):
    with patch("app.dashboard_views.call_command", side_effect=RuntimeError("boom")):
        resp = client.post(reverse("run_backup"), HTTP_X_BACKUP_TOKEN="s3cret")
    assert resp.status_code == 500
    body = resp.json()
    assert body["ok"] is False and "boom" in body["error"]


def test_marker_written_and_read_by_dashboard(tmp_path, settings):
    media = tmp_path / "media"
    media.mkdir()
    settings.MEDIA_ROOT = str(media)

    from app.dashboard.metrics import _last_backup_marker
    from app.management.commands.backup_db import Command

    assert _last_backup_marker() is None  # nothing yet
    Command()._write_marker()
    assert (tmp_path / ".last_backup").exists()
    assert _last_backup_marker()  # dashboard now sees a timestamp
