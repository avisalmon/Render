# exo — Spec

> **Status: FULL SPEC, 2026-09-21.** Kickoff step 4. Written on the approved
> [data model](data_model.md). This is the complete "what and why": every epic
> and feature, ready to be turned into a backlog and built. Decisions that are
> still open are collected in Chapter 13 and are few. Everything else is settled.
>
> **App label `exo`**, mounted at **`/exo/`**. Isolated per
> `docs/building_an_app.md` (own app, own base template and menu, own docs, own
> DRF API; shares only the site login).

---

## 0. Principles and platform

### 0.1 What it is, in one paragraph

`exo` supports Avi's lecture and workshop on **Exponential Organizations** (Salim
Ismail's book). It is an open **educational handout** anyone can read, and an
invite-only **guided builder** that walks an approved person, step by step, from
"here is my idea" to an **Amazon-style press release** in a fake newspaper, with
a public **museum** of those press releases.

### 0.2 Platform: works fully on a phone, designed for both

Workshop participants will use this **on their phones, in the room**, during the
lecture. So every screen, including the AI chat and the brainstorm, must be fully
usable at phone width (~360-420px) with proper tap targets. It must also be
comfortable on a desktop, where people will do the longer thinking. Responsive,
tested at both widths; the phone-guard browser test pattern this site already
uses (tap-target minimum) applies.

### 0.3 Language

**The app is bilingual, Hebrew and English, and Hebrew is the default.** This
is a settled requirement (it resolved Q1), not a preference, and it is
cross-cutting:

- **The UI is fully available in both languages.** Every user-facing string is
  written in **both** languages in the sprint that creates it, never
  retrofitted. A **language switcher** lives in the app's own nav; the choice
  persists in the session, and on the user's profile when logged in.
  **Implementation: `exo/strings.py` + a `{% t %}` tag, not gettext** — the
  house pattern set by `sensorlab/strings.py` and adopted here for its reasons:
  this repo has no `locale/` catalogues and no `msgfmt` on this machine or on
  Render, so gettext would add a build step needing GNU binaries in two places
  for exactly two languages whose copy the app owns outright. Django's *own*
  strings (form and validation errors) still follow the request's active
  language, which is what the app's language middleware sets.
- **Direction follows language**: Hebrew renders RTL, English LTR, from one base
  rule on `<html dir lang>`, so no page is built twice.
- **Content is bilingual in the data**: the reference models carry `_he` / `_en`
  text fields (attribute names and definitions, learn pages, newspaper style
  names); a resource authored in only one language falls back to the filled one
  rather than showing a blank. The ExO framework terms (MTP, SCALE, IDEAS, the
  attribute names) keep their English form in the Hebrew UI with a Hebrew gloss,
  because that is how the field uses them.
- **Each Concept has a language** (`Concept.language`, defaulting to the UI
  language at creation): the AI interview, options and output run in it, and
  the press release records its own `language`, which is what the museum's
  language filter reads. A user can still choose the output language explicitly
  at stage 4 (§5.4, D4.7).

### 0.4 Two guiding rules from the methodology, restated for this app

- **Every real thing is a database row** (Rule 1). The 11 attributes, the learn
  content, the newspaper styles, every concept, every chat message, every option,
  every press release: models. Seeded once where it is reference data, then the
  DB is the truth.
- **A person can fix anything without `/admin/`**: every list is add / edit /
  delete (and reorder where order matters). Concepts, brainstorm entries, the
  press release text: all editable by their owner.

### 0.5 Isolation

Own `templates/exo/base.html` and nav; never the site's base; no link to the
main site from inside `exo`. Own `static/exo/`. Own error pages composed into the
project handlers. Own `docs/exo/` (this spec, `data_model.md`, `backlog.md`, a
dashboard). Migrate with `manage.py migrate exo`.

---

## 1. The two worlds and the map of the app

