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

---

## SPR-1.6 — Copilot Seat Provisioning

**Sprint goal:** Models, stubbed GitHub API, auto-invite/assign/revoke, inactivity reclamation, admin dashboard, seat cap, audit log, user-facing status, policy doc.
**Test file:** `tests/test_spr_1_6.py`
**pytest marker:** `spr16`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-1.6.1-1 | GITHUB_ORG setting reads from env | unit | F-1.6.1 | `settings.GITHUB_ORG` is str | GREEN |
| T-F-1.6.1-2 | GITHUB_PAT setting reads from env | unit | F-1.6.1 | `settings.GITHUB_PAT` is str | GREEN |
| T-F-1.6.1-3 | COPILOT_MAX_SEATS setting reads from env | unit | F-1.6.1 | `settings.COPILOT_MAX_SEATS` is int > 0 | GREEN |
| T-F-1.6.2-1 | UserProfile has github_username field | unit | F-1.6.2 | Field exists on profile | GREEN |
| T-F-1.6.2-2 | github_username is optional (blank) | unit | F-1.6.2 | `full_clean()` passes with empty string | GREEN |
| T-F-1.6.3-1 | CopilotSeat model exists with all fields | unit | F-1.6.3 | Has status, invited_at, accepted_at, assigned_at, revoked_at, last_activity_at | GREEN |
| T-F-1.6.3-2 | CopilotSeat.STATUS_CHOICES covers all states | unit | F-1.6.3 | Includes none/invite_pending/active/expiring/revoked/waitlisted | GREEN |
| T-F-1.6.4-1 | invite_to_org creates pending CopilotSeat | integration | F-1.6.4 | Status = invite_pending, invited_at set | GREEN |
| T-F-1.6.4-2 | invite logs SeatEvent with type=invited | integration | F-1.6.4 | SeatEvent exists with event_type=invited | GREEN |
| T-F-1.6.5-1 | assign_copilot_seat updates status to active | integration | F-1.6.5 | Status = active, assigned_at set | GREEN |
| T-F-1.6.5-2 | assign logs SeatEvent with type=assigned | integration | F-1.6.5 | SeatEvent exists with event_type=assigned | GREEN |
| T-F-1.6.6-1 | revoke_copilot_seat updates status to revoked | integration | F-1.6.6 | Status = revoked, revoked_at set | GREEN |
| T-F-1.6.6-2 | revoke logs SeatEvent with type=revoked | integration | F-1.6.6 | SeatEvent with reason=subscription_cancelled | GREEN |
| T-F-1.6.6-3 | COPILOT_GRACE_PERIOD_DAYS defaults to 14 | unit | F-1.6.6 | Setting == 14 | GREEN |
| T-F-1.6.7-1 | COPILOT_INACTIVITY_WARN_DAYS defaults to 30 | unit | F-1.6.7 | Setting == 30 | GREEN |
| T-F-1.6.7-2 | COPILOT_INACTIVITY_RECLAIM_DAYS defaults to 60 | unit | F-1.6.7 | Setting == 60 | GREEN |
| T-F-1.6.7-3 | check_inactivity warns seats inactive > 30d | integration | F-1.6.7 | User in warned list | GREEN |
| T-F-1.6.7-4 | check_inactivity reclaims seats inactive > 60d | integration | F-1.6.7 | Seat revoked, user in reclaimed list | GREEN |
| T-F-1.6.8-1 | Admin copilot dashboard returns 200 for staff | integration | F-1.6.8 | GET /staff/copilot-dashboard/ → 200 | GREEN |
| T-F-1.6.8-2 | Dashboard context has total_seats and monthly_cost | integration | F-1.6.8 | Context keys present | GREEN |
| T-F-1.6.9-1 | invite refused when COPILOT_MAX_SEATS reached | integration | F-1.6.9 | Second invite returns waitlisted status | GREEN |
| T-F-1.6.9-2 | waitlisted seat has status=waitlisted | integration | F-1.6.9 | Seat status == waitlisted | GREEN |
| T-F-1.6.10-1 | Profile shows copilot_status in context | integration | F-1.6.10 | copilot_status key in response.context | GREEN |
| T-F-1.6.11-1 | SeatEvent model has all required fields | unit | F-1.6.11 | Has created_at, api_response | GREEN |
| T-F-1.6.11-2 | SeatEvent records actor and reason | unit | F-1.6.11 | actor and reason persist correctly | GREEN |
| T-F-1.6.12-1 | copilot_policy.md exists | unit | F-1.6.12 | File on disk | GREEN |

---

## SPR-1.8 — AI Chat (OpenAI)

