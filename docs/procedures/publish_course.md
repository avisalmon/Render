# Publish a course to production

Push a course (with all its lessons/videos and materials) from local dev to
`https://babook.co.il` via the Course Management API.

## Prerequisites

1. **Course exists in local DB.** The push command reads from the local SQLite
   database, not from `data/course_materials/` directly. Create the course +
   videos + materials via Django admin or an import script first.
2. **Videos already uploaded to Bunny Stream.** Each `Video` row must have its
   Bunny ID set. Materials of type `FILE` are uploaded by the push command;
   videos are NOT re-uploaded.
3. **API key.** `COURSE_MGMT_API_KEY` must be set in `mysite/settings_local.py`
   (local) and on Render (prod). Both ends must match.
4. **Intel network proxy.** Outbound HTTPS to `babook.co.il` from the corp
   network requires the proxy; without it `urllib` hangs with `WinError 10060`.

## Command

```powershell
# Activate venv if not already active
.\env\Scripts\Activate.ps1

# Intel proxy (mandatory on corp network)
$env:HTTPS_PROXY = "http://proxy-iil.intel.com:912"
$env:HTTP_PROXY  = "http://proxy-iil.intel.com:912"

# Hebrew slug / title output needs utf-8
$env:PYTHONIOENCODING = "utf-8"

# Push and publish
.\env\Scripts\python.exe manage.py push_course_to_production <slug> `
    --target https://babook.co.il `
    --publish
```

Flags:

| Flag | Effect |
|------|--------|
| `--target <url>` | Base URL of the target server. Falls back to `COURSE_MGMT_TARGET` env var. |
| `--publish` | Sets `is_published=True` on the remote course. Without this the course is uploaded as draft. |
| `--dry-run` | Builds the payload and prints it without sending. Use to inspect what would be pushed. |

## What it does

1. Loads `Course` + related `Video`s (+ optional `LessonQuiz` per video) + `CourseMaterial`s from the **local** DB.
2. For each `FILE` material, uploads the file to
   `<target>/api/v1/media/upload/` and gets back a path on the persistent disk.
3. POSTs the full course payload to `<target>/api/v1/courses/sync/`.
4. If `--publish`, the server sets `is_published=True`.

**Quizzes are kept in sync**: if a video has a `LessonQuiz` locally it is
upserted on the server; if a local video has no quiz, any existing quiz on
the server for that video is **deleted**. Edit quizzes locally (Django admin)
then re-run the push.

Output on success:

```
Course: <title> (<slug>)
  Videos:    16
  Materials: 2
  Uploading: <filename> ...
    → course_materials/<filename>

Syncing to https://babook.co.il/api/v1/courses/sync/ ...
  ✓ synced: 16 videos, 2 quizzes, 2 materials (created|updated)
```

## Verify

```powershell
$key = "HfPxQ1TMJbwOWUNXHBaaG0MpXrD9jbmdv-Ro96SNe3E"  # COURSE_MGMT_API_KEY
$r = Invoke-WebRequest "https://babook.co.il/api/v1/courses/" `
        -UseBasicParsing -Headers @{Authorization="Bearer $key"}
$r.Content | ConvertFrom-Json | ConvertTo-Json -Depth 4
```

Expected:

```json
{
  "courses": [
    {
      "slug": "<slug>",
      "title": "...",
      "is_published": true,
      "video_count": 16,
      "material_count": 2
    }
  ]
}
```

Also confirm the course renders on the site: `https://babook.co.il/courses/<slug>/`.

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `WinError 10060` timeout during upload | Intel proxy not set | `$env:HTTPS_PROXY="http://proxy-iil.intel.com:912"` (and `HTTP_PROXY`) |
| `Course '<slug>' not found in local DB` | Course missing locally | Create the course in local DB first (admin or import) |
| `401 Unauthorized` from server | API key mismatch | Compare `COURSE_MGMT_API_KEY` in local `settings_local.py` vs Render env var |
| `500` on `/api/v1/courses/sync/` | Server-side bug or schema mismatch | Fetch Render logs (`/v1/logs?ownerId=...&resource=srv-...`) and read the traceback |
| Videos appear but show 404 / no playback | Bunny ID missing or wrong on the local `Video` row | Fix the local row, push again — sync is idempotent (upsert by slug) |

## Re-pushing / updates

The endpoint is idempotent. Pushing the same course again **updates** existing
videos/materials (matched by slug/order). Safe to re-run after editing local
content. The summary line will say `updated` instead of `created`.