| Area | Who | Login | Where |
| --- | --- | --- | --- |
| **Learn** (educational handout) | anyone | **no**, and no login button shown | `/exo/`, `/exo/learn/…` |
| **Museum** (showcase of press releases) | anyone | no, to browse public ones | `/exo/museum/` |
| **Request access / login** | a would-be builder | the site's shared login | `/exo/join/`, `/exo/login/` |
| **Waiting room** | requested, not yet approved | yes | `/exo/waiting/` |
| **Builder** (Concept journey) | approved members | yes + in group | `/exo/concepts/…` |
| **Admin: requests & moderation** | Avi (superuser/staff) | yes | `/exo/manage/…` |

The one **entry point into the gated world** from the public pages is a single
button on the learn landing: **"בנה ארגון אקספוננציאלי"** (build an exponential
organization). Pressing it is the only place login is ever suggested to a
visitor; everywhere else the public half is simply open.

---

## 2. EPIC A — Foundation

The scaffold everything else stands on. Small, but it is where the isolation
rules are either honored or quietly broken, so it is its own epic.

- **A1. Django app `exo`**, own `models.py` / `views.py` / `urls.py` / migrations
  from `0001`, mounted in `mysite/urls.py` before the catch-all.
- **A2. Own base template and menu.** `templates/exo/base.html`: header with the
  `exo` wordmark, a menu of *Learn · Museum · Build* (Build only shows to
  approved members; for visitors it is the single "build" button on the landing,
  not a nav item), a footer with the book attribution (§3.4). Hebrew/RTL.
- **A3. Own static assets** under `static/exo/` (CSS, a tiny JS helper for CSRF +
  `fetch`, newspaper-style stylesheets).
- **A4. Error pages** (403/404/500) in the app's look, composed into the
  project's single handlers.
- **A5. DRF installed and wired** for this app, with a router at `/exo/api/`
  and the browsable API on (Chapter 9).
- **A6. Docs directory** `docs/exo/`: this spec, `data_model.md`, `backlog.md`,
  `dashboard.html`.
- **A7. One-time seeding** management command `seed_exo` (§10.1) wired into
  `render.yaml` like the other apps, **idempotent**.
- **A8. Settings/env**: `EXO_AI_PROVIDER`, `EXO_AI_MODEL`, per-user limits
  (§8.5), the approval-key env var (§4.6), all documented in `.env.example`.
- **A9. Bilingual from the first string** (§0.3): `exo/strings.py` holding both
  languages with a `{% t %}` tag; `exo/middleware.py` running each `/exo/`
  request under the chosen language via `translation.override` (so nothing
  leaks to the next request on that worker) and setting `lang`/`dir`; the
  language switcher in the app nav, reachable **without an account**; the single
  `<html dir lang>` rule in `base.html`; and the reference models seeded in
  **both** languages. Built in Sprint 1 so every later page inherits it.

---

## 3. EPIC B — Learn: the public educational handout

Fully open. No account, no nudge. It is the thing a person opens on their phone
while Avi is talking.

- **B1. Landing page** `/exo/`. The lecture's framing in a screenful: what an
  exponential organization is, the formula **MTP + SCALE + IDEAS**, and the
  single "build" button (§1). No login prompt anywhere else on the page.
- **B2. The 11 attributes, browsable.** `/exo/learn/` lists all attributes grouped
  **MTP / SCALE (5) / IDEAS (5)**, each a card: name (EN + HE gloss), one-line
  definition. `/exo/learn/<key>/` is the attribute page: the summary of that
  principle, its book pointer, and any embedded videos. Data: `ExoAttribute` +
  its `LearnResource` rows.
- **B3. General handout pages.** `LearnResource` rows with no attribute: an
  intro, "how to read the book", the two extra canvas blocks explained
  (abundance sources, launch steps), anything Avi wants as a handout. Ordered,
  publishable.
- **B4. Embedded video.** A `LearnResource.youtube_url` renders as a responsive
  embed (privacy-enhanced `youtube-nocookie` domain). Multiple videos per page
  allowed via multiple resources.
- **B5. Book attribution.** The public half **credits Salim Ismail's
  *Exponential Organizations*** clearly (landing + footer), with a pointer to the
  book. Correct, and good for credibility; positioning is §12.
- **B6. Content is editable without code.** All of Learn is `LearnResource` /
  `ExoAttribute` rows: Avi edits in admin (or via the API); seeding never
  overwrites his edits (§10.1).
