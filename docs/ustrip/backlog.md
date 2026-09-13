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

Day-by-day plan, per spec §4.1. Seeded from
[`trip-data/usa-2026.json`](trip-data/usa-2026.json) via `manage.py seed_ustrip`
(wired into `render.yaml`'s startCommand, runs on every deploy, idempotent).
13 day-rows / 84 items seeded and verified in dev. Any `family` member can
view; in-app editing is not built yet (see Sprint 3 note) — for now, edit via
`/admin/`.

## Sprint 3 — Packing & task lists `MODELS DONE, UI READ-ONLY`

`ChecklistGroup`/`ChecklistItem` models, admin registration, and a display
page exist and are deployed. **Deliberately not seeded with fake data** —
spec §4.2 is genuinely empty until the family uses it, and inventing sample
packing lists would look like real content. Not yet built: in-app add/check
UI (spec §4.2 assumes any member can tick items from their phone) — today
that means using `/admin/` instead. That gap is real scope left for a
follow-up sprint, not silently dropped.

## Sprint 4 — Photos / journal `MODELS DONE, UI READ-ONLY`

Same shape as Sprint 3: `JournalPost` model, admin registration, display
page — deployed, empty, no fabricated sample posts. In-app photo upload from
a phone is the follow-up sprint; posting today means `/admin/`.
