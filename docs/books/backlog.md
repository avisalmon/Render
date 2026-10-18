# Books: Backlog

Standing rules: dev first, deploy only on Avi's word. Process is
[building_an_app.md](../building_an_app.md) with
[the_manager.md](../the_manager.md)'s sprint workflow, scaled to Books: this
is the central app of the project, so it keeps the fuller process (screen
contract, refusal tests, screenshots) rather than the light one used for
five-person apps. [spec.md](spec.md) and this file are the two status sources
of truth and move together. The data is [data_model.md](data_model.md).

**IDs and markers.** Epics `BK1` to `BK13` (spec Part B). Sprints
`SPR-BK<epic>.<n>`, features `F-BK<epic>.<n>.<m>`, Avi's actions `ACT-BK.<n>`.
Each sprint's tests live in `tests/test_books_<epic>_<n>.py` with the pytest
marker `sprbk<epic>_<n>`, registered in `pyproject.toml` in that sprint.
Books' screen contract lives in `tests/test_books_screens.py` (marker
`booksscreens`): every screen, by state, at 390 px and 1280 px, light and
dark.

**Gates.** Every push: `pytest -m "smoke or sprbk<epic>_<n>" -q`, plus
`pytest -m booksscreens -k "<entries touched>"` when a template or the
stylesheet changed. Full regression only on Avi's word. Every new screen is
looked at as a screenshot at least once (methodology entry 6).

**Status values:** `TODO`, `WIP`, `DONE (dev)`, `DONE, DEPLOYED <date>`.

**Gate status, 2026-10-18:** intro spec reviewed; data model approved; design
gate closed (spec BK1 §1.1c); full spec approved ("cont"); **this backlog
waits for Avi's approval before any code.**

---

## Avi's actions (outside the code)

| ID | Action | Needed before | Status |
| --- | --- | --- | --- |
| ACT-BK.1 | Ask AnyBook's founders why the consumer app gave way to B2B kiosks (spec 12.15) | BK6 launch | TODO |
| ACT-BK.2 | An Israeli lawyer reads the privacy page, the terms, reading-log privacy (Amendment 13) and the no-money-flow rule | BK6 launch | TODO |
| ACT-BK.3 | Photograph 10 or more real shelves (Hebrew, English, mixed) and label them, for the accuracy gate | SPR-BK3.4 | TODO |
| ACT-BK.4 | Choose the first circle (a book club, school, workplace or neighbourhood) and its first members | BK6 | TODO |
| ACT-BK.5 | Read the Google Books terms against the paid tier (spec 12.11) | BK11 | TODO |
| ACT-BK.6 | Create the Google Cloud Storage bucket for Books (private, Europe or Israel region) and a service account limited to that one bucket; put its key in Render's environment, never in git. I can write the exact steps | SPR-BK1.5 (dev can use local disk until then) | TODO |

---

## Epic BK1: Design, graphics and infrastructure

Goal and done-when: spec Part B, BK1. Built in this order so that a real,
finished-looking empty Books exists after the first two sprints.

### SPR-BK1.1: The skeleton and the seal `DONE (dev), 2026-10-18, awaiting review`

**Goal:** `/books/` exists, sealed from babook in both directions, with its own
base template in the approved bright palette, its own sign-in, onboarding that
creates a Profile, and the API scaffold with its refusal tests. An empty
library at the end.

