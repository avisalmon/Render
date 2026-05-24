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
- SPR-1.6 Copilot Seat Provisioning (Parked Scaffolding)
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

### SPR-1.6 — Copilot Seat Provisioning (Parked Scaffolding)

**Goal:** Keep the local models, dashboards, and policy scaffolding ready while live GitHub billing/provisioning remains parked.
**Status:** DONE (scaffolding) / DEFERRED (live GitHub API)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.6.1 | GitHub org + Copilot Business activation placeholder | REQ-1.5.1 | DEFERRED | Org `babook-learn` exists; live Copilot Business activation parked until §2.10 |
| F-1.6.2 | GitHub username on user (via OAuth or manual) | REQ-1.5.2 | DONE | github_username field on UserProfile |
| F-1.6.3 | Copilot-included subscription tier flag | REQ-1.5.3 | DONE | CopilotSeat model with status choices |
| F-1.6.4 | Auto-invite scaffold | REQ-1.5.4 | DONE | app/copilot.py invite_to_org() stub; no live GitHub API call |
| F-1.6.5 | Auto-assign scaffold | REQ-1.5.5 | DONE | app/copilot.py assign_copilot_seat() stub; no live GitHub API call |
| F-1.6.6 | Revoke scaffold | REQ-1.5.6 | DONE | app/copilot.py revoke_copilot_seat() stub; no live GitHub API call |
| F-1.6.7 | Inactivity reclamation scaffold | REQ-1.5.7 | DONE | app/copilot.py check_inactivity(); local policy logic only |
| F-1.6.8 | Admin Copilot dashboard | REQ-1.5.8 | DONE | /staff/copilot-dashboard/ — seats, cost, status |
| F-1.6.9 | Seat cap enforcement (`COPILOT_MAX_SEATS`) | REQ-1.5.9 | DONE | Waitlist when cap reached |
| F-1.6.10 | User-facing seat status on profile | REQ-1.5.10 | DONE | copilot_status in profile context |
| F-1.6.11 | Audit log of all seat events | REQ-1.5.11 | DONE | SeatEvent model with actor/reason/api_response |
| F-1.6.12 | Org-level Copilot policy draft | REQ-1.5.12 | DEFERRED | Final policy deferred until live Copilot reseller path returns in §2.10 |

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
| F-1.8.2 | Chat endpoint request/response MVP | REQ-1.6.2 | DONE | POST /api/chat/ with JSON; SSE streaming deferred to §2.7 |
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
**Status:** WIP (code ready; rclone configured; awaiting first successful prod backup verification)

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-1.10.1 | rclone configured for Google Drive remote | REQ-1.2.4 | DONE | RCLONE_CONF set on Render; prod run not yet verified |
| F-1.10.2 | Backup management command | REQ-1.2.4 | DONE | `python manage.py backup_db` (WAL checkpoint + upload + retention) |
| F-1.10.3 | Render cron job (03:00 UTC) | REQ-1.2.4 | DONE | `render.yaml` cron job defined |
| F-1.10.4 | Retention policy — keep last 30 backups | REQ-1.2.4 | DONE | `rclone delete --min-age 30d` in command |
| F-1.10.5 | Restore procedure documented | REQ-1.2.18 | DONE | `docs/procedures/backup_restore.md` complete |
| F-1.10.6 | Restore dry-run completed once | REQ-1.2.18 | TODO | ACT-3 done; awaiting first successful backup to test restore |

---

## Avi action items (mirror of spec §1.9)

