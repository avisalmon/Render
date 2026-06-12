"""Pull a course from production into the local DB (local <- prod), so local
edits start from the live version. Mirror of push_course_to_production.

Usage:
    python manage.py pull_course_from_production <slug>
    python manage.py pull_course_from_production <slug> --target https://babook.co.il
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from app.models import Course, CourseMaterial, LessonQuiz, Video


class Command(BaseCommand):
    help = "Pull a course from production into the local DB (local <- prod)."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--target", default="https://babook.co.il")

    def handle(self, *args, **options):
        slug = options["slug"]
        target = options["target"].rstrip("/")
        key = getattr(settings, "COURSE_MGMT_API_KEY", "")
        url = f"{target}/api/v1/courses/{slug}/"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except urllib.error.HTTPError as e:
            raise CommandError(f"pull failed for {slug}: HTTP {e.code}") from e

        cd = data["course"]
        edited = parse_datetime(cd["studio_edited_at"]) if cd.get("studio_edited_at") else None
        course, _ = Course.objects.update_or_create(slug=slug, defaults={
            "title": cd["title"], "title_en": cd.get("title_en", ""),
            "description": cd.get("description", ""), "domain": cd.get("domain", "matazim"),
            "track": cd.get("track", ""), "difficulty": cd.get("difficulty", "beginner"),
            "thumbnail": cd.get("thumbnail", ""), "is_published": cd.get("is_published", False),
            "studio_edited_at": edited,
        })

        orders = []
        for vd in data.get("videos", []):
            o = vd["lesson_order"]
            orders.append(o)
            v, _ = Video.objects.update_or_create(course=course, lesson_order=o, defaults={
                "bunny_video_id": vd.get("bunny_video_id", ""), "title": vd.get("title", ""),
                "title_en": vd.get("title_en", ""), "is_free_preview": vd.get("is_free_preview", False),
                "is_final_lesson": vd.get("is_final_lesson", False),
                "notes_markdown": vd.get("notes_markdown", ""), "summary_he": vd.get("summary_he", ""),
                "reflection_prompt": vd.get("reflection_prompt", ""),
                "duration_seconds": vd.get("duration_seconds", 0),
            })
            quiz = vd.get("quiz")
            if quiz:
                LessonQuiz.objects.update_or_create(video=v, defaults={
                    "question": quiz.get("question", ""),
                    "options_json": quiz.get("options_json", []),
                    "requires_correct": quiz.get("requires_correct", False),
                })
            else:
                LessonQuiz.objects.filter(video=v).delete()

        course.videos.exclude(lesson_order__in=orders).delete()

        for md in data.get("materials", []):
            CourseMaterial.objects.update_or_create(
                course=course, title=md.get("title", ""),
                defaults={"material_type": md.get("material_type", CourseMaterial.LINK),
                          "url": md.get("url", ""), "order": md.get("order", 0)})

        self.stdout.write(self.style.SUCCESS(
            f"Pulled {slug}: {len(orders)} lessons (studio_edited_at={edited})"))
