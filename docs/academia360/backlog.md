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
| **A. Foundation and the public front door** | The app, the data, the API, the agent's door, the import, and the public home and institution pages live on babook.co.il | planned |
| B. The rest of the public site | Map and list, researchers, programs by field, compare, comments and corrections | planned |
| C. People | Sign-in in the app's look, requests to join, approval queue, roles, admin overview | planned |
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
| D.3 | **Round 2, one direction built deep:** the public **home page** (the program at a glance, the criteria, the participating institutions, how to find your way) and the public **institution page**, at computer and phone width, real content, no stat tiles, no people illustrations, the 360 motif as the shape language. Avi judges | in progress |
| D.4 | Rules that survive the mockup written into spec chapter 5 (tokens, type, radii, shapes, how numbers are shown, the committee room's restraint, RTL rules, the banner). Leader home and committee dashboard drawn in the same family | planned |

## Epic A. Foundation and the public front door

Ends with: `https://babook.co.il/academia360/` showing the program home and
32 institution pages from real data, and Avi reading and writing that data
from this chat.

| Sprint | Content | Tests written first | Status |
| --- | --- | --- | --- |
| A.1 Skeleton and circles | Django app `academia360`; claim and edit the shared files through `train.py claim` (settings, urls); own base template with the pilot banner; own 403/404/500 composed into the project's handlers; the permission layer (`public` / `institution` / `committee` circles, roles and attributes from data model §1); models of §1 to §3 (people, program, institution as public knowledge); migrations; DRF viewsets with full CRUD for them, documented schema; portal registry entry; `conftest.py` that blanks the real OpenAI key from the first test | banner on every page; each circle wall crossed and refused; a leader of A cannot read a row of B through the API; anonymous reads public rows only; registry sweep (`tests/test_spr_13_1.py`) | planned |
| A.2 Program side and the import | Models of §4 to §10 (participation, submissions, files in private storage, KPIs, budget, review, discussion, decision, letters, public talk-back, AI, audit); their API; `import_reference` one-time command over the reference folder: institutions, participations, submissions and files, contacts, analyses, structured institution data, researchers, KPI and budget sheets, allocations, the review form, the letters | the import runs twice and the second run changes nothing; a row edited in the app survives a re-run; the real reference folder is read, not a fixture; private files are not reachable under the public media URL | planned |
| A.3 The agent's door | `ACADEMIA360_AGENT_TOKEN` (fails shut, constant-time), token acts as admin inside the app only; the narrow role endpoint (grant / revoke for an existing account, never create, never escalate); `ChangeLog.actor_kind`, `AgentRun`; `scripts/a360.py` CLI against dev and prod | refusals first, two to one: unset token, wrong token, token on a `User` write, grant to a missing account, escalation fields ignored; every token write lands in ChangeLog as `agent` | planned |
| A.4 The public front door (after D.3 approved) | The home page: what the program is, the five criteria, the mandatory KPIs, the timeline, the participating institutions, the way in for each kind of person, the pilot banner; the institution page from real rows (identity, units, programs, numbers with source and date, researchers, centers, timeline); plain search; "no access" page in the same look | screen contract at 320/360/375/390/412 and computer width; every class used is defined; no stat-tile pattern (a test that no element shows a bare number over 28px without a sentence next to it, written once the design rules exist); `dir="auto"` on typed text; every number on the institution page has a source | planned |
| A.5 Ship | Full app tests, `manage.py check`, screenshots at three widths read against the seed, security sweep items for what A created (`|safe`, private files, token compare, caps n/a yet); `train.py ship --app academia360`; verify live by a string only the new code has; Avi reads prod from the chat with `a360` | the live check itself | planned |

Open points carried into A (answered as reached): data model §12 (1 to 6);
the admin overview's content (spec 2.6.7); official app or own product for
the "more on babook" menu.

## Epics B to J

Written as sprints when their turn comes; their scope is spec chapter 4 and
the order is spec chapter 6.
