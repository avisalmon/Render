"""Authoring pipeline: a video -> a draft course (REQ-4.3.3).

Heavy deps (openai, imageio-ffmpeg, yt-dlp) are imported lazily so the studio
UI works even where they are not installed; only run_job() needs them.
"""
import json as _json
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from django.conf import settings
from django.db import close_old_connections
from django.utils.text import slugify


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _client():
    from openai import OpenAI
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _clean(text):
    return (text or "").replace("-", ",").replace("–", "-")


# --- source ---

def download_youtube(url, dest_dir):
    out = os.path.join(dest_dir, "source.%(ext)s")
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist",
         "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
         "--merge-output-format", "mp4", "--ffmpeg-location", _ff(),
         "-o", out, url],
        check=True, capture_output=True, text=True, timeout=1800,
    )
    for name in os.listdir(dest_dir):
        if name.startswith("source") and name.endswith(".mp4"):
            return os.path.join(dest_dir, name)
    raise RuntimeError("download produced no mp4")


def probe_duration(path):
    r = subprocess.run([_ff(), "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr)
    if not m:
        return 0
    h, mi, s = map(int, m.groups())
    return h * 3600 + mi * 60 + s


# --- transcription (whisper-1 verbose_json gives timestamps) ---

def transcribe_with_timestamps(src, dur, on_progress=None):
    client = _client()
    chunk = 600
    n = max(1, math.ceil(dur / chunk))
    segments = []
    for i in range(n):
        start = i * chunk
        mp3 = src + f".seg{i}.mp3"
        subprocess.run([_ff(), "-y", "-ss", str(start), "-i", src, "-t", str(chunk),
                        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-q:a", "9", mp3],
                       check=True, capture_output=True, text=True, timeout=300)
        with open(mp3, "rb") as f:
            r = client.audio.transcriptions.create(
                model="whisper-1", file=f, language="he", response_format="verbose_json")
        for s in (r.segments or []):
            segments.append({"start": round(float(s.start) + start, 1),
                             "end": round(float(s.end) + start, 1), "text": s.text.strip()})
        os.remove(mp3)
        if on_progress:
            on_progress(i + 1, n)
    return segments


def detect_topics(segments, dur, subject):
    client = _client()

    def mmss(s):
        return f"{int(s) // 60}:{int(s) % 60:02d}"

    lines, buf, bs = [], [], None
    for s in segments:
        if bs is None:
            bs = s["start"]
        buf.append(s["text"])
        if s["end"] - bs >= 20:
            lines.append(f"[{mmss(bs)}] {' '.join(buf)}")
            buf, bs = [], None
    if buf:
        lines.append(f"[{mmss(bs)}] {' '.join(buf)}")
    transcript = "\n".join(lines)
    prompt = (
        f"לפניך תמלול עם חותמות זמן של הרצאה בעברית בנושא: {subject}. משך כולל: {dur} שניות.\n"
        "זהה את הנושאים המרכזיים לפי הסדר וחלק לקטעים (שיעורים) בגבולות נושא טבעיים.\n"
        f"5 עד 9 קטעים רציפים המכסים את כל ההרצאה (הראשון מ-0, האחרון עד {dur}). "
        "start של כל קטע = end של הקודם. הימנע מקטע קצר מ-150 שניות.\n"
        'החזר JSON: {"sections":[{"title_he":"...","start_sec":0,"end_sec":123}]}\n\n' + transcript
    )
    r = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}],
                                       response_format={"type": "json_object"}, temperature=0.3)
    sections = _json.loads(r.choices[0].message.content)["sections"]
    sections[0]["start_sec"] = 0
    for i in range(1, len(sections)):
        sections[i]["start_sec"] = sections[i - 1]["end_sec"]
    sections[-1]["end_sec"] = dur
    return sections


def section_transcript(segments, a, b):
    return " ".join(s["text"] for s in segments if a <= s["start"] < b).strip()


