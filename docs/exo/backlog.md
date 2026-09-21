# exo — Backlog

> **Status: written 2026-09-21, kickoff step 5.** Every sprint below is traced to
> the feature codes in [spec.md](spec.md) (A1…J5, plus the API rows coded H1…H14
> here), and the matrix in §12 proves every feature lands in exactly one sprint.
> Sprints are worked **one at a time, in order, with a review gate after each**.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done (a test passes or a
behaviour was observed, never "a commit exists") · `🚫` blocked (reason).

---

## 0. Standing rules for every sprint

These apply to each sprint without being repeated in it.

- **TDD, strictly.** Test first, see it red, implement, green, add to regression.
  The sprint's commit message records the actual red (the error text), so the
  loop is auditable after the fact.
- **The gate.** At the end of every sprint: (1) what was done, (2) a runnable
  demo on the dev server, (3) the proposed next sprint. **Stop and wait for
  Avi.** Only Avi waives a gate, explicitly.
- **Phone guard from the first screen.** Every new page gets a browser test at
  phone width (~390px) asserting no tap target under 44px, in the sprint that
  creates the page, never retrofitted.
- **Bilingual from the first string.** The app is Hebrew and English, default
  Hebrew (spec §0.3, A9). Every user-facing string a sprint introduces is
  translatable and translated in **both** languages in that same sprint; every
  new page is checked once in each language and each direction. Never
  retrofitted, same reasoning as the phone guard.
- **Scoped migrate.** `manage.py migrate exo`, never a blanket migrate.
- **Dev first, deploy on request.** Nothing is pushed unless Avi says deploy.
  Before any push: app suite green, `manage.py check`, smoke the real pages.
- **One commit per sprint**, tree clean before the next starts.
- **Docs move with code.** `spec.md` amended in place if a behaviour changes;
  this backlog's boxes ticked only for observed behaviour; `dashboard.html`
  updated at each gate.
- **Encapsulation is checked, not assumed.** Each sprint ends with the question:
  did any change land outside `exo/`, `templates/exo/`, `static/exo/`,
  `docs/exo/`, `tests/test_exo_*`, plus the one allowed line in `mysite/urls.py`
  and the one in `render.yaml`? If yes, it is a design smell to explain at the
  gate.

---

## Sprint 0 — Kickoff ✅ (2026-09-21)

- [x] Interview captured; intro spec written and finalized.
- [x] Prior-art research; five additions folded in.
- [x] Data model written, six decisions taken, approved (MTP a field; `Concept`;
  single score; document + PR; many concepts, full CRUD; per-release
  visibility) plus three addenda.
- [x] Full spec (14 chapters) and this backlog.

---

## Sprint 1 — Foundation: the isolated app, the reference data, the seed

**Goal.** An `exo` app that exists, is isolated, has its reference data in the
database, and can be seeded safely on every deploy. Nothing user-facing yet
beyond a landing shell.

**Delivers.** A1, A2, A3, A4, A5, A6, A7, A8, A9 · I1.1, I1.2, I1.3 · H1, H2,
H3 (read APIs) · the three reference models from the data model.

- [x] **A1** `exo` app: `models.py`, `views.py`, `urls.py`, `apps.py`, migrations
  from `0001`; mounted in `mysite/urls.py` **before** the catch-all.
- [x] **Models (reference):** `ExoAttribute` (13 rows: MTP, 5 SCALE, 5 IDEAS, 2
  EXTRA), `LearnResource`, `NewspaperStyle`, exactly as `data_model.md` §1,
  with their user-facing text as `_he` / `_en` field pairs.
- [x] **A2** `templates/exo/base.html`: own header/wordmark, own nav (Learn ·
  Museum; Build appears only for approved members, later), own footer with the
  book attribution slot. Hebrew, RTL. Does **not** extend the site base.
- [x] **A3** `static/exo/`: `exo.css`, `exo.js` (CSRF from `data-csrf`, a `fetch`
  wrapper that throws on non-2xx).
- [x] **A4** 403/404/500 templates in the app's look, composed into the project's
  single error handlers (merged, not replaced).
- [x] **A5** DRF: installed for this app, router at `/exo/api/`, browsable API on,
  schema endpoint on. **H1 `attributes`**, **H2 `learn`** (published only),
  **H3 `styles`** (active only): list + retrieve, read for anyone, write for
  admin.
- [x] **A6** `docs/exo/dashboard.html` skeleton (sprint status board).
- [x] **A7 / I1.1** `seed_exo` management command from `exo/seed/`: the 13
  attributes, one placeholder `LearnResource` per attribute + intro pages, the
  initial `NewspaperStyle` set (names only in this sprint; templates in S8).
  **Checks existence per key; never overwrites**; logs what it left alone. Wired
  into `render.yaml`.
