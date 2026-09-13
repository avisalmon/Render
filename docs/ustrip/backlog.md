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

## Sprint 7 — Full DRF CRUD API `DONE, NOT YET DEPLOYED`

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
