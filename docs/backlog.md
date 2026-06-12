# Backlog — babook.co.il

> Tracks delivery of the spec at [main_spec.md](main_spec.md).
> Hierarchy: **Epic → Sprint → Feature**. Every feature traces to one or more `REQ-*` IDs.
>
> **Status legend:** `TODO` / `WIP` / `DONE` / `BLOCKED` / `DEFERRED`
> **Convention:** When a feature changes status, update both this file and the `Status` column in [main_spec.md](main_spec.md).
>
> Live progress dashboard: [dashboard.html](dashboard.html)
>
> **Reconciled 2026-06-09:** statuses below re-audited against the actual code,
> the full regression (**274/274 passing**), and live production routes on
> babook.co.il. The prior snapshot (2026-05-27) was stale — many sprints it
> listed as WIP/failing are implemented, passing, and live. Remaining real work
> is **Stripe billing (DEFERRED)** and **external-service activations pending Avi
> ACT items** (Copilot org, nightly backup scheduling). Verified live this date:
> `/corporate/ /courses/ /pricing/ /chat/` → 200, `/newsletter/signup/` → 405
> (POST-only), password-reset email delivered via Resend.

---

## EPIC-1 — Base Infrastructure

**Goal:** Everything in Chapter 1 of the spec is `DONE`.
**Spec:** [main_spec.md §Chapter 1](main_spec.md)
**Owner:** Avi + Copilot
**Status:** DONE ✅ — all sprints pass; **Stripe billing DEFERRED**; some live external-service activations pending Avi ACTs (Copilot org, backup scheduling).

Sprints in this epic:
- SPR-1.1 Foundations — DONE
- SPR-1.2 Auth & Users — DONE
- SPR-1.3 UI & Branding — DONE
- SPR-1.4 Video Infrastructure — DONE
- SPR-1.5 Billing — Pricing/Entitlement DONE; Stripe DEFERRED
- SPR-1.6 Copilot Seat Provisioning — DONE (code); live org pending ACTs
- SPR-1.7 Ops, Quality & BKMs — DONE
- SPR-1.8 AI Chat (OpenAI) — DONE
- SPR-1.9 Email Service (Resend) — DONE (verified live 2026-06-09)
- SPR-1.10 Database Backups — DONE (command); nightly scheduling pending ACT-3

---

### SPR-1.1 — Foundations

**Goal:** Project skeleton, settings, security, error pages, health, logging.
**Status:** DONE ✅ — 19/19 tests pass

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.1.1 | Env & secrets pattern (`.env`, `settings_local.py`, Render env vars list) | REQ-1.2.3 | DONE | python-dotenv wired |
| F-1.1.2 | SQLite WAL tuning + persistent disk path | REQ-1.5, REQ-1.2.6 | DONE | WAL + busy_timeout in DATABASES OPTIONS |
| F-1.1.3 | Security hardening (SSL redirect, HSTS, cookies, ALLOWED_HOSTS) | REQ-1.2.6 | DONE | Verified by tests |
| F-1.1.4 | Logging config (console + rotating file) | REQ-1.2.5 | DONE | LOGGING dict in settings |
| F-1.1.5 | Custom error pages (404 / 500 / 403) | REQ-1.2.1 | DONE | templates/404.html, 500.html, 403.html |
| F-1.1.6 | Health check endpoint `/healthz` | REQ-1.2.15 | DONE | /healthz → {"status":"ok"}; verified live |
| F-1.1.7 | Static files via WhiteNoise | REQ-1.1.4 | DONE | Verified by tests |
| F-1.1.8 | Media files on persistent disk | REQ-1.1.5 | DONE | MEDIA_ROOT under PERSISTENT_ROOT (/var/data) |

---

### SPR-1.2 — Auth & Users

**Goal:** Google + GitHub login, password auth + reset, user profile, roles, email service.
**Status:** DONE ✅ — 17/17 tests pass

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.2.1 | Resend email backend (dev console / prod Resend) | REQ-1.2.2 | DONE | anymail/Resend; verified live 2026-06-09 (see SPR-1.9) |
| F-1.2.2 | Google OAuth verified end-to-end on prod | REQ-1.1.2 | DONE | Live on prod |
| F-1.2.3 | GitHub OAuth provider (allauth) | REQ-1.6.1, REQ-1.5.2 | DONE | github provider in INSTALLED_APPS |
| F-1.2.4 | Password signup / login / logout | REQ-1.1.3 | DONE | /profile/ added |
| F-1.2.5 | Forgot password / reset password flow | REQ-1.1.3 | DONE | Live — reset email delivered via Resend 2026-06-09 |
| F-1.2.6 | User profile page (view + edit) | REQ-1.1.6 | DONE | /profile/ view + template |
| F-1.2.7 | Roles & permissions (admin/staff/member/guest) | REQ-1.2.8 | DONE | UserProfile.role, auto-created via signal |
| F-1.2.8 | Django admin access + superuser BKM | REQ-1.2.7 | DONE | /admin/ superuser-only |