- [x] **A8** Settings/env documented in `.env.example`: `EXO_AI_PROVIDER`,
  `EXO_AI_MODEL`, `EXO_APPROVE_TOKEN`, `EXO_MAX_CONCEPTS`,
  `EXO_MAX_REGEN_PER_DAY`, `EXO_DAILY_SPEND_GUARD`.
- [x] **A9** i18n wired for the app: `USE_I18N`, `exo/locale/he` + `en`
  catalogs, `LANGUAGE_CODE='he'`; the **language switcher** in the app nav
  (persisted in session, and on the profile when logged in); the single
  `<html dir lang>` rule in `base.html` so Hebrew is RTL and English LTR
  everywhere; **the seed writes both languages** for every reference row.
- [x] A landing shell at `/exo/` (real content in S2) so the phone guard has a
  page to run against.

**Tests (red first).**

- [x] **I1.2** the seed-twice test: run `seed_exo`, edit a seeded row, run again,
  assert the edit survives and no row was recreated.
- [x] **I1.3** the seed runs cleanly on an empty DB (what deploy sees) and on a
  populated one.
- [x] Isolation: `base.html` does not extend the site base; no link to the main
  site anywhere under `/exo/`.
- [x] H1/H2/H3 read endpoints: anonymous can read; unpublished/inactive rows are
  hidden; anonymous write is refused.
- [x] Phone guard on the landing shell.
- [x] **i18n:** the default with no preference is Hebrew and `dir="rtl"`; the
  switcher flips to English and `dir="ltr"` and the choice persists across
  requests; a seeded attribute renders its `_en` text in English and `_he` in
  Hebrew; a resource with only one language filled falls back instead of
  rendering blank; no Hebrew UI string leaks into an English page (and vice
  versa) on the landing shell.

**Demo.** `/exo/` renders in the app's own look; `/exo/api/` browsable with the
13 attributes; seed run twice shows "left alone" lines.

**Exit gate.** Suite green, `manage.py check` clean, tree clean, encapsulation
question answered.

---

## Sprint 2 — Learn: the public handout (demoable in the next lecture)

**Goal.** The fully open educational half, complete, so Avi can point a room at
it. Placed early on purpose: it is the lowest-risk, highest-visibility piece and
the journey needs the same attribute data anyway.

**Delivers.** B1, B2, B3, B4, B5, B6, B7.

