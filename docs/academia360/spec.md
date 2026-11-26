# Academia360: Spec

> **Status: kickoff, step 4 (full spec), 2026-11-26.** Chapters 1 and 2 are
> from the interview; the data model in [data_model.md](data_model.md) is
> **approved**; chapters 3 to 6 (the chat as the operating channel, the
> feature map, the pilot banner, design, the epics) hold Avi's additions of
> the same day. Next: the design options (chapter 5), then the backlog. Reference: [reference/README.md](reference/README.md). Process and
> rules: [building_an_app.md](../building_an_app.md).

---

## 1. What Academia360 is

### 1.1 In one paragraph

Academia360 is the working system around **אקדמיה 360**, the program of ות״ת
and מל״ג for deep change in bachelor's degree programs in Israel's higher
education institutions (2024 to 2028). It gathers in one place everything
about the program and the institutions taking part: the program itself and
its guidelines, the institutions, what each one submitted (its strategic
plan, its success measures, its budget), how the committee reviewed it, and
the letters the committee sent back. On top of that it gives each kind of
person the tools they need: the committee to review and discuss, the
institutions to work on their own plans and measures, and the public a clear
view of the program.

### 1.2 Who it is for (in short; chapter 2 defines them properly)

- **Avi, the full admin.** Owns the system and sees and manages everything.
- **Committee members.** See all the material, comment on it and discuss it.
- **Program leaders at the institutions.** See their own institution's
  material, and use the app's tools to evaluate, improve and discuss what
  they do.
- **The public.** Sees public information only.

### 1.3 Public material and committee material

This is the line the whole app is built around. There are two kinds of
material:

- **Public:** the program, its goals, criteria and guidelines, and public
  facts about the institutions.
- **Not public:** what the institutions submitted, the committee's reviews,
  results and comments, the response letters, budgets and contacts. The
  public never sees any of it. An institution's leaders may see part of what
  concerns their own institution; exactly which part is decided in
  chapter 2.

Who sees what, role by role, is the first thing chapter 2 settles. Until
then, everything that is not clearly public is treated as hidden.

### 1.4 AI at the center

AI is part of the product, not an extra. It is used for:

- smart search over all the material a person is allowed to see;
- chat about the quality of a proposal;
- guidance on the program's guidelines and on how to fill in a plan;
- help with KPIs and success measures.

The details come in later chapters. Two rules hold from now: the AI only
ever sees what the person asking is allowed to see, and it runs on the
server with the keys the site already has. No secret goes to the browser,
and none is kept in the app's files.

### 1.5 Where it starts

From real data. The local reference site Avi built in October 2025 holds the
list of institutions and almost everything relevant about them: who
submitted, the submitted files, the analysis against the program's criteria,
deep research on each institution, and the committee's response letters. It
is imported into the database once, and from then on the database is the
only source of truth. The reference itself is never committed, and the
static site is not ported as it is.

### 1.6 Language and place

- Hebrew, right to left, throughout.
- Its own app on this site, at `/academia360/`, with its own look and menu
  and its own docs in `docs/academia360/`, following the standing rules in
  [building_an_app.md](../building_an_app.md). It shares only the site's
  login.

### 1.7 What it is not

- Not the official site of the program. That stays at מל״ג.
- Not a copy of babook's training engine. If it ever needs courses or
  certificates, it uses babook's.

---

## 2. Personas, roles, flow and governance

*Draft from Avi's answers on 2026-11-26. The open points in 2.6 are still
his to decide.*

### 2.1 The process the app serves

אקדמיה 360 is a funding program. ות״ת (the Planning and Budgeting
Committee) sets the criteria, and each institution applies for a grant under
them. The program's committee then reviews each request, responds, and
approves. It is an ordinary grant process, and the app runs it end to end:

1. **The call.** The program, its criteria, its guidelines and each
   institution's allocation are published.
2. **Submission.** An institution's program leader submits the proposal in
   the app: the strategic plan, נספח א (success measures), נספח ב (budget)
   and the signed commitments.
3. **Review.** Committee members review each proposal against the
   committee's review form (formal requirements, institutional strategy, the
   20% target, the standard (תו תקן), innovation in teaching, employability,
   community, faculty training, management and budget, performance measures).
   For each item there is a checklist, the main points and notes for
   improvement. Committee members discuss it among themselves.
