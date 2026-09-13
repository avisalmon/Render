# ustrip — Spec

> **Status: finalized 2026-09-13.** Every design decision below is settled,
> nothing left blocking Sprint 1.

## 0a. Platform: phone-first

ustrip is used on the road, mid-trip — checking today's plan, ticking off a
packing item, posting a photo. That means **designed for phone first**:
layout, tap targets, and every screen built and checked at phone width
(~360-420px) before anything else. It must still work on a PC (nobody is
locked out at a desktop), but PC is the fit-it-in case, not the design
target — same relationship matazim has to RTL/mobile, just phone instead of
desktop as the default assumption.

## 0. The trip

The family: **Avi and Nirit** (parents), **Yotam, Rotem, and Noam** (kids).

The trip itself: **USA Trip 2026**, Fri Sep 18 – Fri Oct 2, 2026 (15 days).
NYC → Finger Lakes → Niagara Falls (Canada side) → Lancaster/Amish → Washington
DC → Philadelphia → Atlantic City → New Jersey → home. Full day-by-day plan,
lodging, and flights harvested from the family's existing planning site
(`https://avisalmon.github.io/arhab/`) into
[`trip-data/usa-2026.json`](trip-data/usa-2026.json) — this is the seed data
Sprint 2 (itinerary) loads from. That source site itself pulls from a Google
Doc and Google My Maps that stay the family's live source of truth; ustrip's
copy is a snapshot as of 2026-09-13, re-harvest before seeding if the trip
plan has changed since.

This answers spec §5.3 and §5.5 below: it's **one specific trip**, not a
general multi-trip planner — `Trip` can be a single row (or even hardcoded)
rather than a full trip-management feature.

## 1. The charter

ustrip is a private trip planner for Avi's family, built and hosted inside the
babook project. A family member who opens it should see a plain trip app —
itinerary, packing lists, a shared photo journal — with no babook branding,
navigation, or content anywhere in it.

**The one-line rule, same as [[matazim-program-space]]:** babook is the engine
room, ustrip is the building, and the engine room has no door onto the street.

1. **Autonomous presentation.** Its own base template, header/footer, nav,
   styling, and error pages. It does not extend babook's `base.html` and does
   not inherit babook's drawer, top nav, search, or footer.
2. **No route back.** No link, breadcrumb, or nav entry pointing at babook or
   any other babook feature. Babook does not link to ustrip either — it's
   reached only by going straight to its URL.
3. **Shared infrastructure, invisible from the front.** Same Django project,
   database, deploy pipeline, media storage, and — most importantly — the same
   **user accounts**. A family member logs in with the babook account they
   already have (or creates one the normal way); ustrip does not build its own
   signup/login.

## 2. The separation contract

### 2.1 Shared (reused, never duplicated)

| Thing | Why it stays shared |
|---|---|
| Django project, settings, deploy (`render.yaml`) | One app, one deploy, one prod database. |
| `User` accounts and auth backend (`django.contrib.auth` + allauth) | Family members are real babook users. No second password, no second login page. |
| Media storage, mail | Plumbing that already works. |

### 2.2 Separate (built new, owned by this spec)

A new Django app **`ustrip`**, added to `INSTALLED_APPS`, with its own
models, views, `urls.py`, templates (`templates/ustrip/`), static files
(`static/ustrip/`), and its own migration chain starting at `0001`. Nothing
about ustrip lives in `app/`.

```
ustrip/
  models.py
  views.py
  urls.py
  admin.py
  migrations/
templates/ustrip/
  base.html
  ...
static/ustrip/
  ustrip.css
```

Mounted in `mysite/urls.py` before `app.urls`, same as matazim:

```python
path("ustrip/", include("ustrip.urls", namespace="ustrip")),
```

Own `handler403/404/500`, so an error inside `/ustrip/` never renders
babook's chrome (same reasoning as matazim, spec §REQ-M.2).

## 3. Access model — the "family" role

**Superseded 2026-09-13** — replaces the email-allow-list design below with
something Avi can operate entirely from the Django admin, no Render env var
and no email addresses gathered up front.

A standard Django **auth Group named `family`**. `django.contrib.auth`
already ships group membership as a multi-select box on every user's admin
change page — no new field, no new admin UI, nothing to build there. Avi
adds a family member to the site the normal way (they sign up, or he
creates the account) and then checks `family` for that user in
`/admin/auth/user/<id>/change/`.

