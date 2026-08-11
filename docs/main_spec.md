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
| REQ-1.1.1 | Base template | One `base.html` with header (logo + site name), main menu, content block, footer. All pages extend it. Renders identically on desktop and mobile. | DONE |
| REQ-1.1.2 | Google login / logout | Click "Login with Google" → OAuth flow → user logged in. Logout link clears session. Works in dev and prod. | DONE |
| REQ-1.1.3 | Password auth + forgot password | Signup, login, logout, change password, forgot-password (email reset link), reset password. Uses django-allauth. Depends on REQ-1.2.2. | DONE |
| REQ-1.1.4 | Static files | CSS/JS/images via WhiteNoise in prod, runserver in dev. `collectstatic` runs at deploy. No static 404s. | DONE |
| REQ-1.1.5 | Media files | User uploads stored on Render persistent disk at `/var/data/media/`. Survive deploys and restarts. | DONE |
| REQ-1.1.6 | User profile page | Logged-in user can view and edit: display name, avatar, email (read-only if from Google), bio, language preference. | DONE |
| REQ-1.1.7 | Bootstrap + CDN | Bootstrap 5 via CDN in `base.html`. Documented pattern for adding other free CDNs (jsDelivr, unpkg). | DONE |
| REQ-1.1.8 | Icon set | **Bootstrap Icons** loaded via CDN, available in all templates via `<i class="bi bi-...">`. | DONE |
| REQ-1.1.9 | Logo + favicon | Logo in header. Favicon set (16/32/180/192/512 + manifest + apple-touch-icon) wired in `<head>`. AI-learning themed. | DONE |
| REQ-1.1.10 | CI/CD documented | BKM `docs/procedures/cicd.md` covering: local dev setup, branch policy, commit conventions, deploy trigger, rollback, hotfix flow. | DONE |