def split_part(src, start, dur, out):
    subprocess.run([_ff(), "-y", "-ss", str(start), "-i", src, "-t", str(dur),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out],
                   check=True, capture_output=True, text=True, timeout=1800)


def bunny_create(title):
    lib, key = settings.BUNNY_STREAM_LIBRARY_ID, settings.BUNNY_API_KEY
    req = urllib.request.Request(f"https://video.bunnycdn.com/library/{lib}/videos",
                                 data=_json.dumps({"title": title}).encode("utf-8"),
                                 headers={"AccessKey": key, "Content-Type": "application/json",
                                          "accept": "application/json"}, method="POST")
    return _json.loads(urllib.request.urlopen(req, timeout=60).read())["guid"]


def bunny_upload(guid, mp4):
    lib, key = settings.BUNNY_STREAM_LIBRARY_ID, settings.BUNNY_API_KEY
    data = open(mp4, "rb").read()
    req = urllib.request.Request(f"https://video.bunnycdn.com/library/{lib}/videos/{guid}",
                                 data=data, headers={"AccessKey": key,
                                                     "Content-Type": "application/octet-stream"}, method="PUT")
    urllib.request.urlopen(req, timeout=3600).read()


def gen_notes(title, transcript, subject):
    client = _client()
    prompt = (
        f"אתה כותב סיכום שיעור בעברית לקורס בנושא: {subject}. כותרת הקטע: \"{title}\".\n"
        "כתוב סיכום שמשקף נאמנה את מה שהמרצה אומר בקטע (אם התמלול באנגלית, תרגם לעברית טבעית). "
        "כתוב בעברית אנושית. אסור להשתמש בקו מפריד ארוך (-). קוד ופקודות בתוך בלוק ``` בלי המילה bash. "
        "כותרות ## ו-### ורשימות. עברית בלבד, Markdown.\n"
        'החזר JSON: {"title_he":"...","summary_he":"...","notes_markdown":"..."}\n\n'
        f"תמלול הקטע:\n{transcript}"
    )
    r = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}],
                                       response_format={"type": "json_object"}, temperature=0.5, max_tokens=4096)
    d = _json.loads(r.choices[0].message.content)
    d["notes_markdown"] = _clean(d.get("notes_markdown", ""))
    d["title_he"] = _clean(d.get("title_he", "") or title)
    d["summary_he"] = _clean(d.get("summary_he", ""))
    return d


def gen_quiz(title, transcript, subject):
    """Generate one faithful Hebrew multiple-choice question for a lesson.

    Returns {"question": str, "options": [{"text": str, "is_correct": bool}, ...],
    "requires_correct": bool}. Non-gating by default (any answer unlocks Next) -
    these are review drafts. Returns None if the model can't ground a question
    in the transcript.
    """
    client = _client()
    prompt = (
        f"אתה כותב שאלת בדיקת הבנה אחת בעברית לשיעור בקורס בנושא: {subject}. "
        f"כותרת השיעור: \"{title}\".\n"
        "השאלה חייבת להיות מבוססת אך ורק על מה שנאמר בתמלול (גם אם התמלול באנגלית). "
        "כתוב שאלה ברורה אחת עם 3 או 4 תשובות, כאשר בדיוק אחת נכונה. עברית בלבד. "
        "אם אי אפשר לגזור שאלה עניינית מהתמלול, החזר {\"question\": \"\"}.\n"
        'החזר JSON: {"question":"...","options":[{"text":"...","is_correct":true},'
        '{"text":"...","is_correct":false}]}\n\n'
        f"תמלול השיעור:\n{transcript}"
    )
    r = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}],
                                       response_format={"type": "json_object"}, temperature=0.4, max_tokens=1000)
    d = _json.loads(r.choices[0].message.content)
    q = _clean(d.get("question", "")).strip()
    opts = d.get("options") or []
    # Validate: a question, >=2 options, exactly one correct.
    clean_opts = [{"text": _clean(o.get("text", "")).strip(),
                   "is_correct": bool(o.get("is_correct"))}
                  for o in opts if o.get("text")]
    if not q or len(clean_opts) < 2 or sum(o["is_correct"] for o in clean_opts) != 1:
        return None
    return {"question": q, "options": clean_opts, "requires_correct": False}