**Sprint goal:** Chat models, stubbed OpenAI API, rate limiting, cost cap, moderation, usage tracking, chat UI, session management, course context.
**Test file:** `tests/test_spr_1_8.py`
**pytest marker:** `spr18`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-1.8.1-1 | OPENAI_API_KEY setting reads from env | unit | F-1.8.1 | Setting is str | GREEN |
| T-F-1.8.1-2 | OPENAI_DEFAULT_MODEL setting exists | unit | F-1.8.1 | Contains "gpt" | GREEN |
| T-F-1.8.1-3 | OPENAI_PREMIUM_MODEL setting exists | unit | F-1.8.1 | Contains "gpt" | GREEN |
| T-F-1.8.2-1 | Chat endpoint requires auth | integration | F-1.8.2 | POST /api/chat/ → 401 for anon | GREEN |
| T-F-1.8.2-2 | Chat endpoint returns 200 with mock | integration | F-1.8.2 | POST /api/chat/ → 200 | GREEN |
| T-F-1.8.3-1 | ChatSession model exists | unit | F-1.8.3 | Has context_type, created_at, last_activity_at | GREEN |
| T-F-1.8.3-2 | ChatMessage model exists | unit | F-1.8.3 | Has role, content, tokens_used | GREEN |
| T-F-1.8.3-3 | ChatMessage linked to ChatSession | unit | F-1.8.3 | session.messages.count() == 1 | GREEN |
| T-F-1.8.4-1 | SystemPrompt model exists | unit | F-1.8.4 | Has context_type, content | GREEN |
| T-F-1.8.4-2 | SystemPrompt in Django admin | unit | F-1.8.4 | Registered in admin | GREEN |
| T-F-1.8.5-1 | Default model is gpt-4o-mini | unit | F-1.8.5 | Setting == "gpt-4o-mini" | GREEN |
| T-F-1.8.5-2 | Premium model is gpt-4o | unit | F-1.8.5 | Setting == "gpt-4o" | GREEN |
| T-F-1.8.6-1 | Daily token limits setting exists | unit | F-1.8.6 | member limit > 0 | GREEN |
| T-F-1.8.6-2 | Rate limiter rejects over limit | integration | F-1.8.6 | allowed == False | GREEN |
| T-F-1.8.7-1 | UsageLog model exists | unit | F-1.8.7 | Has all fields | GREEN |
| T-F-1.8.7-2 | Admin usage dashboard returns 200 | integration | F-1.8.7 | GET /staff/ai-usage/ → 200 | GREEN |
| T-F-1.8.7-3 | Dashboard has cost/token context | integration | F-1.8.7 | total_cost_month, total_tokens_today | GREEN |
| T-F-1.8.8-1 | Monthly cost cap setting exists | unit | F-1.8.8 | > 0 | GREEN |
| T-F-1.8.8-2 | Chat blocked at cost cap | integration | F-1.8.8 | → 429 | GREEN |
| T-F-1.8.9-1 | Chat page returns 200 | integration | F-1.8.9 | GET /chat/ → 200 | GREEN |
| T-F-1.8.9-2 | Chat page contains widget markup | integration | F-1.8.9 | "chat-widget" in HTML | GREEN |
| T-F-1.8.10-1 | Create new session via API | integration | F-1.8.10 | POST → 201 | GREEN |
| T-F-1.8.10-2 | List sessions via API | integration | F-1.8.10 | GET → 200, sessions array | GREEN |
| T-F-1.8.10-3 | Session timeout setting | unit | F-1.8.10 | == 30 min | GREEN |
| T-F-1.8.11-1 | Moderation rejects flagged content | integration | F-1.8.11 | is_safe == False | GREEN |
| T-F-1.8.11-2 | Moderation logs flagged attempt | integration | F-1.8.11 | ModerationLog created | GREEN |
| T-F-1.8.12-1 | Chat with course context | integration | F-1.8.12 | course_slug sends course metadata | GREEN |

---

## SPR-1.9 — Email Service (Resend)

**Sprint goal:** Transactional email via Resend in prod (console in dev), password reset flow, email verification toggle, admin send test.
**Test file:** `tests/test_spr_1_9.py`
**pytest marker:** `spr19`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-1.9.1-1 | EMAIL_BACKEND setting exists | unit | F-1.9.1 | `settings.EMAIL_BACKEND` is a non-empty string | PLANNED |
| T-F-1.9.1-2 | Dev uses console email backend | unit | F-1.9.1 | When RESEND_API_KEY empty, backend is console | PLANNED |
| T-F-1.9.1-3 | Prod uses Resend backend when key set | unit | F-1.9.1 | When RESEND_API_KEY set, backend is `django_resend.EmailBackend` | PLANNED |
| T-F-1.9.1-4 | django.core.mail.send_mail does not raise | integration | F-1.9.1 | send_mail() succeeds with console backend | PLANNED |
| T-F-1.9.2-1 | RESEND_API_KEY setting reads from env | unit | F-1.9.2 | `settings.RESEND_API_KEY` is str | PLANNED |
| T-F-1.9.2-2 | DEFAULT_FROM_EMAIL setting exists | unit | F-1.9.2 | `settings.DEFAULT_FROM_EMAIL` is non-empty | PLANNED |
| T-F-1.9.3-1 | Password reset URL resolves | integration | F-1.9.3 | `/accounts/password/reset/` returns 200 | PLANNED |
| T-F-1.9.3-2 | Password reset POST sends email | integration | F-1.9.3 | POST with valid email → mail.outbox has 1 entry | PLANNED |
| T-F-1.9.3-3 | Reset confirm URL resolves | integration | F-1.9.3 | Password reset confirm page loads | PLANNED |
| T-F-1.9.3-4 | Login page has forgot-password link | integration | F-1.9.3 | Login template contains link to password reset | PLANNED |
| T-F-1.9.4-1 | ACCOUNT_EMAIL_VERIFICATION setting exists | unit | F-1.9.4 | Setting is one of none/optional/mandatory | PLANNED |
| T-F-1.9.5-1 | send_mail function is importable and callable | unit | F-1.9.5 | `from django.core.mail import send_mail` works | PLANNED |
