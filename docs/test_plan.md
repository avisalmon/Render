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


## SPR-2.0.1 - Design System Foundation

**Sprint goal:** Establish dark-theme design tokens, typography (Heebo/Inter/JetBrains Mono), spacing tokens, `.card-surface` component, WhatsApp sticky CTA, Bootstrap RTL variant. Base for all EPIC-2 UI work.
**Test file:** `tests/test_spr_2_0_1.py`
**pytest marker:** `spr201`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-2.0.1-1 | Color palette tokens defined | unit | F-2.0.1 | All 10 `--bg-*`/`--text-*`/`--accent-*`/`--border` tokens in style.css | GREEN |
| T-F-2.0.1-2 | Palette hex values match spec | unit | F-2.0.1 | `--bg-primary: #0f1117`, `--accent-cta: #22c55e`, etc. | GREEN |
| T-F-2.0.2-1 | Google Fonts loaded in base.html | integration | F-2.0.2 | Heebo + Inter + JetBrains Mono referenced | GREEN |
| T-F-2.0.2-2 | Fonts use `display=swap` | integration | F-2.0.2 | URL contains `display=swap` | GREEN |
| T-F-2.0.2-3 | Font-family CSS vars defined | unit | F-2.0.2 | `--font-heading` etc. in style.css | GREEN |
| T-F-2.0.3-1 | Spacing tokens defined | unit | F-2.0.3 | `--space-section`, `--space-card`, `--max-content-width` | GREEN |
| T-F-2.0.3-2 | Max content width = 1200px | unit | F-2.0.3 | `--max-content-width: 1200px` | GREEN |
| T-F-2.0.4-1 | `.card-surface` class defined | unit | F-2.0.4 | Class in style.css | GREEN |
| T-F-2.0.4-2 | `.card-surface` uses design tokens | unit | F-2.0.4 | Block uses `--bg-surface`, `border-radius`, `padding` | GREEN |
| T-F-2.0.5-1 | `.whatsapp-sticky` class defined | unit | F-2.0.5 | Class in style.css | GREEN |
| T-F-2.0.5-2 | WhatsApp sticky positioning | unit | F-2.0.5 | `position: fixed`, `bottom`, `z-index` set | GREEN |
| T-F-2.0.5-3 | WhatsApp sticky uses CTA color | unit | F-2.0.5 | `--accent-cta` referenced | GREEN |
| T-F-2.0.6-1 | Bootstrap RTL+LTR conditionally loaded | integration | F-2.0.6 | Both `bootstrap.rtl.min.css` and `bootstrap.min.css` in base.html | GREEN |
| T-F-2.0.6-2 | Hebrew request uses RTL | integration | F-2.0.6 | Response has RTL bootstrap or `dir=rtl` | GREEN |
| T-F-2.0.7-1 | Home renders with dark theme | integration | F-2.0.7 | GET / -> 200 | GREEN |
| T-F-2.0.7-2 | body uses `--bg-primary` | unit | F-2.0.7 | body block references token | GREEN |
| T-F-2.0.7-3 | Existing pages still render | integration | F-2.0.7 | /, /healthz, /privacy/, /terms/ -> 200 | GREEN |

---

## SPR-2.1.1 - Corporate Page: Conversion MVP

