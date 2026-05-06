# Main Spec — Root Project

> Root specification for the babook.co.il project. Centered on AI training (video-based).
> All other docs (specs, procedures, decisions, architecture) branch from this file.
>
> **Requirement ID convention:** `REQ-<chapter>.<group>.<n>` — e.g. `REQ-1.2.3`.
> **Status values:** `TODO` / `IN PROGRESS` / `DONE` / `BLOCKED` / `DEFERRED`.
> **Decision IDs:** `DEC-<n>`. **Action items (Avi):** `ACT-<n>`.
> Every commit / PR addressing a requirement must reference its REQ-ID.

---

## Chapter 1 — Base Infrastructure

The foundation the project sits on. Must be in place before any feature work.

### 1.1 Core UI & Auth

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.1.1 | Base template | One `base.html` with header (logo + site name), main menu, content block, footer. All pages extend it. Renders identically on desktop and mobile. | TODO |
| REQ-1.1.2 | Google login / logout | Click "Login with Google" → OAuth flow → user logged in. Logout link clears session. Works in dev and prod. | TODO |
| REQ-1.1.3 | Password auth + forgot password | Signup, login, logout, change password, forgot-password (email reset link), reset password. Uses django-allauth. Depends on REQ-1.2.2. | TODO |
| REQ-1.1.4 | Static files | CSS/JS/images via WhiteNoise in prod, runserver in dev. `collectstatic` runs at deploy. No static 404s. | DONE |
| REQ-1.1.5 | Media files | User uploads stored on Render persistent disk at `/var/data/media/`. Survive deploys and restarts. | DONE |
| REQ-1.1.6 | User profile page | Logged-in user can view and edit: display name, avatar, email (read-only if from Google), bio, language preference. | TODO |
| REQ-1.1.7 | Bootstrap + CDN | Bootstrap 5 via CDN in `base.html`. Documented pattern for adding other free CDNs (jsDelivr, unpkg). | TODO |
| REQ-1.1.8 | Icon set | **Bootstrap Icons** loaded via CDN, available in all templates via `<i class="bi bi-...">`. | TODO |
| REQ-1.1.9 | Logo + favicon | Logo in header. Favicon set (16/32/180/192/512 + manifest + apple-touch-icon) wired in `<head>`. AI-learning themed. | TODO |
| REQ-1.1.10 | CI/CD documented | BKM `docs/procedures/cicd.md` covering: local dev setup, branch policy, commit conventions, deploy trigger, rollback, hotfix flow. | TODO |

### 1.2 Platform & Operations

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.2.1 | Custom error pages | Branded 404, 500, 403 templates extending `base.html`. Visible in prod (DEBUG=False). | DONE |
| REQ-1.2.2 | Email backend | Dev = console backend. Prod = **Resend** via env vars. Sender domain `babook.co.il` configured (SPF/DKIM). | TODO |
| REQ-1.2.3 | Env & secrets | All secrets via env vars. `.env` for local (gitignored). `settings_local.py` pattern. Render env vars list maintained in `docs/procedures/env_vars.md`. No secret in repo. | DONE |
| REQ-1.2.4 | Database backups | Nightly backup of `db.sqlite3` to **GitHub private repo** (`babook-backups`). Documented restore. Last 30 backups retained. | TODO |
| REQ-1.2.5 | Logging | Django `LOGGING`: console + rotating file handler. App logs INFO, security WARNING. Procedure for tailing Render logs documented. | DONE |
| REQ-1.2.6 | Security hardening | `SECURE_SSL_REDIRECT=True` in prod, HSTS, secure cookies, CSRF, `ALLOWED_HOSTS` correct, `DEBUG=False`. `manage.py check --deploy` clean. | DONE |
| REQ-1.2.7 | Django admin | `/admin/` superusers only. Documented procedure for creating a superuser on Render. Default Django admin UI for now. | TODO |
| REQ-1.2.8 | Roles & permissions | Roles: `admin`, `staff`, `member`, `guest`. Django groups + permission decorators. Documented in `docs/architecture/roles.md`. | TODO |
| REQ-1.2.9 | Responsive layout | All pages work ≥ 360px wide. Menu collapses to hamburger on mobile. | TODO |
| REQ-1.2.10 | Language / RTL | **Bilingual** (Hebrew default, English secondary). `dir="rtl"` toggle. Bootstrap RTL variant when `he`. `.po` files via Django i18n. | TODO |
| REQ-1.2.11 | Analytics | **Plausible** (privacy-friendly, GDPR-clean, no cookie banner needed for it). Loaded only in prod. | TODO |
| REQ-1.2.12 | Cookie / privacy notice | First-visit banner. `/privacy/` and `/terms/` pages. Consent stored in cookie. | TODO |
| REQ-1.2.13 | Favicon set | Generated multi-size set referenced in `base.html`. Webmanifest valid. | TODO |
| REQ-1.2.14 | SEO basics | `sitemap.xml`, `robots.txt`, per-page `<title>` + `<meta description>`, Open Graph tags. | TODO |
| REQ-1.2.15 | Health check | `GET /healthz` → 200 `{"status":"ok"}`. Configured as Render health check URL. | DONE |
| REQ-1.2.16 | Testing infra | `pytest-django` configured. `tests/` per app. `pytest` exits 0 locally and in CI. | TODO |
| REQ-1.2.17 | Code quality | `black` + `ruff` in `pyproject.toml`. **Pre-commit hook enabled** (auto-format on commit). | TODO |
| REQ-1.2.18 | Backup & restore BKM | `docs/procedures/backup_restore.md`: how backups work, where they live, how to restore on Render and locally. Test-restore done once and recorded. | TODO |
| REQ-1.2.19 | Rollback BKM | `docs/procedures/rollback.md`: revert bad deploy on Render (manual redeploy of previous commit, env var revert, DB restore if needed). | TODO |