### 1.2 Platform & Operations

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.2.1 | Custom error pages | Branded 404, 500, 403 templates extending `base.html`. Visible in prod (DEBUG=False). | DONE |
| REQ-1.2.2 | Email backend | Dev = console backend. Prod = **Resend** via env vars. Sender domain `babook.co.il` configured (SPF/DKIM). | DONE |
| REQ-1.2.3 | Env & secrets | All secrets via env vars. `.env` for local (gitignored). `settings_local.py` pattern. Render env vars list maintained in `docs/procedures/env_vars.md`. No secret in repo. | DONE |
| REQ-1.2.4 | Database backups | Weekly backup of `db.sqlite3` + media + Bunny video catalog to GCS. Incremental media sync. 30-day rolling retention **plus a permanent monthly snapshot** (`monthly/db_YYYY-MM.sqlite3`, never pruned). Success email with bucket links. Documented + verified restore. | DONE — `backup_db` runs **in-process in the web service** (Render crons can't reach the SQLite disk, DEC-68), triggered **weekly by a GitHub Actions cron** that POSTs a token-protected `/internal/run-backup/` endpoint; verified on prod 2026-06-18 (rolling + monthly snapshot + email) |
| REQ-1.2.5 | Logging | Django `LOGGING`: console + rotating file handler. App logs INFO, security WARNING. Procedure for tailing Render logs documented. | DONE |
| REQ-1.2.6 | Security hardening | `SECURE_SSL_REDIRECT=True` in prod, HSTS, secure cookies, CSRF, `ALLOWED_HOSTS` correct, `DEBUG=False`. `manage.py check --deploy` clean. | DONE |
| REQ-1.2.7 | Django admin | `/admin/` superusers only. Documented procedure for creating a superuser on Render. Default Django admin UI for now. | DONE |
| REQ-1.2.8 | Roles & permissions | Roles: `admin`, `staff`, `member`, `guest`. Django groups + permission decorators. Documented in `docs/architecture/roles.md`. | DONE |
| REQ-1.2.9 | Responsive layout | All pages work ≥ 360px wide. Menu collapses to hamburger on mobile. | DONE |
| REQ-1.2.10 | Language / RTL | **Bilingual** (Hebrew default, English secondary). `dir="rtl"` toggle. Bootstrap RTL variant when `he`. `.po` files via Django i18n. | DONE |
| REQ-1.2.11 | Analytics | **Plausible** (privacy-friendly, GDPR-clean, no cookie banner needed for it). Loaded only in prod. | DONE |
| REQ-1.2.12 | Cookie / privacy notice | First-visit banner. `/privacy/` and `/terms/` pages. Consent stored in cookie. | DONE |
| REQ-1.2.13 | Favicon set | Generated multi-size set referenced in `base.html`. Webmanifest valid. | DONE |
| REQ-1.2.14 | SEO basics | `sitemap.xml`, `robots.txt`, per-page `<title>` + `<meta description>`, Open Graph tags. | DONE |
| REQ-1.2.15 | Health check | `GET /healthz` → 200 `{"status":"ok"}`. Configured as Render health check URL. | DONE |
| REQ-1.2.16 | Testing infra | `pytest-django` configured. `tests/` per app. `pytest` exits 0 locally and in CI. | DONE |
| REQ-1.2.17 | Code quality | `black` + `ruff` in `pyproject.toml`. **Pre-commit hook enabled** (auto-format on commit). | DONE |
| REQ-1.2.18 | Backup & restore BKM | `docs/procedures/backup_restore.md`: how backups work, where they live, how to restore on Render and locally. Test-restore done once and recorded. | WIP — restore **verified 2026-06-18** (downloaded latest GCS backup, `PRAGMA integrity_check` = ok, table/row counts confirmed); BKM doc still describes the old rclone/Drive/cron flow and needs a refresh to the GCS + endpoint mechanism (DEC-68) |
| REQ-1.2.19 | Rollback BKM | `docs/procedures/rollback.md`: revert bad deploy on Render (manual redeploy of previous commit, env var revert, DB restore if needed). | DONE |

### 1.3 Video Infrastructure (Bunny Stream)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.3.1 | Video host: Bunny Stream | All course videos uploaded to Bunny Stream library. API key + library ID stored as env vars. | DONE |
| REQ-1.3.2 | Video model | Django `Video` model: `bunny_video_id`, `title`, `duration_seconds`, `course_id`, `lesson_order`, `is_free_preview`. | DONE |
| REQ-1.3.3 | Embedded player | Bunny iframe player embedded in lesson page. Responsive 16:9. `autoplay=false` by default — video does not auto-play on lesson entry. | DONE |
| REQ-1.3.4 | Signed playback URLs | Paid videos use Bunny's token-authentication (signed URLs, expire in 24h). Only entitled users get a playable URL. | DONE |
| REQ-1.3.5 | Per-user progress | Model `UserVideoProgress`: `user`, `video`, `last_position_seconds`, `percent_watched`, `completed_at`, `quiz_passed`. Updated via JS heartbeat every 10 s. **Visiting a lesson immediately records a UserVideoProgress entry (no minimum watch time required).** A lesson is "complete" when visited AND any `requires_correct` quiz is passed. | DONE |
| REQ-1.3.6 | Resume playback | Player resumes at `last_position_seconds` via Bunny player.js `setCurrentTime()` on `ready` event. Position saved on every heartbeat (10 s) and on page exit (`fetch keepalive`). Skipped if ≤ 5 s. | DONE |
| REQ-1.3.11 | Lesson prev/next navigation | Prev/Next lesson buttons appear at both the **top** and **bottom** of the lesson page. Top buttons are compact (`btn-sm`); bottom buttons are full-size. | DONE |
| REQ-1.3.7 | Course completion / certificate | `CourseCertificate(user, course, certificate_id UUID, issued_at)`. Certificate issued when all `requires_correct` quizzes in the course are passed. **No video-watching threshold required.** Accessed at `/certificate/<uuid>/`. | DONE |
| REQ-1.3.8 | Video upload admin flow | Admin can upload via Bunny dashboard, then register the `video_id` in Django admin. (Direct-upload from Django admin is deferred.) | DONE |
| REQ-1.3.9 | Free preview gating | `is_free_preview=True` videos playable by anonymous users. All others require login + entitlement. | DONE |
| REQ-1.3.10 | Lesson sidebar | Lesson page has a sticky right-side (RTL-aware) sidebar listing all lessons with status icons: playing (▶ blue), completed (✓ green), available (○ grey), locked (🔒). Active lesson highlighted. Collapses on mobile. | DONE |
| REQ-1.3.12 | Sequential lesson locking | Lessons unlock in order: lesson N is accessible only after lesson N-1 is "complete". Attempting to skip ahead redirects to the first incomplete lesson ("frontier"). Enrolled users only; free previews and anonymous users are unaffected. | DONE |
| REQ-1.3.13 | Lesson quizzes | `LessonQuiz(video OneToOne, question, options_json [{text, is_correct}], requires_correct bool)`. When `requires_correct=True`, the Next button is hidden until the user answers correctly. When `requires_correct=False`, any answer passes. | DONE |
| REQ-1.3.14 | Staff bypass | `is_staff` users always see all lessons as unlocked (`locked_ids={}`) and `lesson_completed=True`, so they can freely navigate any course for testing and QA. | DONE |
| REQ-1.3.15 | Volume persistence | Player volume saved to `localStorage("babook_volume")` on `pause` and every 10 s heartbeat via `player.getVolume()`. On player `ready`, restored via `player.setVolume()`. Default: 80 if key not set. Survives page reloads and new sessions on the same device. | DONE |
| REQ-1.3.16 | Continue watching on home | Logged-in users see a "Continue watching" card on `/` showing their last watched lesson (course + title + seconds). Clicking it navigates to that lesson at the saved position. Users with no prior progress see no card. Logo/home link always goes to `/` without redirect. | DONE |

### 1.4 Billing Infrastructure (Stripe + Green Invoice)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.4.1 | Payment processor: Stripe | Stripe account in Israel mode. Test + live API keys in env vars. `dj-stripe` library integrated. | DEFERRED |
| REQ-1.4.2 | Pricing model | **Subscription** (monthly + yearly) for full library access, plus optional **one-time** per-course purchase. Free preview lessons available without payment. | DONE |
| REQ-1.4.3 | Currencies | **ILS primary, USD secondary** (auto-detected by IP, user can switch). Prices displayed inclusive of VAT for ILS. | DEFERRED |
| REQ-1.4.4 | Stripe Checkout | Use Stripe-hosted Checkout (no PCI burden). Redirect from `/pricing/` → Stripe → success/cancel pages. | DEFERRED |
| REQ-1.4.5 | Webhooks | `/stripe/webhook/` endpoint handles: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Signature-verified. | DEFERRED |
| REQ-1.4.6 | Entitlements model | `Entitlement(user, scope, expires_at)` where scope = `all_access` or `course:<id>`. Created/updated on webhook. Checked by REQ-1.3.4. | DONE |
| REQ-1.4.7 | Customer portal | Stripe Customer Portal link from user profile: manage subscription, update card, view invoices, cancel. | DEFERRED |
| REQ-1.4.8 | Coupons & trials | Support Stripe coupons (admin-created). Optional 7-day free trial on first subscription. | DEFERRED |
| REQ-1.4.9 | Israeli invoice (חשבונית מס) | On every successful payment, generate a kosher חשבונית via **Green Invoice (חשבונית ירוקה) API**. Email PDF to customer. Store invoice number in DB. | DEFERRED |
| REQ-1.4.10 | Refunds | Admin can issue refunds via Stripe dashboard. Refund webhook revokes entitlement and issues חשבונית זיכוי via Green Invoice. | DEFERRED |
| REQ-1.4.11 | VAT handling | 17% מע"מ added to ILS prices for Israeli customers. Foreign customers (USD) charged net. Determined by Stripe Tax or billing address. | DEFERRED |
| REQ-1.4.12 | Billing pages | `/pricing/`, `/billing/` (account management deep-link to Stripe portal), `/billing/success/`, `/billing/cancelled/`. | DEFERRED |

### 1.5 GitHub Copilot Seat Provisioning

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.5.1 | GitHub org + Copilot Business | A dedicated GitHub org (e.g. `babook-learn`) with Copilot Business plan active. Org PAT or GitHub App with `manage_billing:copilot` scope stored in env vars. | DONE |
| REQ-1.5.2 | GitHub username on user | User provides GitHub username at signup or in profile (or OAuth-links GitHub via allauth). Stored on user model, validated against GitHub API. | DONE |
| REQ-1.5.3 | Copilot-enabled subscription tier | At least one pricing tier flagged `includes_copilot=True`. Entitlement `copilot_seat` granted on active subscription, revoked on cancel/expiry. | DONE |
| REQ-1.5.4 | Auto-invite to org | On successful subscription with Copilot tier → invite GitHub user to the org via API. Track invite state (`pending` / `accepted` / `expired`). Resend after 7 days if pending. | DONE |
| REQ-1.5.5 | Auto-assign seat | On accepted org invite (webhook or poll) → assign Copilot seat via `POST /orgs/{org}/copilot/billing/selected_users`. Notify user by email with onboarding link (VS Code + sign-in). | DONE |
| REQ-1.5.6 | Auto-revoke on churn | On Stripe `subscription.deleted` or expiry → revoke Copilot seat immediately. Remove from GitHub org after **14-day grace period** (configurable). | DONE |
| REQ-1.5.7 | Inactivity reclamation | Daily job scans `last_activity_at` per seat. Warn user by email at **30 days** inactive. Reclaim seat at **60 days** inactive (configurable env vars). | DONE |
| REQ-1.5.8 | Admin dashboard | Admin sees: total assigned seats, monthly cost ($/mo), per-user last-activity date, pending invites, expired invites. One-click reclaim button per seat. | DONE |
| REQ-1.5.9 | Seat cap | Env var `COPILOT_MAX_SEATS` enforces hard cap to prevent runaway billing. New eligible subscriptions queued (waitlist) if cap reached; admin notified. | DONE |
| REQ-1.5.10 | User-facing status | User profile shows: Copilot seat status (`none` / `invite_pending` / `active` / `expiring` / `revoked`), link to accept org invite, last activity date, link to VS Code setup guide. | DONE |
| REQ-1.5.11 | Audit log | Every seat lifecycle event (invite/accept/assign/revoke/reclaim) written to an `audit_log` table with timestamp, actor (system/admin), reason, and GitHub API response. | DONE |
| REQ-1.5.12 | Org policy enforcement | Org-level Copilot policies set in GitHub UI: telemetry off, public-code suggestions filter on, allowed editors. Documented in `docs/procedures/copilot_policy.md`. | DONE |

### 1.6 AI Chat Infrastructure (OpenAI)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.6.1 | OpenAI API integration | Direct OpenAI API via `openai` Python library. API key stored as env var. Connection verified with a health-check call at startup. | DONE |
| REQ-1.6.2 | Chat endpoint (streaming) | `POST /api/chat/` accepts user message + session ID, returns streaming response via Server-Sent Events (SSE). Frontend renders tokens as they arrive. | DONE |
| REQ-1.6.3 | Conversation model | `ChatSession(user, context_type, created_at)` + `ChatMessage(session, role, content, tokens_used, created_at)`. Stores full history per session. | DONE |
| REQ-1.6.4 | Context-aware system prompts | Configurable system prompts per context: `course_tutor` (injected with course/lesson metadata), `code_helper`, `general_assistant`. Admin can edit prompts via Django admin. | DONE |
| REQ-1.6.5 | Model selection | Default model: **GPT-4o-mini** (fast, cheap). Premium tier: **GPT-4o**. Model choice configurable per subscription tier via env var / admin. | DONE |
| REQ-1.6.6 | Rate limiting | Per-user daily token cap by subscription tier (e.g. free=1k tokens, member=50k, premium=200k). Counter resets at midnight UTC. Exceeded → friendly error, upsell to higher tier. | DONE |
| REQ-1.6.7 | Usage tracking | `UsageLog(user, session, model, prompt_tokens, completion_tokens, cost_usd, created_at)`. Admin dashboard shows: daily/monthly tokens consumed, cost breakdown by user and model. | DONE |
| REQ-1.6.8 | Cost cap (safety) | Env var `OPENAI_MONTHLY_COST_CAP_USD`. If total monthly spend reaches 80%, alert admin. At 100%, disable chat for non-admin users until next month or manual override. | DONE |
| REQ-1.6.9 | Chat UI component | Reusable chat widget (bottom-right or sidebar) available on course pages and standalone `/chat/` page. Markdown rendering in responses (code blocks, lists, etc.). Mobile-friendly. | DONE |
| REQ-1.6.10 | Session management | User can: start new session, view past sessions, continue a session. Sessions auto-close after 30 min of inactivity. Context window managed (last N messages sent to API, older summarized or dropped). | DONE |
| REQ-1.6.11 | Content safety | OpenAI moderation API checked on user input before sending to chat. Flagged content rejected with user-friendly message. Logged for admin review. | DONE |
| REQ-1.6.12 | Chat in course context | When chat is opened from a lesson page, system prompt includes: course title, lesson title, lesson topic summary. User can ask questions about the specific lesson. | DONE |

### 1.7 Database (decided)

- **Engine**: SQLite, on Render persistent disk at `/var/data/db.sqlite3`
- **Justification**: peak load ≤ 100 req/min, well within SQLite (WAL) limits (~1k+ reads/sec, ~500 writes/sec)
- **Tuning required**: WAL mode + `busy_timeout` PRAGMAs in `DATABASES` config
- **Switch trigger**: move to managed Postgres if any of: `database is locked` errors in logs, need for >1 web instance, sustained >500 writes/sec
- Tracked under REQ-1.2.6 / REQ-1.2.4

### 1.7.1 Allauth providers

- **Google** (already wired) — primary social login
- **GitHub** (wired) — enabled for REQ-1.5.2 to capture GitHub username automatically

### 1.8 Decisions log

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-1 | Email backend | **Resend** | Modern API, generous free tier (3k/mo), 5-min setup, great Django support |
| DEC-2 | Language | **Bilingual Hebrew (default) + English**, RTL toggle | `.co.il` site, Israeli audience, but English broadens reach |
| DEC-3 | Analytics | **Plausible** | Privacy-friendly, no cookie banner consent needed for it, simple, GDPR-clean |
| DEC-4 | Icon set | **Bootstrap Icons** | Pairs with Bootstrap 5, free, comprehensive, simple class API |
| DEC-5 | Logo source | **AI-generated placeholder**, Avi swaps later | Unblocks build, no external dependency |
| DEC-6 | Pre-commit hooks | **Yes (black + ruff auto-format)** | Catches issues before push, no debate |
| DEC-7 | Backup target | ~~GitHub private repo~~ → see DEC-18 | Superseded by Google Drive decision |
| DEC-8 | Video host | **Bunny Stream** | Cheap (~$5–10/mo at scale), signed URLs, full per-user tracking, no YouTube distractions |
| DEC-9 | Payments | **Stripe + Green Invoice (חשבונית ירוקה)** | Stripe = best-in-class payments + subscriptions; Green Invoice = legal Israeli חשבונית מס auto-generation |
| DEC-10 | Pricing model | **Subscription (monthly/yearly) + per-course one-time**, free preview lessons | Maximizes flexibility for AI training market |
| DEC-11 | Copilot tier | **Copilot Business** ($19/seat/mo) | Sufficient for training use case; Enterprise ($39) unnecessary at this stage |
| DEC-12 | Org membership after churn | **Remove from org 14 days after subscription ends** | Frees seat quickly, gives buffer for renewal/dispute |
| DEC-13 | Inactivity policy | **Warn at 30 days, reclaim at 60 days** | Reasonable for paid training context; avoids paying for idle seats |
| DEC-14 | Copilot-included pricing floor | **Minimum ₪149/mo (~$40) for any tier including Copilot** | Covers $19 Copilot cost + payment fees + margin |
| DEC-15 | AI Chat API | **Direct OpenAI API** (not Azure) | Simpler setup, no Azure subscription needed, direct access to latest models |
| DEC-16 | Default chat model | **GPT-4o-mini** (premium: GPT-4o) | 4o-mini is 10x cheaper, fast enough for tutoring; 4o for premium users who need advanced reasoning |
| DEC-17 | Tax entity | **עוסק פטור** (exempt dealer, no VAT) | Simplest start; no מע"מ collection/remit; issues קבלות not חשבוניות מס. Revisit if revenue exceeds cap (~120K ILS/yr) |
| DEC-18 | Backup target (revised) | ~~**Google Drive** via rclone~~ → see DEC-68 | Superseded: the actual implementation backs up to **Google Cloud Storage** via the GCS JSON API (not Drive, not rclone) |
| DEC-68 | Backup target + trigger (final) | **GCS** bucket `babook-backups-490715`, written by `backup_db` running **in-process in the web service**, triggered **weekly by a GitHub Actions cron** (`.github/workflows/weekly-backup.yml`, Mon 03:00 UTC + manual dispatch) that POSTs a token-protected `/internal/run-backup/` endpoint. 30-day rolling retention on `db/`; permanent `monthly/` snapshots. | A Render `cron_job` runs in a **separate container that cannot mount the web service's persistent disk**, so it can't read `db.sqlite3` — the old `nightly-backup` cron failed every night for ~4 weeks (`CommandError: Database not found`) and was **deleted via the Render API on 2026-06-18**. Running the backup in-process (triggered by an external cron) is the only way to reach the SQLite disk. GCS over Drive/rclone: service-account auth, no rclone daemon, direct JSON API |

### 1.9 Avi action items

| ID | Action | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, give Copilot API key | REQ-1.1.3, REQ-1.2.2 |
| ACT-2 | Add SPF/DKIM DNS records at babook.co.il registrar | REQ-1.2.2 |
| ~~ACT-3~~ | ~~Set up rclone with Google Drive for DB backups~~ — DONE differently: GCS + GitHub Actions → in-process endpoint (DEC-68), no rclone/Drive | REQ-1.2.4 |
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

## Chapter 2 — Corporate Landing & First Course

> **Back-filled 2026-06-09.** EPIC-2 was implemented (and shipped to prod) ahead
> of a written spec; the backlog used placeholder `REQ-2.x` IDs. This chapter
> documents the requirements that the built, passing, and live features satisfy,
> restoring REQ traceability. Same conventions as Chapter 1
> (`REQ-<chapter>.<group>.<n>`, status `TODO`/`WIP`/`DONE`/`BLOCKED`/`DEFERRED`).

### 2.0 Vision

babook.co.il establishes **Avi Salmon** as a credible AI-training authority for
the Israeli market and beyond. The site has two jobs:
1. **Convert corporate decision-makers** into inbound inquiries for paid
   engagements (workshops, bootcamps, keynotes) — this is the **north-star
   metric: inbound corporate inquiries**.
2. **Teach individuals** through flagship, video-based courses with progress
   tracking, quizzes, and certificates.

### 2.1 Scope

**In scope (this epic — DONE):** a design-system foundation; a conversion-focused
`/corporate/` landing page with lead capture; newsletter capture with double
opt-in; an accessibility/mobile-quality pass; the first flagship course
(`micropython-thonny`) end-to-end (catalog → detail → enrollment → lessons →
completion → certificate); and a remote course-management API to publish courses
from local dev to production.

**Out of scope / deferred:** paid subscriptions and checkout (Chapter 1 §1.4
billing — DEFERRED); a multi-course marketplace beyond the first course;
personalized recommendations; native mobile apps.

### 2.2 Users & Roles

Builds on the roles in [architecture/roles.md](architecture/roles.md):
- **Guest** — anonymous visitor (corporate prospect or browsing learner). Can
  view `/corporate/`, the course catalog, free-preview lessons, submit the
  contact form, and subscribe to the newsletter.
- **Member** — registered/enrolled learner. Watches lessons, takes quizzes,
  earns certificates.
- **Staff** — content/QA; can navigate all lessons unlocked (REQ-1.3.14).
- **Admin** — full Django admin; manages courses, leads, subscribers.
- **Corporate Lead** — a prospect who submits the contact form (`CorporateLead`).
- **Newsletter Subscriber** — double-opt-in email subscriber (`NewsletterSubscriber`).

### 2.3 Design System Foundation

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.3.1 | CSS design tokens | `style.css` defines CSS custom properties for the dark-theme color palette (`--bg-primary`, `--accent-*`, `--text-*`). | DONE |
| REQ-2.3.2 | Web fonts | Google Fonts loaded in `base.html` with `display=swap`. | DONE |
| REQ-2.3.3 | Typography & spacing scale | Font-family and spacing variables defined and used consistently. | DONE |
| REQ-2.3.4 | Max content width | Content constrained to a max width (~1200px) for readability. | DONE |
| REQ-2.3.5 | Card surface component | Reusable `.card-surface` class for elevated content blocks. | DONE |
| REQ-2.3.6 | Sticky WhatsApp CTA | `.whatsapp-sticky` component, env-driven number, RTL-aware. | DONE |
| REQ-2.3.7 | Themed body | `body` uses `--bg-primary` token (no hard-coded colors). | DONE |

### 2.4 Corporate Landing Page (`/corporate/`)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.4.1 | Route + anonymous access | `GET /corporate/` → 200 for anonymous users. | DONE |
| REQ-2.4.2 | SEO | Per-page title/meta/canonical + sitemap entry + OG tags. | DONE |
| REQ-2.4.3 | Hero | Hero section: photo + value-prop copy + primary/secondary CTAs. | DONE |
| REQ-2.4.4 | Service tiers | Cards for the engagement types (workshop / bootcamp / keynote). | DONE |
| REQ-2.4.5 | FAQ | Accordion of common corporate questions. | DONE |
| REQ-2.4.6 | Lead capture | Contact form persists to `CorporateLead`; success/error states. | DONE |
| REQ-2.4.7 | Spam protection | Honeypot field + rate limiting on submit. | DONE |
| REQ-2.4.8 | WhatsApp CTAs | WhatsApp deep-links using `WHATSAPP_NUMBER` env var. | DONE |
| REQ-2.4.9 | Attribution | UTM param capture + Plausible custom events on key actions. | DONE |
| REQ-2.4.10 | Form security | CSRF enforced on AJAX submit; input sanitized (HTML strip + length limits). | DONE |

### 2.5 Newsletter Capture

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.5.1 | Signup endpoint | `POST /newsletter/signup/` creates a `NewsletterSubscriber` (GET → 405). | DONE |
| REQ-2.5.2 | Double opt-in | Email stored lowercase; confirmation email with token; `confirmed_at` set on confirm. | DONE |
| REQ-2.5.3 | Placement | Newsletter component rendered once on `/corporate/`. | DONE |
| REQ-2.5.4 | Hygiene | `purge_unconfirmed_subscribers` management command removes stale unconfirmed signups. | DONE |

### 2.6 Accessibility & Mobile Polish

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.6.1 | Keyboard/AT basics | Skip-to-content link, `:focus-visible` styles, correct H1→H2→H3 hierarchy, section `aria-label`s. | DONE |
| REQ-2.6.2 | Live status | Form status uses an `aria-live` region. | DONE |
| REQ-2.6.3 | Motion | `prefers-reduced-motion` respected in CSS. | DONE |
| REQ-2.6.4 | Mobile layout | Hero sized for mobile (explicit width/height), CTAs stack, tier cards full-width, Bootstrap grid. | DONE |
| REQ-2.6.5 | Sticky CTA polish | WhatsApp sticky z-index + 48px touch target; RTL mirrored position. | DONE |

### 2.7 First Flagship Course (`micropython-thonny`)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.7.1 | Course model | Fields: category, difficulty, thumbnail, `title_en`, `is_published` (migration 0010). | DONE |
| REQ-2.7.2 | Enrollment | `Enrollment` model + enrollment flow. | DONE |
| REQ-2.7.3 | Catalog | `GET /courses/` lists published courses. | DONE |
| REQ-2.7.4 | Detail page | `GET /courses/<slug>/` shows course detail + progress. | DONE |
| REQ-2.7.5 | Lessons | Lesson page with Bunny player, sidebar, prev/next (see REQ-1.3.*). | DONE |
| REQ-2.7.6 | Completion | Course complete when required quizzes passed; certificate issued (REQ-1.3.7). | DONE |
| REQ-2.7.7 | SEO | Course pages have titles/meta + sitemap entries. | DONE |
| REQ-2.7.8 | Funnel hook | Course detail links into the `/corporate/` funnel. | DONE |
| REQ-2.7.9 | Authoring | `load_course_from_manifest` builds a course from a local manifest. | DONE |
| REQ-2.7.10 | Materials | `CourseMaterial` (files + links) per course; shown on detail + lesson sidebar (migration 0013). | DONE |
| REQ-2.7.11 | Certificates on profile | Issued certificates listed on the user profile. | DONE |

### 2.8 Remote Course Management API

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.8.1 | Token auth | All `/api/v1/*` endpoints require `COURSE_MGMT_API_KEY` (Bearer header). | DONE |
| REQ-2.8.2 | List | `GET /api/v1/courses/` returns all courses (verification). | DONE |
| REQ-2.8.3 | Sync | `POST /api/v1/courses/sync/` idempotently upserts course + videos + materials + `LessonQuiz` (omitting quiz deletes it). | DONE |
| REQ-2.8.4 | Media upload | `POST /api/v1/media/upload/` stores a file on the persistent disk; returns its relative path. | DONE |
| REQ-2.8.5 | Publish command | `push_course_to_production` reads the local DB, uploads files, calls the sync API. | DONE |

### 2.9 Acceptance criteria for Chapter 2

Chapter 2 is **DONE** when:
1. All `REQ-2.*` are `DONE` (or formally `DEFERRED`). ✅ (as of 2026-06-09)
2. `/corporate/`, `/courses/`, course detail, and lesson pages render and are
   reachable in production. ✅
3. A corporate lead submitted via the form is persisted and retrievable. ✅
4. A newsletter signup completes the double-opt-in flow. ✅
5. The first course plays end-to-end with progress, quizzes, and a certificate. ✅
6. A course can be published from local dev to prod via the management API. ✅

### 2.10 Chapter 2 decisions

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-19 | Course publishing | **Remote management API** (local dev → prod over REST) | Avoids manual DB/file ops on Render; idempotent, repeatable, auth'd |
| DEC-20 | Lead handling | **Store `CorporateLead` in DB** (no external CRM yet) | Simplest start; export/CRM integration can come later |
| DEC-21 | Newsletter opt-in | **Double opt-in** | Deliverability + compliance; avoids spam complaints |

---

## Chapter 3 — Training Platform & Course Library

> **Back-filled 2026-06-12.** EPIC-3 grew organically (taxonomy, drill-down
> catalog, per-level intros, cross-listing, experiential reflection lessons, a
> 16-course library) and shipped to prod ahead of a written spec. This chapter
> documents the requirements the built, live features satisfy, restoring REQ
> traceability. Same conventions as Chapters 1-2.

### 3.0 Vision

Scale from a single flagship course to a **structured, navigable library** spanning
multiple domains, with a self-documenting taxonomy, experiential (try-it-yourself)
lessons, and faithful, human course notes. The catalog must stay scannable as the
library grows from tens to hundreds of courses.

### 3.1 Training taxonomy (Domain → Track → Course)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-3.1.1 | Course taxonomy fields | `Course.domain` + `Course.track` (migration 0014). | DONE |
| REQ-3.1.2 | Taxonomy definition | `app/taxonomy.py` `TRAINING_TAXONOMY`: domains + tracks with title/subtitle/icon/order/description. | DONE |
| REQ-3.1.3 | Catalog builder | `build_catalog(courses)` groups published courses into Domain → Track → Courses, returns `(domains, uncategorized)`; nothing silently dropped. | DONE |
| REQ-3.1.4 | Domains | מטצים (4 tracks), בינה מלאכותית (3 levels), הובלת חדשנות (ExO / leadership / presentation). | DONE |

### 3.2 Drill-down catalog

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.2.1 | Domains (L0) | `GET /courses/` lists domains as big cards with small topic-chip hints. | DONE |
| REQ-3.2.2 | Tracks (L1) | `GET /courses/topic/<domain>/` lists the domain's tracks with course-name hints. | DONE |
| REQ-3.2.3 | Leaves (L2) | `GET /courses/topic/<domain>/<track>/` lists course cards with descriptions. | DONE |
| REQ-3.2.4 | Breadcrumbs + empties | Breadcrumb nav at L1/L2; empty domains/tracks render a "coming soon" state, not a 404. | DONE |

### 3.3 Per-level intro cards

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.3.1 | Intro row | A domain with `intro_row` renders a top row of one "intro" card per track; a track's `intro_slug` course is featured and listed first within the track. | DONE |

### 3.4 Cross-listing

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.4.1 | extra_slugs | A track's `extra_slugs` lists a course in additional tracks without changing its primary placement (e.g. Python in matazim/software AND ai-l3). | DONE |

### 3.5 Experiential lessons (reflection)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.5.1 | Reflection model | `Video.reflection_prompt` + `LessonReflection(user, video, prompt, user_text, ai_reply)` (migration 0015). | DONE |
| REQ-3.5.2 | Reflection endpoint | `POST /api/lesson/<video_id>/reflect/`: save free-text + GPT reply, complete the lesson (reuses `quiz_passed` gating). Graceful fallback if OpenAI fails. | DONE |
| REQ-3.5.3 | Privacy | Reflections are admin-only (Django admin); the user's own profile shows enrolled courses + completion %, not reflections. | DONE |
| REQ-3.5.4 | Video-optional lessons | A lesson with empty `bunny_video_id` renders as text-only (no player). | DONE |

### 3.6 Content sync (extended)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.6.1 | Extended sync fields | Sync carries `domain/track/reflection_prompt/is_final_lesson/summary_he`; lessons removed in a push are deleted on prod (rework support). | DONE |
| REQ-3.6.2 | WAF-safe payload | Optional gzip+base64 body (`X-Payload-Encoding: gzip-base64`) for code-heavy pushes. | DONE |

### 3.7 Homepage worlds

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.7.1 | Worlds + slim hero | Slim hero + "worlds of babook" cards (Training live, others placeholders); placeholder section pages (`/community/ /services/ /workshops/ /nostalgia/ /research/`). | DONE |

### 3.8 Content quality

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-3.8.1 | Faithful notes | Lesson notes reflect the source (the speaker's points/examples), lightly enriched, with real sources. | DONE |
| REQ-3.8.2 | Clean copy | No em-dashes anywhere user-facing; code/commands in fenced ``` snippets; markdown tables render as HTML. | DONE |

### 3.9 Decisions log

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-22 | Taxonomy storage | **Code-defined `TRAINING_TAXONOMY` + `domain`/`track` fields** | Stable, ordered, fast; no extra models; cross-listing via `extra_slugs` |
| DEC-23 | Assessment | **AI reflection** as an alternative to quizzes for experiential courses | Engagement + captured learner intent; replaces the right/wrong gate |
| DEC-24 | Note generation | **Faithful-first** (capture the talk, then enrich) over generic write-ups | Preserves the speaker's voice and specific examples |
| DEC-25 | Transcription | **gpt-4o-transcribe** (stronger) for important courses | Cleaner transcripts for code-switching / technical Hebrew-English talks |

### 3.10 Acceptance criteria for Chapter 3

Chapter 3 is **DONE** when: all `REQ-3.*` are `DONE`; the drill-down catalog, intros,
cross-listing, reflection flow, and 16-course library are live on babook.co.il; and
the full regression passes.

---

## Chapter 4 — Course Authoring Studio

### 4.0 Vision

Turn course creation from a developer-run local pipeline into a **self-serve,
in-product studio** for Avi and any authorized author. Two complementary modes:
a **manual editor** (full CRUD over courses and lessons) and an **automated
pipeline** (a video → a complete, editable draft course). The studio must be
clean, fast, and good enough to beat off-the-shelf course tools.

### 4.1 Authoring access

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-4.1.1 | Author capability | `UserProfile.is_author`; staff are implicitly authors. `@author_required` guards every studio route (non-authors → 403/redirect). | DONE |
| REQ-4.1.2 | Studio entry | `/studio/` lists the courses with create / edit / delete, visible only to authors (link shown in nav for authors). | DONE |

### 4.2 Manual authoring (CRUD)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-4.2.1 | Create / edit course | Edit title, title_en, description, domain, track, difficulty, thumbnail, is_published. Domain/track from the taxonomy. | DONE |
| REQ-4.2.2 | Delete course | Delete a course (with confirm). | DONE |
| REQ-4.2.3 | Lesson CRUD | Add / edit / delete a lesson: title, notes (markdown), bunny_video_id, is_free_preview, is_final_lesson, reflection_prompt, duration. | DONE |
| REQ-4.2.4 | Markdown editor + preview | The notes editor shows a live rendered preview (same renderer as the lesson page). | DONE |
| REQ-4.2.5 | Reorder lessons | Reorder lessons (drag and/or up/down); lesson_order persists; the final lesson flag follows the last lesson. | DONE |
| REQ-4.2.6 | Publish toggle | Publish / unpublish a course from the studio. | DONE |

### 4.3 Automated pipeline (video → course)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-4.3.1 | New-from-video wizard | Start a course from a YouTube URL **or** an uploaded video, plus title + domain/track. | DONE |
| REQ-4.3.2 | `AuthoringJob` model | Tracks a build job: source, status (pending/running/done/error), progress %, current step, log, linked course. | DONE |
| REQ-4.3.3 | Pipeline | download → transcribe (gpt-4o-transcribe) → detect topics → split → upload to Bunny → faithful notes → draft course with lessons. Runs in the background; progress is written to the job. | DONE |
| REQ-4.3.4 | Live progress | The wizard shows live status/step/progress (polling) until done, then links to the draft course editor. | DONE |
| REQ-4.3.5 | Editable result | The generated draft is a normal course, fully editable with the manual tools (4.2), and unpublished until the author publishes it. | DONE |
| REQ-4.3.6 | Worker fallback | `run_authoring_jobs` management command processes pending jobs (for environments where a YouTube download from the web host is blocked). | DONE |

### 4.4 Local / Studio sync safety

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-4.4.1 | Edited marker | A course edited in the Studio sets `Course.studio_edited_at`; shown as a badge in the studio list/editor. | DONE |
| REQ-4.4.2 | Course-detail API | `GET /api/v1/courses/<slug>/` (Bearer) returns the full course payload; the list endpoint includes `studio_edited_at`. | DONE |
| REQ-4.4.3 | Pull command | `pull_course_from_production <slug>` rebuilds the local copy from prod (local <- prod). | DONE |
| REQ-4.4.4 | Push guard | `push_course_to_production` aborts (suggesting pull) if the remote was Studio-edited more recently than local; `--force` overrides. | DONE |

### 4.5 Decisions log

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-26 | Studio access | **`is_author` flag + staff** | Lets Avi authorize specific creators without giving full admin |
| DEC-27 | Background processing | **Daemon thread + `AuthoringJob` + worker command** | No Celery/Redis on the SQLite/Render setup; thread for self-serve UX, command as robust fallback |
| DEC-28 | Pipeline reuse | **`app/authoring/` package** (in-app pipeline) | Promotes the proven local scripts into tested, importable app code |

### 4.6 Acceptance criteria for Chapter 4

Chapter 4 is **DONE** when: authors can create/edit/delete/reorder courses and
lessons in `/studio/` with a live markdown preview; a video (URL or upload) can be
turned into an editable draft course via the wizard with live progress; non-authors
are blocked; and the full regression passes.

---

## Chapter 5 — Onboarding, Access Model & First-Time Experience

> **Spec approved by Avi 2026-06-12 (DEC-29-35) and implemented the same day.**
> Same conventions as Chapters 1-4. Companion UX concept:
> [architecture/onboarding_ux.md](architecture/onboarding_ux.md). Tests:
> `tests/test_spr_5_1.py` … `test_spr_5_5.py` (47 tests).

### 5.0 Vision

Today a brand-new visitor lands somewhere (homepage, a shared course link, an ad)
and is left to figure the site out alone; the rules for what a logged-out vs a
logged-in user may see live only in code; and nothing captures **why** the visitor
came or **what** they want. Chapter 5 fixes all three:

1. **A canonical access model** — one authoritative matrix of what an anonymous
   (logged-out) visitor can see and do vs a registered member, with the
   enforcement made deliberate and context-aware (not a generic 403).
2. **A deliberate first-visit journey** — value-first exploration, an entry-point-
   aware welcome, a low-friction registration that *preserves the visitor's
   original intent*, and a short **AI onboarding interview** that learns the
   learner's name, goal, level, and interests by conversation (with a static
   fallback).
3. **Personalization from the first minute** — the captured intent and learner
   profile drive a "start here" recommendation and a personalized homepage, so a
   new user reaches their first valuable lesson fast (the activation / "aha"
   moment).

**North-star for this epic:** *activation rate* — the share of new registrations
that complete onboarding **and** finish their first lesson within the first
session. Secondary: anonymous→registered conversion at the gated-action wall.

### 5.1 Access model — logged-out vs logged-in (the canonical matrix)

The authoritative statement of what each audience may see/do. Rows marked
`DONE (existing)` are already enforced in code (cross-referenced); rows marked
`TODO` are new in this epic. This matrix is the single source of truth; code and
`roles.md` must match it.

| Area / action | Anonymous (guest, not logged in) | Registered member | Enforcement |
|---|---|---|---|
| Homepage `/` (worlds) | View | View **+ "Continue watching" + "Recommended for you"** | REQ-1.3.16 (DONE); recs TODO REQ-5.6.* |
| `/corporate/`, `/pricing/`, `/privacy/`, `/terms/` | View | View | REQ-2.4.1 — DONE (existing) |
| Course catalog `/courses/` + drill-down | Browse all published | Browse all | REQ-3.2 — DONE (existing) |
| Course detail `/courses/<slug>/` | View syllabus + intro | View + progress + enroll | REQ-2.7.4 — DONE (existing) |
| First lesson (`is_free_preview=True`) | Watch video + read notes | Watch | REQ-1.3.9 — DONE (existing) |
| Non-preview lessons | **Blocked → context-aware wall** (not generic 403) | Watch if enrolled/entitled | REQ-1.3.9 / REQ-1.3.12 (DONE) + wall TODO REQ-5.4.1 |
| Enrollment | Blocked → wall | Enroll | TODO REQ-5.4.1 |
| Reflections (submit) | Blocked → wall | Submit | REQ-3.5 — DONE (existing) |
| Lesson quizzes | View question (no submit) | Answer / gate Next | REQ-1.3.13 — DONE (existing) |
| Certificates | None | Earned + on profile | REQ-1.3.7 — DONE (existing) |
| AI chat | None | Use (tier rate-limited) | REQ-1.6.6 — DONE (existing) |
| Profile / progress / settings | None | Full | REQ-1.1.6 — DONE (existing) |
| Newsletter signup, contact form | Submit | Submit | REQ-2.5 / REQ-2.4.6 — DONE (existing) |
| Studio `/studio/` | None | Authors only | REQ-4.1.1 — DONE (existing) |

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.1.1 | Canonical access matrix | The table above is the authoritative access model; `roles.md` links to it and matches it; no view grants/denies access in a way that contradicts it. | DONE |
| REQ-5.1.2 | Anonymous never errors out | A logged-out user attempting a gated action is **never** shown a bare 403/login page; they get the context-aware wall (REQ-5.4.1). 404s for truly missing resources are unaffected. | DONE |
| REQ-5.1.3 | Roles doc alignment | `docs/architecture/roles.md` updated to reference REQ-5.1.1 and adds the `guest`-vs-`member` capability split explicitly. | DONE |

### 5.2 Entry-point & intent capture (anonymous, zero-friction)

Capture **how the visitor arrived** and **what they came for** without asking a
single question, by reading the first request. Stored in the session (and the
attribution carried onto the `LearnerProfile` at registration, REQ-5.6.*).

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.2.1 | First-touch capture | On a visitor's first request, store in the session: `entry_path`, `entry_course` (slug if the path is a course/lesson page), `referrer`, `utm_*` (reuse REQ-2.4.9 capture), `first_seen_at`. Written once; never overwritten within a session. | DONE |
| REQ-5.2.2 | Entry-type classification | Classify the entry as one of: `home` (broad), `course` (specific interest = that course/domain), `lesson_locked` (high intent — hit a gate), `corporate` (prospect, routes to the lead funnel not the learner funnel), `other`. | DONE |
| REQ-5.2.3 | Intent → interest seed | When entry is `course`/`lesson_locked`, the course's domain/track is treated as the visitor's **primary interest seed** and pre-fills onboarding (REQ-5.5.*) and recommendations (REQ-5.6.*). | DONE |
| REQ-5.2.4 | Privacy | Capture respects the existing cookie/consent banner (REQ-1.2.12); no PII stored for anonymous visitors beyond session attribution; analytics stay on Plausible (no new trackers). | DONE |

### 5.3 First-visit exploration (value before friction)

A logged-out first-time visitor can explore and taste value before being asked to
do anything.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.3.1 | Free exploration | A first-time visitor can browse the full catalog and watch the free first lesson of any course with no login prompt (per the matrix). | DONE (existing, re-verified) |
| REQ-5.3.2 | First-visit welcome | On the first visit only, a dismissible, RTL welcome strip orients the visitor ("three worlds; start with a free lesson"). If entry is `course`, it acknowledges the course they came for. Dismissal persists (cookie); never shown to logged-in users. | DONE |
| REQ-5.3.3 | No proactive nudges (DEC-34) | While exploring there are **no** proactive registration prompts or "track progress" banners. The **only** registration ask is the context-aware wall (REQ-5.4.1), shown strictly at a genuinely gated action. Free exploration stays clean. | DONE |
| REQ-5.3.4 | Corporate "for your team" path (DEC-35) | A visitor whose entry is `corporate` is offered, alongside the existing lead funnel, a **"for your team" learner path** — a CTA into the learner journey framed for teams (e.g. "preview the training your team would get"), seeding a team-oriented interest. The lead form (REQ-2.4.6) is unchanged. | DONE |

### 5.4 Registration with preserved intent

The conversion moment. When a logged-out visitor reaches a gated action, the wall
is **contextual** and registration **returns them to exactly where they were
going**.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.4.1 | Context-aware wall | Hitting a gated action shows a wall naming the thing they wanted ("Register free to continue *<course title>*"), with one-click Google/GitHub and email options, and the value proposition — not a generic login form. | DONE |
| REQ-5.4.2 | Return-to-intent | After registration/login the user lands on their original target (`?next=` preserved end-to-end through the OAuth round-trip). For a `lesson_locked` entry, that means the lesson they tried to open. | DONE |
| REQ-5.4.3 | Minimal friction | Registration asks for the minimum (name + email + password, or one social click). Display name pre-fills the onboarding greeting. | DONE (allauth + display-name greeting) |
| REQ-5.4.4 | Attribution on signup | At registration, the session intent (REQ-5.2.*) is persisted onto the new `LearnerProfile` (entry path, entry course, utm, referrer). | DONE |

### 5.5 AI onboarding interview (conversational, with static fallback)

Right after first registration, a short conversational interview learns the
learner and routes them to the right starting point. Grounded in research_2's
"AI Interview onboarding — personalization via conversation > static forms."

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.5.1 | Interview entry | A newly registered user with `onboarding_completed_at IS NULL` is routed to `/welcome/` on next page load. Existing/returning users are never sent there. | DONE |
| REQ-5.5.2 | Conversational flow | An OpenAI-backed chat (reuse REQ-1.6 infra, `gpt-4o-mini`) greets by name and asks 2-4 adaptive questions **grounded in the site's taxonomy**: which world (named: AI / מטצים / חדשנות), what they want from the chosen domain in plain language - for AI exactly three choices: cool-stuff-with-existing-tools / build-your-own-AI-and-integrate-at-work / understand-how-AI-works-internally - silently translated to level (never "רמה 1/2/3" or "מתחיל/מתקדם" jargon), goal, time. If entry was `course`, it opens by confirming that interest. It can answer "what is on this site?" from the catalog, and **refuses any off-topic request** (weather/news/coding help), steering back to the interview. | DONE |
| REQ-5.5.3 | Structured extraction | The interview extracts a structured result — `interests[]` (domains/tracks), `goal`, `experience_level`, `persona`, `time_per_week` — and maps it to a **recommended track + first course**. | DONE |
| REQ-5.5.4 | Static fallback | If the user clicks "skip" or AI is unavailable (key unset / error / rate cap), a 3-tap static form (pick interests → level → goal) produces the same `LearnerProfile`. Onboarding is **never** a dead end. | DONE |
| REQ-5.5.5 | Skippable & resumable | Onboarding can be skipped ("later") and resumed from the profile; skipping still seeds recommendations from the entry intent (REQ-5.2.3). | DONE |
| REQ-5.5.6 | Cost guard | Interview length is bounded (max N turns) and uses the cheap model; respects the existing per-user token cap (REQ-1.6.6). | DONE |
| REQ-5.5.7 | Welcome basics step | Before the interview, a soft form captures: the learner's name (saved to `display_name`/`first_name`), email confirmation (+ optional extra contact email), and student/teacher/other (`LearnerProfile.role_type`, migration 0019). The interview then personalizes by name and role. | DONE |
| REQ-5.5.8 | Avi Bot persona | The interview is hosted by "Avi Bot" - Avi's photo as a small chat icon, first-person warm greeting ("excited you're here"), the house joke (the book-sharing site without the book sharing), and a one-sentence site intro - before any question. | DONE |

### 5.6 LearnerProfile & personalization

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.6.1 | `LearnerProfile` model | OneToOne with user: `interests` (JSON), `goal`, `experience_level`, `persona`, `recommended_track`, `recommended_course`, `time_per_week`, `role_type`, `contact_email`, `onboarding_completed_at`, + attribution (`source_entry_path`, `source_course`, `utm_*`, `referrer`). **Everything captured is visible to the admin** in Django admin (LearnerProfile: list columns, filters, search). | DONE |
| REQ-5.6.2 | Recommendation engine | A deterministic mapper turns interests + level + entry intent into a recommended track and first course (taxonomy-driven; no ML). Explainable ("because you're interested in AI and new to it"). | DONE |
| REQ-5.6.3 | Personalized recommendations | The "Recommended for you" rail (driven by `LearnerProfile`) appears **once** on the homepage right after onboarding, then lives **permanently on the profile page**; a ⭐ nav icon next to the user links to it (`/profile/#recommended`) so it is always reachable. The homepage stays clean afterwards. Users with no profile see nothing (generic). | DONE |
| REQ-5.6.4 | Activation hand-off | At the end of onboarding the user sees a one-line path summary + a button (no auto-jump into a lesson); it leads to the personalized homepage where the rail presents the recommendation - or to their preserved `next` if they deep-linked in. | DONE |
| REQ-5.6.5 | Onboarding checklist | A small, dismissible "get started" checklist (watch first lesson → pass a quiz → submit a reflection → enroll) shown on the profile/home until complete. | DONE |
| REQ-5.6.6 | Usage-driven recommendations | Recommendations evolve with the user's actual usage (watched lessons, completed courses, reflections) instead of the one-time interview snapshot. | DEFERRED (Avi 2026-06-12: capture the interview now, dynamic later) |

### 5.7 Measurement

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-5.7.1 | Funnel events | Plausible custom events for each funnel step: `entry`, `free_lesson_watched`, `wall_shown`, `registered`, `onboarding_started`, `onboarding_completed`, `first_lesson_completed`. | DONE |
| REQ-5.7.2 | Activation metric | Activation rate (registered → onboarding+first-lesson in first session) is derivable from the events; documented in `docs/procedures/`. | DONE |

### 5.8 Decisions log (confirmed by Avi 2026-06-12)

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-29 | Friction model | **Value-first** — explore + free preview before any wall | Best-practice (Duolingo/Coursera); lets intent build before the ask; matches the existing free-preview model |
| DEC-30 | Onboarding method | **AI interview default + user-skippable, static form fallback** | research_2: conversation > static forms; skip + fallback guarantee no dead end and respect cost/availability |
| DEC-31 | Intent storage (anonymous) | **Session + attribute-on-signup** (no anonymous DB row) | Privacy-light, simplest; persists to `LearnerProfile` only once a real user exists |
| DEC-32 | Recommendations | **Deterministic taxonomy mapper, not ML** | Explainable, testable, zero infra; the taxonomy already encodes domain/track/level |
| DEC-33 | Return-to-intent | **Django `?next=` preserved through OAuth** | Standard, robust; the single biggest conversion lever for deep-link arrivals |
| DEC-34 | Nudge policy | **Ask strictly at gated actions** — no proactive banners | Keeps exploration clean; avoids nag fatigue; the wall is the single, well-timed ask |
| DEC-35 | Corporate door | **Offer a "for your team" learner path** alongside the lead funnel | Lets a B2B visitor experience the product as a learner; complements (doesn't replace) the existing lead capture |

### 5.9 Acceptance criteria for Chapter 5

Chapter 5 is **DONE** when:
1. The access matrix (REQ-5.1.1) is authoritative, `roles.md` matches it, and no
   anonymous gated action yields a bare 403 (all route to the contextual wall).
2. A deep-link arrival (shared course/lesson link) → wall → register → lands back
   on the exact intended page, with that course seeded as the primary interest.
3. A newly registered user completes the short, taxonomy-grounded AI interview
   (or the static fallback), gets a `LearnerProfile` + a recommended track/first
   course, and chooses where to go (no auto-jump).
4. The rail shows once on the homepage post-onboarding, permanently on the
   profile, and via the ⭐ nav icon; the homepage stays clean afterwards.
5. Funnel events fire and activation rate is measurable.
6. Full regression green; non-authors/anonymous boundaries covered by tests.

---

## Chapter 6 — Community

> **Reviewed by Avi 2026-06-12** (DEC-44–47a); build started the same night on
> his explicit "build with no stop" instruction. **EPIC-6.1 + EPIC-6.2 are DONE**
> (tests test_spr_6_1/6_2.py, 30 tests; independent UX-expert review applied);
> EPIC-6.3+ remain `TODO`. Grounded in the full research corpus
> ([docs/research/](research/)): feature_skeleton Scope 2 + 5, the 15 proven
> AI-Ascent capability types (research_2), the strategic pivot to
> authority-first (research_3), and the community-architecture deep dive
> (research_4). Companion UX concept:
> [architecture/community_ux.md](architecture/community_ux.md).
> The chapter is split into **seven sequenced epics (EPIC-6.1 … EPIC-6.7)** —
> one big thing at a time, each independently shippable.

### 6.0 Vision

Turn babook from a place where people **consume** courses into a place where
they **belong**: ask and answer, show what they built, compete, share tips, and
meet each other. The community is the retention engine between courses and the
strongest authority signal for the corporate funnel (research_3: the platform
is a credibility engine — a visibly alive Hebrew AI community is proof no
competitor in Israel has).

**Design laws — why communities fail and how we don't (research_4):**

| Failure mode (research_4) | Our counter-design |
|---|---|
| Chat-only → knowledge disappears | Durable, searchable Q&A and showcases FIRST; chat later (DEC-36) |
| Creator-dependent → dies when the creator stops | Member-generated content (questions, projects, tips) is the core unit, Avi is host not engine |
| Learning disconnected from doing | Every community object can link to a course/lesson; showcases are "what I built after X" |
| No trust system rewarding quality | Reputation: points, badges, accepted answers, featured projects (the three trust loops: knowledge / skill / delivery) |
| No economy rewarding contribution | Contribution → visibility (featured, leaderboard, badges) now; monetary economy deferred (DEC-42) |

**North-star metric:** weekly active community contributors (members who post,
answer, react, or submit in a week). Secondary: % of course completers who
publish a showcase project.

### 6.1 EPIC-6.1 — Community Foundation (identity, reputation, safety)

The substrate every other epic stands on. Nothing community-facing ships
before this.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-6.1.1 | Public member profile | Opt-in public profile at `/c/<username>/`: display name, avatar, bio, role (תלמיד/מורה/אחר), badges, certificates (existing), showcase projects, contribution stats. Private by default; the user explicitly enables it. Builds on `UserProfile`/`LearnerProfile`. | DONE |
| REQ-6.1.2 | Avatars | Upload or pick a generated avatar; shown everywhere the member appears (posts, comments, leaderboards). | DONE |
| REQ-6.1.3 | Reputation points | `CommunityReputation`: points for accepted answers (+15), upvotes received (+2), published showcase (+10), challenge wins (+25), tips that get reactions (+1). Visible on profile; drives leaderboard + badge tiers. | DONE |
| REQ-6.1.4 | Badge system | `CommunityBadge` (definition) + `BadgeAward` (user, awarded_at, reason). Launch set: ראשון לענות, תשובה מקובלת, בונה (first showcase), מנטור (10 accepted answers), אלוף אתגר, מדריך (published tip ×10), tier badges (Bronze/Silver/Gold per points). AI-Ascent-proven pattern (research_2 #10). | DONE |
| REQ-6.1.5 | Follow | Follow a member → their activity appears in your feed (EPIC-6.4); follower counts on profile. | DONE |
| REQ-6.1.6 | Notifications | In-app notification center (bell icon + unread count): replies to me, accepted my answer, reactions, badge earned, challenge updates, event reminders. Email digest opt-in per type. | DONE |
| REQ-6.1.7 | Community guidelines | `/community/guidelines/` in Hebrew: respect, no spam, no solicitation, credit sources, minors-safe language. Accept-once gate before first post. | DONE |
| REQ-6.1.8 | Moderation tools | Report button on every object → staff queue in admin (hide/delete/warn/suspend); automated checks on submit (existing OpenAI moderation reuse, REQ-1.6 infra); rate limits per member. | DONE |
| REQ-6.1.9 | Minors safety | The matazim audience includes minors: public profiles for `student` role require no real-name policy enforcement, DMs disabled for students by default (EPIC-6.6), all uploads moderated. | DONE |
| REQ-6.1.10 | RTL + mobile | Every community surface is Hebrew-first RTL and works ≥360px (REQ-1.2.9/1.2.10 inherited). | DONE |
| REQ-6.1.11 | Anonymous read, member interact (DEC-45) | Logged-out visitors can READ the forum, showcase, challenges and events pages (SEO + guest funnel; extends the §5.1 access matrix). A soft, dismissible "הירשמו כדי להגיב, לדרג ולפרסם" note is shown to guests. EVERY interaction — post, answer, comment, star/rate, vote, RSVP, follow — requires login and routes anonymous users to the context-aware /join/ wall (REQ-5.4.1) naming what they tried to do. | DONE |
| REQ-6.1.13 | Avatar auto-resize | Profile avatar uploads are **downscaled + recompressed server-side** (Pillow → ≤512px JPEG, EXIF-oriented, transparency flattened) instead of being rejected for size, so any reasonable photo (incl. straight off a phone) just works. Only a sane input cap (15MB) and non-image files are refused, with a friendly message. | DONE |

### 6.2 EPIC-6.2 — Forums & Q&A (durable knowledge)

The knowledge trust-loop. Q&A-first (not chat) so knowledge accumulates and is
searchable — the #1 lesson from research_4.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.2.1 | Forum structure | Categories mirror the taxonomy (AI / מטצים / חדשנות) + רמות + "כללי". A thread is a Question or a Discussion. | DONE |
| REQ-6.2.2 | Q&A mechanics | Answers, voting (up only — friendlier than up/down for a Hebrew learning community), **accepted answer** marked by the asker (or staff), accepted floats to top. | DONE |
| REQ-6.2.3 | Rich posts | Markdown (same renderer as lessons): fenced code blocks, images, links; preview before post. | DONE |
| REQ-6.2.4 | Tags & search | Tags (topic, course slug, difficulty); search across titles+bodies (icontains now, FTS5 when scale demands); filter by unanswered / mine / following. | DONE |
| REQ-6.2.5 | Course-anchored threads | "שאלו את הקהילה" button on every lesson opens a pre-tagged thread; the lesson page shows its open threads. Connects learning to doing. | DONE |
| REQ-6.2.6 | Canonical / pinned | Staff can pin threads and mark canonical answers (Solutions-Hub pattern, feature_skeleton 2.5); canonical content surfaces in search first. | DONE |
| REQ-6.2.7 | AI assist | (a) On posting a question, AI suggests existing similar threads + relevant lessons before submit; (b) threads >10 replies get an AI summary box; (c) optional "Avi Bot draft answer" visible to staff for one-click post. Reuses REQ-1.6 infra. | DONE |
| REQ-6.2.8 | Subscriptions | Follow a thread/category → notification on activity (REQ-6.1.6). | DONE |

### 6.3 EPIC-6.3 — Showcase: דוכן השוויץ (exhibitions / bragging page)

The skill trust-loop and the emotional core of the community: "תראו מה בניתי".
Proven as AI-Ascent capability #14 (Exhibition/Portfolio, Sprints 26-30).
**Naming (DEC-44):** the playful title stays — «דוכן השוויץ» — with a formal
subtitle: «גלריית הפרויקטים של קהילת babook». Two complementary surfaces
(DEC-48): a **stable curated wall** (grid, featured, by stand) and a **flowing
brag feed** (chronological pulse of new projects + reactions). Members organize
their show-off into **stands** (DEC-49) — AI, makers/hardware, retro games,
personal sites, research, apps — and engage via stars, emoji reactions,
comments, and direct messages (DEC-50). Built rich and gamified.

**6.3.a — Projects, stands & wall**

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.3.1 | Project model | `ShowcaseProject`: title, tagline, story (markdown), stand, cover image, gallery (multiple images), demo video (YouTube/Bunny embed), repo/live links, course link ("נבנה בעקבות הקורס X"), tags, status (draft/published), featured flag, published_at. | DONE |
| REQ-6.3.2 | Exhibition wall | `/community/showcase/` — a visual masonry/grid wall; **"נבחרת השבוע"** featured row (staff-curated); filterable by **stand**, course, tag; sortable (חדש / הכי מוערך). | DONE |
| REQ-6.3.8 | Show-off stands (categories) | Distinct stands, each its own page `/community/showcase/stand/<slug>/` with title/icon: כלי AI · מייקרים וחומרה · משחקים ורטרו · אתרים אישיים · מחקר ואקדמיה · אפליקציות ואוטומציות · אחר. New stands are a one-line addition (DEC-49). | DONE |
| REQ-6.3.9 | Create / edit / publish | Rich authoring: cover + gallery upload, video URL, stand picker, markdown story with live preview (reuse forum preview), tags, draft→publish; edit + delete own projects. | DONE |
| REQ-6.3.7 | Student work safety | Projects by `student` role members enter a `pending` review state; staff approve before public listing (REQ-6.1.9). | DONE |

**6.3.b — Engagement: reactions, comments, brag feed, sharing**

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.3.3 | Reactions | **Star** (⭐, the primary signal — toggle, count drives wall ranking; awards the author +1 and notifies) **+ emoji reactions** (🔥 ❤️ 👏 🤯, lightweight flavor, no points), one per member per type. Self-reaction disabled. | DONE |
| REQ-6.3.10 | Comments | Per-project comments (markdown, same moderation + rate-limit pipeline as the forum); notify the project author; report button. | DONE |
| REQ-6.3.11 | Brag feed | `/community/showcase/feed/` — a flowing chronological feed of newly published projects with their cover, builder, stand, and live reaction counts. The pulse of "look what people are building". | DONE |
| REQ-6.3.6 | Sharing | Per-project page sets Open Graph tags (cover + title + tagline) so it looks great on WhatsApp/LinkedIn; copy-link + WhatsApp share buttons. The community's organic-growth surface. | DONE |

**6.3.c — Messaging, integration & gamification**

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.3.12 | Direct messages | Member-to-member DMs (e.g. "אהבתי, איך בנית את X?") with an inbox + conversation view; opt-in, **disabled for `student` role** both ways (DEC-41); block + report; notifies recipient. Pulled forward from EPIC-6.6 because show-off naturally invites "tell me how". | DONE |
| REQ-6.3.5 | Profile portfolio | A member's published projects appear on their public profile (REQ-6.1.1) — a portfolio for free; the public-proof layer of micro-credentials. | DONE |
| REQ-6.3.4 | Course & certificate integration | Course detail shows projects built from that course; the certificate page invites "פרסמו מה בניתם" with the course pre-linked — the natural bragging moment. | DONE |
| REQ-6.3.13 | Gamification | Points: publish (+10), star received (+1), featured (+15). Badges: בונה (first project), אמן התצוגה (5 projects), כוכב עולה (a project hits 25 stars), מוצג נבחר (staff-featured). "נבחרת השבוע" featured row; reaction-milestone notifications. | DONE |
| REQ-6.3.14 | Community feed + home hook | Showcase events feed the community home "מהקהילה" strip and Plausible (`project_published`, `project_reaction`); a "השוויצו" CTA on `/community/`. | DONE |
| REQ-6.3.16 | Live-site cards | For projects with a `live_url` and no uploaded cover, the card + detail auto-show a **live screenshot** of the site (favicon fallback); the cover click opens the live site; a star button + comment count + «בקרו» CTA live on the card itself (no need to open the project). | DONE |
| REQ-6.3.17 | Stored site screenshot | When a project has a live site and no uploaded cover, a screenshot is captured **once** (free service, no token cost) and saved as the project cover, so cards load instantly. Captured in the background on save + on first view of existing projects; `capture_showcase_covers` backfills. | DONE |

### 6.4 EPIC-6.4 — Feed & Tips

The pulse. Makes the community feel alive on every visit, and gives members a
lightweight way to contribute (a tip is 10× easier than a project).

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.4.1 | Community feed | `/community/` home: chronological feed of activity cards — new projects, accepted answers, fresh questions, badges earned, challenge milestones, new tips, upcoming events. Filter: הכל / אני עוקב / התחום שלי (uses LearnerProfile interests). No engagement-bait algorithm (DEC-40). | DONE — events join when EPIC-6.7 lands |
| REQ-6.4.2 | Tips | `Tip`: short-form post (≤2,000 chars, markdown, optional image/link) — "טיפ: ככה אני גורם ל-Copilot…". Tagged by domain/tool; reactions; best tips surface weekly. | DONE |
| REQ-6.4.3 | Feed composer | One "שתפו משהו" box on the feed: tip / question (routes to forum) / project (routes to showcase) — one entry point, right destination. | DONE |
| REQ-6.4.4 | Weekly digest | Reuse the newsletter infra (REQ-2.5): weekly Hebrew email — top tip, featured project, best answer, upcoming events. Opt-in. **Gated (DEC-46): starts only once the community passes ~50 active members**; until then the feed alone carries the pulse. | DONE (scaffold) — `digest_opt_in` + `send_weekly_digest` command built; stays dormant below the threshold |
| REQ-6.4.5 | Homepage hook | The logged-in homepage shows a compact "מהקהילה" strip (3 cards) linking into the feed — discovery without clutter (respects the clean-homepage decision from Ch.5). | DONE |

### 6.5 EPIC-6.5 — CrashTech: Hardware Hackathon Platform

**Source:** [docs/Epic6.5.t.md](Epic6.5.t.md) (CrashTech spec v0.1). This epic
**replaces** the earlier lightweight challenges draft (DEC-55). CrashTech is a
hardware-centric, timed hackathon module hosted inside babook: babook **is** the
host system (CrashTech owns no auth — it grants per-hackathon roles to existing
babook users). Teams receive physical kits (ESP32/FPGA) ~2 weeks ahead, practice
off a linked GitHub repo, then compete in a fixed window (default 24h) to solve
secret challenges judged for points, ending in a permanent public Glory Page.

**Lifecycle:** `SETUP → READINESS (~2wk) → LIVE EVENT (~24h) → CLOSED → GLORY (permanent)`.

**Scoring is dual:** breadth (pass/fail challenges solved) + performance/creativity
(organizer ranks top-N → bonus tiers). Public surfaces are anonymized; a team's
own dashboard is full detail; judging is blind (DEC-57).

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.5.1 | Hackathon model & lifecycle | `Hackathon`: name, start/end, duration, team_size, submission deadline, `github_repo_url`, `hardware_stock`, `status` (setup/readiness/active/closed/glory), organizer. State machine drives what every surface allows. | DONE |
| REQ-6.5.2 | Per-hackathon roles | `HackRole` (hackathon × user × role): organizer / admin / judge / participant. Many-to-many; a user may hold several roles on one event and different roles across events. Organizer-only powers (bonus points, config, judge assignment) stay gated even when the organizer also judges. | DONE |
| REQ-6.5.3 | Setup: hackathon config | Organizer creates/configures a hackathon (name, dates, duration, team size, deadline, GitHub repo URL, hardware stock). Stock caps the number of teams. | DONE |
| REQ-6.5.4 | Setup: challenge authoring | Organizer defines `Challenge` (title, description/brief, point_value, scoring_mode = pass_fail \| performance_creativity, top_submission_count, bonus_points_tiers[], visible). Challenges are **secret** (`visible=false`) until kickoff. | DONE |
| REQ-6.5.5 | Setup: judge assignment | Organizer assigns judges from existing babook users. | DONE |
| REQ-6.5.6 | Readiness: invite participants | Organizer/Admin search babook users + invite; invitee gets an email and joins the hackathon as a participant. | DONE |
| REQ-6.5.7 | Readiness: team formation | Organizer/Admin create/name teams and assign members; team size bounded by the organizer's setting; cannot exceed available hardware stock. | DONE |
| REQ-6.5.8 | Readiness: hardware tracking | Per-team `hardware_status` pending → shipped → received; marking supplied decrements stock; team creation blocked beyond stock. Inventory view (stock/shipped/received). | DONE |
| REQ-6.5.9 | Readiness: practice + countdown | Participants access the linked repo/example solutions; a countdown-to-start is visible to all invited participants. | DONE |
| REQ-6.5.10 | Live: kickoff & event hub | At kickoff all challenges become visible on the Event Main Page (countdown, challenge list, team status). A prominent deadline countdown shows everywhere during the event. | DONE |
| REQ-6.5.11 | Live: submission | A team submits per challenge: **video demo ≤20s** (paste a YouTube link **or** scan a per-team/per-challenge QR token that opens a phone upload form, the token binding the upload to the right team+challenge) **+ source code as a zip uploaded to the site** (DEC-56). Each submission enters a pending queue. | DONE |
| REQ-6.5.12 | Live: judging (blind) | Judges review video+code with team identity **hidden** (DEC-57) and approve/reject pass/fail challenges, each rejection carrying a feedback note. Points count **only after approval**. | DONE |
| REQ-6.5.13 | Live: bonus scoring | **Organizer only** ranks the top-N submissions of a performance/creativity challenge and awards bonus points per rank from `bonus_points_tiers[]`. Judges cannot. | DONE |
| REQ-6.5.14 | Live: resubmission | A rejected/improvable submission can be resubmitted within the window; resubmission resets `status → pending`. Unlimited until the gate closes (DEC-59). | DONE |
| REQ-6.5.15 | Live: anonymized leaderboard | Public leaderboard shows each team under a **stable per-hackathon anonymous label** ("Team One…") with approved points (+bonus) and a **separate pending** indicator; no names, no per-challenge detail. | DONE |
| REQ-6.5.16 | Live: deadline gate | At the deadline (24h or organizer-defined) gates close; submissions are hard-blocked. | DONE |
| REQ-6.5.17 | Glory: certificates | On close, generate certificates: participation for all; winner/runner-up for top teams. Tie-break: most challenges solved → earliest final qualifying submission → most bonus placements (DEC-59). | DONE |
| REQ-6.5.18 | Glory: memorial page | Permanent, public `GloryPage` per hackathon: final rankings, highlights, **consented** videos + event photos; organizer curates and publishes. Winners revealed; others anonymous unless consented (DEC-59). | DONE |
| REQ-6.5.19 | Consent | Glory-page publication consent collected **up-front at team setup**, with a **post-event opt-out** once teams see what would be published (DEC-58). | DONE |
| REQ-6.5.20 | Public surfaces | Anonymized public leaderboard + anonymized solution-video gallery (no team attribution), plus the permanent Glory Page. Read-public (REQ-6.1.11 spirit). | DONE |
| REQ-6.5.21 | Notifications | Event reuses `notify()`: event starting, challenges unlocked, submission approved/rejected, deadline approaching. | DONE |

### 6.6 EPIC-6.6 — Chat & Groups (real-time, after the durable layer)

Deliberately AFTER forums/showcase (DEC-36): chat amplifies a live community,
it cannot create one. Scoped to what SQLite/Render handles (**polling**, no
websocket infra — same pattern proven by the studio-job poller and AI chat).
Every chat surface reuses the existing community spine — guidelines gate
(REQ-6.1.7), AI moderation + rate-limit (REQ-6.1.8), minors safety (REQ-6.1.9),
anonymous-read / login-to-post (DEC-45), notifications (REQ-6.1.6), Hebrew RTL
+ mobile (REQ-6.1.10) — so chat feels native to the site, not bolted on.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.6.1 | Channels | Persistent public **topic channels**: one per taxonomy domain (AI / מטצים / חדשנות) + «כללי», auto-created from code (DEC-49 pattern). A channel view streams messages newest-at-bottom with **JS polling** refresh; history persists and is **searchable**. Read-public; posting requires login → the `/join/` wall (DEC-45). Surfaced on `/community/` and the nav. | DONE |
| REQ-6.6.2 | Course groups + presence | Each course has an optional **members-channel** (cohort feel), reachable from the course page. A "**למדו איתי**" presence row shows members active in that course recently (derived from `UserVideoProgress`, last ~15 min) — live cohort signal without heavy infra. | DONE |
| REQ-6.6.3 | Direct messages (reconciled) | Member-to-member DMs + inbox + thread + block + report shipped in EPIC-6.3 (DEC-50). 6.6 adds the privacy **control**: a profile toggle «קבלת הודעות אישיות» — default **ON for adults** (consistent with the showcase "message the builder" flow, DEC-61), always **OFF for `student` role** (REQ-6.1.9). Honored by `can_message`. | DONE |
| REQ-6.6.4 | Find collaborators | The `/community/members/` directory gains **filters** (domain interest, experience level, role) and a «**פתוח לשיתופי פעולה**» filter + badge (using `open_to_collab`); links to each member's public profile + (allowed) DM. | DONE |
| REQ-6.6.5 | Knowledge capture | A valuable channel message can be **promoted in one click** (author or staff) into a forum thread (question/discussion) or a tip, pre-filled from the message — chat never traps knowledge (anti-failure #1). Links back to the source channel. | DONE |
| REQ-6.6.6 | Channel safety & mentions | Every message runs the moderation + rate-limit pipeline; a **report** action per message → the existing staff queue; **@mention** a member → a notification (REQ-6.1.6). Students may participate in public topic channels (moderated, public, no private contact) but never get DMs or presence exposure beyond the public room (REQ-6.1.9). | DONE |
| REQ-6.6.7 | Live hackathon channel | Each **active CrashTech hackathon** (EPIC-6.5) gets an auto-linked channel for live buzz during the event, retired to read-only when the event closes — ties the real-time layer to the flagship event. | DONE |

### 6.7 EPIC-6.7 — Events & Meetups

Belonging → conversion: "מפגש live ממיר lurkers ל-contributors" (research_4).
Also the natural bridge to the corporate funnel (sponsors, exposure).

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.7.1 | Event model | `CommunityEvent`: title, description (markdown), type (live-coding / AMA / hackathon kickoff / meetup / כנס), online link **or** venue, start/end, capacity, host, optional series + linked hackathon/course; recording (Bunny embed) after the fact. Read-public (DEC-45). | DONE |
| REQ-6.7.2 | Registration | RSVP (login-gated) + downloadable **.ics** calendar file + reminder notifications (24h, 1h); **waitlist** when at capacity, auto-promoted (and notified) when a seat frees. | DONE |
| REQ-6.7.3 | Events page | `/community/events/`: upcoming + past; an event detail page; past events show the **recording** (Bunny embed) + linked threads/projects/hackathon. | DONE |
| REQ-6.7.4 | Recurring formats | `EventSeries` (e.g. «שעת מומחה חודשית עם אבי») with a series page listing all its sessions; an event may belong to a series. | DONE |
| REQ-6.7.5 | Physical meetups | Venue events (TLV/JLM/Haifa) with **attendance check-in** (a per-attendee code/toggle) and event **photos** that feed back into the community feed. | DONE |
| REQ-6.7.6 | Feed & hub integration | Upcoming events surface in the community feed (the slot REQ-6.4.1 reserved), on the `/community/` hub, and in notifications; an event of type «hackathon kickoff» links to its CrashTech event. | DONE |

### 6.8 Cross-cutting: measurement & health

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.8.1 | Community events (Plausible) | A server→client bridge (`flash_event`, mirroring the §5 entry-event pattern): community actions stash a Plausible event in the session, fired by `base.html` on the next page. Wired into `community_post`, `answer_accepted`, `project_published`, `tip_posted`, `event_rsvp` (+ existing `project_reaction`). | DONE |
| REQ-6.8.2 | Health dashboard | Staff-only `/staff/community-health/`: weekly active contributors, unanswered-question rate + time-to-first-answer, projects/week, tips/week, RSVPs, open report-queue size — the community's vital signs at a glance. | DONE |
| REQ-6.8.3 | Activation tie-in | Onboarding (Ch.5) gains a community beat: the home get-started checklist adds «הצטרפו לקהילה» (links to `/community/`), and the Avi Bot opener mentions the community. | DONE |

### 6.9 Deferred (explicitly out of scope for Chapter 6)

Per research_1 "don't launch with advisors" and research_3's authority-first
model — these wait until the community is demonstrably alive:

| Item | Why deferred |
|---|---|
| Skill marketplace (creator economy, 70/30) | Needs critical mass + payments (Stripe still DEFERRED) |
| Advisor/mentor marketplace (paid 1:1) | Needs trust graph + payments; soft-launch later with ~5 advisors |
| Hiring board | Needs employer demand; community proof first |
| Token wallet / credits store | Separate scope (Scope 3), unrelated to community UX |
| Algorithmic feed / engagement optimization | DEC-40 — chronological + curated only |

### 6.10 Decisions log (confirmed by Avi 2026-06-12)

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-36 | Build order | **Durable knowledge first** (foundation → forums → showcase → feed → challenges → chat → events) | research_4: chat-only communities die; knowledge must accumulate before real-time |
| DEC-37 | Reputation currency | **Points + badges + featured visibility** (no monetary economy yet) | Rewards contribution (anti-failure #5) without payments complexity |
| DEC-38 | Voting | **Upvote-only + accepted answer** (no downvotes) | Friendlier for a Hebrew learning community incl. minors; accepted answer carries the quality signal |
| DEC-39 | Challenges ≠ Kaggle | **Course-anchored, human-judged, showcase-producing** | research_1 explicit warning; fits learning community, not ML-metric racing |
| DEC-40 | Feed | **Chronological + staff-curated featured; no engagement algorithm** | Trust + simplicity; the site's tone is human, not addictive |
| DEC-41 | Minors safety | **Student role: no DMs, reviewed publishing, moderated uploads** | matazim audience includes minors; non-negotiable |
| DEC-42 | Monetary community economy | **Deferred** (marketplace/advisors/hiring in 6.9) | research_3: authority first; payments infra (Stripe) still deferred |
| DEC-43 | Tech envelope | **Stay on Django/SQLite: polling/SSE, no websockets/Redis** | One deploy unit; the studio + chat patterns already proven on this stack |
| DEC-44 | Showcase naming | **«דוכן השוויץ» + formal subtitle «גלריית הפרויקטים של קהילת babook»** | Avi: partially formal, partially humoristic; ratings + comments are core |
| DEC-45 | Anonymous access | **Read-public (forum/showcase/challenges/events) + soft register note; ALL interactions require login via the /join/ wall** | Avi confirmed; SEO + guest funnel without anonymous noise |
| DEC-46 | Digest timing | **Gated: explore the weekly digest only after ~50 active members** | Avi: no point emailing an empty room; the feed carries the pulse first |
| DEC-47 | Leaderboard | **Public with opt-out** (Claude's recommendation, AI-Ascent-proven); students appear by display name only (REQ-6.1.9) | Opt-in leaderboards stay empty — defaults drive participation; opt-out + minors naming rule keeps it safe |
| DEC-47a | First challenge | **MicroPython kit** (matazim/hardware, tied to `micropython-thonny`) | Avi's pick; physical-kit projects photograph beautifully on the wall |
| DEC-48 | Showcase surfaces | **Both a stable curated wall AND a flowing brag feed** | Avi: the wall is the portfolio/gallery; the feed is the live pulse — they serve different moments |
| DEC-49 | Stands (categories) | **Code-defined stand set, extensible one-line** (AI / makers / games / web / research / apps / other) | Curated titles+icons+order, RTL-correct; new stands are cheap to add, no model overhead |
| DEC-50 | Messaging in 6.3 | **Pull DMs forward from EPIC-6.6** into the showcase (opt-in, student-disabled) | Avi asked for messaging; show-off naturally invites "tell me how you built it"; full chat/channels still in 6.6 |
| DEC-55 | EPIC-6.5 = CrashTech | **CrashTech (hardware hackathon platform) replaces the old challenges-as-showcase draft** | Avi 2026-06-13: full hardware-hackathon module per docs/Epic6.5.t.md; old REQ-6.5.1–8 retired (MicroPython kit can be a CrashTech event) |
| DEC-56 | Submission code channel | **Source code = zip uploaded to the site** (the hackathon GitHub repo holds starter/tutorial code only) | Avi 2026-06-13: overrides the doc's GitHub-URL recommendation; simplest for participants |
| DEC-57 | Judging | **Blind to judges** (team identity hidden in the UI); organizer de-anonymized for bonus ranking | Avi 2026-06-13: reduces bias. NB: best-effort — code contents are not auto-anonymized |
| DEC-58 | Glory consent | **Up-front at team setup + post-event opt-out** | Avi 2026-06-13: simple early signal, safe final say once teams see the published content |
| DEC-59 | CrashTech defaults (doc §9) | **Unlimited resubmission; pending anonymized like approved; tie-break most-solved → earliest qualifying → most bonus; winners revealed on Glory, others anonymous unless consented** | Avi accepted the documented defaults |
| DEC-60 | Chat tech + minors | **Polling (no websockets/SSE infra); students MAY join public topic channels (moderated, public, no private contact) but never DMs/presence beyond the public room** | Stays in the Django/SQLite envelope (DEC-43); public moderated chat is as safe as the forum, which already allows students |
| DEC-61 | DM control | **DMs default ON for adults (opt-OUT via a profile toggle), always OFF for students** — supersedes the original 6.6.3 "opt-in default OFF" | The showcase "message the builder" flow (DEC-50) already shipped DMs ON; a default-OFF gate would silently break it. A clear opt-out gives control without regressions |

### 6.11 Acceptance criteria for Chapter 6

Chapter 6 is **DONE** when, in production: a member has a public profile with
badges and a portfolio; questions get answered and accepted with knowledge
searchable; projects are published on the exhibition wall and shared outward;
the feed shows a living community and a weekly digest goes out; a full
challenge cycle (brief → submissions → judging → winners) has run; channels
and member directory operate with minors-safe defaults; an event has run end
to end with RSVP and recording; the health dashboard reports weekly active
contributors; and the full regression is green with every epic's tests.

### 6.12 Community UX Polish (post-build fresh-eyes review)

After Chapter 6 was built, a full UX audit (forms / IA / flows) found the
skeleton strong but the experience scattered, with two broken paths. This
section makes the community **friendly and flowing**. Grouped REQs:

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.12.1 | Composer continuity | Text typed in the «שתפו משהו» box carries to the forum/showcase form (no lost text); the three CTAs are visually equal with a one-line hint of what each does. | DONE |
| REQ-6.12.2 | CrashTech self-service teams | Participants can create or join a team themselves (capacity + hardware-stock guarded); an invited-but-unteamed participant sees a clear "form/join a team" state, never a dead-end of challenge cards with no submit UI. | DONE |
| REQ-6.12.3 | Global messages renderer | One Django-messages block in `base.html` so every redirect target shows its flash; remove the ~24 local copies; replace `alert()`/`prompt()` report flows with the styled pattern. | DONE |
| REQ-6.12.4 | Mentions | @mention gains an affordance (hint/datalist) and matches the displayed name → username; a promoted chat message is marked so it isn't promoted twice. | DONE |
| REQ-6.12.5 | Lean forms | Showcase media/links (video/repo/live/gallery) collapse behind an optional disclosure (first publish = title→story→publish); the challenge form hides performance-only fields for pass/fail; events default `end_at` to start+1h and toggle online-url/venue by `is_online` with a series datalist; the avatar size label matches the real 15MB limit. | DONE |
| REQ-6.12.6 | Event RSVP polish | Cancel asks confirm; the .ics download is offered only after RSVP; event list cards get a one-click RSVP. | DONE |
| REQ-6.12.7 | Chat send polish | Posting a message uses fetch + optimistic append (no full reload); the promote-to-forum/tip actions are labeled, not bare emoji. | DONE |
| REQ-6.12.8 | Activation coupling | Posting any public content auto-publishes the profile (the "join the community" banner stops lingering); the `/join/` wall gains named intents for tip/showcase/chat. | DONE |
| REQ-6.12.9 | Community IA: one door | `/community/` gets an «אזורי הקהילה» tile strip covering all 8 areas; CrashTech is folded under קהילה (nav + breadcrumb); the private-DM icon becomes an envelope (distinct from community chat); the «עולמות» dropdown drops unbuilt placeholders; chat/events/CrashTech empty states gain a CTA. | DONE |
| REQ-6.12.10 | Dead-code cleanup | Verify + fix the showcase auto-cover (`site_url` never set by the form) and the unused `tip_create` `link_url` field. | DONE |

---

## Chapter 7 — QA Hardening

> **From Avi's 2026-06-13 QA walkthrough.** Every item logged in the (temporary)
> `docs/qa_session.md` is promoted here to a tracked REQ, built the_manager.md way
> (TDD → regression → deploy), then that scratch file is deleted. Avi authorized
> building the whole chapter in one pass ("do it all, don't stop, report at the
> end"). Decisions: QA-1 → real email verification (password path); QA-13 intros
> → Bunny upload; design → Khan-Academy style, light default + dark toggle.

### 7.1 Quick wins (nav, hero, content, footer, login)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.1.1 | Remove EN toggle (QA-9) | The language switcher is removed; site is Hebrew/RTL only. | DONE |
| REQ-7.1.2 | Nav shows name + avatar (QA-10) | Nav user item shows `public_name` (display_name → first_name → username fallback) + avatar circle when set. | DONE |
| REQ-7.1.3 | Label recommendations (QA-11) | The ⭐ nav item shows a visible «מומלץ עבורך» label on all breakpoints. | DONE |
| REQ-7.1.4 | Hero first-day-only (QA-12) | The homepage hero joke + «העולמות» intro show only within 24h of signup; hidden afterward. | DONE |
| REQ-7.1.5 | Arduino course order in titles (QA-15) | `arduino-tinkercad` title marked #1, `arduino` #2 (confirmed via matazim). | DONE |
| REQ-7.1.6 | Remove chat from nav (QA-17) | «צ'אט AI» nav link removed; `/chat/` route left dormant. | DONE |
| REQ-7.1.7 | Profile enrich-later hint (QA-5) | A note (onboarding end + profile) that the user can add avatar/bio/more later in their profile. | DONE |
| REQ-7.1.8 | Cookie consent logged (QA-18) | Standard consent popup on first visit; acceptance recorded server-side (`CookieConsent` log). | DONE |
| REQ-7.1.9 | Footer "connect with Avi" + photo (QA-20) | Footer CTA «רוצים להתחבר לאבי סלמון?» → contact form; Avi's background-removed photo (generated from `docs/Avi_03.jpg`) on the contact form. | DONE |
| REQ-7.1.10 | Google button starts OAuth directly (QA-22) | Login/register «המשך עם גוגל» hits the provider-login URL directly (no `/accounts/login/` detour). | DONE |

### 7.2 Onboarding rework (conversational, verified)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.2.1 | Email mandatory + verified (QA-1) | Email/password signup requires an email; a verification link is sent and required (Google stays trusted). Closes the forgot-password hole. Revises REQ-1.1.3. | DONE |
| REQ-7.2.2 | Conversational basics (QA-2) | The welcome basics (name / email-confirm / role: student·teacher·professor·industry-engineer·other) are collected **in the Avi Bot chat**, not a form. Revises REQ-5.5.7. | DONE |
| REQ-7.2.3 | Fixed instant opener (QA-6) | The chat's first message is a hardcoded, instant, name-personalized greeting (verbatim copy in qa_session.md), not AI-generated. | DONE |
| REQ-7.2.4 | Site intro + interests + remember (QA-3) | The chat introduces the site + the book joke, asks interests, and persists them (attributes + free-text description on the profile). | DONE |
| REQ-7.2.5 | Finishable, name-only required (QA-4) | A "done" button ends onboarding anytime; the only hard requirement is the name (email enforced at signup). No nagging. | DONE |
| REQ-7.2.6 | Enrich-later, not in entry (QA-5/tone) | Entry chat stays short; profile enrichment (pictures/hobbies) is offered for later, not required. Avi Bot persona throughout. | DONE |
| REQ-7.2.7 | No username at signup | The register form collects name + email + password only; the username is **auto-derived from the email** (unique-ified). | DONE |
| REQ-7.2.8 | Google-first register | The register page leads with **Google/GitHub** (preferred, prominent on top); the email/password form is the secondary option below a divider. | DONE |
| REQ-7.2.9 | Soft-verify, visible journey | Email verification is **non-blocking**: signup logs the user in and routes to `/welcome/`, which shows an explicit "📧 sent a verification email to your address, click the link" notice for unverified accounts; the site-wide banner reminds until verified. Resend renders a clear **"verification sent"** confirmation page (not a silent redirect to profile). Clarifies the journey QA reported as confusing. | DONE |
| REQ-7.2.10 | Self-service account deletion | The profile page offers **delete account** (`/account/delete/`): a confirmation page requiring the user to retype their email, then permanently deletes the user (cascades), logs out, and **frees the email for re-registration**. Profile now also renders Django messages so success toasts are visible. | DONE |

### 7.3 Matazim course intros (QA-13)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.3.1 | Insert intro as lesson 1 | For each of the 9 matazim courses, the course-page intro video (mapped + extracted from matazim) is inserted as the new lesson 1 (existing lessons shift down), uploaded to Bunny. Mapping table in qa_session.md. | DONE |

### 7.4 Design Refresh (QA-7 / QA-8 / QA-21)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.4.1 | Khan-style visual language (QA-21) | Restyle the design tokens/type/components to a bright, clean, friendly Khan-Academy-like look; **light default**; Hebrew RTL; keeps babook personality. Behavior unchanged. | DONE |
| REQ-7.4.2 | Theme toggle (QA-7) | Light (new default) + Dark themes via `data-theme`; choice persists (profile + cookie); switch in menu/profile. | DONE |
| REQ-7.4.3 | Animated background (QA-8) | Opt-in animated background presets (e.g. stars / gears / particles / none) chosen in profile; respects `prefers-reduced-motion`; subtle, perf-safe. | DEFERRED |

### 7.5 Content re-transcription (QA-14)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.5.1 | Re-transcribe scraped courses | Re-transcribe imported courses with the strongest OpenAI model + regenerate faithful high-quality Hebrew notes (Co-Coding method: no em-dashes, fenced code/cmd). Runs as a controlled batch (DB backup first). Long-running. | WIP — tooling ready; supervised batch pending |

### 7.6 Contact email reliability (QA-19)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.6.1 | On-site contact capture + admin notify | Contact/privacy/support routes store the message on-site (admin-visible) and email Avi's admin inbox, so nothing depends on a possibly-dead `privacy@`/`support@` mailbox. **ACT-Avi:** set up the actual mailbox forwarding (DNS). | DONE |

### 7.8 Global navigation hierarchy (QA-16)

> **Correction (2026-06-13):** QA-16 was reported DONE in the build summary but
> had **no REQ and no feature** — only a few page types carried hand-placed
> breadcrumbs, with no back button and nothing on most pages. Now built for real
> as a global element.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-7.8.1 | Breadcrumb + back on every view | A single global bar (in `base.html`, driven by `breadcrumbs_ctx`) renders a "you are here" trail on every page: «בית › section › subsection …», each ancestor a clickable link, plus a «חזרה» back button. Trails come from a central map (`app/breadcrumbs.py`); detail pages override `{% block breadcrumb %}` to show the real course/project/thread title. Chrome-free on home/auth/onboarding. | DONE |

### 7.7 Decisions log

| ID | Topic | Choice |
|---|---|---|
| DEC-51 | QA email verification | Real verification link on the email/password path; Google trusted |
| DEC-52 | QA intro videos | Download + upload to Bunny (consistent player) |
| DEC-53 | QA design direction | Khan-Academy style, **light default** + dark toggle |
| DEC-54 | QA build mode | Whole chapter built in one autonomous pass; review at the end; then delete `qa_session.md` |

---

## Chapter 8 — Admin / Management Control Dashboard

> **Spec approved by Avi 2026-06-14** (idea + DEC-62–67); **built the same day**
> in one autonomous pass (EPIC-8, tests `tests/test_spr_8.py` — 21 tests; full
> regression 602 passing). All `REQ-8.*` are `DONE`; live values for a few cost
> adapters tune later via ACT-23–26 (graceful estimate/manual fallback meanwhile).
> Same conventions as Chapters 1-7 (`REQ-<chapter>.<group>.<n>`, status
> `TODO`/`WIP`/`DONE`/`BLOCKED`/`DEFERRED`; decisions `DEC-*`; Avi actions
> `ACT-*`). Builds on existing telemetry: `UsageLog` (REQ-1.6.7), the Copilot
> admin dashboard (REQ-1.5.8), Plausible funnel events (REQ-5.7 / REQ-6.8.1),
> and the staff community-health view (REQ-6.8.2).

### 8.0 Vision

Today babook's operating signals are scattered — OpenAI cost lives in `UsageLog`,
Copilot spend in one admin page, community vitals in `/staff/community-health/`,
training progress only in raw models, and external spend (Bunny, Resend, Render,
Plausible) nowhere on-site at all. The admin (Avi) has no single place to answer,
every day, **"how is babook doing — people, money, and pulse?"**

Chapter 8 delivers **one admin-only cockpit** at `/admin-dashboard/` that answers
that at a glance, across three pillars:

1. **People & training** — who is here, who actually learns, and which courses win.
2. **Money** — what every paid service costs, pulled live from provider APIs where
   they exist, estimated + manually maintainable where they don't, each with a
   deep link out to the provider's own console.
3. **Pulse & health** — engagement across the whole community surface, plus system
   vitals (deploys, backups, DB, health).

The dashboard is **read-first** but not passive: it raises **threshold alerts**
(budget, queue backlog, unanswered questions, failed backup) through the existing
`notify()` + email infra.

**Design envelope:** stays inside Django/SQLite (DEC-43 spirit) — no new infra.
External data is fetched on a **nightly snapshot** (with manual per-section
refresh) so page loads are instant and provider rate limits are respected, and so
trends come for free. Cost ingestion is built as **pluggable per-service adapters**
so a service that lacks a usable billing API today can still appear (estimate +
manual figure + deep link) and be upgraded to live later without touching the UI.

**Access is the admin only** — strictly superuser, stricter than staff.

**North-star for this epic:** the admin opens one page each morning and needs no
other tool to know the site's people, spend, and health.

### 8.1 Dashboard foundation & access

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.1.1 | Dashboard hub | `/admin-dashboard/` renders a sectioned cockpit (Users & Training, Costs, Engagement, System) with at-a-glance summary cards at the top and links into each section. RTL, mobile-readable, reuses the site design system. | DONE |
| REQ-8.1.2 | Admin-only access | Every `/admin-dashboard/*` route is **superuser-only** (`@superuser_required` or equivalent) — stricter than `@staff`. Non-superusers (incl. staff) get the standard not-authorized response; the nav entry to the dashboard shows **only** to superusers. | DONE |
| REQ-8.1.3 | Snapshot model | `DashboardSnapshot` (captured_at, scope, JSON metrics) + `CostRecord` (service, period, amount_usd, source = `live`/`estimate`/`manual`, fetched_at, raw JSON, note) persist each capture so the dashboard loads instantly from the latest snapshot and trends are derivable. | DONE |
| REQ-8.1.4 | Nightly capture | A management command `capture_dashboard_snapshot` (schedulable like the other cron jobs) collects all internal metrics and runs every cost adapter, writing a `DashboardSnapshot` + `CostRecord` rows. Safe to run repeatedly; partial failure of one adapter never aborts the rest. | DONE |
| REQ-8.1.5 | Manual refresh | Each section has a "refresh now" control that re-runs just that section's collectors on demand and updates its snapshot, with a visible "last updated" timestamp per section. | DONE |
| REQ-8.1.6 | Time range & trends | A range selector (today / 7d / 30d / 90d / all) drives every section; metrics show current value **and** a trend (sparkline or delta vs previous period) built from historical snapshots. | DONE |
| REQ-8.1.7 | Resilience & empty states | Any unavailable source (missing key, API error, no data yet) renders a clear "unavailable / not configured" state with the reason — never a 500 and never a misleading zero. | DONE |

### 8.2 Users & Training statistics

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.2.1 | User totals & growth | Total users; new signups over the selected range; growth trend; breakdown by `role_type` (student / teacher / professor / industry-engineer / other) and by auth provider (Google / GitHub / email). | DONE |
| REQ-8.2.2 | Active users | DAU / WAU / MAU derived from activity (logins, `UserVideoProgress`, community actions); active-rate trend. | DONE |
| REQ-8.2.3 | Training engagement | Enrollments, lessons watched, total watch-hours, lesson-completion rate, course-completion rate, certificates issued, quiz pass rate, reflections submitted — each with range + trend. | DONE |
| REQ-8.2.4 | Popular courses | Ranked table of courses by enrollment, by completion count, and by watch-time, with per-course completion %; top/bottom performers highlighted; each row deep-links to the course detail. | DONE |
| REQ-8.2.5 | Activation funnel | The Chapter 5 funnel (entry → free-lesson → wall → register → onboarding-started → onboarding-completed → first-lesson) with counts, step conversion %, and the activation rate (REQ-5.7.2), sourced from Plausible events and/or local models. | DONE |
| REQ-8.2.6 | Corporate / lead funnel | Corporate leads (`CorporateLead`) and newsletter subscribers (confirmed vs pending) over the range, with the north-star **inbound corporate inquiries** count front-and-center; deep links to the lead/subscriber admin. | DONE |

### 8.3 Cost & spend tracking

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.3.1 | Cost adapter framework | A pluggable `CostAdapter` interface (`name`, `fetch() -> CostRecord`, `deep_link`, `source`) with a registry. Adding a service is a one-class addition. Each adapter declares whether it returns `live` (API), `estimate` (computed on-site), or `manual` (admin-maintained) data, and degrades gracefully when its key is absent. | DONE |
| REQ-8.3.2 | Spend overview | A top panel: total spend this month, month-over-month trend, and a per-service breakdown (bar/table) with each service's amount, source badge (live / estimate / manual), last-fetched time, and a **direct deep link** to that provider's own console. | DONE |
| REQ-8.3.3 | OpenAI (live) | OpenAI spend + token usage from `UsageLog` (REQ-1.6.7) by model (GPT-4o, GPT-4o-mini, gpt-4o-transcribe, gpt-image-1), with the monthly cost-cap status (REQ-1.6.8) shown; cross-checked against the OpenAI usage API where available. | DONE |
| REQ-8.3.4 | Copilot seats (live) | Assigned seats × $19, pending invites, and reclaimable idle seats — reusing the existing Copilot dashboard data (REQ-1.5.8). | DONE |
| REQ-8.3.5 | Bunny Stream | Video storage + streaming/bandwidth cost via the Bunny billing/statistics API where available; estimate from stored minutes + delivered GB otherwise; deep link to the Bunny dashboard. | DONE |
| REQ-8.3.6 | Resend (email) | Email volume vs plan and any overage; from the Resend API where available, estimate from sent-mail counts otherwise; deep link. | DONE |
| REQ-8.3.7 | Render (hosting) | Monthly hosting + persistent-disk cost; live from the Render API if exposed, else a maintained manual figure; deep link to the Render dashboard. | DONE |
| REQ-8.3.8 | Plausible | Analytics subscription cost (manual/plan-based) + a link to the Plausible stats; deep link. | DONE |
| REQ-8.3.9 | Other services | Adapters (live/estimate/manual as available) for: domain registrar (babook.co.il), **Google Cloud Storage backups (live bucket size; first 5 GB free)**, and the showcase screenshot service (REQ-6.3.17). | DONE |
| REQ-8.3.10 | Billing placeholder | A dormant section for **Stripe + Green Invoice** (revenue + fees) wired but inactive while billing is DEFERRED (Ch 1.4), ready to light up when payments ship. | DONE |
| REQ-8.3.11 | Manual cost entry | The admin can set/override a `manual` `CostRecord` per service per month (for anything with no usable API), and those values flow into totals and trends like any other source. | DONE |

### 8.4 Engagement & community health

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.4.1 | Absorb community-health | The dashboard's Engagement section is a superset of the staff community-health view (REQ-6.8.2): weekly active contributors, unanswered-question rate, time-to-first-answer, projects/week, tips/week, RSVPs, open report-queue size. | DONE |
| REQ-8.4.2 | Full engagement breadth | Counts + trends across every community surface: forum threads & answers, accepted-answer rate, showcase projects (by stand), reactions, comments, tips, channel messages, DMs, follows, badges awarded, reputation leaders, events & RSVPs. | DONE |
| REQ-8.4.3 | Engagement rate | An overall engagement rate (active contributors ÷ active users) and a contribution mix (share of members who post / answer / react / publish), with trend. | DONE |
| REQ-8.4.4 | Moderation pulse | Open report queue size, items awaiting student-publish review (REQ-6.3.7), and recent moderation actions — surfaced so a backlog is never missed; deep links into the staff queues. | DONE |
| REQ-8.4.5 | Keep staff view | The existing `/staff/community-health/` page remains available to staff unchanged (so staff do not lose it); the dashboard's Engagement section is the admin-only richer superset (DEC-66). | DONE |

### 8.5 System health

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.5.1 | Deploy status | Latest deploy (commit, time, result) via the GitHub Deployments / Render API; shows current live revision. | DONE |
| REQ-8.5.2 | Backup status | Last successful DB backup time and outcome (REQ-1.2.4) with a clear stale/failed indicator. | DONE |
| REQ-8.5.3 | Database & storage | `db.sqlite3` size, persistent-disk usage, and media footprint, with a headroom indicator against the disk cap. | DONE |
| REQ-8.5.4 | Service reachability | `/healthz` (REQ-1.2.15) status plus a quick reachability/last-error signal per critical external dependency (OpenAI, Bunny, Resend) from the most recent capture. | DONE |

### 8.6 Alerts

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-8.6.1 | Threshold alerts | Configurable thresholds raise an alert via the existing `notify()` + email to the admin: monthly spend crossing a budget (per-service and total), report queue exceeding N, unanswered questions older than N hours, and a failed/stale backup. Reuses the OpenAI cost-cap mechanism (REQ-1.6.8) rather than duplicating it. | DONE |
| REQ-8.6.2 | Alert surface | Active alerts appear as a banner on the dashboard hub and are listed in a small "needs attention" panel; dismissible, with the triggering metric linked to its section. | DONE |
| REQ-8.6.3 | Alert config | Thresholds are admin-editable (env defaults + an in-dashboard settings panel); alerting is opt-in per alert type. | DONE |

### 8.7 Decisions log (confirmed by Avi 2026-06-14)

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-62 | Access scope | **Superuser-only** (`/admin-dashboard/`), stricter than staff | Avi: "only me the admin can see it"; the cockpit aggregates spend + everything, kept private |
| DEC-63 | Cost ingestion | **Pluggable per-service adapters; live where an API exists, estimate or manual otherwise** | Ships a complete dashboard now without blocking on missing/awkward provider billing APIs; each upgradeable to live later with no UI change |
| DEC-64 | Data freshness | **Nightly snapshot + per-section manual refresh** (no live-on-every-load) | Instant page loads, free history/trends, respects provider rate limits and avoids per-view cost |
| DEC-65 | Posture | **Display + threshold alerts** (not display-only) | A daily cockpit should warn before a budget/queue/backup problem grows; reuses `notify()` + the cost-cap pattern |
| DEC-66 | Community-health overlap | **Dashboard absorbs REQ-6.8.2 as an admin-only Engagement superset; the staff `/staff/community-health/` page stays as-is** | Honors "only me" without regressing the staff view |
| DEC-67 | Each cost section deep-links out | **Every service section carries a direct link to that provider's own console** | Avi wants in-dashboard data **and** one click to browse the source directly |

### 8.8 Avi action items

**Existing credentials are reused — no new keys needed for most adapters.** The
cost adapters read the **same** secrets the functional code already uses (from
`settings`/env): `BUNNY_API_KEY` + `BUNNY_STREAM_LIBRARY_ID` (Bunny statistics),
`OPENAI_API_KEY` (and `UsageLog`, which already carries cost — no billing key
required), `RESEND_API_KEY` (Render env var), and the GitHub Copilot org token
(Render env var, alongside `COPILOT_MAX_SEATS`). So Bunny, OpenAI, Resend, and
Copilot need **no action**. Only the items below are genuinely missing.

| ID | Action | Blocks |
|---|---|---|
| ACT-23 | Provide a **Render API token** (read scope) — or confirm a maintained manual hosting figure instead | REQ-8.3.7, REQ-8.5.1 |
| ACT-24 | Provide a **Plausible stats API key** (server-side read) + confirm the plan cost — or confirm we derive funnels from local models and keep cost manual | REQ-8.2.5, REQ-8.3.8 |
| ACT-25 | Provide the monthly **manual $ figures** for any service without a usable billing API (domain registrar, Plausible/Render plan if no token) | REQ-8.3.9, REQ-8.3.11 |
| ACT-26 | Confirm **budget thresholds** for alerts (per-service + total monthly spend, report-queue size, unanswered-question age) | REQ-8.6.1, REQ-8.6.3 |

### 8.9 Acceptance criteria for Chapter 8

Chapter 8 is **DONE** when, in production:

1. `/admin-dashboard/` is reachable **only** by the superuser; staff and members
   cannot access any dashboard route, and the nav entry shows only to the admin.
2. The Users & Training section reports user totals/growth, active users, training
   engagement, **popular courses ranked**, and the activation + corporate funnels.
3. The Costs section shows a spend overview with a per-service breakdown, each
   service marked `live`/`estimate`/`manual`, carrying a **deep link** to its
   provider console; OpenAI and Copilot are live; the rest are populated by their
   adapter or a maintained manual figure; manual override works.
4. The Engagement section reports the full community breadth (superset of the
   staff community-health view), and the staff view still works.
5. The System section reports deploy, backup, DB/storage, and health signals.
6. Nightly capture populates snapshots; per-section refresh works; trends render
   from history; thresholds raise alerts to the admin.
7. Full regression green; admin-only access boundaries covered by tests.

---

## Chapter 9 — Teachers & Classes (Classrooms)

> **Status: BUILT IN DEV (2026-06-21), not deployed.** Approved by Avi ("add it
> to the backlog and run it"). REQ-9.1–9.11 implemented and tested in dev;
> REQ-9.12–9.14 (public class directory + request-to-join with teacher approval,
> notified in-system and by email both ways) added on Avi's follow-up and built
> in dev. Production deploy awaits Avi's explicit word.

### 9.0 Vision

Let any member turn babook from a solo-learning site into something they can
**teach with**: a parent, a school teacher, a youth-group leader, or a course
graduate opens a **class**, invites people by a link / QR / in-system message,
and then follows their students' learning while the class gets a shared space to
discuss and show what they built. Teaching is self-serve (no admin approval), so
the platform grows by its own users bringing their groups in.

**Design laws**
- **Self-serve**: becoming a teacher is one click; no gatekeeping.
- **Frictionless join**: a link or QR is enough; logged-in users join in one tap,
  logged-out users land on the existing `/join/` wall and are dropped into the
  class right after signing in (reuses REQ-5.4 return-to-intent).
- **Privacy by role**: a student's *progress / achievements / "contentment"* is
  visible to the **teacher only**. Only **projects** and **discussions** are
  shared with classmates — and a student can opt a project out (default: shared).
- **No new walled garden**: a class reuses existing objects (courses, lessons,
  `LessonModelSubmission`/showcase projects, community chat/threads, certificates,
  `UserVideoProgress`) — it's a *lens + space over* them, not a parallel system.

### 9.1 Data model (proposed)

- **`TeacherProfile`** (or a `is_teacher` flag on `UserProfile`) — marks a member
  who has opted into teaching. Created on first "become a teacher" click.
- **`Class`** — `owner` (teacher, FK User), `name`, `slug`, `description`,
  `join_code` (random, unguessable; powers link + QR), `is_open` (accepting
  members), `created_at`, optional `course` focus + `capacity`.
- **`ClassMembership`** — `klass` (FK), `student` (FK User), `status`
  (invited / requested / active / removed), `joined_at`,
  `share_projects` (bool, default **True** = opt-out model).
- **`ClassInvite`** (in-system invitations) — `klass`, `inviter`, `invitee`
  (FK User), `status` (pending / accepted / declined), `created_at`. Surfaces as
  a notification + a "request to join the class" message to the invitee.
- **`ClassJoinRequest`** (student-initiated, teacher-approved) — `klass`,
  `student` (FK User), `status` (pending / approved / declined), optional
  `message`, `created_at`, `decided_at`. Created from the public class directory;
  the teacher is notified in-system and by email and approves or declines.
- Classroom discussions/messages use a per-class **`ClassMessage`** model
  (discussion posts; teacher posts are flagged as announcements).
- As built: the class model is **`TeacherClass`** and the `is_teacher` flag lives
  on `UserProfile`.

### 9.2 Requirements

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-9.1 | Become a teacher | Any logged-in member can become a teacher in one click. Flips `is_teacher`; unlocks the teacher UI. No admin approval. | DONE (dev) |
| REQ-9.2 | Create a class | A teacher creates a class (name + optional description). Generates an unguessable `join_code`. Lands on the class management page. | DONE (dev) |
| REQ-9.3 | Invite by link + QR | The class page shows a **shareable join link** (`/class/join/<join_code>/`) and a **QR code** of it, with copy + "share to WhatsApp" buttons, to send to anyone. | DONE (dev) |
| REQ-9.4 | Join via link/QR | Opening the join link: if **logged in** → joins immediately (membership `active`) and lands in the classroom; if **logged out** → routed through `/join/` (login/register), then auto-joined and returned to the classroom (reuses REQ-5.4 return-to-intent). | DONE (dev) |
| REQ-9.5 | Invite existing members in-system | A teacher can **search system users** and send a join invitation. The invitee gets an in-app **notification**; accepting makes them `active`, declining closes it. | DONE (dev) |
| REQ-9.6 | Teacher roster + student insight | For each `active` student the teacher sees their **course progress, deliverables/projects, achievements/certificates** across courses the student has taken. Teacher-only. | DONE (dev) |
| REQ-9.7 | Classroom space | A shared class page every member can see/join, containing: **(a) discussions**, **(b) teacher messages/announcements**, **(c) the class project gallery** (members' shared projects). | DONE (dev) |
| REQ-9.8 | Project sharing opt-out | Each student's projects are shared to the class **by default**; a per-membership toggle lets a student **opt out** (`share_projects=False`) so their projects are hidden from classmates (still visible to the teacher). | DONE (dev) |
| REQ-9.9 | Privacy boundary | Classmates see **only** shared projects + discussions. A student's **progress, achievements, and contentment are never shown to other students** — teacher-only. Enforced in views + covered by tests. | DONE (dev) |
| REQ-9.10 | Leave / manage / close | Students can leave a class; the teacher can remove a member, close/reopen joining, rotate the join code, and delete the class. | DONE (dev) |
| REQ-9.11 | RTL + mobile + anon | All class surfaces are Hebrew-first RTL, work ≥360px, and the join link works for logged-out visitors via the existing wall. | DONE (dev) |
| REQ-9.12 | Find a class by search | Everyone (incl. logged-out) can **search** for a class at `/classes/all/` (search-as-you-type, by class name or teacher) — results show name, teacher, member count. **No full list** (so people don't wander into random classes) and **no student data**. Visitors cannot enter or self-join; the only action is "request to join" (logged-out routed via `/join/`). A top-nav shortcut "הכיתות שלי" appears for anyone who owns or belongs to a class. | DONE (dev) |
| REQ-9.13 | Request to join + teacher approval | From the directory a member sends a **join request** (logged-out users go through `/join/` first). The teacher is notified **in-system (notification) and by email with a link**. The teacher approves or declines; on **approval** the student becomes `active` and is notified **in-system and by email with a link to the class**. State is reflected in the directory (request sent / member). | DONE (dev) |
| REQ-9.14 | Email both ways, safely | Emails are plain Hebrew text, sent via the existing Resend/console backend with `fail_silently=True` so a mail hiccup never breaks the flow. Approval is **owner-only** (the site superuser keeps the admin override used everywhere in Classrooms) and never mutates state on a bare GET (the email link lands on a confirm page; approval is a POST). A closed class (`is_open=False`) rejects new requests, and a pending request never re-spams the teacher. | DONE (dev) |

### 9.3 Acceptance (chapter)

1. A member becomes a teacher, creates a class, and gets a working link + QR.
2. A logged-in user opens the link and is in the class instantly; a logged-out
   user signs in and lands in the class afterwards.
3. A teacher finds an existing user, invites them in-system, and the user accepts
   from their notifications.
4. The teacher sees each student's progress + deliverables; classmates do **not**.
5. The classroom shows discussions, teacher messages, and the shared project
   gallery; a student who opts out is hidden from classmates but not the teacher.
6. Demo: a few seeded teachers + classes + students, viewable end-to-end on dev.
7. Full regression green; privacy boundaries covered by tests.
8. The public directory lists all classes with no student data; a logged-out
   visitor is sent to sign in, then can request to join.
9. A join request reaches the teacher in-system and by email; the teacher
   approves from a link; the student is then notified in-system and by email and
   can enter the class. Only the owner can approve; approval is a POST.

---

## Chapter 10 — מט״צים (Young Technology Leaders)

> **Status: SPR-10.1 BUILT IN DEV (2026-08-08), not deployed. Rest is spec.**
> Sources: Litala Aviv's (ראש תחום חינוך חברתי, רשת החינוך עתיד) site brief of
> 2026-08-03, and the scoping conversation with Avi on 2026-08-08.
> REQ-10.1–10.4, 10.13, 10.14 and 10.33–10.36 are implemented and tested in dev
> (`tests/test_spr_10_1.py`, 16 tests). Everything else is TODO. Production
> deploy awaits Avi's explicit word.
>
> **Still open with Litala before further build**: her sign-off on the core
> change, that the site *reflects* training rather than hosting it.

### 10.0 Vision

**מט״צים = מובילי טכנולוגיה צעירים.** A selective program run with רשת החינוך
עתיד: roughly **20 to 40 teenagers per cohort**, each of whom learns technology
and then **teaches a group of 10 to 20 younger kids**. The program's own funnel
is five stages:

**מתמיינים → לומדים → יוצרים → מדריכים → משפיעים**

`/matazim` manages the מט״צים **as people**: recruitment, application,
acceptance, certification, community, recognition, and reporting.

**It does not teach.** The מט״צים themselves learn on **babook**, through the
existing course engine, fully tracked. `/matazim` watches that activity and
credits it.

**The kids are outside the system entirely.** A מט״צ teaches their group from
**YouTube playlists**. The kids get a link. They do not sign up, they are not
members, they are not modelled, and neither they nor their learning is tracked
in any form (DEC-72). **We track מט״צים and nothing else.**

Being a מט״צ is **high status**. It is granted by hand, by program staff, and
it is meant to be scarce.

**Design laws**

- **Status, not permission.** Certification unlocks nothing on babook. Any
  member can already become a teacher and open a class (REQ-9.1). What
  certification does is make the activity **count**. Consequence: babook needs
  zero permission changes for this chapter.
- **Reads learning state, never writes it.** Every training figure shown in
  `/matazim` is a live query over `Enrollment`, `UserVideoProgress`,
  `CourseCertificate`, `TeacherClass`, `ClassMembership`. Nothing is copied,
  mirrored, or cached into program tables.
- **Retroactive credit.** On the day someone is certified, everything they have
  already done on babook counts, with no backfill step.
- **Granted by hand.** Only program staff (Avi, Litala) flip the switch.
  Selectivity is the product, not an obstacle to it.
- **One tracked population.** Only the מט״צים are tracked. Their teaching is
  recorded as **their own** declared activity, never as data about the children
  they teach. Nothing in this chapter creates, stores, or infers a record about
  a child.
- **Visible outside the walls.** The badge appears on public babook surfaces,
  not only inside `/matazim`. Status that only members can see is not status.
- **Program, not Matazim.** Build one generic program-space abstraction and
  instantiate מט״צים as its first program. A second program (another network,
  another cohort) must not require new code.

### 10.1 Data model (proposed)

Owned by the program space (the only things it writes):

- **`Program`** — `slug` (`matazim`), `name`, `description`, branding fields,
  `is_active`. First and only instance for now.
- **`School`** — `name`, `city`, contact. Referenced by memberships.
- **`ProgramMembership`** — `user`, `program`, `school`, `school_join_status`,
  `cohort_year`, `status`, `endorsed_at/by/note`, `certified_at`,
  `certified_by`, `certification_note`. **Cohort members only**: the adults who
  run the program never get one.
  - `status`: `applied` (מתמיינים) / `in_training` (לומדים) /
    `project_submitted` (יוצרים) / `certified` (מדריכים) / `alumnus` /
    `rejected` / `revoked`. Litala's five-stage funnel **is** this field.
  - `school_join_status`: `pending` / `confirmed`. The member picks the school,
    its leader confirms them onto the roster (DEC-77).

**Roles are two M2M relations, and there is no third** (as built, 2026-08-08):

- **`Program.staff`** — the matazim admins (Avi, Litala). The only authority
  that may open a school, assign a leader, or grant the מט״צ status. Site
  superusers count as staff, matching the admin override used across Classrooms.
- **`School.leaders`** — the teachers. **A leader's scope is exactly the schools
  they appear in**, which makes REQ-10.17 a property of the data rather than a
  rule to remember. M2M so a coordinator can cover several schools.

Deliberately *not* a `role` field on the membership: two sources of truth for a
permission is how cross-school leakage happens.
- **`ProgramApplication`** — `membership`, answers, assessment score
  (placeholder until the entrance tool exists), `decided_at`, `decided_by`.
- **`ProgramStatusLog`** — audit of every status transition: who, when, from,
  to, note. Append-only.
- **`ProgramEvent`** (ימי שיא) — `program`, `title`, `description`, `starts_at`,
  `location`, target schools.
- **`ProgramPost`** — the cohort feed: `program`, `author`, `body`,
  `is_announcement`, `created_at`. Same shape as `ClassMessage`.
- **Project submissions** reuse `CourseCompletionReview` when the project is a
  course deliverable; a standalone `ProgramSubmission` with the same shape
  (link, files, reviewer, status, note) covers projects that are not.

**Derived, never stored**: הדרכות taken and completed (`Enrollment`,
`CourseCertificate`), classes opened (`TeacherClass.owner`), kids taught
(`ClassMembership` where `status='active'`), and those kids' own learning
(`Enrollment` over that set of users).

### 10.2 Requirements

**Program space and identity**

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.1 | Program space at `/matazim` | The space has its own shell (nav, header, branding) inheriting the site base. Public pages open to anyone; member pages require an active `ProgramMembership`. A member of the program gets a "מט״צים" entry in the main site nav. Hebrew RTL, works ≥360px. | TODO |
| REQ-10.2 | Generic program, first instance | The space is driven by a `Program` record. Adding a second program requires data, not code. Nothing hardcodes the string `matazim` outside the seed. | TODO |
| REQ-10.3 | Public pages | דף הבית (what the program is), המסלול השנתי (the five stages as a visual path), בתי הספר המשתתפים. Visible logged out. Doubles as recruitment material for the next cohort. | TODO |

**Acceptance and certification**

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.4 | Apply to the program | Creates a `ProgramMembership` at `applied` plus a `ProgramApplication`. **Three questions only** (grade, why, what have you built): the application is not what assesses them, the entrance test is, so every extra field is only a teenager who does not finish the form. | DONE (dev) |
| REQ-10.4a | The school's invite link | Each school carries an unguessable, rotatable `join_code` powering a link and a QR, which its teacher hands out. Someone arriving through it is attached to that school with **no confirmation step**: the teacher gave them the link, so the assignment is already their decision (DEC-84). Same shape as the Chapter 9 class join code, reused rather than reinvented. | DONE (dev) |
| REQ-10.4b | New and existing users, one link | A logged-out visitor gets a **landing page** naming the school (not a bounce to a bare login form — the link gets pasted into WhatsApp groups), then goes through the existing `/join/` wall, and REQ-5.4 return-to-intent drops them back on the same page, freshly registered or freshly logged in. No new-vs-existing branching is written anywhere in Chapter 10. | DONE (dev) |
| REQ-10.4c | The open door | Applying without a link means choosing a school from the list; its leader then confirms them onto the roster (DEC-77). Both doors end at `applied`, so getting in is still level 1 and still the owner's to grant. | DONE (dev) |
| REQ-10.4d | Link hygiene | A closed school (`is_open=False`) accepts no applications. Rotating the code is **staff-only**, since it invalidates every copy of the old link already in the world. An existing member following a link is sent to their personal area rather than applying twice. | DONE (dev) |
| REQ-10.5 | Assessment as a pluggable slot | The track treats "assessment" as a step type with a pluggable implementation, so the dedicated entrance tool (DEC-74, to be designed) drops into the existing slot later with no rework. Until it exists, the application carries a manual staff score. | TODO |
| REQ-10.6 | Staff decision on an application | Program staff move an application to `in_training` or `rejected` from a staff screen. The applicant is notified in-system and by email. | TODO |
| REQ-10.7 | Certify as מט״צ, one button | **Only `program_staff`** can set a membership to `certified`. One button, required note. Records `certified_at` and `certified_by`. There is no self-serve path and no automatic promotion, ever. | TODO |
| REQ-10.8 | Every grant is audited | Each status transition writes a `ProgramStatusLog` row (who, when, from, to, note). Append-only, shown on the member's staff screen. A status that confers prestige must be traceable. | TODO |
| REQ-10.9 | Lifecycle after certification | A membership can move to `alumnus` (cohort ended) or `revoked` (withdrawn by staff, note required). Both stop counting as a **current** מט״צ while keeping the history and the issued certificate. | TODO |
| REQ-10.10 | Certificate | Certification issues **תעודת מוביל טכנולוגיה צעיר** through the existing `CourseCertificate`-style mechanism, with a public verification page like every other certificate on the site. | TODO |

**Reflection: the mirror over babook**

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.11 | Certification unlocks nothing on babook | A certified מט״צ uses babook with exactly the same permissions as any other member. No new teacher tier, no gating, no changes to `is_teacher`. Teaching happens off-platform (REQ-10.11b), so certification needs to unlock nothing at all. The Chapter 9 classrooms remain open to anyone who wants them, but they are not the expected path here. | TODO |
| REQ-10.11b | Teaching runs on YouTube | The kids a מט״צ teaches receive **YouTube playlist links**. They do not sign up, are not members, and appear nowhere in the data model. Removes the entire minors-signup, consent, and moderation burden that a few hundred child accounts would have created. | TODO |
| REQ-10.11c | Curated playlist library | `/matazim` lists the YouTube playlists a מט״צ may hand to their group, curated by program staff and grouped by topic and age, each with a copy-ready share link. Staff keep control of what is taught without approving anything case by case. | TODO |
| REQ-10.12 | Retroactive credit | On certification, everything the member has already done on babook counts immediately: every הדרכה taken, every lesson completed, every certificate earned. No backfill job, because nothing is copied. | TODO |
| REQ-10.13 | Derived only | Every training figure in `/matazim` is computed live from babook models. The program space never writes learning state. Enforced by review and covered by tests. | TODO |
| REQ-10.14 | אזור אישי | The member's personal area answers four things at a glance: where I am on the track, what I have finished, what my next step is, and what I have taught so far. **This page is the only daily reason to open `/matazim` and gets disproportionate design effort.** | TODO |
| REQ-10.15 | The tracked record | Per מט״צ, two things and only two: (1) **derived** from babook, the הדרכות they took and completed, lesson progress, and certificates; (2) **declared** by them, their teaching activity log (REQ-10.15b). No third level. The children are not measured (DEC-72). | TODO |
| REQ-10.15b | Teaching activity log | A מט״צ records their own sessions: date, which playlist or topic, roughly how many kids attended, an optional photo, and a sentence on how it went. **No child names, no child identities, no per-child anything.** This is the מדריכים/משפיעים evidence and it is the מט״צ's own record of their own work, not data about children. | TODO |
| REQ-10.15c | Photo consent | If a session log carries a photo of a group of children, the upload flow states the consent requirement and the מט״צ confirms the school's consent is in place. Photos pass the existing safety/moderation layer. See ACT-34. | TODO |
| REQ-10.16 | Staff dashboard | One page listing every מט״צ in the cohort with their derived training record and their declared teaching activity, filterable by school and status. At 20 to 40 members: no pagination, no aggregation jobs, no caching. | TODO |
| REQ-10.17 | School leader scoping | A leader sees the **roster** for their own school only. Cross-school leakage is a blocking defect. Enforced in the views, not the templates. Amended by DEC-80: the *page* is open to anyone, so the boundary is the people on it, not the URL. Covered by tests asserting both directions. | DONE (dev) |
| REQ-10.17a | Public school view | Any visitor, logged out included, may open any school and see aggregate figures only: מט״צים count, certified count, הדרכות completed, certificates. **No name, no status, no per-person progress, no controls.** Computed with aggregate queries, so the page stays cheap and cannot be walked person by person. | DONE (dev) |
| REQ-10.17b | Viewing widens nothing | Opening the view to everyone must not open any action. `confirm`, `endorse` and `leader/` each re-check `can_view_school` independently and 404 for an outsider. Covered by a test that asserts the page is 200 while all three POSTs are 404. | DONE (dev) |
| REQ-10.17c | Staff act as the teacher | Program staff get the roster and the same confirm/endorse controls as the school's own leader, in every school. Certification remains absent from school pages for everyone. | DONE (dev) |
| REQ-10.17d | Schools list links in | Every card on בתי הספר המשתתפים links to its school page; a leader's own school is marked so she reaches her roster in one click. | DONE (dev) |
| REQ-10.17e | Site-wide entry | מט״צים appears in the babook top nav and the side drawer **for everyone**, not only members (DEC-82). Members get the nav entry highlighted. | DONE (dev) |
| REQ-10.18a | Opening a school is staff-only | Only `Program.staff` may create a school or assign/remove its leaders. A leader attempting either gets a 404. | DONE (dev) |
| REQ-10.18b | Member picks, leader confirms | A member names their school; the membership sits at `school_join_status=pending` and counts only once a leader of **that** school confirms it. Another school's leader cannot confirm or decline it. Closes ACT-33 and matches Litala's "שהתלמיד יבחר את המוביל שלו". | DONE (dev) |
| REQ-10.18c | ~~Leaders endorse, never certify~~ | **Superseded by REQ-10.19 (DEC-83).** | REMOVED |
| REQ-10.19 | Level 1: accepted into the program | The school owner accepts an applicant (or rejects them), recording who granted it, when, and an optional note. Moves `applied → in_training`. This is the gate the entrance test (§10.7) will feed; until it is built the owner decides on their own judgement and the UI says so. | DONE (dev) |
| REQ-10.19a | Level 2: certified as a מט״צ | The school owner grants the מט״צ status, **note required**, recording the grantor. Available only once level 1 has been granted: certifying an applicant who was never accepted is refused. | DONE (dev) |
| REQ-10.19b | Grants are school-scoped | Both grants check the **member's own school**, so an owner posting another school's membership id directly gets a 404 and nothing changes. | DONE (dev) |
| REQ-10.19c | Revocation stays with program staff | The grants moved to the schools; undoing one did not. Revoke is staff-only, requires a note, and never erases the original grant, so the record of who gave it survives (REQ-10.9). | DONE (dev) |
| REQ-10.19d | The console is oversight, not a queue | ניהול התוכנית shows recent certifications across all schools with who granted each and why, plus revoke. Staff no longer gate the grant, so what they need is visibility over it. | DONE (dev) |
| REQ-10.18d | One school page, two audiences | The leader console and the staff view of a school are the **same page**. The difference is which schools you can reach, enforced in the view. The certify control is absent from it for everybody, staff included, so the recommendation and the grant always sit in different hands. | DONE (dev) |

**Community, events, projects**

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.18 | Cohort feed, not a forum | One feed carrying staff announcements, members' shared projects, new certifications, and upcoming ימי שיא. Explicitly **not** a threaded forum (DEC-73). Reuses the `ClassMessage` shape and the existing safety/moderation layer. | TODO |
| REQ-10.19 | קהילת מט״צים directory | A cohort "who's who": name, school, badge, and what each member built. Respects the existing `is_public`, `courses_visibility`, and `reflections_public` settings. | TODO |
| REQ-10.20 | ימי שיא | Staff create dated events (title, description, when, where, which schools). Members see upcoming events in the personal area and the feed. | TODO |
| REQ-10.20a | Help page, both audiences | A public "איך זה עובד" page at `/matazim/help/`, written for **a 14-year-old and for a teacher who has never seen the site**: what is expected, and what to do at each step. Students first, since there are more of them and they arrive more confused. The teacher half doubles as onboarding for a newly assigned school leader, because nobody is going to train forty teachers one at a time. Reachable from the program nav, the application form, and the home page. | DONE (dev) |
| REQ-10.21 | Project submission and approval | A member submits their יוצרים-stage project; a school leader or staff approves it or returns it with a note. Reuses the `CourseCompletionReview` pattern; a project attached to a `requires_review` course reuses that flow directly rather than duplicating it. | TODO |

**Recognition**

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.22 | Badge visible outside `/matazim` | The מט״צ badge appears on the public member profile, next to the teacher's name on their class pages, and in the public class directory (REQ-9.12). A kid joining a class sees "המדריך שלך: מט״צ מוסמך" linking to the program page. This is what turns a database field into something teenagers want, and it feeds next year's recruitment. | TODO |

### 10.3 Decisions

| DEC | Decision |
|---|---|
| DEC-69 | **Certification is a status, not a permission.** It grants recognition and makes activity count; it unlocks no capability on babook. Rationale: anyone can already teach (REQ-9.1), so babook needs no permission work. |
| DEC-70 | **Credit is retroactive and all-time.** Activity before certification counts. Simpler, more generous, and free given DEC-71. |
| DEC-71 | **`/matazim` reads learning state and never writes it.** No second learning engine, no mirrored tables. |
| DEC-72 | **The kids are outside the system entirely** (Avi, 2026-08-08). They receive YouTube playlist links, do not sign up, are not members, are not modelled, and are never tracked. **Only מט״צים are tracked.** Rationale: a few hundred child accounts would have brought signup friction an 11-year-old cannot clear, plus consent and moderation duties out of proportion to the program. Cost, accepted knowingly: the "what did their kids learn" number is no longer derived, so a מט״צ's teaching is evidenced by their own declared session log (REQ-10.15b) instead. |
| DEC-72b | **Superseded by DEC-72.** The earlier design had each מט״צ run a Chapter 9 class on babook, which made teaching automatically evidenced and gave a three-level rollup. Recorded here because it is the natural fallback if the program later wants per-child data: see ACT-35 for the lighter revival (class code + first name, no email, no account). |
| DEC-73 | **Feed, not forum.** At 20 to 40 teenagers who already share a WhatsApp group, a dedicated forum dies empty and an empty forum makes the site feel abandoned. Community comes from the work being visible. Revisit only if members ask for threads. |
| DEC-74 | **RESOLVED 2026-08-08, see §10.7.** The entrance test is a Tinkercad **replication task**: the system shows a generated 3D object with its dimensions, the applicant models it and uploads an STL, the system measures how close they got. It is a **commitment test, not a skill or creativity test**, and it has no machine-issued rejection. |
| DEC-75 | **Both levels are Chapter 9 classes.** Staff teach the cohort as a class; each מט״צ teaches their group as a class. No teaching subsystem is built. |
| DEC-76 | **Build `Program` generically.** מט״צים is instance one. |
| DEC-77 | **Member picks the school, its leader confirms** (Avi, 2026-08-08). Closes ACT-33. |
| DEC-78 | ~~A school leader endorses, never certifies.~~ **SUPERSEDED by DEC-83 the same day.** Kept on the record because it was a deliberate choice before it was reversed, and because the endorsement machinery built under it was removed rather than left dangling. Its other half stands: opening a school and assigning its leader are still staff-only. |
| DEC-79 | **Roles are `Program.staff` and `School.leaders`, and nothing else** (as built). No `role` field on the membership: a leader's scope *is* the set of schools they appear in, so REQ-10.17 becomes a property of the data rather than a rule someone has to remember in every query. Adults running the program hold no `ProgramMembership` at all. |
| DEC-80 | **A school page is public; its people are not** (Avi, 2026-08-08). Anyone, logged out included, may open any school and see its numbers: how many מט״צים, how many certified, how much has been learned. Names, statuses and per-person progress stay with that school's leader and program staff. This **moves** the REQ-10.17 boundary from the page to the people on it, and it deliberately does not widen any write action: every POST re-checks `can_view_school` on its own. |
| DEC-81 | **Program staff can act as the teacher in any school** (Avi, 2026-08-08). Litala gets the roster and the same confirm/endorse controls as the school's own leader, everywhere. She still cannot certify from a school page: that lives only in ניהול התוכנית. |
| DEC-82 | **The מט״צים entry is in the main nav and the drawer for everyone** (Avi, 2026-08-08), not members-only, because the space is public and doubles as recruitment. Members get it highlighted. |
| DEC-84 | **Each school gets its own invite link** (Avi, 2026-08-08). A teacher generates a link + QR for their school and hands it out; a teen arriving through it is attached to that school immediately, with no confirmation step, because handing out the link *is* the approval. It reuses the Chapter 9 join-code mechanism wholesale, including the logged-out landing page and the `/join/` wall with return-to-intent, so "cope with new and existing users" needed no new code at all. Rotation is staff-only, since it invalidates every copy already in circulation. |
| DEC-83 | **Two levels of certification, both granted by the school owner** (Avi, 2026-08-08). **Supersedes DEC-78.** Level 1 = **accepted into the program**, which is the gate the entrance test (§10.7) feeds. Level 2 = **certified as a מט״צ**. Both are the owner's to give, to their own school's members only, each with a recorded grantor and note. What stays with program staff: opening schools, assigning leaders, and **revoking** a grant. Consequence, accepted knowingly: the badge is now as scarce as each school owner chooses to make it, rather than centrally rationed. Revocation and the audit log (REQ-10.8) are the counterweight, so a grant is always attributable and always reversible. The endorsement built under DEC-78 was removed, not left as dead machinery. |

### 10.4 Open questions (for Litala) and actions

| ID | Item |
|---|---|
| ACT-27 | Confirm cohort size, start date, and the list of participating schools. |
| ACT-28 | ~~**Minors at volume.** 200 to 800 child accounts vs an email-verification signup an 11-year-old cannot clear.~~ **CLOSED 2026-08-08 by DEC-72**: the kids never get accounts. |
| ACT-29 | **The missing course.** The track teaches a מט״צ technology, not how to teach. Ask whether רשת עתיד already has pedagogy content or whether it needs writing. This is the difference between the program working and a lot of frustrated kids. |
| ACT-30 | Is the credential annual and renewed, or granted once for good? Determines whether `alumnus` is automatic at cohort end. |
| ACT-31 | Build the curated **YouTube playlist library** for the kids (REQ-10.11c): which playlists, grouped by topic and age. Content task for Litala and Avi, not a build task. Most of the source video already exists, since the babook courses were built from YouTube in the first place. |
| ACT-32 | Litala's mail of 2026-08-03 carries three inline images (`image011`–`image013`) that are almost certainly her sketch of the site. The Gmail API returned filenames only. Get the files before finalising the page structure. |
| ACT-33 | ~~Is "בחירת מוביל" a free choice by the student or an assignment by staff?~~ **CLOSED 2026-08-08 by DEC-77**: the member picks, the leader confirms. Still open, and smaller: how do school leaders get their accounts in the first place (staff assigns by email/username today, so they must already be babook members). |
| ACT-34 | Confirm with Litala what blanket parental consent רשת עתיד already holds for photographing children in school activities, for REQ-10.15c. |
| ACT-35 | **Parked, not dropped.** If the program later wants per-child data: a class code plus a first name, no email, no password, not a real account. Gives attendance and progress with almost none of the consent burden that killed full signup. Revisit only on Litala's request. |
| ACT-36 | Decide the entrance-test target templates and their dimension ranges with Litala and Avi (§10.7). Starting set: cube with one through-hole, stepped block, plate with two holes. |

### 10.5 Litala's page list, mapped

| # | Page in her brief | Where it lives |
|---|---|---|
| 1 | דף הבית והסבר על תכנית מט״צים | `/matazim`, public (REQ-10.3) |
| 2 | המסלול השנתי | `/matazim`, public preview + personal status when logged in |
| 3 | מבחן הכניסה | `/matazim`, application flow (REQ-10.4/10.5) |
| 4 | הקורסים שלי | **babook**, the existing course engine. Reflected as progress in the personal area |
| 5 | הגשת תוצרים | `/matazim` (REQ-10.21) |
| 6 | ימי שיא | `/matazim` (REQ-10.20) |
| 7 | בתי הספר המשתתפים | `/matazim`, public |
| 8 | קהילת מט״צים | `/matazim` feed + directory (REQ-10.18/10.19) |
| 9 | אזור אישי | `/matazim` (REQ-10.14), linking out to "הכיתות שלי" on babook |

### 10.6 Phasing

1. **Shell and spine.** `/matazim` public pages in the matazim branding (§10.8),
   the five-stage track, and the אזור אישי reading real babook progress.
   Demoable to Litala on its own, and it is the thing she is actually asking for
   when she says נקי, פשוט וברור.
2. **Acceptance and certification.** Application, the entrance test (§10.7),
   staff decision, the certify button, the audit log, the certificate, and the
   badge on babook.
3. **Record and dashboards.** The teaching activity log, the playlist library,
   the staff dashboard, and school-leader scoping with its privacy tests.
4. **Community and logistics.** Feed, directory, ימי שיא, project submission
   and approval.

Phase 2 is the largest, because the entrance test carries the mesh work. If it
needs to ship sooner, the test can launch with a staff-scored manual submission
(REQ-10.5's fallback) and gain the automated measurement afterwards.

### 10.7 מבחן הכניסה — the Tinkercad replication test

Resolves DEC-74. Fills the assessment slot reserved by REQ-10.5.

**What it measures.** Not creativity, not talent, not precision. **Whether this
kid is serious enough to enter the journey.** If they took the Tinkercad
training, built the object they were shown, and submitted something recognisably
correct, that is the whole signal we need. Everything below follows from that
single sentence, and any rule that would fail a dedicated applicant is wrong.

**The task.** The system shows the applicant a target object: a rotatable 3D
view plus a dimensioned drawing. Something simple, a **cube with one through-hole**
being the reference difficulty. They model it in Tinkercad, export an STL, and
upload it. The system measures how close they got and tells them.

**Why a shown object beats a written brief.** Because the system generated the
target, it holds the ground truth. Verifying the submission stops being "detect
whether this was copied", which cannot be won (an STL carries no provenance, and
comparing against the whole internet is not practical), and becomes "measure the
difference between two meshes", which has an exact answer.

**Targets are generated, per applicant, per attempt.**

- Parametric templates (cube with a hole; stepped block; plate with two holes)
  with randomised whole-millimetre dimensions, snapped to multiples of 2 or 5 so
  a beginner can type them straight into Tinkercad.
- A handful of templates × several randomised parameters is thousands of
  distinct objects. Two applicants sitting next to each other never get the same
  one, and **no model downloaded from the internet can match one**, which is
  what removes the cheating problem instead of policing it.
- Targets are **pre-generated offline** by a management command and committed
  (STL + parameter JSON + rendered drawing). The web process never needs a
  boolean/CAD engine; it only reads a target and compares.

**The comparison needs no feature recognition**, only numpy over a triangle list:

| Measure | How | Catches |
|---|---|---|
| Outer dimensions | bounding box, sorted so orientation is irrelevant. Exactly tessellation-proof | wrong size |
| Number of through-holes | Euler number → genus. Exact | the hole they were asked for |
| Hole size | bbox volume minus mesh volume, i.e. the volume cut away | hole too big or small |
| Hole position | mesh centroid vs bbox centre | a drifted hole, and in which direction |
| Overall shape | mean point-to-surface distance after PCA alignment and best-of-24 axis rotations | anything the four specific numbers missed |

**Tolerances are per-feature, and deliberately generous.** Tinkercad dimensions
are **typed**, so outer sizes are usually exact; hole position is **drag-placed**,
so it needs real slack. Calibrated for commitment, not precision:

| What | Accept |
|---|---|
| Outer dimensions | ±3mm |
| Number of holes | exact |
| Hole size | ±30% |
| Hole position | ±5mm |
| Overall shape distance | mean under 2mm |

The bar is "you clearly built the thing I showed you". It cannot be cleared by
accident or with an unrelated file, and it will not fail an honest attempt.

**Tessellation note.** Tinkercad facets curves, so an exported hole is a polygon
prism about 1.6% smaller than a true cylinder. This is why the table compares the
**cut volume** rather than total volume, and why bounding box, genus, and surface
distance carry the verdict: all three are tessellation-proof. The 1.6% bias is a
constant, accounted for once when the reference is generated.

**Watertightness fallback.** Genus is undefined on a non-watertight mesh.
Tinkercad exports normally are watertight, but if one is not, fall back to the
shape-distance comparison. Never fail an applicant over a mesh defect they cannot
see or fix.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.23 | The test is a הדרכה, not a hurdle | The whole entrance test is a short babook course ("מבחן הכניסה למט״צים") whose final lesson is the upload. Someone who never passes has still learned Tinkercad and still earns that course's certificate. Failing is not rejection by a website. | TODO |
| REQ-10.24 | Generated target, shown in 3D | Each applicant is assigned a generated target and sees it as a rotatable 3D view plus a dimensioned drawing. three.js STL viewer, vendored for the strict WhiteNoise manifest, works on mobile ≥360px. | TODO |
| REQ-10.25 | Offline target generation | A management command generates the target set (STL + params + drawing) and commits it. No boolean/CAD engine in the web process. Targets are reviewable by Avi and Litala before any applicant sees one. | TODO |
| REQ-10.26 | Upload and measure | STL upload with a size cap, then the five measures above against the assigned target, with per-feature tolerances held in config rather than code. | TODO |
| REQ-10.27 | **No machine rejection** | The automated verdict is **accepted** or **not yet**. Never "rejected". The application window closes on a date; whoever finished by then enters the pile staff read. Every rejection decision in this program is made by a human (REQ-10.6). | TODO |
| REQ-10.28 | Unlimited retries, and retries are a positive signal | Unlimited attempts, a fresh target each time. Attempt count and history are shown to staff **as evidence of commitment, not as a blemish**: an applicant who missed, read the feedback, and came back has demonstrated more of what the program selects for than one who passed first time. | TODO |
| REQ-10.29 | Specific Hebrew feedback | On a miss, name the actual problem and the actual number ("הגובה שלך 43 מ\"מ במקום 40", "החור קטן מדי"), with their model and the target side by side and the mismatch highlighted. The feedback is a nudge back into Tinkercad, not a rejection notice. | TODO |
| REQ-10.30 | Explain your build | Three sentences: what you made, what was hard, what you would change. A direct commitment signal, and explaining your own work is the seed of teaching. Reuses the existing lesson-reflection machinery and the safety layer. Read by a human only after the automated gate. | TODO |
| REQ-10.31 | Duplicate detection, kept cheap | A PCA-normalised shape fingerprint per submission, compared against all previous ones, flags two applicants sharing a file. Linear scan, milliseconds at this scale. Nothing more elaborate: the randomised target already makes downloaded models useless. | TODO |
| REQ-10.32 | The commitment view | The staff screen shows lessons completed, attempts, and the days over which they were made ("השלים 6/6 שיעורים · 3 ניסיונות על פני 5 ימים · עבר"). Comes free from `Enrollment` / `UserVideoProgress`, and is a richer signal of seriousness than the pass bit alone. | TODO |

**Generalises beyond this program.** The show-a-target / upload-an-STL / measure-
the-difference loop is a **teaching mechanism**, not a one-off gate, and is the
geometric twin of the deterministic Python practice cells. Parked as
**EPIC-11** in the backlog for the Tinkercad course. Whatever gets built here
should be generalised into a lesson block then, not reimplemented.

### 10.8 Branding

The program space carries the identity of the existing **matazim.co.il**, read
from that site's live CSS on 2026-08-08.

| Token | Value | Use |
|---|---|---|
| `--a_primary` | `#00d4a4` | the brand mint/teal |
| `--a_bg_primary` | `#585ba8` | indigo: navbar, cards |
| `--a_bg_light` | `#e6e7f6` | pale lavender panels |
| `--a_secondary` | `#D9534F` | red accent |
| `--a_bg_dark` | `#444` | |
| max width | `1200px` | |

**Logo**: wordmark מטצים drawn as PCB traces with vias and pads, solid `#00d4a4`
on transparent (`logo_full.png` on the source site). **Tagline**: "מטצים –
מובילים טכנולוגיים צעירים". Source-site title: "האקדמיה למטצים".

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-10.33 | Scoped theme, not a fork | `/matazim` sets a body class that remaps babook's own CSS variables to the tokens above and swaps in the logo. babook keeps its layout, components, RTL and mobile work; only colour and mark change. Branding values live on the `Program` record (REQ-10.2), not hardcoded. | TODO |
| REQ-10.34 | Contrast floor | `#00d4a4` measures roughly 2.6:1 on the indigo and 1.9:1 on white, both below the WCAG AA 4.5:1 body-text floor. **Teal is an accent only**: fills, borders, badges, the logo. Body text on light surfaces uses the indigo `#585ba8` or a darkened teal. The audience is teenagers on phones, so readability wins over faithfulness to the source site. | TODO |
| REQ-10.35 | Do not import the source typography | The source site loads Acme, which has **no Hebrew glyphs**, so every Hebrew word on matazim.co.il already renders in a browser fallback. Importing it costs a request and changes nothing. Keep babook's Hebrew typography. Likewise do not bring in W3.CSS. | TODO |
| REQ-10.36 | Hero asset budget | The source hero `tech_bg.jpg` is 3.6MB as a fixed full-page background. Either recompress it hard or use an indigo-to-teal treatment instead. babook is mobile-first and this is a phone audience. | TODO |

### 10.9 Acceptance (chapter)

1. A visitor reads what מט״צים is, sees the annual track and the participating
   schools, logged out, on a phone.
2. A member applies, is assigned a generated target, sees it in 3D with its
   dimensions, uploads a deliberately wrong STL and gets a specific Hebrew
   explanation of what is off, then uploads a correct one and is accepted. At no
   point does the machine say "rejected".
3. Staff see that applicant's lessons completed, attempt count, and the days
   they spread over, and accept them into `in_training`. The member is notified.
4. Staff press one button and the member becomes `certified`. A non-staff user
   cannot reach that button by any route, including a direct POST.
5. The certified member's badge shows on their public babook profile and beside
   their name in the public class directory.
6. The member's אזור אישי immediately shows every הדרכה they have taken,
   including everything done **before** certification, plus their teaching log.
7. The member copies a YouTube playlist link from the curated library and logs a
   session: date, topic, roughly how many kids, a sentence. **No child name is
   requested, stored, or storable anywhere in the flow.**
8. The staff dashboard shows derived training plus declared teaching for the
   whole cohort. A school leader sees only their own school, proven by a test
   that asserts another school's members are absent.
9. Revoking a certification removes the badge and drops the member out of the
   current-cohort counts while the history and the issued certificate survive.
10. `/matazim` renders in the matazim palette with the logo, and no teal body
    text sits on a light background.
11. Full regression green; the school-scoping boundary covered by tests.

---

## Reference

- **Stack**: Django 5.2, Gunicorn, WhiteNoise, SQLite (Render disk), django-allauth (Google + GitHub OAuth), Bunny Stream (video), Stripe + Green Invoice (billing), Resend (email), Plausible (analytics), GitHub Copilot Business (seat provisioning via GitHub REST API), OpenAI API (AI chat, GPT-4o-mini / GPT-4o, gpt-4o-transcribe), yt-dlp + ffmpeg (authoring pipeline)
- **Live URL**: https://babook.co.il
- **Repo**: https://github.com/avisalmon/Render (branch `main`)
- **Deploy**: `git push origin main` → Render auto-deploys
