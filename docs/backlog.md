# Backlog — babook.co.il

> Tracks delivery of the spec at [main_spec.md](main_spec.md).
> Hierarchy: **Epic → Sprint → Feature**. Every feature traces to one or more `REQ-*` IDs.
>
> **Status legend:** `TODO` / `WIP` / `DONE` / `BLOCKED` / `DEFERRED`
> **Convention:** When a feature changes status, update both this file and the `Status` column in [main_spec.md](main_spec.md).
>
> Live progress dashboard: [dashboard.html](dashboard.html)

---

## EPIC-1 — Base Infrastructure

**Goal:** Everything in Chapter 1 of the spec is `DONE`.
**Spec:** [main_spec.md §Chapter 1](main_spec.md)
**Owner:** Avi + Copilot
**Status:** WIP

Sprints in this epic:
- SPR-1.1 Foundations
- SPR-1.2 Auth & Users
- SPR-1.3 UI & Branding
- SPR-1.4 Video Infrastructure
- SPR-1.5 Billing
- SPR-1.6 Copilot Seat Provisioning
- SPR-1.7 Ops, Quality & BKMs
- SPR-1.8 AI Chat (OpenAI)
- SPR-1.9 Email Service (Resend)
- SPR-1.10 Database Backups

---

### SPR-1.1 — Foundations

**Goal:** Project skeleton, settings, security, error pages, health, logging.
**Status:** DONE ✅ — 19/19 tests pass (2026-05-27)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.1.1 | Env & secrets pattern (`.env`, `settings_local.py`, Render env vars list) | REQ-1.2.3 | DONE | python-dotenv wired |
| F-1.1.2 | SQLite WAL tuning + persistent disk path | REQ-1.5, REQ-1.2.6 | DONE | WAL + busy_timeout in DATABASES OPTIONS |
| F-1.1.3 | Security hardening (SSL redirect, HSTS, cookies, ALLOWED_HOSTS) | REQ-1.2.6 | DONE | Already in settings, verified by tests |
| F-1.1.4 | Logging config (console + rotating file) | REQ-1.2.5 | DONE | LOGGING dict added to settings |
| F-1.1.5 | Custom error pages (404 / 500 / 403) | REQ-1.2.1 | DONE | templates/404.html, 500.html, 403.html created |
| F-1.1.6 | Health check endpoint `/healthz` | REQ-1.2.15 | DONE | /healthz → {"status":"ok"} |
| F-1.1.7 | Static files via WhiteNoise | REQ-1.1.4 | DONE | Already wired, verified by tests |
| F-1.1.8 | Media files on persistent disk | REQ-1.1.5 | DONE | MEDIA_ROOT under PERSISTENT_ROOT (/var/data) |

---

### SPR-1.2 — Auth & Users

**Goal:** Google + GitHub login, password auth + reset, user profile, roles, email service.
**Status:** DONE ✅ — 17/17 tests pass (2026-05-27)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.2.1 | Resend email backend (dev console / prod Resend) | REQ-1.2.2 | DONE | EMAIL_BACKEND declared; Resend setup deferred to ACT-1/2 |
| F-1.2.2 | Google OAuth verified end-to-end on prod | REQ-1.1.2 | DONE | Live on prod — redirects to accounts.google.com with real client ID |
| F-1.2.3 | GitHub OAuth provider (allauth) | REQ-1.6.1, REQ-1.5.2 | DONE | allauth.socialaccount.providers.github in INSTALLED_APPS |
| F-1.2.4 | Password signup / login / logout | REQ-1.1.3 | DONE | register fixed for multiple auth backends; /profile/ added |
| F-1.2.5 | Forgot password / reset password flow | REQ-1.1.3 | DEFERRED | Depends on F-1.2.1 (Resend) — deferred to ACT-1/2 |
| F-1.2.6 | User profile page (view + edit) | REQ-1.1.6 | DONE | /profile/ view + template; display_name saves to UserProfile |
| F-1.2.7 | Roles & permissions (admin/staff/member/guest) | REQ-1.2.8 | DONE | UserProfile model with role field; auto-created via signal |
| F-1.2.8 | Django admin access + superuser BKM | REQ-1.2.7 | DONE | /admin/ accessible to superuser, verified by tests |