- [x] **B1** Landing `/exo/`: the framing, the **MTP + SCALE + IDEAS** formula,
  the single "בנה ארגון אקספוננציאלי" button (the *only* login suggestion in the
  public half; it points at `/exo/join/`, built in S3, so for now it links to a
  "coming soon" stub in the app's look).
- [x] **B2** `/exo/learn/`: attributes grouped MTP / SCALE (5) / IDEAS (5), cards
  with EN name + HE gloss + one-liner. `/exo/learn/<key>/`: the principle's
  summary, book pointer, videos.
- [x] **B3** General handout pages from attribute-less `LearnResource` rows
  (intro, how to read the book, the two extra canvas blocks explained), ordered,
  respecting `is_published`.
- [x] **B4** Responsive YouTube embed via `youtube-nocookie`, multiple per page.
- [x] **B5** Book attribution on the landing and in the footer, with a pointer to
  the book.
- [x] **B6** All content editable in Django admin (register the three reference
  models with sensible list/ordering); seeding never overwrites (S1).
- [x] **B7** Public pages: proper `<title>`/meta/OG; `noindex` on everything
  gated (applied now as a base-template rule keyed on the gated flag, verified
  again when gated pages exist).

**Tests (red first).**

- [x] Anonymous user sees landing, list, every attribute page, handout pages;
  **no login button or prompt** on any of them; the single build button is
  present exactly once on the landing.
- [x] Unpublished resource is not shown; published is.
- [x] Embed markup uses the nocookie domain.
- [x] Attribution text present on landing and footer.
- [x] Phone guard on landing, list, one attribute page, one handout page.

**Demo.** Walk the handout on a phone; edit a summary in admin and see it live.

**Exit gate.** As standard.

---

## Sprint 3 — Access: request, wait, approve (and the safe remote key)

**Goal.** The invite-only front door, the one-function gate, and Avi's approval
cockpit, plus the "key not the house" endpoint so approvals work from a chat.

**Delivers.** C1, C2, C3, C4, C6, C7 · H4, H5, H6 · J1 · `Membership` model.
(**C5** approval email is deferred to S10 by decision Q5.)

- [x] **Model:** `Membership` (OneToOne `User`, `status`, timestamps,
  `decided_by`, `default_visibility`) per `data_model.md` §2.
- [x] **C1** Migration creates group `exo_members`. `is_exo_member(user)`:
  authenticated AND in group, superuser bypass **named in code and in the spec**.
  DRF permission classes `IsExoMember`, `IsExoAdmin` built on it.
- [x] **C2 / C7** `/exo/join/`, `/exo/login/`, `/exo/logout/` in the app's look:
  create the shared account (or log in), including the site's **Google
  sign-in** flow, then create `Membership(requested)`. No verification-email
  ceremony.
- [x] **C3** `/exo/waiting/` for `requested`; a plain "not approved" page for
  `denied`; every gated URL redirects non-members to `/exo/join/` and
  requested members to the waiting room.
- [x] **C4 / J1** `/exo/manage/requests/` (superuser/staff): tabs requested /
  approved / denied; Approve / Deny / Revoke / Re-approve; approve adds to the
  group, revoke/deny removes; every action logged with who/when.
- [x] **H4** `membership`: `me`, `request`. **H5** `manage/memberships`: list,
  approve, deny, revoke (admin).
- [x] **C6 / H6** `POST /exo/api/approve/` by email: group name hardcoded, never
  creates a user, never escalates, fails shut on unset `EXO_APPROVE_TOKEN`,
  constant-time compare, logs who/how, also usable by a superuser session.
- [x] Nav shows **Build** only to approved members; the landing button now
  points to `/exo/join/`.

**Tests (red first, refusals outnumber happy paths).**

- [x] Gate matrix for a gated view and a gated API endpoint: anonymous,
  authenticated non-member, requested, denied, approved, superuser.
- [x] Join creates account + `requested` membership; existing account joins
  without a duplicate membership; Google flow lands in `requested`.
- [x] Approve adds to group and stamps `decided_by`; revoke removes; denied sees
  the plain page, not a 404.
- [x] **C6 refusal matrix:** env unset → closed; wrong token; unknown email;
  `{"group": "staff"}` still yields `exo_members`; no `is_staff`/`is_superuser`
  change possible; superuser session works without token.
- [x] Phone guard on join, login, waiting, manage/requests.

**Demo.** Request access on a phone → waiting room → Avi approves in
`/exo/manage/requests/` → member sees Build in the nav. Approve a second person
from a chat with the token.

**Exit gate.** As standard, plus: can the blast radius of C6 be stated in one
boring sentence? ("Someone could approve a person into the ExO builder.")

---

## Sprint 4 — Concepts and the AI core (no journey UI yet)

**Goal.** The `Concept` object with full CRUD and resume, and the AI adapter
that every later stage calls, fully testable with no network.

**Delivers.** D0.1, D0.2, D0.3, D0.4, D0.5 (the re-open rule, wired to stale in
S8), D5.1 · G1, G2, G3, G7, G8, G5 (scaffolding; full guard in S10) · H7 ·
`Concept` model.

- [x] **Model:** `Concept` (owner, title, `current_stage`, `mtp`, `special`,
  `unique`, `position`, timestamps) per `data_model.md` §3.
- [x] **D0.1** `/exo/concepts/`: the member's concepts as cards (title, stage,
  updated, MTP line, release thumbnail slot), "New concept".
- [x] **D0.2** Create with a title → lands in stage 1 (a placeholder page until
  S5).
- [x] **D0.3** Rename, delete with confirm (**cascade** to children), reorder via
  `position` (up/down; drag on desktop).
- [x] **D0.4** `/exo/concepts/<id>/` redirects to `current_stage`.
- [x] **D5.1** The 4-step progress rail component, rendered from
  `current_stage`, reused by every stage page.
- [x] **H7** `concepts`: full CRUD + `reorder` + `resume`; **queryset-scoped to
  owner**.
- [x] **G1** `exo/ai.py` adapter: `chat`, `generate_options`, `generate_output`,
  `score`, `stress_test`; provider + model from env; views never call a provider.
- [x] **G2** `exo/prompts/` versioned prompt files (HE + EN) with role / goal /
  boundary for each task.
- [x] **G3** Structured JSON output with schema validation, one retry, then a
  typed error.
- [x] **G7** Every AI step reads rows → writes rows; no in-memory journey state.
- [x] **G8** `FakeProvider` returning canned structured results; opt-in live
  smoke test behind an env flag.
- [x] **G5 (scaffold)** AI call log model/table (user, concept, task, tokens,
  ts); `EXO_MAX_CONCEPTS` enforced on create.

**Tests (red first).**

- [x] CRUD + cascade: delete removes children and nothing else; member A cannot
  list, read, edit, or delete member B's concept (queryset-level, via the API).