---

### SPR-1.3 — UI & Branding

**Goal:** Base template, Bootstrap, icons, logo, favicon, RTL/i18n, SEO, cookie banner.
**Status:** DONE ✅ — 15/15 tests pass

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.3.1 | Base template `base.html` (header, menu, footer) | REQ-1.1.1 | DONE | All pages extend base |
| F-1.3.2 | Bootstrap 5 via CDN | REQ-1.1.7 | DONE | jsdelivr bootstrap@5.3.3 |
| F-1.3.3 | Bootstrap Icons via CDN | REQ-1.1.8 | DONE | jsdelivr bootstrap-icons@1.11.3 |
| F-1.3.4 | Logo + favicon set | REQ-1.1.9, REQ-1.2.13 | DONE | SVG open-book logo + favicon |
| F-1.3.5 | Bilingual i18n (Hebrew default + English) + RTL toggle | REQ-1.2.10 | DONE | LocaleMiddleware, dir=rtl |
| F-1.3.6 | Responsive layout audit | REQ-1.2.9 | DONE | Bootstrap grid, hamburger navbar |
| F-1.3.7 | SEO basics (sitemap.xml, robots.txt, meta, OG) | REQ-1.2.14 | DONE | /sitemap.xml + /robots.txt live (200) |
| F-1.3.8 | Cookie / privacy banner + `/privacy/` + `/terms/` | REQ-1.2.12 | DONE | Banner + editable privacy/terms |
| F-1.3.9 | Plausible analytics snippet (prod only) | REQ-1.2.11 | DONE | Conditional on PLAUSIBLE_DOMAIN |

---

### SPR-1.4 — Video Infrastructure (Bunny Stream)

**Goal:** Upload, embed, gate, and track video playback per user.
**Status:** DONE ✅ — 21/21 tests pass. All prior gaps (lesson/heartbeat/detail views, gating, responsive CSS, resume) RESOLVED. Lesson routes verified live on prod 2026-06-09.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.4.1 | Bunny Stream account + library + env keys | REQ-1.3.1 | DONE | ACT-9 complete |
| F-1.4.2 | `Video` + `Course` models + admin | REQ-1.3.2, REQ-1.3.8 | DONE | Models + admin wired |
| F-1.4.3 | Embedded responsive Bunny player | REQ-1.3.3 | DONE | `.lesson-player` 16:9 wrapper (style.css) |
| F-1.4.4 | Signed playback URL generation | REQ-1.3.4 | DONE | `bunny.py` generate_signed_url |
| F-1.4.5 | `UserVideoProgress` model + heartbeat endpoint | REQ-1.3.5 | DONE | Model + `/api/video-progress/` |
| F-1.4.6 | Resume playback from `last_position` | REQ-1.3.6 | DONE | Bunny `?start=` when pos > 5s |
| F-1.4.7 | Course progress aggregation (% complete) | REQ-1.3.7 | DONE | |
| F-1.4.8 | Lesson sidebar navigation | REQ-1.3.10 | DONE | Sticky sidebar, status icons |
| F-1.4.9 | Progress on navigation | REQ-1.3.5 | DONE | Visit → recorded; Next → complete |
| F-1.4.10 | Free preview gating (`is_free_preview`) | REQ-1.3.9 | DONE | Anonymous can view previews; paid → 403 |
| F-1.4.11 | get_item filter None-guard (Django render safety) | REQ-1.3.12 | DONE | Fixed 2026-06-09 (commit 0fd3b64) |

---

### SPR-1.5 — Billing (Stripe + Green Invoice)

