"""
Re-transcribe a course's lessons with the strongest OpenAI model and
regenerate high-quality faithful Hebrew notes (REQ-7.5.1 / QA-14), the
proven «Co-Coding» method.

SUPERVISED batch - real OpenAI cost + long runtime. Recommended flow:
    python manage.py backup_db                         # back up first (ACT)
    python manage.py retranscribe_course python --dry-run   # preview 1 lesson
    python manage.py retranscribe_course python             # do the course
Then review quality before doing the rest. --limit N caps lessons per run.
"""
import os
import tempfile
import urllib.request

from django.core.management.base import BaseCommand

from app.models import Course

STRONG_MODEL = "gpt-4o-transcribe"  # stronger than whisper-1 (no timestamps)
CHUNK_SECONDS = 600


class Command(BaseCommand):
    help = "Re-transcribe a course with the strong model + regenerate notes (REQ-7.5.1)."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--dry-run", action="store_true", help="first lesson only, don't save")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        import math
        import subprocess

        from app.authoring.pipeline import _client, _ff, gen_notes, probe_duration
        from app.bunny import generate_signed_url

        course = Course.objects.filter(slug=opts["slug"]).first()
        if not course:
            self.stderr.write(f"course not found: {opts['slug']}")
            return
        lessons = list(course.videos.exclude(bunny_video_id="").order_by("lesson_order"))
        if opts["dry_run"]:
            lessons = lessons[:1]
        elif opts["limit"]:
            lessons = lessons[: opts["limit"]]

        client = _client()
        for v in lessons:
            self.stdout.write(f"[{course.slug} #{v.lesson_order}] {v.title} - downloading ...")
            with tempfile.TemporaryDirectory() as tmp:
                src = os.path.join(tmp, "v.mp4")
                try:
                    url = generate_signed_url(v.bunny_video_id)
                    urllib.request.urlretrieve(url, src)
                    dur = probe_duration(src) or 0
                    # chunked strong transcription
                    parts = []
                    n = max(1, math.ceil(dur / CHUNK_SECONDS)) if dur else 1
                    for i in range(n):
                        mp3 = os.path.join(tmp, f"s{i}.mp3")
                        subprocess.run(
                            [_ff(), "-y", "-ss", str(i * CHUNK_SECONDS), "-i", src,
                             "-t", str(CHUNK_SECONDS), "-vn", "-ac", "1", "-ar", "16000",
                             "-c:a", "libmp3lame", "-q:a", "5", mp3],
                            check=True, capture_output=True, text=True, timeout=600)
                        with open(mp3, "rb") as f:
                            r = client.audio.transcriptions.create(
                                model=STRONG_MODEL, file=f, language="he",
                                response_format="text")
                        parts.append(r if isinstance(r, str) else getattr(r, "text", str(r)))
                    transcript = "\n".join(parts).strip()
                    notes = gen_notes(v.title, transcript, course.title)
                except Exception as e:
                    self.stderr.write(f"  FAILED: {e}")
                    continue

            if opts["dry_run"]:
                self.stdout.write(self.style.WARNING("--- DRY RUN notes preview ---"))
                self.stdout.write(notes[:1200])
            else:
                v.notes_markdown = notes
                v.save(update_fields=["notes_markdown"])
                self.stdout.write(self.style.SUCCESS(f"  updated ({len(notes)} chars)"))
        self.stdout.write(self.style.SUCCESS("done - review quality, then push_course_to_production"))