### 1.3 Video Infrastructure (Bunny Stream)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.3.1 | Video host: Bunny Stream | All course videos uploaded to Bunny Stream library. API key + library ID stored as env vars. | TODO |
| REQ-1.3.2 | Video model | Django `Video` model: `bunny_video_id`, `title`, `duration_seconds`, `course_id`, `lesson_order`, `is_free_preview`. | TODO |
| REQ-1.3.3 | Embedded player | Bunny iframe player embedded in lesson page. Responsive 16:9. Hebrew/English captions when uploaded. | TODO |
| REQ-1.3.4 | Signed playback URLs | Paid videos use Bunny's token-authentication (signed URLs, expire in 24h). Only entitled users get a playable URL. | TODO |
| REQ-1.3.5 | Per-user progress | Model `UserVideoProgress`: `user`, `video`, `last_position_seconds`, `percent_watched`, `completed_at`. Updated via JS heartbeat every 15s. | TODO |
| REQ-1.3.6 | Resume playback | Player auto-seeks to `last_position_seconds` on next view. | TODO |
| REQ-1.3.7 | Course progress aggregation | Course detail page shows % completed across all lessons. Course marked complete when all videos ≥ 95% watched. | TODO |
| REQ-1.3.8 | Video upload admin flow | Admin can upload via Bunny dashboard, then register the `video_id` in Django admin. (Direct-upload from Django admin is deferred.) | TODO |
| REQ-1.3.9 | Free preview gating | `is_free_preview=True` videos playable by anonymous users. All others require login + entitlement. | TODO |

### 1.4 Billing Infrastructure (Stripe + Green Invoice)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.4.1 | Payment processor: Stripe | Stripe account in Israel mode. Test + live API keys in env vars. `dj-stripe` library integrated. | TODO |
| REQ-1.4.2 | Pricing model | **Subscription** (monthly + yearly) for full library access, plus optional **one-time** per-course purchase. Free preview lessons available without payment. | TODO |
| REQ-1.4.3 | Currencies | **ILS primary, USD secondary** (auto-detected by IP, user can switch). Prices displayed inclusive of VAT for ILS. | TODO |
| REQ-1.4.4 | Stripe Checkout | Use Stripe-hosted Checkout (no PCI burden). Redirect from `/pricing/` → Stripe → success/cancel pages. | TODO |
| REQ-1.4.5 | Webhooks | `/stripe/webhook/` endpoint handles: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Signature-verified. | TODO |
| REQ-1.4.6 | Entitlements model | `Entitlement(user, scope, expires_at)` where scope = `all_access` or `course:<id>`. Created/updated on webhook. Checked by REQ-1.3.4. | TODO |
| REQ-1.4.7 | Customer portal | Stripe Customer Portal link from user profile: manage subscription, update card, view invoices, cancel. | TODO |
| REQ-1.4.8 | Coupons & trials | Support Stripe coupons (admin-created). Optional 7-day free trial on first subscription. | TODO |
| REQ-1.4.9 | Israeli invoice (חשבונית מס) | On every successful payment, generate a kosher חשבונית via **Green Invoice (חשבונית ירוקה) API**. Email PDF to customer. Store invoice number in DB. | TODO |
| REQ-1.4.10 | Refunds | Admin can issue refunds via Stripe dashboard. Refund webhook revokes entitlement and issues חשבונית זיכוי via Green Invoice. | TODO |
| REQ-1.4.11 | VAT handling | 17% מע"מ added to ILS prices for Israeli customers. Foreign customers (USD) charged net. Determined by Stripe Tax or billing address. | TODO |
| REQ-1.4.12 | Billing pages | `/pricing/`, `/billing/` (account management deep-link to Stripe portal), `/billing/success/`, `/billing/cancelled/`. | TODO |

