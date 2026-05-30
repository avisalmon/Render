"""
transcribe_course.py
====================
For each lesson in the micropython-thonny course:
  1. Download audio-only from YouTube (via yt-dlp)
  2. Transcribe with Azure Whisper (Hebrew)
  3. Fetch matching demo code from GitHub (avisalmon/single_button)
  4. Analyse with Azure GPT: generate lesson title, objectives, notes
  5. Save to data/course_materials/micropython-thonny/lesson_NN.json

Re-runnable: already-completed lessons are skipped unless --force is passed.

Usage:
  python scripts/transcribe_course.py [--force] [--lesson N]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "course_materials" / "micropython-thonny"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PLAYLIST_URL = "https://youtube.com/playlist?list=PL0zMMCdiaE56wAuAqmGXPQlCa_2BCWRi6"

AZURE_API_BASE = "https://oai-modelon-eastus2.cognitiveservices.azure.com"
AZURE_API_VERSION = "2025-04-01-preview"
WHISPER_DEPLOYMENT = "whisper"
CHAT_DEPLOYMENT = "gpt-5.3-chat"

PROXIES = {
    "http":  "http://proxy-iil.intel.com:912",
    "https": "http://proxy-iil.intel.com:912",
}

GITHUB_RAW = "https://raw.githubusercontent.com/avisalmon/single_button/main/{filename}"

# All known .py files in the repo, ordered by number prefix
GITHUB_PY_FILES = [
    "010 lines.py",
    "020 move the line.py",
    "030 more than lines.py",
    "040 text.py",
    "050 read button.py",
    "060 blit.py",
    "070 move around.py",
    "080 few players.py",
    "090 pong part 1.py",
    "100 pong part 2.py",
    "110 pong part 3 colision.py",
    "120 pong part 4 beep.py",
    "130 smake.py",
    "140 simon.py",
    "150 space.py",
    "170 space animated.py",
    "210 watch example.py",
    "220 robot arm.py",
    "230 robot arm controlled.py",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_azure_key():
    env_path = Path.home() / ".copilot" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("AZURE_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("AZURE_API_KEY not found in ~/.copilot/.env")


def fetch_playlist_metadata():
    """Return list of {index, id, title, duration_seconds}."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--print", "%(playlist_index)s\t%(id)s\t%(title)s\t%(duration)s",
        PLAYLIST_URL,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        idx_str, yt_id, title, dur = parts
        try:
            idx = int(idx_str)
            duration = int(float(dur)) if dur not in ("NA", "None", "") else 0
        except ValueError:
            continue
        videos.append({"index": idx, "id": yt_id, "title": title, "duration_seconds": duration})
    return videos


