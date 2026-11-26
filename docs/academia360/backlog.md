# Academia360: Backlog

> Sprints and their status. Spec: [spec.md](spec.md). Data model:
> [data_model.md](data_model.md) (approved 2026-11-26). Design:
> [design/README.md](design/README.md). Process:
> [building_an_app.md](../building_an_app.md). Status words: `planned`,
> `in progress`, `built in dev`, `shipped`, `dropped`.

## The order

| Epic | What it delivers | Status |
| --- | --- | --- |
| **D. Design** | One deep direction (Campus IL leads), approved by Avi, rules in spec ch. 5 | in progress |
| **A. Foundation and the public front door** | The app, the data, the API, the agent's door, the import, and the public home and institution pages live on babook.co.il | built in dev; reviewed 2026-11-26 (style approved, phone pass A.6); not shipped |
| B. The rest of the public site | The program page, map and list, researchers, compare, comments and corrections, search (programs by field wait for data, Epic I) | built in dev, awaiting Avi's epic review |
| C. People | Sign-in in the app's look, requests to join, approval queue, invitations, roles, admin overview | in progress (2026-11-26) |
| D2. Committee file and flow dashboard | Submissions, files, extracts, analysis, review form, dashboard | planned |
| E. Discussion, decision, letters | Threads, meetings and summaries, decision, letters, notifications | planned |
| F. Leader's workspace | Home, submit, KPIs, budget, 20%, letters | planned |
| G. Committee assistant | Model metadata, read-only queries, document index, super chat | planned |
| H. Leader's assistant | Policies, building the request, readiness view, KPI guidance | planned |
| I. Enrichment at scale | Agent runs as a routine, health view | planned |
| J. Later | Mail bot, scheduler, English, open data | planned |

Every epic ships on its own through the release train and is useful to Avi
from the chat the day it lands.

---

## Epic D. Design (gate 4b, before any screen is coded)

