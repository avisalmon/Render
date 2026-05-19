"""
Django management command: backup_db

Full disaster-recovery backup to Google Drive via Python API:
- SQLite database (WAL checkpoint + .backup API)
- Media files (incremental sync)
- Bunny Stream video catalog (metadata export for re-download)
- Retention: deletes DB backups older than 30 days
- Requires GDRIVE_SERVICE_ACCOUNT env var (base64-encoded service account JSON)
  and GDRIVE_FOLDER_ID env var (Google Drive folder ID to upload into)
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


def _get_drive_service(credentials_json):
    """Build Google Drive API service from service account credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        credentials_json,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=creds)


def _upload_file(service, filepath, folder_id, filename=None):
    """Upload a file to a Google Drive folder. Returns file ID."""
    from googleapiclient.http import MediaFileUpload

    fname = filename or Path(filepath).name
    file_metadata = {"name": fname, "parents": [folder_id]}
    media = MediaFileUpload(str(filepath), resumable=True)
    result = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    return result.get("id")


def _ensure_subfolder(service, parent_id, folder_name):
    """Get or create a subfolder. Returns folder ID."""
    query = (
        f"name='{folder_name}' and '{parent_id}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    # Create
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder.get("id")


def _delete_old_files(service, folder_id, prefix, max_age_days):
    """Delete files in folder older than max_age_days with given prefix."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    query = (
        f"'{folder_id}' in parents and name contains '{prefix}' "
        f"and createdTime < '{cutoff_str}' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id,name)").execute()
    deleted = 0
    for f in results.get("files", []):
        service.files().delete(fileId=f["id"]).execute()
        deleted += 1
    return deleted


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

    def _get_service(self):
        """Get authenticated Drive service from env var."""
        creds_b64 = os.environ.get("GDRIVE_SERVICE_ACCOUNT", "")
        if not creds_b64:
            raise CommandError(
                "GDRIVE_SERVICE_ACCOUNT env var not set. "
                "Create a service account in Google Cloud Console, "
                "download the JSON key, base64-encode it, and set the env var."
            )
        creds_json = json.loads(base64.b64decode(creds_b64))
        return _get_drive_service(creds_json)

    def _get_folder_id(self):
        """Get target Drive folder ID from env var."""
        folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")
        if not folder_id:
            raise CommandError(
                "GDRIVE_FOLDER_ID env var not set. "
                "Create a folder in Google Drive, share it with the service account email, "
                "and set GDRIVE_FOLDER_ID to the folder's ID from the URL."
            )
        return folder_id

    def _backup_database(self, db_path, tmpdir, service, folder_id, dry_run, retention_days):
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

        db_folder = _ensure_subfolder(service, folder_id, "db")
        _upload_file(service, backup_path, db_folder, backup_filename)
        self.stdout.write(self.style.SUCCESS(f"  Uploaded {backup_filename}"))

        # Retention
        deleted = _delete_old_files(service, db_folder, "db_backup_", retention_days)
        if deleted:
            self.stdout.write(f"  Deleted {deleted} old backup(s)")

    def _backup_media(self, service, folder_id, dry_run):
        """Upload media files to Google Drive."""
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write("  Media directory does not exist, skipping")
            return

        files = [f for f in media_root.rglob("*") if f.is_file()]
        self.stdout.write(f"  Media files found: {len(files)}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"  [DRY RUN] Would sync {len(files)} media files"
            ))
            return

        media_folder = _ensure_subfolder(service, folder_id, "media")
        for f in files:
            rel = f.relative_to(media_root)
            # Create subfolder structure
            target_folder = media_folder
            for part in rel.parts[:-1]:
                target_folder = _ensure_subfolder(service, target_folder, part)
            _upload_file(service, f, target_folder, rel.name)
        self.stdout.write(self.style.SUCCESS(f"  Uploaded {len(files)} media file(s)"))

    def _backup_video_catalog(self, tmpdir, service, folder_id, dry_run):
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
                "  [DRY RUN] Would upload video_catalog.json"
            ))
            return

        _upload_file(service, catalog_path, folder_id, "video_catalog.json")
        self.stdout.write(self.style.SUCCESS("  Video catalog uploaded"))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        retention_days = options["retention_days"]
        skip_media = options["skip_media"]
        skip_videos = options["skip_videos"]

        db_path = settings.DATABASES["default"]["NAME"]
        if not Path(db_path).exists():
            raise CommandError(f"Database not found: {db_path}")

        service = None
        folder_id = None
        if not dry_run:
            service = self._get_service()
            folder_id = self._get_folder_id()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Database backup
            self.stdout.write(self.style.MIGRATE_HEADING("=== Database backup ==="))
            self._backup_database(db_path, tmpdir, service, folder_id, dry_run, retention_days)

            # 2. Media files
            if not skip_media:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Media files ==="))
                self._backup_media(service, folder_id, dry_run)

            # 3. Video catalog
            if not skip_videos:
                self.stdout.write(self.style.MIGRATE_HEADING("=== Video catalog ==="))
                self._backup_video_catalog(tmpdir, service, folder_id, dry_run)

            self.stdout.write(self.style.SUCCESS("\nBackup complete."))
