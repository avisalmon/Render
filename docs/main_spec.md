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

> **Stage: TRACKED** — Core platform is operational. Backup automation is code-complete and awaiting first prod restore dry-run. Stripe/Green Invoice and live Copilot provisioning are parked by DEC-19a and are no longer Chapter 1 launch blockers.

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
| REQ-1.2.4 | Database backups | Nightly backup of `db.sqlite3` to **Google Drive** via rclone. Code, Render cron, and rclone config are ready. Completion requires first verified prod backup + restore dry-run. | IN PROGRESS |
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
| REQ-1.2.18 | Backup & restore BKM | `docs/procedures/backup_restore.md`: how backups work, where they live, how to restore on Render and locally. Procedure is written; test-restore still needs one successful prod backup. | IN PROGRESS |
| REQ-1.2.19 | Rollback BKM | `docs/procedures/rollback.md`: revert bad deploy on Render (manual redeploy of previous commit, env var revert, DB restore if needed). | DONE |

### 1.3 Video Infrastructure (Bunny Stream)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.3.1 | Video host: Bunny Stream | All course videos uploaded to Bunny Stream library. API key + library ID stored as env vars. | DONE |
| REQ-1.3.2 | Video model | Django `Video` model: `bunny_video_id`, `title`, `duration_seconds`, `course_id`, `lesson_order`, `is_free_preview`. | DONE |
| REQ-1.3.3 | Embedded player | Bunny iframe player embedded in lesson page. Responsive 16:9. Hebrew/English captions when uploaded. | DONE |
| REQ-1.3.4 | Signed playback URLs | Paid videos use Bunny's token-authentication (signed URLs, expire in 24h). Only entitled users get a playable URL. | DONE |
| REQ-1.3.5 | Per-user progress | Model `UserVideoProgress`: `user`, `video`, `last_position_seconds`, `percent_watched`, `completed_at`. Updated via JS heartbeat every 15s. | DONE |
| REQ-1.3.6 | Resume playback | Player auto-seeks to `last_position_seconds` on next view. | DONE |
| REQ-1.3.7 | Course progress aggregation | Course detail page shows % completed across all lessons. Course marked complete when all videos ≥ 95% watched. | DONE |
| REQ-1.3.8 | Video upload admin flow | Admin can upload via Bunny dashboard, then register the `video_id` in Django admin. (Direct-upload from Django admin is deferred.) | DONE |
| REQ-1.3.9 | Free preview gating | `is_free_preview=True` videos playable by anonymous users. All others require login + entitlement. | DONE |

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

### 1.5 GitHub Copilot Seat Provisioning (Parked)

> The local data model, dashboards, and lifecycle scaffolding are implemented and tested. Live GitHub org billing, PAT/App setup, and real API provisioning are **parked** by DEC-19a until token/Copilot bundling returns in §2.10.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.5.1 | GitHub org + Copilot scaffolding | Settings, models, dashboards, and env-var hooks exist for a future dedicated GitHub org. Live Copilot Business activation and PAT/App setup are deferred to §2.10. | DONE |
| REQ-1.5.2 | GitHub username on user | User provides GitHub username at signup or in profile (or OAuth-links GitHub via allauth). Stored on user model, validated against GitHub API. | DONE |
| REQ-1.5.3 | Copilot-enabled subscription tier | At least one pricing tier flagged `includes_copilot=True`. Entitlement `copilot_seat` granted on active subscription, revoked on cancel/expiry. | DONE |
| REQ-1.5.4 | Invite lifecycle scaffolding | On future Copilot-tier subscription, local service creates invite-pending state and audit event. Real GitHub invite API call is deferred to §2.10. | DONE |
| REQ-1.5.5 | Seat assignment scaffolding | Local service moves a seat to active and logs the event. Real Copilot billing API call is deferred to §2.10. | DONE |
| REQ-1.5.6 | Seat revocation scaffolding | Local service revokes internal seat state and logs churn/reclaim reasons. Real GitHub org removal is deferred to §2.10. | DONE |
| REQ-1.5.7 | Inactivity reclamation scaffolding | Local inactivity thresholds, warning/reclaim logic, and audit records are implemented. Real Copilot activity polling is deferred to §2.10. | DONE |
| REQ-1.5.8 | Admin dashboard | Admin sees: total assigned seats, monthly cost ($/mo), per-user last-activity date, pending invites, expired invites. One-click reclaim button per seat. | DONE |
| REQ-1.5.9 | Seat cap | Env var `COPILOT_MAX_SEATS` enforces hard cap to prevent runaway billing. New eligible subscriptions queued (waitlist) if cap reached; admin notified. | DONE |
| REQ-1.5.10 | User-facing status | User profile shows: Copilot seat status (`none` / `invite_pending` / `active` / `expiring` / `revoked`), link to accept org invite, last activity date, link to VS Code setup guide. | DONE |
| REQ-1.5.11 | Audit log | Every seat lifecycle event (invite/accept/assign/revoke/reclaim) written to an `audit_log` table with timestamp, actor (system/admin), reason, and GitHub API response. | DONE |
| REQ-1.5.12 | Org policy documentation | Policy document exists for future Copilot org setup. Actual GitHub UI policy enforcement is deferred until Copilot bundling is reactivated. | DONE |

### 1.6 AI Chat Infrastructure (OpenAI)

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-1.6.1 | OpenAI API integration | Direct OpenAI API via `openai` Python library. API key stored as env var. Connection verified with a health-check call at startup. | DONE |
| REQ-1.6.2 | Chat endpoint (request/response MVP) | `POST /api/chat/` accepts user message + session ID and returns a usable response with history/usage tracking. SSE token streaming is deferred to the AI Mentor/Chat polish work in §2.7. | DONE |
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

| ID | Action | Blocks | Status |
|---|---|---|---|
| ACT-1 | Sign up Resend, give Copilot API key | REQ-1.1.3, REQ-1.2.2 | DONE |
| ACT-2 | Add SPF/DKIM DNS records at babook.co.il registrar | REQ-1.2.2 | DONE |
| ACT-3 | Set up rclone with Google Drive for DB backups | REQ-1.2.4 | DONE |
| ACT-4 | Approve AI-generated logo OR provide own | REQ-1.1.9 | DONE |
| ACT-5 | Create Plausible account, share site ID | REQ-1.2.11 | DONE |
| ACT-6 | Confirm Render persistent disk attached at `/var/data/` | REQ-1.1.5, REQ-1.2.4, REQ-1.5 | DONE |
| ACT-7 | Review draft privacy + terms text | REQ-1.2.12 | DONE |
| ACT-8 | Confirm `https://babook.co.il/accounts/google/login/callback/` in Google Cloud OAuth redirect URIs | REQ-1.1.2 | DONE |
| ACT-9 | Sign up Bunny.net, create Stream library, share API key + library ID | REQ-1.3.1 | DONE |
| ACT-10 | Create Stripe account (Israel), share test + live keys | REQ-1.4.1 | DEFERRED |
| ACT-11 | Sign up Green Invoice (חשבונית ירוקה), share API key | REQ-1.4.9 | DEFERRED |
| ACT-12 | Confirm עוסק status (מורשה / פטור) for VAT handling | REQ-1.4.11 | DONE |
| ACT-13 | Decide initial pricing (ILS amounts for monthly / yearly / per-course) | REQ-1.4.2, REQ-1.4.3 | DONE |
| ACT-14 | Create or identify GitHub org for seat provisioning (e.g. `babook-learn`) | REQ-1.5.1 | DONE |
| ACT-15 | Activate Copilot Business on that org (billing setup, payment method) | §2.10 | DEFERRED |
| ACT-16 | Generate org PAT or install GitHub App with `manage_billing:copilot` scope; share token | §2.10 | DEFERRED |
| ACT-17 | Confirm minimum subscription price for Copilot-included tier (recommended ≥ ₪149/mo) | REQ-1.5.3, DEC-14 | DONE |
| ACT-18 | Configure org-level Copilot policies in GitHub UI (telemetry, public-code filter, editors) | §2.10 | DEFERRED |
| ACT-19 | Create OpenAI API account + payment method, share API key | REQ-1.6.1 | DONE |
| ACT-20 | Set token-rate limits per tier (daily caps) | REQ-1.6.6 | DONE |
| ACT-21 | Set monthly cost cap amount (USD) | REQ-1.6.8 | DONE |
| ACT-22 | Set up email addresses on babook.co.il domain: `privacy@`, `support@`, `noreply@` | REQ-1.2.2 | DONE |
| | **Chapter 2 — Epic 2.1** | | |
| ACT-23 | Provide professional headshot photo (WebP, dark bg, chest-up) | REQ-2.1.9 | DONE — `docs/Avi_03.jpg` → `static/avi-headshot.webp` (2092×2093) |
| ACT-24 | Provide WhatsApp business number for `WHATSAPP_NUMBER` env var | REQ-2.1.40 | DONE — `972547885798` (private number, approved by Avi); set in `settings_local.py` and Render env var |
| ACT-25 | Collect company logo permissions (3+ companies, SVG files) | REQ-2.1.15 | TODO |
| ACT-26 | Collect testimonial quotes + written consent (2+ people) | REQ-2.1.23, REQ-2.1.24 | TODO |
| ACT-27 | Create 1200×630 social card image for og:image | REQ-2.1.3 | TODO |
| ACT-28 | Review/approve FAQ content (10 Hebrew Q&As) | REQ-2.1.26 | DONE — 10 Hebrew Q&As approved as-is (May 2026) |
| ACT-29 | Confirm service tier pricing signals (₪ amounts per tier) | REQ-2.1.17, REQ-2.1.18, REQ-2.1.19 | DONE — see DEC-25 |

### 1.10 Acceptance criteria for Chapter 1

Chapter 1 is **DONE** when:
1. All `REQ-1.*` are `DONE` or formally `DEFERRED`
2. All `DEC-*` resolved (already done)
3. All launch-blocking `ACT-*` completed or marked deferred by DEC-19a
4. `python manage.py check --deploy` passes cleanly
5. `pytest` exits 0 locally and in CI
6. Clean deploy from `main` to babook.co.il succeeds, all public pages render, Google + password login work, password reset email arrives, health check returns 200, free/paid-preview video gating behaves as configured, AI chat returns a response with correct rate limiting, and the first prod backup + restore dry-run is recorded.

Parked components explicitly excluded from Chapter 1 launch acceptance: real Stripe checkout, Green Invoice issuing, live Copilot Business activation/API provisioning, and SSE chat streaming. These revive only when their later Epic 2 sections are pulled forward.

---

## Chapter 2 — babook.co.il Product (Authority Platform)

**Business model:** babook.co.il is a marketing and credibility engine. The platform offers high-quality AI content (some free, some paid) to position Avi as the go-to AI trainer in Israel. The platform may generate its own revenue, but its primary purpose is a marketing funnel for corporate training engagements (₪15-50K per gig). Every feature must answer: "Does this make Avi's phone ring?"

**North star metric:** Number of inbound corporate training inquiries per month.

**Epic lifecycle stages:**

| Stage | Meaning | What exists |
|-------|---------|-------------|
| `DEFINITION` | Paragraph describing intent + priority. Not executable yet. | Epic paragraph only |
| `SPECCED` | REQ rows with acceptance criteria written. Ready for sprint planning. | REQ table with Status column |
| `TRACKED` | Backlog entries created (EPIC + SPR + Features in `backlog.md`). Execution underway or complete. | Backlog ↔ Spec bidirectional links |

**Pivot note (see DEC-19a):** Research phases 1 and 4 recommended token-resale (Copilot/OpenAI) as "CRITICAL" revenue. Chapter 1 shipped the full Copilot seat provisioning machinery (REQ-1.5.1–1.5.12) and Stripe entitlements for that thesis. After research phase 3, we pivoted to authority-marketing. The Copilot/Stripe code is parked — not deleted — and may be revived in §2.10 (P3) if/when the audience justifies it.

---

### Personas

The platform serves distinct user archetypes. Every feature must be designed for at least one persona. If a feature does not clearly serve a persona's goal, it should be questioned.

| Persona | Who | Goal on Platform | Success Metric |
|---------|-----|-----------------|----------------|
| **Practitioner (Learner)** | Software engineer, data scientist, or DevOps who wants to skill-up on AI tools. Age 25–40. Hebrew-speaking. Works at Israeli tech company. | Learn practical AI skills (Copilot, agents, MCP) quickly and apply them at work tomorrow. | Completes a course, applies skill at work, returns for next course. |
| **Engineering Manager (Buyer)** | Team lead or VP R&D responsible for upskilling a team of 5–50 engineers. Budget holder. Israeli tech company. | Find a credible trainer, validate expertise, book corporate training for the team. | Submits corporate inquiry form or sends WhatsApp message. |
| **Casual Visitor (Discovery)** | Lands from Google search, LinkedIn post, or peer referral. Unknown intent. May be practitioner or manager. | Get value quickly (answer a question, watch a free lesson, read a thread). Decide if this platform is trustworthy. | Signs up (newsletter or account), consumes content, returns within 7 days. |
| **Community Member (Contributor)** | Experienced practitioner who answers questions, shares knowledge, and builds reputation. Already completed 1+ courses. | Help others, gain visibility, build professional reputation in the Israeli AI community. | Posts answers, earns accepted-answer count, stays active weekly. |
| **Content Creator (Future, P2)** | Expert practitioner who wants to publish mini-courses, templates, or prompt libraries. | Monetize expertise, reach the babook audience, build personal brand. | Publishes content, earns revenue share, attracts enrollments. |
| **Corporate HR/L&D (Secondary)** | Learning & Development or HR person researching training vendors for their engineering org. | Compare vendors, validate credentials, get pricing, present options to management. | Downloads info, forwards /corporate/ link to manager, initiates contact. |

**Persona priority:** Engineering Manager is the primary conversion target (north-star metric = inbound corporate inquiries). Practitioner is the primary engagement target (their activity creates the social proof that convinces managers). Casual Visitor is the acquisition target. All features must ultimately serve the Manager→Practitioner→Manager flywheel.

**Core journey (the funnel):**
1. **Discover** — Casual Visitor finds babook via Google (forum thread, course page) or LinkedIn (shared certificate, newsletter reshare)
2. **Engage** — Visitor watches a free lesson, reads a forum answer, or subscribes to newsletter → becomes Practitioner
3. **Trust** — Practitioner completes a course, sees certificates counter, reads testimonials → trusts Avi's expertise
4. **Convert** — Practitioner's manager (Engineering Manager) sees the employee's certificate on LinkedIn, visits /corporate/, or the Practitioner directly recommends Avi → Manager submits inquiry
5. **Retain** — After corporate gig, trained team members join platform as Practitioners, continuing the cycle

---

### Design Guidelines

> General visual and interaction design direction for all of babook.co.il. Derived from competitive research of: **Frontend Masters** (dark professional course platform), **Maven** (cohort expert-led courses), **DeepLearning.AI** (Andrew Ng authority + newsletter), **Level Effect** (gamified learning with career testimonials), **Josh Bersin** (personal brand authority blog), **Wix Engineering** (Israeli tech company culture site), **Skool** (simple community + courses). These are not abstract principles; they are extracted from platforms that successfully convert the same personas we target.

#### Design Philosophy

**"Substance over flash. Professional, not playful."**

The audience is Israeli software engineers and their engineering managers. They are allergic to marketing fluff, animated gradients, and startup theater. They respect substance, speed, and clarity. The design must feel like a tool built by an engineer, not a Squarespace template chosen by a marketer.

**Design north star:** Frontend Masters meets DeepLearning.AI in Hebrew. Dark, clean, content-dense, instructor-centric, no wasted space.

#### Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#0f1117` (near-black) | Page background, nav, footer |
| `--bg-surface` | `#1a1d27` (dark charcoal) | Cards, containers, sidebar |
| `--bg-elevated` | `#242836` (slate) | Hover states, active cards, dropdowns |
| `--text-primary` | `#f0f0f5` (off-white) | Body text, headings |
| `--text-secondary` | `#9ca3af` (muted gray) | Captions, metadata, timestamps |
| `--accent-primary` | `#3b82f6` (blue) | Links, primary buttons, progress bars |
| `--accent-warm` | `#f59e0b` (amber) | Badges, certificates, completion states |
| `--accent-success` | `#10b981` (emerald) | Success states, "active" indicators |
| `--accent-cta` | `#22c55e` (WhatsApp green) | WhatsApp button only |
| `--border` | `#2d3748` (subtle border) | Card borders, dividers |

**Rationale:** Dark theme communicates "developer tool" not "marketing site." Frontend Masters, GitHub, VS Code, and Vercel all use dark themes and are trusted by engineers. The accent blue is familiar (links), amber signals achievement (GitHub stars, badges), and WhatsApp green is an instant Israeli B2B recognition pattern.

**Light mode:** Not required for V1. If added later, swap `--bg-*` to white/gray; accent colors remain unchanged.

#### Typography

| Role | Font | Weight | Size (desktop) | Notes |
|------|------|--------|----------------|-------|
| Headings (Latin) | **Inter** | 700 (bold) | 2rem–3rem | Clean, geometric, used by Vercel/Linear |
| Headings (Hebrew) | **Heebo** | 700 | 2rem–3rem | Google Fonts, designed for Hebrew, pairs well with Inter |
| Body (Latin) | Inter | 400 | 1rem (16px) | |
| Body (Hebrew) | Heebo | 400 | 1rem (16px) | |
| Code/mono | **JetBrains Mono** | 400 | 0.875rem | For code blocks in forum, chat, lessons |

**Loading:** Use `font-display: swap`. Load via Google Fonts CDN (already pattern per REQ-1.1.7).

**RTL rules:** `dir="rtl"` on `<html>` when Hebrew. All spacing, alignment, and icon positions mirror. Bootstrap RTL variant handles most of this. Test: no clipped text, no overlapping icons, no reversed code blocks.

#### Spacing & Layout

- **Max content width:** 1200px (centered). No full-bleed text.
- **Grid:** 12-column Bootstrap grid. Cards in 3-column on desktop, 1-column on mobile.
- **Section spacing:** 80px between major page sections (desktop), 48px (mobile).
- **Card padding:** 24px internal padding. 16px gap between cards.
- **Border radius:** 8px on cards, 6px on buttons, 4px on inputs. No fully rounded corners (not playful).
- **Shadows:** Minimal. Use border + subtle background shift instead of box-shadow. Dark theme = shadows are invisible anyway.

#### Component Patterns (inspired by research)

| Component | Reference | Implementation notes |
|-----------|-----------|---------------------|
| **Course card** | Frontend Masters | Dark card, thumbnail top (16:9), title below, instructor name + avatar, duration badge, difficulty tag. Hover: subtle border-color shift to accent-primary. |
| **Instructor block** | Maven | Avi's photo (high-quality headshot, not stock), name, one-line credential ("15+ years engineering leadership, Intel/startups"), social links. Appears on course pages and /corporate/. |
| **Social proof strip** | DeepLearning.AI | Horizontal logo row (grayscale by default, color on hover). "Trained teams at:" label above. 5–8 logos max. Below hero on /corporate/ and home. |
| **Testimonial card** | Level Effect | Photo (circle, 48px), name, title, company on one line. Quote in italics. "Hired at X" or "Completed Y course" badge if applicable. Carousel on mobile, grid on desktop. |
| **Pricing tier cards** | Level Effect | 3 cards side-by-side. Center card highlighted (border: accent-primary, "Popular" badge). Each: tier name, price, feature list (checkmarks), CTA button. |
| **Newsletter CTA** | DeepLearning.AI | Inline block (not popup). Dark surface card, short value prop headline, email input + button on one line. Appears in footer of every page and between sections on long pages. |
| **WhatsApp sticky** | Israeli B2B norm | Fixed bottom-right, 56px circle, WhatsApp green, icon only. On click: opens wa.me with pre-filled message. Z-index above all content. Mobile: slightly smaller (48px), bottom-right with 16px margin. |
| **Forum thread** | Discourse/Stack Overflow | Clean thread list: title, category badge, reply count, last-activity time. Thread page: OP top, replies below, accepted-answer highlighted with green border. |
| **Chat widget** | Intercom-style | Slide-out panel from right (desktop) or bottom sheet (mobile). Does not obscure main content. Header: session context. Input at bottom with send button. Messages render markdown. |
| **Progress bar** | Frontend Masters | Thin horizontal bar (4px) at top of course page header. Green fill = % complete. Non-intrusive, always visible. |