| ID | Feature | Traces | Status |
| --- | --- | --- | --- |
| F-BK1.1.1 | Django app `books` in `INSTALLED_APPS`, mounted at `/books/` before the catch-all, namespace `books`, own migration chain from `0001` | Rules 2, 5 | DONE |
| F-BK1.1.2 | Own 403/404/500 in Books' look, composed into `mysite/errors.py` by prefix | spec BK1 §1.5 | DONE |
| F-BK1.1.3 | Base template: `--bk-*` tokens from spec §1.1c (light default, dark under a `data-theme` switch), David Libre + Heebo, header and menu, no babook chrome, no link out | Rule 3, §1.1c | DONE |
| F-BK1.1.4 | Sign in, sign up, sign out, password reset in Books' look on the shared `User`; Google sign-in first | §1.5 | DONE |
| F-BK1.1.5 | `Profile` model (data model §4), created at onboarding: display name, language, 18+ confirmation, terms accepted, area (stored **rounded**, never an address) | data model §4, spec 12.9 | DONE |
| F-BK1.1.6 | DRF scaffold under `/books/api/`: router, owner-scoped permission base, `profile` endpoint; browsable for staff | Rule 6 | DONE |
| F-BK1.1.7 | Refusal tests: anonymous refused everywhere; another person's profile is 404; unrounded coordinates are rounded on save; no route answers for a person without a Profile except onboarding | §1.7 | DONE |
| F-BK1.1.8 | The empty library screen (an empty shelf under the lamp, "photograph your first shelf") | design board | DONE |
| F-BK1.1.9 | The seal in `tests/test_smoke.py`: Books' pages serve 200; no `/books` link from babook; no babook chrome or link inside Books | Rule 3 | DONE |
| F-BK1.1.10 | `docs/books/dashboard.html`, Books' own progress view | Rule 4 | DONE |

**Sprint notes (2026-10-18).**

- 30 tests in `tests/test_books_1_1.py` (marker `sprbk1_1`), refusals first; the
  smoke gate gains Books' front doors and its seal. All green. The two smoke
  failures in the same run are matazim's (`--mz-action-text`, a stale matazim
  dashboard), from another session's uncommitted work, present before this
  sprint.
- A test caught a real gap on the first run: Django's sign-in follows any
  same-site `next`, so `/books/login/?next=/admin/` left Books. Sign-in now only
  follows a `next` inside `/books/`.
- Screenshots at 390 and 1280 looked at: sign-in, onboarding, the empty
  library. One fix from looking: letter-spacing on Hebrew text pulls the
  letters apart, so the kicker style has none (the design boards used it;
  it does not work in Hebrew).
- The profile API is full CRUD scoped to the caller, except create, which is
  onboarding's job (it records age and terms); tier, age and terms are
  read-only. A precise point sent to it is stored rounded.
- Not deployed. The dev database has migration `books.0001`.

### SPR-BK1.2: The design system and the shelf `TODO`

**Goal:** every shared component exists once, in both themes, and the home
shelf (lamp, spines from data, swipe along, tap to lift, the museum label) works
on sample data exactly as on the approved board.

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.2.1 | Components: buttons, fields, chips (the five choices), cards, sheet, dialog, toast, empty states, the cover tile, the spine. Every class `bk-`-namespaced | TODO |
| F-BK1.2.2 | The shelf component: spines drawn from data (colour, height, width, title, author), leaning and slight tilt, swipe along, tap to lift and light, label below, keyboard reachable | TODO |
| F-BK1.2.3 | One icon family, inline SVG, labelled or hidden from screen readers | TODO |
| F-BK1.2.4 | Motion: lift, settle, slide-in on accept; respects reduced-motion | TODO |
| F-BK1.2.5 | Guard tests: every class used is defined (entry 13); no colour outside the tokens; contrast AA measured in both themes | TODO |
| F-BK1.2.6 | Screen contract entries for home (empty, with books, a book lifted) at 390 and 1280, light and dark; screenshots looked at | TODO |

### SPR-BK1.3: Two languages, two directions `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.3.1 | One string catalogue, Hebrew and English, inside the app; language from Profile, else the browser; a switch in the header | TODO |
| F-BK1.3.2 | Right-to-left and left-to-right mirroring, including pointing icons; book titles keep their own direction whatever the interface | TODO |
| F-BK1.3.3 | Guard test: no hard-coded interface string in Books' templates | TODO |

### SPR-BK1.4: Every screen size, installable, accessible `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.4.1 | The approved desktop layout: side menu with rooms, two shelves per room, side panel | TODO |
| F-BK1.4.2 | Tablet layout between the two | TODO |
| F-BK1.4.3 | Web manifest and icons, installable to the home screen | TODO |
| F-BK1.4.4 | Accessibility pass: screen-reader labels, keyboard, focus, 44 px targets, no meaning by colour alone; checked in the screen contract | TODO |

