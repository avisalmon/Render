# ustrip — Backlog

Standing rule: dev first, deploy on request ([[dev-first-deploy-on-request]]).
Avi said "deploy" on 2026-09-13, so Sprints 1-6 below went to prod that day.

Spec lives in [`spec.md`](spec.md) and is finalized. Data model lives in
[`data_model.md`](data_model.md) (added 2026-09-13, per building_an_app.md
Rule 4 — reverse-engineered rather than written first, since ustrip
predates that rule). Process for this backlog is spec §6: informal
sprints, no REQ-ID bookkeeping, tests for the access gate and models
registered in the root [`docs/regression.md`](../regression.md).

---

## Sprint 1 — The front door `DONE, DEPLOYED 2026-09-13`

**Goal:** the app exists, is reachable at `/ustrip/`, is sealed off from
babook's look and nav, and only `family`-group members can see it.

| Item | Status |
|---|---|
| New Django app `ustrip`, added to `INSTALLED_APPS` | DONE |
| Mounted at `/ustrip/` in `mysite/urls.py`, before `app.urls` | DONE |
| Own base template, phone-first styling (spec §0a), no babook chrome | DONE |
| `Trip` model — single trip, USA 2026 (spec §0) | DONE |
| Migration creating the `family` auth Group (spec §3) | DONE — `0002_family_group.py` |
| Access gate: `family`-group check, denied users get an access-denied page (spec §3) | DONE — `access.py` |
| Own `handler403/404/500`, composed with matazim's in `mysite/errors.py` (Django allows only one project-wide handler) | DONE |
| Tests: access gate (member / non-member / anonymous / superuser-without-`family` / empty group), registered in `docs/regression.md` | DONE — `tests/test_ustrip_access.py`, 7 passing |
| Superuser bypass added 2026-09-13: `is_superuser` always gets in (spec §3), so Avi has access without being in `family` | DONE |
| Sign in / sign up links on the access-denied page, so a family member without a babook account yet can get one, then wait for Avi | DONE, later replaced by ustrip's own login/signup in Sprint 5 |
| **Avi marks `family` for Nirit and the kids in `/admin/auth/user/`** | **TODO — nobody but Avi (superuser) is in yet, so ustrip is locked for the rest of the family until this happens** |

## Sprint 2 — Itinerary `DONE, DEPLOYED 2026-09-13`

Day-by-day plan, per spec §4.1. Imported once from
[`trip-data/usa-2026.json`](trip-data/usa-2026.json) via `manage.py seed_ustrip`
(wired into `render.yaml`'s startCommand, so it runs on every deploy — but
is a no-op once the trip already has data; see the Sprint 5.1 bug below).
13 day-rows / 84 items seeded and verified in dev. Any `family` member can
view and (since Sprint 5) add/edit items in-app.

## Sprint 3 — Packing & task lists `DONE, DEPLOYED 2026-09-13`

`ChecklistGroup`/`ChecklistItem` models, admin registration, and a display
page exist. **Deliberately not seeded with fake data** — spec §4.2 is
genuinely empty until the family uses it. Since Sprint 5: any `family`
member can add a list, add an item, and tap to check/uncheck it in-app —
no more admin-only editing.

## Sprint 4 — Photos / journal `DONE, DEPLOYED 2026-09-13`

Same shape as Sprint 3: `JournalPost` model, admin registration, display
page — empty, no fabricated sample posts. Since Sprint 5: any `family`
member can post a caption + optional photo in-app.

## Sprint 5 — Own auth, in-app editing skeleton, menu `DONE, DEPLOYED 2026-09-13`

**Goal:** close the three gaps Sprints 1-4 left open — babook-branded
auth pages, admin-only editing on packing/journal, and no way to sign out
without leaving ustrip.

