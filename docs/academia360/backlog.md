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
| **A. Foundation and the public front door** | The app, the data, the API, the agent's door, the import, and the public home and institution pages live on babook.co.il | shipped 2026-11-26, train T1126-191451 (0267727), live on babook.co.il; reviewed 2026-11-26 (style approved, phone pass A.6) |
| B. The rest of the public site | The program page, map and list, researchers, compare, comments and corrections, search (programs by field wait for data, Epic I) | shipped 2026-11-26, train T1126-191451 (0267727), live on babook.co.il; approved by Avi 2026-11-26 ("All ok") |
| C. People | Sign-in in the app's look, requests to join, approval queue, invitations, roles, admin overview | shipped 2026-11-26, train T1126-191451 (0267727), live on babook.co.il; approved by Avi 2026-11-26 ("All ok") |
| D2. Committee file and flow dashboard | Submissions, files, extracts, analysis, review form, dashboard | shipped 2026-11-27 morning, train T1127-073758 (96162b2), live; approved by Avi ("Ok. Push and cont") |
| E. Discussion, decision, letters, notifications | Threads, the chair's decision, letters with shared general sections, sending, the PDF, the bell | shipped 2026-11-27 10:55, train T1127-103925 (7958e06), after Avi's "Push" |
| **P. The institution page, read like a book; the reference in full** | The page rebuilt in Avi's order (status for the committee only, one paragraph, what matters to Academia 360, what they teach and how many, research that stands out, the story folded, compare at the bottom), a rich researcher page, a second reading of the reference (focus, metrics, publications, distinctions, student split, timeline), a coverage list in manage; no new facts for institutions without material | shipped 2026-11-27 18:42 (bc3f738), production replicated |
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
| A.5 Ship | The road for the data: the reference folder never leaves Avi's PC, so `manage.py replicate_to --base https://babook.co.il` pushes the dev rows (Django fixtures, in model order, never the audit, AI or people tables) and the private files through two token-only endpoints (`api/admin/replicate/`, which refuses a target that already holds institutions unless forced); the submitted files' storage is a private bucket when `ACADEMIA360_GCS_BUCKET` is set, else the private folder on the disk; Render env vars declared. Then: full app tests, `manage.py check`, the security sweep for what A created, `train.py ship --app academia360` on Avi's word, verify live, set the token in Render, replicate, and Avi reads prod from the chat with `a360` | endpoints closed to all but token and admin; a full target refuses without force; audit and people tables never travel; a file lands under its row's name and is served by circle; the command round-trips (`tests/test_academia360_a5.py`) | shipped 2026-11-26, train T1126-191451 (0267727), live on babook.co.il; token set in Render (the env-var change needed a deploy by hand, PM-105); 1919 rows and 108 files replicated the same evening |

Open points carried into A (answered as reached): data model §12 (1 to 6);
the admin overview's content (spec 2.6.7); official app or own product for
the "more on babook" menu.

## Epic A, after the review (2026-11-26)

Avi's verdict: the style is right ("הסגנון טוב אז תתקדם"); it did not open
nicely on his phone. A.6 answers that before B begins.

| Sprint | Scope | Tests | Status |
| --- | --- | --- | --- |
| A.6 The phone pass | The bar at phone width is two tidy rows (brand and sign-in, then the tabs); researcher links sit under the name, never across from it, and vanish when empty; the institution's English name, year and site as spaced spans; action pills may wrap; every public page read top to bottom on iPhone SE and Pixel 7 profiles and on the desktop | the screen contract gains the bar rule (PM-99); 7 screen and page tests green | built in dev |

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
| B.7 Search and the epic's end | Plain search widened to programs, researchers, guideline and criterion text, grouped by kind with counts; then the epic's end: the full app suite, `manage.py check`, the security sweep for what B added, bkm_drift, the review with Avi | search finds each kind; nothing private in results for anonymous; the whole suite green | built in dev; epic end 2026-11-26: 110 tests, check clean, sweep done (PM-100), drift clean |

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
| C.6 The epic's end | The screen contract for every new screen, the whole app suite, `manage.py check`, the security sweep for what C added (forms, mails, the signup door, redirects), bkm_drift, the review with Avi | the whole suite green | done 2026-11-26: 134 app tests green (110 + 24 of Epic C), screen contract at six widths, check clean, sweep clean, drift clean, PM-103 landed (BKM 062c4a2); approved by Avi 2026-11-26 ("All ok"), shipped 2026-11-26, train T1126-191451 (0267727), live on babook.co.il |

