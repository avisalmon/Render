"""
Django management command: backup_db

Full disaster-recovery backup to Google Cloud Storage:
- SQLite database (WAL checkpoint + .backup API)
- Media files (incremental sync)
- Bunny Stream video catalog (metadata export for re-download)
- Retention: deletes DB backups older than 30 days
- Requires GCS_SERVICE_ACCOUNT env var (base64-encoded service account JSON)
  and GCS_BUCKET env var (GCS bucket name)
"""
import base64
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

GCS_API = "https://storage.googleapis.com/storage/v1"
GCS_UPLOAD = "https://storage.googleapis.com/upload/storage/v1"


def _get_gcs_session(credentials_json):
    """Build an authorized requests.Session for GCS API."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        credentials_json,
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )
    return AuthorizedSession(creds)


def _upload_file(session, bucket, filepath, object_name):
    """Upload a file to GCS bucket. Returns object name."""
    with open(filepath, "rb") as f:
        resp = session.post(
            f"{GCS_UPLOAD}/b/{bucket}/o",
            params={"uploadType": "media", "name": object_name},
            data=f,
            headers={"Content-Type": "application/octet-stream"},
        )
    resp.raise_for_status()
    return resp.json().get("name")


def _list_objects(session, bucket, prefix):
    """List objects in bucket with given prefix."""
    resp = session.get(
        f"{GCS_API}/b/{bucket}/o",
        params={"prefix": prefix},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _delete_old_objects(session, bucket, prefix, max_age_days):
    """Delete objects older than max_age_days with given prefix."""
    from urllib.parse import quote

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    objects = _list_objects(session, bucket, prefix)
    deleted = 0
    for obj in objects:
        created = datetime.fromisoformat(obj["timeCreated"].replace("Z", "+00:00"))
        if created < cutoff:
            name_encoded = quote(obj["name"], safe="")
            session.delete(f"{GCS_API}/b/{bucket}/o/{name_encoded}").raise_for_status()
            deleted += 1
    return deleted


class Command(BaseCommand):
    help = "Back up database, media, and video catalog to Google Cloud Storage"

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

    def _get_session(self):
        """Get authenticated GCS session from env var."""
        creds_b64 = os.environ.get("GCS_SERVICE_ACCOUNT", "")
        if not creds_b64:
            raise CommandError(
                "GCS_SERVICE_ACCOUNT env var not set. "
                "Base64-encode the service account JSON key and set it."
            )
        creds_json = json.loads(base64.b64decode(creds_b64))
        return _get_gcs_session(creds_json)

    def _get_bucket(self):
        """Get target GCS bucket name from env var."""
        bucket = os.environ.get("GCS_BUCKET", "")
        if not bucket:
            raise CommandError("GCS_BUCKET env var not set.")
        return bucket

    def _backup_database(self, db_path, tmpdir, session, bucket, dry_run, retention_days):
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
                f"  [DRY RUN] Would upload {backup_filename}"
            ))
            return

        _upload_file(session, bucket, backup_path, f"db/{backup_filename}")
        self.stdout.write(self.style.SUCCESS(f"  Uploaded db/{backup_filename}"))

        # Retention
        deleted = _delete_old_objects(session, bucket, "db/db_backup_", retention_days)
        if deleted:
            self.stdout.write(f"  Deleted {deleted} old backup(s)")

    def _backup_media(self, session, bucket, dry_run):
        """Incrementally sync media files to GCS — only upload files that are new
        or whose size changed since the last backup (REQ-1.2.4). Unchanged
        objects are left in place, so a weekly run only ships the delta."""
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write("  Media directory does not exist, skipping")
            return

        files = [f for f in media_root.rglob("*") if f.is_file()]
        self.stdout.write(f"  Media files found: {len(files)}")

        # {object_name: size} already in the bucket, so we skip unchanged files
        # instead of re-uploading everything every run.
        existing = {}
        if not dry_run:
            for obj in _list_objects(session, bucket, "media/"):
                existing[obj["name"]] = int(obj.get("size") or 0)

        to_upload = []
        for f in files:
            rel = f.relative_to(media_root)
            object_name = f"media/{rel.as_posix()}"
            if existing.get(object_name) == f.stat().st_size:
                continue  # already backed up, unchanged
            to_upload.append((f, object_name))

        skipped = len(files) - len(to_upload)
        self.stdout.write(f"  Media new or changed: {len(to_upload)} (skipping {skipped} unchanged)")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                "  [DRY RUN] Would sync only new/changed media (live run skips already-backed-up files)"
            ))
            return

        for f, object_name in to_upload:
            _upload_file(session, bucket, f, object_name)
        self.stdout.write(self.style.SUCCESS(
            f"  Uploaded {len(to_upload)} media file(s); {skipped} unchanged skipped"
        ))

    def _backup_video_catalog(self, tmpdir, session, bucket, dry_run):
        """Export Bunny video catalog (metadata for disaster recovery)."""
        from app.models import Course

        catalog = {
            "exported_at": datetime.utcnow().isoformat(),
            "bunny_library_id": settings.BUNNY_STREAM_LIBRARY_ID,
            "bunny_cdn_hostname": settings.BUNNY_STREAM_CDN_HOSTNAME,
            "courses": [],
        }

        for course in Course.objects.prefetch_related("videos").all():
            course_data = {
                "title": course.title,
                "slug": course.slug,
                "videos": [],
            }
            for video in course.videos.order_by("lesson_order"):
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
                "  [DRY RUN] Would upload video_catalog.json"
            ))
            return

        _upload_file(session, bucket, catalog_path, "video_catalog.json")
        self.stdout.write(self.style.SUCCESS("  Video catalog uploaded"))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        retention_days = options["retention_days"]
        skip_media = options["skip_media"]
        skip_videos = options["skip_videos"]

        db_path = settings.DATABASES["default"]["NAME"]
        if not Path(db_path).exists():
            raise CommandError(f"Database not found: {db_path}")

        session = None
        bucket = None
        if not dry_run:
            session = self._get_session()
            bucket = self._get_bucket()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Database backup
            self.stdout.write(self.style.MIGRATE_HEADING("=== Database backup ==="))
            self._backup_database(db_path, tmpdir, session, bucket, dry_run, retention_days)

            # 2. Media files
            if not skip_media:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Media files ==="))
                self._backup_media(session, bucket, dry_run)

            # 3. Video catalog
            if not skip_videos:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Video catalog ==="))
                self._backup_video_catalog(tmpdir, session, bucket, dry_run)

            self.stdout.write(self.style.SUCCESS("\nBackup complete."))