| Sprint | Content | Status |
| --- | --- | --- |
| D.1 | Round 1: three directions on three screens. Rejected by Avi (2026-11-26): stat tiles, same buttons, a template in three colours | done, rejected |
| D.2 | Campus IL language studied, tokens recorded in design/README.md. Avi picked it as the lead (2026-11-26) | done |
| D.3 | **Round 2, one direction built deep:** the public **home page** (the program at a glance, the criteria, the participating institutions, how to find your way) and the public **institution page**, at computer and phone width, real content, no stat tiles, no people illustrations, the 360 motif as the shape language. Four artboards on a private canvas and in `design/round2/`. Avi judges at the epic review | built, awaiting Avi |
| D.4 | Rules that survive the mockup written into spec chapter 5 (tokens, type, radii, shapes, how numbers are shown, the committee room's restraint, RTL rules, the banner). Leader home and committee dashboard drawn in the same family | rules written (spec 5.1 to 5.4); the two private screens are drawn when their epics start |

## Epic A. Foundation and the public front door

Ends with: `https://babook.co.il/academia360/` showing the program home and
32 institution pages from real data, and Avi reading and writing that data
from this chat.

| Sprint | Content | Tests written first | Status |
| --- | --- | --- | --- |
| A.1 Skeleton and circles | Django app `academia360`; claim and edit the shared files through `train.py claim` (settings, urls); own base template with the pilot banner; own 403/404/500 composed into the project's handlers; the permission layer (`public` / `institution` / `committee` circles, roles and attributes from data model §1); models of §1 to §3 (people, program, institution as public knowledge); migrations; DRF viewsets with full CRUD for them, documented schema; portal registry entry; `conftest.py` that blanks the real OpenAI key from the first test | banner on every page; each circle wall crossed and refused; a leader of A cannot read a row of B through the API; anonymous reads public rows only; registry sweep (`tests/test_spr_13_1.py`) | built in dev, committed 1a86ddf (2026-11-26); `tests/test_academia360_a1.py`, 18 tests |
| A.2 Program side and the import | Models of §4 to §10 (participation, submissions, files in private storage, KPIs, budget, review, discussion, decision, letters, public talk-back, AI, audit) plus meetings and requests to join; their API with one write-policy table (`access.WRITE_POLICY`) and chair-only fields; private file views with an access log; `import_reference` one-time command over the reference folder: program, years, the 11 criteria, the review form's questions, mandatory KPIs, guidelines, institutions, participations, submissions and files, contacts, analyses, structured institution data, researchers, KPI sheets, allocations, the letters. Budget sheets are kept as files only (formats differ too much to read blind) | the import runs twice and the second run changes nothing; a row edited in the app survives a re-run; the real reference folder is read when present (skipped, never faked, where it is not); private files are not reachable under the public media URL; the circle walls on every program-side model | in progress; `tests/test_academia360_a2.py` |
| A.3 The agent's door | `ACADEMIA360_AGENT_TOKEN` (fails shut, constant-time; `academia360/agent_auth.py`), the token acts as the admin inside the app only; the narrow role endpoint `api/roles/grant/` (grant / revoke for an existing account, never create, never escalate; chair and reviewer as attributes); `ChangeLog.actor_kind`, `AgentRun` and the `X-A360-Run` / `X-A360-Reason` headers; `scripts/a360.py` CLI against dev and prod | refusals first: unset token, wrong token, no account to act as, the token outside the app, grant to a missing account, escalation fields ignored, a leader without an institution, the endpoint closed to a committee member; the happy path logs as `agent`; the CLI builds the same requests | built in dev; `tests/test_academia360_a3.py`, 11 tests |
| A.4 The public front door | The home page: the program in a few sentences, the five-arc criteria ring, what the program asks, who takes part (not-applied muted), the program's timeline, the three ways in; the institutions page with kind chips and search; the institution page from real rows (identity, the process box that shows steps and never content, what the institution published, researchers with dated metrics and verified links, units and programs, numbers with source, centers, timeline); plain search over institutions, researchers, programs and guidelines; sign-in, "no access" and error pages in the same look. Coded in the round-2 language before Avi's verdict on it (his instruction: finish the epic, review it whole) | screen contract at 320/360/375/390/412 and 1280 (`tests/test_academia360_screens.py`: edge, 16px fields, 44px targets, labels, contrast, banner first, content first on a phone); content and circle on the pages (`tests/test_academia360_a4.py`: who applied, the process box never shows a letter, filters, search, no stat tiles) | built in dev, looked at on real data at 390 and 1280 |
| A.5 Ship | The road for the data: the reference folder never leaves Avi's PC, so `manage.py replicate_to --base https://babook.co.il` pushes the dev rows (Django fixtures, in model order, never the audit, AI or people tables) and the private files through two token-only endpoints (`api/admin/replicate/`, which refuses a target that already holds institutions unless forced); the submitted files' storage is a private bucket when `ACADEMIA360_GCS_BUCKET` is set, else the private folder on the disk; Render env vars declared. Then: full app tests, `manage.py check`, the security sweep for what A created, `train.py ship --app academia360` on Avi's word, verify live, set the token in Render, replicate, and Avi reads prod from the chat with `a360` | endpoints closed to all but token and admin; a full target refuses without force; audit and people tables never travel; a file lands under its row's name and is served by circle; the command round-trips (`tests/test_academia360_a5.py`) | built in dev; shipping waits for Avi's word |

Open points carried into A (answered as reached): data model §12 (1 to 6);
the admin overview's content (spec 2.6.7); official app or own product for
the "more on babook" menu.

## Epic A, after the review (2026-11-26)

Avi's verdict: the style is right ("הסגנון טוב אז תתקדם"); it did not open
nicely on his phone. A.6 answers that before B begins.

| Sprint | Scope | Tests | Status |
| --- | --- | --- | --- |
| A.6 The phone pass | The bar at phone width is two tidy rows (brand and sign-in, then the tabs); researcher links sit under the name, never across from it, and vanish when empty; the institution's English name, year and site as spaced spans; action pills may wrap; every public page read top to bottom on iPhone SE and Pixel 7 profiles and on the desktop | the screen contract gains the bar rule (PM-97); 7 screen and page tests green | built in dev |

## Epic B. The rest of the public site

Scope: spec 4.1 beyond the front door. Every sprint: desktop first, then
the phone pass of A.6 (both profiles, read top to bottom), then the
contract. What the data does not yet carry (programs by field, campuses,
year series, timelines) is left to Epic I rather than faked.

| Sprint | Scope | Tests | Status |
| --- | --- | --- | --- |
| B.1 The program | `/academia360/program/`: what the program is and its goals (the Program row), the eleven review domains with the five headline criteria in colour, the ten guideline sections readable in place, the five mandatory KPIs with how each is measured, the timeline, the official sources; the home links into it; guideline and criterion text searchable | page open to all; public-circle rows only; every section shows when its rows exist and hides when they do not; the search finds a guideline sentence | built in dev |
| B.2 The map and the list | `/academia360/institutions/` gains a map of the country (Leaflet 1.9.4 from cdnjs, OpenStreetMap tiles toned down by a CSS filter since CARTO's now want a key, markers by kind, a marker's popup links to the page) beside the list on the desktop and behind a "המפה" button on the phone, a region select next to the kind chips (which fold behind "סוג מוסד" on the phone, mistake 84), and the institutions' coordinates (`Institution.lat`, `lng`, `region`, seeded by city in the import; data_model §7 updated) | coordinates seeded idempotently for every city; the region filter; a page with no coordinates still renders; the map is a progressive layer (the list stands without JS) | built in dev |
| B.3 Researchers | `/academia360/researchers/` across institutions (filter by institution and kind, search by name and area, grouped by area words) and `/academia360/researchers/<slug>/` with the profile, dated metrics, links, unit and institution; the institution page links each name | public rows only, `verified` shown, the metric's date and source on the page, an unknown slug is the app's own 404 | built in dev |
| B.4 The institution page, completed | Collaborations and research centers as sections; metrics as sentences with year and source (one year, no chart; the chart arrives with the year series in Epic I); a "compare" link; comments and corrections entry points (B.5) | sections appear only with rows; sources on every number | built in dev |
| B.5 Talk back | Signed-in visitors comment and like on an institution's page and a researcher's page, and propose a correction on any fact (a short form: what is wrong, the right value, the source); `/academia360/me/` lists one's own proposals and their status; anonymous visitors see the comments and a sign-in invitation; the committee's and admin's decisions on corrections stay in the API (C and D2 build their screens) | anonymous cannot post (401/redirect), a signed-in person posts and sees their own status, a chair's decision shows on the proposer's page, every write in the ChangeLog, dir="auto" on typed text | built in dev |
| B.6 Compare | `/academia360/compare/?a=&b=&c=`: two or three institutions side by side on public facts: kind, city, founded, participation, student and faculty numbers with year, units, programs, researchers, collaborations; chosen from the list page | two and three, a missing slug ignored, numbers with their year, nothing from the institution or committee circles | built in dev |
| B.7 Search and the epic's end | Plain search widened to programs, researchers, guideline and criterion text, grouped by kind with counts; then the epic's end: the full app suite, `manage.py check`, the security sweep for what B added, bkm_drift, the review with Avi | search finds each kind; nothing private in results for anonymous; the whole suite green | built in dev; epic end 2026-11-26: 110 tests, check clean, sweep done (PM-98), drift clean |

Data flags for Epic I (seen while building B.3, not fixed by hand; the
rows are the truth and the fix is an enrichment run from the chat):
the reference's researcher import put a person's role into `areas` or into
a `Unit` ("President | Visual Communication", "פרופסור חבר"), and read a few
HTML headings as people ("🎨 אמנות חזותית ואיור" at Bezalel); 39 of 219
researchers carry a metric, 84 a link; `StudyProgram.field` is empty for
all 29 rows; `InstitutionMetric` has one year per key, so no series.

## Epic C. People

Spec 2.2 to 2.6, 4.5 and 4.8. The rule the whole epic stands on (methodology
53 and 55): every path that gives a person access goes through one function
in `academia360/people.py`, which writes the rows, logs the change and sends
the one mail, and a screen says "sent" only from the backend's own count.
The admin's screens live under `/academia360/manage/` (not `/admin/`, which
is Django's). Admin screens are drawn in the committee room's restraint
(spec 5.3): greys, dense rows, flat tables, no arcs.

| Sprint | What it delivers | Tests | Status |
| --- | --- | --- | --- |
| C.1 Ask to join | `/academia360/join/`: a signed-in person asks to be a program leader (their institution and title) or a committee member (who they are), with a message; anonymous visitors sign in first and come back; one open request per kind; the request is mailed to the admin; `/me/` shows the person's roles and requests with their status; the home page's doors and the sign-in page point at it | anonymous redirected and returned; a request lands and one mail leaves; a second open request of the same kind is refused; `/me/` shows status; a stranger's request never shows | built in dev (`tests/test_academia360_c1.py`, 5) |
| C.2 People, one function per act | `people.py`: grant and revoke a role, set and clear chair and reviewer, link a leader to an institution, approve or decline a request; each writes, logs and mails through `mail.py`; `RoleGrantView` and the CLI call the same functions; `POST api/admin/requests/<pk>/decide/` for the chat; a plain PATCH of a request's status through the generic API is refused with the pointer | a mail per path, counted; the backend refusing reads "not sent"; approve grants the role and mails the person; decline mails the word; the API refusals | built in dev (`tests/test_academia360_c2.py`, 8; the role API's a3 tests still pass) |
| C.3 Invitations | Invite by email a person who has no account: an `Invitation` with a token and a 14-day life, mailed with its link; the link page offers Google sign-in or a password account in the app's look (made only from a valid invitation, email fixed to the invited one); ownership first (the person who redeemed it may open it again), validity second; redeeming grants the role through C.2 | owner's second visit is a no-op; a stranger's is refused; expired refused; the account is made with the invited email and no flags; the role lands and the admin is told | built in dev (`tests/test_academia360_c3.py`, 6; migration 0004 adds `accepted_by`, `title`) |
| C.4 The admin's people screen | `/academia360/manage/people/`: the queue of open requests (approve, or decline with a word), everyone with a role grouped (admins; committee members with chair and reviewed institutions; leaders by institution with title), grant by email, invite, revoke, mark chair, assign a reviewer; every form posts to C.2 | admin only (committee and leaders get "no access"); each form through the browser once; the screen contract at every width | built in dev (`tests/test_academia360_c4.py`) |
| C.5 The admin overview | `/academia360/manage/`: people and roles in a sentence, institutions with and without a leader, participations by state, what is waiting on whom (open requests, open corrections, submissions with no review yet), what the public sent in lately with "hide" on a comment, what the agent did lately (`AgentRun`), AI spend today; the bar shows "ניהול" to the admin. Built to spec 4.5 as written; Avi's own words on it were cut off and he confirms or changes it at the epic review | admin only; every number read against the seed; hide works and is logged | built in dev (`tests/test_academia360_c4.py`); the bar shows ניהול to the admin as a yellow tab |
| C.6 The epic's end | The screen contract for every new screen, the whole app suite, `manage.py check`, the security sweep for what C added (forms, mails, the signup door, redirects), bkm_drift, the review with Avi | the whole suite green | planned |

## Epics D2 to J

Written as sprints when their turn comes; their scope is spec chapter 4 and
the order is spec chapter 6.
