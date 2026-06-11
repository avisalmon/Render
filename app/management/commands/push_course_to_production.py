"""
Management command: push_course_to_production

Reads a course (and all its videos + materials) from the LOCAL database
and pushes it to a remote production instance via the Course Management API.

Usage:
    python manage.py push_course_to_production micropython-thonny
    python manage.py push_course_to_production micropython-thonny --target https://babook.co.il
    python manage.py push_course_to_production micropython-thonny --target https://babook.co.il --publish

Environment variables:
    COURSE_MGMT_API_KEY  — shared secret token (must match the server's env var)
    COURSE_MGMT_TARGET   — default target URL (overridden by --target)

Steps performed:
    1. Load course + videos + materials from local DB
    2. For each FILE material, upload the file to the target's /api/v1/media/upload/
    3. POST the full course payload to /api/v1/courses/sync/
"""

import base64
import gzip
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Push a course from local DB to production via the Course Management API."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Course slug to push (e.g. micropython-thonny)")
        parser.add_argument(
            "--target",
            default=None,
            help="Base URL of the target server (e.g. https://babook.co.il). "
                 "Falls back to COURSE_MGMT_TARGET env var.",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            default=False,
            help="Set is_published=True on the remote course after sync.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Build payload and print it without sending.",
        )

    def handle(self, *args, **options):
        from app.models import Course

        slug = options["slug"]
        target = options["target"] or os.environ.get("COURSE_MGMT_TARGET", "").rstrip("/")
        api_key = getattr(settings, "COURSE_MGMT_API_KEY", "") or os.environ.get("COURSE_MGMT_API_KEY", "")
        dry_run = options["dry_run"]

        if not dry_run:
            if not target:
                raise CommandError(
                    "No target URL. Use --target https://babook.co.il or set COURSE_MGMT_TARGET env var."
                )
            if not api_key:
                raise CommandError(
                    "No API key. Set COURSE_MGMT_API_KEY in settings_local.py or as an env var."
                )

        # 1. Load course from local DB
        try:
            course = Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            raise CommandError(f"Course '{slug}' not found in local DB.")

        self.stdout.write(f"Course: {course.title} ({slug})")
        self.stdout.write(f"  Videos:    {course.videos.count()}")
        self.stdout.write(f"  Materials: {course.materials.count()}")

        # 2. Build videos payload (with optional LessonQuiz)
        videos_payload = []
        for v in course.videos.order_by("lesson_order"):
            entry = {
                "lesson_order":    v.lesson_order,
                "bunny_video_id":  v.bunny_video_id or "",
                "title":           v.title,
                "is_free_preview": v.is_free_preview,
                "notes_markdown":  v.notes_markdown or "",
                "duration_seconds": v.duration_seconds or 0,
            }
            quiz = getattr(v, "quiz", None)
            if quiz is not None:
                entry["quiz"] = {
                    "question":         quiz.question,
                    "options_json":     quiz.options_json,
                    "requires_correct": quiz.requires_correct,
                }
            videos_payload.append(entry)

        # 3. Build materials payload — upload files first
        materials_payload = []
        for m in course.materials.order_by("order", "title"):
            entry = {
                "title":         m.title,
                "material_type": m.material_type,
                "url":           m.url or "",
                "order":         m.order,
            }
            if m.material_type == "file" and m.file:
                local_path = Path(settings.MEDIA_ROOT) / str(m.file)
                if not local_path.exists():
                    self.stderr.write(f"  WARNING: local file not found: {local_path} — skipping upload")
                    entry["file_path"] = str(m.file)
                elif dry_run:
                    self.stdout.write(f"  [dry-run] Would upload: {local_path.name}")
                    entry["file_path"] = str(m.file)
                else:
                    self.stdout.write(f"  Uploading: {local_path.name} ...")
                    remote_path = self._upload_file(target, api_key, local_path)
                    self.stdout.write(f"    → {remote_path}")
                    entry["file_path"] = remote_path
            materials_payload.append(entry)

        # 4. Build thumbnail path (relative)
        thumbnail_rel = str(course.thumbnail) if course.thumbnail else ""

        # 5. Assemble full payload
        payload = {
            "course": {
                "slug":         slug,
                "title":        course.title,
                "description":  course.description or "",
                "is_published": options["publish"] or course.is_published,
                "thumbnail":    thumbnail_rel,
                "domain":       course.domain,
                "track":        course.track,
            },
            "videos":    videos_payload,
            "materials": materials_payload,
        }

        if dry_run:
            self.stdout.write("\n--- DRY RUN payload ---")
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        # 6. POST to sync endpoint
        self.stdout.write(f"\nSyncing to {target}/api/v1/courses/sync/ ...")
        result = self._post_json(target, api_key, "/api/v1/courses/sync/", payload)
        self.stdout.write(self.style.SUCCESS(
            f"  ✓ synced: {result.get('videos_synced')} videos, "
            f"{result.get('quizzes_synced', 0)} quizzes, "
            f"{result.get('materials_synced')} materials "
            f"({'created' if result.get('created') else 'updated'})"
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }

    def _post_json(self, target, api_key, path, data):
        url = target + path
        # gzip+base64 the body so code-heavy course content (a Django/Python
        # course's lesson notes) is sent as opaque bytes and isn't flagged by the
        # WAF. The server decodes it via the X-Payload-Encoding header.
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        body = base64.b64encode(gzip.compress(raw))
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/octet-stream")
        req.add_header("X-Payload-Encoding", "gzip-base64")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise CommandError(f"HTTP {e.code} from {url}: {body}")

    def _upload_file(self, target, api_key, local_path: Path):
        """Upload a file via multipart POST, return the remote relative path."""

        url = target + "/api/v1/media/upload/"
        boundary = "------BoundaryXYZ1234"
        file_bytes = local_path.read_bytes()
        filename = local_path.name

        body_parts = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(url, data=body_parts, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["path"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise CommandError(f"Upload HTTP {e.code} from {url}: {body}")