| ACT | Title | Blocks | Status |
|---|---|---|---|
| ACT-1 | Sign up Resend, share API key | F-1.2.1 | DONE |
| ACT-2 | SPF/DKIM DNS records for babook.co.il | F-1.2.1 | DONE |
| ACT-3 | Configure Google Drive `rclone` token on Render (`RCLONE_CONF`) | F-1.10.1, F-1.10.6 | DONE |
| ACT-4 | Approve AI logo or provide own | F-1.3.4 | DONE |
| ACT-5 | Plausible account + site ID | F-1.3.9 | DONE |
| ACT-6 | Confirm Render persistent disk at `/var/data/` | F-1.1.2, F-1.1.8 | DONE |
| ACT-7 | Review draft privacy + terms text | F-1.3.8 | DONE |
| ACT-8 | Confirm Google OAuth redirect URI on prod | F-1.2.2 | DONE |
| ACT-9 | Bunny.net account + Stream library + API key | F-1.4.1 | DONE |
| ACT-10 | Stripe account (Israel) + keys | F-1.5.1 | DEFERRED |
| ACT-11 | Green Invoice account + API key | F-1.5.9 | DEFERRED |
| ACT-12 | Confirm עוסק status (מורשה/פטור) | F-1.5.9, F-1.5.11 | DONE |
| ACT-13 | Decide initial pricing (ILS) | F-1.5.2 | DONE |
| ACT-14 | Create/identify GitHub org for Copilot | F-1.6.1 | DONE |
| ACT-15 | Activate Copilot Business on org | F-1.6.1 | DEFERRED |
| ACT-16 | Generate org PAT / GitHub App with `manage_billing:copilot` | F-1.6.1 | DEFERRED |
| ACT-17 | Confirm pricing for Copilot tier (≥ ₪149/mo) | F-1.6.3 | DONE |
| ACT-18 | Configure Copilot org policies in GitHub UI | F-1.6.12 | DEFERRED |
| ACT-19 | Create OpenAI API account + payment method, share API key | F-1.8.1 | DONE |
| ACT-20 | Set token-rate limits per tier (daily caps) | F-1.8.6 | DONE |
| ACT-21 | Set monthly cost cap amount (USD) | F-1.8.8 | DONE |
| ACT-22 | Set up email addresses on babook.co.il domain: `privacy@`, `support@`, `noreply@` | F-1.2.1, F-1.3.8 | DONE |

---

## EPIC-2 — Authority Platform (Chapter 2)

**Goal:** Build the marketing funnel: Corporate page → Content → Newsletter → Forum. Every feature answers "Does this make Avi's phone ring?"
**Spec:** [main_spec.md §Chapter 2](main_spec.md)
**Owner:** Avi + Copilot
**Status:** WIP

**Sequencing (per spec §2.14):** P0a is the immediate conversion loop: `/corporate/` lean cut + newsletter capture. Then publish one flagship course, then add forum/community once there is enough content and traffic to avoid a cold launch.

Sprints in this epic:
- SPR-2.0.1 Design System Foundation
- SPR-2.1.1 Corporate Page — Conversion MVP
- SPR-2.1.2 Corporate Page — CMS & Social Proof (Deferred)
- SPR-2.1.3 Newsletter Capture — MVP
- SPR-2.1.4 Corporate Page — Polish & Compliance

---

### SPR-2.0.1 — Design System Foundation

**Goal:** Implement the dark-theme design system (CSS custom properties, typography, component base classes) that all Chapter 2 pages will use. Shared foundation, built once, reused everywhere.
**Status:** DONE
**Tests:** `tests/test_spr_2_0_1.py` — 17/17 GREEN. Full regression: 190/190 PASS.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.0.1 | CSS custom properties (color palette) | REQ-2.1.51 | DONE | `--bg-primary`, `--bg-surface`, `--bg-elevated`, `--text-primary`, `--text-secondary`, `--accent-*`, `--border` in `style.css` |
| F-2.0.2 | Typography setup (Heebo + Inter + JetBrains Mono) | REQ-2.1.52 | DONE | Google Fonts CDN with `display=swap`, preconnect hints |
| F-2.0.3 | Spacing & layout tokens | REQ-2.1.53 | DONE | `--space-section` (80px/48px), `--space-card`, `--max-content-width: 1200px` |
| F-2.0.4 | Dark card component (`.card-surface`) | REQ-2.1.54 | DONE | Uses `--bg-surface`, 8px radius, 24px padding, `--border` border, hover state |
| F-2.0.5 | WhatsApp sticky button component | REQ-2.1.39 | DONE | 56px circle (48px mobile), fixed bottom-right (left in RTL), `--accent-cta`, z-index 1000 |
| F-2.0.6 | Bootstrap RTL variant loaded | REQ-2.1.55 | DONE | Conditional `bootstrap.rtl.min.css` for Hebrew (was already in place from SPR-1.3, now verified by test) |
| F-2.0.7 | `base.html` dark theme integration | REQ-2.1.51 | DONE | body uses `--bg-primary`, dark nav/footer; all Chapter 1 pages still 200 |

