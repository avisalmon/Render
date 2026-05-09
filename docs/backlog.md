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

---

### SPR-1.1 — Foundations

**Goal:** Project skeleton, settings, security, error pages, health, logging.
**Status:** DONE

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
**Status:** DONE

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
**Status:** DONE

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
**Status:** TODO

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.4.1 | Bunny Stream account + library + env keys | REQ-1.3.1 | TODO | Depends on ACT-9 |
| F-1.4.2 | `Video` model + admin registration | REQ-1.3.2, REQ-1.3.8 | TODO | |
| F-1.4.3 | Embedded responsive Bunny player | REQ-1.3.3 | TODO | |
| F-1.4.4 | Signed playback URL generation | REQ-1.3.4 | TODO | |
| F-1.4.5 | `UserVideoProgress` model + heartbeat endpoint | REQ-1.3.5 | TODO | |
| F-1.4.6 | Resume playback from `last_position` | REQ-1.3.6 | TODO | |
| F-1.4.7 | Course progress aggregation (% complete) | REQ-1.3.7 | TODO | |
| F-1.4.8 | Free preview gating (`is_free_preview`) | REQ-1.3.9 | TODO | |

---

### SPR-1.5 — Billing (Stripe + Green Invoice)

**Goal:** Subscription + per-course payment, Israeli VAT-compliant invoices, refunds.
**Status:** TODO

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.5.1 | Stripe account (Israel) + `dj-stripe` integration | REQ-1.4.1 | TODO | Depends on ACT-10 |
| F-1.5.2 | Pricing model (subscription + one-time, free preview) | REQ-1.4.2 | TODO | Depends on ACT-13 |
| F-1.5.3 | Multi-currency (ILS + USD) | REQ-1.4.3 | TODO | |
| F-1.5.4 | Stripe Checkout integration (`/pricing/`) | REQ-1.4.4, REQ-1.4.12 | TODO | |
| F-1.5.5 | Stripe webhook handler + signature verify | REQ-1.4.5 | TODO | |
| F-1.5.6 | `Entitlement` model + access checks | REQ-1.4.6 | TODO | Used by F-1.4.4 |
| F-1.5.7 | Stripe Customer Portal link from profile | REQ-1.4.7 | TODO | |
| F-1.5.8 | Coupons & 7-day trial support | REQ-1.4.8 | TODO | |
| F-1.5.9 | Green Invoice integration (חשבונית מס auto-issue) | REQ-1.4.9 | TODO | Depends on ACT-11, ACT-12 |
| F-1.5.10 | Refund flow + חשבונית זיכוי | REQ-1.4.10 | TODO | |
| F-1.5.11 | VAT handling (17% מע"מ for Israeli buyers) | REQ-1.4.11 | TODO | Depends on ACT-12 |

---

### SPR-1.6 — Copilot Seat Provisioning

**Goal:** Subscribers on the Copilot tier get auto-invited to GitHub org and assigned Copilot Business seats.
**Status:** TODO

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.6.1 | GitHub org + Copilot Business activated | REQ-1.5.1 | TODO | Depends on ACT-14, ACT-15, ACT-16 |
| F-1.6.2 | GitHub username on user (via OAuth or manual) | REQ-1.5.2 | TODO | Depends on F-1.2.3 |
| F-1.6.3 | Copilot-included subscription tier flag | REQ-1.5.3 | TODO | Depends on ACT-17 |
| F-1.6.4 | Auto-invite to org on subscribe | REQ-1.5.4 | TODO | |
| F-1.6.5 | Auto-assign Copilot seat on accept | REQ-1.5.5 | TODO | |
| F-1.6.6 | Auto-revoke seat on churn (+14d org removal) | REQ-1.5.6 | TODO | |
| F-1.6.7 | Inactivity reclamation (30d warn / 60d reclaim) | REQ-1.5.7 | TODO | |
| F-1.6.8 | Admin Copilot dashboard | REQ-1.5.8 | TODO | |
| F-1.6.9 | Seat cap enforcement (`COPILOT_MAX_SEATS`) | REQ-1.5.9 | TODO | |
| F-1.6.10 | User-facing seat status on profile | REQ-1.5.10 | TODO | |
| F-1.6.11 | Audit log of all seat events | REQ-1.5.11 | TODO | |
| F-1.6.12 | Org-level Copilot policy doc | REQ-1.5.12 | TODO | Depends on ACT-18 |

---

### SPR-1.7 — Ops, Quality & BKMs

**Goal:** Tests, code quality, backups, rollback, CI/CD, all BKM docs.
**Status:** TODO

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.7.1 | pytest-django setup + first tests | REQ-1.2.16 | TODO | |
| F-1.7.2 | black + ruff + pre-commit hooks | REQ-1.2.17 | TODO | |
| F-1.7.3 | Nightly DB backup to GitHub private repo | REQ-1.2.4 | TODO | Depends on ACT-3 |
| F-1.7.4 | `docs/procedures/backup_restore.md` BKM | REQ-1.2.18 | TODO | |
| F-1.7.5 | `docs/procedures/rollback.md` BKM | REQ-1.2.19 | TODO | |
| F-1.7.6 | `docs/procedures/cicd.md` BKM | REQ-1.1.10 | TODO | |
| F-1.7.7 | `docs/procedures/env_vars.md` BKM | REQ-1.2.3 | TODO | |
| F-1.7.8 | `docs/architecture/roles.md` | REQ-1.2.8 | TODO | |
| F-1.7.9 | `docs/procedures/copilot_policy.md` | REQ-1.5.12 | TODO | |

---

### SPR-1.8 — AI Chat (OpenAI)

**Goal:** Streaming AI chat with context-aware tutoring, rate limiting, usage tracking, cost safety.
**Status:** TODO

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.8.1 | OpenAI API integration + health check | REQ-1.6.1 | TODO | Depends on ACT-19 |
| F-1.8.2 | Chat endpoint with SSE streaming | REQ-1.6.2 | TODO | |
| F-1.8.3 | `ChatSession` + `ChatMessage` models | REQ-1.6.3 | TODO | |
| F-1.8.4 | Context-aware system prompts (admin-editable) | REQ-1.6.4 | TODO | |
| F-1.8.5 | Model selection by tier (4o-mini / 4o) | REQ-1.6.5 | TODO | |
| F-1.8.6 | Per-user daily token rate limiting | REQ-1.6.6 | TODO | Depends on ACT-20 |
| F-1.8.7 | Usage tracking + admin cost dashboard | REQ-1.6.7 | TODO | |
| F-1.8.8 | Monthly cost cap safety switch | REQ-1.6.8 | TODO | Depends on ACT-21 |
| F-1.8.9 | Chat UI widget (reusable component) | REQ-1.6.9 | TODO | |
| F-1.8.10 | Session management (new/continue/history) | REQ-1.6.10 | TODO | |
| F-1.8.11 | Content safety (moderation API) | REQ-1.6.11 | TODO | |
| F-1.8.12 | Chat in course context (lesson-aware prompts) | REQ-1.6.12 | TODO | |

---

## Avi action items (mirror of spec §1.8)

| ACT | Title | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, share API key | F-1.2.1 |
| ACT-2 | SPF/DKIM DNS records for babook.co.il | F-1.2.1 |
| ACT-3 | GitHub private `babook-backups` repo + deploy key | F-1.7.3 |
| ACT-4 | Approve AI logo or provide own | F-1.3.4 |
| ACT-5 | Plausible account + site ID | F-1.3.9 |
| ACT-6 | Confirm Render persistent disk at `/var/data/` | F-1.1.2, F-1.1.8 |
| ACT-7 | Review draft privacy + terms text | F-1.3.8 |
| ACT-8 | Confirm Google OAuth redirect URI on prod | F-1.2.2 |
| ACT-9 | Bunny.net account + Stream library + API key | F-1.4.1 |
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
