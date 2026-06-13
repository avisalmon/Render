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
| T-F-1.4.7-2 | Visiting a lesson marks it complete (no watch threshold) | integration | F-1.4.7 | UserVideoProgress created on visit; lesson counts as complete for progress | GREEN |
| T-F-1.4.8-1 | Free preview video accessible to anonymous | integration | F-1.4.8 | GET lesson with `is_free_preview=True` returns 200 for anon | GREEN |
| T-F-1.4.8-2 | Non-preview video redirects anonymous to login | integration | F-1.4.8 | GET lesson with `is_free_preview=False` redirects to login | GREEN |
| T-F-1.4.9-1 | Sequential locking: lesson 2 locked without visiting lesson 1 | integration | F-1.4.9 | Enrolled user accessing lesson 2 with no prior progress is redirected to lesson 1 | GREEN |
| T-F-1.4.9-2 | Sequential locking: lesson 2 unlocks after lesson 1 visited | integration | F-1.4.9 | After UserVideoProgress for lesson 1 exists, lesson 2 returns 200 | GREEN |
| T-F-1.4.10-1 | LessonQuiz model has required fields | unit | F-1.4.10 | `question`, `options_json`, `requires_correct` exist on model | GREEN |
| T-F-1.4.10-2 | requires_correct quiz hides Next until passed | integration | F-1.4.10 | `lesson_completed=False` in context when quiz not yet passed | PLANNED |
| T-F-1.4.10-3 | Non-required quiz: any answer passes | integration | F-1.4.10 | `quiz_passed` saved as True when requires_correct=False and any option chosen | PLANNED |
| T-F-1.4.11-1 | CourseCertificate model exists | unit | F-1.4.11 | Has `certificate_id` (UUID), `issued_at`, `user`, `course` | PLANNED |
| T-F-1.4.11-2 | course_finish issues certificate when all required quizzes passed | integration | F-1.4.11 | POST to finish URL creates CourseCertificate and redirects to `/certificate/<uuid>/` | PLANNED |
| T-F-1.4.11-3 | course_finish blocks if required quiz not passed | integration | F-1.4.11 | POST redirects to the lesson with `?error=quiz` | PLANNED |
| T-F-1.4.12-1 | Staff user sees all lessons as unlocked | integration | F-1.4.12 | `locked_ids` is empty and `lesson_completed=True` for staff user regardless of progress | PLANNED |
| T-F-1.4.13-1 | Home shows "Continue watching" card for user with progress | integration | REQ-1.3.16 | GET `/` by logged-in user with `UserVideoProgress` returns 200 and contains course/lesson info | GREEN |
| T-F-1.4.13-2 | Home shows normal page when no prior progress | integration | REQ-1.3.16 | GET `/` by logged-in user with no `UserVideoProgress` returns 200 (no redirect) | GREEN |
| T-F-1.4.14-1 | Volume persistence: localStorage key in lesson template | manual | REQ-1.3.15 | Lesson template contains `babook_volume` string (localStorage key for volume save/restore) | GREEN |

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


## EPIC-6.1 — Community Foundation

**Sprint goal:** Identity, reputation, badges, follow, notifications, safety, anonymous-read gate.
**Test file:** `tests/test_spr_6_1.py`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-6.1.1.2-1 | Public profile renders | integration | F-6.1.1.2 | /c/<u>/ 200 with name+bio | GREEN |
| T-F-6.1.1.2-2 | Private profile 404 / owner preview | integration | F-6.1.1.2 | stranger 404, owner 200 | GREEN |
| T-F-6.1.1.4-1 | Community settings save | integration | F-6.1.1.4 | is_public/bio/collab persist | GREEN |
| T-F-6.1.2.1-1 | Points ledger + total | unit | F-6.1.2.1 | 15+2=17, 2 events | GREEN |
| T-F-6.1.2.2-1 | Tier badge at threshold | unit | F-6.1.2.2 | bronze at >=50 | GREEN |
| T-F-6.1.2.2-2 | Badge idempotent + notifies | unit | F-6.1.2.2 | 1 award, 1 notification | GREEN |
| T-F-6.1.3.1-1 | Follow toggle + notification | integration | F-6.1.3.1 | follow/unfollow, notify | GREEN |
| T-F-6.1.3.2-1 | Notifications page + bell | integration | F-6.1.3.2 | mark-read, bell link present | GREEN |
| T-F-6.1.3.3-1 | notify() never self-notifies | unit | F-6.1.3.3 | None on actor==user | GREEN |
| T-F-6.1.4.1-1 | Guidelines accept-once | integration | F-6.1.4.1 | accepted_at set | GREEN |
| T-F-6.1.4.2-1 | Report creates queue item | integration | F-6.1.4.2 | open report persisted | GREEN |
| T-F-6.1.4.2-2 | Report requires login | integration | F-6.1.4.2/5 | anonymous -> /join/ | GREEN |
| T-F-6.1.2.4-1 | Leaderboard opt-out | integration | F-6.1.2.4 | opted-out hidden | GREEN |
| T-F-6.1.4.5-1 | Community pages read-public | integration | F-6.1.4.5 | 5 pages 200 + register note | GREEN |
| T-F-6.1.4.5-2 | Interactions hit the wall | integration | F-6.1.4.5 | anonymous -> /join/ | GREEN |