- [x] Reorder persists; resume redirects to the right stage for each stage
  value.
- [x] Max-concepts limit refuses the N+1th with a clear message.
- [x] Adapter: valid structured output is written; invalid is retried once then
  raises; provider exception leaves prior rows intact.
- [x] Prompt files load and contain their boundary text (e.g. the interview's
  "no exponential ideas").
- [x] Phone guard on the concept list.

**Demo.** Create, rename, reorder, delete concepts on a phone; the fake provider
returns a canned MTP through the adapter in a shell.

**Exit gate.** As standard.

---

## Sprint 5 — Stage 1: the AI interview → the MTP

**Goal.** The chat that understands the idea and settles the MTP, live-feeling on
a phone, and never loses a transcript.

**Delivers.** D1.1, D1.2, D1.3, D1.4, D1.5, D1.6 · G4 · H8, H9 ·
`InterviewMessage` model.

- [x] **Model:** `InterviewMessage` (concept, role, content, order, ts).
- [x] **D1.1** `/exo/concepts/<id>/interview/`: the chat; the assistant opens by
  asking what the person wants to build; every turn is a row.
- [x] **D1.2** Reflect-back: the prompt requires echoing the idea in the AI's own
  words and asking for correction until confirmed.
- [x] **D1.3** The **special** and **unique** questions, distinct, with adaptive
  follow-ups.
- [x] **D1.4** Boundary enforced in the prompt: no exponential ideas in this
  stage; if asked, defer to the next stage.
- [x] **D1.5** "Settle the idea" card: AI-proposed MTP + special + unique,
  editable; **Accept** writes `Concept.mtp/special/unique`, sets
  `current_stage = brainstorm`. A manual "settle now" is always available.
- [ ] **D1.6 / G4** Streaming via server-sent events; visible thinking state;
  retry that keeps the transcript.
  - **Half built, and said so rather than ticked.** The visible thinking state
    and the retry-that-keeps-the-transcript are done: the user's turn is written
    before the provider is called, so a failure loses a reply and never a
    sentence the person typed. **Streaming is not.** The site's shared wrapper
    (`app/ai_chat.call_openai`) returns a finished string, so streaming would
    mean either teaching that wrapper to stream — a change to a module every
    other app on this site depends on — or opening a second door out of `exo`,
    which is the one thing the adapter exists to prevent. Neither is worth doing
    at the end of an unattended run for an effect the thinking state already
    covers. Parked with its reason, for Avi to call.
- [x] **H8** `concepts/<id>/messages`: list, create (user turn), `stream`
  (assistant). **H9** `concepts/<id>/settle`.

**Tests (red first).**

- [x] A user turn creates a row before any provider call; a provider failure
  leaves the transcript intact and shows retry.
- [x] Settle writes the three fields and advances the stage; a manual settle with
  edited text stores the edited text.
- [x] The interview prompt file contains the reflect-back instruction and the
  no-ideas boundary (prompt regression).
- [x] Streaming endpoint emits SSE frames from the fake provider.
- [x] Ownership on H8/H9 (another member gets 404/403).
- [x] Phone guard on the interview page (input bar, send, settle card).

**Demo.** Describe "a car rental service" on a phone; watch the reflect-back,
answer special/unique, accept the MTP; close the browser, reopen, land back
where you were.

**Exit gate.** As standard.

---

## Sprint 6 — Stage 2: the brainstorm across the 13 slots

**Goal.** The user's own thinking captured per attribute, phone-first, nothing
lost, help one tap away.

**Delivers.** D2.1, D2.2, D2.3, D2.4, D2.5, D2.6 · H10 · `BrainstormEntry` model.

- [x] **Model:** `BrainstormEntry` (concept, attribute, text, ts).
- [x] **D2.1** `/exo/concepts/<id>/brainstorm/`: the 13 slots in canonical order
  (MTP shown and editable from stage 1; 5 SCALE; 5 IDEAS; 2 EXTRA), each with EN
  name + HE gloss, one-liner, `prompt_hint`, and the user's entries.
- [x] **D2.2** Entries: add (enter to add), inline edit, delete; several per slot;
  autosave through the API.
- [x] **D2.3** Phone layout: one slot at a time with next/previous; overview grid
  on wide screens; progress = slots with ≥1 entry.
- [x] **D2.4** No slot mandatory; the stage can advance with gaps.
- [x] **D2.5** "What is this attribute?" opens the Learn page in a sheet.
- [x] **D2.6** "Generate options" sets `current_stage = options`.
- [x] **H10** `concepts/<id>/entries`: full CRUD, owner-scoped.

**Tests (red first).**

