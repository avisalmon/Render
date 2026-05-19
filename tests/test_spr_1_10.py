"""
SPR-1.10 — Database Backups
Tests for the backup_db management command (dry-run + error handling).
Run: pytest tests/test_spr_1_10.py -v
"""
import sqlite3
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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
        """Dry run should complete without RCLONE_CONF."""
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

    def test_missing_rclone_conf_raises(self, real_db):
        """Without RCLONE_CONF env var and not dry-run, should raise."""
        with patch.dict("os.environ", {"RCLONE_CONF": ""}, clear=False):
            with pytest.raises(CommandError, match="RCLONE_CONF"):
                call_command("backup_db")

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

    @patch("subprocess.run")
    def test_upload_calls_rclone(self, mock_run, real_db):
        """With RCLONE_CONF set, should call rclone for db, media, and catalog."""
        import base64

        fake_conf = base64.b64encode(b"[gdrive]\ntype = drive\n").decode()
        mock_run.return_value = type("Result", (), {"returncode": 0, "stderr": ""})()

        with patch.dict("os.environ", {"RCLONE_CONF": fake_conf}, clear=False):
            out = StringIO()
            call_command("backup_db", "--skip-media", "--skip-videos", stdout=out)

        # DB: copy + delete (retention)
        assert mock_run.call_count == 2
        copy_args = mock_run.call_args_list[0][0][0]
        assert "copy" in copy_args
        delete_args = mock_run.call_args_list[1][0][0]
        assert "delete" in delete_args

    @patch("subprocess.run")
    def test_upload_failure_raises(self, mock_run, real_db):
        """If rclone copy fails, should raise CommandError."""
        import base64

        fake_conf = base64.b64encode(b"[gdrive]\ntype = drive\n").decode()
        mock_run.return_value = type(
            "Result", (), {"returncode": 1, "stderr": "network error"}
        )()

        with patch.dict("os.environ", {"RCLONE_CONF": fake_conf}, clear=False):
            with pytest.raises(CommandError, match="rclone.*failed"):
                call_command("backup_db", "--skip-media", "--skip-videos")