---

### SPR-2.1.1 — Corporate Page: Conversion MVP

**Goal:** Ship a credible `/corporate/` page that can convert visitors now: page route, strong hero, static/page-local service tiers and FAQ, WhatsApp CTAs, lead form, email notification, basic SEO, mobile polish, and security. Admin-managed CMS/social-proof automation is intentionally deferred.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.1 | URL route + anonymous view + template | REQ-2.1.1, REQ-2.1.71 | DONE | `/corporate/` renders without login and extends base dark theme |
| F-2.1.2 | Basic SEO + sitemap inclusion | REQ-2.1.2 | DONE | Unique title/meta description + `/corporate/` in sitemap |
| F-2.1.3 | Fast page budget | REQ-2.1.6 | DONE | WebP hero, no render-blocking JS; verified in SPR-2.1.4 |
| F-2.1.4 | Responsive breakpoint pass | REQ-2.1.7 | DONE | Bootstrap grid verified; mobile breakpoints tested in SPR-2.1.4 |
| F-2.1.5 | Hero section | REQ-2.1.8, REQ-2.1.9, REQ-2.1.10, REQ-2.1.11, REQ-2.1.12 | DONE | Avi_03.jpg → avi-headshot.webp; ACT-23 DONE |
| F-2.1.6 | Static service tier cards | REQ-2.1.16, REQ-2.1.17, REQ-2.1.18, REQ-2.1.19 | DONE | Pricing confirmed per DEC-25; ACT-29 DONE |
| F-2.1.7 | FAQ accordion | REQ-2.1.25, REQ-2.1.26 | DONE | 10 Hebrew Q&As approved; ACT-28 DONE |
| F-2.1.8 | Contact form UI | REQ-2.1.29, REQ-2.1.34 | DONE | Accessible labels, fields per spec, inline success/error states |
| F-2.1.9 | Contact form submit + email | REQ-2.1.30, REQ-2.1.31, REQ-2.1.35 | DONE | POST creates CorporateLead row and sends notification email |
| F-2.1.10 | Spam protection + privacy notice | REQ-2.1.32, REQ-2.1.33, REQ-2.1.70 | DONE | Honeypot, rate limit, privacy link near submit |
| F-2.1.11 | WhatsApp CTAs + prefilled messages | REQ-2.1.39, REQ-2.1.40, REQ-2.1.41 | DONE | WHATSAPP_NUMBER=972547885798; ACT-24 DONE |
| F-2.1.12 | Basic conversion tracking | REQ-2.1.43, REQ-2.1.46 | DONE | Plausible form-submit event and UTM capture fields |
| F-2.1.13 | Accessibility baseline | REQ-2.1.58, REQ-2.1.59, REQ-2.1.60, REQ-2.1.61 | DONE | Full a11y audit completed in SPR-2.1.4 |
| F-2.1.14 | Mobile-specific polish | REQ-2.1.62, REQ-2.1.63, REQ-2.1.65 | DONE | Mobile hero 200px, stacked tier cards, sticky WhatsApp verified in SPR-2.1.4 |
| F-2.1.15 | Security checks | REQ-2.1.68, REQ-2.1.69 | DONE | CSRF enforced; message fields stripped and length-limited |

**Post-mortem:**