### 1.5 GitHub Copilot Seat Provisioning

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.5.1 | GitHub org + Copilot Business | A dedicated GitHub org (e.g. `babook-learn`) with Copilot Business plan active. Org PAT or GitHub App with `manage_billing:copilot` scope stored in env vars. | TODO |
| REQ-1.5.2 | GitHub username on user | User provides GitHub username at signup or in profile (or OAuth-links GitHub via allauth). Stored on user model, validated against GitHub API. | TODO |
| REQ-1.5.3 | Copilot-enabled subscription tier | At least one pricing tier flagged `includes_copilot=True`. Entitlement `copilot_seat` granted on active subscription, revoked on cancel/expiry. | TODO |
| REQ-1.5.4 | Auto-invite to org | On successful subscription with Copilot tier → invite GitHub user to the org via API. Track invite state (`pending` / `accepted` / `expired`). Resend after 7 days if pending. | TODO |
| REQ-1.5.5 | Auto-assign seat | On accepted org invite (webhook or poll) → assign Copilot seat via `POST /orgs/{org}/copilot/billing/selected_users`. Notify user by email with onboarding link (VS Code + sign-in). | TODO |
| REQ-1.5.6 | Auto-revoke on churn | On Stripe `subscription.deleted` or expiry → revoke Copilot seat immediately. Remove from GitHub org after **14-day grace period** (configurable). | TODO |
| REQ-1.5.7 | Inactivity reclamation | Daily job scans `last_activity_at` per seat. Warn user by email at **30 days** inactive. Reclaim seat at **60 days** inactive (configurable env vars). | TODO |
| REQ-1.5.8 | Admin dashboard | Admin sees: total assigned seats, monthly cost ($/mo), per-user last-activity date, pending invites, expired invites. One-click reclaim button per seat. | TODO |
| REQ-1.5.9 | Seat cap | Env var `COPILOT_MAX_SEATS` enforces hard cap to prevent runaway billing. New eligible subscriptions queued (waitlist) if cap reached; admin notified. | TODO |
| REQ-1.5.10 | User-facing status | User profile shows: Copilot seat status (`none` / `invite_pending` / `active` / `expiring` / `revoked`), link to accept org invite, last activity date, link to VS Code setup guide. | TODO |
| REQ-1.5.11 | Audit log | Every seat lifecycle event (invite/accept/assign/revoke/reclaim) written to an `audit_log` table with timestamp, actor (system/admin), reason, and GitHub API response. | TODO |
| REQ-1.5.12 | Org policy enforcement | Org-level Copilot policies set in GitHub UI: telemetry off, public-code suggestions filter on, allowed editors. Documented in `docs/procedures/copilot_policy.md`. | TODO |