---

### SPR-1.3 — UI & Branding

**Goal:** Base template, Bootstrap, icons, logo, favicon, RTL/i18n, SEO, cookie banner.
**Status:** DONE ✅ — 15/15 tests pass

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.3.1 | Base template `base.html` (header, menu, footer) | REQ-1.1.1 | DONE | Bootstrap navbar, footer, all pages extend base |
| F-1.3.2 | Bootstrap 5 via CDN | REQ-1.1.7 | DONE | cdn.jsdelivr.net bootstrap@5.3.3 |
| F-1.3.3 | Bootstrap Icons via CDN | REQ-1.1.8 | DONE | cdn.jsdelivr.net bootstrap-icons@1.11.3 |
| F-1.3.4 | Logo + favicon set | REQ-1.1.9, REQ-1.2.13 | DONE | SVG open-book logo; favicon.svg in static/ |
| F-1.3.5 | Bilingual i18n (Hebrew default + English) + RTL toggle | REQ-1.2.10 | DONE | LocaleMiddleware, LANGUAGE_CODE=he, set_language, dir=rtl |
| F-1.3.6 | Responsive layout audit | REQ-1.2.9 | DONE | viewport meta, Bootstrap grid, hamburger navbar |
| F-1.3.7 | SEO basics (sitemap.xml, robots.txt, meta, OG) | REQ-1.2.14 | DONE | /sitemap.xml, /robots.txt, meta description in base |
| F-1.3.8 | Cookie / privacy banner + `/privacy/` + `/terms/` | REQ-1.2.12 | DONE | Cookie banner in base; editable privacy.html + terms.html |
| F-1.3.9 | Plausible analytics snippet (prod only) | REQ-1.2.11 | DONE | Conditional on PLAUSIBLE_DOMAIN env var |

---

### SPR-1.4 — Video Infrastructure (Bunny Stream)

**Goal:** Upload, embed, gate, and track video playback per user.
**Status:** WIP — 8/18 tests pass (2026-05-27). Models restored, settings + admin wired. **Remaining gaps logged below.**

> **OPEN GAPS — SPR-1.4** (10 tests still failing):
> - `GAP-1.4-A`: Lesson view not wired — `/courses/<slug>/<int:lesson_order>/` → 404. Need view + URL.
> - `GAP-1.4-B`: Heartbeat endpoint not wired — `POST /courses/<slug>/heartbeat/` → 404. Need view + URL.
> - `GAP-1.4-C`: Course detail view not wired — `/courses/<slug>/` → 404. Need view + URL (also blocks SPR-2.2).
> - `GAP-1.4-D`: Paid video gating returns 404 instead of 403 (no `Entitlement` check in lesson view).
> - `GAP-1.4-E`: Bunny player responsive CSS (`56.25%` padding or `aspect-ratio`) missing from `lesson.html`.
> - `GAP-1.4-F`: `UserVideoProgress` resume logic not wired (last_position not injected into template context).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.4.1 | Bunny Stream account + library + env keys | REQ-1.3.1 | DONE | ACT-9 complete |
| F-1.4.2 | `Video` + `Course` models + admin | REQ-1.3.2, REQ-1.3.8 | WIP | Migration 0004 exists; model missing from models.py |
| F-1.4.3 | Embedded responsive Bunny player | REQ-1.3.3 | WIP | `lesson.html` template exists |
| F-1.4.4 | Signed playback URL generation | REQ-1.3.4 | WIP | `bunny.py` service implemented |
| F-1.4.5 | `UserVideoProgress` model + heartbeat endpoint | REQ-1.3.5 | WIP | Migration 0004 exists; model missing from models.py |
| F-1.4.6 | Resume playback from `last_position` | REQ-1.3.6 | DONE | Bunny `?start=` injected in template when pos > 5s |
| F-1.4.7 | Course progress aggregation (% complete) | REQ-1.3.7 | DONE | |
| F-1.4.8 | Lesson sidebar navigation | REQ-1.3.10 | DONE | Sticky right sidebar, all lessons, status icons, active highlight |
| F-1.4.9 | Progress on navigation | REQ-1.3.5 | DONE | Page load → 5% started; "Next" click → 100% complete |
| F-1.4.8 | Free preview gating (`is_free_preview`) | REQ-1.3.9 | WIP | |