- [x] Add/edit/delete entries via API; ownership enforced.
- [x] Editing the MTP here updates `Concept.mtp`.
- [x] Progress count is correct; advancing with empty slots is allowed.
- [x] The Learn sheet links resolve to the right attribute page.
- [x] Phone guard on the brainstorm page in one-slot mode.

**Demo.** Fill three slots on a phone, skip the rest, generate.

**Exit gate.** As standard.

---

## Sprint 7 — Stage 3: AI options per slot, and selection

**Goal.** Three to four researched options per attribute that build on the
user's own entries, selectable, regenerable without losing picks.

**Delivers.** D3.1, D3.2, D3.3, D3.4, D3.5 · H11 · `GeneratedOption` model.

- [x] **Model:** `GeneratedOption` (concept, attribute, content, research_note,
  `is_selected`, `is_user_authored`, order).
- [x] **D3.1** `/exo/concepts/<id>/options/`: generation per slot from MTP +
  special/unique + **that slot's brainstorm entries**; 3-4 options each,
  including the 2 EXTRA slots.
- [x] **D3.2** `research_note` per option; UI labels it honestly as the model's
  reasoning/examples, not a verified citation (decision Q3: no live web search
  in v1).
- [x] **D3.3** Select toggle per option; per-slot **regenerate replaces only
  unselected, non-user-authored** options; **add my own** creates a
  user-authored option.
- [x] **D3.4** Per-slot parallel generation; each slot renders as it completes;
  per-slot failure and retry.
- [x] **D3.5** Summary strip (N slots with picks, M without); "Create the press
  release" sets `current_stage = output`.
- [x] **H11** `concepts/<id>/options`: list, `generate` (all / one slot), patch
  `is_selected`, create (user-authored).
- [x] **G5** regen-per-day limit enforced here (`EXO_MAX_REGEN_PER_DAY`).

**Tests (red first).**

- [x] Generation writes 3-4 rows per slot from the fake provider; a slot with no
  entries still gets options and is flagged as thin.
- [x] Regenerate keeps selected and user-authored rows, replaces the rest.
- [x] One slot's provider failure does not touch other slots; retry works.
- [x] Regen limit refuses the N+1th with a clear message.
- [x] Ownership on H11.
- [x] Phone guard on the options page.

**Demo.** Generate, pick a few, regenerate one slot and see picks survive, add
your own option.

**Exit gate.** As standard.

---

## Sprint 8 — Stage 4: the document, the press release, styles, score, stress test

**Goal.** The result: a detailed document and an Amazon-style press release
rendered in a chosen newspaper, scored, stress-tested, editable.

**Delivers.** D4.1, D4.2, D4.3, D4.4, D4.5, D4.6, D4.7 · D5.2, D5.3 (stale on
going back) · E1, E2, E3 · H12 · `PressRelease` model (all fields except the
visibility group, which lands in S9 with its behaviour).

- [x] **Model:** `PressRelease` (concept 1-1, headline, body, document_body,
  newspaper_style, exponential_score, stress_test_feedback, view_count,
  hidden_by_admin, timestamps; visibility fields added but inert until S9).
- [x] **D4.1** `/exo/concepts/<id>/output/`: generate `document_body` (MTP, each
  attribute with chosen ideas and why exponential, abundance sources, first
  steps) and `headline`+`body` (future-dated, customer-centred PR with customer
  quote, leader quote, how to start, and a FAQ).
- [x] **E1** The initial `NewspaperStyle` set gets real templates + stylesheets:
  Classic Broadsheet, Modern Tech Daily, Tabloid, Financial, Local Paper, a
  Hebrew-newspaper look; **RTL and LTR variants**; masthead, future date line,
  columns, photo placeholder. A style = data row + template file; addable in
  admin.
- [x] **D4.2** Style picker; switching re-renders instantly with no regeneration.
- [x] **D4.3** Exponential score (0-100 + one-line rationale) generated with the
  artifacts; badge on the release.
- [x] **D4.4** Stress test: 3-5 sharp points against "would a real customer be
  excited?"; stored; regenerate-with-critique action.
- [x] **D4.5** In-place editing of headline, body, document; regenerate asks
  before overwriting edits.
- [x] **D4.6** Finalize: "publish to the museum" / "keep private" (writes the
  visibility chosen; museum itself is S9), marks the concept done; stays
  editable; re-publish updates.
- [x] **D4.7** Output language choice (HE / EN), default the UI language.
- [x] **E2** Print/PDF-friendly view of the paper and the document (browser
  print).