- The group is created automatically by an ustrip migration
  (`Group.objects.get_or_create(name="family")`) so it exists the moment
  the app is deployed — nobody has to remember to create it by hand.
- **Closed by default, one deliberate exception:** access requires
  `request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name="family").exists())`.
  An empty or missing group means *nobody but a superuser* gets in — no email
  pattern, no domain check, and no `family`-implies-anything-else shortcut,
  only explicit named membership or being a babook site admin.
- **Superseded 2026-09-13 (again):** being a babook site admin/superuser
  *does* imply access, so Avi (the superuser) is never locked out of his own
  app waiting to remember to add himself to `family`. Everyone else —
  Nirit, the kids — still needs explicit `family` membership; this exception
  is scoped to `is_superuser` only, not to babook staff/admin roles in
  general. This narrows the [[home-security-relay]] comparison: `/home`
  keeps superuser and viewer-list fully separate because it protects someone
  else's physical security camera; ustrip is Avi's own app, so admin access
  for its own admin is a reasonable default.
- Anonymous visitors and logged-in non-members get the same plain
  "you don't have access" page (not a 404) — ustrip has no reason to hide
  that it exists, unlike `/home`.
- This retires the `USTRIP_MEMBER_EMAILS` design and §5's open question
  about gathering emails up front — Avi grants access per-account, whenever
  each family member actually has one, instead of pre-declaring a list.

## 4. Features (MVP)

Three pieces, each simple, built in this order:

### 4.1 Itinerary — day-by-day plan
- A trip has a start/end date and a name.
- A trip has many `ItineraryDay` entries (one per calendar day) each holding
  free-form plan items (time, title, location/notes).
- Any allow-listed member can view **and edit** — no creator-only lock. Five
  trusted family members don't need a permissions system, and a lock would
  just be friction the first time Nirit wants to fix a time Avi typed wrong.

### 4.2 Packing & task lists
- Shared checklists scoped to the trip: a list has a name (e.g. "Packing —
  Dad", "Before we leave") and items with a checked/unchecked state and who
  checked it off.
- Lists can be per-person or shared; both are just a `TripChecklist` with an
  optional `assigned_to` user.

### 4.3 Photos / journal
- A simple feed scoped to the trip: each post has an author (the logged-in
  family member), an optional photo, a caption/note, and a timestamp.
- Reverse-chronological, no likes/comments/algorithmic anything — a shared
  photo diary, not a social feature.

## 5. Open questions — none

Nothing left. §3's move to a `family` group means Sprint 1 no longer needs
a pre-gathered email list or an answer on how each kid logs in — Avi grants
`family` membership per-account, whenever each one exists.

## 6. Process — how this gets built

Same discipline as the rest of the repo ([`docs/the_manager.md`](../the_manager.md)),
scaled to the size of the app: five users, three features, not a multi-sprint
product built for strangers. Concretely, matazim's version of this process
(own `docs/matazim/spec.md` + `backlog.md`, `REQ-M.*`/`F-M.*`/`SPR-M.*` IDs,
a full screen-contract catalogue) is more ceremony than this app needs.
ustrip keeps:

- **`docs/ustrip/spec.md` + `backlog.md`** as the two sources of truth,
  updated together, same as everywhere else in the repo.
- **Dev first, deploy on request** ([[dev-first-deploy-on-request]]) —
  unchanged, no exception for a small app.
- **Tests for what can actually break silently:** the access gate (`family`
  member, non-member, anonymous, superuser-without-`family`), and the
  models/seeding logic. These register in the root
  [`docs/regression.md`](../regression.md) like every other test in the
  repo — one pytest suite, one Django project, no separate "ustrip test run."
- **Informal sprints** in `backlog.md` (Sprint 1, 2, 3…), each sprint a
  feature from §4 — no REQ-ID/F-ID bookkeeping, no separate test_plan.md.

What it skips: REQ-numbered traceability, and the screen-contract
catalogue/browser-rendered-state discipline matazim built after real
defects kept hiding in unrendered states. That machinery earned its keep on
a product with dozens of screens and outside users; three simple screens for
five family members don't carry the same risk. Worth reconsidering only if
ustrip's scope grows a lot past the current MVP.

## 7. Out of scope (for now)

- Any invite/join flow (matazim-style) — membership is just the email
  allow-list, edited by Avi via Render env vars.
- Budget/expense splitting (flagged as a maybe in the original ask, not
  picked as an MVP feature — revisit later if wanted).
- Maps/location features beyond a free-text location field on itinerary
  items.
