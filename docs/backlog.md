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
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.4.1 | Bunny Stream account + library + env keys | REQ-1.3.1 | DONE | ACT-9 complete; 4 env vars wired via os.environ.get() |
| F-1.4.2 | `Video` model + `Course` model + admin registration | REQ-1.3.2, REQ-1.3.8 | DONE | Course + Video + UserVideoProgress models; all in admin |
| F-1.4.3 | Embedded responsive Bunny player | REQ-1.3.3 | DONE | iframe.mediadelivery.net embed, 16:9 responsive |
| F-1.4.4 | Signed playback URL generation | REQ-1.3.4 | DONE | SHA256 token auth, 24h expiry; app/bunny.py |
| F-1.4.5 | `UserVideoProgress` model + heartbeat endpoint | REQ-1.3.5 | DONE | POST /api/video-progress/ with JSON body |
| F-1.4.6 | Resume playback from `last_position` | REQ-1.3.6 | DONE | last_position_seconds in template context + JS var |
| F-1.4.7 | Course progress aggregation (% complete) | REQ-1.3.7 | DONE | /course/<slug>/ shows %, complete badge at 95% threshold |
| F-1.4.8 | Free preview gating (`is_free_preview`) | REQ-1.3.9 | DONE | Anonymous→login redirect; logged-in without entitlement→403 |

---

### SPR-1.5 — Billing (Mock Mode)

