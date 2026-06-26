"""
Insert the matazim course-page intro video as the new lesson 1 of each course
(REQ-7.3.1 / QA-13). Downloads the YouTube intro, uploads to Bunny, shifts the
existing lessons down by one. Idempotent: skips a course that already has the
intro. Run locally (has Bunny keys), then push each course to production.

    python manage.py add_course_intros            # all 9
    python manage.py add_course_intros --only python django
"""
import tempfile

from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Course, Video

# babook course slug -> YouTube intro video id (auto-discovered from matazim)
INTROS = {
    "tinkercad": "d0idL0XK2F8",
    "fusion360": "Ae-3XfZ3itA",
    "arduino-tinkercad": "308vFRiOm20",
    "arduino": "nQaaHJIdp2U",
    "scratch": "83_XBSVUS_Q",
    "scratch-advanced": "Qg8PFBOvdYk",
    "python": "i9-HWYsrh_k",
    "django": "0_bt63WLOHw",
    "video-editing": "uK6P2lTUWwc",
}
INTRO_TITLE = "מבוא להדרכה"


class Command(BaseCommand):
    help = "Insert matazim intro videos as lesson 1 (REQ-7.3.1)."

    def add_arguments(self, parser):
        parser.add_argument("--only", nargs="*", default=None)

    def handle(self, *args, **opts):
        from app.authoring.pipeline import (
            bunny_create,
            bunny_upload,
            download_youtube,
            probe_duration,
        )
        slugs = opts.get("only") or list(INTROS)
        for slug in slugs:
            yt = INTROS.get(slug)
            if not yt:
                self.stderr.write(f"no intro mapping for {slug}")
                continue
            course = Course.objects.filter(slug=slug).first()
            if not course:
                self.stderr.write(f"course not found: {slug}")
                continue
            if course.videos.filter(lesson_order=1, title=INTRO_TITLE).exists():
                self.stdout.write(f"[skip] {slug} already has the intro")
                continue

            self.stdout.write(f"[{slug}] downloading {yt} ...")
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    mp4 = download_youtube(f"https://www.youtube.com/watch?v={yt}", tmp)
                    dur = probe_duration(mp4)
                    self.stdout.write(f"[{slug}] uploading to Bunny ...")
                    guid = bunny_create(f"{course.title} - {INTRO_TITLE}")
                    bunny_upload(guid, mp4)
                except Exception as e:
                    self.stderr.write(f"[{slug}] FAILED: {e}")
                    continue

            with transaction.atomic():
                # Shift existing lessons down by one, highest-first so the
                # (course, lesson_order) unique constraint never clashes.
                for v in course.videos.order_by("-lesson_order"):
                    Video.objects.filter(pk=v.pk).update(lesson_order=v.lesson_order + 1)
                Video.objects.create(
                    course=course, lesson_order=1, title=INTRO_TITLE,
                    bunny_video_id=guid, duration_seconds=dur, is_free_preview=True,
                    summary_he="סרטון פתיחה והיכרות עם ההדרכה.",
                )
            self.stdout.write(self.style.SUCCESS(
                f"[{slug}] intro inserted as lesson 1 ({course.videos.count()} lessons)"
            ))
        self.stdout.write(self.style.SUCCESS("done"))
