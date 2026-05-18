"""
Django management command: backup_db

Safely backs up the SQLite database to Google Drive via rclone.
- WAL checkpoint for consistency
- Timestamped filename
- Retention: deletes backups older than 30 days
- Requires RCLONE_CONF env var (base64-encoded rclone.conf)
"""
import base64
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Back up db.sqlite3 to Google Drive via rclone"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually uploading",
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=30,
            help="Delete backups older than N days (default 30)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        retention_days = options["retention_days"]

        db_path = settings.DATABASES["default"]["NAME"]
        if not Path(db_path).exists():
            raise CommandError(f"Database not found: {db_path}")

        # 1. Write rclone config from env var
        rclone_conf_b64 = os.environ.get("RCLONE_CONF", "")
        if not rclone_conf_b64 and not dry_run:
            raise CommandError(
                "RCLONE_CONF env var not set. "
                "Run 'rclone config' locally, then base64-encode the config file."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write rclone config
            conf_path = Path(tmpdir) / "rclone.conf"
            if rclone_conf_b64:
                conf_path.write_bytes(base64.b64decode(rclone_conf_b64))

            # 2. Create safe backup via sqlite3 .backup
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"db_backup_{timestamp}.sqlite3"
            backup_path = Path(tmpdir) / backup_filename

            self.stdout.write(f"Creating backup: {backup_filename}")
            conn = sqlite3.connect(db_path)
            try:
                # WAL checkpoint first for consistency
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                # Use sqlite3 backup API
                backup_conn = sqlite3.connect(str(backup_path))
                conn.backup(backup_conn)
                backup_conn.close()
            finally:
                conn.close()

            backup_size = backup_path.stat().st_size
            self.stdout.write(f"Backup size: {backup_size:,} bytes")

            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"[DRY RUN] Would upload {backup_filename} to gdrive:babook-backups/"
                ))
                return

            # 3. Upload to Google Drive
            self.stdout.write("Uploading to Google Drive...")
            result = subprocess.run(
                [
                    "rclone", "copy",
                    "--config", str(conf_path),
                    str(backup_path),
                    "gdrive:babook-backups/",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise CommandError(f"rclone upload failed: {result.stderr}")

            self.stdout.write(self.style.SUCCESS(
                f"Uploaded {backup_filename} to gdrive:babook-backups/"
            ))

            # 4. Retention — delete old backups
            self.stdout.write(f"Cleaning backups older than {retention_days} days...")
            result = subprocess.run(
                [
                    "rclone", "delete",
                    "--config", str(conf_path),
                    "--min-age", f"{retention_days}d",
                    "gdrive:babook-backups/",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.stderr.write(f"Warning: retention cleanup failed: {result.stderr}")
            else:
                self.stdout.write(self.style.SUCCESS("Retention cleanup done."))