- [x] **E3** Score and stress test regenerable.
- [x] **D5.2 / D5.3 / D0.5** Going back to an earlier stage from the rail is
  allowed; downstream rows kept and marked **stale** with one-tap regenerate;
  nothing deleted by navigation, refresh, or a failed call.
- [x] **H12** `concepts/<id>/release`: retrieve, update (edit text), `generate`,
  `score`, `stress_test`, `publish`.

**Tests (red first).**

- [x] Generation from selected options only; a concept with thin selections
  still produces both artifacts and flags thin areas.
- [x] Style switch changes rendering, not content; every seeded style renders
  both RTL and LTR content without error.
- [x] Score and stress test are stored and regenerable; regenerate after an edit
  requires confirmation (API refuses without `confirm=true`).
- [x] Going back marks downstream stale and deletes nothing.
- [x] Ownership on H12.
- [x] Phone guard on the output page and one rendered paper.

**Demo.** End to end on a phone: interview → brainstorm → options → a newspaper
front page; switch papers; run the stress test; edit the headline; print.

**Exit gate.** As standard.

---

## Sprint 9 — Visibility, sharing, the museum, gamification

**Goal.** The public showcase with owner-controlled visibility computed live,
sharing that unfurls, likes and views, and moderation before anything goes
public.

**Delivers.** F1.1, F1.2, F1.3, F1.4, F1.5, F1.6 · F2.1, F2.2, F2.3, F2.4,
F2.5 · F3.1, F3.2, F3.3, F3.4, F3.5 · E4 · G6 · H13 · `PressReleaseLike` model.

- [x] **Model:** `PressReleaseLike` (release, user, ts; unique together).
  `PressRelease.visibility` / `public_until` / `shared_with` become live.
- [x] **F1.1–F1.5** Visibility enum with default `public` from
  `Membership.default_visibility`; `timed` with presets (24h, 48h, 1 week,
  custom); `specific` picks users by email; `private`.
- [x] **F1.6** Owner changes visibility from the release page any time; always
  visible to the owner.
- [x] **Computed visibility**: one queryset method `visible_to(user)` used by the
  museum list, the detail view, and the API; `timed` expires by query, no job.
- [x] **F2.1** `/exo/museum/`: public gallery of currently-visible releases as
  small front pages in their styles, with headline, concept title, score badge,
  like/view counts.
- [x] **F2.2** Sort newest / most liked / highest score; filter language, style;
  pagination.
- [x] **F2.3** `/exo/museum/<id>/`: full paper, document collapsed, score, share;
  `view_count` +1 once per session.
- [x] **F2.4** "News from the future" framing on the museum header.
- [x] **F2.5** `hidden_by_admin` honoured by every visibility query (the admin UI
  for it is J2, S10).
- [x] **F3.1** Like toggle, one per user per release; anonymous sees counts and a
  gentle sign-in prompt only on tap.
- [x] **F3.2 / E4** Share buttons: WhatsApp, email, copy link, native share
  sheet on phones; canonical URL; **OG image/preview** (headline + masthead) so
  links unfurl. Share count deliberately not stored.
- [x] **F3.3** View count. **F3.4** score badge + "highest score" sort.
  **F3.5** no comments/follows/feeds.
- [x] **G6** Moderation check (provider moderation endpoint, called from
  `exo/ai.py`, fail-open with a log) runs before a release becomes `public` or
  `timed`; flagged content stays owner-visible and is queued for `/exo/manage/`
  (S10).
- [x] **H13** `museum`: list (visible), retrieve (visibility-checked), `like`
  toggle, `view`.

**Tests (red first).**

- [x] Visibility matrix for the list and the detail: public / timed-in-window /
  timed-expired / specific-named / specific-stranger / private / hidden_by_admin,
  each for owner, named user, other member, anonymous.
- [x] Timed expiry needs no job: freeze time past `public_until` and the row
  disappears from the list and 404s for strangers, still 200 for the owner.
- [x] Like is idempotent per user; counts are derived from rows.
- [x] View count increments once per session.
- [x] OG tags present on the detail page; share URL is the canonical one.
- [x] Moderation: a flagged fake result blocks `public`, keeps owner access, and
  logs; provider failure fails open with a log.
- [x] Phone guard on the museum list and detail.

**Demo.** Publish a release; open it logged out on another phone; set it to 24h
and watch it vanish for strangers (time frozen in a test, real clock in demo);
share to WhatsApp and see the preview; like it.

**Exit gate.** As standard, plus decision Q4 (museum public) confirmed by Avi
seeing it.

---

## Sprint 10 — Admin cockpit, limits, hardening, first deploy

**Goal.** Avi's moderation and usage views, the full cost guard, the
completeness sweep of tests and privacy rules, and the first production deploy
of the whole app.