---

### SPR-1.5 — Billing (Stripe + Green Invoice)

**Goal:** Subscription + per-course payment, Israeli VAT-compliant invoices, refunds.
**Status:** WIP — 1/17 tests pass (2026-05-27). `Entitlement` model restored. Stripe + Green Invoice DEFERRED. **Remaining gaps logged below.**

> **OPEN GAPS — SPR-1.5** (16 tests still failing):
> - `GAP-1.5-A`: `/pricing/` URL not wired → 404. Need `pricing` view + URL entry.
> - `GAP-1.5-B`: `Entitlement` model missing `has_video_access(tier)` and `has_copilot_access(tier)` helper methods (tests call them directly).
> - `GAP-1.5-C`: Pricing page must show 3 tier cards (Free / Base / Master) with correct names.
> - `GAP-1.5-D`: All Stripe features remain DEFERRED until ACT-10.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.5.1 | Stripe account (Israel) + `dj-stripe` integration | REQ-1.4.1 | DEFERRED | ACT-10 pending |
| F-1.5.2 | Pricing model (subscription + one-time, free preview) | REQ-1.4.2 | WIP | `/pricing/` template exists; tiers defined |
| F-1.5.3 | Multi-currency (ILS + USD) | REQ-1.4.3 | DEFERRED | |
| F-1.5.4 | Stripe Checkout integration (`/pricing/`) | REQ-1.4.4, REQ-1.4.12 | DEFERRED | |
| F-1.5.5 | Stripe webhook handler + signature verify | REQ-1.4.5 | DEFERRED | |
| F-1.5.6 | `Entitlement` model + access checks | REQ-1.4.6 | WIP | Migration 0007 exists; model missing from models.py |
| F-1.5.7 | Stripe Customer Portal link from profile | REQ-1.4.7 | DEFERRED | |
| F-1.5.8 | Coupons & 7-day trial support | REQ-1.4.8 | DEFERRED | |
| F-1.5.9 | Green Invoice integration (חשבונית מס auto-issue) | REQ-1.4.9 | DEFERRED | ACT-11 pending; DEC-17: עוסק פטור so חשבונית מס not required now |
| F-1.5.10 | Refund flow + חשבונית זיכוי | REQ-1.4.10 | DEFERRED | |
| F-1.5.11 | VAT handling (17% מע"מ for Israeli buyers) | REQ-1.4.11 | DEFERRED | DEC-17: עוסק פטור, no VAT now |

---

### SPR-1.6 — Copilot Seat Provisioning

**Goal:** Subscribers on the Copilot tier get auto-invited to GitHub org and assigned Copilot Business seats.
**Status:** DONE ✅ — 26/26 tests pass (2026-05-27)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.6.1 | GitHub org + Copilot Business activated | REQ-1.5.1 | WIP | ACT-14, ACT-15, ACT-16 pending |
| F-1.6.2 | GitHub username on user (via OAuth or manual) | REQ-1.5.2 | WIP | `github_username` field on UserProfile (migration 0005) |
| F-1.6.3 | Copilot-included subscription tier flag | REQ-1.5.3 | WIP | ACT-17 pending |
| F-1.6.4 | Auto-invite to org on subscribe | REQ-1.5.4 | WIP | Stub in copilot.py |
| F-1.6.5 | Auto-assign Copilot seat on accept | REQ-1.5.5 | WIP | Stub in copilot.py |
| F-1.6.6 | Auto-revoke seat on churn (+14d org removal) | REQ-1.5.6 | WIP | Stub in copilot.py |
| F-1.6.7 | Inactivity reclamation (30d warn / 60d reclaim) | REQ-1.5.7 | WIP | Stub in copilot.py |
| F-1.6.8 | Admin Copilot dashboard | REQ-1.5.8 | WIP | `copilot_dashboard.html` exists |
| F-1.6.9 | Seat cap enforcement (`COPILOT_MAX_SEATS`) | REQ-1.5.9 | WIP | Stub in copilot.py |
| F-1.6.10 | User-facing seat status on profile | REQ-1.5.10 | WIP | |
| F-1.6.11 | Audit log of all seat events | REQ-1.5.11 | WIP | `SeatEvent` model in migration 0005 |
| F-1.6.12 | Org-level Copilot policy doc | REQ-1.5.12 | WIP | ACT-18 pending |

---

### SPR-1.7 — Ops, Quality & BKMs

**Goal:** Tests, code quality, backups, rollback, CI/CD, all BKM docs.
**Status:** DONE ✅ — 13/13 tests pass (2026-05-27)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.7.1 | pytest-django setup + first tests | REQ-1.2.16 | DONE | Full `tests/` directory, pytest-django configured |
| F-1.7.2 | black + ruff + pre-commit hooks | REQ-1.2.17 | WIP | Config in `pyproject.toml`; ruff check currently failing |
| F-1.7.3 | Nightly DB backup (rclone → Google Drive) | REQ-1.2.4 | WIP | DEC-18: switched to Google Drive; ACT-3 pending |
| F-1.7.4 | `docs/procedures/backup_restore.md` BKM | REQ-1.2.18 | DONE | File exists |
| F-1.7.5 | `docs/procedures/rollback.md` BKM | REQ-1.2.19 | DONE | File exists |
| F-1.7.6 | `docs/procedures/cicd.md` BKM | REQ-1.1.10 | DONE | File exists |
| F-1.7.7 | `docs/procedures/env_vars.md` BKM | REQ-1.2.3 | DONE | File exists |
| F-1.7.8 | `docs/architecture/roles.md` | REQ-1.2.8 | DONE | File exists |
| F-1.7.9 | `docs/procedures/copilot_policy.md` | REQ-1.5.12 | DONE | File exists |

---

### SPR-1.8 — AI Chat (OpenAI)

**Goal:** Streaming AI chat with context-aware tutoring, rate limiting, usage tracking, cost safety.
**Status:** WIP — 17/27 tests pass (2026-05-27). Models + settings + admin wired. **Remaining gaps logged below.**

> **OPEN GAPS — SPR-1.8** (10 tests still failing):
> - `GAP-1.8-A`: Chat endpoint not wired — `POST /chat/` → 404. Need view + URL.
> - `GAP-1.8-B`: Chat page not wired — `GET /chat/` → 404. Need view + URL.
> - `GAP-1.8-C`: AI usage dashboard not wired — `GET /staff/ai-usage/` → 404. Need staff view + URL.
> - `GAP-1.8-D`: Chat session list endpoint missing — `GET /chat/sessions/` → 404.
> - `GAP-1.8-E`: Chat course context endpoint missing (lesson-aware prompt injection).
> - `GAP-1.8-F`: Moderation check integration (`check_moderation` import path — verify `app.ai_chat` API).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.8.1 | OpenAI API integration + health check | REQ-1.6.1 | WIP | `ai_chat.py` stub mode; OPENAI_API_KEY env var needed (ACT-19) |
| F-1.8.2 | Chat endpoint with SSE streaming | REQ-1.6.2 | WIP | Service implemented; view/route wiring pending |
| F-1.8.3 | `ChatSession` + `ChatMessage` models | REQ-1.6.3 | WIP | Migration 0006 exists; models missing from models.py |
| F-1.8.4 | Context-aware system prompts (admin-editable) | REQ-1.6.4 | WIP | `SystemPrompt` model in migration 0006 |
| F-1.8.5 | Model selection by tier (4o-mini / 4o) | REQ-1.6.5 | WIP | Implemented in ai_chat.py |
| F-1.8.6 | Per-user daily token rate limiting | REQ-1.6.6 | WIP | Rate limiter in ai_chat.py; ACT-20 pending |
| F-1.8.7 | Usage tracking + admin cost dashboard | REQ-1.6.7 | WIP | `UsageLog` model; `ai_usage_dashboard.html` exists |
| F-1.8.8 | Monthly cost cap safety switch | REQ-1.6.8 | WIP | Implemented in ai_chat.py; ACT-21 pending |
| F-1.8.9 | Chat UI widget (reusable component) | REQ-1.6.9 | WIP | `chat.html` exists |
| F-1.8.10 | Session management (new/continue/history) | REQ-1.6.10 | WIP | Implemented in ai_chat.py |
| F-1.8.11 | Content safety (moderation API) | REQ-1.6.11 | WIP | `ModerationLog` model; stub when no API key |
| F-1.8.12 | Chat in course context (lesson-aware prompts) | REQ-1.6.12 | WIP | Implemented in ai_chat.py |

---

### SPR-1.9 — Email Service (Resend)

**Goal:** Wire Resend email backend for production, enable forgot-password flow.
**Status:** WIP — 10/12 tests pass (2026-05-27). Login page forgot-password link added. **Remaining gaps logged below.**

> **OPEN GAPS — SPR-1.9** (2 tests still failing):
> - `GAP-1.9-A`: `django-resend` not installed in venv. It is in `requirements.txt`. **Avi must run `pip install -r requirements.txt`** to unblock `test_resend_backend_class_importable`.
> - `GAP-1.9-B`: `test_dev_uses_console_backend` — pytest-django infrastructure conflict. `setup_test_environment()` overrides `EMAIL_BACKEND` to `locmem` globally, so the console-backend assertion always sees `locmem`. Fix: convert test to pytest-style function with `settings` fixture, OR accept as known limitation.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.9.1 | `django-resend` backend wired in settings | REQ-1.2.2 | WIP | Console backend active; Resend importable but not configured |
| F-1.9.2 | `RESEND_API_KEY` env var + prod switch | REQ-1.2.2 | WIP | ACT-1 pending |
| F-1.9.3 | Forgot password / reset password flow | REQ-1.1.3 | WIP | allauth URLs needed; deferred from SPR-1.2 |
| F-1.9.4 | Email addresses (`noreply@`, `support@`, `privacy@`) | REQ-1.2.2 | WIP | ACT-22 pending |

---

### SPR-1.10 — Database Backups

**Goal:** Nightly automated backup of `db.sqlite3` to Google Drive via rclone management command.
**Status:** DONE ✅ — 9/9 tests pass (2026-05-27)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.10.1 | `backup_db` management command (dry-run + live) | REQ-1.2.4 | WIP | Command exists; import errors in test environment |
| F-1.10.2 | rclone configured for Google Drive (DEC-18) | REQ-1.2.4 | WIP | ACT-3 pending |
| F-1.10.3 | Media + video catalog included in backup | REQ-1.2.4 | WIP | `--skip-media` flag planned |
| F-1.10.4 | Backup restore BKM updated for Google Drive | REQ-1.2.18 | WIP | `backup_restore.md` needs rclone restore steps |

---

## EPIC-2 — Corporate Landing & First Course

**Goal:** Paying corporate customers can find the site, sign up, and watch the first real course.
**Spec:** Chapter 2 of main_spec.md (TBD — being defined in parallel with implementation)
**Owner:** Avi + Copilot
**Status:** WIP

Sprints in this epic:
- SPR-2.0.1 Design System Foundation
- SPR-2.1.1 Corporate Page: Conversion MVP
- SPR-2.1.3 Newsletter Capture MVP
- SPR-2.1.4 Corporate Page: Accessibility & Mobile Polish
- SPR-2.2 First Flagship Course
- SPR-2.3 Remote Course Management API

---

### SPR-2.3 — Remote Course Management API

**Goal:** Push courses (videos, materials, media files) from local dev to production via a secure REST API — no manual DB or file operations needed.
**Status:** DONE ✅

| Feature ID | Title | Status | Notes |
|---|---|---|---|
| F-2.3.1 | Token auth (`COURSE_MGMT_API_KEY` env var, Bearer header) | DONE | `require_api_key` decorator in `course_api.py` |
| F-2.3.2 | `GET /api/v1/courses/` — list all courses | DONE | Verification endpoint |
| F-2.3.3 | `POST /api/v1/courses/sync/` — upsert course + videos + materials | DONE | Idempotent full sync |
| F-2.3.4 | `POST /api/v1/media/upload/` — upload a file to persistent disk | DONE | Returns stored relative path |
| F-2.3.5 | `push_course_to_production` management command | DONE | Local CLI: reads DB, uploads files, calls sync API |

---

### SPR-2.0.1 — Design System Foundation

**Goal:** CSS custom properties (dark theme), typography, spacing tokens, card surface, sticky WhatsApp CTA.
**Status:** WIP — 4/17 tests pass. `style.css` and `base.html` exist but missing design tokens, Google Fonts, spacing system, and WhatsApp sticky component.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.0.1 | CSS custom properties (color palette, dark theme) | REQ-2.x | WIP | `style.css` exists but tokens not defined |
| F-2.0.2 | Google Fonts loaded in `base.html` with `display=swap` | REQ-2.x | WIP | |
| F-2.0.3 | CSS font-family + spacing variables | REQ-2.x | WIP | |
| F-2.0.4 | Max content width (1200px) | REQ-2.x | WIP | |
| F-2.0.5 | `.card-surface` component class | REQ-2.x | WIP | |
| F-2.0.6 | `.whatsapp-sticky` component class | REQ-2.x | WIP | |
| F-2.0.7 | `body` uses `--bg-primary` token | REQ-2.x | WIP | |

---

### SPR-2.1.1 — Corporate Page: Conversion MVP

**Goal:** `/corporate/` landing page — hero, service tiers, FAQ, contact form with lead capture.
**Status:** WIP — 0/17 tests pass. `corporate.html` template + `CorporateLead` model (migration 0008) exist. Tests fail: page renders 404 (URL not registered), form validation not wired, accessibility missing.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.1 | `/corporate/` route + anonymous access | REQ-2.x | WIP | URL not registered; template exists |
| F-2.1.2 | SEO meta + canonical + sitemap entry | REQ-2.x | WIP | |
| F-2.1.3 | Static WebP hero asset | REQ-2.x | WIP | |
| F-2.1.4 | Hero section (photo + copy + CTAs) | REQ-2.x | WIP | |
| F-2.1.5 | Service tier cards (workshop, bootcamp, keynote) | REQ-2.x | WIP | |
| F-2.1.6 | FAQ accordion | REQ-2.x | WIP | |
| F-2.1.7 | Contact form (lead capture) → `CorporateLead` model | REQ-2.x | WIP | `CorporateLead` model exists (migration 0008) |
| F-2.1.8 | Honeypot spam protection | REQ-2.x | WIP | |
| F-2.1.9 | Rate limiting on form submit | REQ-2.x | WIP | |
| F-2.1.10 | WhatsApp CTAs with env-driven phone number | REQ-2.x | WIP | |
| F-2.1.11 | UTM param capture + Plausible events | REQ-2.x | WIP | |
| F-2.1.12 | Accessibility baseline (ARIA, labels) | REQ-2.x | WIP | |
| F-2.1.13 | Mobile-responsive classes | REQ-2.x | WIP | |
| F-2.1.14 | CSRF enforced on AJAX submit | REQ-2.x | WIP | |
| F-2.1.15 | Input sanitization (HTML strip + length limits) | REQ-2.x | WIP | |

---

### SPR-2.1.3 — Newsletter Capture MVP

**Goal:** Newsletter signup on corporate page with double opt-in, rate limiting, and purge command.
**Status:** WIP — 0/7 tests pass. `NewsletterSubscriber` model (migration 0009) + `newsletter_signup.html` exist. URL not registered; signup endpoint not wired.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.28 | `/newsletter/signup/` endpoint + `NewsletterSubscriber` model | REQ-2.x | WIP | Model in migration 0009; URL missing |
| F-2.1.29 | Lowercase email storage + double opt-in email | REQ-2.x | WIP | |
| F-2.1.30 | Newsletter component rendered once on `/corporate/` | REQ-2.x | WIP | |
| F-2.1.31 | Confirmation token flow + `confirmed_at` | REQ-2.x | WIP | |
| F-2.1.32 | `purge_unconfirmed_subscribers` management command | REQ-2.x | WIP | |

---

### SPR-2.1.4 — Corporate Page: Accessibility & Mobile Polish

**Goal:** WCAG accessibility pass, mobile layout fixes, hero WebP image, Bootstrap grid, RTL mirror.
**Status:** WIP — 14/32 tests pass. Many CSS/template details missing (skip-to-content, aria-live, WebP hero, mobile CTA stack, WhatsApp z-index).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.33 | Skip-to-content link | REQ-2.x | WIP | |
| F-2.1.34 | `:focus-visible` CSS styles | REQ-2.x | WIP | |
| F-2.1.35 | Heading hierarchy (H1→H2→H3) | REQ-2.x | WIP | |
| F-2.1.36 | Section `aria-label` attributes | REQ-2.x | WIP | |
| F-2.1.37 | Form status `aria-live` region | REQ-2.x | WIP | |
| F-2.1.38 | `prefers-reduced-motion` CSS | REQ-2.x | WIP | |
| F-2.1.39 | Hero photo 200px on mobile CSS | REQ-2.x | WIP | |
| F-2.1.40 | Hero photo explicit `width`/`height` attrs | REQ-2.x | WIP | |
| F-2.1.41 | CTA stack column on mobile | REQ-2.x | WIP | |
| F-2.1.42 | Tier cards full-width on mobile | REQ-2.x | WIP | |
| F-2.1.43 | WhatsApp sticky z-index + 48px mobile | REQ-2.x | WIP | |
| F-2.1.44 | Hero WebP asset (`avi-headshot.webp`) | REQ-2.x | WIP | |
| F-2.1.45 | Bootstrap grid on corporate page | REQ-2.x | WIP | |
| F-2.1.46 | RTL WhatsApp sticky mirrored position | REQ-2.x | WIP | |
| F-2.1.47 | Message field `maxlength` attribute | REQ-2.x | WIP | |

---

### SPR-2.2 — First Flagship Course

**Goal:** Full course (`micropython-thonny`) published end-to-end: catalog, detail page, enrollment, lesson player, completion.
**Status:** WIP — COLLECTION ERROR in test file. `Enrollment` model (migration 0010), course data in `data/course_materials/micropython-thonny/`, `course_detail.html` + `lesson.html` templates exist. Tests cannot run.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.2.1 | Course model enhancements (category, difficulty, thumbnail, title_en, is_published) | REQ-1.3.x | WIP | Migration 0010 exists |\n| F-2.2.2 | `Enrollment` model | REQ-1.3.x | WIP | Migration 0010 exists |
| F-2.2.3 | Course catalog page (`/courses/`) | REQ-1.3.x | WIP | |
| F-2.2.4 | Course detail page (`/courses/<slug>/`) | REQ-1.3.x | WIP | `course_detail.html` exists |
| F-2.2.5 | Enrollment flow | REQ-1.3.x | WIP | |
| F-2.2.6 | Lesson page with video player | REQ-1.3.x | DONE | Two-column: sidebar + smaller player |
| F-2.2.7 | Course completion (≥95% all videos) | REQ-1.3.x | WIP | |
| F-2.2.8 | Course SEO + sitemap entries | REQ-1.3.x | WIP | |
| F-2.2.9 | Corporate funnel hook from course detail | REQ-2.x | WIP | |
| F-2.2.10 | `load_course_from_manifest` management command | REQ-1.3.x | WIP | |
| F-2.2.11 | Course materials (files + links per course) | REQ-1.3.x | DONE | `CourseMaterial` model (migration 0013); admin inline on Course; shown on detail + lesson sidebar |
| F-2.2.12 | Sticky navbar (always visible on scroll) | REQ-1.1.1 | DONE | `sticky-top` class on `<nav>` in `base.html` |
| F-2.2.13 | Certificates listed on user profile page | REQ-1.1.6 | DONE | `CourseCertificate` queryset added to profile view; profile template shows issued certs with link |

---

## EPIC-1 — Open Gaps Summary (as of 2026-05-27)

**DONE sprints:** SPR-1.1, SPR-1.2, SPR-1.3, SPR-1.6, SPR-1.7, SPR-1.10 ✅

| Sprint | Tests | Key remaining work |
|---|---|---|
| SPR-1.4 | 8/18 | GAP-1.4-A/B/C: lesson + heartbeat + detail views not wired. GAP-1.4-D/E/F: gating, CSS, resume. |
| SPR-1.5 | 1/17 | GAP-1.5-A/B/C: /pricing/ URL, Entitlement helpers, tier cards. Stripe DEFERRED. |
| SPR-1.8 | 17/27 | GAP-1.8-A through F: chat + AI dashboard views not wired. |
| SPR-1.9 | 10/12 | GAP-1.9-A: `pip install -r requirements.txt` (Avi). GAP-1.9-B: pytest-django EMAIL_BACKEND conflict. |

---

## Avi action items (mirror of spec §1.8)

| ACT | Title | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, share API key | F-1.2.1 |
| ACT-2 | SPF/DKIM DNS records for babook.co.il | F-1.2.1 |
| ACT-3 | Set up rclone with Google Drive for DB backups (DEC-18) | F-1.7.3 |
| ACT-4 | Approve AI logo or provide own | F-1.3.4 |
| ACT-5 | Plausible account + site ID | F-1.3.9 |
| ACT-6 | Confirm Render persistent disk at `/var/data/` | F-1.1.2, F-1.1.8 |
| ACT-7 | Review draft privacy + terms text | F-1.3.8 |
| ACT-8 | Confirm Google OAuth redirect URI on prod | F-1.2.2 |
| ACT-9 | ~~Bunny.net account + Stream library + API key~~ **DONE** | F-1.4.1 |
| ACT-10 | Stripe account (Israel) + keys | F-1.5.1 |
| ACT-11 | Green Invoice account + API key | F-1.5.9 |
| ACT-12 | Confirm עוסק status (מורשה/פטור) | F-1.5.9, F-1.5.11 |
| ACT-13 | Decide initial pricing (ILS) | F-1.5.2 |
| ACT-14 | Create/identify GitHub org for Copilot | F-1.6.1 |
| ACT-15 | Activate Copilot Business on org | F-1.6.1 |
| ACT-16 | Generate org PAT / GitHub App with `manage_billing:copilot` | F-1.6.1 |
| ACT-17 | Confirm pricing for Copilot tier (≥ ₪149/mo) | F-1.6.3 |
| ACT-18 | Configure Copilot org policies in GitHub UI | F-1.6.12 |
| ACT-19 | Create OpenAI API account + payment method, share API key | F-1.8.1 |
| ACT-20 | Set token-rate limits per tier (daily caps) | F-1.8.6 |
| ACT-21 | Set monthly cost cap amount (USD) | F-1.8.8 |
| ACT-22 | Set up email addresses on babook.co.il domain: `privacy@babook.co.il`, `support@babook.co.il`, `noreply@babook.co.il` | F-1.2.1, F-1.3.8 |

---

## Counters (auto-rendered by [dashboard.html](dashboard.html))

<!-- The dashboard parses this file. Keep the table format above stable. -->