| Item | Status |
|---|---|
| Own `/ustrip/login/`, `/ustrip/signup/`, `/ustrip/logout/` — same shared `User` accounts (spec §2.1), own styling, no babook branding anywhere in the flow | DONE — replaces the Sprint-1 links out to babook's `/login/`/`/register/` |
| Signup skips email verification (unlike babook's public `app.views.register`) — account works immediately, `family` grant still comes from Avi | DONE — `ustrip/forms.py` |
| Account menu in the header (a `<details>` disclosure, no JS needed for the menu itself) — shows who's signed in, Sign out button | DONE |
| Every write (add/edit/toggle) goes through a JSON API at `/ustrip/api/...`, not a form POST to the page — spec §0b | DONE at the time — hand-rolled `JsonResponse` views; **superseded by Sprint 7's move to a full DRF CRUD API** |
| Packing: add a list, add an item, tap to toggle done — instantly, no reload | DONE |
| Journal: post a caption + optional photo from the phone — new post appears without a reload | DONE |
| Itinerary: add an item to a day, edit an existing item — no creator lock (spec §4.1) | DONE — add is instant; edit is still its own page (submits via fetch, then navigates back) |
| Tests: signup/login/logout, the API's own 403 for a non-member, and one add+edit path per feature | DONE — 8 passing at the time |

## Sprint 5.1 — Two data bugs, found and fixed `DONE, DEPLOYED 2026-09-13`

Avi's review of the shipped data ("it looks like text, not data objects")
surfaced two real bugs, not just a naming complaint:

1. The JSON's `flights` and `rental_car` blocks were harvested but never
   modeled — `seed_ustrip` silently ignored them, so that data sat in a
   text file nobody could see in the app. Fixed: new `Flight`/`RentalCar`
   models, seeded, shown on Home under "Trip essentials". `route_summary`
   seeded onto `Trip` too, shown under the trip dates.
2. **More serious:** `seed_ustrip` wholesale-deleted and recreated the
   entire itinerary from the static JSON on *every* deploy (it's wired into
   `render.yaml`'s startCommand, which runs on every push). Combined with
   Sprint 5's in-app "add item"/edit, the next unrelated deploy would have
   silently erased anything a family member added. Fixed: the command is
   now a one-time import — once a trip has any days/flights, it leaves them
   alone; the database is the source of truth from there on, not the JSON.
   Same treatment for the rental car's `confirmed` flag and, once
   confirmed, its other fields too (a real booking's details shouldn't keep
   getting overwritten by the original researched-proposal numbers).
   `tests/test_ustrip_seed.py` calls the real command twice to guard both
   bugs concretely, not just via fixtures.

The JSON's `lodging` array is deliberately still not its own model — it's
the same information as each day's `sleeping` field, grouped by
night-block instead of by day; a second model would just be two copies of
the same fact free to disagree.

## Sprint 6 — Every item can be deleted, edited, reordered `DONE, DEPLOYED 2026-09-13`

**Goal:** close the delete/reorder gap Sprint 5 explicitly left open. Avi's
framing: this isn't a nice-to-have — the reference source is just HTML/text,
and everything imported from it has to become a real object the family can
play with, not a read-mostly display. No creator lock anywhere here, same
philosophy as itinerary edit in Sprint 5.

| Item | Status |
|---|---|
| Itinerary items: delete, move up/down within the day | DONE |
| Packing items: edit text, delete, move up/down within the list | DONE |
| Packing lists: delete (cascades its items) | DONE |
| Journal posts: edit caption/location, delete | DONE — replacing the photo itself isn't built; re-post if it was wrong |
| Flights: edit (own small page, like itinerary item edit) | DONE — no delete via the UI; there are exactly two (outbound/return) |
| Rental car: edit every field including `confirmed` (own small page) | DONE — no delete via the UI, same reasoning as flights |
| Tests: one delete+reorder path per list type, edit+delete for journal/flight/rental car | DONE — 12 tests at the time |

## Sprint 7 — Full DRF CRUD API `DONE, DEPLOYED 2026-09-13`

**Goal:** align ustrip with building_an_app.md Rule 6, written after
Sprints 1-6 shipped: every app gets a full, documented CRUD API on Django
REST Framework, as standard infrastructure — not the hand-rolled
`JsonResponse` views Sprint 5 built before that rule existed. Found during
an explicit audit of ustrip against the whole methodology doc (the other
five rules already held).

| Item | Status |
|---|---|
| `djangorestframework` added to `requirements.txt` and installed | DONE |
| One `ModelSerializer` per model (`ustrip/serializers.py`) — `order`/`done_by`/`author` read-only, set server-side, never client-supplied | DONE |
| One `ModelViewSet` per model (`ustrip/api.py`), registered on a `DefaultRouter` at `/ustrip/api/...` — full create/read/update/delete on every model, including `Flight`/`RentalCar` (the UI still only exposes edit for those, but the API itself is real CRUD) | DONE |
| `IsFamilyMember` DRF permission (`ustrip/permissions.py`), wrapping the same `is_family` check page views use — one rule, two callers | DONE |
| `move` (reorder) kept as a custom `@action` on the two viewsets with real ordering — it isn't one of the four CRUD verbs, so it doesn't belong on create/update | DONE — `ustrip/reorder.py` |
| DRF's browsable API (default renderer) is the "documented" part of Rule 6 — no separate schema generator for a five-person app | DONE |
| Old hand-rolled `api_*` views, `family_required_api`, and the ad hoc JSON serializer functions in `views.py` | REMOVED |
| Every page's JS (`static/ustrip/ustrip.js` + inline scripts) updated to call the new REST endpoints and field names | DONE |
| Tests rewritten against the real DRF endpoints, plus one confirming `author` can't be client-supplied and one confirming the API allows a flight delete even though the UI never offers it | DONE — `tests/test_ustrip_features.py`, 15 passing |
| `docs/ustrip/dashboard.html` (Rule 4's last missing piece) | DONE |
| Full audit of `trip-data/usa-2026.json` against the models, prompted by "did you fill all data?" — found `ItineraryDay` had no `note` field, so Day 3's open decision and Day 9's parking heads-up were silently dropped on every import | DONE — `note` field added, seeded, shown on the day page; `duration_days`/`family` name-list confirmed deliberately unmodeled (derivable / superseded by real accounts), documented in `data_model.md` |

## Sprint 8 — Days and items: the rich item, the flow schedule, drag-and-drop `DONE, DEPLOYED 2026-09-14`

**Goal (Avi, 2026-09-14):** "I want each item to have a very rich detail
page that will be linked from the day list", plus photos, a schedule, likes
and comments, ordered by the schedule in the day view, draggable at the
day level with the schedule updating automatically. Two design questions
settled with Avi before building: the schedule is a **flow with pinned
anchors** (not per-item stored times), and drag works **between days**
too, not just within one.

Also answered here: "did you fill them all from the source, planned and
optional?" — yes by count (84 items, 69 plan / 15 optional), but the first
import had condensed every line to a sentence and dropped all the links.
This sprint recovers the source text and links exactly.

| Item | Status |
|---|---|
| `ItineraryItem` gains `title`, `location`, `cost`, `duration_minutes`, `fixed_start`, `tips`, `booking`; a `rejected` tag; `ItineraryDay.start_time` | DONE — migration 0005 |
| New `ItineraryLink`, `ItineraryPhoto`, `ItineraryLike`, `ItineraryComment` | DONE |
| `ustrip/schedule.py`: computed flow schedule with anchors; `start`/`end` on every item representation, stored nowhere | DONE |
| API: viewsets for the four new models; `reorder` on the day (takes ids from any day — one endpoint for within-day and between-day drags); `like` toggle on the item; changing an item's `day` appends it to the new day and renumbers the old | DONE |
| The one creator lock: comments (and likes) are owner-only to change — `IsOwnerOrReadOnly` | DONE |
| Item detail page `/ustrip/itinerary/item/<id>/`: everything above, photos + upload, like toggle with avatars, comments, edit/delete | DONE |
| Edit page: every field, day picker (the non-drag way to move an item), links add/remove | DONE |
| Day page: computed times, titles linking to detail, tags (optional / dropped / booked / to book / pinned), like/comment/photo counts, day start control, drag-and-drop reorder with times updating in place | DONE |
| Itinerary list: each day a collapsible section with its items; drag between two open days | DONE |
| `ustrip.sortable` — pointer-events drag-and-drop written by hand (HTML5 drag events don't fire for touch on phones) | DONE — `static/ustrip/ustrip.js` |
| `trip-data/build_items_json.py` + `source/daily-plan.html` snapshot → `usa-2026-items.json`: full text + every link (mechanical), titles/durations/anchors/costs/tips/booking (curated) | DONE |
| `manage.py enrich_ustrip_items`: one-time fill under the seed rule (untouched → everything; enriched → blanks only; family-edited → skipped, links included); wired into `render.yaml` after `seed_ustrip` | DONE |
| The Day 8 "Considered … dropped" line, tagged `plan` by the first import because the source had no tag, becomes `rejected` | DONE |
| Tests: schedule + anchors, reorder within/between days, move-to-day, links, photo upload, like toggle, comment author lock, the three pages, enrichment twice with an edited item in the way | DONE — `tests/test_ustrip_items.py` |
| Deploy | DONE — pushed f53dcfb on Avi's word, live build verified serving the new CSS ~2 min later; the start command ran migration 0005 and `enrich_ustrip_items` (84 enriched) on the way up |

Not built, on purpose, until asked: replacing a photo (delete and re-add),
editing a link in place (remove and re-add), reordering links or photos.

## Sprint 9 — When a day doesn't fit `DONE, DEPLOYED 2026-09-14`

**Avi's question (2026-09-14):** what should happen with events that can't
squeeze into a day — alert, refuse, make room? Decided: **warn, never
refuse, never auto-fix.** The schedule keeps computing exactly as before;
it also reports what doesn't fit, the pages show it where it happens, and
the family decides (shorten, move, unpin, make optional).

| Item | Status |
|---|---|
| `ItineraryDay.end_time` (default 23:00 — 22:00 made most NYC evenings red, and a warning that fires on most days stops being one), editable next to the start on the day page | DONE — migration 0006 |
| Engine reports per item: `overrun_minutes` + `overrun_into` (runs into the next planned anchor), `gap_before_minutes` (free time, not a conflict), `past_day_end`; per day: `schedule_ends_at`, `schedule_over_minutes`, `schedule_conflicts` | DONE — `ustrip/schedule.py` |
| A next-morning anchor (Day 14–15's landing after an 11h flight) is a gap, not a 17-hour overrun | DONE |
| Fix: an *optional* pinned item used to reset the clock for the planned items after it, contradicting Sprint 8's rule | DONE |
| Day page: "Day runs 09:00 to 22:00", a summary line ("Ends 23:40 · 1h 40m past 22:00 · 2 stops don't fit"), a red note on the squeezed item, red times past the day's end, "1h 15m free" markers before pinned stops — all updated in place after a drag or a time change | DONE |
| Itinerary list: "ends 23:30 (1h 30m past 22:00) · 1 doesn't fit" per day, a red "!" on the rows that don't fit, updated after cross-day drags | DONE |
| API: the fields above on every item and day representation, so adding an item that doesn't fit succeeds (201) and the response says so | DONE |
| Tests: overrun into an anchor, gap before an anchor, past-day-end with the day's totals, next-morning anchor, optional pin doesn't move the clock, add-that-doesn't-fit succeeds and reports, `end_time` editable + the page and list render the summary and the gap | DONE — 7 more in `tests/test_ustrip_items.py` |
| Deploy | not yet — dev only until Avi says |

Not built, on purpose, until asked: suggestions ("shorten X by 25m?",
"move to Day 3?") that the person accepts with one tap. That is the
acceptable form of "make room" — a proposal, never a silent change.

## Sprint 10 — Before we fly `DONE, DEPLOYED 2026-09-14`

**Why now:** the trip starts 2026-09-18. Home showed the first item of the
first day forever; nothing knew what day it was; six of seven nights had no
hotel object to put a booking on; the family's practical notes lived only in
a Google Doc.

| Item | Status |
|---|---|
| `ItineraryDay.date` / `date_end`; `Trip.timezone` (New York); `Lodging`; `TripNote` | DONE — migration 0007 |
| `seed_ustrip`: backfills dates once by position where empty; seeds the 7 stays and the notes once; never touches an existing stay or note | DONE |
| `ustrip/today.py`: `position(trip, now)` → before (days to go, first stop) / during (today's day; the planned stop now, or next today, or tomorrow's first) / after — on the trip's clock, pure and testable | DONE |
| Home: phase line ("4 days to go" / "Today: Day 5 · Finger Lakes"), the Now / Next up / Tomorrow / First up card, "Where we sleep" with "not booked yet" pills and Add a stay, "Good to know" with add/edit/delete/reorder inline | DONE |
| Itinerary list marks today and opens it; day page shows the stay covering that night (linked to its edit page) instead of the free-text line | DONE |
| Stay edit page (`lodging/<id>/edit/`, `lodging/new/`): hotel, where, dates, booked, notes, delete; API viewsets for stays and notes (notes with `move`) | DONE |
| Tests: position in all three phases and the timezone case, a two-date row, seed dates/backfill, stays once + booked survives a redeploy, notes once + edits survive, Home/list/day pages, stays and notes API | DONE — `tests/test_ustrip_today.py` |
| Deploy | not yet — dev only until Avi says |

## Sprint 10.1 — Notes in the day `DONE, DEPLOYED 2026-09-14`

**Avi (2026-09-14):** items in a day don't necessarily have a schedule —
reminders, information, things that don't touch the times but sit in the
order wherever they read best, as many as wanted.

| Item | Status |
|---|---|
| `ItineraryItem.kind`: `stop` (scheduled, as before) or `note` (no time, never moves the clock, never in a conflict or gap) | DONE — migration 0008 |
| Day page: a note shows an info mark instead of a time, a hollow dot, no duration; the add form has a "just a note" checkbox that hides the timing fields; the edit page has a Kind select | DONE |
| List page and detail page render notes without a time; notes drag like any item, within and between days | DONE |
| Tests: a note has no time and B still flows straight from A; a note is created through the API, renders on the three pages, and reorders | DONE — 2 more in `tests/test_ustrip_items.py` |

## Sprint 11 — The fix sprint `P1+P2 DONE, F7/F8/F9/F11/F13 DONE, F12 mostly moot`

A full review on **2026-09-14**, after Sprints 8-10.1 landed, against
[spec.md](spec.md) and [building_an_app.md](../building_an_app.md).
Nothing here is a new feature: every row is something already built that
doesn't hold up on a phone, on a bad connection, or under a query count.
Findings are measured, not guessed — the numbers below are from a real
run against the seeded trip (13 days, 84 items).

**State at review:** 68/68 ustrip tests pass, `manage.py check` clean, all
six methodology rules aligned. The app is in good shape; this is the list
of what would embarrass us on the road.

**Context that sets the priority:** the trip starts **Fri Sep 18** — four
days out. P1 is what matters standing on a street corner in Manhattan
with one bar of signal. P3 and P4 can wait until after the trip.

### P1 — On the road, or none of it matters

| # | Item | Why |
|---|---|---|
| F1 | **Offline: PWA manifest + service worker.** Cache the app shell and the whole itinerary; today's day must open with no signal. Installable to the home screen. Writes made offline are queued or refused out loud, never silently dropped | The app has neither today. Niagara, the Finger Lakes and a rental car between Lancaster and DC are exactly where signal goes, and the itinerary is the one thing the app exists to hold. Spec §0a.2  **DONE.** Manifest + service worker at `/ustrip/sw.js` (served from a view so the scope is `/ustrip/` and it can never touch babook); app shell and pages cached, network-first so online always wins; writes are refused out loud, never queued. Tested for real: Playwright cuts the network and the day page still renders. |
| F2 | **Downscale photos in the browser before upload** (canvas, ~1600px long edge, JPEG ~0.82) | Raw phone photos are 3-8MB and go up untouched. Render's disk is **1GB and the SQLite database is on it** — a few hundred photos fill the volume the database lives on. Spec §0a.3  **DONE.** `ustrip.shrinkPhotos()` downscales to a 1600px long edge at JPEG 0.82 before upload, on both the journal and the stop-photo forms. Anything that fails to decode is passed through untouched — a broken resize must never cost the family the photo. |
| F3 | **Tap targets to 44px; move Delete out of the button row** | `.box` (the packing checkbox) is **20px** — under even WCAG 2.5.8's 24px floor. `.mini-btn`, `.add-btn`, `.drag-handle` are 26px, and on every itinerary row four of them sit adjacent with **delete next to move-down**. Spec §0a.1  **DONE.** Hit areas to 44px throughout, and delete pushed clear of the move cluster. The guard test found it was not just the row buttons: the bottom nav, the back arrow, the account menu, the booked checkbox and every list title were all under 44 too. |
| F4 | **Disable a control while its request is in flight** | No form does. On slow wifi a second tap posts a second journal entry / adds a second item. Spec §0a.1  **DONE.** Central: a capture-phase submit listener notes the button, `request()` disables it until the response lands. `ustrip.hold()` covers the async cases (the photo resize holds it across resize *and* upload). |

### P2 — Performance and the guard that should have caught F3

| # | Item | Why |
|---|---|---|
| F5 | **Kill the API N+1.** Annotate like/comment counts on the viewset queryset, pass the day's computed schedule into the nested item serializer instead of recomputing per item, prefetch `likes`/`comments` | Measured: `/ustrip/api/itinerary-days/` = **425 queries**, `/ustrip/api/itinerary-items/` = **342**. Per item it runs `likes.count()`, `likes.filter().exists()`, `comments.count()` and a **full day re-`compute()`**. The pages are fine (15-20) because the views precompute — it's the API, which Rule 6 calls the infrastructure, that is slow. Target: under 15 each  **DONE.** 425 → **7** queries on the days endpoint, 342 → **7** on items. Counts annotated onto the queryset, the day's schedule computed once per request instead of per item. |
| F6 | **A phone guard test for ustrip**, like `test_matazim_mobile.py`: real browser at 390px over every ustrip page — nothing wider than the viewport, no tap target under 44px, the menu opens | matazim, which is *not* phone-first, has this test. ustrip, which declares phone-first in spec §0a, has none — which is exactly why 20px checkboxes shipped  **DONE.** `tests/test_ustrip_mobile.py`: overflow, effective tap targets (probed, not measured from CSS), a real offline reload, and installability. It found every one of F3's targets and two bugs of its own — see below. |

### P3 — Interactions that feel unfinished

| # | Item | Why |
|---|---|---|
| F7 | **Replace `alert` / `confirm` / `prompt` with in-page editing and a toast** | **48** native dialogs across the templates. Editing a packing item or a "good to know" note is a `prompt()` — single-line, unstyled, and on iOS it announces the domain. Spec §0a.1 |
| F8 | **Stop reloading the page after a reorder** — patch the DOM from the response | **8** `location.reload()` calls. The reorder API already returns the recomputed day, so the data is in hand; reloading throws away your scroll position halfway down a 12-stop day or the long Home page. Spec §0a.1  **DONE (packing).** The row swaps with its neighbour in place from the response. Still to do on the itinerary day and list pages, which reload for the same reason. |
| F9 | **Packing: "N of M packed" per list, and a "just mine" filter** | The page shows "12 items" but never how many are done — the one number that matters while packing. `ChecklistGroup.assigned_to` is already modeled, so "mine" is a filter over data we have, not a new feature  **DONE, and more than asked.** "N of M packed" with a bar per list, green when a list is finished; a Mine/All filter remembered in `localStorage`; a `assigned_to` picker on the new-list form, without which the filter was a filter over a field nobody could set outside `/admin/`; and multi-line add (`add_items`), because packing is eight things at once, not one per round trip. |
| F10 | **Home: drop the "Around the trip" tiles** | They link to Itinerary / Packing / Journal — the exact three destinations in the bottom nav, visible on the same screen. Home is now long (hero, next-up, getting there, where we sleep, good to know, tiles); this is the section that earns its space least |

### P4 — Worth a decision, maybe not a build

| # | Item | Why |
|---|---|---|
| F11 | **Journal: group by day or place** | A flat reverse-chron feed over 15 days and 5 posters has no way to find "the Niagara photos." Cheap version: a date separator. Real version: tie a post to its `ItineraryDay` |
| F12 | **Backup cadence during the trip** | Media is in the weekly GCS backup, so the loss window is up to **7 days of the family's photos** during a 15-day trip. Daily for the trip window is a two-line change to the workflow — but it's Avi's risk call, not an obvious yes |
| F13 | **Two consecutive optional stops show the same start time** | Correct per the schedule design (an optional doesn't move the clock), but two rows reading "14:00" look like a bug to anyone who didn't design it. Possibly just a label: "14:00 if you go" |

### What building the fix sprint turned up

Two things the review had not found, both surfaced by F6's guard test the
moment it existed — which is the argument for the test:

- **Everything was under 44px, not just the row buttons.** The review named the
  20px checkbox and the 26px row cluster. The test added the bottom nav (39px,
  and the most-tapped thing in the app), the back arrow, the account menu, the
  "actually booked" checkbox, every stop title in both list views, and the
  Post/Save buttons. A review reads templates; the test measures what a thumb
  hits.
- **The bottom nav made every long page scroll sideways.** `position: fixed;
  left: 0; right: 0` resolves against the viewport *including* the scrollbar, so
  on any page tall enough to scroll the bar came out 4px wider than the document.
  Now `position: sticky` inside `.app`, which sizes to the column the rest of the
  app already lives in. This was live in production and nobody had noticed.

The guard test also needed two fixes of its own before it was honest, both
worth knowing if it ever reports something odd: controls below the fold have
their centre outside the viewport (they are scrolled into view first), and a
control that is present but covered — the account menu while its `<details>` is
shut — fails every probe for reasons that have nothing to do with size (if the
centre does not hit the control, it is skipped). Overflow is asserted on a named
offending element rather than `scrollWidth`, which under mobile emulation tracks
the visual viewport and reports 4px of overflow on a page where nothing
overflows.

## Sprint 12 — The week before we fly `PART DONE`

Not a bug list: what the family actually touches between now and Friday.

**Packing was the real gap, and it was not on the review's list.** Seeding
creates the itinerary, flights, rental car, lodging and trip notes, but
deliberately no packing lists (spec §4.2: nothing fabricated). That was right
in principle and wrong in effect — the family packs *this* week, and the tab
was a blank page with a one-item-at-a-time box behind a 30px plus button.
Fixed above as F9 plus multi-line add.

| Item | Status |
|---|---|
| Packing: progress, Mine/All filter, owner picker, multi-line add | DONE — see F8/F9 |
| The whole packing label is the tap target, not the 26px box inside it | DONE — and it exposed that the phone guard was testing an *empty* packing page, because seeding creates no lists. The fixture now gives packing and the journal real content, and the guard immediately failed on five controls it had never been able to see |
| F8 on the itinerary day and list pages | DONE — the day's arrows and delete now take the same path the drag already did: swap in the DOM, send the new order, re-time from the response. The list page only ever reloaded on error, which is the right fallback and stays. Home's note arrows swap in place too. A browser test covers the day page, which nothing else did |
| F12 backup cadence during the trip | **Avi's decision, mostly moot since Sprint 15.** The original risk was the weekly GCS backup window leaving up to 7 days of photos unbacked in `MEDIA_ROOT`. New photos never touch `MEDIA_ROOT` at all now — they go straight to Drive, which is its own durable store, not something this app backs up. Only photos already on disk before Sprint 15 still carry the old exposure, and only until `migrate_ustrip_photos_to_drive` runs (blocked on the Drive credentials being set, same as everything else in that sprint) |
| F10 Home tiles | DONE — the three tiles duplicated the nav bar six centimetres below them. The counts they carried stay, as one line instead of three cards |
| Adding a stop still reloads the day page | OPEN — the least painful of the reloads, since browsers restore scroll on reload, and the row markup is rich enough that building it in JS would duplicate the template |
| F13 optional-stop label | DONE — a tilde (`~14:00`) on an optional stop's time, in both the server-rendered row and its JS twin. The schedule itself was already correct (an optional stop is a candidate, not a reservation, so it never claims a time slot); this only changed how the same correct number reads when two stops land on it |
| F7 native dialogs | DONE — 47 call sites across 10 templates. Own `toast()`, `confirm()` and `editInPlace()` in `ustrip.js`, reusing the app's existing design tokens rather than a component library. Proved with a real browser: `tests/test_ustrip_mobile.py::test_no_native_dialog_ever_fires` edits and deletes a real packing item through the real UI with Playwright's `dialog` listener armed, and was confirmed to fail — not just pass — by putting one `confirm()` back and watching it catch that exact regression |
| F11 journal grouping | DONE — grouped by the day a post was *made on*, not a day picked by hand at post time (the "real version" in the original note, without the extra control that would have added). The label is the day's own title ("Niagara Falls"), read through `ItineraryDay.covers()`, which already existed for `today.py`; no schema change, no migration. `ustrip/journal_grouping.py`. Converted to the trip's own clock, the same reasoning `today.py` already uses, and tested for the exact failure that reasoning exists to prevent: an 11pm post staying on the correct calendar day rather than sliding to the next one in UTC. Headers merge when consecutive posts share a day and clean up after themselves when the last post under one is deleted — proved with a real browser, and proved to actually catch a regression by breaking the merge logic once and watching the test fail on it |

**Still needs Avi, not code:** nobody but Avi is in the `family` group, so
none of this is visible to Nirit or the kids; everyone should open the app
once on wifi so the service worker caches the itinerary on their phone; and
the rental car and some lodging still say "not booked yet" in the app.

## Sprint 13 — Granting access without a laptop `DONE (DEV)`

**Avi, 2026-09-14: "Can you add יותם to the family?"** I could not, and that
was the finding. Everything else about ustrip can be built, checked and fixed
from a chat; letting a family member in stopped dead at "open
`/admin/auth/user/` on your phone and tick a box" — four people to add, four
days before the trip, from a phone, while running three chats.

| Item | Status |
|---|---|
| `/ustrip/api/family/` — GET who is in (and which accounts exist but are not), POST to add, DELETE to remove | DONE — `ustrip/family_api.py` |
| Auth: a shared secret in `USTRIP_ADMIN_TOKEN`, constant-time compare, following `app/security_api.py`'s convention. A superuser session also works, so it is usable from the browsable API and still works if the env var was never set | DONE |
| Scope fenced by code, not intentions: only the `family` group (the name is not a parameter), never creates an account, never grants staff/superuser, never deletes a user, fails shut when unset | DONE — 8 of the 13 tests are refusals |
| Written up as a BKM in [building_an_app.md](../building_an_app.md) | DONE |

**Why it is not an admin key.** An app here shares a database with every
other app, so a general admin key is a skeleton key to other people's
accounts — and it will end up in a chat transcript, because that is how it
reaches the agent that needs it. The worst a stolen `USTRIP_ADMIN_TOKEN` can
do is add or remove somebody on a private family trip planner. That sentence
is only true because of the scope rules above.

**To turn it on:** set `USTRIP_ADMIN_TOKEN` in Render to a long random
string. Unset means closed, so nothing changes until it is set. Rotate by
changing the value; no redeploy of logic.

### Sprint 13.1 — "Is the API secure?" answered by attacking it

Avi, 2026-09-14: "verify again that your REST API is secure and no one not
authorized can just CRUD all data."

| Item | Status |
|---|---|
| `tests/test_ustrip_api_locked.py` — every route the router registers, every verb, as an anonymous stranger and as a signed-in babook user who is not in `family`. Asserts the refusal *and* that the database is unchanged; a 403 that still wrote the row would pass a status-only check. Routes come from `ustrip.urls.router`, so an endpoint added next month is covered the day it exists | DONE — 43 tests, all refused; and the inverse, a family member *can* read every route, because a test that only checks refusals also passes on a broken app |
| The same probe against production, anonymously: 12 endpoints × GET/POST/DELETE | DONE — 403 across the board |
| The family endpoint used to hand back the 50 most recent accounts with email addresses to answer "what did Yotam sign up as." Some of those are מט״צים teenagers. That is the general-admin-key objection one floor down, in my own code | DONE — candidates are now opt-in via `?q=`, two characters minimum so `?q=a` cannot walk the user base, ten results max |

## Sprint 14 — Someone finds out if it breaks `DONE (DEV)`

The trip is fifteen days with nobody watching a log. No Sentry, no `ADMINS`,
no error email anywhere on the site — a 500 in ustrip on day six at Niagara
went into Render's log and stopped there; Avi would find out when someone
texted him.

| Item | Status |
|---|---|
| `ustrip/middleware.py` — an unhandled `/ustrip/` exception mails `USTRIP_ERROR_NOTIFY`; every other path is untouched | DONE |
| Throttled per error signature (type + file + line, not the message), so a crashloop sends one mail every 30 minutes, not one per request | DONE |
| Body: path, method, who was signed in, error, traceback tail. Never the request body — a journal caption or a password has no place in an error email | DONE |
| Real bug found building this: the recipient fell back through `CONTACT_NOTIFY_EMAIL` to `DEFAULT_FROM_EMAIL`, which has a non-blank hardcoded default in this project's settings.py. That meant "unset" was never actually unset — it would have mailed a sender address nobody reads, in every environment, including a laptop running the test suite | FIXED — `USTRIP_ERROR_NOTIFY` only, no fallback chain, and a test locks it in |
| Verified end-to-end, not just unit-level: a real exception through a real `/ustrip/` view, over the real Django request cycle — the 500 page still renders and the mail still sends | DONE |
| Tests: 8, including the crashloop throttle, the path-scoping to `/ustrip/` only, and the no-fallback regression | DONE — `tests/test_ustrip_error_notify.py` |

**To turn on:** set `USTRIP_ERROR_NOTIFY` in Render to an address that's
actually read. Unset means silent, same principle as `USTRIP_ADMIN_TOKEN`.

## Sprint 15 — Photos move off Render's disk into Drive `DONE (DEV)`

Avi, 2026-09-15: "I want to use my drive as I use in the home app for
photos." The home app's own pattern doesn't transfer directly — there, the
house uploads to Drive itself and only ever hands babook a link; here, the
family uploads straight from their phones through this app, so ustrip has
to be the one talking to Drive.

**The plan changed twice in one day, and both changes were Avi's calls.**
First cut: reuse the security relay's own OAuth credentials and Drive
folder, with ustrip's own subfolder inside it — his answer when first
asked. Then, having watched the trail to find out where those credentials
actually lived (a home PC's local `.env`, nowhere near Render), he asked
instead for a Drive set up "completely for all the apps... as the main
storage" — this project's **own** dedicated Google Cloud project and OAuth
client, not borrowed from a system that deploys on a different machine on a
different schedule. That is what shipped. Whether to keep a local copy too
was never a strong preference either way — Drive-only, per spec §0a.3,
since a local copy would keep the exact 1GB-disk risk this sprint exists to
close.

| Item | Status |
|---|---|
| `app/drive.py` — hand-written `DriveClient` (OAuth refresh, `upload_bytes`, `download`, `delete`, `root_folder_name`), shaped like the home security app's own `seccore/drive.py` but a separate module, separate credentials, separate Google Cloud project. One root folder (`DRIVE_FOLDER_ID`), one named subfolder per app | DONE |
| `app/management/commands/drive_setup.py` — one-time local OAuth consent flow (ported from the Security repo's proven `scripts/drive_setup.py`), `drive.file` scope, loopback redirect, prints the three credentials Render needs; `--check` verifies them read-only, without creating anything | DONE |
| `ItineraryPhoto` / `JournalPost`: `drive_file_id`, `drive_url`, `content_type` added; `photo` relaxed to optional (legacy, no longer written to) | DONE — migration `0009` |
| `photo_url` model property: Drive via the proxy view when `drive_file_id` is set, the legacy local file otherwise, `""` when there is no photo at all (legal for a journal post) | DONE |
| Two proxy views, `@family_required` — the same gate as every other ustrip URL, never a raw Drive URL an outsider could open if they got the link | DONE — `/ustrip/itinerary/photo/<pk>/file/`, `/ustrip/journal/photo/<pk>/file/` |
| Upload viewsets: `photo` is write-only on the serializer, goes to Drive via `_attach_drive_photo`, never to disk; delete cascades to a best-effort Drive delete | DONE |
| Drive not configured, or the upload fails: refused with a clear error, never a silent fallback to local disk | DONE |
| **Bug found by the test written for the failure case**: the photo row was being created *before* the Drive upload was attempted, so a failed upload left an empty, photo-less row behind rather than nothing at all. Fixed — `perform_create` wraps the save and the upload in one transaction | FIXED |
| `migrate_ustrip_photos_to_drive` — one-time, idempotent backfill for the photos Sprint 4 already put on disk; local file freed only after the Drive upload is confirmed | DONE |
| Templates and their inline JS (`itinerary_item_detail.html`, `journal.html`) switched from `photo.photo.url` / `post.photo` to `photo_url` | DONE |
| `render.yaml`: `DRIVE_CLIENT_ID`, `DRIVE_CLIENT_SECRET`, `DRIVE_REFRESH_TOKEN`, `DRIVE_FOLDER_ID` declared `sync: false` — shared across apps, not ustrip-specific, so no `USTRIP_` prefix | DONE |
| Tests: 14 (`test_ustrip_photos_drive.py`) plus the existing upload/delete test updated for the new response shape — Drive unconfigured, upload failure, atomicity, family-only proxy access, text-only journal posts, delete cascade, backfill idempotency | DONE — 145 ustrip tests pass |

**To turn on, before it does anything, in order:**

1. Run `manage.py drive_setup` locally — walks through creating a Google
   Cloud project, enabling the Drive API, publishing the OAuth consent
   screen, and a Desktop app OAuth client; then opens a browser for the
   one-time approval and prints `DRIVE_CLIENT_ID`, `DRIVE_CLIENT_SECRET`,
   `DRIVE_REFRESH_TOKEN`.
2. Create (or pick) one Drive folder to be the shared root, copy its id out
   of the URL — that is `DRIVE_FOLDER_ID`.
3. Put all four in Render (babook service → Environment). Nothing changes
   until all four are set — uploads are refused with a clear message in the
   meantime, same as `USTRIP_ADMIN_TOKEN` unset.
4. `manage.py drive_setup --check` confirms the token refreshes and the
   folder id resolves, without writing anything.

**Publish the OAuth consent screen before the trip, not after.** Left in
"Testing" status, Google expires the refresh token after seven days —
uploads would stop silently on day eight of a fifteen-day trip while
everything else looked healthy. This is a fresh OAuth client with no track
record yet, unlike the home app's, so "it's probably fine" does not apply
here the way it might have to a years-old grant — check it explicitly.

**Not done, and not blocking:** existing local photos are migrated by
running `migrate_ustrip_photos_to_drive` once by hand in production — it
has not been run yet, because the four credentials are not in Render yet
either. Both happen together, whenever Avi finishes the setup above.

**Also not done:** matazim and memz do not use `app/drive.py` yet. Nothing
stops them — same four credentials, their own subfolder name — but nobody
has asked for it, and building it speculatively for apps that do not upload
anything today would be exactly the kind of unasked-for work this project's
own methodology warns against.
