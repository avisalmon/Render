# Test Plan

> TDD test plan for each sprint. Tests are written BEFORE implementation.
> All tests live in `tests/` and run via `pytest`.
> Status: `PLANNED` → `RED` (written, failing) → `GREEN` (passing) → `REGRESSION` (promoted)
>
> Test ID convention: `T-<feature-id>-<n>` e.g. `T-F-1.1.2-1`

---

## SPR-1.1 — Foundations

**Sprint goal:** Env/secrets, SQLite WAL, security hardening, logging, error pages, health check, static files, media files.
**Test file:** `tests/test_spr_1_1.py`
**pytest marker:** `spr11`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-1.1.1-1 | `.env` file is loaded by settings | unit | F-1.1.1 | `os.environ` contains vars defined in `.env` after Django init | PLANNED |
| T-F-1.1.1-2 | SECRET_KEY reads from env, not hardcoded | unit | F-1.1.1 | `settings.SECRET_KEY != "dev-only-insecure-key"` when env var is set | PLANNED |
| T-F-1.1.2-1 | SQLite journal mode is WAL | unit | F-1.1.2 | `PRAGMA journal_mode` returns `"wal"` | PLANNED |
| T-F-1.1.2-2 | SQLite busy_timeout ≥ 5000 ms | unit | F-1.1.2 | `PRAGMA busy_timeout` returns value ≥ 5000 | PLANNED |
| T-F-1.1.3-1 | Security: X-Content-Type-Options header | integration | F-1.1.3 | Any response includes `X-Content-Type-Options: nosniff` | PLANNED |
| T-F-1.1.3-2 | Security: X-Frame-Options header present | integration | F-1.1.3 | Any response includes `X-Frame-Options` header | PLANNED |
| T-F-1.1.3-3 | ALLOWED_HOSTS read from env var | unit | F-1.1.3 | `settings.ALLOWED_HOSTS` is not empty list | PLANNED |
| T-F-1.1.4-1 | LOGGING setting is configured | unit | F-1.1.4 | `settings.LOGGING` exists and has `"handlers"` key | PLANNED |
| T-F-1.1.4-2 | Django logger does not raise | unit | F-1.1.4 | `logging.getLogger("django").info("test")` does not raise | PLANNED |
| T-F-1.1.5-1 | 404 template exists | unit | F-1.1.5 | File `templates/404.html` exists on disk | PLANNED |
| T-F-1.1.5-2 | 500 template exists | unit | F-1.1.5 | File `templates/500.html` exists on disk | PLANNED |
| T-F-1.1.5-3 | 403 template exists | unit | F-1.1.5 | File `templates/403.html` exists on disk | PLANNED |
| T-F-1.1.5-4 | 404 response on unknown URL | integration | F-1.1.5 | GET `/nonexistent-url-xyz/` returns status 404 | PLANNED |
| T-F-1.1.6-1 | Health check returns 200 | integration | F-1.1.6 | GET `/healthz` returns HTTP 200 | PLANNED |
| T-F-1.1.6-2 | Health check returns JSON status ok | integration | F-1.1.6 | GET `/healthz` response body = `{"status": "ok"}` | PLANNED |
| T-F-1.1.7-1 | WhiteNoise middleware is active | unit | F-1.1.7 | `whitenoise.middleware.WhiteNoiseMiddleware` in `settings.MIDDLEWARE` | PLANNED |
| T-F-1.1.7-2 | Static file `style.css` is served | integration | F-1.1.7 | GET `/static/style.css` returns HTTP 200 | PLANNED |
| T-F-1.1.8-1 | MEDIA_ROOT is inside PERSISTENT_ROOT | unit | F-1.1.8 | `settings.MEDIA_ROOT` starts with str(`settings.PERSISTENT_ROOT`) | PLANNED |
| T-F-1.1.8-2 | Media file upload saves to MEDIA_ROOT | integration | F-1.1.8 | Upload a 1px PNG via test client, file appears under `settings.MEDIA_ROOT` | PLANNED |

---

## SPR-1.4 — Video Infrastructure (Bunny Stream)

**Sprint goal:** Video model, embedded Bunny player, signed URLs, per-user progress tracking, resume playback, course progress aggregation, free preview gating.
**Test file:** `tests/test_spr_1_4.py`
**pytest marker:** `spr14`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-1.4.1-1 | Bunny settings exist in Django settings | unit | F-1.4.1 | `settings.BUNNY_API_KEY`, `BUNNY_STREAM_LIBRARY_ID`, `BUNNY_STREAM_CDN_HOSTNAME`, `BUNNY_STREAM_TOKEN_KEY` all exist | GREEN |
| T-F-1.4.1-2 | Bunny settings read from env vars | unit | F-1.4.1 | Settings fall back to `os.environ.get()` pattern | GREEN |
| T-F-1.4.2-1 | Course model exists with required fields | unit | F-1.4.2 | Model has `title`, `slug`, `description` | GREEN |
| T-F-1.4.2-2 | Video model exists with required fields | unit | F-1.4.2 | Model has `bunny_video_id`, `title`, `duration_seconds`, `course`, `lesson_order`, `is_free_preview` | GREEN |
| T-F-1.4.2-3 | Video registered in Django admin | unit | F-1.4.2 | `Video` appears in `admin.site._registry` | GREEN |
| T-F-1.4.2-4 | Course registered in Django admin | unit | F-1.4.2 | `Course` appears in `admin.site._registry` | GREEN |
| T-F-1.4.3-1 | Lesson page renders Bunny iframe | integration | F-1.4.3 | GET `/course/<slug>/lesson/<n>/` contains `<iframe` with bunny CDN hostname | GREEN |
| T-F-1.4.3-2 | Player is responsive 16:9 | integration | F-1.4.3 | Iframe wrapper has aspect-ratio style | GREEN |
| T-F-1.4.4-1 | generate_signed_url() produces valid token URL | unit | F-1.4.4 | URL contains `token=` and `expires=` params, expires within 24h | GREEN |
| T-F-1.4.4-2 | Paid video without entitlement returns 403 | integration | F-1.4.4 | Logged-in user without entitlement gets 403 on paid lesson | GREEN |
| T-F-1.4.5-1 | UserVideoProgress model exists with required fields | unit | F-1.4.5 | Model has `user`, `video`, `last_position_seconds`, `percent_watched`, `completed_at` | GREEN |
| T-F-1.4.5-2 | Heartbeat endpoint accepts POST with position | integration | F-1.4.5 | POST `/api/video-progress/` with video_id, position, percent returns 200 | GREEN |
| T-F-1.4.5-3 | Heartbeat updates existing progress record | integration | F-1.4.5 | Second POST updates `last_position_seconds`, no duplicate | GREEN |
| T-F-1.4.6-1 | Lesson page includes last_position in context | integration | F-1.4.6 | Template context has `last_position_seconds` for logged-in user | GREEN |
| T-F-1.4.7-1 | Course detail shows progress percentage | integration | F-1.4.7 | GET `/course/<slug>/` shows correct progress % | GREEN |
| T-F-1.4.7-2 | Course marked complete at 95% threshold | unit | F-1.4.7 | All videos >= 95% watched marks course complete | GREEN |
| T-F-1.4.8-1 | Free preview video accessible to anonymous | integration | F-1.4.8 | GET lesson with `is_free_preview=True` returns 200 for anon | GREEN |
| T-F-1.4.8-2 | Non-preview video redirects anonymous to login | integration | F-1.4.8 | GET lesson with `is_free_preview=False` redirects to login | GREEN |