4. **Response.** The committee writes a response letter to the institution:
   general comments drawn from all the submissions, then specific comments on
   this proposal. The institution sees it only once it is sent.
5. **Approval.** The committee approves the request, and the funding with it.
6. **Follow-up.** The institution reports on execution and on its measures
   over the program's years, and may submit an updated plan. The cycle of
   review and response repeats on what it sends.

### 2.2 The roles

**Admin (Avi).** Owns the system. Gives people their roles and permissions,
links program leaders to their institutions, manages the public content, and
handles what the public sends in. Sees and can do everything.

**Committee member.** Sees all the material of every institution: the
requests, the files, the reviews, the comments of every committee member,
and the response letters. Everything is shared between committee members.
This is the role that reviews, discusses, writes the response and approves.

**Program leader (at an institution).** The person in charge of the program
at their institution. Linked in the database to one institution. Submits
their institution's proposals and files through the app, sees what their
institution submitted, and sees the response letters sent to their
institution. Never sees the committee's internal discussion, and never sees
anything of another institution. Uses the app's AI tools to work on their own
plan and measures.

**The public.** Anyone, without signing in. Sees the public side: the
program, and general information about the institutions (study tracks,
leading professors and researchers, and other public facts). A general
interest site. Once signed in, a person from the public can also comment,
like, and send the admin a proposed correction.

### 2.3 Who sees what

| Material | Public | Public, signed in | Program leader | Committee member | Admin |
| --- | --- | --- | --- | --- | --- |
| The program, its criteria and guidelines | see | see | see | see | edit |
| An institution's public profile (tracks, researchers, public facts) | see | see, comment, like, propose a correction | see | see | edit |
| Their own institution's submission and files | no | no | submit, see | see | all |
| Another institution's submission and files | no | no | no | see | all |
| The committee's reviews, comments and discussion | no | no | no | see, write | all |
| The response letter, before it is sent | no | no | no | see, write | all |
| The response letter, once sent | no | no | own institution only | see | all |
| Approval and funding decision | no | no | no | see; a chair decides | all |
| Corrections proposed by the public | no | their own | no | see; a chair accepts | all |

### 2.4 Governance

- Roles are given only by the admin. Nobody grants themselves access.
- A program leader belongs to exactly one institution, and every page and
  every AI answer they get is limited to it.
- The AI sees only what the person asking may see, by the table above.
- What the public sends in (comments, corrections) reaches the admin. A
  correction changes the public profile only when the admin accepts it.
- Every closed page answers "no access" without revealing what is behind it.

### 2.5 What the reference shows

The local reference (see [reference/README.md](reference/README.md)) holds
real examples of every step: the tracking sheet of submissions and
allocations, the committee's review form, the split of institutions between
reviewers, the submitted files, execution reports from some institutions,
and the response letters of April 2025. The app's records are modeled on
them.

### 2.6 Decisions (Avi, 2026-11-26)

1. **A person can hold several roles, and the higher one wins.** A
   committee member who is also a program leader at an institution sees
   every institution, because the committee role allows it. There is no
   conflict-of-interest hiding: committee members are professionals from
   the field, and this is inherent to the program. The admin assigns the
   roles.
2. **Reviewer is an attribute, not a role.** A committee member can be
   marked as reviewer of specific institutions (the split in the reference).
   It records who leads the review of what; it hides nothing from the other
   committee members.
3. **Committee chair is an attribute too, and the chair decides.** One
   committee member (Shira, later) carries the "committee chair" attribute
   and is the decision maker: approvals and the acceptance of public
   corrections are hers and the admin's. The system allows several chairs,
   though in practice there will be one.
4. **An institution can have several program leaders.**
5. **A program leader sees the response letter, and nothing more of the
   result.** No approval status, no amounts.
6. **Public corrections are visible to committee members**, but only the
   admin or a committee chair can accept one and change the public profile.
7. **The admin has an overview** of the whole system (people, roles,
   institutions, what is waiting). *Avi's words here were cut off.* Built in
   Epic C (C.5, `/academia360/manage/`) to 4.5 "Overview" as written: people
   and roles in one sentence, institutions that applied and have no leader,
   participations by state, what waits on whom (requests, corrections,
   submissions with no review), what the public sent in lately with "hide"
   on a comment, the agent's last runs, AI spend today. Avi confirms or
   changes it at the Epic C review.

