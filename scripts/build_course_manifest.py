"""
Build course_manifest.json — single source of truth for lesson page construction.
Merges lesson JSON data with Bunny video IDs from the DB.
Run any time lesson JSONs or DB change.
"""
import sqlite3, json
from pathlib import Path

BASE  = Path("data/course_materials/micropython-thonny")
DB    = "data/db.sqlite3"
OUT   = BASE / "course_manifest.json"

# --- Pull Bunny video IDs from DB ---
db = sqlite3.connect(DB)
db_rows = db.execute("""
    SELECT v.lesson_order, v.bunny_video_id, v.is_free_preview, v.duration_seconds
    FROM app_video v
    JOIN app_course c ON v.course_id = c.id
    WHERE c.slug = 'micropython-thonny'
    ORDER BY v.lesson_order
""").fetchall()
db.close()
bunny_map = {r[0]: {"bunny_video_id": r[1], "is_free_preview": bool(r[2]), "duration_seconds": r[3]} for r in db_rows}

# --- Build manifest ---
lessons = []
for i in range(1, 16):
    path = BASE / f"lesson_{i:02d}.json"
    d    = json.loads(path.read_text(encoding="utf-8"))
    a    = d.get("analysis") or {}
    bun  = bunny_map.get(i, {})
    t    = d.get("transcript_he", "")

    # Readiness checks
    checks = {
        "has_transcript":  len(t) > 100,
        "has_analysis":    bool(a.get("title_en")),
        "has_bunny_id":    bool(bun.get("bunny_video_id")),
        "has_code":        bool(d.get("github_file")),
        "thin_transcript": len(t) < 200,
    }
    checks["ready"] = (checks["has_transcript"] or not checks["thin_transcript"]) \
                      and checks["has_analysis"] \
                      and checks["has_bunny_id"]

    entry = {
        "lesson_order":    i,
        "youtube_id":      d.get("youtube_id"),
        "youtube_title":   d.get("youtube_title"),
        "bunny_video_id":  bun.get("bunny_video_id"),
        "is_free_preview": bun.get("is_free_preview", False),
        "duration_seconds":bun.get("duration_seconds") or d.get("duration_seconds"),
        "title_he":        a.get("title_he", ""),
        "title_en":        a.get("title_en", ""),
        "difficulty":      a.get("difficulty", "beginner"),
        "keywords":        a.get("keywords", []),
        "objectives":      a.get("objectives", []),
        "summary_he":      a.get("summary_he", ""),
        "notes_markdown":  a.get("notes_markdown", ""),
        "github_file":     d.get("github_file"),
        "has_code_example":bool(d.get("github_file")),
        "transcript_chars":len(t),
        "status":          checks,
    }
    lessons.append(entry)
    # Also backfill bunny_video_id into each individual lesson JSON
    if bun.get("bunny_video_id") and not d.get("bunny_video_id"):
        d["bunny_video_id"] = bun["bunny_video_id"]
        d["is_free_preview"] = bun.get("is_free_preview", False)
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

manifest = {
    "course_slug":  "micropython-thonny",
    "course_title": "מיקרופייתון עם תוני",
    "total_lessons": len(lessons),
    "ready_count":   sum(1 for l in lessons if l["status"]["ready"]),
    "needs_work":    [l["lesson_order"] for l in lessons if not l["status"]["ready"]],
    "lessons":       lessons,
}

OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Ready: {manifest['ready_count']}/{manifest['total_lessons']}")
if manifest["needs_work"]:
    print(f"Needs work: lessons {manifest['needs_work']}")