**Sprint goal:** Ship a lean `/corporate/` conversion page with hero, service tiers, FAQ, WhatsApp CTAs, contact form, email notification, SEO, UTM capture, mobile/accessibility baseline, and security.
**Test file:** `tests/test_spr_2_1_1.py`
**pytest marker:** `spr211`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-2.1.1-1 | Corporate page renders for anonymous users | integration | F-2.1.1 | GET `/corporate/` returns 200 and page markup, no login redirect | GREEN |
| T-F-2.1.2-1 | SEO meta and sitemap inclusion | integration | F-2.1.2 | Title/meta/canonical present; `/corporate/` in sitemap | GREEN |
| T-F-2.1.3-1 | Fast static assets | integration | F-2.1.3 | Hero uses WebP; no heavy frontend framework bundle | GREEN |
| T-F-2.1.4-1 | Responsive page structure | integration | F-2.1.4 | Bootstrap responsive columns, no fixed-width wrapper | GREEN |
| T-F-2.1.5-1 | Hero photo/copy/CTAs | integration | F-2.1.5 | Headline, Avi alt text, WhatsApp CTA, form CTA render | GREEN |
| T-F-2.1.6-1 | Static service tier cards | integration | F-2.1.6 | Workshop, bootcamp, keynote cards and pricing signals render | GREEN |
| T-F-2.1.7-1 | FAQ accordion | integration | F-2.1.7 | Bootstrap accordion with 6+ Hebrew FAQ items | GREEN |
| T-F-2.1.8-1 | Contact form UI/accessibility | integration | F-2.1.8 | Required fields, labels, aria-live status present | GREEN |
| T-F-2.1.9-1 | Form creates lead and sends email | integration | F-2.1.9 | AJAX POST creates CorporateLead and sends notification email | GREEN |
| T-F-2.1.10-1 | Honeypot spam rejection | integration | F-2.1.10 | Filled honeypot returns 200 but writes no lead | GREEN |
| T-F-2.1.10-2 | Submission rate limit | integration | F-2.1.10 | Fourth submission from same IP in one hour returns 429 | GREEN |
| T-F-2.1.11-1 | WhatsApp env number and encoded messages | integration | F-2.1.11 | Hero/tier/footer/sticky links use env number and encoded text | GREEN |
| T-F-2.1.12-1 | UTM capture and Plausible event | integration | F-2.1.12 | Hidden UTM fields and `corporate_form_submit` event exist | GREEN |
| T-F-2.1.13-1 | Accessibility baseline | integration | F-2.1.13 | Single h1, skip link, aria labels, reduced motion support | GREEN |
| T-F-2.1.14-1 | Mobile-specific classes | integration | F-2.1.14 | Mobile hero/classes/touch-target styling present | GREEN |
| T-F-2.1.15-1 | CSRF enforcement | integration | F-2.1.15 | AJAX POST without CSRF is rejected when checks enforced | GREEN |
| T-F-2.1.15-2 | Input sanitization | integration | F-2.1.15 | HTML stripped from message and message stored at <=1000 chars | GREEN |

---

## SPR-2.1.3 - Newsletter Capture: MVP

**Sprint goal:** Add a lightweight site-wide newsletter capture flow with a subscriber model, reusable CTA, double opt-in confirmation, spam protection, duplicate-safe handling, source attribution, UTM capture, and Plausible signup tracking.
**Test file:** `tests/test_spr_2_1_3.py`
**pytest marker:** `spr213`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-2.1.28/29-1 | Signup creates subscriber and sends confirmation | integration | F-2.1.28, F-2.1.29 | Lowercased unique email stored with source/UTM fields; confirmation email sent | GREEN |
| T-F-2.1.29/30-1 | Newsletter component renders once | integration | F-2.1.29, F-2.1.30 | `/corporate/` renders exactly one reusable CTA with consent copy | GREEN |
| T-F-2.1.29-2 | Confirmation token works | integration | F-2.1.29 | Confirmation link sets `confirmed_at` and renders success page | GREEN |
| T-F-2.1.31-1 | Honeypot, rate limit, duplicates | integration | F-2.1.31 | Bots write no rows; duplicates stay idempotent; fourth IP submission returns 429 | GREEN |
| T-F-2.1.28/31-2 | Validation and CSRF | integration | F-2.1.28, F-2.1.31 | Invalid email returns 400; missing CSRF returns 403 with checks enforced | GREEN |
| T-F-2.1.32-1 | Non-PII signup tracking | integration | F-2.1.32 | UTM fields render; Plausible event uses source page and language only | GREEN |
| T-F-2.1.29-3 | Purge old unconfirmed subscribers | integration | F-2.1.29 | Management command deletes unconfirmed subscribers older than 14 days only | GREEN |

---

## SPR-2.1.4 — Corporate Page: Polish & Compliance

**Sprint goal:** Accessibility (WCAG AA contrast, keyboard nav, screen reader, reduced motion), mobile hero/tiers/sticky WhatsApp, performance (WebP, no blocking JS), RTL verification, responsive breakpoints, CSRF/sanitization, sitemap.
**Test file:** `tests/test_spr_2_1_4.py`
**pytest marker:** `spr214`