- What went well: the lean conversion MVP stayed focused on the real funnel: page, WhatsApp, lead form, email, tracking, security, and regression coverage. Static/page-local content avoided premature CMS work.
- What can improve: content-dependent items should be surfaced earlier as Avi ACT blockers before implementation starts, especially real imagery, pricing, FAQ approval, and production contact numbers.
- Direction check: still aligned with the north-star metric of inbound corporate inquiries. The page can collect leads locally now, but production readiness remains gated by ACT-23, ACT-24, ACT-28, and ACT-29.

---

### SPR-2.1.2 — Corporate Page: CMS & Social Proof (Deferred)

**Goal:** Add admin-managed content, logos, testimonials, counters, bilingual content, rich structured data, and detailed analytics after the conversion MVP is live or content churn justifies CMS work.
**Status:** DEFERRED

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.16 | SiteConfig singleton model | REQ-2.1.66 | DEFERRED | whatsapp_number, hero copy, thresholds, manual overrides |
| F-2.1.17 | ServiceTier model + admin | REQ-2.1.20 | DEFERRED | Move page-local tier data into admin when needed |
| F-2.1.18 | FAQ model + admin | REQ-2.1.27 | DEFERRED | Move page-local FAQ content into admin when needed |
| F-2.1.19 | CompanyLogo model + logo strip | REQ-2.1.13, REQ-2.1.14, REQ-2.1.15 | DEFERRED | Requires 3+ approved logos and permission evidence |
| F-2.1.20 | Testimonial model + section | REQ-2.1.21, REQ-2.1.22, REQ-2.1.23, REQ-2.1.24 | DEFERRED | Requires 2+ approved testimonials and consent evidence |
| F-2.1.21 | Counter strip + animation | REQ-2.1.47, REQ-2.1.48, REQ-2.1.49, REQ-2.1.50 | DEFERRED | Live aggregates/cached values; hidden below thresholds |
| F-2.1.22 | Open Graph social card | REQ-2.1.3 | DEFERRED | 1200x630 image and social metadata |
| F-2.1.23 | JSON-LD structured data | REQ-2.1.4, REQ-2.1.28 | DEFERRED | Organization, Service, and FAQPage schema |
| F-2.1.24 | Bilingual/LTR content | REQ-2.1.5, REQ-2.1.55, REQ-2.1.56, REQ-2.1.57 | DEFERRED | English copy and full layout flip |
| F-2.1.25 | Detailed Plausible taxonomy | REQ-2.1.42, REQ-2.1.44, REQ-2.1.45 | DEFERRED | WhatsApp/tier/scroll depth event props |
| F-2.1.26 | Advanced lead admin + retention | REQ-2.1.36, REQ-2.1.37, REQ-2.1.38 | DEFERRED | Status workflow, filters, bulk actions, 24-month anonymize |
| F-2.1.27 | Admin preview links | REQ-2.1.67 | DEFERRED | View-on-site and staff edit links |

---

### SPR-2.1.3 — Newsletter Capture: MVP

**Goal:** Add a lightweight capture mechanism for people who are interested but not ready to book a corporate call. This sprint should stay small and use the same design system as `/corporate/`.
**Status:** DONE

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.28 | Newsletter signup model or provider bridge | REQ-2.3.1 | DONE | `NewsletterSubscriber` model + admin; provider sync deferred |
| F-2.1.29 | Signup form component | REQ-2.3.2, REQ-2.3.3 | DONE | Email field, consent text, AJAX success/error state, confirmation email, 14-day purge command |
| F-2.1.30 | Capture placement | REQ-2.3.2 | DONE | Site-wide reusable footer partial, including `/corporate/` |
| F-2.1.31 | Double-submit/spam protection | REQ-2.3.11 | DONE | Rate limit, duplicate handling, honeypot |
| F-2.1.32 | Basic signup tracking | REQ-2.3.1, REQ-2.3.12 | DONE | Source page, UTM fields, Plausible signup-success event only |

**Post-mortem:**

- What went well: the MVP stayed narrow while still covering the legal-critical double opt-in path, duplicate-safe behavior, and source attribution.
- What can improve: newsletter requirements are broad; future slices should separate subscriber capture, unsubscribe/compliance, sending pipeline, and analytics into smaller explicit sprints from the start.
- Direction check: this strengthens the authority funnel by capturing visitors who are not ready for a corporate call yet, without adding popup friction.