#### Photography & Imagery

- **Avi's headshot:** Professional, approachable, not corporate-stiff. Black T-shirt or casual collar. Neutral background. Used on: hero, course pages, /corporate/, about page. Must be real (not AI-generated).
- **Course thumbnails:** Dark background, tool/topic icon (Copilot logo, agent diagram, MCP symbol), course title overlaid. Consistent 16:9 ratio. No stock photos of people typing.
- **Illustrations:** None. This is not a consumer app. If visual explanation needed, use diagrams (mermaid or simple SVG) not illustrated characters.
- **Company logos:** Grayscale SVGs. Same height (32px). Sourced only from companies where Avi has actually trained or consulted. Never fake.

#### Interaction & Motion

- **Page transitions:** None. Instant navigation. No fade-ins, no skeleton screens for content that loads in <200ms.
- **Hover states:** Border-color shift or background-color shift. Transition: 150ms ease. Never scale transforms on cards.
- **Loading states:** Spinner only for async operations (chat response, form submit). Never block navigation.
- **Scroll behavior:** Smooth scroll for anchor links only. No parallax. No scroll-triggered animations. Content is above the fold or it's not.
- **Mobile gestures:** Swipe on carousels (testimonials, course cards). Pull-to-refresh where applicable. No custom gesture overrides.

#### Accessibility

- **Contrast:** All text meets WCAG AA (4.5:1 for body, 3:1 for large text). Dark theme makes this easier — light text on dark bg naturally has high contrast.
- **Focus indicators:** Visible focus ring (2px solid accent-primary, 2px offset) on all interactive elements. Never `outline: none` without replacement.
- **Keyboard navigation:** All interactive elements reachable via Tab. Escape closes modals/panels. Enter activates buttons.
- **Screen reader:** Semantic HTML (headings hierarchy, landmarks, aria-labels on icon-only buttons). Hebrew lang attribute set.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables all transitions/animations.

#### RTL-Specific Design Rules

- **Text alignment:** Right-aligned by default (Hebrew). Code blocks remain LTR.
- **Icon position:** Leading icons switch to right side. Trailing arrows switch to left.
- **Navigation:** Menu items right-to-left. Hamburger on right side.
- **Progress bars:** Fill from right to left.
- **Breadcrumbs:** Right to left, separator mirrors.
- **Forms:** Labels right-aligned, input text right-aligned for Hebrew fields. Email/URL fields remain LTR within RTL context.
- **When English toggled:** Entire layout flips to LTR. Single source of truth: `dir` attribute on `<html>`.

#### Performance Budget

- **First Contentful Paint:** <1.5s on 3G.
- **Total page weight:** <500KB (excluding video player iframe).
- **Fonts:** Max 4 font files (Heebo regular/bold, Inter regular/bold). Subset to used character ranges.
- **Images:** WebP format, lazy-loaded below fold. Course thumbnails <50KB each.
- **JavaScript:** Minimal. No SPA framework. Django templates + vanilla JS + htmx for interactivity. Bootstrap JS only for collapse/dropdown.
- **CSS:** Single stylesheet. Bootstrap (CDN) + custom overrides (<20KB).

---

### Gamification Strategy

> Platform-wide gamification framework for babook.co.il. Designed for a professional audience (Israeli software engineers and their managers). Every gamification mechanic must pass the "would a senior engineer at Wix/Monday find this condescending?" test. If yes, kill it.

#### Philosophy: Invisible Progress, Visible Achievement

