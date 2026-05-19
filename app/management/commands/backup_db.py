"""
Django management command: backup_db

Full disaster-recovery backup to Google Drive via rclone:
- SQLite database (WAL checkpoint + .backup API)
- Media files (incremental sync)
- Bunny Stream video catalog (metadata export for re-download)
- Retention: deletes DB backups older than 30 days
- Requires RCLONE_CONF env var (base64-encoded rclone.conf)
"""
import base64
import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Back up database, media, and video catalog to Google Drive"

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
            help="Delete DB backups older than N days (default 30)",
        )
        parser.add_argument(
            "--skip-media",
            action="store_true",
            help="Skip media file sync",
        )
        parser.add_argument(
            "--skip-videos",
            action="store_true",
            help="Skip Bunny video catalog export",
        )

    def _rclone_cmd(self, conf_path, args):
        """Run an rclone command with the given config."""
        return subprocess.run(
            ["rclone", "--config", str(conf_path)] + args,
            capture_output=True,
            text=True,
        )

    def _backup_database(self, db_path, tmpdir, conf_path, dry_run, retention_days):
        """Back up SQLite database with WAL checkpoint."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.sqlite3"
        backup_path = Path(tmpdir) / backup_filename

        self.stdout.write(f"Creating DB backup: {backup_filename}")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            backup_conn = sqlite3.connect(str(backup_path))
            conn.backup(backup_conn)
            backup_conn.close()
        finally:
            conn.close()

        backup_size = backup_path.stat().st_size
        self.stdout.write(f"  Database size: {backup_size:,} bytes")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"  [DRY RUN] Would upload {backup_filename} to gdrive:babook-backups/db/"
            ))
            return

        result = self._rclone_cmd(conf_path, [
            "copy", str(backup_path), "gdrive:babook-backups/db/",
        ])
        if result.returncode != 0:
            raise CommandError(f"rclone DB upload failed: {result.stderr}")
        self.stdout.write(self.style.SUCCESS(f"  Uploaded {backup_filename}"))

        # Retention
        result = self._rclone_cmd(conf_path, [
            "delete", "--min-age", f"{retention_days}d", "gdrive:babook-backups/db/",
        ])
        if result.returncode != 0:
            self.stderr.write(f"  Warning: retention cleanup failed: {result.stderr}")
        else:
            self.stdout.write(f"  Cleaned backups older than {retention_days} days")

    def _backup_media(self, conf_path, dry_run):
        """Sync media files to Google Drive (incremental)."""
        media_root = settings.MEDIA_ROOT
        if not Path(media_root).exists():
            self.stdout.write("  Media directory does not exist, skipping")
            return

        file_count = sum(1 for _ in Path(media_root).rglob("*") if _.is_file())
        self.stdout.write(f"  Media files found: {file_count}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"  [DRY RUN] Would sync {file_count} media files to gdrive:babook-backups/media/"
            ))
            return

        result = self._rclone_cmd(conf_path, [
            "sync", str(media_root), "gdrive:babook-backups/media/",
        ])
        if result.returncode != 0:
            raise CommandError(f"rclone media sync failed: {result.stderr}")
        self.stdout.write(self.style.SUCCESS("  Media sync complete"))

    def _backup_video_catalog(self, tmpdir, conf_path, dry_run):
        """Export Bunny video catalog (metadata for disaster recovery)."""
        from app.models import Course

        catalog = {
            "exported_at": datetime.utcnow().isoformat(),
            "bunny_library_id": settings.BUNNY_STREAM_LIBRARY_ID,
            "bunny_cdn_hostname": settings.BUNNY_STREAM_CDN_HOSTNAME,
            "courses": [],
        }

        for course in Course.objects.prefetch_related("video_set").all():
            course_data = {
                "title": course.title,
                "slug": course.slug,
                "videos": [],
            }
            for video in course.video_set.order_by("lesson_order"):
                course_data["videos"].append({
                    "title": video.title,
                    "bunny_video_id": video.bunny_video_id,
                    "lesson_order": video.lesson_order,
                    "is_free_preview": video.is_free_preview,
                })
            catalog["courses"].append(course_data)

        catalog_path = Path(tmpdir) / "video_catalog.json"
        catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False))

        video_count = sum(len(c["videos"]) for c in catalog["courses"])
        self.stdout.write(f"  Video catalog: {len(catalog['courses'])} courses, {video_count} videos")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                "  [DRY RUN] Would upload video_catalog.json to gdrive:babook-backups/"
            ))
            return

        result = self._rclone_cmd(conf_path, [
            "copy", str(catalog_path), "gdrive:babook-backups/",
        ])
        if result.returncode != 0:
            raise CommandError(f"rclone catalog upload failed: {result.stderr}")
        self.stdout.write(self.style.SUCCESS("  Video catalog uploaded"))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        retention_days = options["retention_days"]
        skip_media = options["skip_media"]
        skip_videos = options["skip_videos"]

        db_path = settings.DATABASES["default"]["NAME"]
        if not Path(db_path).exists():
            raise CommandError(f"Database not found: {db_path}")

        rclone_conf_b64 = os.environ.get("RCLONE_CONF", "")
        if not rclone_conf_b64 and not dry_run:
            raise CommandError(
                "RCLONE_CONF env var not set. "
                "Run 'rclone config' locally, then base64-encode the config file."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = Path(tmpdir) / "rclone.conf"
            if rclone_conf_b64:
                conf_path.write_bytes(base64.b64decode(rclone_conf_b64))

            # 1. Database backup
            self.stdout.write(self.style.MIGRATE_HEADING("=== Database backup ==="))
            self._backup_database(db_path, tmpdir, conf_path, dry_run, retention_days)

            # 2. Media files
            if not skip_media:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Media files ==="))
                self._backup_media(conf_path, dry_run)

            # 3. Video catalog
            if not skip_videos:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Video catalog ==="))
                self._backup_video_catalog(tmpdir, conf_path, dry_run)

            self.stdout.write(self.style.SUCCESS("\nBackup complete."))
