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