Gamification on babook is NOT Duolingo. It is NOT a game. It is a **professional development tracking system** that happens to use behavioral psychology to increase completion rates and community participation. The audience hates being "gamified" but responds strongly to:
- Progress visibility (knowing how far they've come)
- Social status (being recognized as an expert)
- Completion drives (not wanting to leave something 80% done)
- Peer comparison (healthy, opt-in competition)

**Core principle:** Reward outcomes, not inputs. Completing a course = valuable. Watching 50 videos = not necessarily valuable. Answering a question that helps someone = valuable. Posting 20 times = spam.

#### XP Economy

| Action | XP | Rationale |
|--------|-----|-----------|
| Complete a lesson | 10 | Base engagement unit |
| Complete a course | 100 | Outcome-based, not effort-based |
| First forum post | 25 | Overcomes initial participation barrier |
| Forum answer accepted | 50 | Quality signal, not volume |
| Attend an event | 30 | Shows up, participates |
| Share certificate on LinkedIn | 20 | Viral marketing for babook |
| Refer a colleague (who enrolls) | 75 | High-value action, hard to game |
| 7-day streak | 15 | Consistency bonus (modest, not dominant) |
| Publish marketplace item (approved) | 100 | Content creation is hard work |

**XP is NOT currency.** It cannot be spent or redeemed. It is a score that reflects professional development investment. No inflation, no pay-to-earn, no purchasing XP with money.

**Level system (5 tiers):**

| Level | XP Range | Title (Hebrew) | Title (English) | Unlock |
|-------|----------|----------------|-----------------|--------|
| 1 | 0–99 | מתחיל | Newcomer | Forum posting |
| 2 | 100–499 | לומד | Learner | Custom profile badge display |
| 3 | 500–1499 | מתרגל | Practitioner | Marketplace publishing eligibility |
| 4 | 1500–4999 | מומחה | Expert | Leaderboard visibility, mentoring badge |
| 5 | 5000+ | מוביל | Leader | Creator revenue share boost, featured profile |

**Anti-gaming rules:**
- Max 200 XP/day from any single category (prevents forum spam for points)
- Streak XP capped at 7-day intervals (no 365-day streak domination)
- XP from referrals requires the referred user to complete at least one lesson (prevents fake signups)
- Admin can freeze XP on suspicious accounts

#### Badge Architecture

Badges fall into 4 categories. Each badge has ONE clear trigger, no ambiguity.

**Learning badges (course journey):**
| Badge | Trigger | Icon concept |
|-------|---------|--------------|
| First Steps | Complete first lesson | Single step icon |
| Course Graduate | Complete any course | Graduation cap |
| Polyglot | Complete 3+ courses in different topics | Connected nodes |
| Speed Runner | Complete a course within 7 days of enrollment | Lightning bolt |
| Completionist | Complete ALL published courses | Crown |

**Community badges (forum + events):**
| Badge | Trigger | Icon concept |
|-------|---------|--------------|
| First Voice | Publish first forum post | Speech bubble |
| Helpful | 5 accepted answers | Checkmark in circle |
| Mentor | 25 accepted answers | Star |
| Regular | Active 30+ days in forum (any 30 days) | Calendar |
| Networker | Attend 3+ events | People group |

**Sharing badges (viral actions):**
| Badge | Trigger | Icon concept |
|-------|---------|--------------|
| Ambassador | 3 successful referrals | Megaphone |
| LinkedIn Sharer | Share 2+ certificates on LinkedIn | LinkedIn icon |
| Team Builder | Refer 5+ people from same company | Building |

**Streak badges (consistency):**
| Badge | Trigger | Icon concept |
|-------|---------|--------------|
| 7-Day Streak | 7 consecutive active days | Small flame |
| 30-Day Streak | 30 consecutive active days | Medium flame |
| 100-Day Streak | 100 consecutive active days | Large flame |

**Badge display rules:**
- Profile page shows up to 8 badges (2 rows of 4). User chooses which to display (like Xbox showcase).
- Forum posts show top 1 badge next to username (user-selected "featured badge").
- Badges are monochrome (gray) when locked, amber when earned. No animation on earn beyond a subtle 1-second highlight.
- Badge hover tooltip shows: name, description, earn date.

#### Streak System

**Definition of "active day":** User performs at least ONE of: watch a lesson (any duration), post in forum, attend an event, complete a chat session (5+ messages). Passive login does NOT count.

**Grace period:** 1 freeze per 14 days (automatic, no user action needed). If a user misses one day within a 14-day window, streak does not break. After 2 consecutive missed days, streak resets.

**Streak visibility:**
- Nav bar: small icon (flame or calendar dot) with number, next to user avatar. Only visible to the user themselves, never public.
- Profile page: streak calendar (mini heatmap, 90-day view). Light green = active, gray = inactive, amber = freeze used.
- Notification: "Your 7-day streak is at risk! Complete a lesson today to keep it." (email at 8pm if no activity that day, opt-out available).

**Anti-frustration rules:**
- Streak-at-risk notification sent only once per day, never more.
- Losing a streak has NO punishment (no XP deduction, no badge removal). It simply resets to 0.
- 100-day streak badge, once earned, is permanent even if streak later breaks.

#### Leaderboard Design

**Opt-in only.** Users must explicitly toggle "Show me on leaderboard" in settings. Default: off.

**Scope:** Monthly reset. Shows: rank, avatar, name, XP this month, top badge. Top 50 visible. User always sees their own rank even if outside top 50.

**Categories:** Overall | Learning | Community | Streaks. Tabs on leaderboard page.

**Anti-toxicity:**
- No "you dropped X positions" notifications (creates anxiety).
- No visible XP gap between ranks (prevents "I'll never catch #1" discouragement).
- Anonymous option: user can appear on leaderboard as "Anonymous Engineer" while still seeing their own position.

#### Notifications & Nudges

All gamification notifications follow these rules:
- **Max 1 gamification notification per day** (email). If multiple events occur (badge + streak + level), combine into one message.
- **In-app toast:** Small, bottom-left, auto-dismiss in 5 seconds. Shows badge icon + "Badge unlocked: First Steps!" No modal, no blocking.
- **Never interrupt active learning.** If user is watching a video or in a chat session, queue the notification for after they leave the page.
- **Opt-out granularity:** User can disable: streak reminders, badge notifications, leaderboard updates — independently.

#### Gamification Persona Alignment

| Persona | Primary mechanics | Avoid |
|---------|-----------------|-------|
| Practitioner (Learner) | Course completion progress, streaks, learning badges | Leaderboard pressure (opt-in only) |
| Community Member | Accepted answers, reputation level, mentoring badges | Volume-based rewards (prevent spam) |
| Engineering Manager | Team dashboard scores, team skill heatmap | Individual public ranking of team members |
| Casual Visitor | None until signup. Post-signup: gentle "first lesson" nudge | Any gamification before they experience value |
| Content Creator | Publishing badges, marketplace ratings, featured status | Penalizing slow publishing cadence |

#### Technical Implementation Notes

- **XP ledger:** Append-only `XPEvent(user, action, xp_delta, source_id, created_at)` table. Current XP = SUM of all events. Never mutate past events.
- **Badge evaluation:** Badges are evaluated on trigger events (course_completed, answer_accepted, etc.), not on periodic cron. Immediate feedback.
- **Streak calculation:** Single `UserStreak(user, current_count, last_active_date, freeze_used_date)` row. Updated daily via midnight cron job, not real-time.
- **Leaderboard:** Materialized view or cached query (refresh every 15 min). Never compute on page load.
- **Feature flags:** Each gamification subsystem (XP, badges, streaks, leaderboard) has an independent feature flag. Can be enabled progressively.

#### Success Metrics for Gamification

| Metric | Target | Measurement |
|--------|--------|-------------|
| Course completion rate | +20% vs pre-gamification baseline | % of enrolled users who complete |
| Weekly active users (forum) | +30% | Users with 1+ forum action/week |
| 7-day retention after signup | +15% | Users active on day 7 after registration |
| Certificate LinkedIn shares | +40% | Certificates shared / certificates issued |
| NPS impact | No decrease | Gamification must not annoy; monitor NPS monthly |

#### What We Will NOT Do

- No loot boxes, mystery rewards, or random mechanics.
- No pay-to-earn or pay-to-boost.
- No punitive mechanics (losing XP, losing badges, public shame).
- No gamification on the /corporate/ page (managers don't need game mechanics to book training).
- No sound effects, confetti explosions (except the single 2-second certificate confetti), or screen-shaking animations.
- No daily login rewards (encourages empty visits, not learning).
- No mandatory participation — all gamification is opt-in or passively accrued.

---

### 2.1 Corporate Training Page (P0)

The single most important page on the site. A dedicated landing page at `/corporate/` (or `/training/`) that sells Avi as a premium corporate AI trainer. Includes: service offerings (workshop, bootcamp, keynote), social proof (testimonials, company logos, certificates-issued counter), pricing signals, and clear calls-to-action (book a call, WhatsApp button, contact form). WhatsApp is a primary conversion lever in Israeli business culture. This page is where the entire funnel converts visitors into paying corporate clients.

**Execution discipline:** ship this page as a conversion MVP first. The first release must prove the funnel with a credible page, WhatsApp CTA, lead form, email notification, basic SEO, and mobile polish. Admin-managed content models, logo/testimonial CMS, animated counters, detailed analytics taxonomy, and retention automation are valuable, but they are follow-up polish after the page is live and generating signal.

**MVP cut for the next implementation sprint:** REQ-2.1.1, 2.1.2, 2.1.6-2.1.12, 2.1.16-2.1.19, 2.1.25-2.1.26, 2.1.29-2.1.35, 2.1.39-2.1.40, 2.1.43, 2.1.46, 2.1.58-2.1.63, 2.1.68-2.1.71. Everything else in §2.1 is the full target spec and should not block first launch.

#### UX Direction — Personas & Journeys

**Primary persona: Engineering Manager (Buyer)**
- **Entry:** Arrives from LinkedIn post, peer recommendation, Google search "AI training Israel", or forwarded by a Practitioner employee.
- **Mindset:** Evaluating vendor credibility. Needs to justify spend to VP/CFO. Time-pressured, scanning quickly.
- **Journey:** Hero section confirms relevance in 3 seconds (photo + one-liner + logos) → scrolls to service tiers to understand scope/cost → social proof validates ("60 companies trained") → FAQ removes objections → WhatsApp/form = zero-friction action.
- **UX principles:** (1) No registration required to view or contact. (2) WhatsApp is default CTA (Israeli B2B norm). (3) Price signals reduce back-and-forth ("from ₪15K"). (4) Mobile-first — managers browse on phone between meetings.
- **Success moment:** Manager taps WhatsApp button within 60 seconds of landing.

**Secondary persona: Corporate HR/L&D**
- **Entry:** Researching vendors for a training budget RFP. Comparing 3–5 options.
- **Journey:** Needs downloadable one-pager or clear scope/pricing info to present internally. FAQ + service tiers serve this need. May bookmark and return with manager.
- **UX principle:** Content should be screenshot-friendly and shareable (no interactive-only info).

**Tertiary persona: Practitioner (Referrer)**
- **Entry:** Lands on /corporate/ to share it with their manager. Already trusts Avi.
- **Journey:** Grabs URL, sends to manager on Slack/WhatsApp. Page must self-explain without context.
- **UX principle:** The page must convert a cold visitor who arrives from a shared link with zero prior context.

#### Design Direction

**Reference models:** Level Effect pricing page (tiered cards with clear differentiation) + Maven instructor pages (photo + credentials + social proof) + Israeli B2B landing pages (WhatsApp-first CTA).

**Layout (top to bottom):**
1. **Hero (viewport height, max 600px):** Left: Avi's professional photo (cropped, not full-body). Right: one-line Hebrew headline ("מאמן AI לצוותי הנדסה"), 2-line subhead (who it's for + outcome), WhatsApp CTA button (green, full-width on mobile), secondary "שלח טופס" link below.
2. **Logo strip (80px height):** "הדריכו צוותים ב-:" + 5-8 grayscale company logos. No label if fewer than 3 real logos yet.
3. **Service tiers (3 cards):** Dark cards, each with: icon (calendar/books/mic), tier name (Workshop/Bootcamp/Keynote), duration, audience size, scope bullets (3-4), price signal, individual WhatsApp CTA with pre-filled tier name.
4. **Testimonials (carousel on mobile, 3-column grid on desktop):** Photo + name + title + company + 2-sentence quote. Max 6. Rotate.
5. **FAQ (accordion):** Dark surface. Expand/collapse with smooth 200ms transition. 6-10 questions. Hebrew.
6. **Contact form (alternate path):** Simple, no-scroll form. 5 fields max + textarea. Submit = email to Avi + DB row. Success = inline "נקבל אליך תוך 24 שעות" + confetti-free confirmation.
7. **Footer CTA repeat:** WhatsApp button + phone number in plain text.

**Critical design rules for /corporate/:**
- No login required. Zero gates. Anonymous visitors must be able to contact.
- Page must load in <2 seconds. No lazy-loaded above-fold content.
- WhatsApp button visible on scroll (sticky) without being annoying. 56px circle, bottom-right.
- Mobile layout: single column, thumb-reachable CTAs, no horizontal scroll.
- The page is ONE scrollable page, not multi-tab or multi-page.

#### Gamification Direction

**Role on this page:** Minimal. The /corporate/ page is a sales page, not a learning environment. Gamification elements serve only as **social proof signals**, not as interactive mechanics.

**What appears here:**
- **Live counter strip (from social proof engine):** "127 certificates issued" / "12 companies trained" / "2,400+ active learners." These are outputs of the gamification system (badges earned, courses completed) surfaced as trust signals. The counters themselves are animated (count-up on first view) but are NOT interactive.
- **No badges, no XP, no streaks visible.** A manager does not need to see gamification mechanics. They need to see results.

**Anti-pattern:** Never show a leaderboard, badge grid, or streak counter on /corporate/. This is not the audience for game mechanics.

**Indirect gamification contribution:** Every certificate issued, every LinkedIn share, every forum answer — all driven by gamification elsewhere — feeds the live counters and testimonial pool displayed here. Gamification is the engine; /corporate/ displays the exhaust.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| | **Page Infrastructure** | | |
| REQ-2.1.1 | Page route + template | `/corporate/` route renders a dedicated template extending `base.html`. No login required. Anonymous visitors see full page. HTTP 200 for all visitors. | DONE |
| REQ-2.1.2 | SEO meta | Unique `<title>` ("הדרכות AI לצוותי הנדסה — babook"), `<meta description>` (155 chars, Hebrew, includes "AI training Israel"), canonical URL, no `noindex`. Page included in `sitemap.xml`. | DONE |
| REQ-2.1.3 | Open Graph tags | `og:title`, `og:description`, `og:image` (1200×630 social card with Avi photo + headline), `og:url`, `og:type=website`. Twitter card (`summary_large_image`). Image hosted on static, not generated on-the-fly. | DEFERRED |
| REQ-2.1.4 | JSON-LD structured data | `Organization` + `Service` schema markup. Includes: name, description, provider (Avi), areaServed (Israel), price range signal. Validates via Google Rich Results Test. | DEFERRED |
| REQ-2.1.5 | Language toggle | Hebrew default (`dir="rtl"`, `lang="he"`). English toggle available (same URL with `?lang=en` or session preference). All content blocks have bilingual versions. | DEFERRED |
| REQ-2.1.6 | Performance | Page weight <400KB total (excluding fonts from CDN cache). First Contentful Paint <1.5s on 3G. No render-blocking JS. Hero image optimized WebP, above-fold content server-rendered (no JS dependency). | IN PROGRESS |
| REQ-2.1.7 | Responsive layout | Single-column mobile (≥360px), three-column desktop tier cards (≥992px). No horizontal scroll at any breakpoint. Thumb-reachable CTAs on mobile (bottom 60% of screen). Tested on: iPhone SE, iPhone 14, Samsung Galaxy, iPad, 1920px desktop. | IN PROGRESS |
| | **Hero Section** | | |
| REQ-2.1.8 | Hero layout | Viewport height (max 600px). Desktop: two-column (photo left 40%, text+CTA right 60%). Mobile: stacked (photo top, text below, CTA full-width). No content below fold is required to understand the value prop. | DONE |
| REQ-2.1.9 | Avi photo | Professional headshot (real, not AI-generated). WebP format, max 150KB. Cropped chest-up. Neutral or dark background matching `--bg-primary`. Responsive: 300px width desktop, 200px mobile. `alt` text: "אבי סלמון — מאמן AI". | IN PROGRESS |
| REQ-2.1.10 | Headline + subhead | H1 headline: "מאמן AI לצוותי הנדסה" (bold, Heebo 700, 2.5rem desktop / 1.75rem mobile). Subhead (2 lines max): target audience + outcome statement. `--text-primary` color. | DONE |
| REQ-2.1.11 | Hero WhatsApp CTA | Primary button: WhatsApp green (`--accent-cta`), full-width on mobile, contains WhatsApp icon + "דבר איתי בוואטסאפ". Click → `wa.me/972XXXXXXXXX?text=<pre-filled Hebrew message>`. Pre-filled: "היי אבי, אשמח לשמוע על הדרכות AI לצוות שלי." | IN PROGRESS |
| REQ-2.1.12 | Hero secondary CTA | Text link below WhatsApp button: "או שלח טופס ←". Smooth-scrolls to contact form section. Styled as underlined link, `--accent-primary` color. | DONE |
| | **Logo Strip (Social Proof)** | | |
| REQ-2.1.13 | Company logos row | Horizontal strip, 80px height. Label: "הדריכו צוותים ב-:" (Heebo 400, `--text-secondary`). 5–8 company logos in a row, grayscale SVG, uniform 32px height. CSS grid with auto-fit. Hover: logo transitions to color (200ms ease). | DEFERRED |
| REQ-2.1.14 | Logo empty state | If fewer than 3 approved logos in DB: hide entire logo strip section. No sad-looking 1-logo display. Graceful degradation. | DEFERRED |
| REQ-2.1.15 | Logo admin management | Django admin: `CompanyLogo(name, svg_file, url, display_order, is_active, permission_evidence, approved_at)`. Only `is_active=True` logos render on page. Permission evidence field stores reference to approval email/doc. | DEFERRED |
| | **Service Tiers** | | |
| REQ-2.1.16 | Tier cards layout | Three cards side-by-side (desktop), stacked (mobile). Dark surface cards (`--bg-surface`), 8px border-radius, 24px padding. Center card highlighted: 2px border `--accent-primary` + "הכי פופולרי" badge (amber). | DONE |
| REQ-2.1.17 | Workshop card | Icon: calendar. Title: "סדנה". Duration: "יום אחד (6-8 שעות)". Audience: "8-30 משתתפים". Scope bullets (3-4): hands-on exercises, live coding, tool setup, Q&A. Price signal: "החל מ-₪15,000". Individual WhatsApp CTA: pre-filled with "אשמח לשמוע על סדנת AI ליום אחד." | IN PROGRESS |
| REQ-2.1.18 | Bootcamp card | Icon: books. Title: "בוטקאמפ". Duration: "3-5 ימים". Audience: "8-20 משתתפים". Scope bullets: multi-day deep dive, project-based, follow-up mentoring, custom curriculum. Price signal: "החל מ-₪35,000". Individual WhatsApp CTA with bootcamp text. | IN PROGRESS |
| REQ-2.1.19 | Keynote card | Icon: microphone. Title: "הרצאה". Duration: "45-90 דקות". Audience: "50-500 משתתפים". Scope bullets: inspirational, high-level, thought-leadership, conference/all-hands format. Price signal: "החל מ-₪8,000". Individual WhatsApp CTA with keynote text. | IN PROGRESS |
| REQ-2.1.20 | Tier data model | Django model `ServiceTier(name_he, name_en, icon, duration_he, duration_en, audience_he, audience_en, bullets_he, bullets_en, price_signal_he, price_signal_en, whatsapp_message, display_order, is_active)`. Editable via Django admin. Page renders from DB, not hardcoded template. | DEFERRED |
| | **Testimonials** | | |
| REQ-2.1.21 | Testimonial display | Desktop: 3-column grid (max 6 testimonials). Mobile: horizontal swipe carousel (1 visible + peek of next). Card: circle photo (48px), name (bold), "Title @ Company" (`--text-secondary`), 2-3 sentence quote (italic), optional badge. | DEFERRED |
| REQ-2.1.22 | Testimonial empty state | If fewer than 2 approved testimonials in DB: hide entire testimonial section. No single lonely testimonial. | DEFERRED |
| REQ-2.1.23 | Testimonial data model | Django model `Testimonial(person_name, job_title, company_name, quote_he, quote_en, photo, badge_text, display_order, is_active, consent_given_at, consent_evidence, created_at)`. Admin can approve/reject. Only `is_active=True` with `consent_given_at` set render on page. | DEFERRED |
| REQ-2.1.24 | Testimonial consent tracking | `consent_evidence` field: text/file field storing reference to written consent (email screenshot, form response link). Testimonial cannot be activated (`is_active=True`) if `consent_given_at` is null. Admin UI enforces this. | DEFERRED |
| | **FAQ** | | |
| REQ-2.1.25 | FAQ accordion | 6-10 collapsible Q&A items. Dark surface container. Click question → expands answer with 200ms slide transition. Only one item open at a time (accordion behavior). Keyboard accessible: Enter/Space toggles, arrow keys navigate. | DONE |
| REQ-2.1.26 | FAQ content (Hebrew) | Questions covering: (1) מה ההבדל בין סדנה לבוטקאמפ? (2) האם אפשר להתאים את התוכן לצוות שלנו? (3) מה המחיר? (4) האם יש אפשרות לשילוב אונליין? (5) באיזה שפה ההדרכה? (6) מה כולל המחיר? (7) האם יש NDA? (8) מה לגבי תשלום ותנאים? (9) כמה זמן מראש צריך להזמין? (10) האם אתה מגיע למשרדים שלנו? | IN PROGRESS |
| REQ-2.1.27 | FAQ data model | Django model `FAQ(question_he, question_en, answer_he, answer_en, display_order, page, is_active)`. `page` field allows reuse on other pages later. Editable in admin. Rendered from DB. | DEFERRED |
| REQ-2.1.28 | FAQ structured data | JSON-LD `FAQPage` schema on page when FAQ items present. Each Q&A as `Question` + `acceptedAnswer`. Validates via Google Rich Results Test. Enables FAQ rich snippets in Google search results. | DEFERRED |
| | **Contact Form** | | |
| REQ-2.1.29 | Form fields | Fields: name (required, text), company (required, text), role (optional, text), team_size (required, select: 1-5/6-15/16-50/50+), training_type (required, select: workshop/bootcamp/keynote/not sure), message (optional, textarea max 1000 chars). All labels in Hebrew. | DONE |
| REQ-2.1.30 | Form submission (AJAX) | Submit via AJAX (no page reload). On success: hide form, show inline confirmation message "תודה! נחזור אליך תוך 24 שעות." (green accent). On error: show field-level validation errors in Hebrew. Button shows spinner during submission. | DONE |
| REQ-2.1.31 | Form → DB + Email | On valid submit: (1) Create `CorporateLead` row, (2) Send notification email to Avi via Resend with all form data + UTM params + referrer URL + timestamp. Email subject: "ליד חדש מ-/corporate/ — [company name]". | DONE |
| REQ-2.1.32 | Spam protection | Honeypot field (hidden CSS, not `type=hidden`). If filled → silent reject (HTTP 200, no error message, no DB write). Rate limit: max 3 submissions per IP per hour. CSRF token required (Django default). | DONE |
| REQ-2.1.33 | Form privacy notice | Below submit button, small text (`--text-secondary`, 0.8rem): "הפרטים שלך ישמשו ליצירת קשר בלבד. ראה [מדיניות פרטיות](/privacy/)." Link opens in new tab. No checkbox needed (B2B legitimate interest). | DONE |
| REQ-2.1.34 | Form accessibility | All inputs have associated `<label>` elements. Error messages announced via `aria-live="polite"`. Form navigable via keyboard (Tab order logical). Focus trapped in form when submitting (no accidental double-submit). Submit button has `aria-label`. | DONE |
| | **Lead Management** | | |
| REQ-2.1.35 | CorporateLead model | `CorporateLead(name, company, role, team_size, training_type, message, source_page, utm_source, utm_medium, utm_campaign, utm_content, referrer_url, ip_hash, created_at, status, status_changed_at, notes)`. `ip_hash` = SHA-256 of IP (for rate limiting, not tracking). | DONE |
| REQ-2.1.36 | Lead status workflow | Status enum: `new` → `contacted` → `meeting_scheduled` → `proposal_sent` → `won` → `lost`. Status changes log timestamp in `status_changed_at`. Admin can add freeform `notes` per lead. | DEFERRED |
| REQ-2.1.37 | Lead admin view | Django admin list: name, company, tier, status (colored badge), created_at (relative "3 days ago"), notes preview. Filters: status, training_type, date range. Search: name, company. Bulk action: change status. | DEFERRED |
| REQ-2.1.38 | Lead data retention | Automated: leads with status `lost` and `status_changed_at` > 24 months ago → anonymize (clear name, company, message; retain aggregate row for conversion metrics). Manual purge available via admin action. | DEFERRED |
| | **WhatsApp Integration** | | |
| REQ-2.1.39 | Sticky WhatsApp button | Fixed position, bottom-right, 56px circle (48px on mobile). WhatsApp green background, white icon (Bootstrap Icons `bi-whatsapp`). `z-index: 1000`. Visible on all scroll positions. 16px margin from viewport edge. | DONE |
| REQ-2.1.40 | WhatsApp deep link | Click → opens `https://wa.me/972XXXXXXXXX?text=<encoded message>`. Phone number stored in env var `WHATSAPP_NUMBER` (not hardcoded). Message URL-encoded. Works on desktop (WhatsApp Web) and mobile (WhatsApp app). | IN PROGRESS |
| REQ-2.1.41 | Per-tier WhatsApp messages | Each service tier card has its own WhatsApp CTA. Pre-filled message includes the tier name: "היי אבי, אני מתעניין/ת ב[סדנה/בוטקאמפ/הרצאה] בנושא AI לצוות שלי." Tier name injected from page tier data. | IN PROGRESS |
| REQ-2.1.42 | WhatsApp click tracking | Every WhatsApp button click fires Plausible custom event `corporate_whatsapp_click` with props: `tier` (hero/workshop/bootcamp/keynote/sticky), `device` (mobile/desktop). Vanilla JS, no external dependencies. | DEFERRED |
| | **Conversion Tracking (Plausible)** | | |
| REQ-2.1.43 | Form submit event | On successful form submission (AJAX 200 response), fire Plausible event `corporate_form_submit` with props: `training_type`, `team_size`. No PII in event props. | DONE |
| REQ-2.1.44 | Tier click event | On click of any service tier card (anywhere on card), fire Plausible event `corporate_tier_click` with prop: `tier` (workshop/bootcamp/keynote). Tracks interest distribution. | DEFERRED |
| REQ-2.1.45 | Scroll depth tracking | Fire Plausible events at 25%, 50%, 75%, 100% scroll depth: `corporate_scroll` with prop `depth`. Measures how far down the page visitors get. Implemented via Intersection Observer (no scroll event listener spam). | DEFERRED |
| REQ-2.1.46 | UTM parameter capture | On page load, extract `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` from URL query params. Store in hidden form fields (auto-populate contact form). Pass to lead model on submit. Plausible captures UTMs automatically. | DONE |
| | **Counters (Social Proof Metrics)** | | |
| REQ-2.1.47 | Counter strip | Horizontal strip between logo section and tiers. 3-4 metric boxes: "X תעודות הונפקו" / "X חברות הודרכו" / "X+ לומדים פעילים" / optional "X.X ⭐ דירוג ממוצע". Numbers large (2rem bold, `--accent-warm`), labels small (0.875rem, `--text-secondary`). | DEFERRED |
| REQ-2.1.48 | Counter data source | Counters query live aggregated data: certificates = `COUNT(Certificate WHERE issued=True)`, companies = `COUNT(CompanyLogo WHERE is_active=True)` OR manual override via `SiteConfig` model, learners = `COUNT(User WHERE is_active=True AND last_login > 30 days ago)`. Values cached (15-min TTL). | DEFERRED |
| REQ-2.1.49 | Counter animation | On first viewport entry (Intersection Observer), animate from 0 to actual value over 1.5 seconds (easing: ease-out). Animation fires once per page load, not on every scroll past. If `prefers-reduced-motion: reduce`, show final number immediately (no animation). | DEFERRED |
| REQ-2.1.50 | Counter empty state | If total certificates < 10: hide counter strip entirely. If any individual counter is 0: hide that specific counter. Never show "0 companies trained." Minimum thresholds configurable via `SiteConfig`. | DEFERRED |
| | **Design System Compliance** | | |
| REQ-2.1.51 | Color palette | All elements use CSS custom properties from Design Guidelines. Background: `--bg-primary`. Cards: `--bg-surface`. Text: `--text-primary` / `--text-secondary`. Borders: `--border`. No hardcoded hex values in template. | DONE |
| REQ-2.1.52 | Typography | Headings: Heebo 700 (Hebrew), Inter 700 (English). Body: Heebo 400 / Inter 400. Sizes per Design Guidelines. Google Fonts loaded with `font-display: swap`. Maximum 4 font files. | DONE |
| REQ-2.1.53 | Spacing | Section spacing: 80px desktop, 48px mobile. Card padding: 24px. Card gap: 16px. Max content width: 1200px centered. All spacing via Bootstrap utilities or CSS custom properties. | DONE |
| REQ-2.1.54 | Component patterns | Tier cards match "Pricing tier cards" pattern. Testimonials match "Testimonial card" pattern. WhatsApp button matches "WhatsApp sticky" pattern. All from Design Guidelines Component Patterns table. | DONE |
| | **RTL & Bilingual** | | |
| REQ-2.1.55 | RTL layout (Hebrew default) | Page renders `dir="rtl"` with `lang="he"`. All text right-aligned. Icons positioned correctly for RTL. Bootstrap RTL variant loaded. Hero photo on RIGHT (text on left) in RTL mode. | DONE |
| REQ-2.1.56 | LTR layout (English) | When English selected: `dir="ltr"`, `lang="en"`. All text left-aligned. Hero photo on LEFT. All content blocks switch to English versions. URL/email fields remain LTR in both modes. | DEFERRED |
| REQ-2.1.57 | Bilingual content | All user-facing text stored in paired `_he` / `_en` fields or equivalent content source. Template renders correct language based on session/cookie preference. Fallback: Hebrew if English translation missing. | DEFERRED |
| | **Accessibility** | | |
| REQ-2.1.58 | WCAG AA compliance | All text meets 4.5:1 contrast ratio (body) / 3:1 (large text). Verified via automated contrast checker. All images have `alt` text. Page passes Lighthouse accessibility audit ≥ 90. | IN PROGRESS |
| REQ-2.1.59 | Keyboard navigation | Full page navigable via keyboard. Tab order: nav → hero CTA → logo strip (skip) → tier cards → testimonials → FAQ (expand/collapse via Enter) → contact form → footer. Skip-to-content link present. | IN PROGRESS |
| REQ-2.1.60 | Screen reader | Semantic HTML: single `<h1>`, logical heading hierarchy (`h2` per section, `h3` per tier), `<main>`, `<nav>`, `<footer>` landmarks. FAQ uses `<details>`/`<summary>` or ARIA accordion pattern. Form errors announced via `aria-live`. | IN PROGRESS |
| REQ-2.1.61 | Reduced motion | `@media (prefers-reduced-motion: reduce)`: disable counter animation, FAQ transition, carousel auto-advance. All interactions remain functional, only animation removed. | IN PROGRESS |
| | **Mobile-Specific** | | |
| REQ-2.1.62 | Mobile hero | Photo: 200px width, centered above text. CTA button: full-width, min height 48px (touch target). Subhead max 2 lines. No horizontal scroll. | IN PROGRESS |
| REQ-2.1.63 | Mobile tiers | Cards stack vertically. Each card full-width. WhatsApp CTA per card: full-width button, min 48px height. Highlighted card (bootcamp) has visible border on mobile too. | IN PROGRESS |
| REQ-2.1.64 | Mobile testimonials | Horizontal swipe carousel. Touch swipe + dot indicators below. 1 card visible + 20% peek of next. Auto-advance every 5s (pauses on touch). Cards min-height to prevent layout shift. | DEFERRED |
| REQ-2.1.65 | Mobile sticky WhatsApp | Bottom-right, 48px circle, 16px margin from viewport edges. Does not overlap form submit button when form is in view. `z-index` below modal/dropdown layers. | IN PROGRESS |
| | **Admin & Configuration** | | |
| REQ-2.1.66 | SiteConfig model | Singleton model: `SiteConfig(whatsapp_number, hero_headline_he, hero_headline_en, hero_subhead_he, hero_subhead_en, counter_min_certificates, counter_min_companies, counter_min_learners, manual_companies_count, manual_learners_count)`. Editable via admin. Page reads from this — allows copy changes without code deploy. | DEFERRED |
| REQ-2.1.67 | Admin preview | "View on site" link from admin models (CorporateLead, ServiceTier, FAQ, Testimonial) opens `/corporate/` in new tab. Staff users see a thin admin bar at top with "Edit in admin" links per section. | DEFERRED |
| | **Security** | | |
| REQ-2.1.68 | CSRF protection | Contact form includes `{% csrf_token %}`. AJAX submissions send CSRF token in header. Rejected without valid token (Django default). | DONE |
| REQ-2.1.69 | Input sanitization | All form inputs sanitized server-side. No raw HTML rendered from user input (Django autoescaping). `message` field: strip HTML tags, limit to 1000 chars, validate UTF-8. | DONE |
| REQ-2.1.70 | Rate limiting | Form submissions: max 3/hour per IP (via Django cache + decorator). WhatsApp clicks: no rate limit needed (client-side navigation only). Failed rate-limit attempts: log IP hash + timestamp, return HTTP 429 with friendly Hebrew message. | DONE |
| REQ-2.1.71 | No login requirement | Page renders fully for `AnonymousUser`. No `@login_required` decorator. No conditional blocks that hide content from non-authenticated users. Contact form works without authentication. | DONE |

#### Legal & Privacy Direction

**Applicable law:** Israeli Privacy Protection Law (1981) + GDPR (EU visitors possible via LinkedIn/Google traffic) + Israeli Spam Law (חוק התקשורת, 2008).

**Contact form data:**
- **Legal basis:** Legitimate interest (B2B lead processing). No explicit consent checkbox required for B2B contact forms under Israeli law, but transparency is mandatory.
- **Privacy notice (inline):** Below the submit button, one line: "הפרטים שלך ישמשו ליצירת קשר בלבד. ראה מדיניות פרטיות." with link to `/privacy/`.
- **Data retention:** `CorporateLead` records retained for 24 months after last status change. Leads marked `lost` for 12+ months should be purged or anonymized (delete name/company, keep aggregate count).
- **No marketing opt-in implied:** Submitting the contact form does NOT subscribe the user to the newsletter. These are separate consent actions.

**WhatsApp CTA:**
- Clicking the WhatsApp button transfers the user to WhatsApp (Meta platform). No personal data is sent from babook to WhatsApp — the user initiates the conversation themselves. No consent needed for this flow.
- The pre-filled message does NOT include any user data, only the service tier name.

**Testimonials display (from §2.5):**
- Every testimonial displayed on /corporate/ requires explicit written consent from the quoted person. Consent must cover: name, job title, company name, and quote text. Store consent evidence (email screenshot or form submission) in admin.
- Company logos require permission from the company (email confirmation from authorized contact). Never display a company logo without written approval.

**Plausible analytics (REQ-2.1.8):**
- Plausible is cookieless and GDPR-compliant by design. No cookie banner needed for Plausible alone. Custom events (`corporate_whatsapp_click`, etc.) do not track PII.
- If any future tool requires cookies (e.g., A/B testing), cookie consent must be added. For now: no cookies on /corporate/ except Django session cookie (functional, exempt from consent).

**Accessibility & anti-discrimination:**
- All pricing information must be equally accessible to all visitors (no discriminatory pricing by location/identity).
- Contact form must be keyboard-accessible and screen-reader-friendly (WCAG AA).

**Stage: TRACKED** — Full target REQs specced (71), with a lean conversion MVP explicitly separated from deferred CMS/social-proof/polish requirements. Backlog sprints should execute the MVP first, then pull deferred items forward only after the page is live or a real content-change need appears.

---

### 2.2 Authority Content (P0)

Practical AI courses that prove Avi's expertise and attract the target audience (engineering managers, team leads, practitioners). Courses are short (2-4 hours each), opinionated, Hebrew-first, and focused on current tools (Copilot, AI agents, MCP, prompt engineering). Some courses are free (top-of-funnel), others are paid (platform revenue). They serve as the funnel: users discover babook via Google or LinkedIn, take a course, trust Avi, and eventually their manager books a corporate session. Where possible, courses include optional cohort start-dates and checkpoints to boost completion via accountability.

Note: video player, signed URLs, progress tracking, and free-preview gating already shipped under REQ-1.3.*. This section covers the **content layer** on top: course catalog UX, lesson structure, completion flow, and corporate-funnel hooks.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Learner)**
- **Entry:** Google search "Copilot tutorial Hebrew", LinkedIn post by Avi, newsletter link, or forum thread recommendation.
- **Mindset:** Wants immediate practical value. Not looking for academic theory. Evaluating whether to invest 2–4 hours.
- **Journey:** Catalog page → scan thumbnails/titles/durations → click interesting course → read outcomes + preview a free lesson → decide to enroll → watch sequentially → complete → get certificate → share on LinkedIn.
- **UX principles:** (1) Progress must feel effortless — auto-resume, clear "next" CTA, no navigation friction. (2) Free preview lessons must be high-value (not teasers) to prove quality. (3) Short lessons (10–15 min each) respect attention span. (4) Mobile viewing supported (commute learning). (5) Completion must feel rewarding — certificate, counter, congratulations moment.
- **Key friction points to eliminate:** Registration wall before preview (bad — allow anonymous preview). Unclear course length. No progress indicator. No "what's next" after completion.
- **Success moment:** Practitioner applies a technique from the course at work the next day.

