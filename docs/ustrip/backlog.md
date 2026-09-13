# ustrip — Backlog

Standing rule: dev first, deploy on request ([[dev-first-deploy-on-request]]).
Avi said "deploy" on 2026-09-13, so Sprints 1-2 below went to prod that day.

Spec lives in [`spec.md`](spec.md) and is finalized. Process for this backlog
is spec §6: informal sprints, no REQ-ID bookkeeping, tests for the access
gate and models registered in the root [`docs/regression.md`](../regression.md).

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
| Sign in / sign up links on the access-denied page added 2026-09-13, so a family member without a babook account yet can get one, then wait for Avi | DONE — reuses babook's `login`/`register` views, `?next=` sends them back to `/ustrip/` after |
| **Avi marks `family` for Nirit and the kids in `/admin/auth/user/`** | **TODO — nobody but Avi (superuser) is in yet, so ustrip is locked for the rest of the family until this happens** |

## Sprint 2 — Itinerary `DONE, DEPLOYED 2026-09-13`

Day-by-day plan, per spec §4.1. Imported once from
[`trip-data/usa-2026.json`](trip-data/usa-2026.json) via `manage.py seed_ustrip`
(wired into `render.yaml`'s startCommand, so it runs on every deploy — but
is a no-op once the trip already has data; see the Sprint 5.1 bug below).
13 day-rows / 84 items seeded and verified in dev. Any `family` member can
view and (since Sprint 5) add/edit items in-app.

**Two bugs found and fixed 2026-09-13 (Sprint 5.1):**

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

## Sprint 6 — Every item can be deleted, edited, reordered `DONE, NOT YET DEPLOYED`

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
| Flights: edit (own small page, like itinerary item edit) | DONE — no delete; there are exactly two (outbound/return) and deleting one serves no purpose |
| Rental car: edit every field including `confirmed` (own small page) | DONE — no delete, same reasoning as flights |
| Tests: one delete+reorder path per list type, edit+delete for journal/flight/rental car | DONE — `tests/test_ustrip_features.py`, 12 tests total now |

## Sprint 3 — Packing & task lists `DONE, NOT YET DEPLOYED`

`ChecklistGroup`/`ChecklistItem` models, admin registration, and a display
page exist. **Deliberately not seeded with fake data** — spec §4.2 is
genuinely empty until the family uses it. Since Sprint 5: any `family`
member can add a list, add an item, and tap to check/uncheck it in-app —
no more admin-only editing.

## Sprint 4 — Photos / journal `DONE, NOT YET DEPLOYED`

Same shape as Sprint 3: `JournalPost` model, admin registration, display
page — empty, no fabricated sample posts. Since Sprint 5: any `family`
member can post a caption + optional photo in-app.

## Sprint 5 — Own auth, in-app editing skeleton, menu `DONE, NOT YET DEPLOYED`

**Goal:** close the three gaps Sprints 1-4 left open — babook-branded
auth pages, admin-only editing on packing/journal, and no way to sign out
without leaving ustrip.

| Item | Status |
|---|---|
| Own `/ustrip/login/`, `/ustrip/signup/`, `/ustrip/logout/` — same shared `User` accounts (spec §2.1), own styling, no babook branding anywhere in the flow | DONE — replaces the Sprint-1 links out to babook's `/login/`/`/register/` |
| Signup skips email verification (unlike babook's public `app.views.register`) — account works immediately, `family` grant still comes from Avi | DONE — `ustrip/forms.py` |
| Account menu in the header (a `<details>` disclosure, no JS needed for the menu itself) — shows who's signed in, Sign out button | DONE |
| Every write (add/edit/toggle) goes through a JSON API at `/ustrip/api/...`, not a form POST to the page — spec §0b | DONE — plain `JsonResponse` views (`family_required_api`), `static/ustrip/ustrip.js` fetch helper, pages patch their own DOM from the response |
| Packing: add a list, add an item, tap to toggle done — instantly, no reload | DONE |
| Journal: post a caption + optional photo from the phone — new post appears without a reload | DONE |
| Itinerary: add an item to a day, edit an existing item — no creator lock (spec §4.1) | DONE — add is instant; edit is still its own page (submits via fetch, then navigates back) |
| Tests: signup/login/logout, the API's own 403 (JSON, not the HTML page) for a non-member, and one add+edit path per feature | DONE — `tests/test_ustrip_features.py`, 8 passing |
| Not in this sprint: delete/reorder on any list, editing someone else's journal post, "today" highlighting on the itinerary (the CSS exists, the date math doesn't yet), inline (non-page) itinerary edit | Open — candidates for Sprint 6 |