def download_audio(yt_id, tmpdir, idx):
    """Download audio-only (mp3) for a single video. Returns file path or None."""
    out_template = os.path.join(tmpdir, f"{idx:03d}_%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",   # 128kbps-ish — good enough for speech
        "-o", out_template,
        f"https://www.youtube.com/watch?v={yt_id}",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    for fname in sorted(os.listdir(tmpdir)):
        if fname.startswith(f"{idx:03d}_") and fname.endswith(".mp3"):
            return os.path.join(tmpdir, fname)
    return None


def transcribe_audio(audio_path, azure_key):
    """Send audio to Azure Whisper. Returns transcript string or None."""
    url = (
        f"{AZURE_API_BASE}/openai/deployments/{WHISPER_DEPLOYMENT}"
        f"/audio/transcriptions?api-version={AZURE_API_VERSION}"
    )
    headers = {"api-key": azure_key}
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data = {"language": "he", "response_format": "json"}
        r = requests.post(url, headers=headers, files=files, data=data,
                          proxies=PROXIES, timeout=300)
    if r.status_code == 200:
        return r.json().get("text", "")
    print(f"  Whisper error {r.status_code}: {r.text[:200]}")
    return None


def fetch_github_code(video_title):
    """Try to find the matching .py file by numeric prefix. Returns (filename, code) or (None, None)."""
    # Extract leading number from video title (e.g. "010 lines" → "010", "021 move" → "021")
    m = re.match(r"^(\d+)", video_title.strip())
    if not m:
        return None, None
    prefix = m.group(1)

    # Find .py file whose name starts with the same prefix
    for fname in GITHUB_PY_FILES:
        if fname.startswith(prefix + " ") or fname.startswith(prefix + "_"):
            raw_url = GITHUB_RAW.format(filename=quote(fname))
            r = requests.get(raw_url, proxies=PROXIES, timeout=15)
            if r.status_code == 200:
                return fname, r.text
    return None, None


def analyse_lesson(title, transcript, code, azure_key):
    """Call GPT to generate structured lesson notes from transcript + code."""
    code_block = f"\n\nCode from demo file:\n```python\n{code}\n```" if code else ""
    prompt = f"""You are building a MicroPython course for Israeli engineering teams.
Below is the Hebrew transcript of a lesson titled "{title}",{code_block}

Based on the transcript (and code if provided), produce a JSON object with these keys:
- "title_he": short lesson title in Hebrew (5-8 words)
- "title_en": short lesson title in English (5-8 words)
- "objectives": list of 3-4 learning objectives in Hebrew (what the student will be able to do after this lesson)
- "summary_he": 2-3 paragraph lesson summary in Hebrew (what is taught, key concepts, tips)
- "notes_markdown": markdown lesson notes in Hebrew, 200-400 words, with ### headings, bullet points, and a code example if relevant
- "difficulty": one of "beginner", "intermediate", "advanced"
- "keywords": list of 4-6 Hebrew/English keywords

Respond ONLY with valid JSON. No explanation, no markdown wrapper.

Transcript:
{transcript[:6000]}"""

    url = (
        f"{AZURE_API_BASE}/openai/deployments/{CHAT_DEPLOYMENT}"
        f"/chat/completions?api-version={AZURE_API_VERSION}"
    )
    headers = {"api-key": azure_key, "Content-Type": "application/json"}
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 1200,
    }
    r = requests.post(url, headers=headers, json=body, proxies=PROXIES, timeout=120)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        content = re.sub(r"^```json\s*|```$", "", content, flags=re.MULTILINE).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"  JSON parse error — raw response saved")
            return {"raw_analysis": content}
    print(f"  GPT error {r.status_code}: {r.text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-process already-done lessons")
    parser.add_argument("--lesson", type=int, help="Process only this lesson index")
    parser.add_argument("--analyse-only", action="store_true", dest="analyse_only",
                        help="Skip download/transcription; only run GPT analysis on saved JSON files")
    args = parser.parse_args()

    print("Loading Azure key…")
    azure_key = load_azure_key()

    print("Fetching playlist metadata…")
    videos = fetch_playlist_metadata()
    print(f"Found {len(videos)} videos.\n")

    if args.lesson:
        videos = [v for v in videos if v["index"] == args.lesson]
        if not videos:
            print(f"Lesson {args.lesson} not found.")
            return

    if args.analyse_only:
        print("Analyse-only mode — reading saved JSON files and filling missing analysis…\n")
        for json_file in sorted(OUTPUT_DIR.glob("lesson_*.json")):
            result = json.loads(json_file.read_text(encoding="utf-8"))
            if result.get("analysis") and not args.force:
                print(f"  {json_file.name}: analysis already present — skipping")
                continue
            transcript = result.get("transcript_he", "")
            code = result.get("github_code")
            title = result.get("youtube_title", json_file.stem)
            if not transcript:
                print(f"  {json_file.name}: no transcript — skipping")
                continue
            print(f"  {json_file.name}: analysing '{title}'…")
            analysis = analyse_lesson(title, transcript, code, azure_key)
            if analysis:
                result["analysis"] = analysis
                json_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"    Done")
            else:
                print(f"    Failed")
        print("\nAnalysis pass complete.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        for v in videos:
            idx = v["index"]
            yt_id = v["id"]
            title = v["title"]
            out_path = OUTPUT_DIR / f"lesson_{idx:02d}.json"

            print(f"[{idx:>2}/15] {title}")

            if out_path.exists() and not args.force:
                print("  Already done — skipping (use --force to redo)\n")
                continue

            result = {
                "lesson_order": idx,
                "youtube_id": yt_id,
                "youtube_title": title,
                "duration_seconds": v["duration_seconds"],
            }

            # 1. Download audio
            print("  Downloading audio…")
            try:
                audio_path = download_audio(yt_id, tmpdir, idx)
            except subprocess.CalledProcessError as e:
                print(f"  Download failed: {e.stderr.decode()[:200]}\n")
                continue

            if not audio_path:
                print("  Audio file not found after download\n")
                continue

            size_mb = Path(audio_path).stat().st_size // 1_048_576
            print(f"  Audio: {size_mb} MB")

            # 2. Transcribe
            print("  Transcribing (Azure Whisper, Hebrew)…")
            transcript = transcribe_audio(audio_path, azure_key)
            if transcript:
                result["transcript_he"] = transcript
                print(f"  Transcript: {len(transcript)} chars")
            else:
                result["transcript_he"] = ""
                print("  Transcription failed")

            # Clean up audio immediately
            try:
                os.remove(audio_path)
            except OSError:
                pass

            # 3. Fetch GitHub code
            code_file, code = fetch_github_code(title)
            if code_file:
                result["github_file"] = code_file
                result["github_code"] = code
                print(f"  Code: {code_file} ({len(code)} chars)")
            else:
                result["github_file"] = None
                result["github_code"] = None
                print("  No matching code file")

            # 4. Analyse
            if result["transcript_he"]:
                print("  Analysing with GPT…")
                analysis = analyse_lesson(title, result["transcript_he"], code, azure_key)
                if analysis:
                    result["analysis"] = analysis
                    print(f"  Analysis done")
            else:
                result["analysis"] = None

            # 5. Save
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  Saved → {out_path.name}\n")

    print(f"\nAll done. Materials saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