**Secondary persona: Casual Visitor (Discovery)**
- **Entry:** Lands on a specific course page from Google or social media.
- **Journey:** Watches free preview → impressed → browses catalog → signs up for newsletter or enrolls in full course.
- **UX principle:** Course pages must work as standalone landing pages (hero, outcomes, preview, social proof) — not just list items that require browsing from catalog first.

**Corporate funnel connection:** Every course completion feeds the flywheel: certificate shared on LinkedIn → manager sees it → visits /corporate/. The course page footer explicitly bridges this ("Train your whole team → /corporate/").

#### Design Direction

**Reference models:** Frontend Masters (course catalog as card grid with paths + latest + popular sections) + DeepLearning.AI (short courses with partner logos and clear duration) + Maven (instructor-centric course cards with photo + credential).

**Catalog page (`/courses/`):**
- **Filter bar (sticky top):** Horizontal pill-style filter buttons: All | Copilot | Agents | MCP | Prompting. Active = filled accent-primary, inactive = bordered. No dropdown. One-click filter.
- **Course grid:** 3 columns desktop, 1 column mobile. Card structure: dark surface, 16:9 thumbnail (top), below: difficulty tag (beginner/intermediate), title (bold, 1.25rem), duration + lesson count ("8 שיעורים · 2.5 שעות"), Avi's mini-avatar + "אבי סלמון" (bottom-left), "Free" badge (green, top-right) on free courses.
- **Sort:** Default by popularity. Secondary: newest, shortest, longest. Minimal — don't over-engineer filters for <10 courses.
- **Empty state:** "Coming soon" cards with topic + "notify me" button for announced but unfinished courses.

**Course detail page (`/courses/<slug>/`):**
- **Hero section:** Course thumbnail (large, 40% width desktop), beside it: title, 3-4 bullet learning outcomes (checkmark icons), difficulty + duration + format badges, "הרשמה (חינם)" CTA button (or "צפה בתצוגה מקדימה" for paid).
- **Lesson list:** Numbered list with icons. Free preview lessons: unlocked icon + "Preview" badge. Paid: lock icon. Playing lesson: highlighted row with progress %.
- **Instructor section:** Avi headshot (larger, 120px), 3-line bio, link to /corporate/. Same block reused across all courses.
- **Corporate hook footer:** Full-width dark banner: "מעוניין להכשיר צוות שלם? ← /corporate/" with WhatsApp button.

**Lesson page:**
- **Video player:** Bunny iframe, 16:9, full content-width. Below: lesson title + duration. Thin progress bar (green, 4px) at very top of page.
- **Below video:** Lesson notes (rendered markdown, dark surface card). "Next lesson" button (prominent, right-aligned for RTL). AI Mentor chat sidebar trigger (icon in right margin).
- **Navigation:** Previous/Next arrows. Lesson sidebar (collapsible on mobile) showing full lesson list with current highlighted.

**Critical design rules for courses:**
- Free preview lessons play without any login prompt (anonymous users see video).
- Course cards must look equally good with 3 courses or 30 courses.
- No "Buy now" dark patterns. If free, it's clearly free. If paid, price is shown upfront before any form.
- Mobile: video plays full-width, notes below, chat accessible via bottom sheet.

#### Gamification Direction

**Primary mechanics:** Progress tracking, completion rewards, streak integration, and milestone badges. Courses are the central XP-earning activity on the platform.

**Lesson completion XP:**
- Each lesson watched to 95%+ = 10 XP. Instant feedback: small toast "+ 10 XP" in bottom-left (auto-dismiss 3 seconds). Never interrupts video playback.
- Course completion = 100 XP bonus (on top of per-lesson XP). Triggers: badge evaluation, certificate generation, celebration screen.

**Progress visualization (in course context):**
- **Thin progress bar (4px, green)** at top of course page. Shows % of lessons completed. This is NOT XP — it's simple progress.
- **Lesson list checkmarks:** Completed lessons get a green checkmark. Current lesson highlighted. Remaining: muted, locked icon if paid.
- **"Next milestone" micro-prompt (subtle):** Below the lesson list, a single line: "2 more lessons until your certificate 🎓". Only shows when >50% complete. Not modal, not annoying — just a gentle nudge in the existing UI.

**Badge triggers from courses:**
- "First Steps" badge: first lesson completed (any course).
- "Course Graduate" badge: any course completed.
- "Speed Runner" badge: course completed within 7 days of enrollment.
- "Polyglot" badge: 3 courses in different topic categories.
- "Completionist" badge: all published courses completed.

**Streak contribution:** Watching a lesson (any duration, any course) counts as an active day for streak purposes.

**Anti-gaming:** Rewatching an already-completed lesson does NOT award XP again. Progress is monotonic.

**Corporate funnel integration:** Course completion feeds the social proof counter on /corporate/. "127 certificates issued" grows with every gamified completion event.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.2.1 | Course catalog page | `/courses/` lists all published courses with thumbnail, title, duration, lesson count, difficulty tag. Filterable by topic (Copilot / Agents / MCP / Prompting). Hebrew-first, English toggle. | TODO |
| REQ-2.2.2 | Course detail page | `/courses/<slug>/` shows description, learning outcomes, lesson list with free-preview badges, instructor bio (Avi), "Enroll free" CTA. | TODO |
| REQ-2.2.3 | Enrollment flow | Click "Enroll" → login if needed → `Enrollment(user, course, enrolled_at)` row created. Free courses: immediate access. Paid courses: payment gate (Stripe or mock) before enrollment completes. Redirect to first lesson on success. | TODO |
| REQ-2.2.4 | Lesson page | Existing Bunny player + progress (REQ-1.3.*) + lesson notes (markdown) + "next lesson" CTA + AI Mentor chat sidebar stub (filled by §2.7). | TODO |
| REQ-2.2.5 | Course completion | When all lessons ≥ 95% watched, mark course `completed`. Trigger: certificate issue stub (§2.6), social-proof counter increment (§2.5), email "You completed X — share on LinkedIn". | TODO |
| REQ-2.2.6 | Initial course set | At least 3 published courses at launch, Hebrew audio + Hebrew captions, English captions optional. Topics: Copilot for engineers, AI agents basics, MCP fundamentals. | TODO |
| REQ-2.2.7 | Cohort start-dates (optional) | Course can optionally have a `cohort_start_date` + `cohort_end_date`. Banner on course page shows "Next cohort starts X". Enrolled users get 3 cohort emails: kickoff, mid-checkpoint, completion nudge. | TODO |
| REQ-2.2.8 | SEO for courses | Each course page has unique `<title>`, `<meta description>`, Open Graph image, JSON-LD `Course` schema, included in `sitemap.xml`. | TODO |
| REQ-2.2.9 | Corporate funnel hook | Every course page footer block: "מאמן את הצוות שלך? ראה /corporate/". Click logs Plausible event `course_to_corporate`. | TODO |

#### Legal & Privacy Direction

**Video content ownership:**
- All course videos are Avi's original content. Courses must not include substantial third-party copyrighted material (short fair-use clips for educational purpose are acceptable under Israeli Copyright Act §19).
- Tool logos (GitHub Copilot, VS Code, etc.) used in course thumbnails: permitted under fair use for educational/descriptive purposes. Never imply endorsement.

**User enrollment data:**
- **Legal basis:** Contract performance (user enrolls = agreement to receive the course service).
- **Data collected on enrollment:** user_id, course_id, enrolled_at, progress events. This is functional data necessary for service delivery.
- **Video progress tracking (REQ-1.3.5):** Heartbeat every 15 seconds records `last_position_seconds`. This is essential for the resume-playback feature (legitimate interest). Not shared externally. Retained while user has an active account.

**Bunny Stream (video CDN):**
- Bunny.net acts as a data processor. Bunny receives: viewer IP (for CDN delivery), signed token (for access control). Bunny's privacy policy confirms no viewer profiling.
- **DPA (Data Processing Agreement):** Verify Bunny.net's standard DPA covers GDPR processor obligations. Document in `/privacy/` that video delivery uses a third-party CDN.

**Free preview for anonymous users:**
- Anonymous video viewing collects NO personal data on babook's side (no user row, no progress tracking). Bunny may log IPs in server access logs (standard CDN behavior, disclosed in privacy policy).

**Course completion emails:**
- "You completed X — share on LinkedIn" email is a transactional/service email (not marketing). Permitted without separate email consent because it relates directly to the user's action. However, include an opt-out link for these service emails in user profile settings.

**Cohort emails (REQ-2.2.7):**
- Cohort emails (kickoff, mid-checkpoint, completion nudge) are service emails tied to user's enrollment action. Legal basis: contract performance. Include unsubscribe/opt-out option per email.

---

### 2.3 Newsletter & Audience Capture (P0)

Email signup mechanism (newsletter) that captures every visitor into a lead pool. Weekly AI digest keeps Avi top-of-mind with 2,000+ subscribers. Every page includes a signup CTA. The newsletter is the direct line between platform visitors and future corporate leads — a manager who reads the newsletter regularly will eventually need training for their team.

#### UX Direction — Personas & Journeys

**Primary persona: Casual Visitor (Discovery) → Subscriber**
- **Entry:** On any page (home, course, forum thread, blog post).
- **Mindset:** Mildly interested but not ready to commit. Willing to give email for clear value.
- **Journey:** Sees inline CTA ("Weekly AI insights for engineers — free") → enters email → receives confirmation email → clicks confirm → gets first issue next week → reads regularly → eventually enrolls in course or forwards to manager.
- **UX principles:** (1) CTA must state the value proposition, not just "subscribe". (2) No more than email field + button — name is optional, never mandatory upfront. (3) Confirmation email must arrive within 30 seconds (deliverability is credibility). (4) First email should deliver immediate value (not "thanks for subscribing"). (5) Unsubscribe must be one click, no login required.
- **Key friction points to eliminate:** Popup fatigue (use inline/footer, not modal popups). Vague value prop ("stay updated" is weak). Double opt-in email going to spam.

**Secondary persona: Practitioner (Post-course)**
- **Entry:** Just completed a course or enrolled. System prompts newsletter opt-in.
- **Journey:** Already engaged, high trust. Newsletter keeps them in the ecosystem between courses.
- **UX principle:** Opt-in prompt should feel like a natural next step ("Get weekly tips like the ones in this course"), not a sales grab.

**Engineering Manager persona (passive):**
- **Entry:** Manager subscribes after visiting /corporate/ but not yet ready to buy.
- **Journey:** Receives weekly digest → sees Avi's depth weekly → when budget cycle comes, already trusts enough to book without further research.
- **UX principle:** Newsletter content must mix practitioner-level tips with manager-relevant signals (industry trends, team productivity data, case studies).

#### Design Direction

**Reference models:** DeepLearning.AI "The Batch" newsletter signup (inline, value-prop-driven, on every page) + Substack (clean email template, readable on mobile) + Pat Flynn (CTA in multiple locations without being annoying).

**Signup CTA component (appears site-wide):**
- **Inline footer variant:** Dark surface card (full content-width), single row: left = short headline ("טיפ AI שבועי לתיבה שלך · 2,000+ מהנדסים כבר בפנים"), right = email input + "הרשמה" button. One line. No name field. Mobile: stacks to two rows.
- **Post-course variant:** After course completion screen: "רוצה להמשיך ללמוד? הצטרף לניוזלטר השבועי" + email field. Pre-filled if user is logged in.
- **Lead-magnet variant:** Course-page sidebar: PDF icon + "מדריך Copilot חינם" + email field + "שלח לי" button. Tracks which lead magnet captured the subscriber.

**Placement rules:**
- Every page has exactly ONE newsletter CTA. Not two. Not zero.
- Home page: mid-page section break (between courses and community).
- Course page: after lesson list, before corporate footer hook.
- Forum: sidebar on desktop, after 3rd thread on mobile.
- Blog/article pages: end of article.

**Email template design:**
- Max-width 600px. Dark background matching site palette. Or inverted (white bg, dark text) for better email-client compatibility — test and choose.
- Header: babook logo (small), issue number, date.
- Content: 1 main article (3-5 paragraphs, practical tip), 2-3 link bullets ("Read more on..."), corporate CTA block at bottom ("הזמן סדנה לצוות → /corporate/").
- Footer: unsubscribe (one-click), social links, "Forward to a colleague" link.
- Must render correctly in Gmail, Outlook, Apple Mail. No custom fonts in email (system stack).

**Critical design rules for newsletter:**
- No popups. Ever. No exit-intent popups. No timed modals. Israeli engineers close tabs instantly when annoyed.
- Confirmation email arrives within 30 seconds. Test deliverability to Gmail and Outlook before launch.
- Subscriber count shown publicly only when >500 ("הצטרף ל-X מהנדסים"). Below that, hide count.

#### Gamification Direction

**Role:** Newsletter is an engagement channel for gamification, not a gamified feature itself. It serves as the notification backbone and re-engagement trigger.

**Newsletter as gamification delivery mechanism:**
- **Weekly digest includes:** User's personal stats ("This week: 2 lessons completed, 30 XP earned, streak: 12 days"). Small section, bottom of email, personalized per user.
- **Milestone triggers in email:** "You're 1 lesson away from your certificate!" or "You just entered the Top 20 on the monthly leaderboard" — included in weekly digest, never as separate emails.
- **Badge unlock announcements:** When a user earns a badge, next newsletter includes a celebratory line ("You earned: Helpful 🏅 — 5 accepted answers!"). Subtle, not a dedicated badge email.

**Subscriber gamification (lightweight):**
- No XP for subscribing (subscribing is passive, not an achievement).
- Reading the newsletter does NOT count as an active day (cannot be tracked reliably + would inflate streaks meaninglessly).
- Newsletter referral tracking: "Share this issue with a colleague" link is tracked. If 3+ colleagues subscribe via a user's shares → triggers "Ambassador" badge.

**Anti-pattern:** Never gamify open rates or click rates visible to the user. That creates anxiety about email behavior. Gamification is about learning actions, not inbox actions.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.3.1 | Subscriber model | `NewsletterSubscriber(email, name, language, source_page, utm_*, confirmed_at, unsubscribed_at, created_at)`. Email unique + lowercased. | DONE |
| REQ-2.3.2 | Signup CTA component | Reusable footer/inline block: email input + button. Renders on every page. Submit via AJAX, shows inline success/error. | DONE |
| REQ-2.3.3 | Double opt-in | Submit → send confirmation email via Resend (Hebrew + English templates) → click link sets `confirmed_at`. Unconfirmed subs purged after 14 days. | DONE |
| REQ-2.3.4 | Unsubscribe flow | Every newsletter email includes one-click unsubscribe link with signed token. Sets `unsubscribed_at`. CAN-SPAM + GDPR compliant. | TODO |
| REQ-2.3.5 | Lead-magnet variant | Course-page CTA variant: "Get the free Copilot cheat-sheet" → signup → email with PDF link. Tracks `lead_magnet_id` on subscriber. | TODO |
| REQ-2.3.6 | Sending pipeline | Weekly digest sent via Resend in batches (≤ 100/batch, throttled). Send log: `NewsletterSend(subject, sent_at, recipient_count, open_count, click_count)`. Hard-cap recipients per env var for safety. | TODO |
| REQ-2.3.7 | Admin compose UI | Django admin (or simple staff page): subject, markdown body, preview, send-test-to-self, schedule-send. No external ESP UI required at this stage. | TODO |
| REQ-2.3.8 | Open/click tracking | Pixel + link-wrapping for opens/clicks. Stored on subscriber + send. Plausible event `newsletter_click` on landing. | TODO |
| REQ-2.3.9 | Auto-capture on course events | On enrollment + completion, prompt user to opt-in to newsletter (pre-checked checkbox, must be revocable). | TODO |
| REQ-2.3.10 | Subscriber dashboard | Admin sees: total confirmed, growth chart (weekly), last 10 unsubscribes, top source pages. | TODO |
| REQ-2.3.11 | Signup abuse protection | Newsletter signup rejects bot submissions with a CSS-hidden honeypot, rate-limits repeated submissions by IP, and handles duplicate emails idempotently without revealing subscriber state. | DONE |
| REQ-2.3.12 | Signup analytics | Successful newsletter signup fires a Plausible event `newsletter_signup` with non-PII props only (`source_page`, `language`). UTM/source page values are stored on the subscriber row. | DONE |

#### Legal & Privacy Direction

**This is the highest legal-risk feature.** Email marketing is heavily regulated in Israel and under GDPR. Non-compliance = fines + domain blacklisting + reputation damage.

**Israeli Spam Law (חוק התקשורת, 2008):**
- **Consent required BEFORE first commercial email.** The double opt-in flow (REQ-2.3.3) satisfies this. Never send to unconfirmed addresses.
- **Every email must contain:** (1) Sender identity ("אבי סלמון, babook.co.il"), (2) Physical or contact address, (3) Clear unsubscribe mechanism that works within 5 business days (ours is instant — good).
- **B2B exception:** Israeli law has a limited B2B exemption for existing business relationships. However, newsletter subscribers are NOT in a business relationship unless they also purchased something. Always require opt-in.

**GDPR (EU subscribers who land from Google/LinkedIn):**
- **Legal basis:** Consent (explicit opt-in via double opt-in). Consent must be: freely given, specific, informed, unambiguous.
- **Records of consent:** Store: timestamp of signup, IP address, source page, confirmation timestamp. This is the evidence if challenged.
- **Right to erasure:** Unsubscribe must completely remove the subscriber's email from sending lists. If they request full deletion (GDPR Article 17), remove all `NewsletterSubscriber` data (not just unsubscribed_at flag).
- **Data portability:** On request, export subscriber's data in machine-readable format (JSON). Edge case but legally required.

**Open/click tracking (REQ-2.3.8):**
- **Tracking pixels:** GDPR requires disclosure of tracking. Privacy policy must state: "We track email opens and link clicks to improve our newsletter." No consent checkbox needed (legitimate interest for analytics), but disclosure is mandatory.
- **Link wrapping:** Redirect links must not disguise the destination. The wrapped URL should clearly resolve to the expected page.