## EPIC-6.2 — Forums & Q&A

**Sprint goal:** Threads/answers/votes/accepted, discovery, lesson anchoring, AI assist, subscriptions.
**Test file:** `tests/test_spr_6_2.py`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-6.2.1.3-1 | Ask->answer->accept flow | integration | F-6.2.1.3/4 | +15, badge, notifications | GREEN |
| T-F-6.2.1.3-2 | Inline guidelines gate keeps the post | integration | F-6.2.1.3 | re-render w/ content; checkbox publishes | GREEN |
| T-F-6.2.1.2-1 | Anonymous read, write walled | integration | F-6.2.1.2 | read 200; write -> /join/ | GREEN |
| T-F-6.2.1.4-1 | Upvote toggle, no self-vote | integration | F-6.2.1.4 | +2 rep; self-vote 400 | GREEN |
| T-F-6.2.1.4-2 | Accept restricted to asker/staff | integration | F-6.2.1.4 | rando 403 | GREEN |
| T-F-6.2.2.2-1 | Search + unanswered filter | integration | F-6.2.2.2/3 | filtered results | GREEN |
| T-F-6.2.2.4-1 | Staff pin + canonical | integration | F-6.2.2.4 | flags set; non-staff 403 | GREEN |
| T-F-6.2.3.1-1 | Lesson page community block | integration | F-6.2.3.1 | button + threads shown | GREEN |
| T-F-6.2.3.1-2 | Lesson ask pre-tags | integration | F-6.2.3.1 | course/video/tag linked | GREEN |
| T-F-6.2.3.1-3 | Anonymous lesson-ask keeps query | integration | F-6.2.3.1 | next preserves course+lesson | GREEN |
| T-F-6.2.3.2-1 | Similar threads dedup | integration | F-6.2.3.2 | match suggested | GREEN |
| T-F-6.2.3.3-1 | AI summary long-thread + cache | integration | F-6.2.3.3 | 400 short; cached summary | GREEN |
| T-F-6.2.3.4-1 | Avi Bot draft staff-only | integration | F-6.2.3.4 | draft for staff; 403 others | GREEN |
| T-F-6.2.3.5-1 | Subscribers notified | integration | F-6.2.3.5 | reply + answer notifications | GREEN |
| T-F-6.1.4.1-2 | Guidelines next anti-open-redirect | integration | F-6.1.4.1 | external next -> /community/ | GREEN |


## EPIC-6.3 — Showcase (דוכן השוויץ)