- **B7. Search-engine friendly.** Public pages have proper titles/meta and are
  crawlable; the gated pages are `noindex`.

---

## 4. EPIC C — Access: request, wait, approve

Invite-only by design: the builder spends AI money and generates content, so a
person has to be let in by Avi.

- **C1. The gate is one function**: `is_exo_member(user)` = authenticated **and**
  in Django group **`exo_members`**, with a named **superuser bypass** (so the site
  admin is never locked out of his own app). Used by every gated view and API
  permission. The group is created by a migration so it exists on first deploy.
- **C2. Request access** `/exo/join/`. In the app's own look (not the site's
  branded pages): create the shared site account if new, or log in if existing
  — **email/password or the site's Google sign-in**, the same shared `User`
  table underneath — then create `Membership(status=requested)`. Immediate
  account, no verification-email ceremony (the methodology's "lighter front
  door"); access is still gated by the group.
- **C3. Waiting room** `/exo/waiting/`. A requested-but-unapproved member sees a
  calm page: "your request is waiting for approval", nothing else of the builder.
  Every gated URL redirects here for a `requested` member, and to `/exo/join/`
  for a non-member. **Denied** members see a plain "not approved" page, not a 404
  (the app does not hide that it exists).
- **C4. Admin approval view** `/exo/manage/requests/` (superuser/staff only).
  Lists memberships by status: **requested** (default tab, newest first) with
  **Approve / Deny** buttons; **approved** with **Revoke**; **denied** with
  **Re-approve**. Approve = set status, stamp `decided_at/by`, **add to group**.
  Revoke/deny = remove from group. Every action logged.
- **C5. Notifications on decision.** On approve, the member gets an email (the
  site's existing mail path) saying they are in, with a link to `/exo/concepts/`.
  *(Optional in sprint 1; the waiting page polling on refresh is the minimum.)*
- **C6. Approval from a chat, safely** — the methodology's BKM ("a key, not the
  house"). One endpoint, `POST /exo/api/approve/`, one job: approve an
  **existing** account by email into `exo_members`. Group name hardcoded; never
  creates a user; never escalates; fails shut when the env var is unset;
  constant-time compare; logs who/how; also usable by a superuser session. Refusal
  tests outnumber happy paths. Blast radius: "someone could approve a person into
  the ExO builder", nothing more. Reference: `ustrip/family_api.py`.
- **C7. Login/logout pages** in the app's look, against the shared `User`.

---

## 5. EPIC D — The Concept journey

The heart of the app. An approved member creates **Concepts** (many, "the more
the better"), each a stateful journey through four stages. The journey is a
**guided sequence**: the UI always shows where you are (a 4-step progress rail:
*ראיון → סיעור מוחות → אפשרויות → תוצר*), what is done, and the one thing to do
next.

### 5.0 Concepts: the list, and CRUD

- **D0.1** `/exo/concepts/` — the member's concepts as cards: title, stage,
  updated-at, a one-line MTP if set, a thumbnail of the press release once it
  exists. **"New concept"** button.
- **D0.2** Create: title only; the rest comes from the journey. Lands in stage 1.
- **D0.3** Every concept is a real object: **rename, delete** (with confirm;
  cascades its messages, entries, options and press release), **reorder** (drag
  or up/down; a `position` field). Delete never touches other users' data.
- **D0.4** `/exo/concepts/<id>/` **resumes**: redirects to the concept's
  `current_stage`. Closing the app and coming back lands exactly where you were.
- **D0.5** A concept can be **re-opened at an earlier stage** (e.g. go back and
  add brainstorm ideas). Going back never deletes downstream work; it marks it
  *stale* so the user knows options/output may no longer match (§5.6).

### 5.1 Stage 1 — AI interview → the MTP

- **D1.1** A chat, `/exo/concepts/<id>/interview/`. The assistant opens by asking
  what the person wants to build (organization, initiative, idea). Messages are
  `InterviewMessage` rows, so the transcript survives and resumes.
- **D1.2** **Reflect-back.** After the user describes it, the AI **echoes it back
  in its own words** to confirm understanding ("so you want to build a car rental
  service that…"), and asks the user to correct it until it is right.
- **D1.3** **Special and unique.** The AI asks what the user thinks could be
  **special** about their idea and what could be **unique** — two distinct
  questions, adaptively followed up.
- **D1.4** **Adaptive, not scripted.** Follow-ups depend on the answers. The
  system prompt pins the *goal* (understand; extract MTP, special, unique) and the
  *boundary* (**no exponential ideas at this stage** — if the user asks for them,
  the AI says that comes next and stays in interview mode).
- **D1.5** **The MTP is the output.** When the AI judges the picture clear, it
  proposes a first-cut **Massive Transformative Purpose** and the *special* /
  *unique* summaries, shown as an editable **"settle the idea"** card. The user
  edits/accepts. Accepting writes `Concept.mtp/special/unique`, sets
  `current_stage = brainstorm`, and moves on. The user can also settle manually
  at any time.
- **D1.6** Streaming responses (tokens appear as they arrive) so the chat feels
  live on a phone; a visible "thinking" state; a retry on failure that never loses
  the transcript.

### 5.2 Stage 2 — Brainstorm across the attributes

- **D2.1** `/exo/concepts/<id>/brainstorm/`. The **13 slots** as cards in the
  canonical order: **MTP** (shown, editable, carried from stage 1), the **5
  SCALE**, the **5 IDEAS**, then the **2 extra blocks** (*sources of abundance*,
  *first launch steps*). Each card: the attribute name + Hebrew gloss, its
  one-line definition, a **prompt hint** tailored to help thinking, and the
  user's entries.
- **D2.2** Entries are **`BrainstormEntry`** rows: add (a text box, enter to
  add), **edit inline, delete**. Several per slot. Autosave; nothing is lost on
  navigation.
- **D2.3** **Phone-first layout**: one slot at a time with next/previous, plus
  an overview grid on wider screens. Progress shows how many slots have at least
  one entry.
- **D2.4** **Skipping is allowed.** No slot is mandatory; the AI in stage 3 works
  with what exists and says which slots had nothing.
- **D2.5** A small **"what is this attribute?"** link on each card opens the Learn
  page for it (§3) in a sheet, so the handout is one tap away mid-exercise.
- **D2.6** "Generate options" advances to stage 3 (allowed even with gaps).

### 5.3 Stage 3 — AI-generated options, and selection

- **D3.1** `/exo/concepts/<id>/options/`. On entering (or on "regenerate"), the
  AI produces **3-4 options per attribute** (the 11; the 2 extra blocks get
  options too, as concrete abundance sources and first steps). Inputs to the
  model: the MTP, special/unique, and **the user's own brainstorm entries for
  that slot** — the options must build on the user's thinking, not ignore it.
  Stored as `GeneratedOption` rows with an `order`.
- **D3.2** **"Research."** Each option carries a short `research_note`: why it is
  exponential, and a real-world reference or analogue where the model can give
  one. Honest labelling: the note is the model's reasoning and examples, not a
  verified citation, and the UI says so lightly. *(If a web-search tool is
  available to the provider it is used and noted; it is not required for v1 —
  Chapter 13, Q3.)*
- **D3.3** **Selection.** Each option has a select toggle; the user picks any
  number per attribute (including none). Selected = `is_selected`. A per-slot
  **"regenerate"** replaces that slot's *unselected* options only, so picks are
  never lost. A per-slot **"add my own"** lets the user type an option of their
  own (stored as a `GeneratedOption` flagged user-authored).
- **D3.4** Generation is **per slot, in parallel**, with each slot rendering as it
  completes, so a phone user sees progress rather than a long wait. Failures are
  per slot and retryable.
- **D3.5** A summary strip: N attributes with selections, M without. "Create the
  press release" advances to stage 4 (allowed with any selections; the AI works
  from what is selected and flags thin areas).

### 5.4 Stage 4 — The output: document and press release

- **D4.1** `/exo/concepts/<id>/output/`. From the MTP, special/unique and the
  **selected** options, the AI generates **two artifacts** in one `PressRelease`
  row:
  - **`document_body`** — the **detailed concept document**: the MTP, then each
    attribute with its chosen ideas and how they make the concept exponential,
    the abundance sources and first steps. The full "what we would build."
  - **`headline` + `body`** — the **Amazon-style press release** ("working
    backwards"): dated in the future, written as if launched, customer-centred:
    the problem, the solution, a customer quote, a leader quote, how to get
    started. Plus a short **FAQ** section (part of `body`).
- **D4.2** **Newspaper style.** The user picks a `NewspaperStyle` (§6.1); the
  press release renders inside that paper's look. Switching style re-renders the
  same content instantly (no regeneration).
- **D4.3** **Exponential score.** A single number (0-100) with a one-line
  rationale, generated alongside the artifacts. Shown as a badge on the release
  and in the museum. *(Single number by decision; a per-attribute breakdown is a
  later option.)*
- **D4.4** **Stress test.** One tap: the AI critiques the press release against
  Amazon's own kill question — *"would a real customer actually be excited by
  this?"* — returning 3-5 sharp points (what is compelling, what is vague, what a
  customer would not believe). Stored as `stress_test_feedback`, shown beside the
  release. The user can then **regenerate** the release taking the critique into
  account, or **edit**.
- **D4.5** **Editing.** Headline, body and document are **editable in place** by
  the owner (a real object, fixable without admin). Regenerate is always
  available and asks before overwriting edits.
- **D4.6** **Finalize.** "Publish to the museum" (or "keep private") sets the
  visibility (§7) and marks the concept `output`/done. The concept stays fully
  editable afterwards; re-publishing updates the museum copy.
- **D4.7** **Language of the output** is chosen here (Hebrew / English), default
  the user's UI language (§0.3).

### 5.5 Resume, progress, and going back

- **D5.1** `current_stage` is the single source of "where am I"; every stage page
  renders the progress rail from it.
- **D5.2** Going back to an earlier stage is allowed from the rail. Downstream
  artifacts are kept but shown with a **stale** marker ("your brainstorm changed
  since these options were generated") and a one-tap regenerate.
- **D5.3** Nothing in the journey is ever lost by navigation, refresh, or a
  failed AI call; every write is to a row.

---

## 6. EPIC E — The press release: styles, score, stress test

- **E1. Newspaper styles.** `NewspaperStyle` rows, seeded with an initial set
  (e.g. *Classic Broadsheet*, *Modern Tech Daily*, *Tabloid*, *Financial*, *Local
  Paper*, and a Hebrew-newspaper look), each a template + stylesheet: masthead,
  date line (a future date), typography, columns, a "photo" placeholder. **RTL
  and LTR variants** so Hebrew and English releases both look like real papers.
  Avi can add styles in admin without code (a style is data + a template file).
- **E2. Render pipeline.** The release page and the museum card render the same
  `PressRelease` through the chosen style; a **print/PDF-friendly** view for the
  "document" and the paper (browser print, no server PDF in v1).
- **E3. Score and stress test** as in §5.4; both regenerable.
- **E4. Share surface.** Every release has a **canonical public URL**
  `/exo/museum/<id>/` (visibility permitting), an **OG image/preview** (headline
  and masthead) so WhatsApp/email links unfurl nicely, and **share buttons**:
  WhatsApp, email, copy link (native share sheet on phones).

---

## 7. EPIC F — Visibility, sharing, the museum, gamification

### 7.1 Visibility (owner-controlled, default: share forever)

- **F1.1** `PressRelease.visibility` ∈ {`public`, `timed`, `specific`,
  `private`}; default **`public`** (from `Membership.default_visibility`).
- **F1.2** **`public`**: in the museum, viewable by anyone, forever.
- **F1.3** **`timed`**: public until `public_until` (a picker with presets: 24h,
  48h, 1 week, custom — "just for the workshop"). After that it is
  **owner-only**; it leaves the museum and shared links stop resolving for
  others. Computed live by the query; no expiry job.
- **F1.4** **`specific`**: only the users in `shared_with` (picked by email
  among site accounts) can open it, logged in. Not in the public museum.
- **F1.5** **`private`**: owner only. (This is the museum opt-out.)
- **F1.6** The owner can change visibility at any time from the release page;
  the museum reflects it immediately. Always visible to the owner.

### 7.2 The museum `/exo/museum/`

- **F2.1** Public, no login. A gallery of **currently-visible** releases
  (`public`, or `timed` still in window), each as a small newspaper front page in
  its style, with headline, concept title, score badge, like/view counts.
- **F2.2** Sort: newest, most liked, highest score. Filter: language, style.
  Paginated / infinite scroll, phone-friendly.
- **F2.3** Detail `/exo/museum/<id>/`: the full paper, the document (collapsed),
  the score, share buttons. Viewing increments `view_count` (once per session).
- **F2.4** **"News from the future"** framing: the museum's own header presents it
  as a gallery of artifacts from the future (§12.4).
- **F2.5** Admin moderation: a superuser can **hide** any release from the museum
  (`hidden_by_admin`), independent of the owner's visibility. Revoking a member
  does not delete their content; hiding is the tool.

### 7.3 Gamification (light)

- **F3.1** **Like**: one per user per release (`PressReleaseLike`, unique
  together), toggleable. Logged-in only; anonymous visitors see counts and a
  gentle "sign in to like" only on tap (no nagging).
- **F3.2** **Share** buttons (§E4) and a share count is *not* stored in v1.
- **F3.3** **View count** per release.
- **F3.4** The **exponential score** as a badge, and the museum's "highest score"
  sort, are the competitive hook for a workshop.
- **F3.5** Deliberately no comments, no follows, no feeds. A showcase, not a
  social network.

---

## 8. EPIC G — The AI layer

The app is AI-driven at three points (interview, options, output + score +
stress test). This chapter is how that is done safely, cheaply and reliably.

- **G1. One adapter, provider-configurable.** `exo/ai.py` exposes
  `chat(messages, stream=…)`, `generate_options(...)`, `generate_output(...)`,
  `score(...)`, `stress_test(...)`. Provider and model come from env
  (`EXO_AI_PROVIDER`, `EXO_AI_MODEL`). The site already has an OpenAI key wired;
  Anthropic is supported by the same adapter. *(Default provider: Chapter 13,
  D2.)* Views never call a provider directly.
- **G2. Prompts are versioned files** in `exo/prompts/` (system prompts per
  task, in Hebrew and English), so they are reviewable and testable, not buried
  in view code. Each prompt states its **role, goal, boundary** (e.g. the
  interview's "no exponential ideas yet").
- **G3. Structured output.** Options, score, and stress-test results are
  requested as **structured JSON** (schema-validated) and written to rows — never
  parsed loosely from prose. Failures to validate are retried once, then surfaced
  as a retryable error, never as silent garbage.
- **G4. Streaming** for the interview chat (server-sent events); non-streamed,
  per-slot parallel calls for options; single calls for output/score/test.
- **G5. Limits and cost control.** Per user (env-configurable defaults): max
  **20 concepts**, max **5 regenerations per stage per concept per day**, request
  timeouts, and a global daily spend guard that degrades to "try later" rather
  than failing the site. The approval gate (Chapter 4) is the primary control;
  these are the backstop. All AI calls are logged with user, concept, task,
  tokens.
- **G6. Content safety.** Public museum content is user-generated + AI-generated
  and visible to the world, so **before a release becomes `public`/`timed`** it
  passes a moderation check (the provider's moderation endpoint, called from
  `exo/ai.py`, fail-open with a log — the same stance as the site's
  `app/safety.py`, but **implemented inside `exo`** to keep the app encapsulated,
  not by importing from `app/`). Flagged content stays visible to the owner and
  is queued for Avi in `/exo/manage/`.
- **G7. Failure never loses work.** Every AI step reads from rows and writes to
  rows; a failed call leaves the previous state intact and shows a retry. No
  in-memory journey state.
- **G8. Test doubles.** The adapter is injectable; the suite uses a fake provider
  returning canned structured results, so the whole journey is tested without
  network, cost, or nondeterminism. One opt-in live smoke test per task for
  manual verification.

---

## 9. EPIC H — The REST API (DRF, full CRUD)

Standard infrastructure (Rule 6). Router at `/exo/api/`, browsable API on,
schema exposed. Pages are consumers of these endpoints (via the small `fetch`
helper); nothing a page does is impossible through the API.

| Resource | Endpoints | Who |
| --- | --- | --- |
| `attributes` | list, retrieve | anyone (read); admin write |
| `learn` (LearnResource) | list, retrieve (published) | anyone (read); admin write |
| `styles` (NewspaperStyle) | list, retrieve (active) | anyone (read); admin write |
| `membership` | `me` (my status), `request` (create) | authenticated |
| `manage/memberships` | list, approve, deny, revoke | superuser/staff |
| `approve` (key endpoint, §C6) | POST by email | token or superuser |
| `concepts` | full CRUD + `reorder`, `resume` | owner; member |
| `concepts/<id>/messages` | list, create (user turn); `stream` (assistant) | owner |
| `concepts/<id>/settle` | POST mtp/special/unique → stage 2 | owner |
| `concepts/<id>/entries` | full CRUD (BrainstormEntry) | owner |
| `concepts/<id>/options` | list; `generate` (all / one slot); patch `is_selected`; create (user-authored) | owner |
| `concepts/<id>/release` | retrieve, update (edit text), `generate`, `score`, `stress_test`, `publish` (visibility) | owner |
| `museum` | list (visible), retrieve (visibility-checked), `like` toggle, `view` | anyone / authenticated for like |
| `manage/releases` | list, `hide`/`unhide` | superuser/staff |

Permissions are one class per scope (`IsExoMember`, `IsOwner`, `IsExoAdmin`)
built on the single gate function (§C1). Ownership is enforced in querysets, not
just in checks, so a member can never even *list* another's concept.

---

## 10. EPIC I — Data, seeding, tests, quality, deploy

### 10.1 Seeding (one-time, idempotent)

- **I1.1** `seed_exo` seeds `ExoAttribute` (the 13), an initial set of
  `LearnResource` (one summary per attribute + intro pages, placeholders for Avi
  to edit), and the initial `NewspaperStyle` set — from a committed
  `exo/seed/` source. **Checks existence per key and never overwrites** an
  existing row; logs what it left alone.
- **I1.2** The ustrip lesson, enforced: a test runs `seed_exo` **twice**, edits a
  seeded row in between, and asserts the edit survives the second run.
- **I1.3** Seeding runs on every deploy via `render.yaml` and is therefore safe
  only because of I1.1.

### 10.2 Tests (what can break silently) — **I2**

- The gate: non-member, requested, denied, approved, superuser — every gated view
  and every API endpoint (refusals first).
- The approval key endpoint: the BKM refusal matrix (unset env, wrong token,
  unknown email, attempts to pass a group, attempts to escalate).
- The journey state machine: create → settle → brainstorm → options → output;
  resume lands on the right stage; going back marks stale, deletes nothing.
- CRUD + cascade: deleting a concept removes its rows and nothing else; a member
  cannot touch another's concept (queryset-level).
- AI adapter with the fake provider: structured-output validation, per-slot
  failure isolation, regenerate keeps selections, edits are asked before
  overwrite.
- Visibility: the museum query for public / timed-in-window / timed-expired /
  specific / private, and the detail view for owner / named user / stranger.
- Likes: idempotent, one per user.
- Phone guard: browser tests at phone width on the landing, an attribute page,
  the interview, brainstorm, options, output, museum — tap targets ≥ 44px.
- Seeding twice (§10.1).

### 10.3 Deploy discipline — **I3**

Dev first, always. `manage.py migrate exo` (scoped). `manage.py check`. Full
app test suite green. Smoke-test the real pages against seeded data. Push only
when asked. Verify the live site picked up something the old build could not
have (a new page), not just that the homepage loads.

### 10.4 Privacy and data — **I4**

- Concepts and chats are the member's; visible to the member and (for
  moderation) to Avi. Not to other members unless shared.
- Public museum content is public by the owner's choice (default) and can be
  withdrawn by the owner at any time (`private` / `timed` expiry) or hidden by
  Avi.
- Deleting a concept deletes its data. Revoking a member keeps their content
  (owner can still delete it after re-approval; Avi can hide it).

---

## 11. EPIC J — Admin and moderation (Avi's cockpit)

- **J1.** `/exo/manage/requests/` — approvals (§C4).
- **J2.** `/exo/manage/releases/` — all releases with visibility, flags from the
  moderation check (§G6), **hide/unhide**, open any concept read-only.
- **J3.** `/exo/manage/usage/` — AI usage: calls, tokens, spend estimate per
  day and per member (from the call log, §G5), and the daily guard status.
- **J4.** Content editing (attributes, learn pages, styles) via Django admin
  and the API; no custom editor in v1.
- **J5.** Dashboard `docs/exo/dashboard.html` for build progress, per Rule 4.

---

## 12. Prior art and positioning (research, 2026-09-21)

A web search found **no direct competitor** doing this end-to-end journey; the
pieces exist separately. Recorded here because it shaped four features.

- **12.1 OpenExO (Salim Ismail's org)** has the **ExO Canvas** (a static
  worksheet, 11 blocks + 2 extra — the source of the two extra brainstorm
  blocks), an **AI chat** trained on the book (Q&A, not a builder), the **ExQ
  assessment** (a diagnostic score for an *existing* org, used by 40,000+ — the
  inspiration for the exponential score, repurposed to rate a *new* concept), and
  human-run workshops. None is a guided build-a-concept-to-press-release journey.
- **12.2 MTP + SCALE + IDEAS = 11** is the canonical structure; the journey is
  built MTP-first for that reason.
- **12.3 Amazon PR/FAQ generators** exist but are generic; some run an AI
  interview to stress-test a PR/FAQ — the basis for the stress test. None is tied
  to ExO. ExO + the Amazon press release is part of what makes `exo` distinct.
- **12.4 "Artifacts from the future" / "news from the future"** is an
  established speculative-design format (Institute for the Future, Wired's
  "FOUND", Oakley 2025): curated galleries, not user-generated. It validates the
  museum's framing.
- **12.5 Positioning.** Built on OpenExO's public, book-based framework, adjacent
  to their official tools. Fine (the framework is published); the app credits the
  book. Adjacent-vs-differentiated-vs-partnership is a later call, not a blocker.

---

## 13. Open decisions (few; defaults stated — build proceeds on the defaults)

- **Q1. Language — RESOLVED 2026-09-21.** The app is bilingual, Hebrew and
  English, default Hebrew, UI and content alike (§0.3, A9). No longer open.
- **Q2. AI provider default.** The site has OpenAI wired; the adapter supports
  Anthropic too. Default to the provider already configured on the site; switch is
  one env var. Confirm or name a model.
- **Q3. Web search in stage 3.** v1 uses the model's knowledge with honest
  labelling; live web search added only if the provider exposes it cleanly.
- **Q4. Museum: public or members-only?** Default **public** (consistent with
  "share forever" as the default and the showcase purpose). Confirm.
- **Q5. Approval email (C5)** in sprint 1 or later? Default: later; the waiting
  page suffices to start.

---

## 14. Epic and feature inventory (the backlog seed)

| Epic | Features |
| --- | --- |
| **A Foundation** | A1-A9 |
| **B Learn** | B1-B7 |
| **C Access** | C1-C7 |
| **D Concept journey** | D0.1-D0.5, D1.1-D1.6, D2.1-D2.6, D3.1-D3.5, D4.1-D4.7, D5.1-D5.3 |
| **E Press release** | E1-E4 |
| **F Visibility · museum · gamification** | F1.1-F1.6, F2.1-F2.5, F3.1-F3.5 |
| **G AI layer** | G1-G8 |
| **H REST API** | the table in Ch. 9 |
| **I Data · tests · deploy** | I1.1-I1.3, §10.2-10.4 |
| **J Admin** | J1-J5 |

Suggested build order (to be turned into sprints in `backlog.md`): **A → C →
G(core adapter + fakes) → D1 → D2 → D3 → D4/E → F → B → J → I(hardening)**,
with B (Learn) early enough to demo in the next lecture, and the phone guard
applied from the first screen, not retrofitted.
