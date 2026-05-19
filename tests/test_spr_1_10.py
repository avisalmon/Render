"""
SPR-1.10 — Database Backups
Tests for the backup_db management command (dry-run + error handling).
Run: pytest tests/test_spr_1_10.py -v
"""
import json
import sqlite3
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


pytestmark = pytest.mark.django_db


@pytest.fixture()
def real_db(tmp_path, settings):
    """Point Django at a real temp SQLite file for backup tests."""
    db_file = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.close()
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(db_file),
        }
    }
    return db_file


class TestBackupDbCommand:
    def test_dry_run_succeeds(self, real_db):
        """Dry run should complete without credentials."""
        out = StringIO()
        call_command("backup_db", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "DRY RUN" in output
        assert "Database" in output

    def test_dry_run_reports_size(self, real_db):
        """Dry run should report backup size."""
        out = StringIO()
        call_command("backup_db", "--dry-run", stdout=out)
        assert "bytes" in out.getvalue()

    def test_dry_run_includes_media(self, real_db, tmp_path, settings):
        """Dry run should mention media files."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        (media_dir / "test.jpg").write_bytes(b"\xff\xd8")
        settings.MEDIA_ROOT = str(media_dir)
        out = StringIO()
        call_command("backup_db", "--dry-run", stdout=out)
        assert "Media" in out.getvalue()

    def test_dry_run_includes_video_catalog(self, real_db):
        """Dry run should mention video catalog."""
        out = StringIO()
        call_command("backup_db", "--dry-run", stdout=out)
        assert "Video catalog" in out.getvalue()

    def test_skip_media_flag(self, real_db):
        """--skip-media should not mention media."""
        out = StringIO()
        call_command("backup_db", "--dry-run", "--skip-media", stdout=out)
        assert "Media" not in out.getvalue()

    def test_skip_videos_flag(self, real_db):
        """--skip-videos should not mention video catalog."""
        out = StringIO()
        call_command("backup_db", "--dry-run", "--skip-videos", stdout=out)
        assert "Video catalog" not in out.getvalue()

    def test_missing_credentials_raises(self, real_db):
        """Without GCS_SERVICE_ACCOUNT env var, should raise."""
        with patch.dict("os.environ", {"GCS_SERVICE_ACCOUNT": ""}, clear=False):
            with pytest.raises(CommandError, match="GCS_SERVICE_ACCOUNT"):
                call_command("backup_db", "--skip-media", "--skip-videos")

    def test_missing_database_raises(self, settings):
        """If database file doesn't exist, should raise."""
        settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": "/nonexistent/path/db.sqlite3",
            }
        }
        with pytest.raises(CommandError, match="not found"):
            call_command("backup_db", "--dry-run")

    @patch("app.management.commands.backup_db._upload_file")
    @patch("app.management.commands.backup_db._delete_old_objects")
    @patch("app.management.commands.backup_db._get_gcs_session")
    def test_upload_calls_drive_api(self, mock_session, mock_delete, mock_upload, real_db):
        """With credentials set, should call GCS API."""
        import base64

        fake_creds = base64.b64encode(json.dumps({
            "type": "service_account",
            "project_id": "test",
            "private_key_id": "x",
            "private_key": "x",
            "client_email": "test@test.iam.gserviceaccount.com",
            "client_id": "123",
        }).encode()).decode()

        mock_session.return_value = MagicMock()
        mock_upload.return_value = "db/db_backup_test.sqlite3"
        mock_delete.return_value = 0

        with patch.dict("os.environ", {
            "GCS_SERVICE_ACCOUNT": fake_creds,
            "GCS_BUCKET": "test-bucket",
        }, clear=False):
            out = StringIO()
            call_command("backup_db", "--skip-media", "--skip-videos", stdout=out)

        mock_upload.assert_called_once()
        assert "Uploaded" in out.getvalue()