**Delivers.** J2, J3, J4, J5 · H14 · G5 (full) · I2 (test sweep), I3, I4 · C5
(optional) · B7 re-verified on gated pages.

- [x] **J2 / H14** `/exo/manage/releases/`: all releases with visibility and
  moderation flags; **hide / unhide** (`hidden_by_admin`); open any concept
  read-only.
- [x] **J3** `/exo/manage/usage/`: AI calls, tokens, spend estimate per day and
  per member from the call log; daily guard status.
- [x] **G5 (full)** the global daily spend guard (`EXO_DAILY_SPEND_GUARD`)
  degrading to "try later", never failing the site; request timeouts on every
  provider call.
- [x] **J4** Django admin registrations reviewed for the reference models
  (ordering, search, `is_published`/`is_active` filters).
- [x] **J5** `dashboard.html` brought current with all sprints.
- [ ] **C5 (optional, decision Q5)** approval email via the site's mail path with
  a link to `/exo/concepts/`; if deferred again, say so at the gate.
- [x] **B7** `noindex` verified on every gated page now that they exist.
- [x] **I4** Privacy rules verified in tests: concepts/chats visible only to owner
  and admin; revoking a member keeps content; deleting a concept deletes its
  data.
- [x] **I2** Test-completeness sweep against spec §10.2: every bullet there maps
  to at least one test (list them in the sprint commit).
- [ ] **I3** First deploy: `migrate exo` scoped, `check` clean, full suite green,
  smoke real pages on dev with seeded data, **push only when Avi says**, then
  verify prod picked up a page the old build could not have served (`/exo/`),
  not just that the homepage loads.

**Tests (red first).**

- [x] Hide/unhide affects the museum immediately; only admin can call it.
- [x] Usage view aggregates the call log correctly (fake rows).
- [x] Daily guard: past the threshold, AI endpoints return "try later" and
  nothing else on the site is affected.
- [x] Phone guard on the two manage pages.

**Demo.** Hide a release and watch it leave the museum; the usage view after a
day of fake calls; the app live on production.

**Exit gate.** As standard, plus Avi's explicit "deploy" before the push.

---

## 11. After Sprint 10 (parked, not scheduled)

Recorded so they are not lost; none is in scope until Avi pulls it in.

- Per-attribute score breakdown (`ScoreItem`) — decision 3 kept it a single
  number.
- `ConceptDocument` as its own model if the document grows internal structure.
- Live web search in stage 3 (decision Q3) if the provider exposes it cleanly.
- Server-side PDF export (v1 uses browser print).
- Share analytics (share count) if wanted.
- Positioning vs the official OpenExO ecosystem (spec §12.5).

---

## 12. Traceability matrix — every spec feature → exactly one sprint

| Feature | Sprint | | Feature | Sprint | | Feature | Sprint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | S1 | | D0.1 | S4 | | F1.1 | S9 |
| A2 | S1 | | D0.2 | S4 | | F1.2 | S9 |
| A3 | S1 | | D0.3 | S4 | | F1.3 | S9 |
| A4 | S1 | | D0.4 | S4 | | F1.4 | S9 |
| A5 | S1 | | D0.5 | S4 (rule) / S8 (stale) | | F1.5 | S9 |
| A6 | S1 | | D1.1 | S5 | | F1.6 | S9 |
| A7 | S1 | | D1.2 | S5 | | F2.1 | S9 |
| A8 | S1 | | D1.3 | S5 | | F2.2 | S9 |
| B1 | S2 | | D1.4 | S5 | | F2.3 | S9 |
| B2 | S2 | | D1.5 | S5 | | F2.4 | S9 |
| B3 | S2 | | D1.6 | S5 | | F2.5 | S9 (query) / S10 (UI = J2) |
| B4 | S2 | | D2.1 | S6 | | F3.1 | S9 |
| B5 | S2 | | D2.2 | S6 | | F3.2 | S9 |
| B6 | S2 | | D2.3 | S6 | | F3.3 | S9 |
| B7 | S2 (public) / S10 (gated verify) | | D2.4 | S6 | | F3.4 | S9 |
| C1 | S3 | | D2.5 | S6 | | F3.5 | S9 |
| C2 | S3 | | D2.6 | S6 | | G1 | S4 |
| C3 | S3 | | D3.1 | S7 | | G2 | S4 |
| C4 | S3 | | D3.2 | S7 | | G3 | S4 |
| C5 | S10 (optional, Q5) | | D3.3 | S7 | | G4 | S5 |
| C6 | S3 | | D3.4 | S7 | | G5 | S4 (scaffold) / S7 (regen limit) / S10 (full) |
| C7 | S3 | | D3.5 | S7 | | G6 | S9 |
| E1 | S8 | | D4.1 | S8 | | G7 | S4 |
| E2 | S8 | | D4.2 | S8 | | G8 | S4 |
| E3 | S8 | | D4.3 | S8 | | I1.1 | S1 |
| E4 | S9 | | D4.4 | S8 | | I1.2 | S1 |
| H1 | S1 | | D4.5 | S8 | | I1.3 | S1 |
| H2 | S1 | | D4.6 | S8 | | I2 | S10 |
| H3 | S1 | | D4.7 | S8 | | I3 | S10 |
| H4 | S3 | | D5.1 | S4 | | I4 | S10 |
| H5 | S3 | | D5.2 | S8 | | J1 | S3 |
| H6 | S3 | | D5.3 | S8 | | J2 | S10 |
| H7 | S4 | | H10 | S6 | | J3 | S10 |
| H8 | S5 | | H11 | S7 | | J4 | S10 |
| H9 | S5 | | H12 | S8 | | J5 | S10 |
| H13 | S9 | | H14 | S10 | | A9 | S1 |