---

## 3. Everything runs from the chat (Avi, 2026-11-26)

Avi builds, operates and enriches this system from his Claude chat, often
from a phone. "Everything from this chat" is a requirement of the product,
not a convenience of the build. It means:

### 3.1 Live production data, readable from the chat

The agent can read any row in production: list institutions, open a
submission, read every review of it, pull the KPI table of one institution
or of all of them, see what is waiting for the chair. This goes through the
app's own REST API (Rule 6), which exists for every model from day one, so
"show me X in production" is one call, not a database dump.

### 3.2 Updates from the chat

The agent can create and change rows in production: add an institution, fix
a professor's h-index, enter the KPI values from a spreadsheet Avi mailed,
attach a file, write a profile section, record a decision Avi dictates.
Every such write is a normal API write, recorded in the `ChangeLog` with
`actor_kind = agent` and the source it worked from, and grouped into an
`AgentRun` so Avi can later see "what did the chat do on Tuesday, from
which sources".

### 3.3 Enrichment by deep research

Avi wants to deepen the public knowledge about each institution the way the
reference did, and keep doing it over time: new researchers, updated
numbers, new centers, a timeline. The way this works: Avi asks in the chat,
the agent researches (web, documents he sends, the files already in the
system), writes structured rows (never prose into a text blob when a model
exists for it), cites the source on each row (`source`, `as_of`), and
reports what it added. Facts it could not verify stay out, or go in flagged
as unverified and hidden from the public until Avi confirms them in the app.

### 3.4 How the agent gets in, safely

Following the standing BKM in [building_an_app.md](../building_an_app.md)
("giving an agent a key, without giving it the house"):

- One token, one environment variable (`ACADEMIA360_AGENT_TOKEN`), fails
  shut when unset, constant-time compared, rotated by changing it.
- The token acts **as the admin, inside this app only**: it can touch every
  Academia360 row, and nothing outside the app. It cannot create or change
  site accounts, passwords or staff flags.
- Granting roles (section 2.2) is the one admin act that the token does
  through a narrow, named endpoint (grant / revoke a role for an account
  that already exists), as ustrip does, and never by editing `User`.
- Every use is logged (`AgentRun`, `ChangeLog`, `AccessLog`).
- A superuser session works everywhere the token does, so the same API is
  usable from the browser when Avi is at a computer.
- The blast radius, said plainly: someone holding this token could read and
  change the committee's material in this app. That is serious, so the token
  lives only in Render's environment and in Avi's chat with the agent, never
  in a file in the repo or the reference folder.

### 3.5 The agent's tools in the repo

A small command-line client, `scripts/a360.py`, wraps the API so the chat
can say `a360 institutions`, `a360 kpi --institution technion`,
`a360 import-researchers file.csv --institution shenkar`, `a360 grant
committee someone@example.com`, against dev or production. It is a thin
consumer of the API, like the pages are; it has no logic of its own.

---

## 4. What the app does: the feature map

High-level chapters, one per kind of person, then the shared machinery. Each
chapter becomes epics and sprints in [backlog.md](backlog.md); the order of
building is decided there, not here.

### 4.1 The public site: Academia 360 for everyone

- **The front door (Avi, 2026-11-26).** `/academia360/` is a public page,
  open without signing in, that gives the big picture from the top: what
  the program is in a few sentences, the five criteria as the way the
  program thinks, who takes part (the participating institutions, and that
  some did not), where the program stands in time, and a clear way in for
  each kind of visitor: read on as the public, sign in as a leader or a
  committee member, ask to join. Anyone who lands there understands the
  program and knows how to find their way through the site. It is the
  first screen designed (backlog D.3) and the first screen shipped (A.4).
- **The program.** What Academia 360 is, its goals, the five criteria, the
  guidelines section by section, the mandatory KPIs, the timeline of the
  program (call, submissions, letters, reporting years), links to the
  official sources.
- **The map of higher education.** Every budgeted institution on a map and
  in a list, by kind (university, college, teacher training) and region,
  with whether it takes part in the program.
- **An institution's page.** Identity, campuses, units and degree programs,
  student numbers over the years as a chart, research strengths and
  centers, collaborations, a timeline, and the leading researchers with
  their verified profiles and dated metrics. Every number shows its source
  and date.