**Sprint goal:** Projects across stands, wall + brag feed, reactions, comments, messaging, gamification, integration.
**Test file:** `tests/test_spr_6_3.py`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-6.3.1.3-1 | Publish awards points + builder badge | integration | F-6.3.1.3 | +10, badge, published | GREEN |
| T-F-6.3.1.3-2 | Draft private until published | integration | F-6.3.1.3 | stranger 404, owner 200 | GREEN |
| T-F-6.3.1.6-1 | Student work -> review queue | integration | F-6.3.1.6 | pending, not on wall | GREEN |
| T-F-6.3.3.4-1 | showcase_master badge at 5 | integration | F-6.3.3.4 | badge awarded | GREEN |
| T-F-6.3.1.4-1 | Wall lists + stand filter | integration | F-6.3.1.4 | filtered by stand | GREEN |
| T-F-6.3.1.4-2 | Tag filter SQLite-safe (regression) | integration | F-6.3.1.4 | no crash, matches | GREEN |
| T-F-6.3.1.4-3 | Featured row + top sort | integration | F-6.3.1.4 | featured shown, sorted | GREEN |
| T-F-6.3.2.3-1 | Brag feed read-public | integration | F-6.3.2.3 | 200 + projects | GREEN |
| T-F-6.3.1.5-1 | Anonymous view, create walled | integration | F-6.3.1.5 | view 200, new -> /join/ | GREEN |
| T-F-6.3.2.1-1 | Star toggle: count/points/notify | integration | F-6.3.2.1 | +1, notify, toggle | GREEN |
| T-F-6.3.2.1-2 | Emoji reaction + no self-react | integration | F-6.3.2.1 | fire toggles; self 400 | GREEN |
| T-F-6.3.3.4-2 | rising_star badge at 25 stars | integration | F-6.3.3.4 | badge awarded | GREEN |
| T-F-6.3.2.2-1 | Comment notifies author | integration | F-6.3.2.2 | comment + notify | GREEN |
| T-F-6.3.3.4-3 | Staff feature awards + notify | integration | F-6.3.3.4 | +15, badge; non-staff 403 | GREEN |
| T-F-6.3.3.1-1 | DM send + notify | integration | F-6.3.3.1 | message + notify | GREEN |
| T-F-6.3.3.1-2 | Students cannot message | integration | F-6.3.3.1 | blocked + notice | GREEN |
| T-F-6.3.3.1-3 | Block prevents messages | integration | F-6.3.3.1 | no message stored | GREEN |
| T-F-6.3.3.2-1 | Project on profile + course | integration | F-6.3.3.2/3 | shown both places | GREEN |
| T-F-6.3.3.5-1 | Follower notified on publish | integration | F-6.3.3.5 | notification fired | GREEN |

## SPR-6.4 — Feed & Tips

| Test ID | Description | Type | Feature traced | Expected | Status |
|---|---|---|---|---|---|
| T-F-6.4.1-1 | Post tip + listed publicly | integration | F-6.4.1 | Tip saved, body on /community/tips/ | GREEN |
| T-F-6.4.1-2 | Tip body capped at 2000 chars | integration | F-6.4.1 | stored body <= 2000 | GREEN |
| T-F-6.4.1-3 | Empty tip rejected | integration | F-6.4.1 | no Tip created | GREEN |
| T-F-6.4.1-4 | Guest cannot post tip | integration | F-6.4.1 | redirect to /join/ | GREEN |
| T-F-6.4.1-5 | מדריך badge at 10 tips | integration | F-6.4.1 | tipster badge awarded | GREEN |
| T-F-6.4.1-6 | Tip reaction toggle + points + notify | integration | F-6.4.1 | +1, notify, toggle off | GREEN |
| T-F-6.4.1-7 | No self-reaction on tip | integration | F-6.4.1 | 400 | GREEN |
| T-F-6.4.2-1 | Feed aggregates all sources | integration | F-6.4.2 | tip/project/thread shown | GREEN |
| T-F-6.4.2-2 | Following scope filters to followed | integration | F-6.4.2 | only followed authors | GREEN |
| T-F-6.4.2-3 | Domain scope uses interests | integration | F-6.4.2 | only interest-tagged | GREEN |
| T-F-6.4.2-4 | build_feed reverse-chronological (DEC-40) | unit | F-6.4.2 | newest-first order | GREEN |
| T-F-6.4.3-1 | Composer present + routes | integration | F-6.4.3 | forum/showcase links | GREEN |
| T-F-6.4.5-1 | Homepage community strip (logged-in) | integration | F-6.4.5 | מהקהילה shown | GREEN |
| T-F-6.4.5-2 | No strip for anonymous | integration | F-6.4.5 | מהקהילה absent | GREEN |
| T-F-6.4.4-1 | digest_opt_in defaults off | unit | F-6.4.4 | False | GREEN |
| T-F-6.4.4-2 | Digest command dormant below threshold | integration | F-6.4.4 | 0 emails (DEC-46) | GREEN |