## Epic D2. The committee's file and flow dashboard

Spec 4.3 (the flow dashboard, an institution's file, review, the analysis),
4.7 (extraction), 5.3 (the committee room's restraint). Everything under
`/academia360/committee/`, committee only (a leader gets "no access"; the
leader's own workspace is Epic F). Discussion, decision and letters are Epic
E; "compare across institutions" waits for the budget and 20% rows, which
the import did not have (0 `TargetChoice`, 0 `BudgetLine`), and lands with E
or F. The data the room opens on day one: 28 proposals, 81 files, 24
analyses with 362 findings, 27 letters, 34 review questions under 11
criteria, 0 reviews.

Decisions taken while planning (2026-11-26 evening, to raise at the review):
the committee member's door is a teal "הוועדה" tab; the admin keeps the
yellow "ניהול" tab and reaches the room from the overview (six tabs do not
fit a 320px phone). PDF text comes through PyMuPDF: measured on four real
submitted PDFs, pypdf returned one of them with every Hebrew word reversed,
PyMuPDF read all four in order, five to ten times faster. Extraction runs
on the server that holds the files (a token endpoint and `a360 extract`),
never by shipping text from the PC.

| Sprint | What it delivers | Test first | Status |
| --- | --- | --- | --- |
| D2.1 The flow dashboard | `/academia360/committee/`: every institution of the round on one screen, a row each: kind, state, the latest submission and its files, the reviewers, reviews done of expected, the analysis (none / draft / confirmed), the decision, the letter (none / draft / sent, with its link); "waiting for me" first; filter by state, reviewer, kind, mine. A table on a computer, two-line rows on a phone. The "הוועדה" tab for committee members; the admin overview links to the room | closed to the public and to a leader (403), open to a member; a row per applied institution reading the seed; the reviewer's unfinished review counts as waiting for them and for nobody else; each filter narrows; the tab shows for the member and not the leader | built in dev 2026-11-26; `academia360/committee.py: board`, `templates/academia360/committee/board.html`; `tests/test_academia360_d1.py`, 5 tests |
| D2.2 An institution's file | `/academia360/committee/<slug>/`: participation and allocation, contacts, every submission with its files (open in the browser, download, the extracted text), the structured extracts that exist (graduate profile, standard, plan programs, components by criterion, governance, institutional KPIs with their values by year, 20% basis, budget, commitments, community share; an empty part says so), the analysis read by criterion, the reviews and their state, the letter and its file; links to the public page and back to the board | closed to a leader of that very institution; every section renders from the seed; a file link is the private view; the letter file link only when the file exists; a submission without an analysis says "אין ניתוח" and offers to write one | built in dev 2026-11-26; `committee.py: file`, `committee/file.html`; `tests/test_academia360_d2.py`, 4 tests |
| D2.3 Extraction | `academia360/extract.py`: PDF (PyMuPDF), DOCX (its XML), XLSX (`xlsx.py`) into `extracted_text`, with `extracted_at` and a note (pages, sheets, "no text", "unsupported", the error); on upload through the API; `POST api/admin/extract/` (token or admin) takes the files without text, a few at a time; `a360 extract`; `/academia360/files/<pk>/text/` shows the text beside the file for whoever may open the file; the admin overview counts files without text | each format from bytes built in the test; an empty PDF says "no text"; an unknown extension is noted, never raised; the endpoint is closed to a member; the text view follows the file's circle; the CLI builds the call; the overview number reads the seed | built in dev 2026-11-26; `academia360/extract.py`, migration 0005 (`extracted_at`, `extraction_note`), `api.py: ExtractView` and extraction on upload, `a360 extract [--count]`, `/files/<pk>/text/`; ten files per call (a real batch of 81 took 200 s on the PC); in dev 66 of 81 files have text, 14 are scans and one is `.ods`; `tests/test_academia360_d3.py`, 8 tests |
| D2.4 The review form | `/academia360/committee/review/<submission>/`: my review of this submission, created on first open (and the submission moves to "under review"); the form question by question under each criterion: the mark (yes / partly / no / not relevant), main points, notes for improvement, an overall note; save as I go, mark done, reopen; progress on the board; the other reviewers' answers side by side once mine is done, or always for a chair | opening creates one review per member; saving keeps answers; done sets the time and shows on the board; another member's answers are hidden until mine is done and shown to a chair; a leader is refused; every save is logged | built in dev 2026-11-26; `academia360/reviewing.py` (my_review, save_review, others), `committee/review.html`; an answered package ("responded") never waits for a review; `tests/test_academia360_d4.py`, 4 tests |
| D2.5 The analysis | `/academia360/committee/analysis/<submission>/`: the one shared analysis of a submission: summary, and under each criterion the findings, strengths and challenges, one per line, saved back as rows (a removed line removes its row); "confirmed" by a member; an AI draft shows as such (the flag exists for Epic G) | the seed's findings come back as lines; editing one line changes one row; removing a line deletes it; a new criterion block creates rows in order; confirmed and author are kept; logged; a leader refused | built in dev 2026-11-26; `reviewing.py: save_analysis, analysis_blocks`, `committee/analysis.html`; confirming an AI draft drops its flag; `tests/test_academia360_d5.py`, 3 tests |
| D2.6 The epic's end | The screen contract for every new screen at six widths (a member and the admin), the whole app suite, `manage.py check`, the security sweep for what D2 added (the private text view, the token endpoint, forms, the safe filter), bkm_drift, the post-mortem, the review with Avi | the whole suite green | done 2026-11-26 night: 151 app tests green (24 new), screen contract at six widths with seven new screens (three contract findings fixed: the checkbox as a 44px target, links on the room's grey at 5:1, a hidden legend that widened the phone page), check clean, sweep clean, drift clean, PM-106 (BKM a4bc52c); Avi 2026-11-27 morning: "Ok. Push and cont"; the first train (T1127-072834) failed on PyMuPDF missing from the train's own env (PM-107, mistake 82, BKM 72b2fcf; `train.py` now installs changed requirements); shipped by the next train, T1127-073758 (96162b2), live on babook.co.il |

## Epic E. Discussion, decision, letters, notifications

Spec 4.3 (Discuss, Letters, Reviewing the letters), 4.4 (Decide, Send
letters), 4.7 (the letter as a PDF), 4.8 (notifications: mail and a bell).
Started 2026-11-27 morning on Avi's "Push and cont" after Epic D2. Left out
on purpose: meetings and summaries (spec 4.3) wait for the AI summary of
Epic G, which is what makes a meeting row worth a screen; "compare across
institutions" still waits for the budget and 20% rows (Epic F).

Decisions taken while planning (2026-11-27, to raise at the review):

- A decision changes nothing the institution can see: the participation's
  status stays, and only the sending of the letter moves the submission and
  the participation to "responded" (spec 2.6.5: the leader sees the letter
  and nothing else of the result).
- Comments on a letter draft are a committee thread tied to the submission
  under a fixed title, shown inline under the draft; no new table.
- Notifications are a new table, `Notification` (user, kind, title, url,
  actor, read at), the bell of spec 4.8; data_model.md section 10 gets the
  row. Mail goes only where 4.8 lists it; the bell gets everything.
- Mentions are ticked from the list of members under the post, not parsed
  out of the text: Hebrew names have spaces in them.
- The PDF is ReportLab with the Heebo font already in `static/fonts/` and
  python-bidi, the way the breakout kit does it (a reference, not an import;
  rule 2). It is written into the letter's file at sending time unless a
  signed file was uploaded, and can be previewed on the fly before that.
- The specific sections of a letter can be drafted without AI, from the
  analysis's challenges and the done reviews' notes for improvement, one
  section per criterion; the AI first draft of spec 4.3 comes with Epic G
  through the same door.

| Sprint | What it delivers | Test first | Status |
| --- | --- | --- | --- |
| E.1 Notifications | `Notification` model and migration; `academia360/notify.py`: one function per event (a submission arrived: the committee, with the institution's reviewers told a review waits for them; a reviewer assigned to an institution with an open submission; a letter sent: the institution's leaders; a decision recorded: the admin; a correction proposed: the admin and the chairs; mentioned in a discussion; a new post in a thread I am in), each writing bell rows for everyone but the actor and mailing where spec 4.8 says; the bell in the bar for every signed-in person with the unread count; `/academia360/notifications/`: the list, newest first, unread marked; following an item marks it read; "mark all read"; the API route lists one's own only | a row per person, never the actor; the mail count is the backend's; the bell shows the count and nothing when zero; following marks read and redirects inside the app only; another person's rows are hidden from the API; the admin sees all | built in dev 2026-11-27; `academia360/notify.py` (tell + one function per event + the three views), migration 0006, `templates/academia360/notifications.html`, the bell in `base.html`; the arrival fires from the API's create and update of a Submission, the reviewer's from `people.set_attribute`, the correction's from `talk.correct`; `tests/test_academia360_e1.py`, 8 tests |
| E.2 Discussion | `/academia360/committee/discuss/`: the round's threads (about the program, about a submission), newest activity first, a form to open one; `?sub=<pk>` narrows to one submission's threads and opens the form on it; `/committee/discuss/<pk>/`: the thread, its posts as sanitized markdown, reply, edit my own post (stamped), mentions ticked from the members; the file lists each submission's threads | closed to the public and to a leader; a thread with a mention notifies and mails the mentioned; a reply notifies the thread's earlier people and not the author; only the author (or the admin) edits a post; a script in a post is stripped; the file shows the thread | built in dev 2026-11-27; `academia360/discuss.py`, `committee/discuss.html`, `committee/thread.html`, `committee/_mentions.html`; posts render through `text.render_markdown` (nh3); a reply form may say `next` (inside the app) for the letter page; `tests/test_academia360_e2.py`, 5 tests |
| E.3 The chair's decision | `/committee/decide/<submission>/`: the chair's (or the admin's) form: outcome, approved amount, conditions; one decision per submission, re-recorded in place; logged field by field; the admin is told; the board and the file link to it for a chair and show it to everyone | a member is refused, a chair records, the admin records; a second record changes the row and logs the change; the amount accepts "5,000,000"; the admin's bell and mail | built in dev 2026-11-27; `academia360/deciding.py`, `access.chair_only`, `committee/decide.html`; the board's decision cell is the chair's link, the file's row too; `tests/test_academia360_e3.py`, 4 tests |
| E.4 The letter | `/committee/letters/general/`: the round's general sections, written once (title, body, order; add, edit, remove); `/committee/letter/<submission>/`: the draft, made on first open with the addressee from the primary contact and every general section attached: addressee, the general sections ticked on or off, the specific sections (one textarea each, an empty one to add), a closing; "draft from the reviews" fills the specific sections from the analysis's challenges and the done reviews' notes, a section per criterion; the comments thread inline; the history (who changed what, from the ChangeLog); preview as a PDF | a general section edited once changes every draft that uses it; first open makes the draft with the addressee and the general sections; unticking removes a section row; "draft from the reviews" writes a section per criterion that has material and nothing for one that has none; an emptied section is deleted; the history lists the changes; a leader is refused | built in dev 2026-11-27; `academia360/letters.py` (general_sections, save_general, letter_of, drafted_specific, apply_draft, save_letter, compose, history), `academia360/letter_pages.py` (general, draft), `committee/letters_general.html`, `committee/letter.html`; the comments are the submission's thread "הערות על טיוטת המכתב" (discuss.letter_thread); `tests/test_academia360_e4.py`, 6 tests |
| E.5 Sending, the letter page, the PDF | `academia360/letter_pdf.py`: the letter as an A4 PDF (header, date, addressee, subject, sections, closing, the pilot line on every page); "send" for a chair or the admin: sent at, sent by, the PDF into the letter's file unless a signed file is there, the submission and the participation to "responded", the institution's leaders told and mailed with the link; `/academia360/letters/<pk>/`: the letter as a page for the committee always and for the institution's leaders once sent, with an access log row; `/letters/<pk>/pdf/` on the fly under the same rule | a member cannot send; sending stamps, files a PDF that opens, moves the statuses, notifies and mails the leaders; before sending the leader gets "no access" and after it reads the page; a leader of another institution is refused; the PDF holds the addressee and the sections; an uploaded signed file is kept | built in dev 2026-11-27; `academia360/letter_pdf.py` (compose first, draw second; Heebo + python-bidi; the pilot line and the page number on every page), `letters.send`, `letter_pages.page` and `.pdf`, `templates/academia360/letter.html`; `/letters/<pk>/` and `/letters/<pk>/pdf/` follow `access.can_see` (the sent letter opens to the institution through `INSTITUTION_Q`); `tests/test_academia360_e5.py`, 4 tests |
| E.6 The epic's end | The screen contract for every new screen at six widths (a member, a chair, a leader), the whole app suite, `manage.py check`, the security sweep for what E added (posts as markdown, the mention list, the mail bodies, the redirect after "go", the PDF route), bkm_drift, the post-mortem, the review with Avi | the whole suite green | done 2026-11-27 morning: the app suite green (162 collected by `tests/test_academia360_*`, 27 new in E plus one for the child-process readers), the screen contract green at six widths with ten new screens (findings fixed on the way: the bell and the account on one line at 320px, a bell never under 40px, an 18px link out of a heading, two classes the sweep caught), check clean, sweep done (markdown through nh3, mentions validated against the member list, `next` and the bell's redirect through `url_has_allowed_host_and_scheme`, the PDF route behind `can_see` with an access-log row, Notification creation admin-only through the API), drift as before plus the new headings, PM-107 (train requirements), PM-108 (the 502 on extraction, readers in a child), PM-109 (epic end) all landed in FullStackBKM; dev screenshots at 320/412/1280 read; Avi 2026-11-27 10:20: "Push"; the first train (T1127-102056) failed on the bell test, newest-first with two rows in one clock tick (PM-111, mistake 86, BKM 8f511d9; Notification orders by `-created_at, -pk`, migration 0007); shipped by T1127-103925 (7958e06, deploy success, live 10:55 after a second deploy of the same commit from breakout's render.yaml line); production extraction then run by the agent script two files at a time: 81 files, 66 with text, 14 scans without a text layer, one .ods unsupported, no 502 |

## Epics F to J

Written as sprints when their turn comes; their scope is spec chapter 4 and
the order is spec chapter 6.

## Epic P. The institution page, read like a book; the reference in full

Avi, 2026-11-27 noon, after seeing the live page: "when I go into an
institute I want it to be very very clear to read." The order he gave, top
to bottom: the name on the right and the status on the left, the status
for committee members only; one big paragraph (where it is, what it
teaches, what its research is known for); public material that matches
what Academia 360 cares about (graduate image, vision, special programs),
clean, with links; the main professions with student numbers per domain;
research that stands out (prizes, leading researchers) that opens to rich
pages; compare out of the front, into a menu. Two content rules: first,
everything his October 2025 research holds finds its place on the site;
second, nothing is added for an institution we have no material for: it
stays an honest placeholder, and a management list says which institutions
are empty, so that two later jobs (recheck the existing, fill the empty)
have a list to work from. Fresh deep research per institution is a
separate job (Epic I), by me or by someone else.

What the check found before planning (2026-11-27): 24 of 36 institutions
have research pages in the reference (an overview page and a researchers
page each; 5 also have a structured file); 12 have nothing (the music
academy, Achva, Western Galilee, Hadassah, College of Management, Carmel,
Oranim, Kaye, Orot, Gordon, David Yellin, the Hebrew University). The first
import kept researcher names, areas and links and lost focus, h-index,
citations, publications and distinctions (0 of 219 researchers have a
metric in production); the overview pages became 147 short sections, 103 of
them "other"; the timeline matched nothing; one institution has an identity
paragraph. The pages do not share one markup (each was generated on its
own), so the second reading goes by meaning, not by class names.

Decisions taken while planning (to raise at the review):

- The status card shows participation, letter and next step to committee
  members and the admin; the public sees no status at all, not even "took
  part" (Avi: "any other random user just sees public information").
- The one paragraph is written by a model from the institution's own
  reference overview page and nothing else, marked with that source and
  date; an institution without a page gets no paragraph. It is the only
  model call in this epic, one per institution, once.
- New tables: Distinction (a prize or honour, of a researcher or of the
  institution), UnitEnrollment (students per faculty or school, with the
  share), and PublicDocument grows a kind, a summary and the criteria it
  speaks to. Institution grows a tagline and a research status (none /
  imported / rechecked, with a date and a note) for the coverage list.
- Numbers stay in sentences and rows, never tiles (spec 5).
- Pass-1 rows reach production by replication of the public-knowledge
  models only (a `--models` option), after the code ships.
- Found on the way (PM-113): the first import had read the pages by class
  names and kept little; the second reading goes by meaning, with a tag
  walk, and fills only what is empty, so it ran over the first without
  harm. Beit Berl's people page lists research areas, not people, so it
  is the one "partial" institution; 44 area headings the first import had
  taken for researchers are turned off (verified=False), not deleted.
- Researcher gets a `position` field (migration 0009). Publications keep
  their venue and year; a year already inside the venue is not repeated.

| Sprint | Content | Tests written first | Status |
| --- | --- | --- | --- |
| P.1 Data model | Distinction, UnitEnrollment, PublicDocument's kind / summary / criteria / source / verified, Institution.tagline + research_status / research_as_of / research_note, new ProfileSection kinds; migration; API routes and write policy; data_model.md §3 | the API lists and writes the new rows under the same rules as their neighbours |done 2026-11-27 noon: migrations 0008 and 0009 (Researcher.position), 3 tests |
| P.2 The second reading | `import_reference` reads the people pages by meaning (a card is a heading with a title; unit, focus, h-index and citations with ~, bio, publications, links incl. homepage, prizes) and the overview pages (tagline, hero facts as metrics, students per faculty, timeline, section kinds, prize sections); fills only what is empty; `--identity` writes the one paragraph from the page's text through the model | two small pages in two vocabularies parse to the same rows; a second run changes nothing; a filled field is never overwritten; the real folder, when present, yields at least the counts we measured |done 2026-11-27 afternoon: `reference_pages.py` (a tag walk, not a regex; a label is words only; a prize is a badge-like line), `reread.py`, `reread_reference` command; landed in dev: 116 new researchers (291 verified, 44 area headings turned off), 306 publications, 214 metrics, 107 timeline rows, 45 faculty splits, 18 distinctions, 19 taglines, 23 paragraphs for $0.01 (gpt-4o-mini); second run: 0 changes; 6 tests |
| P.3 The page | Avi's order; status for the committee only; one paragraph; "what matters to Academia 360" from PublicDocument (hidden when empty); what they teach and how many (units with their share and count); research that stands out (distinctions, researcher cards); the story folded under "read more"; compare at the bottom and on the list page; an honest line when the institution has no material yet | the public sees no status and a member does; sections hide when empty; the compare link is not in the hero; no stat tiles; the b3/a4 assertions updated |done 2026-11-27 afternoon: `institution.html` rewritten in Avi's order, `<details>` folds for the story, compare in a tools line at the bottom; a4 test turned around; 4 tests |
| P.4 The researcher page | Focus and bio, metrics with dates, publications, distinctions, links, colleagues; a page with nothing says so | a rich page shows all of it; an empty one says what is missing |done 2026-11-27 afternoon: `researcher.html` rewritten; publications and prizes section; 1 test (in p3) |
| P.5 Coverage | `/academia360/manage/coverage/`: a row per institution with what it has (paragraph, sections, researchers, with metrics, publications, split, timeline, documents, distinctions), a state (empty / partial / rich), the research status editable in place, filters; the same through the API for the chat | the list counts right; the admin only; setting a status is logged |done 2026-11-27 afternoon: `coverage.py` (page, set, API view), `manage/coverage.html`; dev: 12 empty, 1 partial (Beit Berl: an areas page, no people), 23 rich; 3 tests |
| P.6 Epic end | `replicate_to --models`; the screen contract for the new screens at six widths; suite, check, sweep, drift, post-mortem; the review with Avi; after his push: replicate the pass-1 rows to production | | done 2026-11-27 evening: `--models` with its test; screen contract green at six widths with four new screens (findings fixed on the way: a document title link too short to tap, the institution tag on the researcher page as a short link, the coverage table past the phone's edge, now a stack of labelled cards under 700px, two dynamic class names); class sweep clean; check clean; drift as before; PM-113 (BKM d03590c, mistake 99); dev screenshots at 390/1280 read; Avi 2026-11-27 18:20: "Ok..push"; carried by the breakout chat's train T1127-181834 (bc3f738, live 18:42 after the second deploy of the same commit); then `replicate_to --models` of the 15 public-knowledge tables, 1,676 rows: production went from 1 rich / 23 partial / 12 empty to 23 rich / 1 partial / 12 empty, 291 researchers, 306 publications, 45 splits, 24 paragraphs; live pages checked |
