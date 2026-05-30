"""
Management command: load_course_from_manifest

Reads data/course_materials/<slug>/course_manifest.json and upserts the Course
and Video records into the database.  Idempotent — safe to run on every deploy.

Usage:
    python manage.py load_course_from_manifest                  # all manifests
    python manage.py load_course_from_manifest micropython-thonny  # one course

Called automatically from render.yaml startCommand (after migrate, before gunicorn).
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.models import Course, Video

BASE_DIR = Path(settings.BASE_DIR)
MATERIALS_ROOT = BASE_DIR / "data" / "course_materials"


class Command(BaseCommand):
    help = "Upsert Course and Video records from course_manifest.json files."

    def add_arguments(self, parser):
        parser.add_argument(
            "slugs",
            nargs="*",
            help="Course slug(s) to load.  Omit to load all manifests found.",
        )

    def handle(self, *args, **options):
        slugs = options["slugs"]

        if slugs:
            manifest_paths = []
            for slug in slugs:
                p = MATERIALS_ROOT / slug / "course_manifest.json"
                if not p.exists():
                    raise CommandError(f"Manifest not found: {p}")
                manifest_paths.append(p)
        else:
            manifest_paths = sorted(MATERIALS_ROOT.glob("*/course_manifest.json"))
            if not manifest_paths:
                self.stdout.write(self.style.WARNING(f"No manifests found under {MATERIALS_ROOT}"))
                return

        for path in manifest_paths:
            self._load_manifest(path)

    def _load_manifest(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data["course_slug"]

        # --- Course record ---
        course_defaults = {
            "title": data.get("course_title", slug),
            "description": data.get("course_description", ""),
            "thumbnail": data.get("thumbnail", ""),
            "difficulty": data.get("difficulty", "beginner"),
            "is_published": data.get("is_published", False),
            "category": data.get("category", ""),
        }

        course, course_created = Course.objects.update_or_create(
            slug=slug,
            defaults=course_defaults,
        )
        action = "created" if course_created else "updated"
        self.stdout.write(f"  Course {action}: {course.title} ({slug})")

        # --- Video records ---
        created_count = 0
        updated_count = 0

        for lesson in data.get("lessons", []):
            bunny_id = lesson.get("bunny_video_id")
            if not bunny_id:
                self.stdout.write(
                    self.style.WARNING(f"    L{lesson['lesson_order']:02d}: no bunny_video_id, skipping")
                )
                continue

            video_defaults = {
                "bunny_video_id": bunny_id,
                "title": lesson.get("title_he") or lesson.get("youtube_title", ""),
                "duration_seconds": lesson.get("duration_seconds") or 0,
                "is_free_preview": lesson.get("is_free_preview", False),
                "notes_markdown": lesson.get("notes_markdown", ""),
                "title_en": lesson.get("title_en", ""),
                "summary_he": lesson.get("summary_he", ""),
                "has_code_example": lesson.get("has_code_example", False),
                "github_file": lesson.get("github_file") or "",
            }

            _video, video_created = Video.objects.update_or_create(
                course=course,
                lesson_order=lesson["lesson_order"],
                defaults=video_defaults,
            )
            if video_created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"    Videos: {created_count} created, {updated_count} updated"
            )
        )