**Auto-capture on course events (REQ-2.3.9):**
- **Pre-checked checkbox is problematic under GDPR.** While Israeli law is less strict, best practice: checkbox should be UNCHECKED by default, with clear label: "שלחו לי גם את הניוזלטר השבועי." If you must pre-check (UX decision), document that this is a deliberate Israeli-law choice and add "[you can unsubscribe anytime]" next to it.
- **Recommendation:** Unchecked by default. It's better for trust and avoids GDPR disputes.

**Lead-magnet emails (REQ-2.3.5):**
- Downloading a lead magnet and providing an email constitutes consent to receive the specific promised asset. It does NOT constitute consent to receive ongoing newsletters. You must ask separately: "רוצה לקבל גם טיפים שבועיים?" (separate checkbox).

**Data retention:**
- Confirmed subscribers: retained until unsubscribe.
- Unsubscribed: anonymize after 30 days (keep aggregate count for metrics, delete email).
- Unconfirmed: purge after 14 days (already in REQ-2.3.3 — good).
- Bounce/invalid emails: remove from list within 24h of bounce notification.

**Resend (email provider) as processor:**
- Resend processes subscriber emails on our behalf. Their DPA must cover GDPR obligations. Document the processor relationship in privacy policy.
- Subscriber email addresses are transmitted to Resend for delivery. No other PII is shared.

---

### 2.4 Community Forums (P0)

A durable knowledge community (Q&A + discussions) where practitioners ask questions, share solutions, and build reputation. Provides daily engagement, SEO value (Google indexes threads), and positions Avi as the hub of Israel's AI practitioner community. Unlike chat (Discord/Slack), forum content is searchable, canonical, and accumulates value over time. Threads become marketing assets — a manager searching "AI agents Israel" lands on a babook thread, sees Avi answering, clicks Corporate page, books. Forums create NEW leads via Google; the newsletter captures known ones.

Decision pending (DEC-25, TODO): build native Django forum vs embed Discourse vs use `django-machina`. Default recommendation: `django-machina` for speed + native integration with our user model + RTL support.

#### UX Direction — Personas & Journeys

**Primary persona: Community Member (Contributor)**
- **Entry:** Completed a course, has questions or knowledge to share. Sees forum link in course completion email or navigation.
- **Mindset:** Wants to help others (reputation-building) and get help (stuck on implementation). Values fast answers and recognition.
- **Journey:** Browse categories → find relevant thread → reply with solution → get "accepted answer" → profile shows expertise count → feels valued → returns daily → becomes a regular.
- **UX principles:** (1) First post must be frictionless (no approval queue for verified users). (2) Recognition must be visible (accepted answer badge, post count). (3) Notifications must be timely but not overwhelming (daily digest option). (4) Mobile posting supported — engineers answer between meetings.
- **Success moment:** Their answer gets accepted and a peer thanks them publicly.

**Secondary persona: Casual Visitor (SEO entry)**
- **Entry:** Google search "how to use MCP with Copilot" → lands on a specific forum thread.
- **Mindset:** Looking for a quick answer. Does not know babook exists. Will leave in 30 seconds if no value.
- **Journey:** Reads thread → finds answer → notices quality of discussion → browses related threads → sees "Learn more in this course" link → clicks → enters Practitioner funnel.
- **UX principles:** (1) Thread pages must render full content without login (SEO-critical). (2) Related threads/courses shown in sidebar. (3) Newsletter CTA on every thread page. (4) No "register to see answers" dark pattern — kills SEO and trust.
- **Success moment:** Visitor bookmarks babook and returns organically within a week.

**Engineering Manager persona (passive discovery):**
- **Entry:** Googles a technical question, lands on a babook thread where Avi is answering with depth and authority.
- **Journey:** Reads Avi's answer → sees "Founder" badge → clicks profile → lands on /corporate/ → books.
- **UX principle:** Avi's posts must be visually distinct (badge, styling) and link to /corporate/. The forum is a trust-building machine for managers who "accidentally" discover it.

**Anti-persona: Spammer/Troll**
- Must be blocked without hurting legitimate new users. Rate limits + honeypot + email verification is the minimum viable moderation stack.

#### Design Direction

**Reference models:** Discourse (durable threaded knowledge, SEO-optimized thread pages, clean moderation UI) + Stack Overflow (accepted answer highlight, reputation badges) + Wix Engineering community (Israeli tech tone, Hebrew-first).

**Forum index (`/forum/`):**
- **Category sidebar (desktop) / top tabs (mobile):** Category pills with post-count badges. Active = filled, inactive = outlined. Categories: Copilot | Agents | MCP | Prompting | קריירה | מטא.
- **Thread list:** Each row: title (bold, 1.1rem), category badge (small colored pill), reply count, last activity ("לפני 3 שעות"), OP avatar (24px circle). Hover: subtle bg shift. Pinned threads: pin icon + "מוצמד" label, appear first.
- **Sort/Filter:** Latest (default), Most replies, Unanswered. Tabs, not dropdowns.

**Thread page (`/forum/<category>/<slug>/`):**
- **OP (original post):** Full-width, dark surface. Author block left (avatar 48px, name, "Founder" badge for Avi, post count). Content right (markdown rendered, code blocks with syntax highlighting + copy button).
- **Accepted answer:** Green left-border (4px), "✓ תשובה מקובלת" badge in header. Appears immediately after OP, regardless of chronological order.
- **Replies:** Stacked, alternating subtle background (surface/elevated). Timestamp + "Reply" button on each.
- **Reply composer:** Bottom of page, markdown editor with preview tab. "שלח" button. No WYSIWYG toolbar clutter — just markdown with common formatting hints.

**Avi's "Founder" badge:**
- Distinct styling for Avi's posts: subtle amber left-border, "מייסד babook" badge next to name. Links to /corporate/. This is not vanity — it's a trust signal for managers who stumble onto threads via Google.

**SEO requirements:**
- Thread pages render full content server-side (no JS-only rendering).
- Clean URL: `/forum/copilot/how-to-use-mcp-with-copilot/`
- `<title>`: thread title + " — babook forum"
- `<meta description>`: first 155 chars of OP.
- JSON-LD: `QAPage` schema for threads marked as Q&A.

**Critical design rules for forum:**
- No "register to read" gate. All content visible to anonymous users (critical for SEO).
- Post creation requires login (standard).
- Mobile: full-width threads, avatar sizes reduce to 32px, reply button becomes floating action button.
- Empty state (launch): 20 seed threads by Avi. Category pages with 0 threads show "Be the first to ask" prompt.
- Search: full-text search bar in forum header. Instant results on type (SQLite FTS5). Min 3 chars.

#### Gamification Direction

**Primary mechanics:** Reputation system, accepted-answer rewards, contribution badges, and level-gated privileges. The forum is the #1 gamification arena on the platform — community participation is harder to motivate than course consumption.

**XP from forum activity:**
- First forum post ever: 25 XP (one-time bonus to overcome initial posting anxiety).
- Answer accepted by OP: 50 XP. This is the highest-value repeatable XP action. Rewards quality over quantity.
- Thread created (not closed/deleted within 24h): 5 XP. Low to prevent spam.
- Reply posted (not self-reply): 3 XP. Capped at 10 replies/day for XP purposes.

**Reputation display in forum:**
- Next to every username: level badge (text: "מתחיל" / "לומד" / "מתרגל" / "מומחה" / "מוביל"). Color matches level tier.
- Accepted answer count shown on profile hover-card: "12 accepted answers".
- Avi gets permanent "Founder" badge regardless of level system (unique, non-earnable).

**Badge triggers from forum:**
- "First Voice": Publish first post.
- "Helpful": 5 accepted answers.
- "Mentor": 25 accepted answers.
- "Regular": Active in forum 30+ distinct days.

**Level-gated forum privileges:**
- Level 1 (Newcomer): Can post and reply. Limited to 5 new threads/day.
- Level 2 (Learner): Can edit own posts within 30 min (vs 15 min default).
- Level 3 (Practitioner): Can vote on answers (helpful/not helpful).
- Level 4 (Expert): Can suggest thread closure, flag duplicates.
- Level 5 (Leader): Can pin community threads (with Avi approval), moderate language.

**Accepted answer mechanics:**
- OP can mark ONE answer as accepted. Accepted answer gets: green border, "✓ תשובה מקובלת" badge, 50 XP to author.
- If OP doesn't accept within 7 days and thread has a reply with 3+ upvotes, system suggests: "This answer seems helpful — mark it as accepted?"

**Anti-gaming rules:**
- Self-accept (answering own question and accepting) awards 0 XP.
- Bulk posting (>10 posts in 1 hour) triggers rate limit AND disables XP for that session.
- Duplicate detection: if post content matches >80% of another recent post, XP withheld + warning.

**Community health signal:** Display on forum index: "X active contributors this week" (counts users with 2+ actions). Grows the "this community is alive" perception.

| REQ-ID | Title | Expectation (acceptance) | Status |
|---|---|---|---|
| REQ-2.4.1 | Forum engine choice | Pick + integrate forum library (default: `django-machina`). Mounted at `/forum/`. Uses our existing user/auth. Survives RTL Hebrew content. | TODO |
| REQ-2.4.2 | Category structure | Initial categories: Copilot, AI Agents, MCP, Prompting, Career & Hiring, Meta. Each category has Hebrew + English name, description, ordering. | TODO |
| REQ-2.4.3 | Thread + post UX | Logged-in users can: create thread, reply, edit own posts (15-min window), mark thread as Q&A, accept best answer. Markdown + code blocks + image upload to Bunny/static. | TODO |
| REQ-2.4.4 | SEO for threads | Every thread has clean URL `/forum/<category>/<slug>/`, unique `<title>`, `<meta description>` (first 160 chars of post), JSON-LD `QAPage` schema when marked Q&A. Included in `sitemap.xml`. Indexable by default. | TODO |
| REQ-2.4.5 | Moderation tools | Avi (staff role from REQ-1.2.8) can: pin/unpin, lock, move thread between categories, delete post, ban user. Audit-logged. | TODO |
| REQ-2.4.6 | Anti-spam | Per-user rate limit (≤ 5 new threads/day, ≤ 30 posts/day for new accounts). Honeypot + simple keyword filter. Email confirmation required before first post. | TODO |
| REQ-2.4.7 | Search | Full-text search across threads + posts. SQLite FTS5 sufficient at current scale; Postgres tsvector when DB migrates. Hebrew tokenization good-enough (substring fallback). | TODO |
| REQ-2.4.8 | Notifications | User gets email on: reply to own thread, mention `@username`, accepted answer. Per-user opt-out in profile. Daily digest option (not per-event). | TODO |
| REQ-2.4.9 | Reputation lite | Simple post count + accepted-answer count on user profile. Full badges/leaderboard deferred to §2.11 (P3). | TODO |
| REQ-2.4.10 | Corporate funnel hook | Sidebar block on every forum page: "מנהל צוות? ראה /corporate/". Avi's posts get a "Founder" badge linking to /corporate/. | TODO |
| REQ-2.4.11 | Seed content | At launch: 20 seed threads written by Avi (real Q&A from past consults), spread across categories. Avoids cold-start empty-forum problem. | TODO |

#### Legal & Privacy Direction

**User-generated content (UGC) liability:**
- Under Israeli law, the platform operator is not liable for UGC until notified (notice-and-takedown). However, proactive moderation (REQ-2.4.5) creates a duty of care. Document the moderation policy publicly.
- **Terms of Service must include:** (1) Users retain copyright on their posts but grant babook a perpetual, non-exclusive license to display, distribute, and index the content. (2) Users must not post infringing, defamatory, or illegal content. (3) babook reserves the right to remove content without notice.

**Forum content and SEO (public data):**
- All forum content is publicly visible (no login gate — critical for SEO). This means: usernames, post content, and timestamps are public. Users must be informed at registration that their forum activity is publicly indexed by search engines.
- **Privacy notice at signup:** "פוסטים בפורום גלויים לציבור ומאונדקסים על ידי מנועי חיפוש." Users should not post PII (phone numbers, addresses) in public threads.