# --- orchestration ---

def run_job(job_id):
    """Process an AuthoringJob end to end, writing progress as it goes."""
    close_old_connections()
    from app.models import AuthoringJob, Course, Video
    job = AuthoringJob.objects.get(pk=job_id)
    try:
        job.mark(status="running", progress=2, step="מתחיל", log="job started")
        workdir = tempfile.mkdtemp(prefix=f"authjob{job_id}_")

        # 1) source
        if job.source_type == "youtube":
            job.mark(progress=5, step="מוריד וידאו מ-YouTube", log=f"download {job.source_url}")
            src = download_youtube(job.source_url, workdir)
        else:
            src = job.source_file.path
            job.mark(progress=5, step="משתמש בקובץ שהועלה", log=src)

        dur = probe_duration(src)
        job.mark(progress=10, step=f"משך הוידאו: {dur//60}:{dur%60:02d}", log=f"duration={dur}s")

        # 2) transcribe
        job.mark(progress=12, step="מתמלל (Whisper)")
        segments = transcribe_with_timestamps(
            src, dur,
            on_progress=lambda i, n: job.mark(
                progress=12 + int(28 * i / n), step=f"תמלול {i}/{n}", save=True))
        job.mark(progress=42, step=f"תמלול הושלם ({len(segments)} קטעים)")

        # 3) topics
        job.mark(progress=45, step="מזהה נושאים")
        sections = detect_topics(segments, dur, job.title)
        job.mark(progress=50, step=f"זוהו {len(sections)} שיעורים")

        # 4) draft course
        slug = slugify(job.title) or f"course-{job_id}"
        base, k = slug, 2
        while Course.objects.filter(slug=slug).exclude(authoring_jobs=job).exists():
            slug = f"{base}-{k}"
            k += 1
        course, _ = Course.objects.update_or_create(slug=slug, defaults={
            "title": job.title, "domain": job.domain, "track": job.track,
            "difficulty": "beginner", "is_published": False})
        job.course = course
        job.save(update_fields=["course"])
        course.videos.all().delete()

        # 5) per section: split + upload + notes
        n = len(sections)
        for i, sec in enumerate(sections, 1):
            start, end = sec["start_sec"], sec["end_sec"]
            seg_dur = end - start
            part = os.path.join(workdir, f"part_{i:02d}.mp4")
            job.mark(progress=50 + int(45 * (i - 1) / n), step=f"שיעור {i}/{n}: חיתוך", save=True)
            split_part(src, start, seg_dur, part)
            job.mark(step=f"שיעור {i}/{n}: מעלה ל-Bunny", save=True)
            guid = bunny_create(f"{slug} {i} - {sec['title_he']}")
            bunny_upload(guid, part)
            job.mark(step=f"שיעור {i}/{n}: כותב סיכום", save=True)
            tr = section_transcript(segments, start, end)
            notes = gen_notes(sec["title_he"], tr, job.title)
            Video.objects.create(
                course=course, lesson_order=i, bunny_video_id=guid,
                title=notes["title_he"], duration_seconds=seg_dur,
                is_free_preview=(i == 1), is_final_lesson=(i == n),
                notes_markdown=notes["notes_markdown"], summary_he=notes["summary_he"])
            try:
                os.remove(part)
            except OSError:
                pass

        job.mark(status="done", progress=100, step="הקורס מוכן לעריכה",
                 log=f"created course {slug} with {n} lessons")
    except Exception as e:  # noqa: BLE001
        job.mark(status="error", step="שגיאה", log=f"ERROR {type(e).__name__}: {e}")
    finally:
        close_old_connections()


def run_job_async(job_id):
    """Spawn a daemon thread to process the job (self-serve UX)."""
    import threading
    t = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    t.start()
    return t
