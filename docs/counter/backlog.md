# counter: Backlog

Standing rules: dev first, deploy on request. Process weight is small, per
[building_an_app.md](../building_an_app.md): [spec.md](spec.md) and this file
are the two sources of truth and move together; tests cover what can break
silently. Sprints are `SPR-N.n`, tests live in `tests/test_ctr_<n>.py` with
the pytest marker `ctr<n>`.

Status values: `TODO`, `WIP`, `DONE`, `DONE, DEPLOYED <date>`.

## SPR-N.1: counting `DONE (dev), 2026-10-16, awaiting review`

| ID | Feature | Status |
| --- | --- | --- |
| F-N.1.1 | App `counter`, mounted at `/counter/`, own base template, own 403/404/500 composed into `mysite/errors.py`, own login (Google link plus password) | DONE |
| F-N.1.2 | Models Site, Page, Event, Promo, PromoPlacement, migration 0001 | DONE |
| F-N.1.3 | Public API: `POST /counter/api/hit/`, `GET /counter/api/stats/<key>/[?path=]`, `GET /counter/api/promo/<key>/?path=`, CORS open, hit sent as text/plain (no preflight) | DONE |
| F-N.1.4 | Owner API: full DRF CRUD for sites, pages, events, promos, placements; owner-scoped, superuser only; `sites/<id>/stats/` | DONE |
| F-N.1.5 | Snippet at `/counter/c.js`: records a view, fills `data-counter="views"/"uniques"` (page or `data-counter-scope="site"`), `data-counter-click`, `counter.track()`, anonymous visitor id in localStorage, silent on localhost | DONE, checked cross-origin in a real browser |
| F-N.1.6 | Dashboard: sites with totals, add a site, site page with tiles, 30-day bars, top pages, ready-to-paste snippet, edit and delete | DONE, screenshot checked at 390px |
| F-N.1.7 | Tests: 42, refusals first (anonymous, non-superuser, other owner's site, forged key, owner/key not settable) | DONE |

Notes: no raw IP is stored, only a salted hash. Snippet origin is always
`COUNTER_PUBLIC_ORIGIN` (default `https://babook.co.il`) so a copy from dev
never points at localhost. Not deployed.

## SPR-N.2: promos `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-N.2.1 | Snippet renders a promo into `[data-counter-promo]` from `/api/promo/`, records `promo_shown` and `promo_click` | TODO |
| F-N.2.2 | Dashboard screens for promos and placements, with click-through rate | TODO |

## SPR-N.3: track this site `TODO`

| ID | Feature | Status |
| --- | --- | --- |
| F-N.3.1 | "Track this site" button hands Claude a ready job (site, repo, local path, snippet); Claude inserts it, commits and pushes; sets `snippet_installed_at` | TODO |
| F-N.3.2 | Seed Avi's existing sites list from his repos | TODO |

## Later

Sharing with other people (loosen `access.can_use`; every queryset is
already owner-scoped), daily rollup if queries slow down, per-referrer stats.