### 1.6 AI Chat Infrastructure (OpenAI)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.6.1 | OpenAI API integration | Direct OpenAI API via `openai` Python library. API key stored as env var. Connection verified with a health-check call at startup. | TODO |
| REQ-1.6.2 | Chat endpoint (streaming) | `POST /api/chat/` accepts user message + session ID, returns streaming response via Server-Sent Events (SSE). Frontend renders tokens as they arrive. | TODO |
| REQ-1.6.3 | Conversation model | `ChatSession(user, context_type, created_at)` + `ChatMessage(session, role, content, tokens_used, created_at)`. Stores full history per session. | TODO |
| REQ-1.6.4 | Context-aware system prompts | Configurable system prompts per context: `course_tutor` (injected with course/lesson metadata), `code_helper`, `general_assistant`. Admin can edit prompts via Django admin. | TODO |
| REQ-1.6.5 | Model selection | Default model: **GPT-4o-mini** (fast, cheap). Premium tier: **GPT-4o**. Model choice configurable per subscription tier via env var / admin. | TODO |
| REQ-1.6.6 | Rate limiting | Per-user daily token cap by subscription tier (e.g. free=1k tokens, member=50k, premium=200k). Counter resets at midnight UTC. Exceeded → friendly error, upsell to higher tier. | TODO |
| REQ-1.6.7 | Usage tracking | `UsageLog(user, session, model, prompt_tokens, completion_tokens, cost_usd, created_at)`. Admin dashboard shows: daily/monthly tokens consumed, cost breakdown by user and model. | TODO |
| REQ-1.6.8 | Cost cap (safety) | Env var `OPENAI_MONTHLY_COST_CAP_USD`. If total monthly spend reaches 80%, alert admin. At 100%, disable chat for non-admin users until next month or manual override. | TODO |
| REQ-1.6.9 | Chat UI component | Reusable chat widget (bottom-right or sidebar) available on course pages and standalone `/chat/` page. Markdown rendering in responses (code blocks, lists, etc.). Mobile-friendly. | TODO |
| REQ-1.6.10 | Session management | User can: start new session, view past sessions, continue a session. Sessions auto-close after 30 min of inactivity. Context window managed (last N messages sent to API, older summarized or dropped). | TODO |
| REQ-1.6.11 | Content safety | OpenAI moderation API checked on user input before sending to chat. Flagged content rejected with user-friendly message. Logged for admin review. | TODO |
| REQ-1.6.12 | Chat in course context | When chat is opened from a lesson page, system prompt includes: course title, lesson title, lesson topic summary. User can ask questions about the specific lesson. | TODO |

### 1.7 Database (decided)

- **Engine**: SQLite, on Render persistent disk at `/var/data/db.sqlite3`
- **Justification**: peak load ≤ 100 req/min, well within SQLite (WAL) limits (~1k+ reads/sec, ~500 writes/sec)
- **Tuning required**: WAL mode + `busy_timeout` PRAGMAs in `DATABASES` config
- **Switch trigger**: move to managed Postgres if any of: `database is locked` errors in logs, need for >1 web instance, sustained >500 writes/sec
- Tracked under REQ-1.2.6 / REQ-1.2.4

### 1.7.1 Allauth providers

- **Google** (already wired) — primary social login
- **GitHub** (to add) — required for REQ-1.5.2 to capture verified GitHub username automatically

### 1.8 Decisions log

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-1 | Email backend | **Resend** | Modern API, generous free tier (3k/mo), 5-min setup, great Django support |
| DEC-2 | Language | **Bilingual Hebrew (default) + English**, RTL toggle | `.co.il` site, Israeli audience, but English broadens reach |
| DEC-3 | Analytics | **Plausible** | Privacy-friendly, no cookie banner consent needed for it, simple, GDPR-clean |
| DEC-4 | Icon set | **Bootstrap Icons** | Pairs with Bootstrap 5, free, comprehensive, simple class API |
| DEC-5 | Logo source | **AI-generated placeholder**, Avi swaps later | Unblocks build, no external dependency |
| DEC-6 | Pre-commit hooks | **Yes (black + ruff auto-format)** | Catches issues before push, no debate |
| DEC-7 | Backup target | **GitHub private repo** (`babook-backups`) | Free, version-controlled, trivial restore via `git clone` |
| DEC-8 | Video host | **Bunny Stream** | Cheap (~$5–10/mo at scale), signed URLs, full per-user tracking, no YouTube distractions |
| DEC-9 | Payments | **Stripe + Green Invoice (חשבונית ירוקה)** | Stripe = best-in-class payments + subscriptions; Green Invoice = legal Israeli חשבונית מס auto-generation |
| DEC-10 | Pricing model | **Subscription (monthly/yearly) + per-course one-time**, free preview lessons | Maximizes flexibility for AI training market |
| DEC-11 | Copilot tier | **Copilot Business** ($19/seat/mo) | Sufficient for training use case; Enterprise ($39) unnecessary at this stage |
| DEC-12 | Org membership after churn | **Remove from org 14 days after subscription ends** | Frees seat quickly, gives buffer for renewal/dispute |
| DEC-13 | Inactivity policy | **Warn at 30 days, reclaim at 60 days** | Reasonable for paid training context; avoids paying for idle seats |
| DEC-14 | Copilot-included pricing floor | **Minimum ₪149/mo (~$40) for any tier including Copilot** | Covers $19 Copilot cost + payment fees + margin |
| DEC-15 | AI Chat API | **Direct OpenAI API** (not Azure) | Simpler setup, no Azure subscription needed, direct access to latest models |
| DEC-16 | Default chat model | **GPT-4o-mini** (premium: GPT-4o) | 4o-mini is 10x cheaper, fast enough for tutoring; 4o for premium users who need advanced reasoning |