**Goal:** Subscription + per-course payment, Israeli VAT-compliant invoices, refunds.
**Status:** WIP — 17/17 tests pass for the **non-Stripe** scope (pricing page, tiers, Entitlement access checks). **All Stripe + Green Invoice features remain DEFERRED** pending ACT-10/11/13 and DEC-17 (עוסק פטור → חשבונית מס not required now). `/pricing/` live on prod (200).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.5.1 | Stripe account (Israel) + `dj-stripe` integration | REQ-1.4.1 | DEFERRED | ACT-10 pending |
| F-1.5.2 | Pricing model (subscription + one-time, free preview) | REQ-1.4.2 | DONE | `/pricing/` live; 3 tier cards |
| F-1.5.3 | Multi-currency (ILS + USD) | REQ-1.4.3 | DEFERRED | |
| F-1.5.4 | Stripe Checkout integration (`/pricing/`) | REQ-1.4.4, REQ-1.4.12 | DEFERRED | |
| F-1.5.5 | Stripe webhook handler + signature verify | REQ-1.4.5 | DEFERRED | |
| F-1.5.6 | `Entitlement` model + access checks | REQ-1.4.6 | DONE | Model + has_video_access/has_copilot_access |
| F-1.5.7 | Stripe Customer Portal link from profile | REQ-1.4.7 | DEFERRED | |
| F-1.5.8 | Coupons & 7-day trial support | REQ-1.4.8 | DEFERRED | |
| F-1.5.9 | Green Invoice integration (חשבונית מס auto-issue) | REQ-1.4.9 | DEFERRED | ACT-11; DEC-17 (עוסק פטור) |
| F-1.5.10 | Refund flow + חשבונית זיכוי | REQ-1.4.10 | DEFERRED | |
| F-1.5.11 | VAT handling (17% מע"מ for Israeli buyers) | REQ-1.4.11 | DEFERRED | DEC-17: עוסק פטור, no VAT now |

---

### SPR-1.6 — Copilot Seat Provisioning

**Goal:** Subscribers on the Copilot tier get auto-invited to GitHub org and assigned Copilot Business seats.
**Status:** DONE ✅ (code) — 26/26 tests pass. **Live org activation pending ACT-14/15/16** (create org, activate Copilot Business, share org PAT). Logic runs against the GitHub API once those creds exist.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.6.1 | GitHub org + Copilot Business activated | REQ-1.5.1 | BLOCKED | ACT-14/15/16 (Avi) — external setup |
| F-1.6.2 | GitHub username on user (via OAuth or manual) | REQ-1.5.2 | DONE | `github_username` on UserProfile |
| F-1.6.3 | Copilot-included subscription tier flag | REQ-1.5.3 | DONE | Tier flag; pricing pending ACT-17 |
| F-1.6.4 | Auto-invite to org on subscribe | REQ-1.5.4 | DONE | copilot.py (live once org exists) |
| F-1.6.5 | Auto-assign Copilot seat on accept | REQ-1.5.5 | DONE | copilot.py |
| F-1.6.6 | Auto-revoke seat on churn (+14d org removal) | REQ-1.5.6 | DONE | copilot.py |
| F-1.6.7 | Inactivity reclamation (30d warn / 60d reclaim) | REQ-1.5.7 | DONE | copilot.py |
| F-1.6.8 | Admin Copilot dashboard | REQ-1.5.8 | DONE | copilot_dashboard.html |
| F-1.6.9 | Seat cap enforcement (`COPILOT_MAX_SEATS`) | REQ-1.5.9 | DONE | env COPILOT_MAX_SEATS=10 |
| F-1.6.10 | User-facing seat status on profile | REQ-1.5.10 | DONE | |
| F-1.6.11 | Audit log of all seat events | REQ-1.5.11 | DONE | `SeatEvent` model |
| F-1.6.12 | Org-level Copilot policy doc | REQ-1.5.12 | DONE | copilot_policy.md; ACT-18 (live config) pending |

---

### SPR-1.7 — Ops, Quality & BKMs

**Goal:** Tests, code quality, backups, rollback, CI/CD, all BKM docs.
**Status:** DONE ✅ — 13/13 tests pass (ruff check now clean as of 2026-06-09).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.7.1 | pytest-django setup + first tests | REQ-1.2.16 | DONE | Full `tests/`; 274 passing |
| F-1.7.2 | black + ruff + pre-commit hooks | REQ-1.2.17 | DONE | Config in pyproject; ruff check clean. NOTE: pre-commit hook not installed on this machine (`pre-commit install` to enable); black hook pins python3.11 |
| F-1.7.3 | Nightly DB backup (rclone → Google Drive) | REQ-1.2.4 | WIP | `backup_db` command exists (GCS-based); nightly schedule + target setup pending ACT-3 |
| F-1.7.4 | `docs/procedures/backup_restore.md` BKM | REQ-1.2.18 | DONE | File exists |
| F-1.7.5 | `docs/procedures/rollback.md` BKM | REQ-1.2.19 | DONE | File exists |
| F-1.7.6 | `docs/procedures/cicd.md` BKM | REQ-1.1.10 | DONE | File exists |
| F-1.7.7 | `docs/procedures/env_vars.md` BKM | REQ-1.2.3 | DONE | File exists |
| F-1.7.8 | `docs/architecture/roles.md` | REQ-1.2.8 | DONE | File exists |
| F-1.7.9 | `docs/procedures/copilot_policy.md` | REQ-1.5.12 | DONE | File exists |

---

### SPR-1.8 — AI Chat (OpenAI)

**Goal:** Streaming AI chat with context-aware tutoring, rate limiting, usage tracking, cost safety.
**Status:** DONE ✅ — 27/27 tests pass. Chat + AI-usage dashboard routes wired and live on prod (`/chat/` → 200). OPENAI_API_KEY configured (env). Prior gaps A–F RESOLVED.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.8.1 | OpenAI API integration + health check | REQ-1.6.1 | DONE | OPENAI_API_KEY set (env) |
| F-1.8.2 | Chat endpoint with SSE streaming | REQ-1.6.2 | DONE | view/route wired |
| F-1.8.3 | `ChatSession` + `ChatMessage` models | REQ-1.6.3 | DONE | |
| F-1.8.4 | Context-aware system prompts (admin-editable) | REQ-1.6.4 | DONE | `SystemPrompt` model |
| F-1.8.5 | Model selection by tier (4o-mini / 4o) | REQ-1.6.5 | DONE | |
| F-1.8.6 | Per-user daily token rate limiting | REQ-1.6.6 | DONE | Caps configurable (ACT-20 to tune) |
| F-1.8.7 | Usage tracking + admin cost dashboard | REQ-1.6.7 | DONE | `/staff/ai-usage/` |
| F-1.8.8 | Monthly cost cap safety switch | REQ-1.6.8 | DONE | OPENAI_MONTHLY_COST_CAP_USD set |
| F-1.8.9 | Chat UI widget (reusable component) | REQ-1.6.9 | DONE | chat.html |
| F-1.8.10 | Session management (new/continue/history) | REQ-1.6.10 | DONE | |
| F-1.8.11 | Content safety (moderation API) | REQ-1.6.11 | DONE | `ModerationLog` |
| F-1.8.12 | Chat in course context (lesson-aware prompts) | REQ-1.6.12 | DONE | |

---

### SPR-1.9 — Email Service (Resend)

**Goal:** Wire Resend email backend for production, enable forgot-password flow.
**Status:** DONE ✅ — 12/12 tests pass. **Verified live 2026-06-09:** prod password-reset email delivered to inbox via Resend (anymail backend). Prior gaps A/B RESOLVED.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.9.1 | Resend backend wired in settings (anymail) | REQ-1.2.2 | DONE | `anymail.backends.resend.EmailBackend` (was broken `django_resend` ref; fixed commit 4e8fc77) |
| F-1.9.2 | `RESEND_API_KEY` env var + prod switch | REQ-1.2.2 | DONE | Set on Render; dev = console |
| F-1.9.3 | Forgot password / reset password flow | REQ-1.1.3 | DONE | allauth reset live; email delivered |
| F-1.9.4 | Email addresses (`noreply@`, `support@`, `privacy@`) | REQ-1.2.2 | DONE | noreply@babook.co.il sending verified; support@/privacy@ per ACT-22 |

---

### SPR-1.10 — Database Backups

**Goal:** Nightly automated backup of `db.sqlite3` + media to cloud storage.
**Status:** WIP — 9/9 tests pass; `backup_db` command implemented (GCS-based, env `GCS_BUCKET`/`GCS_SERVICE_ACCOUNT`). **Nightly scheduling not yet wired** (no cron/Render job) — pending ACT-3 / a scheduler decision.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.10.1 | `backup_db` management command (dry-run + live) | REQ-1.2.4 | DONE | Command works; 9/9 tests |
| F-1.10.2 | Cloud target configured (GCS bucket) | REQ-1.2.4 | WIP | `babook-backups-490715` referenced; verify creds + run |
| F-1.10.3 | Media + video catalog included in backup | REQ-1.2.4 | DONE | `--skip-media` flag; catalog JSON |
| F-1.10.4 | Nightly schedule (Render cron / scheduler) | REQ-1.2.4 | TODO | Not yet scheduled |
| F-1.10.5 | Backup restore BKM (cloud restore steps) | REQ-1.2.18 | WIP | `backup_restore.md` exists; confirm cloud restore steps |

---

## EPIC-2 — Corporate Landing & First Course

**Goal:** Paying corporate customers can find the site, sign up, and watch the first real course.
**Spec:** [main_spec.md §Chapter 2](main_spec.md) — back-filled 2026-06-09 (REQ-2.3 through REQ-2.8).
**Owner:** Avi + Copilot
**Status:** DONE ✅ — all sprints pass (274/274) and are live on prod. Chapter 2 spec written and every feature now traces to a real `REQ-2.x` ID.

Sprints in this epic:
- SPR-2.0.1 Design System Foundation — DONE
- SPR-2.1.1 Corporate Page: Conversion MVP — DONE
- SPR-2.1.3 Newsletter Capture MVP — DONE
- SPR-2.1.4 Corporate Page: Accessibility & Mobile Polish — DONE
- SPR-2.2 First Flagship Course — DONE
- SPR-2.3 Remote Course Management API — DONE

---

### SPR-2.3 — Remote Course Management API

**Goal:** Push courses (videos, materials, media files) from local dev to production via a secure REST API.
**Status:** DONE ✅ — used in production to publish the `micropython-thonny` course.

| Feature ID | Title | Status | Notes |
|---|---|---|---|
| F-2.3.1 | Token auth (`COURSE_MGMT_API_KEY`, Bearer header) | DONE | `require_api_key` in course_api.py |
| F-2.3.2 | `GET /api/v1/courses/` — list all courses | DONE | |
| F-2.3.3 | `POST /api/v1/courses/sync/` — upsert course + videos + materials + quiz | DONE | Idempotent; quiz sync semantics documented (commit c2ff533) |
| F-2.3.4 | `POST /api/v1/media/upload/` — upload file to persistent disk | DONE | |
| F-2.3.5 | `push_course_to_production` management command | DONE | Local CLI → prod |

---

### SPR-2.0.1 — Design System Foundation

**Goal:** CSS custom properties (dark theme), typography, spacing tokens, card surface, sticky WhatsApp CTA.
**Status:** DONE ✅ — 17/17 tests pass. Design tokens, Google Fonts, spacing, `.card-surface`, `.whatsapp-sticky` all present.

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-2.0.1 | CSS custom properties (color palette, dark theme) | REQ-2.3.1 | DONE |
| F-2.0.2 | Google Fonts loaded with `display=swap` | REQ-2.3.2 | DONE |
| F-2.0.3 | CSS font-family + spacing variables | REQ-2.3.3 | DONE |
| F-2.0.4 | Max content width (1200px) | REQ-2.3.4 | DONE |
| F-2.0.5 | `.card-surface` component class | REQ-2.3.5 | DONE |
| F-2.0.6 | `.whatsapp-sticky` component class | REQ-2.3.6 | DONE |
| F-2.0.7 | `body` uses `--bg-primary` token | REQ-2.3.7 | DONE |

---

### SPR-2.1.1 — Corporate Page: Conversion MVP

**Goal:** `/corporate/` landing page — hero, service tiers, FAQ, contact form with lead capture.
**Status:** DONE ✅ — 17/17 tests pass. `/corporate/` live on prod (200).

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-2.1.1 | `/corporate/` route + anonymous access | REQ-2.4.1 | DONE |
| F-2.1.2 | SEO meta + canonical + sitemap entry | REQ-2.4.2 | DONE |
| F-2.1.3 | Static hero asset | REQ-2.4.3 | DONE |
| F-2.1.4 | Hero section (photo + copy + CTAs) | REQ-2.4.3 | DONE |
| F-2.1.5 | Service tier cards (workshop, bootcamp, keynote) | REQ-2.4.4 | DONE |
| F-2.1.6 | FAQ accordion | REQ-2.4.5 | DONE |
| F-2.1.7 | Contact form (lead capture) → `CorporateLead` model | REQ-2.4.6 | DONE |
| F-2.1.8 | Honeypot spam protection | REQ-2.4.7 | DONE |
| F-2.1.9 | Rate limiting on form submit | REQ-2.4.7 | DONE |
| F-2.1.10 | WhatsApp CTAs with env-driven phone number | REQ-2.4.8 | DONE |
| F-2.1.11 | UTM param capture + Plausible events | REQ-2.4.9 | DONE |
| F-2.1.12 | Accessibility baseline (ARIA, labels) | REQ-2.6.1 | DONE |
| F-2.1.13 | Mobile-responsive classes | REQ-2.6.4 | DONE |
| F-2.1.14 | CSRF enforced on AJAX submit | REQ-2.4.10 | DONE |
| F-2.1.15 | Input sanitization (HTML strip + length limits) | REQ-2.4.10 | DONE |

---

### SPR-2.1.3 — Newsletter Capture MVP

**Goal:** Newsletter signup on corporate page with double opt-in, rate limiting, and purge command.
**Status:** DONE ✅ — 7/7 tests pass. `/newsletter/signup/` wired (POST-only; GET → 405).

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-2.1.28 | `/newsletter/signup/` endpoint + `NewsletterSubscriber` model | REQ-2.5.1 | DONE |
| F-2.1.29 | Lowercase email storage + double opt-in email | REQ-2.5.2 | DONE |
| F-2.1.30 | Newsletter component rendered once on `/corporate/` | REQ-2.5.3 | DONE |
| F-2.1.31 | Confirmation token flow + `confirmed_at` | REQ-2.5.2 | DONE |
| F-2.1.32 | `purge_unconfirmed_subscribers` management command | REQ-2.5.4 | DONE |

---

### SPR-2.1.4 — Corporate Page: Accessibility & Mobile Polish

**Goal:** WCAG accessibility pass, mobile layout fixes, hero image, Bootstrap grid, RTL mirror.
**Status:** DONE ✅ — 32/32 tests pass.

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-2.1.33 | Skip-to-content link | REQ-2.6.1 | DONE |
| F-2.1.34 | `:focus-visible` CSS styles | REQ-2.6.1 | DONE |
| F-2.1.35 | Heading hierarchy (H1→H2→H3) | REQ-2.6.1 | DONE |
| F-2.1.36 | Section `aria-label` attributes | REQ-2.6.1 | DONE |
| F-2.1.37 | Form status `aria-live` region | REQ-2.6.2 | DONE |
| F-2.1.38 | `prefers-reduced-motion` CSS | REQ-2.6.3 | DONE |
| F-2.1.39 | Hero photo 200px on mobile CSS | REQ-2.6.4 | DONE |
| F-2.1.40 | Hero photo explicit `width`/`height` attrs | REQ-2.6.4 | DONE |
| F-2.1.41 | CTA stack column on mobile | REQ-2.6.4 | DONE |
| F-2.1.42 | Tier cards full-width on mobile | REQ-2.6.4 | DONE |
| F-2.1.43 | WhatsApp sticky z-index + 48px mobile | REQ-2.6.5 | DONE |
| F-2.1.44 | Hero image asset | REQ-2.6.4 | DONE |
| F-2.1.45 | Bootstrap grid on corporate page | REQ-2.6.4 | DONE |
| F-2.1.46 | RTL WhatsApp sticky mirrored position | REQ-2.6.5 | DONE |
| F-2.1.47 | Message field `maxlength` attribute | REQ-2.4.10 | DONE |

---

### SPR-2.2 — First Flagship Course

**Goal:** Full course (`micropython-thonny`) published end-to-end: catalog, detail page, enrollment, lesson player, completion.
**Status:** DONE ✅ — 25/25 tests pass. Course **live on prod** (`/courses/micropython-thonny/` + lessons 200).

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.2.1 | Course model enhancements (category, difficulty, thumbnail, title_en, is_published) | REQ-2.7.1 | DONE | Migration 0010 |
| F-2.2.2 | `Enrollment` model | REQ-2.7.2 | DONE | Migration 0010 |
| F-2.2.3 | Course catalog page (`/courses/`) | REQ-2.7.3 | DONE | Live (200) |
| F-2.2.4 | Course detail page (`/courses/<slug>/`) | REQ-2.7.4 | DONE | Live |
| F-2.2.5 | Enrollment flow | REQ-2.7.2 | DONE | |
| F-2.2.6 | Lesson page with video player | REQ-2.7.5 | DONE | Sidebar + player |
| F-2.2.7 | Course completion (quizzes passed) | REQ-2.7.6 | DONE | |
| F-2.2.8 | Course SEO + sitemap entries | REQ-2.7.7 | DONE | |
| F-2.2.9 | Corporate funnel hook from course detail | REQ-2.7.8 | DONE | Link to /corporate/ |
| F-2.2.10 | `load_course_from_manifest` management command | REQ-2.7.9 | DONE | |
| F-2.2.11 | Course materials (files + links per course) | REQ-2.7.10 | DONE | `CourseMaterial` (migration 0013) |
| F-2.2.12 | Sticky navbar (always visible on scroll) | REQ-1.1.1 | DONE | `sticky-top` in base.html |
| F-2.2.13 | Certificates listed on user profile page | REQ-1.1.6 | DONE | `CourseCertificate` on profile |
| F-2.2.14 | Lesson quizzes (`LessonQuiz`, requires_correct) | REQ-1.3.13 | DONE | Quiz gating; sync-aware (commit c2ff533) |

---

## EPIC-3 — Training Platform & Course Library

**Goal:** A structured, navigable course library (Domain → Track → Course) with
experiential lessons and faithful notes, scaling beyond the single first course.
**Spec:** [main_spec.md §Chapter 3](main_spec.md) — back-filled 2026-06-12 (REQ-3.1–3.8).
**Owner:** Avi + Claude
**Status:** DONE ✅ — live on prod; tests in `tests/test_spr_3_1.py`.

Sprints in this epic:
- SPR-3.1 Taxonomy & Drill-down Catalog — DONE
- SPR-3.2 Intros & Cross-listing — DONE
- SPR-3.3 Experiential Lessons (Reflection) — DONE
- SPR-3.4 Content Sync & Quality — DONE

### SPR-3.1 — Taxonomy & Drill-down Catalog

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-3.1.1 | `Course.domain` + `Course.track` fields (migration 0014) | REQ-3.1.1 | DONE |
| F-3.1.2 | `TRAINING_TAXONOMY` (domains/tracks metadata) | REQ-3.1.2 | DONE |
| F-3.1.3 | `build_catalog()` Domain→Track→Course grouping | REQ-3.1.3 | DONE |
| F-3.1.4 | L0 domains page `/courses/` | REQ-3.2.1 | DONE |
| F-3.1.5 | L1 tracks page `/courses/topic/<domain>/` | REQ-3.2.2 | DONE |
| F-3.1.6 | L2 leaves page `/courses/topic/<domain>/<track>/` | REQ-3.2.3 | DONE |
| F-3.1.7 | Breadcrumbs + coming-soon empties | REQ-3.2.4 | DONE |

### SPR-3.2 — Intros & Cross-listing

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-3.2.1 | Per-level intro cards (`intro_row`/`intro_slug`) | REQ-3.3.1 | DONE |
| F-3.2.2 | Cross-listing via `extra_slugs` | REQ-3.4.1 | DONE |

### SPR-3.3 — Experiential Lessons (Reflection)

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-3.3.1 | `reflection_prompt` + `LessonReflection` (migration 0015) | REQ-3.5.1 | DONE |
| F-3.3.2 | Reflection endpoint + lesson completion | REQ-3.5.2 | DONE |
| F-3.3.3 | Admin-only reflections; profile courses + completion % | REQ-3.5.3 | DONE |
| F-3.3.4 | Video-optional (text-only) lessons | REQ-3.5.4 | DONE |

### SPR-3.4 — Content Sync & Quality

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-3.4.1 | Extended sync fields + lesson deletion on push | REQ-3.6.1 | DONE |
| F-3.4.2 | gzip+base64 WAF-safe payload | REQ-3.6.2 | DONE |
| F-3.4.3 | Homepage worlds + slim hero + placeholder pages | REQ-3.7.1 | DONE |
| F-3.4.4 | Faithful, em-dash-free notes; fenced code; HTML tables | REQ-3.8.1, REQ-3.8.2 | DONE |

---

## EPIC-4 — Course Authoring Studio

**Goal:** Self-serve, in-product course creation: a manual editor (full CRUD) and
an automated video → draft-course pipeline, for Avi and authorized authors.
**Spec:** [main_spec.md §Chapter 4](main_spec.md) (REQ-4.1–4.3).
**Owner:** Avi + Claude
**Status:** DONE ✅ — tests in tests/test_spr_4_1.py (15 tests)

Sprints in this epic:
- SPR-4.1 Access & Studio Shell — DONE
- SPR-4.2 Manual Authoring (CRUD) — DONE
- SPR-4.3 Automated Pipeline (video → course) — DONE

### SPR-4.1 — Access & Studio Shell

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-4.1.1 | `UserProfile.is_author` + `@author_required` guard | REQ-4.1.1 | DONE |
| F-4.1.2 | `/studio/` course list + create/delete + nav link | REQ-4.1.2 | DONE |

### SPR-4.2 — Manual Authoring (CRUD)

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-4.2.1 | Create / edit course metadata | REQ-4.2.1 | DONE |
| F-4.2.2 | Delete course | REQ-4.2.2 | DONE |
| F-4.2.3 | Lesson create / edit / delete | REQ-4.2.3 | DONE |
| F-4.2.4 | Markdown editor + live preview | REQ-4.2.4 | DONE |
| F-4.2.5 | Reorder lessons | REQ-4.2.5 | DONE |
| F-4.2.6 | Publish / unpublish | REQ-4.2.6 | DONE |

### SPR-4.3 — Automated Pipeline (video → course)

| Feature ID | Title | REQ trace | Status |
|---|---|---|---|
| F-4.3.1 | New-from-video wizard (YouTube URL / upload) | REQ-4.3.1 | DONE |
| F-4.3.2 | `AuthoringJob` model | REQ-4.3.2 | DONE |
| F-4.3.3 | `app/authoring/` pipeline (download→transcribe→topics→split→Bunny→notes) | REQ-4.3.3 | DONE |
| F-4.3.4 | Background runner + live progress polling | REQ-4.3.4 | DONE |
| F-4.3.5 | Editable draft result | REQ-4.3.5 | DONE |
| F-4.3.6 | `run_authoring_jobs` worker command | REQ-4.3.6 | DONE |

---

## Status Summary (reconciled 2026-06-09)

**Full regression: 274/274 passing.** Per-sprint test counts: 1.1=19, 1.2=17,
1.3=15, 1.4=21, 1.5=17, 1.6=26, 1.7=13, 1.8=27, 1.9=12, 2.0.1=17, 2.1.1=17,
2.1.3=7, 2.1.4=32, 2.2=25.

**DONE & live:** SPR-1.1, 1.2, 1.3, 1.4, 1.7, 1.8, 1.9, 2.0.1, 2.1.1, 2.1.3,
2.1.4, 2.2, 2.3.

**Code DONE, external activation pending Avi:**
| Sprint | What's left | Blocking ACT |
|---|---|---|
| SPR-1.5 | Stripe Checkout/webhooks/invoicing (DEFERRED) | ACT-10, ACT-11, ACT-13 |
| SPR-1.6 | Live GitHub org + Copilot Business activation | ACT-14, ACT-15, ACT-16 (+17, 18) |
| SPR-1.10 | Nightly backup schedule + verify cloud target/restore | ACT-3 |

**Tracking debt:** None outstanding — Chapter 2 of [main_spec.md](main_spec.md)
was back-filled 2026-06-09 (REQ-2.3–2.8) and every EPIC-2 feature now traces to a
real `REQ-2.x` ID.

---

## Avi action items (mirror of spec §1.9)

| ACT | Title | Blocks | Status |
|---|---|---|---|
| ACT-1 | Sign up Resend, share API key | F-1.2.1 | DONE |
| ACT-2 | SPF/DKIM DNS records for babook.co.il | F-1.2.1 | DONE (mail delivering) |
| ACT-3 | Set up backup target + nightly schedule (DEC-18 / GCS) | F-1.7.3, F-1.10.4 | OPEN |
| ACT-4 | Approve AI logo or provide own | F-1.3.4 | DONE |
| ACT-5 | Plausible account + site ID | F-1.3.9 | OPEN (optional) |
| ACT-6 | Confirm Render persistent disk at `/var/data/` | F-1.1.2, F-1.1.8 | DONE |
| ACT-7 | Review draft privacy + terms text | F-1.3.8 | OPEN |
| ACT-8 | Confirm Google OAuth redirect URI on prod | F-1.2.2 | DONE |
| ACT-9 | ~~Bunny.net account + Stream library + API key~~ **DONE** | F-1.4.1 | DONE |
| ACT-10 | Stripe account (Israel) + keys | F-1.5.1 | OPEN |
| ACT-11 | Green Invoice account + API key | F-1.5.9 | OPEN |
| ACT-12 | Confirm עוסק status (מורשה/פטור) | F-1.5.9, F-1.5.11 | DEC-17: פטור |
| ACT-13 | Decide initial pricing (ILS) | F-1.5.2 | OPEN |
| ACT-14 | Create/identify GitHub org for Copilot | F-1.6.1 | OPEN |
| ACT-15 | Activate Copilot Business on org | F-1.6.1 | OPEN |
| ACT-16 | Generate org PAT / GitHub App with `manage_billing:copilot` | F-1.6.1 | OPEN |
| ACT-17 | Confirm pricing for Copilot tier (≥ ₪149/mo) | F-1.6.3 | OPEN |
| ACT-18 | Configure Copilot org policies in GitHub UI | F-1.6.12 | OPEN |
| ACT-19 | OpenAI API account + key | F-1.8.1 | DONE |
| ACT-20 | Set token-rate limits per tier (daily caps) | F-1.8.6 | OPEN (tune) |
| ACT-21 | Set monthly cost cap amount (USD) | F-1.8.8 | DONE ($50) |
| ACT-22 | Email addresses on babook.co.il (`privacy@`, `support@`, `noreply@`) | F-1.2.1, F-1.3.8 | noreply DONE; others OPEN |

---

## Counters (auto-rendered by [dashboard.html](dashboard.html))

<!-- The dashboard parses this file. Keep the table format above stable. -->