---

### SPR-2.1.4 — Corporate Page: Polish & Compliance

**Goal:** Final QA hardening for the lean `/corporate/` MVP: accessibility, responsive layout, RTL, performance, and production edge cases. LTR/bilingual polish stays deferred with CMS/social-proof work.
**Status:** DONE
**Tests:** `tests/test_spr_2_1_4.py` — 32/32 GREEN. Full regression: 246/246 PASS.

| Feature ID | Title | REQ trace | Status | Notes |
|---|---|---|---|---|
| F-2.1.35 | WCAG AA contrast check | REQ-2.1.58 | DONE | All key combos verified: text-primary/bg-primary (≥4.5:1), text-secondary/bg-surface (≥3:1), accent-warm/bg-surface (≥3:1), white/accent-cta (≥3:1 large bold). --accent-cta darkened from #22c55e → #16a34a |
| F-2.1.36 | Keyboard navigation (full tab order) | REQ-2.1.59 | DONE | Skip-to-content link, all buttons labelled, all inputs have labels, :focus-visible outline added to style.css |
| F-2.1.37 | Screen reader audit (semantic HTML) | REQ-2.1.60 | DONE | Single h1, h1→h2→h3 hierarchy, ≥3 aria-labelledby sections, aria-live polite on form status, all images have alt |
| F-2.1.38 | Reduced motion support | REQ-2.1.61 | DONE | prefers-reduced-motion in style.css (global) and corporate.html inline style |
| F-2.1.39 | Mobile hero optimization | REQ-2.1.62 | DONE | 200px photo on mobile (≤768px), flex-column CTA stack, explicit width/height on img |
| F-2.1.40 | Mobile tiers stacked layout | REQ-2.1.63 | DONE | col-12 col-lg-4 Bootstrap grid; tier CTA width:100% |
| F-2.1.41 | Mobile sticky WhatsApp (non-overlapping) | REQ-2.1.65 | DONE | 48px on mobile; z-index:1000 (below Bootstrap modals at 1055) |
| F-2.1.42 | Performance audit (<400KB, FCP <1.5s) | REQ-2.1.6 | DONE | WebP hero (avi-headshot.webp); no render-blocking scripts in head |
| F-2.1.43 | Responsive breakpoint testing | REQ-2.1.7 | DONE | Bootstrap col-12/col-lg grid; viewport meta verified |
| F-2.1.44 | RTL layout verification | REQ-2.1.55 | DONE | dir= set via LANG_BIDI; sticky WhatsApp mirrors to left in RTL |
| F-2.1.46 | CSRF + input sanitization | REQ-2.1.68, REQ-2.1.69 | DONE | CSRF token present; message maxlength=1000; strip_tags in view (from SPR-2.1.1) |
| F-2.1.49 | Sitemap inclusion | REQ-2.1.2 | DONE | /corporate/ confirmed in /sitemap.xml |

---

### SPR-2.1 Avi Action Items

| ACT | Title | Blocks | Status |
|---|---|---|---|
| ACT-23 | Provide professional headshot photo (WebP, dark bg, chest-up) | F-2.1.5 | DONE |
| ACT-24 | Provide WhatsApp business number for env var | F-2.1.11 | DONE |
| ACT-25 | Collect company logo permissions (3+ companies) | F-2.1.19 | DEFERRED |
| ACT-26 | Collect testimonial quotes + consent (2+ people) | F-2.1.20 | DEFERRED |
| ACT-27 | Create 1200x630 social card image (for og:image) | F-2.1.22 | DEFERRED |
| ACT-28 | Review/approve FAQ content (Hebrew) | F-2.1.7 | DONE |
| ACT-29 | Confirm service tier pricing signals (ILS amounts) | F-2.1.6 | DONE |

---

## Counters (auto-rendered by [dashboard.html](dashboard.html))

<!-- The dashboard parses this file. Keep the table format above stable. -->