### SPR-BK1.5: Storage, jobs, cost, privacy plumbing `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.5.1 | Images to Books' own private Google Cloud Storage bucket (needs ACT-BK.6); resized copies; covers public, personal photos through short-lived signed links only | TODO |
| F-BK1.5.1b | Photo location as a bonus: read EXIF GPS once on upload, keep it only rounded to a neighbourhood (suggest the area, tell which home a shelf is in), then strip the precise point from the stored image | TODO |
| F-BK1.5.2 | A background job runner for recognition (no request ever waits on a model) | TODO |
| F-BK1.5.3 | Every model call recorded with its cost. **Needs a small data model addition** (a cost record per call), to be shown to Avi before it is built | TODO |
| F-BK1.5.4 | Download everything Books holds about me; delete my Books data | TODO |
| F-BK1.5.5 | Privacy and terms pages in both languages, marked draft until ACT-BK.2 | TODO |

### SPR-BK1.6: Appearance settings `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.6.1 | Settings › Appearance: light (default), dark, follow the device | TODO |
| F-BK1.6.2 | The other themes as token sets: Warm library, Bright and playful, Collector's den | TODO |

### SPR-BK1.7: Other shelf views `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.7.1 | Bookcase view (two shelves, tap to pull out) | TODO |
| F-BK1.7.2 | Living shelf view (drag to rearrange, tap to pull) | TODO |

SPR-BK1.6 and BK1.7 can move after BK3 if Avi prefers to reach scanning
sooner; they do not block anything.

---

## Epic BK2: The book catalogue (outline)

Sprints are written in full when BK1 is done.

- **SPR-BK2.1** CatalogEntry, Creator (with aliases), Tag, EntryIdentifier,
  BookDetail; admin; API with refusal tests; the tag list seeded once.
- **SPR-BK2.2** Sources: Open Library, National Library of Israel, Google
  Books, each copied into our records with its source; caching and limits;
  covers into storage.
- **SPR-BK2.3** Matching (identifier, then title, creator and publisher;
  danacode) and search in both languages, tolerant of spelling and vowel marks.
- **SPR-BK2.4** Curation: verify, merge duplicates, accept corrections.

## Epic BK3: Shelf scan and confirmation (outline)

- **SPR-BK3.1** ShelfScan, ScanItem, ScanCandidate; capture from the phone
  camera and upload on desktop; the shelf label.
- **SPR-BK3.2** The recognition job on the `bookshelf-recognition` pipeline,
  candidates from BK2, confidence, cost per scan.
- **SPR-BK3.3** The confirmation flow from the approved board: lowest
  confidence first, one tap to accept, alternatives, manual search, skip, bulk
  accept, Copy and Offer created on accept, location prefilled, the 1,000 cap.
- **SPR-BK3.4** **The accuracy gate** on ACT-BK.3's shelves, the number
  written into the spec.

## Epic BK4: My library (outline)

- **SPR-BK4.1** Copy page, edit, delete, move in bulk, photos, rooms and
  shelves on the home shelf.
- **SPR-BK4.2** Browse and search my books, wishlist, scan history, export.

## Epic BK5: The hub (outline)

- **SPR-BK5.1** Browse near me and the free-tier view; Deal requests and
  Messages; Block and Report.
- **SPR-BK5.2** Handover, loans, due dates, reminders, returns, exchange,
  transfers with CopyTransfer, the lost and dispute rules.
- **SPR-BK5.3** Reputation counts, wishlist alerts, notifications, meeting
  places.

## Epic BK6: Circles and the first launch (outline)

- **SPR-BK6.1** Circle and CircleMember, invites, a circle's books.
- **SPR-BK6.2** Pilot tools and dashboard for Avi, in-app feedback; launch
  checklist (ACT-BK.1, ACT-BK.2, ACT-BK.4 done).

## Epics BK7 to BK13

Not broken into sprints yet: community, play, discovery, rare books and the
museum, tiers and billing, advanced creation, other collections. Each gets its
sprints when the pilot (BK1 to BK6) is live and Avi has seen it used.