- **Researchers.** A page per researcher, and a cross-institution view: who
  works on what, by field, with links out.
- **Study programs across the country.** All bachelor's programs by field
  (the 15 למ"ס fields), who teaches what where.
- **Compare.** Two or three institutions side by side on public facts.
- **Talk back.** A signed-in visitor comments, likes, and proposes a
  correction on any fact ("this number is wrong, here is the source").
  Their own proposals and their status are visible to them.
- **Search.** A fast plain search over the public side (institutions,
  programs, researchers, guideline text). No AI for the public (4.6).
- **Hebrew first,** right to left, phone first. Typed text gets
  `dir="auto"`.

### 4.2 The program leader's workspace: my institution

- **Home.** My institution, where it stands in the program (submitted, under
  review, responded, reporting), what is due next, the letters received.
- **Submit.** Start a submission of a kind (proposal, updated plan,
  execution report, KPI report), upload its files, fill in the structured
  parts (the plan's programs, KPI baselines and forecasts, budget lines,
  commitments, the graduate profile, the standard), save as draft, submit.
  A submitted package is frozen; a correction is a new submission.
- **Our KPIs.** The institution's measures as a table and chart across the
  years: baseline, forecasts, actuals as they come in. Enter this year's
  actuals here.
- **Our budget.** Planned against transferred against spent, by year and
  category, with the 15% community share shown against the requirement.
- **Our 20%.** The chosen basis (programs or students), the full list of
  degree programs, which ones the plan updates and their state, and the
  percent reached so far.
- **The letters.** Every response letter sent to this institution, as text
  and as the signed file. Nothing of the committee's internal work.
- **Our public page.** Preview the public profile as the public sees it and
  propose corrections to it (they go to the admin like any other).
- **AI help** (4.6): discuss the quality of our plan against the criteria,
  get guidance on the guidelines, help defining and measuring KPIs, draft
  improvements. Scoped to this institution and the public material only.
- **People.** See who else at the institution is a leader here.

### 4.3 The committee member's workspace

- **The flow dashboard.** The whole round on one screen: every institution
  with the state of its submission, who owns its review and how far each
  review is, the analysis, the decision, the letter (drafted / sent, with a
  link to it), what is waiting for me, what is waiting for the chair,
  deadlines. Filter by state, reviewer, kind of institution; click through
  to any item. This is the committee's working view and its status report
  in one.
- **Meetings and summaries.** A committee meeting is a row: date, who came,
  the agenda (which submissions), notes typed or pasted (or a transcript
  uploaded), and an AI summary with decisions and action items that a
  member edits and confirms. The same summary tool works on a discussion
  thread and on the comments of a review ("what did we say about Sapir's
  budget").
- **Reviewing the letters.** Before a letter is sent, every committee
  member can read the draft, comment on it inline and suggest changes; the
  chair resolves and sends. A letter's history (who changed what) is kept.
- **Finding a time to meet** (very low priority): propose a few slots,
  members tick what suits them, the chair picks. Our own small Doodle, only
  if ever wanted.
- **An institution's file.** Everything: public profile, participation,
  every submission with its files (viewable in the browser), the structured
  extracts (KPIs, budget, plan programs, graduate profile, standard,
  governance, contacts), the analysis against the criteria, every review,
  the discussion, the decision, the letters.
- **Review.** Fill the committee's review form for a submission, question
  by question: checklist mark, main points found, notes for improvement.
  Save as I go, mark done. See the other reviewers' answers side by side
  once mine is done (or always; a chair setting).
- **The analysis.** The criterion-by-criterion reading of a submission
  with strengths and challenges, written by a member or drafted by the AI
  and edited. One shared analysis per submission.
- **Discuss.** Threads per submission and per program, with mentions and
  notifications. Internal to the committee, never shown outside.
- **Compare across institutions.** The KPI table of all institutions on one
  measure; the budget shares; the 20% basis each chose; who addressed
  which criterion how (from the review checklists). The round seen as a
  whole, which is what the general comments of the letters are made of.
- **Letters.** Draft the response letter from the reviews and the analysis:
  the round's general sections (written once, reused), the specific
  sections for this institution, an AI first draft to edit. A chair or the
  admin sends it; sending makes it visible to the institution.
- **Public corrections.** See what the public proposed; a chair or the
  admin accepts or rejects.
- **AI help** (4.6): ask across all the material; "summarize what this
  institution plans for employability"; "which institutions mention a
  standard with a minimum bar"; "draft specific comments from these three
  reviews".

### 4.4 The chair

Everything a committee member has, plus:

- **Decide.** Record the decision on a submission: outcome, approved
  amount, conditions. Sends nothing by itself.
- **Send letters.** Release a drafted letter to the institution.
- **Accept corrections** from the public.
- **Round settings.** Open and close a round, set dates, assign reviewers,
  choose whether reviewers see each other's answers before finishing.

### 4.5 The admin

- **Overview.** People and their roles, institutions and their leaders, the
  state of every participation, what is waiting on whom, what the public
  sent in, what the agent did lately (`AgentRun`), AI spend today.
- **People, and requests to join.** A signed-in person can ask to be a
  program leader (naming their institution and their title) or a committee
  member (saying who they are). The request lands in the admin's queue with
  everything they wrote; the admin approves (the role is granted and the
  person is mailed) or declines with a word. The same screen invites by
  email, grants and revokes roles, marks chair and reviewers, links leaders
  to institutions. Each path goes through one function that also sends the
  mail.
- **Content.** Edit any public text and fact in the app, with the change
  history; manage the program's guidelines and criteria; hide a comment.
- **Import and enrichment.** The one-time import of the reference; later
  imports of spreadsheets and structured files per institution; the
  agent's enrichment runs with their sources. Each import idempotent.
- **The agent's door** (chapter 3): the token, the logs, the CLI.
- **Health.** Index freshness, failed extractions, files without extracted
  text, unverified facts waiting, AI cap status.

### 4.6 AI: one assistant per role, for two roles only (Avi, 2026-11-26)

AI costs tokens, and Avi pays for it where it earns its keep: **committee
members and program leaders get an assistant. The public and the admin do
not.** The public gets a fast plain search over the public side; the admin
works through the chat with the agent (chapter 3), which is a different
budget.

**The committee member's assistant: a super chat over everything.** Any
question about anything in the site: "which institutions chose the students
basis for the 20%", "what does Ariel plan for community engagement", "which
faculties does Shenkar have", "compare the KPI forecasts of the three
engineering colleges", "what did we say about Sapir's budget in the
discussion". Two sources feed it, and the assistant picks per question:

- **Facts from the data model.** The app generates, from the models
  themselves, a description of every table and field in plain Hebrew and
  English (what it is, its choices, how it relates), kept current by a test
  that fails when a model changes and the description did not. The
  assistant uses it to turn a question into a query over the rows, run it
  (read-only, inside the asker's circle), and answer from the result with
  the numbers. This is how "how many" and "which" questions get exact
  answers instead of guesses.
- **Text from the documents.** The index of chunks (data model, section 9)
  for anything written in a plan, a review, a letter or a discussion, with
  citations.

**The program leader's assistant: a guide to a quality submission.** Scoped
to their own institution and the public material:

- **Understand the policies:** what the program asks, criterion by
  criterion, what the review form will check, what the committee's general
  comments of the last round said everyone should do.
- **Build the request:** help draft each part (graduate profile, standard,
  plan components, governance), from the leader's own notes and the
  institution's public facts.
- **Evaluate before sending:** read the draft submission the way the
  committee will, question by question of the review form, mark what is
  missing or weak, and say why. The leader sees a readiness view ("formal
  requirements: complete; employability: thin, no employer named") before
  the submit button.
- **Guide the metrics:** define measurable institutional KPIs, check that
  the mandatory ones are filled, sanity-check forecasts against baselines,
  flag a KPI that does not follow from the strategy, propose how to
  measure.

**Drafting for the committee** (through the same assistant): the analysis of
a submission, the specific sections of a letter from the reviews, a meeting
or discussion summary. All drafts a person edits; AI-drafted rows are
flagged until confirmed.

Rules that hold everywhere: retrieval and queries are filtered by the
asker's circle and institution **before** the model sees anything; every
answer cites its sources (rows or chunks); the keys live on the server; a
daily cap per person and for the whole app in our own code, with a visible
"used today" line; the AI proposes, a person decides.

### 4.7 Documents and files

- Private storage for everything submitted, served only through a checking
  view, with an access log. Never under the public media folder.
- Text extraction on upload (PDF, DOCX, XLSX) into `extracted_text` and
  the AI index; a view of the extracted text next to the file.
- Spreadsheet import for נספח א and נספח ב into rows, with a preview before
  commit and a report of what could not be read.
- Generate the response letter as a PDF in the committee's format.
- Export any table (KPIs, budget, the board) to a spreadsheet.

### 4.8 Notifications

- Email on: a submission arrived (committee), a review is due (reviewer), a
  letter was sent (leaders), a decision was recorded (admin), a correction
  was proposed (admin, chair), a mention in a discussion.
- "Sent" means the backend said so (building_an_app.md, mistake 53).
- A bell in the app with the same items.

### 4.9 Security and privacy, from the first sprint

- Three circles enforced in one place (a permission layer every view and
  every API endpoint and the AI retrieval use), with tests that cross each
  wall and fail.
- Closed pages answer "no access", not 404; the app does not hide that it
  exists.
- Members' text is sanitized after markdown; JSON into pages is escaped;
  CSRF on every posting page; the security sweep list run in the sprint
  that creates each subject.
- Contacts (names, emails, phones) are committee material and never
  indexed for the public.

### 4.10 The pilot banner (Avi, 2026-11-26)

This is a pilot built by Avi Salmon, not an official site of the government,
of מל״ג or ות״ת, of Intel, or of any institution. Every page, for every
role, signed in or not, carries a **thin banner fixed at the very top**
saying so, in Hebrew (and English on any English page). It is always on: it
cannot be dismissed, it is part of the app's base template, and a test
reads it on every page. Wording to settle in the design chapter; the sense
is: "אתר פיילוט שנבנה על ידי אבי סלמון. אינו אתר רשמי של הממשלה, מל״ג/ות״ת,
אינטל או כל מוסד."

### 4.11 Later, if wanted

- **A mail bot for one named person**, as מט״צים has: a specified user
  writes emails, the bot reads them, does the work in the app, replies in
  the thread, and serves that person without Avi in the loop. Same
  mechanics as the matazim bot (local scheduled task, label-by-id, a
  heartbeat); specified when Avi names the person.
- A second program or a second round, reusing everything (the data model
  is built for it).
- Public open data: a documented read-only API of the public side.
- English pages for the public side.
- Per-institution dashboards an institution can embed on its own site.
- The meeting scheduler (4.3).

---

## 5. Design

The app must look like a professional website, built by people who build
such sites for ministries, universities and funding bodies, and not like a
generated one.

**How it was settled.** Round 1 (2026-11-26): three directions on three
screens, rejected by Avi as "boring, standard, AI made this": stat tiles,
same-looking buttons, one template in three colours. Round 2 the same day:
Avi picked **Campus IL** (campus.gov.il, Israel's national digital campus)
as the lead, and one direction was built deep on the two public screens,
the home page and the institution page, at computer and phone width
(`design/round2/`, four artboards). Sprint A.4 was coded in that language
before Avi's verdict on round 2, on his instruction to finish the epic and
review it whole; if he sends it back, the templates change and the data and
API do not.

### 5.1 The language

- **Ground:** paper `#FBFBF9`, cards white with a 14px radius and one soft
  shadow (`0 2px 14px rgba(40,44,45,.07)`), lines `#E6E8E8`. Ink `#2A2C2D`,
  muted `#666A6B` (4.5:1 on white and on paper).
- **The bar:** charcoal `#323435`, white wordmark "אקדמיה 360°" with the
  small ring mark; nav links in `#D6D8D8`, the current one white with a teal
  underline; a ghost pill for sign-in.
- **Four colours, used as colour and never as a wash:** teal `#63BAC5`
  (deep `#1E7C88` for links and small text), yellow `#F6C21A`, coral
  `#EE6B67`, green `#8FC457`, each with a tint for backgrounds (`#E7F5F7`,
  `#FEF5D6`, `#FCE7E6`, `#EEF6E3`). The fifth arc of the ring is charcoal.
- **The shape language is the 360:** arcs and rings in the tints, bleeding
  off the page corners, drawn as inline SVG with `aria-hidden`. No people
  illustrations, no gradients, no stock photos. A real photograph is allowed
  where it says something.
- **Type:** Assistant, 400/600/700/800. Page titles 34px on a phone, 48px on
  a computer, weight 800, tight leading; section titles 24/28px; body 16px,
  the lede 17/18px at 1.65.
- **Buttons are pills:** 46px high, 999px radius; dark (charcoal fill) for
  the one main action, line (1.5px charcoal border) for the second, ghost
  (white border) on the bar. Never two dark pills side by side.
- **Numbers live in sentences and small marks.** No stat tiles: no bare
  number over a label. "36 מוסדות מתוקצבים. 28 מהם הגישו..." is the
  pattern; a quantity that needs a visual gets a thin arc or a progress
  line beside its sentence. Tabular numerals, `dir="ltr"` on the number.
- **Every fact shows its source and date** in a 12px muted line under it
  (`.a360-src`): "מקור: ... · נכון ל־12.2024".
- **The pilot banner** (4.10) is the first element of every page: yellow
  tint, 12px, one line, never dismissable.

### 5.2 Components (all `a360-*`, tokens `--a360-*`, in `static/academia360/a360.css`)

`a360-pilot`, `a360-bar` / `a360-nav` / `a360-account`, `a360-hero` with
`a360-arc-*`, `a360-card`, `a360-pill-{dark,line,ghost}`, `a360-ring` (the
five-arc criteria ring), `a360-asks` (bordered-top list of what the program
asks), `a360-inst-groups` (institutions by kind, three columns on a
computer, one on a phone; not-applied names muted), `a360-steps` (the
program's timeline, horizontal on a computer, vertical on a phone),
`a360-doors` (the three ways in), `a360-rows` / `a360-row` (key: value
lines), `a360-tags`, `a360-chips` + `a360-search` (filters), `a360-form` /
`a360-field` (46px inputs, 16px text so phones do not zoom), `a360-fix`
(the "found a mistake" box), `a360-timeline`.

### 5.3 The committee room (to be drawn in D.4)

Same type, radii, pills and bar; the colour turned down: charcoal, greys,
one accent, flat tables that scroll in their own box on a phone, dense rows.
No arcs behind someone's budget.

### 5.4 Rules that hold on every screen

- Hebrew first, right to left; typed text `dir="auto"`; signed numbers and
  ranges `dir="ltr"`.
- Every number shows its source and date; evidence, not decoration.
- Dense, readable tables for the committee; calm, generous pages for the
  public; one system underneath.
- **Desktop is the priority, the phone is very good (Avi, 2026-11-26).**
  Every screen is designed for the computer first and must be perfect
  there; the same screen must also read well on a phone, because Avi
  reviews from his phone when he is away. "Perfect on desktop, very good on
  phone" is the bar, for every role and every screen; the screen contract
  runs both.
- The pilot banner on top of everything.

---

## 6. Epics, the direction (to be made into the backlog)

Order of building, each epic shippable on its own and useful to Avi from the
chat the day it lands:

- **A. Foundation and the chat as the operating channel.** The app, its base
  template with the banner, the three circles in one permission layer, the
  models of the data model, the full DRF API, the agent token, the CLI, the
  one-time import of the reference, a first public institution page. From
  this point Avi reads and writes production data from the chat.
- **B. Design and the public site.** The chosen look applied: the program,
  the map and list, the institution page with its charts, researchers,
  programs by field, compare, plain search, comments and corrections.
- **C. People.** Sign-in in the app's look, requests to join, the admin's
  approval queue, invitations, roles and attributes, the admin overview.
- **D. The committee's file and flow dashboard.** Participation,
  submissions, private files with extraction, structured extracts,
  analysis, the review form, the dashboard.
- **E. Discussion, decision, letters.** Threads, the chair's decision,
  letter drafting with shared general sections, inline review of drafts,
  sending, the PDF, notifications.
- **F. The leader's workspace.** Home, submit with structured parts and
  spreadsheet import, KPIs, budget, 20%, letters, public page preview.
- **G. The committee assistant.** Model metadata generation and the
  read-only query path, the document index with circles, the super chat,
  drafting and summaries, caps.
- **H. The leader's assistant.** Policies, building the request,
  pre-submission evaluation and readiness view, KPI guidance.
- **I. Enrichment at scale.** Agent runs from the chat as a routine:
  deep-research per institution, imports, verification flags, the health
  view.
- **J. Later.** The mail bot, the scheduler, English, open data.