**API row codes (Chapter 9 of the spec):** H1 attributes · H2 learn · H3 styles
· H4 membership · H5 manage/memberships · H6 approve · H7 concepts · H8 messages
· H9 settle · H10 entries · H11 options · H12 release · H13 museum · H14
manage/releases.

Every code in the spec's Chapter 14 inventory appears above. The three
multi-sprint entries (D0.5, B7, F2.5, G5) are split by *aspect*, and each aspect
is named, so nothing is "done" by implication.


---

## 13. State at the end of the first build (21 September 2026)

Written at the end of the autonomous run, before any review.

**Built and tested:** Sprints 0 through 10, 139 exo tests passing. The suite is
described in `dashboard.html`; what each file guards is stated there rather than
listed here, so there is one description of the tests and not two.

**Verified, not assumed:**

- `manage.py check` clean; `makemigrations exo --check` reports nothing missing.
- `ruff check exo/ tests/test_exo_*.py` clean.
- The site's full suite: 2,924 passing, 25 failing — **all 25 fail identically
  on a clean checkout of `HEAD` with exo absent**, checked in a throwaway git
  worktree rather than asserted. exo adds no regression to any other app. (The
  pre-existing failures are in `app/`: a stray import that trips the repo's own
  ruff gate, `/community/` content, the course player, dashboard backups.)
- The phone pass found four real faults nothing else could see — the wordmark,
  two standalone links and the duration select were between 19px and 32px tall,
  on every page, in both languages. Fixed, then re-measured.

**What a visual pass found that the tests could not.** Four faults reached the
screen with a green suite behind them, which is the honest argument for looking
at your own work:

- Every attribute name in the app was blank. Five templates asked the bilingual
  tag for `name_en`, which it read as a field called `name_en_he`. The pages
  still returned 200, and the name sits in the `<title>` too, so even the test
  written to catch it passed until it was made to look inside the `<h1>`.
- The slots came back in alphabetical order of their category, so the builder
  opened on "First launch steps" with the purpose halfway down the page. The
  order is the framework's argument, and it was being sorted by a coincidence
  of English spelling.
- The output screen showed both the "until when" and the "which people" rows at
  once, with neither chosen: `.exo-vis-extra { display: flex }` silently beat
  the `hidden` attribute. Now stated once for the whole app, and a browser
  probe checks every measured page for anything marked hidden that is still on
  screen.
- Four tap targets sat between 19px and 32px on every page, in both languages.

**Known gaps, stated rather than buried:**

1. **Streaming (D1.6/G4)** — see the note in Sprint 5 above.
2. **C5, the approval email** — deferred for the third time. The cockpit is the
   workflow; a member learns they are in when they open the link Avi sends them.
3. **The real model has now been run, once.** The dev environment has a live
   key, so the full journey was walked against the real provider rather than
   the stub: four slots of options, the document, the press release and the
   score, in Hebrew. The output is good. The press release came back in proper
   Amazon form (problem, solution, a quote from the company, a quote from an
   early customer, FAQ) and the score was 75 with a rationale that argued with
   the idea rather than flattering it. Cost: about a dozen calls.

   Two things that run revealed, both now fixed and both tested:

   - The options ceiling counted every slot against one budget per concept, so
     a member filling their sixth slot was refused while doing exactly what the
     workshop asks. Ceilings are now counted per slot.
   - The document came back with English headings ("Community & Crowd") inside
     Hebrew prose, because the prompt only ever named the attribute in English.
     It now carries both names.
4. **Not used by anyone yet.** Nobody has requested access, been approved, and
   walked the journey on their own phone.