### 1.9 Avi action items

| ID | Action | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, give Copilot API key | REQ-1.1.3, REQ-1.2.2 |
| ACT-2 | Add SPF/DKIM DNS records at babook.co.il registrar | REQ-1.2.2 |
| ACT-3 | Create GitHub private repo `babook-backups` + deploy key | REQ-1.2.4 |
| ACT-4 | Approve AI-generated logo OR provide own | REQ-1.1.9 |
| ACT-5 | Create Plausible account, share site ID | REQ-1.2.11 |
| ACT-6 | Confirm Render persistent disk attached at `/var/data/` | REQ-1.1.5, REQ-1.2.4, REQ-1.5 |
| ACT-7 | Review draft privacy + terms text | REQ-1.2.12 |
| ACT-8 | Confirm `https://babook.co.il/accounts/google/login/callback/` in Google Cloud OAuth redirect URIs | REQ-1.1.2 |
| ACT-9 | Sign up Bunny.net, create Stream library, share API key + library ID | REQ-1.3.1 |
| ACT-10 | Create Stripe account (Israel), share test + live keys | REQ-1.4.1 |
| ACT-11 | Sign up Green Invoice (חשבונית ירוקה), share API key | REQ-1.4.9 |
| ACT-12 | Confirm עוסק status (מורשה / פטור) for VAT handling | REQ-1.4.11 |
| ACT-13 | Decide initial pricing (ILS amounts for monthly / yearly / per-course) | REQ-1.4.2, REQ-1.4.3 |
| ACT-14 | Create or identify GitHub org for seat provisioning (e.g. `babook-learn`) | REQ-1.5.1 |
| ACT-15 | Activate Copilot Business on that org (billing setup, payment method) | REQ-1.5.1 |
| ACT-16 | Generate org PAT or install GitHub App with `manage_billing:copilot` scope; share token | REQ-1.5.1 |
| ACT-17 | Confirm minimum subscription price for Copilot-included tier (recommended ≥ ₪149/mo) | REQ-1.5.3, DEC-14 |
| ACT-18 | Configure org-level Copilot policies in GitHub UI (telemetry, public-code filter, editors) | REQ-1.5.12 |

### 1.10 Acceptance criteria for Chapter 1

Chapter 1 is **DONE** when:
1. All `REQ-1.*` are `DONE` or formally `DEFERRED`
2. All `DEC-*` resolved (already done)
3. All `ACT-*` completed or marked N/A
4. `python manage.py check --deploy` passes cleanly
5. `pytest` exits 0 locally and in CI
6. Clean deploy from `main` to babook.co.il succeeds, all pages render, Google + password login work, password reset email arrives, health check returns 200, a test purchase via Stripe completes end-to-end and produces a Green Invoice חשבונית, a paid video plays via signed URL and progress is tracked, a Copilot-tier subscription auto-invites the test user to the GitHub org and assigns a Copilot seat (and revokes on cancel), AI chat returns a streaming response with correct rate limiting

---

## Chapter 2 — Project Definition

_TBD — defined after Chapter 1 is locked._

### 2.1 Vision
_TBD_

### 2.2 Scope
_TBD_

### 2.3 Users & Roles
_TBD_

### 2.4 Core Features
_TBD_

---

## Reference

- **Stack**: Django 5.2, Gunicorn, WhiteNoise, SQLite (Render disk), django-allauth (Google + GitHub OAuth), Bunny Stream (video), Stripe + Green Invoice (billing), Resend (email), Plausible (analytics), GitHub Copilot Business (seat provisioning via GitHub REST API), OpenAI API (AI chat, GPT-4o-mini / GPT-4o)
- **Live URL**: https://babook.co.il
- **Repo**: https://github.com/avisalmon/Render (branch `main`)
- **Deploy**: `git push origin main` → Render auto-deploys
