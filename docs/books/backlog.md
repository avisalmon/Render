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

**Gate status, 2026-10-18:** every kickoff gate closed; backlog approved;
BK1 and BK2 built and pushed the same day (autonomous run on Avi's mandate).
**Avi acked every decision of BK1 and BK2 on 2026-10-18**, kept Books open to
anyone who reaches it (no allow-list), and said start BK3.

---

## Avi's actions (outside the code)

| ID | Action | Needed before | Status |
| --- | --- | --- | --- |
| ACT-BK.1 | Ask AnyBook's founders why the consumer app gave way to B2B kiosks (spec 12.15) | BK6 launch | TODO |
| ACT-BK.2 | An Israeli lawyer reads the privacy page, the terms, reading-log privacy (Amendment 13) and the no-money-flow rule | BK6 launch | TODO |
| ACT-BK.3 | Photograph 10 or more real shelves (Hebrew, English, mixed) and label them, for the accuracy gate | SPR-BK3.4 | TODO |
| ACT-BK.4 | Choose the first circle (a book club, school, workplace or neighbourhood) and its first members | BK6 | TODO |
| ACT-BK.5 | Read the Google Books terms against the paid tier (spec 12.11) | BK11 | TODO |
| ACT-BK.6 | Create the Google Cloud Storage bucket for Books (private, Europe or Israel region) and a service account limited to that one bucket; put its key in Render's environment (`BOOKS_GCS_BUCKET`, `BOOKS_GCS_CREDENTIALS_JSON`), never in git. I can write the exact steps | images in prod (disk fallback until then) | TODO |
| ACT-BK.7 | Request a National Library of Israel API key and set `BOOKS_NLI_API_KEY` in Render; until then Hebrew look-ups rely on Open Library and Google Books | BK3 accuracy gate | TODO |
| ACT-BK.8 | Optionally a Google Books API key (`BOOKS_GOOGLE_BOOKS_KEY`) for a higher quota | BK3 | TODO |

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

### SPR-BK1.2: The design system and the shelf `DONE (dev), 2026-10-18`

**Goal:** every shared component exists once, in both themes, and the home
shelf (lamp, spines from data, swipe along, tap to lift, the museum label) works
on sample data exactly as on the approved board.

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.2.1 | Components: buttons, fields, chips (the five choices), cards, sheet, dialog, toast, empty states, the cover tile, the spine. Every class `bk-`-namespaced | DONE |
| F-BK1.2.2 | The shelf component: spines drawn from data (colour, height, width, title, author), leaning and slight tilt, swipe along, tap to lift and light, label below, keyboard reachable | DONE |
| F-BK1.2.3 | One icon family, inline SVG, labelled or hidden from screen readers | DONE |
| F-BK1.2.4 | Motion: lift, settle, slide-in on accept; respects reduced-motion | DONE |
| F-BK1.2.5 | Guard tests: every class used is defined (entry 13); no colour outside the tokens; contrast AA measured in both themes | DONE |
| F-BK1.2.6 | Screen contract entries for home (empty, with books, a book lifted) at 390 and 1280, light and dark; screenshots looked at | DONE |

**Sprint notes.** Tokens for light, dark and the three other palettes in one
stylesheet; every class `bk-` namespaced; the shelf (`static/books/shelf.js`)
draws spines from JSON (colour, width, height, lean, title, author), swipes by
native scrolling, lifts on tap with the label below, walks by arrow keys. A
staff-only `/books/design/` page shows every component and all three shelf
views on sample books (linked from nowhere). Guards: every class used is
defined, no colour outside the token blocks, no hex in templates. Screen
contract `tests/test_books_screens.py` (marker `booksscreens`): 10 screens x
light/dark x 390/1280, contrast measured, overflow, 44 px targets, labels,
plus the lift, the keyboard, the English direction and the drag. Looked at as
images in both themes and widths. One fix from looking: letter-spacing is off
on Hebrew.

### SPR-BK1.3: Two languages, two directions `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.3.1 | One string catalogue, Hebrew and English, inside the app; language from Profile, else the browser; a switch in the header | DONE |
| F-BK1.3.2 | Right-to-left and left-to-right mirroring, including pointing icons; book titles keep their own direction whatever the interface | DONE |
| F-BK1.3.3 | Guard test: no hard-coded interface string in Books' templates | DONE |

**Sprint notes.** `books/strings.py` is the one catalogue (he and en for every
key, a test fails on a missing half); `{% t %}` in templates, `t()` in forms;
`books/middleware.py` decides the language (Profile, then session, then the
browser, then Hebrew), the direction, the theme, and runs the request under
`translation.override` so Django's own messages follow and nothing leaks to
the next request. A header switch saves on the Profile or in the session.
Guard: no Hebrew and no English copy hard-coded in any template. Decision: not
gettext, for the reason exo and sensorlab recorded (no msgfmt here or on
Render).

### SPR-BK1.4: Every screen size, installable, accessible `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.4.1 | The approved desktop layout: side menu with rooms, two shelves per room, side panel | DONE |
| F-BK1.4.2 | Tablet layout between the two | DONE |
| F-BK1.4.3 | Web manifest and icons, installable to the home screen | DONE |
| F-BK1.4.4 | Accessibility pass: screen-reader labels, keyboard, focus, 44 px targets, no meaning by colour alone; checked in the screen contract | DONE |

**Sprint notes.** Desktop from 900 px: side menu, wider shelf, a two-column
home with an aside; a tablet step at 700 px. Web manifest, SVG favicon and PNG
icons drawn by `books/design_assets/make_icons.py` (a lamp over a shelf).
Accessibility checked in the contract: every image has alt, every control a
name, every field a label, a skip link, `lang` and `dir` on the page, focus
visible, reduced motion respected.

### SPR-BK1.5: Storage, jobs, cost, privacy plumbing `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.5.1 | Images to Books' own private Google Cloud Storage bucket (needs ACT-BK.6); resized copies; covers public, personal photos through short-lived signed links only | DONE |
| F-BK1.5.1b | Photo location as a bonus: read EXIF GPS once on upload, keep it only rounded to a neighbourhood (suggest the area, tell which home a shelf is in), then strip the precise point from the stored image | DONE |
| F-BK1.5.2 | A background job runner for recognition (no request ever waits on a model) | DONE |
| F-BK1.5.3 | Every model call recorded with its cost. **Needs a small data model addition** (a cost record per call), to be shown to Avi before it is built | DONE |
| F-BK1.5.4 | Download everything Books holds about me; delete my Books data | DONE |
| F-BK1.5.5 | Privacy and terms pages in both languages, marked draft until ACT-BK.2 | DONE |

**Sprint notes.** `books/storage.py`: Books' own private GCS bucket through
django-storages (signed links, 10 minutes) when `BOOKS_GCS_BUCKET` is set,
else `media/books/`; `books/images.py`: reads GPS once, keeps it rounded to
two decimals, re-encodes as a clean JPEG with no metadata (tested with a real
EXIF GPS block); `books/jobs.py` + `Job` + `ModelCall` (data model section
11); `/books/internal/run-jobs/` behind a token that fails shut, plus
`books_run_jobs`; My data: a JSON export that walks every owned model, and a
typed-word delete that removes Books' data and keeps the account. Terms and
privacy pages are drafts in both languages. ACT-BK.6 (the bucket) still open;
dev and prod run on the disk fallback until then, and prod logs it.

### SPR-BK1.6: Appearance settings `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.6.1 | Settings › Appearance: light (default), dark, follow the device | DONE |
| F-BK1.6.2 | The other themes as token sets: Warm library, Bright and playful, Collector's den | DONE |

**Sprint notes.** Settings page: name, language, area, radius, theme (light /
dark / follow the device), style (lamp-lit / warm library / bright and playful
/ collector's den), shelf view, two privacy toggles. Palettes are token sets;
warm and bright bring their own type. Defaults are Avi's.

### SPR-BK1.7: Other shelf views `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK1.7.1 | Bookcase view (two shelves, tap to pull out) | DONE |
| F-BK1.7.2 | Living shelf view (drag to rearrange, tap to pull) | DONE |

**Sprint notes.** Bookcase (two shelves in a wooden case with brass plates,
tap pulls out) and living shelf (pointer drag to rearrange, the others make
room, order event emitted) live in the same `shelf.js`, chosen by
`data-shelf-view`. Persisting a dragged order waits for Copy (BK3).

SPR-BK1.6 and BK1.7 can move after BK3 if Avi prefers to reach scanning
sooner; they do not block anything.

---

## Epic BK2: The book catalogue `DONE (dev), 2026-10-18`

Goal and done-when: spec Part B, BK2. Built in the autonomous run; decisions
listed in data_model.md section 11 and in the sprint notes for Avi's ack.

### SPR-BK2.1: Models, seed, API `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK2.1.1 | CollectionType, Creator (+ CreatorAlias), Tag, CatalogEntry (editions under a parent), EntryCreator, EntryIdentifier, BookDetail, EntryCorrection; migration 0004 | DONE |
| F-BK2.1.2 | `seed_books`: the `book` type and 54 tags (genre, audience, mood, form) from `books/seed_assets/tags.json`, one-time, never overwrites; wired into render.yaml | DONE |
| F-BK2.1.3 | DRF: catalog, creators, creator-aliases, tags, identifiers, book-details, corrections; search / verify / merge / suggest actions | DONE |
| F-BK2.1.4 | Refusal tests: anonymous and un-onboarded get nothing; a reader may add an unverified record and edit it until verified; nobody sets verified, owner or source; delete, verify and merge are a curator's; tags and creators read-only for readers | DONE |

### SPR-BK2.2: Sources `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK2.2.1 | Adapters: Open Library (no key, contact User-Agent, 0.4 s interval), Google Books (optional key), National Library of Israel (needs `BOOKS_NLI_API_KEY`, skipped without; reads danacodes) | DONE |
| F-BK2.2.2 | `lookup()` across enabled sources, cached a day, a failing source skipped and logged | DONE |
| F-BK2.2.3 | `upsert_from_record`: identifier match, then exact normalised title + creator; fills blanks on an existing entry; importing twice changes nothing | DONE |
| F-BK2.2.4 | Covers copied into Books' storage by a background job; Open Library's 1x1 placeholder ignored | DONE |

### SPR-BK2.3: Matching and search `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK2.3.1 | `textnorm`: vowel marks, final letters, quotes, articles, ISBN-10/13 validation and folding, danacode, similarity | DONE |
| F-BK2.3.2 | `search_local`: a typed ISBN or danacode goes straight to the record; else every token must appear, ranked by similarity; merged entries never return | DONE |
| F-BK2.3.3 | `/books/catalog/`: search, genre chips, "look in the big libraries too" (copies the results in), "add a book by hand" | DONE |
| F-BK2.3.4 | `/books/catalog/new/` and `/edit/`: title, subtitle, creators, language, year, publisher, ISBN or danacode (validated), genres | DONE |
| F-BK2.3.5 | `/books/catalog/<id>/`: cover, creators, facts, identifiers, editions, tags, a correction form; merged records redirect to their winner | DONE |

### SPR-BK2.4: Curation `DONE (dev), 2026-10-18`

| ID | Feature | Status |
| --- | --- | --- |
| F-BK2.4.1 | Verify; merge (identifiers, creators, tags, editions, corrections and blanks move to the winner, the loser points at it so old links resolve); duplicate suspects by normalised title and a shared creator | DONE |
| F-BK2.4.2 | Corrections: a reader suggests (page form or API), sees only their own; a curator accepts (the record changes) or declines | DONE |
| F-BK2.4.3 | `/books/curate/` (staff, 404 for others): unverified queue, suspects with one-click merge, open corrections | DONE |

**Epic notes (2026-10-18).** 62 tests in `tests/test_books_2_*.py` plus seven
catalogue screens in the contract, both themes and widths. Decisions for
Avi's ack: (1) anyone onboarded may add a record, unverified, and edit it
until a curator verifies it; (2) a mistyped 13-digit ISBN is refused rather
than kept as a danacode; (3) sources are not deduped at look-up, the merge
happens on import so the second source fills the first's blanks; (4) the NLI
adapter waits for a key, ACT-BK.7; (5) `EntryCorrection`, `merged_into`,
`search_text` and `CreatorAlias` are additions to the approved model. Known
polish: the language shows as its code on a record page; the genre list on
the add-by-hand form is long on a phone.

## Epic BK3: Shelf scan and confirmation `DONE (dev), 2026-10-19`

Built in one run after Avi acked BK1 and BK2 and said start BK3, with his
answers: use the site's OpenAI key (every call recorded with its cost); the
accuracy labels come through the app (his corrections in real scans are the
labels); bucket steps sent to his email.

| ID | Feature | Status |
| --- | --- | --- |
| F-BK3.1 | ShelfScan, ScanItem, ScanCandidate, Copy, Offer (migration 0005); capture page: phone camera or upload, photo tips, shelf label, default choices for the scan | DONE |
| F-BK3.2 | `books/recognition.py`: the skill's measured method ported (gpt-6.1-sol, effort low, detail high, 2 strips 15% overlap, strict schema, edge-only merge), key from settings, a 401 stops the job, each strip call a ModelCall with cost | DONE |
| F-BK3.3 | The `scan.read` job: reads, records, then candidates per book (local catalogue, then the sources when nothing local is strong, top 3 with confidence); the page polls and turns into the confirmation list | DONE |
| F-BK3.4 | Confirmation: lowest confidence first, the photo's reading beside up to three candidates, "keep it as read" with editable title and author, the five choices in the same card, location prefilled, skip, "confirm all sure ones", add a book the photo missed; nothing becomes a Copy without an accept; offers imply public; the free cap of 1,000 held books | DONE |
| F-BK3.5 | Photo privacy: stored with no metadata, served only to its owner through `/books/scan/<id>/photo.jpg` (never /media/); GPS used once, rounded, to fill an empty area | DONE |
| F-BK3.6 | The home shelf draws the person's copies (colour, width, height and lean stable per book, from the board's palette); the living shelf's drag is saved | DONE |
| F-BK3.7 | API: scans (upload), scan-items (accept, skip), copies, offers, all scoped to the caller; going private withdraws every offer | DONE |
| F-BK3.8 | **The accuracy gate**: `manage.py books_measure` over labelled shelves, and `--app` for the share confirmed without retyping in real scans | DONE, measured below |

**The accuracy gate, measured 2026-10-19** on the four labelled shelves the
skill was built on (70 books, mostly Hebrew): at 2000 px, 61/70 found (87%), 5
extra; at 4000 px, **63/70 found (90%), 3 extra, about $0.024 a shelf, 23 to
45 s**. Books therefore reads and stores scans at up to 4000 px. The 90%
target is met on this set. The in-app number (confirmed without retyping)
starts counting with Avi's first real scans (ACT-BK.3, now done through the
app).

**What a real end-to-end run in dev showed** (one of Avi's BookEngine shelves,
17 books, $0.027, 35 s): every title read correctly, but only the two English
books found a catalogue match. Hebrew books have no free source here: Open
Library rarely has them and Google Books answered 429 without a key. They go
through "keep it as read", which creates an unverified record from the spine
reading; the next person with the same book matches it. The National Library
key (ACT-BK.7) is what turns Hebrew matches on. Two bugs found by that run and
fixed: a nested inline job closed the caller's database connection; the
lookup cache key held raw Hebrew. A source answering 429 is now paused ten
minutes instead of asked per book.

Decisions for Avi's ack: (1) scans stored at up to 4000 px (measured better);
(2) shelf photos served only through Books to their owner; (3) GPS fills the
area only when the person has none; (4) the shelf's spine colours and sizes
are derived from the record, stable, from the board's palette (no colour is
read from the photo yet); (5) "confirm all sure ones" means confidence of 0.85
or more with a catalogue match; (6) a lend offer defaults to 30 days; (7)
`Copy.position`, the scan's default choices and cost fields, and the split of
`raw_text` into `raw_title` / `raw_author` are additions to the model, in
data_model.md section 11.

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