**Right to be forgotten (forum posts):**
- If a user requests account deletion: delete their profile data, anonymize their posts (replace username with "משתמש שנמחק"). Do NOT delete the post content itself (it may be referenced by other users' replies). This balances deletion rights with community integrity.
- Alternative: offer "deactivate" (hide profile, anonymize display name) vs "full delete" (anonymize posts). Document both options in privacy policy.

**Seed content (REQ-2.4.11):**
- Seed threads are based on "real Q&A from past consults." Ensure ALL identifying information from the original consults is removed (company names, individual names, specific project details). Generic technical questions only. If any seed content could identify a past client, get written permission first.

**Moderation and banning:**
- Banning a user must: (1) prevent new posts, (2) NOT delete existing posts retroactively (unless content is illegal), (3) notify the user by email with reason. Israeli law does not require a hearing for private platform bans, but transparency reduces legal risk.
- Store moderation actions in an audit log (REQ-2.4.5 already requires this — good).

**Email notifications (REQ-2.4.8):**
- Forum notifications (reply to your thread, mention, accepted answer) are transactional/service emails. Legal basis: legitimate interest (user engaged in a conversation). However, must include per-user opt-out in profile.
- Daily digest option: this aggregates notifications, reducing email volume. Still requires opt-out capability.

**Image uploads in posts:**
- Users may upload images containing third-party content, faces, or copyrighted material. Terms of Service must state: users are responsible for having rights to upload content. babook will remove infringing content on notice.
- Consider EXIF stripping on uploaded images (removes GPS coordinates, camera model, etc.) to prevent unintentional PII leakage.

**Children's data:**
- Platform targets professionals (25-40 age range). No specific children's protections needed, but Terms should state: "platform is intended for users aged 18+."

---

### 2.5 Social Proof Engine (P1)

Automated collection and display of authority signals: total certificates issued, course completions counter, testimonial collection (post-course survey), company logos wall, and case studies. These signals appear on the homepage, the corporate page, and in email footers. Social proof is what turns "interesting platform" into "let's book this guy for our team."

#### UX Direction — Personas & Journeys

**Primary persona: Engineering Manager (Buyer)**
- **How social proof serves them:** Manager arrives on /corporate/ skeptical. Sees "127 certificates issued", "Trained teams at Wix, Monday, Check Point" (logos), and 3 real testimonials with names/titles. Skepticism dissolves. This is the difference between "who is this guy?" and "others like me already trust him."
- **UX principles:** (1) Numbers must be live and growing (not static text). (2) Logos must be real companies (even 3–5 is enough early on). (3) Testimonials must include name + title + company (anonymous testimonials are worthless). (4) Social proof blocks must appear above the fold on /corporate/ and on the homepage.
- **Journey impact:** Without social proof, manager exits after 10 seconds. With it, they scroll to CTA.

**Secondary persona: Practitioner (Post-completion)**
- **How they contribute:** After course completion, prompted with a one-question survey ("Would you recommend this course? + one-line quote"). Low friction = high response rate.
- **UX principle:** Testimonial collection should feel like celebration ("You did it! Quick question..."), not obligation. Offer to feature their name on the site (opt-in vanity).

**Content Owner (Avi):**
- Needs an admin view showing: which testimonials are approved/pending, which companies have given logo permission, running counter values. One-click approve/reject flow.

#### Design Direction

**Reference models:** Level Effect testimonial wall (photo + name + title + company + outcome badge) + DeepLearning.AI partner logo strip (horizontal, grayscale, subtle animation) + Frontend Masters "What they're saying" section (real quotes with social proof).

**Social proof components (reusable across pages):**
- **Counter bar:** Horizontal strip with 3-4 key numbers. Each: large number (2rem, bold, accent-warm amber animated count-up on first view) + label below (0.875rem, muted). Example: "127 תעודות הונפקו" | "12 חברות הודרכו" | "4.9 ⭐ דירוג ממוצע". Appears: /corporate/ hero area, home page, email footer.
- **Logo wall:** CSS grid, 4-6 columns. Grayscale SVGs, uniform 32px height. Hover: color version fades in (200ms). Label above: "הדריכו צוותים ב-". Graceful degradation: if <3 logos, hide entire component (don't show a sad-looking 1-logo wall).
- **Testimonial carousel/grid:** Card structure: circle photo (48px), name (bold), "Title @ Company" (muted), 2-3 sentence quote (italic), optional outcome badge ("סיים קורס Copilot", green). Desktop: 3 cards visible. Mobile: horizontal swipe carousel, 1 card visible + peek of next.

**Collection mechanism (design for the survey):**
- Triggered 24h after course completion via email. One-screen survey: "Would you recommend? (1-5 stars)" + "One sentence about your experience" (textarea) + "Can we show your name + company on babook?" (checkbox). Low friction = high response rate.
- Admin dashboard: table of pending testimonials. Preview card. Approve/Reject buttons. Approved ones go live immediately.

#### Gamification Direction

**Role:** Social proof is the public-facing output of the gamification system. The counters, logos, and testimonials displayed here are fueled by gamified actions happening elsewhere (course completions, certificate shares, forum contributions).

**Gamification-fed counters:**
- "X certificates issued" — incremented by course completion events (Epic 2.2 gamification).
- "X active learners" — count of users with activity in the last 30 days (streak system data).
- "X forum answers" — total accepted answers (forum gamification).
- These counters are the social proof ENGINE's fuel. They must update in real-time (or within 15 minutes via cached aggregation).

**Testimonial collection tied to achievements:**
- Testimonial survey triggered at TWO moments: (1) 24h after course completion, (2) immediately after earning the "Helpful" badge (5 accepted answers). Catch users at peak satisfaction.
- Users who provide a testimonial earn 10 XP ("Community Voice" micro-reward). Small incentive, not a bribe.

**Social proof as gamification feedback loop:**
- User completes course → certificate counter increments → counter visible on /corporate/ and home → new visitors see growing community → more signups → more completions → counter grows. The gamification system makes the social proof self-reinforcing.

**What NOT to show:** Never display raw XP totals or leaderboard rankings as social proof to external visitors. "127 certificates issued" is meaningful. "Total XP earned: 45,000" is meaningless to a manager.

#### Legal & Privacy Direction

**Testimonial consent (critical):**
- Every testimonial requires **explicit, documented consent** covering: (1) exact quote text displayed, (2) display of full name, (3) job title, (4) company name, (5) photo (if used). Consent must be freely given — never implied from course completion.
- **Consent mechanism:** Post-course survey includes explicit checkbox: "אני מאשר/ת ל-babook להציג את שמי, תפקידי וציטוט המלצה שלי באתר." Separate from the testimonial text itself.
- **Right to withdraw:** User can revoke testimonial consent at any time (email request or profile setting). Removal within 48 hours.
- **Admin must store:** consent timestamp, consent method (form/email), exact approved text. Never edit a testimonial without re-getting approval for the edited version.

**Company logos:**
- Displaying a company's logo implies a business relationship. Using a logo without permission could constitute trademark infringement or false endorsement.
- **Required:** Written permission from an authorized representative (email is sufficient) for each company logo displayed. Store evidence.
- **Safe alternative (pre-permission):** Use text-only mentions ("Trained teams at Wix, Monday.com") without logos until permission is secured. Text mentions of factual business relationships are generally protected as truthful commercial speech.

**Aggregated counters ("תעודות 127"):**
- Counters display aggregated, non-personal statistics. No privacy concern.
- **Accuracy requirement:** Numbers must reflect actual data (not inflated). Displaying materially false statistics in advertising context could violate Israeli Consumer Protection Law (חוק הגנת הצרכן). Automated counters from real database = always accurate.

**Star ratings:**
- If displaying average rating (e.g., "4.9 ⭐"), ensure minimum review count before showing (5+ reviews). Showing "5.0" from 1 review is misleading.

---

### 2.6 Certificates & LinkedIn Sharing (P1)

Branded certificates issued upon course completion, with one-click LinkedIn sharing. Every certificate shared on LinkedIn is free marketing to engineering managers in the sharer's network. Includes verification URL, QR code, and professional design. The certificate system turns every course completer into an organic marketing channel — each share says "I learned AI from Avi at babook." This is a direct funnel asset under the north-star metric.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Achiever)**
- **Entry:** Just completed final lesson. Sees "Congratulations!" screen with certificate preview.
- **Mindset:** Pride, accomplishment, desire to show off professionally. Willingness to share is highest in this 60-second window.
- **Journey:** Course complete → certificate auto-generated → preview shown with name + course title + date → "Share on LinkedIn" button (pre-filled post) → one click → certificate image + verification URL posted to LinkedIn feed → manager sees it in their feed.
- **UX principles:** (1) Share must be ONE click from the congratulations screen (no "go to profile, find certificate, copy link"). (2) Certificate must look premium (design quality = perceived course quality). (3) LinkedIn share must include the certificate image as a visual (not just a URL). (4) Verification URL (`/verify/<token>`) must work for anyone (no login required) — this is what the manager clicks.
- **Success moment:** Practitioner sees likes/comments on their LinkedIn post within hours.

**Secondary persona: Engineering Manager (Passive recipient)**
- **Entry:** Sees employee's LinkedIn post with babook certificate.
- **Journey:** Sees certificate in feed → clicks verification URL → lands on babook → sees "Train your whole team" CTA → visits /corporate/.
- **UX principle:** The verification page is a landing page in disguise: shows certificate validity + "Want this for your team?" CTA. This is a high-intent visitor — they already trust the platform because their employee completed it.

**Content Owner (Avi):**
- Needs: certificate template customization (logo, colors, layout), ability to revoke certificates, analytics on how many were shared and click-through from verification pages.

#### Design Direction

**Reference models:** Maven course completion certificates + LinkedIn "Add to profile" integration + Level Effect "Skill Sheet" (verifiable, professional, not gimmicky diploma clip-art).

**Certificate visual design:**
- **Format:** Landscape A4 (web-rendered HTML/CSS, exportable as PDF/PNG).
- **Style:** Dark background matching site palette. Minimal border (1px accent-primary). No ornate borders, no gold seals, no clip-art scrolls. This is for engineers — it should look like a GitHub achievement, not a kindergarten diploma.
- **Content:** babook logo (top-left), "Certificate of Completion" (top-center, inter/heebo bold), course name (large, 1.5rem), recipient name (larger, 2rem, accent-warm amber), completion date, Avi's signature (scanned), QR code linking to verification URL (bottom-right), unique certificate ID.
- **Branding:** Subtle babook.co.il URL at bottom. No visual noise.

**Completion flow UI:**
- Confetti animation (subtle, 2 seconds, particles in accent colors) on course completion screen. Then: certificate preview (scaled to fit viewport), below: "Share on LinkedIn" button (LinkedIn blue) + "Download PDF" button + "הוסף לפרופיל" link.
- LinkedIn share: pre-fills post text in Hebrew with course name + verification URL. Certificate image attached as preview (Open Graph image on verification page).

**Verification page (`/verify/<token>`):**
- Public, no login required. Shows: certificate (full render), recipient name, course name, completion date, "Valid ✓" green badge.
- Below certificate: "Want this for your team?" CTA → /corporate/. This page is a conversion opportunity disguised as a verification utility.
- Invalid/revoked tokens: "Certificate not found" with link to homepage. No error details.

**Critical design rule:** Certificate must look premium when screenshotted and posted on LinkedIn. Test: screenshot the rendered certificate, post it as a LinkedIn image — does it look professional and legible at LinkedIn's image crop?

#### Gamification Direction

**Primary mechanics:** Certificates are the most powerful gamification output — they are both an intrinsic reward (pride) and an extrinsic viral mechanism (LinkedIn sharing). The certificate IS the badge.

**XP and badge triggers:**
- Course completion (which generates the certificate) awards 100 XP.
- Sharing certificate on LinkedIn awards 20 XP + triggers "LinkedIn Sharer" badge progress (need 2 shares).
- Sharing is tracked via click on the "Share on LinkedIn" button (intent-based, not verification of actual LinkedIn post).

**Certificate as collectible:**
- Profile page: "My Certificates" section. Grid of earned certificates (miniature card view: course name + date + thumbnail). Clicking opens full certificate view.
- Certificate count visible on profile hover-card in forum ("3 courses completed").
- Users with 3+ certificates get "Polyglot" badge displayed prominently.

**Completion celebration (the peak moment):**
- This is the ONE place where brief animation is acceptable: 2-second confetti burst (accent-primary blue + accent-warm amber particles). Then static certificate + share buttons.
- Toast notification: "+ 100 XP — Course Graduate badge unlocked!" appears alongside the certificate. Clear, not cluttered.
- If this completion unlocks multiple badges (e.g., "Speed Runner" + "Course Graduate"), show them stacked in the toast, not as separate interruptions.

**Verification page gamification bridge:**
- When a manager clicks the verification URL from LinkedIn, they see the certificate AND a subtle line: "Join X engineers who completed this course." This is the social proof counter feeding from gamification data.

**Anti-pattern:** Never gate certificate generation behind additional gamification requirements. If user watched all lessons, they get the certificate. Period. No "earn 50 more XP" or "post in the forum first" requirements.

#### Legal & Privacy Direction

**Certificate as personal data:**
- Certificates contain: full name, course name, completion date, unique ID. This is personal data under GDPR/Israeli law.
- **User controls visibility:** Verification page (`/verify/<token>`) is accessible only to anyone who has the token (URL). The token is a long random string — effectively private unless the user shares it. The user decides whether to share the link.
- **No public certificate directory.** Never create a browsable list of all issued certificates. Each certificate is accessible only via its unique token URL.

**LinkedIn sharing (data transfer to third party):**
- When user clicks "Share on LinkedIn," they are redirected to LinkedIn's share dialog. babook sends to LinkedIn: (1) the verification page URL, (2) pre-filled post text. No additional personal data is transferred programmatically.
- The Open Graph meta tags on the verification page (which LinkedIn crawls) contain: course name, recipient first name (in og:description). User should be informed that sharing makes this information visible to their LinkedIn network.
- **Consent:** The act of clicking "Share on LinkedIn" constitutes informed consent to share the certificate publicly. No additional consent checkbox needed — the action is self-explanatory.

**Verification page (public):**
- Shows: name, course name, date, validity. This is intentionally public (that's the point of verification). The user opted into this by sharing the URL.
- **Invalid/revoked certificates:** Must NOT show the original holder's name. Just "Certificate not found." This prevents data leakage if a certificate is revoked.

**Certificate revocation:**
- Avi can revoke certificates (e.g., if fraud detected). Revocation must: (1) invalidate the verification URL immediately, (2) notify the user by email with reason, (3) NOT remove the certificate from the user's profile (they can still see it was revoked + reason). Transparency prevents disputes.

**PDF download:**
- Downloaded PDF contains the same data as the web certificate. Once downloaded, babook has no control over distribution. Privacy policy should note: "Downloaded certificates are under your control. We cannot revoke or modify downloaded copies."

**עוסק פטור considerations:**
- babook certificates are educational completion certificates, NOT professional licenses. They do not constitute a תעודה מקצועית under Israeli law. Clear disclaimer on certificate: "Certificate of completion. Not a professional accreditation."

---

### 2.7 AI Mentor Chat (P1)

An AI-powered mentor chatbot available on every course page and as a standalone tool. Reuses the proven AI Ascent interview/chat pattern (OpenAI service layer, already shipped in REQ-1.6.*). Serves two purposes: (1) helps learners get unstuck, boosting completion rates; (2) demonstrates technical depth — "even his bot is smart." The mentor chat is a credibility amplifier that few competitors offer.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Learner, stuck)**
- **Entry:** Watching a lesson, gets confused by a concept or can't get code to work. Sees chat icon in sidebar/corner.
- **Mindset:** Frustrated, wants a quick answer without leaving the lesson. Does not want to search forums or wait for a reply.
- **Journey:** Clicks chat bubble → chat opens in sidebar (lesson still visible) → types question in context ("What does this MCP config line mean?") → gets immediate, course-aware response → applies fix → continues lesson without losing momentum.
- **UX principles:** (1) Chat must be contextual (knows which lesson the user is on, references lesson content in answers). (2) Must not obscure the video player or lesson content — sidebar or slide-out, not modal. (3) Response time must be <3 seconds (streaming tokens visible immediately). (4) Code in responses must be copy-pasteable with one click. (5) Must gracefully handle rate limits with upsell, not dead-end error.
- **Key friction points to eliminate:** Having to re-explain context ("I'm on lesson 3 of the Copilot course..."). Chat losing history on page navigation. Robotic tone (should feel like asking a knowledgeable colleague).
- **Success moment:** User says "Oh, I get it now" and resumes the video within 30 seconds.

**Secondary persona: Casual Visitor (Tire-kicker)**
- **Entry:** Discovers standalone /chat/ page. Wants to test "how smart is this AI mentor?"
- **Journey:** Asks a practical AI question → gets a great answer → impressed → explores courses → enrolls.
- **UX principle:** Free tier (limited tokens) must be generous enough to demonstrate value (at least 3–5 meaningful exchanges before hitting a limit).

**Engineering Manager persona (indirect):**
- Never uses the chat directly. But when their employee says "I got unstuck using the AI mentor," it validates that babook is a complete learning solution worth paying for at team scale.

#### Design Direction

**Reference models:** ChatGPT sidebar UX (clean, minimal, streaming tokens) + Intercom (slide-out panel, does not block content) + GitHub Copilot Chat (code-aware context, inline code rendering).

**Chat widget (in-lesson):**
- **Trigger:** Floating icon button (bottom-right, 48px circle, accent-primary, chat-bubble icon). On course/lesson pages only.
- **Panel:** Slides out from right (desktop, 380px width) or slides up as bottom-sheet (mobile, 60% viewport height). Dark surface background. Does not obscure video player.
- **Header:** "AI Mentor" label, context badge ("Copilot Course — Lesson 3"), close (X) button, "New session" button (icon-only).
- **Messages area:** Chat bubbles. User = right-aligned, darker bg. AI = left-aligned, slightly lighter surface. Markdown rendered (bold, code inline, code blocks with syntax highlighting + copy button, lists). Streaming: tokens appear one-by-one with blinking cursor.
- **Input:** Single-line expanding textarea (grows to max 3 lines), send button (arrow icon). Placeholder: "שאל שאלה על השיעור..."
- **Rate limit reached:** Inline banner in chat: "הגעת למגבלה היומית. שדרג לתוכנית פרימיום" with CTA link. Not a modal, not a dead-end.

**Standalone chat page (`/chat/`):**
- Full-page layout. Left sidebar: session history list (title, date, first-line preview). Main area: active chat. Same message styling as widget but full-width (max 768px content).
- Empty state: "שאל שאלה על AI — אני כאן לעזור" + 3 suggested starter prompts (clickable chips).

**Critical design rules for chat:**
- First response token must appear within 2 seconds. Streaming is non-negotiable — users must see progress immediately.
- Code blocks must have: syntax highlighting (highlight.js, dark theme), copy button (top-right of block), language label.
- Chat panel must not reset or lose context when user navigates between lessons in the same course.
- Mobile bottom-sheet: drag handle at top, dismiss by dragging down. Does not interfere with video player controls.

#### Gamification Direction

**Role:** Chat is a supporting tool for learning, not a primary gamification surface. Gamification here is minimal and focused on driving course completion (the real goal), not chat usage for its own sake.

**Streak contribution:** A meaningful chat session (5+ messages exchanged) counts as an active day for streak purposes. This means: stuck on a problem → ask the mentor → streak maintained. The chat prevents streak-breaking frustration when a user can't watch a full lesson that day.

**XP:** No XP for chat messages. Using the chat is a tool, not an achievement. Awarding XP for questions would incentivize asking meaningless questions.

**Subtle nudge integration:**
- If a user asks the AI mentor about a topic covered in an uncompleted lesson, the mentor can respond with: "This is covered in Lesson 5 of your current course — want to jump there?" This bridges chat back to the lesson progression (where XP and badges await).
- If user completes a course but hasn't shared the certificate, mentor can mention: "Congrats on finishing! Share your certificate on LinkedIn? 📰"

**Rate limit messaging with gamification context:**
- When rate limit is hit, instead of just "upgrade," add: "You've asked 10 questions today — that's dedication! Upgrade to premium for unlimited AI mentoring."
- The message acknowledges effort (positive framing) rather than blocking access (negative framing).

**What NOT to gamify:** Number of chat sessions, length of conversations, number of code blocks copied. These are means, not ends. Never create a "Chatty" badge or "100 questions asked" achievement.

#### Legal & Privacy Direction

**OpenAI data processing (highest privacy sensitivity in the platform):**
- Every user message is sent to OpenAI's API for processing. OpenAI is a **data processor** (not controller) when using the API.
- **OpenAI's data use policy (API):** As of current terms, API data is NOT used to train models (opted out by default for API). Verify this remains the case. Document in privacy policy.
- **Data sent to OpenAI:** User's message text + system prompt (contains course/lesson metadata). User's name, email, and other PII are NOT sent in the API call. If the user types PII in their message (e.g., "My email is..."), that's user-initiated.

**Disclosure requirement (critical):**
- Users MUST be informed they are chatting with an AI, not a human. The chat interface clearly labels itself "AI Mentor" (already in Design Direction — good).
- **Privacy policy must state:** "Chat conversations are processed by OpenAI's API. Your messages are sent to OpenAI for generating responses. OpenAI does not use API data to train their models."
- **First-use disclosure:** On first chat session, show a one-time banner: "הצ'אט מופעל על ידי AI. השיחות שלך מעובדות על ידי OpenAI. אל תשתף מידע רגיש או סודי." Dismissible, shown once per user.

**Chat history storage:**
- `ChatMessage` records (REQ-1.6.3) stored in babook's database. Retention: active sessions retained indefinitely while account is active. User can delete individual sessions or all chat history from their profile.
- **Right to erasure:** On account deletion, all `ChatSession` and `ChatMessage` records must be permanently deleted (not just soft-deleted).

**Content safety and liability:**
- Content moderation (REQ-1.6.11) checks user input before processing. If the AI produces harmful/inaccurate advice (especially regarding code security), babook has limited liability — but include a disclaimer.
- **Disclaimer (footer of chat panel, small text):** "תשובות AI עלולות להכיל שגיאות. בדוק קוד לפני שימוש בפרודקשן."

**Rate limiting and paid tiers:**
- Rate limits by subscription tier (REQ-1.6.6) are a business decision, not a privacy issue. However, the token counter (`UsageLog`) stores per-user consumption data. This is functional data, legal basis: contract performance.

**Children/minors:**
- Chat is only available to logged-in users. Registration requires being 18+ (per Terms). No additional age-gating needed for chat.

---

### 2.8 Skill Marketplace (P2)

A creator-economy marketplace where community members publish and share mini-courses, templates, prompts, and tools. Positions Avi not just as a teacher but as a curator and platform owner. The marketplace generates content without Avi producing everything himself, builds community investment, and signals ecosystem maturity to corporate buyers evaluating the platform.

#### UX Direction — Personas & Journeys

**Primary persona: Content Creator**
- **Entry:** Active Community Member who has expertise and wants to monetize it. Sees "Become a creator" CTA in profile or forum.
- **Mindset:** Wants low-friction publishing (not a 6-month course production). Willing to share a template, prompt library, or 30-min mini-course.
- **Journey:** Applies to create → approved by Avi → uses simple creator dashboard to upload content (markdown + video + downloadable files) → sets price (free or paid) → published to marketplace → earns revenue share on sales → sees analytics (views, purchases, ratings).
- **UX principles:** (1) Publishing must be dramatically simpler than creating a full course (think "Gumroad for AI practitioners"). (2) Quality bar maintained via Avi's curation (approval before listing). (3) Revenue share must be transparent and instant (not "we'll pay you eventually"). (4) Creator profile page builds their personal brand within the babook ecosystem.
- **Success moment:** Creator earns first revenue from a $5 prompt template within a week of publishing.

**Secondary persona: Practitioner (Buyer/Browser)**
- **Entry:** Browsing marketplace for ready-made templates, prompts, or micro-learning after completing a main course.
- **Journey:** Browse by category/rating → preview description + sample → purchase (or access free) → download/use immediately.
- **UX principle:** Marketplace must not cannibalize Avi's main courses. Clear separation: Avi's courses = structured learning paths; marketplace = tools, templates, and supplementary content from the community.

**Engineering Manager persona (indirect):**
- Marketplace maturity signals "this is a real ecosystem, not a one-man show." When evaluating vendors, seeing a marketplace reinforces platform credibility.

#### Design Direction

**Reference models:** Gumroad (simple product cards with price + instant purchase) + Hugging Face Spaces (community-contributed artifacts, clean grid) + Skool classroom (creator content within community context).

**Marketplace page (`/marketplace/`):**
- **Filter/category bar:** Horizontal pills: All | Mini-courses | Templates | Prompts | Tools. Secondary sort: Popular / Newest / Price (low-high).
- **Product card:** Dark surface card, square thumbnail (1:1, 200px), below: title (bold), creator name + avatar (small), price badge (accent-warm for paid, "Free" green badge for free), star rating (if >5 ratings), download/enrollment count.
- **Product detail page:** Header: title + creator block (avatar, name, bio link). Body: description (markdown), preview/sample section, "Purchase" or "Get free" CTA button. Reviews section below.
- **Creator dashboard:** Simple table of published items + sales stats (views, purchases, revenue). Upload flow: title → description (markdown) → files → price → submit for review.

**Visual separation from Avi's courses:** Marketplace cards have a subtle "Community" badge. Avi's main courses live at /courses/ with a visually distinct, curated feel. Marketplace is clearly "community-contributed" with Avi's curation stamp ("Approved by Avi ✓").

#### Gamification Direction

**Primary mechanics:** Creator reputation system, buyer trust signals, and publishing milestones. The marketplace turns the gamification system into a two-sided incentive: creators earn status by publishing quality content, buyers discover quality via gamification-derived signals.

**Creator gamification:**
- Publishing a marketplace item (approved by Avi) = 100 XP. High XP because content creation is significantly harder than consumption.
- Creator profile shows: items published, total downloads/purchases, average rating, level badge. This becomes a mini-portfolio.
- Badge triggers: "First Publish" (first item approved), "Popular Creator" (any item reaches 50 purchases), "Top Rated" (average rating ≥ 4.5 with 10+ reviews).
- Level 3 (Practitioner) required to apply as a creator. This ensures creators have platform experience before publishing.

**Buyer-side gamification signals:**
- Product cards show creator's level badge (small, next to name). A Level 5 ("מוביל") creator signals trust.
- Products show: download count + average rating. These are gamification-adjacent trust signals.
- Purchasing a marketplace item does NOT award XP (buying is not an achievement).

**Quality control via gamification:**
- Low-rated items (<3 stars after 10 reviews) get flagged for Avi review. Possible delisting.
- Creators with 3+ published items and average ≥ 4.5 get "Verified Creator" status (amber badge on all their items). This is a quality moat.

**Anti-pattern:** Never gamify publishing volume ("Publish 10 items for a badge"). This incentivizes quantity over quality. Reward ratings and downloads instead.

#### Legal & Privacy Direction

**Intellectual property (creator content):**
- **Creator retains copyright** on all content they upload. babook receives a non-exclusive license to display, distribute, and promote the content on the platform. This must be explicit in creator Terms of Service / Creator Agreement.
- **Creator Agreement (required before first publish):** Covers: IP ownership (creator retains), license grant to babook, revenue share terms, content standards, takedown procedures, indemnification (creator warrants content is original / they have rights).
- **DMCA / Takedown:** If a third party claims infringement, babook must: (1) remove the content within 48h of valid notice, (2) notify the creator, (3) allow counter-notification. Follow US DMCA safe-harbor principles even though Israeli law doesn't require it (best practice for platforms hosting UGC).

**Revenue share and taxation:**
- Creators earning revenue through the marketplace are independent contractors, NOT employees. babook does not withhold taxes.
- **Israeli tax obligations:** If creator earns above the ניכוי מס threshold (currently ~₪5,500/year from a single source), babook must issue a טופס 856 (annual payment summary) and potentially withhold tax at source unless creator provides a פטור ניכוי מס certificate.
- **Creator onboarding must collect:** Full name, Israeli ID (ת.ז.) or business number (ח.פ.), bank details for payment, tax exemption certificate (if applicable). Store securely, access restricted to admin.

**Buyer rights:**
- Digital content purchases: Israeli Consumer Protection Law provides a 14-day cooling-off period for remote purchases, BUT digital content accessed/downloaded is typically exempt once consumption begins. Clearly state: "No refunds on accessed digital content" in purchase flow.
- If content is defective (e.g., corrupted file, misleading description): refund must be offered regardless of exemption.

**Content moderation:**
- Avi's curation (approval before listing) means babook actively reviews content. This increases duty of care — babook cannot claim ignorance of content quality/legality.
- Prohibited content: pirated material, content containing malware, content that violates third-party rights, content promoting illegal activities.

**Reviews/ratings:**
- Reviews are UGC. Same rules as forum posts: users responsible for content, babook removes on valid notice. Fake reviews (paid or self-generated) violate Israeli Consumer Protection Law.

---

### 2.9 Events & Meetups (P2)

Virtual and physical events system: weekly office hours, monthly meetups (Tel Aviv, Jerusalem), quarterly conferences. Events serve as direct lead-generation — attendees meet Avi in person, see expertise firsthand, and refer their managers. Physical presence in the Israeli tech ecosystem converts online authority into offline business relationships.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Attendee)**
- **Entry:** Sees event announcement in newsletter, forum banner, or LinkedIn post.
- **Mindset:** Curious about a topic, wants networking with Israeli AI peers, low commitment (free or cheap event).
- **Journey:** Sees event listing → reads agenda/speaker info → RSVPs (one click if logged in) → gets confirmation email + calendar invite → attends (virtual: Zoom link; physical: venue directions) → post-event: gets recording link + follow-up resources → prompted to enroll in related course.
- **UX principles:** (1) RSVP must be one-click (no separate Eventbrite/Meetup registration). (2) Event page must show who else is attending (social proof + networking motivation). (3) Reminder emails at 24h and 1h before. (4) Physical events show map + parking + public transport info. (5) Recording available within 48h for no-shows and as course-adjacent content.
- **Success moment:** Attendee meets Avi in person, shakes hands, feels personal connection that no online course can replicate.

**Secondary persona: Engineering Manager (Attendee or referrer)**
- **Entry:** Attends a free office-hours session to evaluate Avi's teaching style before committing to a paid corporate engagement.
- **Journey:** Attends → sees Avi's expertise live → impressed → books corporate training post-event.
- **UX principle:** Events are "free samples" of the corporate training product. Quality must match or exceed the paid experience.

**Content Owner (Avi):**
- Needs: event creation dashboard (title, date, type, capacity, virtual/physical, price), attendee list export, post-event email trigger, integration with Plausible for `event_rsvp` tracking.

#### Design Direction

**Reference models:** Luma (clean event pages with RSVP, attendee avatars, calendar integration) + Maven workshops (date + time + instructor + format in one glanceable card) + Meetup (community discovery, TLV tech meetups).

**Events listing (`/events/`):**
- **Upcoming events:** Vertical timeline or card list. Each event: date block (large day number + month, accent-primary), title (bold), time + timezone, format badge ("מקוון" blue / "פיזי — תל אביב" amber), attendee count ("32 נרשמו"), RSVP button.
- **Past events:** Grayed section below with "Recording available" badge linking to lesson/video.
- **Filters:** Upcoming / Past. Type: All | Office Hours | Meetup | Workshop.

**Event detail page:**
- **Hero:** Event title, date/time (large), format + location, Avi's instructor block, "הרשמה" CTA button (prominent, full-width on mobile).
- **Details section:** Markdown description, agenda/schedule, requirements.
- **Attendee section:** Avatar grid (showing first 12 attendees, "+20 more"), anonymous until RSVP'd.
- **Post-RSVP:** Button changes to "נרשמת ✓", calendar invite (.ics) download link appears, reminder preferences (email at 24h/1h).
- **Physical event specifics:** Google Maps embed, address in copyable text, parking info, public transport links.

**Critical design rule:** RSVP must be ONE click for logged-in users (no form, no second confirmation page). If not logged in, login + auto-RSVP on return.

#### Gamification Direction

**Primary mechanics:** Attendance tracking, networking badges, and event-as-streak-saver. Events are offline/live moments that bridge the digital gamification system into real-world interactions.

**XP from events:**
- RSVP + attend (confirmed by check-in or virtual presence) = 30 XP. RSVP alone without attendance = 0 XP (prevents gaming).
- Attendance verified by: (virtual) joining Zoom call for >50% of duration, (physical) manual check-in by Avi or QR code scan at venue.

**Badge triggers:**
- "Networker": Attend 3+ events (any type).
- "Regular Attendee": Attend 5 events in a single quarter.
- No badge for single event attendance (too easy, not meaningful).

**Streak contribution:** Attending an event counts as an active day. Users who can't watch a lesson that day but attend an office-hours session maintain their streak.

**Event-specific leaderboard (lightweight):**
- After each event: "Attendees from this event" section showing avatars + names of attendees who opted-in to public display. Not a ranking — just a participant wall.
- For recurring events (weekly office hours): "X total sessions attended" counter on user profile. Not public by default.

**Post-event gamification nudge:**
- 24h after event: email with "You earned 30 XP from yesterday's meetup. Continue your momentum — next lesson in your course awaits." Bridges live event energy back into platform engagement.

**Physical event exclusive:**
- Users who attend a physical event get a one-time "IRL" badge (only earnable at in-person events). This creates scarcity and incentivizes showing up in Tel Aviv. Not repeatable — once earned, permanent.

**Anti-pattern:** Never require event attendance for course completion or certificate generation. Events are optional enrichment, not gates.

#### Legal & Privacy Direction

**Event registration data:**
- RSVP collects: user_id + event_id + timestamp. Minimal data, no additional PII beyond existing account info. Legal basis: contract performance (user requests to attend).
- **Attendee list visibility:** The spec shows attendee avatars publicly on the event page. Users must opt-in to public attendee display (not default-on). Some attendees may not want their employer to know they attend external training events.
- **Recommendation:** Show attendee count ("32 registered") publicly. Show individual avatars/names only to other registered attendees (mutual visibility), or make it opt-in per user ("Show me as attending").

**Physical events:**
- **Photography/video consent:** If events are recorded (for later viewing per the spec), attendees must be informed BEFORE the event. Registration confirmation email must state: "האירוע יצולם. בהרשמה אתה מסכים להופיע בצילום." Users who object should have the option to attend without being on camera (practical for physical events: designated no-camera zone or camera angles that exclude certain seating).
- **Venue safety:** For physical events, babook (Avi) is the organizer. Standard duty of care applies (safe venue, emergency exits, accessibility). Not a platform issue per se, but document responsibility.

**Virtual events (Zoom/Meet):**
- Third-party tool (Zoom) processes attendee data (name, email, IP). Zoom's privacy policy applies. Disclose in privacy policy: "Virtual events use [Zoom]. Your participation is subject to their privacy policy."
- Recording notice: Zoom displays a recording indicator. Ensure the babook event description also states recording will occur.

**Calendar invites (.ics):**
- .ics files contain event details (title, date, location). No PII beyond what the user already provided. No privacy concern.

**Post-event emails:**
- Follow-up emails (recording link, related course) are transactional (related to user's RSVP action). Legal basis: legitimate interest. Include opt-out link.

**Capacity and waitlists:**
- If event has capacity limits, waitlist collects same data as RSVP. Waitlisted users' data retained until event passes, then purged (or offer to notify for next event — requires separate opt-in).

**Children at physical events:**
- Platform is 18+. Physical events follow the same policy. No minors unless explicitly stated (family-friendly event variant, unlikely for this audience).

---

### 2.10 Token & Copilot Bundling (P3)

Optional bundling of GitHub Copilot seats and OpenAI API credits for platform users. Serves as a user acquisition hook ("get Copilot cheaper through babook") rather than a primary revenue source. Leverages the already-shipped REQ-1.5.* Copilot provisioning code. Secondary revenue stream at scale, but only worth activating once the audience and authority are established. Not essential for the core business model.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Cost-sensitive)**
- **Entry:** Enrolled in a course, sees bundled pricing ("₪149/mo includes Copilot Business seat + all courses + AI mentor").
- **Mindset:** Already paying for Copilot individually ($19/mo). Attracted by bundled value.
- **Journey:** Sees pricing comparison → understands the bundle saves money vs. buying separately → subscribes → gets Copilot seat auto-provisioned (REQ-1.5.*) → uses Copilot at work → attributes value to babook subscription → retains longer.
- **UX principles:** (1) Value proposition must be crystal clear (side-by-side price comparison). (2) Copilot provisioning must be invisible (auto-invite, auto-seat-assign — no manual steps). (3) Status visible in profile ("Your Copilot seat: Active"). (4) Churn path must be graceful (14-day grace, clear communication).
- **Risk:** Users subscribe only for cheap Copilot, never engage with courses. Mitigation: require minimum platform activity or tie to course enrollment.

**Engineering Manager persona (indirect):**
- Team-level Copilot bundling ("subscribe 10 seats at a discount") could become an enterprise upsell path. Dashboard showing team Copilot usage + learning activity = compelling package for L&D budget justification.

#### Design Direction

**Reference models:** Level Effect pricing tiers (clear comparison cards) + GitHub Copilot account page (seat status, activity indicator) + Frontend Masters "Teams" page (group pricing with value prop).

**Pricing page integration:**
- Bundle tier card appears alongside individual plan. Side-by-side comparison table: "Without babook" (Copilot $19/mo + courses $X/mo = total) vs "With babook bundle" (one price, savings highlighted in accent-warm amber). Visual strikethrough on "old total."
- Copilot status in user profile: simple status line with icon — green circle "Active", yellow "Invite pending", gray "Not included." Link to VS Code setup guide next to status.

**Design rule:** Copilot provisioning must be invisible. No manual steps, no "click here to accept invite" screens within babook (the invite flow happens in GitHub's UI). User sees status update automatically.

#### Gamification Direction

**Role:** Gamification serves as a retention mechanism for bundle subscribers, preventing the "subscribe for Copilot, never use courses" anti-pattern.

**Activity requirements (soft-gate):**
- Bundle subscribers see a dashboard widget: "Your bundle includes: Copilot seat ✓ | All courses ✓ | AI Mentor ✓." Below: "This month: X lessons completed, Y XP earned." This is visibility, not enforcement.
- Optional (DEC pending): If a subscriber shows ZERO platform activity for 60 days (no lessons, no forum, no chat), send a friendly "You're paying for courses + Copilot but only using Copilot — here's what you're missing" email with personalized course recommendations. Never revoke access — this is nudging, not punishing.

**Team bundle gamification (enterprise upsell):**
- When a manager subscribes 5+ seats: team dashboard unlocks automatically with aggregated gamification data (team XP, collective courses completed, team streak average).
- "Team AI Score" — an aggregate metric combining: courses completed / total available × active members / total members × streak participation rate. Displayed as a single percentage with color coding (red <40%, yellow 40-70%, green >70%).

**XP:** No XP for subscribing or maintaining subscription. Paying money is not a gamifiable achievement.

**Anti-pattern:** Never tie Copilot access to gamification milestones ("earn 500 XP to unlock Copilot"). The bundle is a paid product, not a reward.

#### Legal & Privacy Direction

**GitHub data sharing (critical):**
- Copilot provisioning (REQ-1.5.*) requires sharing the user's **GitHub username** with GitHub's API (to invite to org and assign seat). This is a transfer of personal data to a third party (Microsoft/GitHub).
- **Explicit consent required:** At the point where user provides their GitHub username (profile or signup), display: "Your GitHub username will be shared with GitHub to provision your Copilot seat. GitHub's privacy policy applies to your Copilot usage."
- **Data minimization:** Only the GitHub username is shared. No other babook data (email, courses, progress) is sent to GitHub.

**Subscription and auto-renewal (Israeli Consumer Protection Law):**
- Auto-renewing subscriptions must: (1) clearly state renewal terms before purchase, (2) allow cancellation at any time with effect at end of billing period, (3) send reminder email 3-5 days before renewal.
- **14-day cooling-off period:** Israeli law grants 14 days to cancel remote transactions. For subscription services, this means: if user cancels within 14 days of first subscription, full refund (minus reasonable cancellation fee if Copilot seat was provisioned). After 14 days: cancellation takes effect at period end, no refund for current period.

**Copilot usage monitoring:**
- REQ-1.5.7 (inactivity reclamation) monitors `last_activity_at` per Copilot seat. This data comes from GitHub's API, not from monitoring the user's coding activity directly.
- **Disclosure:** Privacy policy must state: "We check your Copilot seat activity status via GitHub's API to manage seat allocation. We do not monitor your coding activity or access your code."

**Seat revocation:**
- Revoking a Copilot seat (on churn or inactivity) affects the user's development tools. Provide adequate notice: 14-day grace period on churn (already in REQ-1.5.6), 30-day warning on inactivity (REQ-1.5.7). Never revoke without warning.

**Team/enterprise bundles:**
- If a manager subscribes seats for team members: the manager provides team members' GitHub usernames. Ensure the manager has authority to do so (their employment relationship typically provides this, but babook should state in Terms: "By providing team member details, you confirm you have authorization to enroll them.").

---

### 2.11 Gamification & Engagement (P3)

Badges, leaderboards, streaks, and achievement system to drive course completion and community participation. Ported from proven AI Ascent patterns (9 badge types, tier system, opt-in leaderboard). Improves engagement metrics which feed social proof ("2,000 engineers certified"). Only matters once there's an active user base to gamify.

#### UX Direction — Personas & Journeys

**Primary persona: Community Member (Engaged regular)**
- **Entry:** Active user who has completed courses and participates in forums. Sees badge unlock notification.
- **Mindset:** Motivated by recognition, status, and visible progress. Competitive in a healthy way.
- **Journey:** Completes action (course, forum answer, streak) → badge unlocks with celebration animation → badge appears on profile → leaderboard position updates → shares achievement → motivated to continue.
- **UX principles:** (1) Badges must feel earned, not given away (scarcity = value). (2) Leaderboard must be opt-in (not everyone wants public ranking). (3) Streaks must be forgiving (1-day grace period prevents frustration). (4) Gamification must not feel childish — this audience is professional engineers. Use understated design (think GitHub contribution graph, not mobile game).
- **Anti-pattern:** Gamification that rewards quantity over quality (spamming forum posts for points). Tie rewards to outcomes (accepted answers, course completions) not volume.

**Secondary persona: Practitioner (Lurker, needs nudge)**
- **Entry:** Enrolled but stalled at lesson 3. Receives "You're 60% done — 2 more lessons for your certificate!" nudge.
- **Journey:** Streak reminder + progress bar + proximity to badge → returns → completes course.
- **UX principle:** Gamification is a retention tool for users who already started but dropped off. It does not acquire new users.

#### Design Direction

**Reference models:** GitHub contribution graph (understated, professional, data-driven) + Duolingo streaks (effective but adapt for adult professionals — less playful) + Kaggle notebooks/rankings (subtle tier indicators).

**Badge system visual:**
- Badge icons: simple geometric SVGs (not emoji, not cartoon). Monochrome (muted gray) when locked, accent-warm amber when earned. Small (32px) in profile grid, 24px inline next to name in forum.
- Badge names: professional, not playful. "First Course", "5 Answers Accepted", "7-Day Streak", "Community Helper". Not "Code Warrior" or "AI Ninja."
- Profile badge grid: max 2 rows (8-10 visible), "+ X more" expandable.

**Streak indicator:**
- Small flame/calendar icon in nav header (next to user avatar) showing current streak count. Color: muted gray if 0, amber if active. Clicking opens mini-panel showing streak calendar (like GitHub's contribution heatmap but simplified — just green squares for active days).

**Leaderboard (`/leaderboard/`, opt-in only):**
- Simple table: rank, avatar, name, score, top badge. Top 50 shown. User's own rank highlighted regardless of position. Monthly reset option.
- Opt-in toggle in profile settings. Users who opt out don't appear and don't see leaderboard link.

**Design rule:** Gamification elements must never feel childish or condescending. This audience writes code for a living. Think GitHub's subtle "Arctic Code Vault Contributor" badge — small, meaningful, earned.

#### Gamification Direction

**This IS the gamification epic.** Epic 2.11 is the implementation home for the platform-wide gamification strategy defined in the "Gamification Strategy" section above. All other epics reference gamification mechanics; this epic builds the infrastructure.

**Implementation scope for this epic:**
1. **XP ledger system** — append-only event table, daily aggregation, level calculation.
2. **Badge engine** — trigger-based evaluation, badge definitions table, unlock events.
3. **Streak tracker** — daily cron job, grace period logic, streak-at-risk notifications.
4. **Leaderboard** — materialized view, monthly reset, opt-in toggle, category tabs.
5. **Profile gamification section** — badge grid, streak calendar, level indicator, XP total.
6. **Notification system** — in-app toasts, email digest integration, opt-out granularity.
7. **Admin gamification dashboard** — total badges issued, active streaks, leaderboard health, suspicious activity flags.

**Rollout strategy (progressive enablement):**
- **Phase 1:** XP + levels + profile display only. Users see their progress but no social features.
- **Phase 2:** Badges + unlock notifications. Visual rewards for milestones.
- **Phase 3:** Streaks + streak notifications. Retention mechanics.
- **Phase 4:** Leaderboard (opt-in). Social competition.

Each phase has an independent feature flag. Phases can be separated by 2-4 weeks to measure impact and iterate.

**Dependency map:**
- Requires: Course completion events (Epic 2.2), forum post events (Epic 2.4), event attendance (Epic 2.9).
- Feeds into: Social proof counters (Epic 2.5), certificate generation trigger (Epic 2.6), newsletter personalization (Epic 2.3).
- Optional integration: Referral milestones (Epic 2.12), team scores (Epic 2.13).

**Success criteria for this epic:**
- Course completion rate increases 20% within 8 weeks of Phase 1 launch.
- Forum participation (posts/week) increases 30% within 4 weeks of Phase 2.
- Weekly active user retention improves 15% within 6 weeks of Phase 3.
- If any metric DECREASES, that phase's feature flag gets turned off and the mechanic is re-evaluated.

#### Legal & Privacy Direction

**Profiling under GDPR:**
- The gamification system creates user profiles (XP history, badge collection, streak data, level). Under GDPR Article 22, automated profiling that produces legal or significant effects requires explicit consent or contractual necessity.
- **Assessment:** Gamification on babook does NOT produce legal effects (no credit scoring, no employment decisions). It produces engagement features. Legal basis: legitimate interest (improving service engagement). No explicit consent needed for the profiling itself.
- **However:** If gamification data is ever used for differential pricing (higher level = different price) or access gating (level required to access content), that crosses into "significant effects" territory. Current design avoids this.

**Leaderboard and public display:**
- Leaderboard displays: username, avatar, XP score, badges. This is personal data displayed publicly.
- **Opt-in requirement (already in spec — good):** Users must explicitly enable leaderboard visibility. Default: off. Toggle in settings.
- **Anonymous option:** Users who opt-in can choose "Anonymous Engineer" display. This satisfies users who want to compete but not be identified.
- **Right to removal:** User can opt-out at any time. Removal from leaderboard must be immediate (not "next month").

**Streak notifications (email):**
- "Your streak is at risk" emails are service communications tied to user's active engagement. Legal basis: legitimate interest.
- **Must include opt-out.** User should be able to disable streak notifications without disabling the streak feature itself.

**XP data retention:**
- XP events are append-only (per technical spec). On account deletion, all XP events for that user must be permanently deleted. The append-only design must not prevent GDPR erasure.
- **Implementation note:** Soft-delete the user first (anonymize), then batch-delete XP events in background. Never retain XP events for deleted users "for analytics."

**Badge display on forum (public):**
- Forum posts show the user's level badge next to their name. This is public data. Since the user actively posted in a public forum, displaying their earned level badge alongside their post is consistent with the forum's public nature. No additional consent needed.

**Behavioral nudging ethics:**
- Gamification is designed to influence behavior (increase completion, participation). This is ethically acceptable for educational content aimed at professionals making informed choices.
- **Red line:** Never use gamification to pressure purchases (e.g., "earn XP to unlock discount" with a countdown timer). Current design avoids this.

---

### 2.12 Referral Engine (P3)

Peer-to-peer referral system with tracking links, enrollment attribution, and rewards. Every course completer becomes a potential referrer. Proven in AI Ascent (Sprint 27-28) to drive organic growth. Reduces customer acquisition cost and builds network effects. Relevant only after the platform has enough value to be worth sharing.

#### UX Direction — Personas & Journeys

**Primary persona: Practitioner (Referrer)**
- **Entry:** Just completed a course or earned a certificate. Sees "Share with a colleague — you both get [reward]" prompt.
- **Mindset:** Genuinely wants to help a peer learn what they learned. Reward is a bonus, not the primary motivation.
- **Journey:** Copies personal referral link → shares on Slack/WhatsApp with a colleague → colleague signs up via link → both get reward (free month, bonus content, badge) → referrer sees attribution in profile ("You brought 3 people to babook").
- **UX principles:** (1) Referral link must be easy to copy and share (one button). (2) Reward must be immediate and visible for both parties. (3) Must not feel like MLM/spam — the framing is "recommend to a colleague" not "recruit people for points." (4) Attribution must be reliable (cookie + URL param, 30-day window).
- **Success moment:** Referrer sees "Your colleague just completed the same course you recommended" notification.

**Engineering Manager persona (team referral):**
- **Variant journey:** Manager refers their whole team. Referral link becomes a team onboarding URL. When 5+ people from same company sign up via one link, trigger "Enterprise interest" flag → Avi gets notified → potential corporate deal.
- **UX principle:** Volume referral from one source is a buying signal. System should detect and surface this automatically.

#### Design Direction

**Reference models:** Dropbox referral program (simple share link + progress toward reward) + Morning Brew referral dashboard (milestone rewards, share count visible).

**Referral panel (in user profile/settings):**
- Section titled "הזמן עמיתים". Personal referral link (copy button, one click). Share buttons: WhatsApp (pre-filled Hebrew message), LinkedIn, copy-raw-link.
- Progress indicator: "הזמנת X אנשים" with milestone markers (e.g., at 3: free month, at 5: exclusive content). Simple horizontal progress bar with milestone dots.
- Referral history: simple table — name (or "Pending"), signup date, status (signed up / enrolled / completed course).

**Design rule:** Referral flow must be shareable via WhatsApp in one tap. The pre-filled message should be casual and authentic ("היי, קורס ה-Copilot הזה עזר לי — שווה לך לבדוק"), not marketing copy.

#### Gamification Direction

**Primary mechanics:** Referral milestones, ambassador progression, and XP for successful referrals. The referral engine is where gamification directly drives business growth.

**XP from referrals:**
- Referred user signs up: 0 XP (signup alone is too easy to game).
- Referred user completes first lesson: 75 XP to referrer. This ensures the referral was genuine (someone who actually engages).
- Referred user completes a course: 25 XP bonus to referrer (deferred reward, reinforces long-term quality referrals).

**Badge progression (Ambassador track):**
- "First Referral": 1 successful referral (completed first lesson). Icon: single person with plus.
- "Ambassador": 3 successful referrals. Icon: megaphone.
- "Team Builder": 5+ referrals from same company domain. Icon: building. Triggers enterprise interest flag.
- "Community Catalyst": 10 successful referrals (lifetime). Icon: network graph. Unlocks: featured profile, exclusive content access.

**Milestone rewards (beyond XP):**
| Milestone | Reward |
|-----------|--------|
| 1 referral | 75 XP + "First Referral" badge |
| 3 referrals | "Ambassador" badge + 1 free month of premium |
| 5 referrals (same company) | "Team Builder" badge + enterprise flag + Avi personally reaches out |
| 10 referrals | "Community Catalyst" badge + permanent featured profile |

**Referral dashboard gamification:**
- Progress bar toward next milestone ("2/3 referrals until Ambassador badge").
- Visual celebration when milestone is hit (subtle toast, badge unlock animation).
- Referred users' progress visible: "Yossi completed Copilot Course — you earned 25 bonus XP!"

**Anti-gaming rules:**
- Referred user must: (a) use a different email domain than referrer (prevents self-referral), (b) complete at least one lesson within 30 days.
- Same IP address registrations via referral link flagged and XP withheld pending review.
- Max 5 referral XP events per day (prevents mass-spam campaigns).

**Enterprise signal integration:** When system detects 5+ signups from same email domain via one referral link, it automatically: (1) awards "Team Builder" badge, (2) creates a `CorporateLead` entry with source="referral_cluster", (3) notifies Avi. This turns the gamification system into a lead-gen sensor.

#### Legal & Privacy Direction

**Referral tracking (cookies and attribution):**
- Referral attribution uses: URL parameter (`?ref=<code>`) + cookie (30-day attribution window). The cookie is a **functional/analytics cookie** used to track the referral source.
- **Cookie consent:** This referral cookie goes beyond "strictly necessary" (the site works without it). Under GDPR: requires consent via cookie banner. Under Israeli law: less strict, but disclosure required.
- **Recommendation:** Include in the existing cookie consent banner (REQ-1.2.12): "We use cookies to track referral links." Allow users to reject referral tracking cookies (attribution simply won't work for those users — acceptable tradeoff).

**Referred user's privacy:**
- When a referral is successful, the referrer sees: referred person's name (or "Pending"), signup date, enrollment status. This displays one user's activity to another user.
- **Consent from referred user:** At signup via referral link, display notice: "הגעת דרך הזמנה של [referrer name]. פרטי ההתקדמות שלך ישותפו עם המזמין." The referred user must be informed.
- **Data minimization:** Referrer sees ONLY: name + signup date + completion status (binary: enrolled/completed). Never: specific courses, time spent, forum activity, or any other behavioral data.
- **Opt-out:** Referred user can break the referral link (hide from referrer's dashboard) via profile settings. Referrer still keeps earned XP/rewards.

**Enterprise signal detection (email domain analysis):**
- The system analyzes email domains to detect corporate clusters (5+ signups from same domain). This constitutes automated analysis of personal data.
- **Legal basis:** Legitimate interest (business development). Email domain is not highly sensitive data.
- **Disclosure:** Privacy policy: "We may analyze signup patterns to identify potential corporate training opportunities."
- **Never share the individual names** of clustered signups with Avi's notification. Only: "5+ signups detected from [domain].co.il." Avi should not see individual users' identities from this automated signal — only the pattern.

**Referral rewards:**
- If rewards have monetary value (free month = ~₪149), this may have tax implications for the referrer. Below Israeli reporting thresholds for casual benefits, but document that rewards are "platform credits, not cash" to avoid tax complications.
- Rewards must be clearly described before the user participates. No bait-and-switch (changing reward tiers retroactively). Grandfather existing referrers under the terms they signed up for.

**Anti-spam:**
- Referral system must NOT allow mass-emailing via babook infrastructure. The share mechanism is: copy link + paste in WhatsApp/LinkedIn yourself. babook never sends referral emails on behalf of users (avoids spam liability).

---

### 2.13 Enterprise Dashboard (P3)

A team-level AI readiness view for engineering managers: who completed what, skill gaps, time invested, team score. This feature sells the corporate training — a manager sees the dashboard, identifies gaps, and books Avi to close them. Only relevant when babook has enough enterprise users to justify the investment. Long-term, this becomes the upsell trigger.

#### UX Direction — Personas & Journeys

**Primary persona: Engineering Manager (Active customer)**
- **Entry:** Post-corporate-training. Avi sets up a team dashboard showing which team members completed follow-up self-paced courses.
- **Mindset:** Wants to measure ROI of training investment. Needs data to justify next budget cycle.
- **Journey:** Logs in → sees team overview (members, courses completed, hours invested, skill coverage heatmap) → identifies gaps ("3 engineers haven't started the MCP course") → sends nudge or books follow-up session with Avi.
- **UX principles:** (1) Dashboard must be visual and skimmable (heatmap, progress bars, not spreadsheets). (2) Must answer "Was my investment worth it?" in 10 seconds (top-line metrics: X hours learned, Y certifications earned). (3) Export to PDF for management reporting. (4) Compare team to anonymous benchmark ("Your team is in the top 20% for AI readiness").
- **Success moment:** Manager shows dashboard to their VP, who approves next quarter's training budget.

**Secondary persona: Practitioner (Team member)**
- **Entry:** Sees their name on team leaderboard. Knows their manager can see their progress.
- **Journey:** Social accountability drives completion. Sees "Your team average is 80% — you're at 40%" → motivated to catch up.
- **UX principle:** Individual view shows personal progress + gentle team context. Never shame publicly, but provide healthy competition.

**Upsell trigger design:**
- When team dashboard shows gaps (e.g., "0/8 team members completed Advanced Agents course"), system suggests: "Close this gap — book a team workshop with Avi." Direct pipeline from dashboard metric to corporate booking.

#### Design Direction

**Reference models:** GitHub organization insights (clean data viz, team activity graphs) + Frontend Masters "Teams" dashboard (usage stats per member) + Pluralsight Skills (skill assessment heatmaps for teams).

**Team dashboard layout:**
- **Top-line metrics (hero row):** 4 metric cards in a row: "Total hours learned" (number + delta vs last month), "Courses completed" (number), "Active this week" (X/Y members), "Team AI readiness score" (percentage, circular progress ring).
- **Member table:** Name, avatar, courses completed (count), last active (relative time), current course (progress bar), status badge (active/stalled/not started). Sortable by any column. "Nudge" action button per row (sends a friendly "Your team is waiting" email).
- **Skill heatmap:** Grid: rows = team members, columns = skill areas (Copilot, Agents, MCP, Prompting). Cell color: empty (gray), started (light accent), completed (accent-primary). Visual gap identification at a glance.
- **Export:** "Download PDF report" button generates a branded one-page summary for management presentations.
- **Upsell block (bottom):** If gaps detected: "3 team members haven't started the MCP course. Book a team workshop →" with WhatsApp CTA.

**Critical design rules:**
- Dashboard data must load fast (<1 second). Pre-aggregate metrics, don't calculate on the fly.
- Individual member view shows only personal progress + team average (anonymized peers). No public shaming.
- Manager sees full team view. Members see only their own progress + anonymous team context.
- PDF export must look presentable for a VP/CFO audience (company logo, date, clear metrics, no developer jargon).

#### Gamification Direction

**Role:** The enterprise dashboard surfaces gamification data at the team level. It translates individual XP, badges, and streaks into management-friendly metrics that justify training ROI.

**Team-level gamification metrics:**
- **Team AI Readiness Score:** Aggregate of: (courses completed / total available) × 0.4 + (active streaks / team size) × 0.3 + (forum contributions / team size) × 0.3. Displayed as a single percentage with trend arrow (up/down vs last month).
- **Team XP (this month):** Sum of all member XP this month. Shown as a number + bar chart (last 6 months). Managers don't need to understand XP mechanics — they see "team activity is growing."
- **Badges earned (team total):** Count of badges earned this quarter across team. Feeds the narrative: "Your team earned 23 certifications this quarter."

**Skill heatmap powered by gamification:**
- Each cell in the skills heatmap is derived from course completion events (gamification triggers). "Completed" = course completion badge earned. "In Progress" = >0% but <100%. "Not started" = no enrollment.
- Color coding: gray (not started), light accent (enrolled/in-progress), accent-primary (completed). This is the same badge logic, just surfaced as a grid.

**Manager-specific gamification (gentle):**
- Managers do NOT earn XP or badges for dashboard viewing. That would be absurd.
- However: "Send nudge" button next to stalled team members triggers a friendly email ("Your team is making progress — join them!"). The nudge references the member's proximity to their next badge: "You're 1 lesson from your Course Graduate badge."

**Team competition (opt-in, enterprise only):**
- If an enterprise client has multiple teams (e.g., Backend team, Frontend team, DevOps team), enable inter-team leaderboard: teams ranked by AI Readiness Score. Opt-in per team, visible only within the organization.
- This creates healthy inter-team competition that drives completion without individual shaming.

**Benchmark comparison:**
- "Your team is in the top 20% of all babook teams for course completion." Anonymized benchmark against other enterprise teams on the platform. Requires 10+ teams to be statistically meaningful — until then, don't show.

**Anti-pattern:** Never expose individual team member XP or leaderboard rank to the manager. The manager sees: courses completed (yes/no), active (yes/no), badge count. Not: "Yossi has 450 XP and Dan has 1200 XP." That creates workplace tension.

#### Legal & Privacy Direction

**Employee monitoring (highest legal sensitivity in the platform):**
- The enterprise dashboard shows a manager their team members' learning activity. This is **employee monitoring** — a heavily regulated area under Israeli labor law and GDPR.
- **Israeli Privacy Protection Law (workplace):** Employers may monitor work-related activity with proper notice. However, babook is NOT the employer — it's a third-party platform providing data to the employer. Different legal standing.

**Consent architecture (critical):**
- **Option A (recommended): Team members opt-in to team visibility.** When a manager creates a team dashboard and adds member emails, each member receives an invitation: "Your manager [name] wants to see your learning progress on babook. Accept / Decline." Only opted-in members appear on the dashboard.
- **Option B: Employment relationship justification.** Manager asserts authority to view team progress as part of work duties. Legally defensible under Israeli employment law IF the training was employer-directed. Document in Terms: "By enrolling team members, the subscribing organization confirms it has informed employees that their progress will be visible to their manager."
- **Recommendation:** Option A for self-service signups. Option B for corporate contracts (where Avi's B2B agreement with the company covers employee notification).

**Data visible to managers:**
- Strictly limit to: courses completed (count + names), active/inactive status, hours invested (aggregate), skill coverage. NEVER: chat transcripts, forum posts, specific lesson timestamps (e.g., "watched at 2am"), failed quiz answers, or detailed behavioral patterns.
- **Principle:** Manager sees OUTCOMES (what was achieved), not BEHAVIOR (how/when it was achieved). Watching a lesson at midnight is not the manager's business.

**Data retention for enterprise dashboards:**
- If an employee leaves the team or company: their data must be removable from the team dashboard within 30 days of request.
- If the enterprise subscription ends: team dashboard data archived (not displayed) for 12 months, then deleted. Manager loses access immediately on subscription end.

**PDF export (sensitive):**
- PDF reports contain: team member names + completion data. This is a document that will be shared internally (to VPs, CFOs).
- **Watermark:** Each PDF should contain a subtle watermark: "Confidential — [company name] — Generated [date]." Discourages unauthorized distribution.
- **No individual PII beyond name + completion.** Never include email addresses, login times, or behavioral details in the PDF.

**Cross-team benchmarking:**
- "Your team is in the top 20%" compares against OTHER companies' teams. This uses aggregated, anonymized data. No privacy concern IF: (1) minimum cohort size enforced (10+ teams), (2) no individual company identifiable from the benchmark, (3) only percentile ranking shown (not absolute numbers from other teams).

**GDPR Data Protection Impact Assessment (DPIA):**
- Employee monitoring at scale (enterprise dashboard) likely triggers DPIA requirement under GDPR Article 35. If EU-based companies use this feature, conduct a DPIA before launch. For Israeli-only customers: not legally required but recommended as best practice.

**Terms of Service for enterprise tier:**
- Separate Enterprise Terms (not the individual Terms of Service) covering: data processor role (babook processes employee data on behalf of the employer-controller), DPA, sub-processors list, security measures, breach notification procedures (72h), data location (Render US servers — document for clients with data residency concerns).

---

### 2.14 Priority Summary

| Priority | Sections | Stage | Timeline | Goal |
|----------|----------|-------|----------|------|
| **P0a** | 2.1 lean cut + 2.3 capture | **TRACKED** | Weeks 1–4 | Immediate conversion loop: corporate page + WhatsApp/form + newsletter capture |
| **P0b** | 2.2 first flagship course | SPECCED | Weeks 5–8 | One excellent proof asset that feeds the funnel |
| **P0c** | 2.4 forum after seed content | SPECCED | Weeks 9–14 | SEO/community layer only after page + capture + content exist |
| **P1** | 2.5, 2.6, 2.7 | DEFINITION | Weeks 15–22 | Authority depth + viral marketing flywheel |
| **P2** | 2.8, 2.9 | DEFINITION | Weeks 23–32 | Growth: network effects + organic marketing |
| **P3** | 2.10, 2.11, 2.12, 2.13 | DEFINITION | Weeks 33+ | Scale: only after phone is already ringing |

Sequencing is intentionally narrow: **ship `/corporate/` and newsletter capture first**, publish **one excellent flagship course** next, then launch forum only when there is seed content and enough traffic to avoid a cold empty community. Admin CMS, social-proof automation, detailed analytics, marketplace, token resale, and enterprise dashboards remain behind the "does this make Avi's phone ring sooner?" gate.

### 2.15 Decisions (Chapter 2)

| ID | Topic | Choice | Rationale |
|---|---|---|---|
| DEC-19 | Business model | Platform = free marketing engine; revenue = corporate training gigs | Research Phase 3 conclusion |
| DEC-19a | Pivot from token-resale thesis | Copilot/Stripe code (REQ-1.5.*, REQ-1.4.*) is **parked, not deleted**. Research recommended token-resale as primary revenue, but single-operator reality (no sales team, no partner negotiation bandwidth) makes authority-marketing the faster path. Token code revives in §2.10 if audience justifies it. | Research Phase 3 overrides Research Phase 1 recommendation |
| DEC-20 | Geography | Israel-first, Hebrew-first | Corporate training is local, face-to-face, Hebrew-speaking |
| DEC-21 | Content strategy | Free, short, practical, opinionated courses | Authority positioning, not course sales |
| DEC-22 | Revenue target | 20 gigs/year × ₪25K avg = ₪500K Year 1 | Conservative, achievable with 2-3 gigs/month |
| DEC-23 | Platform revenue | Break-even or minimal; not the business | Avoid over-engineering billing/subscriptions |
| DEC-24 | Single-operator concentration risk | **Known and accepted for Year 1.** Mitigation plan for Year 2: recorded keynotes scale Avi's time; co-trainer pipeline for lower-ticket workshops; partner network for overflow. If Avi is unavailable 6+ weeks, platform content + community continue generating leads passively. | Founder-led businesses carry this risk; acknowledge, don't ignore |
| DEC-25 | Corporate tier pricing (confirmed May 2026) | **הרצאה:** עד 3 שעות · ₪9,000 + מע"מ · 50-500 משתתפים. **סדנה:** יום אחד 6-8 שעות · ₪15,000 + מע"מ · 8-30 משתתפים. **בוטקאמפ:** 4-5 שבועות · 2 שעות שבועיות + שעת קבלה · ₪35,000 + מע"מ · 8-20 משתתפים. Bootcamp = הכי פופולרי badge. | Confirmed by Avi in ACT-29 |

---

## Reference

- **Active stack**: Django 5.2, Gunicorn, WhiteNoise, SQLite (Render disk), django-allauth (Google + GitHub OAuth), Bunny Stream (video), Resend (email), Plausible (analytics), OpenAI API (AI chat, GPT-4o-mini / GPT-4o)
- **Parked components (see DEC-19a)**: Stripe checkout, Green Invoice integration, GitHub Copilot seat provisioning. Code shipped under REQ-1.4.* and REQ-1.5.*, not wired into the active funnel. May be revived in §2.10 (P3).
- **Live URL**: https://babook.co.il
- **Repo**: https://github.com/avisalmon/Render (branch `main`)
- **Deploy**: `git push origin main` → Render auto-deploys
