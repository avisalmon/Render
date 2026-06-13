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
| REQ-1.2.4 | Database backups | Nightly backup of `db.sqlite3` to cloud (GCS). Documented restore. Retention policy. | WIP — `backup_db` command DONE; nightly schedule + cloud target verify pending (ACT-3) |
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
| REQ-1.2.18 | Backup & restore BKM | `docs/procedures/backup_restore.md`: how backups work, where they live, how to restore on Render and locally. Test-restore done once and recorded. | WIP — BKM file exists; one test-restore not yet recorded |
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
| DEC-18 | Backup target (revised) | **Google Drive** via rclone | Already have account, 15GB free, built-in 30-day versioning, no extra repos/keys |

### 1.9 Avi action items

| ID | Action | Blocks |
|---|---|---|
| ACT-1 | Sign up Resend, give Copilot API key | REQ-1.1.3, REQ-1.2.2 |
| ACT-2 | Add SPF/DKIM DNS records at babook.co.il registrar | REQ-1.2.2 |
| ACT-3 | Set up rclone with Google Drive for DB backups | REQ-1.2.4 |
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

### 6.5 EPIC-6.5 — Challenges, Competitions & Hackathons

Cohort cadence + belonging. Designed per the research warning **not to copy
Kaggle** (research_1): challenges here are course-anchored, human-judged,
showcase-producing — not ML-metric leaderboards.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.5.1 | Challenge model | `Challenge`: title, brief (markdown), domain, difficulty, start/end dates, rubric, prizes (badges + featured + real prizes optional), linked course(s), status (upcoming/active/judging/done). | TODO |
| REQ-6.5.2 | Submissions | A submission IS a ShowcaseProject tagged to the challenge — one object, two surfaces; deadline enforced. | TODO |
| REQ-6.5.3 | Judging | Two-phase: community voting (stars, one per member) + staff/judge scoring per rubric; transparent weights; winners announced on the feed + badges (אלוף אתגר). | TODO |
| REQ-6.5.4 | Challenge page | Live page per challenge: brief, countdown, submissions wall, leaderboard during judging, winners podium after. | TODO |
| REQ-6.5.5 | Cadence | Seasonal rhythm: monthly mini-challenge per domain + 1-2 yearly hackathons (multi-day, team-based, virtual event integration from EPIC-6.7). | TODO |
| REQ-6.5.6 | Teams | Hackathons support teams (2-5): team page, joint submission, "מחפשים חברי צוות" board (the find-collaborators seed, feature_skeleton 5.2). | TODO |
| REQ-6.5.7 | School mode | A teacher (`role_type=teacher`) can clone a challenge for their class only — private leaderboard for their students (matazim B2B2C angle). | TODO |
| REQ-6.5.8 | Inaugural challenge (DEC-47a) | EPIC-6.5 launches with a real first challenge: **the MicroPython kit** (matazim/hardware, anchored to the `micropython-thonny` course) — build something with the kit, show it on the wall. Brief written and announced by Avi at launch. | TODO |

### 6.6 EPIC-6.6 — Chat & Groups (real-time, after the durable layer)

Deliberately AFTER forums/showcase (DEC-36): chat amplifies a live community,
it cannot create one. Scoped to what SQLite/Render handles (polling/SSE, no
websocket infra).

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.6.1 | Channels | Public channels per domain + per active challenge + כללי; message history persists and is searchable; lightweight polling (studio-job pattern) or SSE (chat-stream pattern, REQ-1.6.2). | TODO |
| REQ-6.6.2 | Course groups | Each course gets an optional members-channel (cohort feel); a "למדו איתי" presence row shows others currently learning the course. | TODO |
| REQ-6.6.3 | Direct messages | Member-to-member DMs, opt-in (default OFF), **disabled for `student` role members** (REQ-6.1.9); block + report built-in. | TODO |
| REQ-6.6.4 | Find collaborators | `/community/members/` directory: filter by domain interest, level, role; "פתוח לשיתופי פעולה" flag on the profile (feature_skeleton 5.2). | TODO |
| REQ-6.6.5 | Knowledge capture | A great chat answer can be promoted to a forum answer/tip in one click (staff or author) — chat never traps knowledge (anti-failure #1). | TODO |

### 6.7 EPIC-6.7 — Events & Meetups

Belonging → conversion: "מפגש live ממיר lurkers ל-contributors" (research_4).
Also the natural bridge to the corporate funnel (sponsors, exposure).

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.7.1 | Event model | `CommunityEvent`: title, description, type (live-coding / AMA / hackathon kickoff / meetup / כנס), virtual link or venue, start/end, capacity, host. | TODO |
| REQ-6.7.2 | Registration | RSVP + calendar file (.ics) + reminder notifications (24h, 1h); waitlist when full. | TODO |
| REQ-6.7.3 | Events page | `/community/events/`: upcoming + past; past events show recording (Bunny embed) + linked threads/projects. | TODO |
| REQ-6.7.4 | Recurring formats | Support a recurring series (e.g. שעת מומחה חודשית עם אבי — the AMA pattern); series page with all sessions. | TODO |
| REQ-6.7.5 | Physical meetups | Venue events (TLV/JLM/Haifa per research) with attendance check-in; photos feed back to the community feed. | TODO |

### 6.8 Cross-cutting: measurement & health

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-6.8.1 | Community events (Plausible) | `community_post`, `answer_accepted`, `project_published`, `challenge_submission`, `event_rsvp`, `tip_posted` — funnel doc extended. | TODO |
| REQ-6.8.2 | Health dashboard | Staff dashboard: weekly active contributors, unanswered-question rate, time-to-first-answer, projects/week, report-queue size. | TODO |
| REQ-6.8.3 | Activation tie-in | Onboarding (Ch.5) gains a community beat: the welcome checklist adds "הצטרפו לקהילה"; Avi Bot mentions the community in the greeting. | TODO |

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

### 6.11 Acceptance criteria for Chapter 6

Chapter 6 is **DONE** when, in production: a member has a public profile with
badges and a portfolio; questions get answered and accepted with knowledge
searchable; projects are published on the exhibition wall and shared outward;
the feed shows a living community and a weekly digest goes out; a full
challenge cycle (brief → submissions → judging → winners) has run; channels
and member directory operate with minors-safe defaults; an event has run end
to end with RSVP and recording; the health dashboard reports weekly active
contributors; and the full regression is green with every epic's tests.

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

## Reference

- **Stack**: Django 5.2, Gunicorn, WhiteNoise, SQLite (Render disk), django-allauth (Google + GitHub OAuth), Bunny Stream (video), Stripe + Green Invoice (billing), Resend (email), Plausible (analytics), GitHub Copilot Business (seat provisioning via GitHub REST API), OpenAI API (AI chat, GPT-4o-mini / GPT-4o, gpt-4o-transcribe), yt-dlp + ffmpeg (authoring pipeline)
- **Live URL**: https://babook.co.il
- **Repo**: https://github.com/avisalmon/Render (branch `main`)
- **Deploy**: `git push origin main` → Render auto-deploys