**Goal:** Users choose Free / Base / Master tier at ₪0; access gating enforced. Real Stripe deferred.
**Status:** DONE (mock mode)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.5.1 | Stripe account (Israel) + `dj-stripe` integration | REQ-1.4.1 | DEFERRED | Real billing postponed |
| F-1.5.2 | Pricing model (Free / Base / Master tiers) | REQ-1.4.2 | DONE | Mock ₪0 — `/pricing/` page |
| F-1.5.3 | Multi-currency (ILS + USD) | REQ-1.4.3 | DEFERRED | Real billing postponed |
| F-1.5.4 | Stripe Checkout integration (`/pricing/`) | REQ-1.4.4, REQ-1.4.12 | DEFERRED | Real billing postponed |
| F-1.5.5 | Stripe webhook handler + signature verify | REQ-1.4.5 | DEFERRED | Real billing postponed |
| F-1.5.6 | `Entitlement` model + access checks | REQ-1.4.6 | DONE | Tier gating on video + copilot |
| F-1.5.7 | Stripe Customer Portal link from profile | REQ-1.4.7 | DEFERRED | Real billing postponed |
| F-1.5.8 | Coupons & 7-day trial support | REQ-1.4.8 | DEFERRED | Real billing postponed |
| F-1.5.9 | Green Invoice integration (חשבונית מס auto-issue) | REQ-1.4.9 | DEFERRED | Real billing postponed |
| F-1.5.10 | Refund flow + חשבונית זיכוי | REQ-1.4.10 | DEFERRED | Real billing postponed |
| F-1.5.11 | VAT handling (17% מע"מ for Israeli buyers) | REQ-1.4.11 | DEFERRED | עוסק פטור — no VAT (DEC-17) |

---

### SPR-1.6 — Copilot Seat Provisioning

**Goal:** Subscribers on the Copilot tier get auto-invited to GitHub org and assigned Copilot Business seats.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.6.1 | GitHub org + Copilot Business activated | REQ-1.5.1 | DONE | Org `babook-learn` created; settings stubbed; ACT-15/16 pending June 1 |
| F-1.6.2 | GitHub username on user (via OAuth or manual) | REQ-1.5.2 | DONE | github_username field on UserProfile |
| F-1.6.3 | Copilot-included subscription tier flag | REQ-1.5.3 | DONE | CopilotSeat model with status choices |
| F-1.6.4 | Auto-invite to org on subscribe | REQ-1.5.4 | DONE | app/copilot.py invite_to_org() — stubbed API |
| F-1.6.5 | Auto-assign Copilot seat on accept | REQ-1.5.5 | DONE | app/copilot.py assign_copilot_seat() — stubbed API |
| F-1.6.6 | Auto-revoke seat on churn (+14d org removal) | REQ-1.5.6 | DONE | app/copilot.py revoke_copilot_seat() — stubbed API |
| F-1.6.7 | Inactivity reclamation (30d warn / 60d reclaim) | REQ-1.5.7 | DONE | app/copilot.py check_inactivity() |
| F-1.6.8 | Admin Copilot dashboard | REQ-1.5.8 | DONE | /staff/copilot-dashboard/ — seats, cost, status |
| F-1.6.9 | Seat cap enforcement (`COPILOT_MAX_SEATS`) | REQ-1.5.9 | DONE | Waitlist when cap reached |
| F-1.6.10 | User-facing seat status on profile | REQ-1.5.10 | DONE | copilot_status in profile context |
| F-1.6.11 | Audit log of all seat events | REQ-1.5.11 | DONE | SeatEvent model with actor/reason/api_response |
| F-1.6.12 | Org-level Copilot policy doc | REQ-1.5.12 | DONE | docs/procedures/copilot_policy.md |

---

### SPR-1.7 — Ops, Quality & BKMs

**Goal:** Tests, code quality, backups, rollback, CI/CD, all BKM docs.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.7.1 | pytest-django setup + first tests | REQ-1.2.16 | DONE | 82 tests across 5 sprints |
| F-1.7.2 | black + ruff + pre-commit hooks | REQ-1.2.17 | DONE | pyproject.toml + .pre-commit-config.yaml |
| F-1.7.3 | Nightly DB backup to Google Drive | REQ-1.2.4 | DEFERRED | Moved to SPR-1.10 |
| F-1.7.4 | `docs/procedures/backup_restore.md` BKM | REQ-1.2.18 | DONE | Google Drive via rclone |
| F-1.7.5 | `docs/procedures/rollback.md` BKM | REQ-1.2.19 | DONE | Revert/redeploy/force-push |
| F-1.7.6 | `docs/procedures/cicd.md` BKM | REQ-1.1.10 | DONE | Full local+deploy workflow |
| F-1.7.7 | `docs/procedures/env_vars.md` BKM | REQ-1.2.3 | DONE | All vars documented |
| F-1.7.8 | `docs/architecture/roles.md` | REQ-1.2.8 | DONE | admin/staff/member/guest |
| F-1.7.9 | `docs/procedures/copilot_policy.md` | REQ-1.5.12 | DEFERRED | Depends on ACT-18 |

---

### SPR-1.8 — AI Chat (OpenAI)

**Goal:** Streaming AI chat with context-aware tutoring, rate limiting, usage tracking, cost safety.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.8.1 | OpenAI API integration + health check | REQ-1.6.1 | DONE | Settings wired; stub mode when no key |
| F-1.8.2 | Chat endpoint with SSE streaming | REQ-1.6.2 | DONE | POST /api/chat/ with JSON; streaming deferred |
| F-1.8.3 | `ChatSession` + `ChatMessage` models | REQ-1.6.3 | DONE | Full history per session |
| F-1.8.4 | Context-aware system prompts (admin-editable) | REQ-1.6.4 | DONE | SystemPrompt model in admin |
| F-1.8.5 | Model selection by tier (4o-mini / 4o) | REQ-1.6.5 | DONE | OPENAI_DEFAULT_MODEL / OPENAI_PREMIUM_MODEL |
| F-1.8.6 | Per-user daily token rate limiting | REQ-1.6.6 | DONE | OPENAI_DAILY_TOKEN_LIMITS by role |
| F-1.8.7 | Usage tracking + admin cost dashboard | REQ-1.6.7 | DONE | UsageLog model + /staff/ai-usage/ |
| F-1.8.8 | Monthly cost cap safety switch | REQ-1.6.8 | DONE | OPENAI_MONTHLY_COST_CAP_USD; blocks chat at cap |
| F-1.8.9 | Chat UI widget (reusable component) | REQ-1.6.9 | DONE | /chat/ page with JS widget |
| F-1.8.10 | Session management (new/continue/history) | REQ-1.6.10 | DONE | /api/chat/sessions/ GET+POST |
| F-1.8.11 | Content safety (moderation API) | REQ-1.6.11 | DONE | ModerationLog model; flagged = rejected |
| F-1.8.12 | Chat in course context (lesson-aware prompts) | REQ-1.6.12 | DONE | course_slug param injects course metadata |

---

### SPR-1.9 — Email Service (Resend)

**Goal:** Transactional email working on prod via Resend. Password reset, notifications, and all Django `send_mail()` calls delivered to real inboxes.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.9.1 | `django-anymail[resend]` backend wired in settings | REQ-1.2.2 | DONE | anymail + Resend; console in dev, Resend in prod |
| F-1.9.2 | `RESEND_API_KEY` + `DEFAULT_FROM_EMAIL` env vars | REQ-1.2.2, REQ-1.2.3 | DONE | Local + Render env var set |
| F-1.9.3 | Forgot-password / reset-password flow works | REQ-1.1.3 | DONE | allauth templates + styled pages |
| F-1.9.4 | Email verification on signup (optional) | REQ-1.1.3 | DONE | ACCOUNT_EMAIL_VERIFICATION = "none" (configurable) |
| F-1.9.5 | Admin can test-send from Django shell | REQ-1.2.2 | DONE | Tested: delivers to Gmail + Intel inboxes |
| F-1.9.6 | SPF/DKIM DNS records for `babook.co.il` | REQ-1.2.2 | DONE | DNS moved to Cloudflare; fully verified |

---

### SPR-1.10 — Database Backups

**Goal:** Nightly automated backup of `db.sqlite3` to Google Drive via rclone. Documented restore procedure. Last 30 backups retained.
**Status:** BLOCKED (code ready; ACT-3 pending for Avi to configure rclone token)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.10.1 | rclone configured for Google Drive remote | REQ-1.2.4 | BLOCKED | ACT-3: Avi runs `rclone config`, base64-encodes, sets RCLONE_CONF on Render |
| F-1.10.2 | Backup management command | REQ-1.2.4 | DONE | `python manage.py backup_db` (WAL checkpoint + upload + retention) |
| F-1.10.3 | Render cron job (03:00 UTC) | REQ-1.2.4 | DONE | `render.yaml` cron job defined |
| F-1.10.4 | Retention policy — keep last 30 backups | REQ-1.2.4 | DONE | `rclone delete --min-age 30d` in command |
| F-1.10.5 | Restore procedure documented | REQ-1.2.18 | DONE | `docs/procedures/backup_restore.md` complete |
| F-1.10.6 | Restore dry-run completed once | REQ-1.2.18 | BLOCKED | After ACT-3 — first real backup + restore test |

---

## Avi action items (mirror of spec §1.8)

| ACT | Title | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, share API key | F-1.2.1 |
| ACT-2 | SPF/DKIM DNS records for babook.co.il | F-1.2.1 |
| ACT-3 | Configure Google Drive `rclone` token on Render (`RCLONE_CONF`) | F-1.10.1, F-1.10.6 |
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