| Test ID | Description | Type | Feature | Expected result | Status |
|---|---|---|---|---|---|
| T-F-2.1.35-1 | --text-primary on --bg-primary ≥4.5:1 | unit | F-2.1.35 | Contrast ratio of #f0f0f5 on #0f1117 ≥ 4.5 | GREEN |
| T-F-2.1.35-2 | --text-secondary on --bg-surface ≥3:1 | unit | F-2.1.35 | Contrast ratio of #9ca3af on #1a1d27 ≥ 3.0 | GREEN |
| T-F-2.1.35-3 | --accent-warm price text ≥3:1 | unit | F-2.1.35 | Contrast ratio of #f59e0b on #1a1d27 ≥ 3.0 | GREEN |
| T-F-2.1.35-4 | White on --accent-cta ≥3:1 (large bold) | unit | F-2.1.35 | Contrast ratio of #fff on #16a34a ≥ 3.0 | GREEN |
| T-F-2.1.36-1 | Skip-to-content link present | integration | F-2.1.36 | href="#corporate-main" in /corporate/ | GREEN |
| T-F-2.1.36-2 | All buttons have aria-label or text | integration | F-2.1.36 | No button is empty and unlabelled | GREEN |
| T-F-2.1.36-3 | Form inputs have matching labels | integration | F-2.1.36 | Every input id has a label[for] | GREEN |
| T-F-2.1.36-4 | :focus-visible in CSS | unit | F-2.1.36 | style.css contains :focus-visible rule | GREEN |
| T-F-2.1.37-1 | Single h1 on /corporate/ | integration | F-2.1.37 | Exactly one <h1> | GREEN |
| T-F-2.1.37-2 | Heading hierarchy h1→h2→h3 | integration | F-2.1.37 | h2 and h3 exist; h1 precedes h2 | GREEN |
| T-F-2.1.37-3 | Sections have aria-labelledby | integration | F-2.1.37 | ≥3 sections with aria-labelledby | GREEN |
| T-F-2.1.37-4 | Form status has role=status + aria-live | integration | F-2.1.37 | role="status" and aria-live="polite" present | GREEN |
| T-F-2.1.37-5 | All images have non-empty alt text | integration | F-2.1.37 | No <img> missing or empty alt | GREEN |
| T-F-2.1.38-1 | prefers-reduced-motion in CSS | unit | F-2.1.38 | style.css contains prefers-reduced-motion query | GREEN |
| T-F-2.1.38-2 | prefers-reduced-motion in corporate template | unit | F-2.1.38 | corporate.html inline style contains prefers-reduced-motion | GREEN |
| T-F-2.1.39-1 | Mobile hero photo 200px in CSS | unit | F-2.1.39 | CSS has 200px width for hero photo at ≤768px | GREEN |
| T-F-2.1.39-2 | Hero photo has explicit dimensions | integration | F-2.1.39 | <img> has width= and height= attributes | GREEN |
| T-F-2.1.39-3 | CTA stack flex-column on mobile | unit | F-2.1.39 | .corporate-cta-stack has flex-direction: column | GREEN |
| T-F-2.1.40-1 | Tier cards use col-12 for mobile | integration | F-2.1.40 | col-12 col-lg-4 on tier card columns | GREEN |
| T-F-2.1.40-2 | Tier CTA is full-width | unit | F-2.1.40 | .corporate-tier-cta has width:100% | GREEN |
| T-F-2.1.41-1 | Sticky WhatsApp z-index is 1000 | unit | F-2.1.41 | z-index: 1000 in .whatsapp-sticky | GREEN |
| T-F-2.1.41-2 | Sticky WhatsApp 48px on mobile | unit | F-2.1.41 | 48px in whatsapp-sticky mobile rule | GREEN |
| T-F-2.1.42-1 | Hero uses .webp | integration | F-2.1.42 | avi-headshot.webp referenced in /corporate/ | GREEN |
| T-F-2.1.42-2 | No render-blocking scripts in <head> | integration | F-2.1.42 | No <script src> without defer/async in head | GREEN |
| T-F-2.1.42-3 | avi-headshot.webp exists in static/ | unit | F-2.1.42 | File exists on disk | GREEN |
| T-F-2.1.43-1 | Bootstrap responsive grid used | integration | F-2.1.43 | col-12 and col-lg- classes present | GREEN |
| T-F-2.1.43-2 | Viewport meta in base.html | unit | F-2.1.43 | <meta name="viewport" width=device-width> | GREEN |
| T-F-2.1.44-1 | dir= set by LANG_BIDI | unit | F-2.1.44 | base.html dir= uses LANG_BIDI template var | GREEN |
| T-F-2.1.44-2 | RTL flips sticky WhatsApp to left | unit | F-2.1.44 | html[dir="rtl"] .whatsapp-sticky left:16px in CSS | GREEN |
| T-F-2.1.46-1 | CSRF token in form | integration | F-2.1.46 | csrfmiddlewaretoken in /corporate/ | GREEN |
| T-F-2.1.46-2 | Message field has maxlength=1000 | integration | F-2.1.46 | maxlength="1000" on textarea | GREEN |
| T-F-2.1.49-1 | /corporate/ in sitemap.xml | integration | F-2.1.49 | /corporate/ appears in /sitemap.xml | GREEN |
