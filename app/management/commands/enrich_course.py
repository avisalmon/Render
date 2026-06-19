"""
Management command: enrich_course

For each lesson (Video) in a course:
  1. Fetch the audio — preferring the original YouTube source mapped in
     data/course_materials/<slug>/sources.json (Bunny's CDN has token auth on
     direct play.mp4); falls back to Bunny play.mp4 if no source id is mapped.
  2. Transcribe the audio (chunked) with the strong OpenAI model, in --lang
  3. Generate faithful Hebrew notes + summary  (app.authoring.pipeline.gen_notes)
  4. Generate a Hebrew multiple-choice quiz   (app.authoring.pipeline.gen_quiz)
  5. Save notes_markdown + summary_he on the Video, upsert its LessonQuiz

SUPERVISED batch — real OpenAI cost + long runtime. Resumable: lessons that
already have notes are skipped unless --force is passed.

Usage:
    python manage.py enrich_course fpga-processor-vga --lang en --dry-run   # lesson 1 preview, no save
    python manage.py enrich_course fpga-processor-vga --lang en --lesson 5  # one lesson
    python manage.py enrich_course fpga-processor-vga --lang en             # whole course
    python manage.py enrich_course fpga-processor-vga --lang en --force     # redo even if notes exist
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from app.models import Course, LessonQuiz

STRONG_MODEL = "gpt-4o-transcribe"  # stronger than whisper-1 (no timestamps needed here)
CHUNK_SECONDS = 600
BUNNY_API_BASE = "https://video.bunnycdn.com/library"


class Command(BaseCommand):
    help = "Transcribe + generate notes & quizzes for every lesson in a course."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--lang", default="he", help="Transcription language (e.g. 'en', 'he')")
        parser.add_argument("--lesson", type=int, help="Only this lesson_order")
        parser.add_argument("--limit", type=int, default=0, help="Cap lessons processed this run")
        parser.add_argument("--dry-run", action="store_true", help="First lesson only, print, don't save")
        parser.add_argument("--force", action="store_true", help="Redo lessons that already have notes")
        parser.add_argument("--no-quiz", action="store_true", help="Skip quiz generation")

    def handle(self, *args, **opts):
        from app.authoring.pipeline import _client, _ff, gen_notes, gen_quiz, probe_duration
        from app.bunny import generate_signed_url

        course = Course.objects.filter(slug=opts["slug"]).first()
        if not course:
            self.stderr.write(f"course not found: {opts['slug']}")
            return

        lessons = list(course.videos.exclude(bunny_video_id="").order_by("lesson_order"))
        if opts["lesson"]:
            lessons = [v for v in lessons if v.lesson_order == opts["lesson"]]
        elif opts["dry_run"]:
            lessons = lessons[:1]
        elif opts["limit"]:
            lessons = lessons[: opts["limit"]]

        if not lessons:
            self.stdout.write("no matching lessons")
            return

        yt_ids = self._load_sources(course.slug)
        client = _client()
        lang = opts["lang"]
        done = skipped = failed = 0

        for v in lessons:
            if v.notes_markdown and not opts["force"] and not opts["dry_run"]:
                self.stdout.write(f"[{course.slug} #{v.lesson_order}] notes present — skipping (use --force)")
                skipped += 1
                continue

            self.stdout.write(f"[{course.slug} #{v.lesson_order}] {v.title}")
            yt_id = yt_ids.get(str(v.lesson_order))

            try:
                with tempfile.TemporaryDirectory() as tmp:
                    if yt_id:
                        self.stdout.write(f"  downloading audio from YouTube ({yt_id})…")
                        src = self._download_youtube_audio(yt_id, tmp)
                    else:
                        if not self._wait_encoded(v.bunny_video_id):
                            self.stderr.write("  no YouTube source and not encoded on Bunny — skipping")
                            failed += 1
                            continue
                        self.stdout.write("  downloading from Bunny…")
                        src = os.path.join(tmp, "v.mp4")
                        urllib.request.urlretrieve(generate_signed_url(v.bunny_video_id), src)
                    dur = probe_duration(src) or v.duration_seconds or 0

                    transcript = self._transcribe(client, _ff(), src, tmp, dur, lang)
                    if not transcript:
                        self.stderr.write("  empty transcript — skipping")
                        failed += 1
                        continue
                    self.stdout.write(f"  transcript: {len(transcript)} chars")

                    notes = gen_notes(v.title, transcript, course.title)
                    quiz = None if opts["no_quiz"] else gen_quiz(v.title, transcript, course.title)
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f"  FAILED: {type(e).__name__}: {e}")
                failed += 1
                continue

            if opts["dry_run"]:
                self.stdout.write(self.style.WARNING("  --- DRY RUN (nothing saved) ---"))
                self.stdout.write(f"  summary_he: {notes.get('summary_he', '')[:300]}")
                self.stdout.write("  notes_markdown (first 800 chars):")
                self.stdout.write(notes.get("notes_markdown", "")[:800])
                if quiz:
                    self.stdout.write(f"  quiz: {quiz['question']}")
                    for o in quiz["options"]:
                        self.stdout.write(f"      {'[x]' if o['is_correct'] else '[ ]'} {o['text']}")
                done += 1
                continue

            v.notes_markdown = notes.get("notes_markdown", "")
            v.summary_he = notes.get("summary_he", "")
            v.save(update_fields=["notes_markdown", "summary_he"])
            if quiz:
                LessonQuiz.objects.update_or_create(
                    video=v,
                    defaults={
                        "question": quiz["question"],
                        "options_json": quiz["options"],
                        "requires_correct": quiz["requires_correct"],
                    },
                )
            self.stdout.write(self.style.SUCCESS(
                f"  saved ({len(v.notes_markdown)} chars{', + quiz' if quiz else ''})"))
            done += 1

        self.stdout.write(self.style.SUCCESS(
            f"done — {done} processed, {skipped} skipped, {failed} failed. "
            "Review quality, then push_course_to_production when ready."))

    # ------------------------------------------------------------------

    def _load_sources(self, slug):
        """Return {lesson_order(str): youtube_id} from sources.json, or {}."""
        p = Path(settings.BASE_DIR) / "data" / "course_materials" / slug / "sources.json"
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8")).get("youtube_ids", {})

    def _download_youtube_audio(self, yt_id, tmp):
        """Download bestaudio as m4a for one video. Returns the local path."""
        out = os.path.join(tmp, "a.%(ext)s")
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist",
             "-f", "bestaudio[ext=m4a]/bestaudio/best", "-o", out,
             f"https://www.youtube.com/watch?v={yt_id}"],
            check=True, capture_output=True, text=True, timeout=1800)
        for name in os.listdir(tmp):
            if name.startswith("a."):
                return os.path.join(tmp, name)
        raise RuntimeError("yt-dlp produced no audio file")

    def _wait_encoded(self, guid, timeout=900):
        """Poll Bunny until the video status is 4 (finished). Returns True/False."""
        lib = settings.BUNNY_STREAM_LIBRARY_ID
        key = settings.BUNNY_API_KEY
        url = f"{BUNNY_API_BASE}/{lib}/videos/{guid}"
        deadline = time.time() + timeout
        announced = False
        while time.time() < deadline:
            try:
                req = urllib.request.Request(url, headers={"AccessKey": key, "accept": "application/json"})
                status = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("status")
            except Exception:  # noqa: BLE001
                status = None
            if status == 4:
                return True
            if status in (5, 6):  # 5 = failed, 6 = presigned upload failed
                return False
            if not announced:
                self.stdout.write("  waiting for Bunny encoding…")
                announced = True
            time.sleep(20)
        return False

    def _transcribe(self, client, ff, src, tmp, dur, lang):
        """Chunked transcription. Returns the concatenated transcript text."""
        n = max(1, math.ceil(dur / CHUNK_SECONDS)) if dur else 1
        parts = []
        for i in range(n):
            mp3 = os.path.join(tmp, f"s{i}.mp3")
            subprocess.run(
                [ff, "-y", "-ss", str(i * CHUNK_SECONDS), "-i", src,
                 "-t", str(CHUNK_SECONDS), "-vn", "-ac", "1", "-ar", "16000",
                 "-c:a", "libmp3lame", "-q:a", "5", mp3],
                check=True, capture_output=True, text=True, timeout=600)
            if os.path.getsize(mp3) < 1024:  # silent/empty tail chunk
                continue
            with open(mp3, "rb") as f:
                r = client.audio.transcriptions.create(
                    model=STRONG_MODEL, file=f, language=lang, response_format="text")
            parts.append(r if isinstance(r, str) else getattr(r, "text", str(r)))
        return "\n".join(p.strip() for p in parts if p).strip()
