# SensorLab — Backlog

Sprints and their status. With [spec.md](spec.md) this is one of the **two
sources of truth** for where SensorLab stands; they are updated together
(`the_manager.md` Cardinal Rule 5). Epic scope lives in spec §9; this file
tracks the work.

---

## Process weight for this app

`building_an_app.md` says process weight scales to the app's size and that
the choice is made **explicitly per app**, so here it is.

**Kept:**

- `spec.md` + `backlog.md` as the two sources of truth, updated together.
- **TDD**: tests written first, seen red, then implemented. Tests in
  `tests/`, one pytest marker per sprint (`sprsl1`, `sprsl2`, …), matching
  this repo's existing convention.
- **Screen-contract tests**, in a SensorLab-scoped form. Kept deliberately:
  this app has many screens × two languages × two text directions, which is
  precisely where silent breakage lives.
- **Regression at the end of each EPIC, not each sprint** (Avi, 2026-09-18).
  A sprint closes on its own marker being green; the full `pytest` run is
  the gate on the epic. The trade is deliberate: the suite takes long
  enough that running it nine times across Epics A and B costs more than
  the earlier warning is worth at this stage. The cost is a wider bisect
  if something does break — accepted, and revisited if it bites.
- A dashboard ([dashboard.html](dashboard.html)), updated each sprint.

**Dropped, on purpose:**

- REQ-ID / F-ID bookkeeping and a separate `test_plan.md`. The main site
  carries those because it is a multi-sprint product with a compliance
  surface; SensorLab's features are described in prose here and traced by
  sprint marker instead.
- A per-sprint written post-mortem. Lessons go into the sprint's entry here,
  or into `building_an_app.md` when they generalise.

**Unchanged from the site's rules:** no `git push` without Avi's explicit
say-so, no `pip install` (dependencies go in `requirements.txt` and Avi
runs pip), `env\Scripts\activate` for everything Python, and
`manage.py migrate sensorlab` rather than a blanket migrate (Rule 5).

---

## Status at a glance

| Epic | Sprints | Status |
|---|---|---|
| **A — Infrastructure and look and feel** | SL-A1 … SL-A5 | 🔵 in progress |
| **B — Curriculum and authoring** | SL-B1 … SL-B4 | ⬜ not started |
| C — Sensor access layer (risk spike) | tbd at gate | ⬜ |
| D — The lab runner | tbd at gate | ⬜ |
| E — Predict | tbd at gate | ⬜ |
| F — Capture | tbd at gate | ⬜ |
| G — Analysis | tbd at gate | ⬜ |
| H — Lab notebook | tbd at gate | ⬜ |
| I — AI tutor | tbd at gate | ⬜ |
| J — Video motion tracking | tbd at gate | ⬜ (candidate to cut) |
| K — Remote / multi-device capture | tbd at gate | ⬜ |
| L — Groups, sharing and gamification | tbd at gate | ⬜ |
| M — Content build-out | tbd at gate | ⬜ |
| N — PWA and deploy | tbd at gate | ⬜ |

Legend: ⬜ not started · 🔵 in progress · ✅ done · 🚫 blocked

---

## Epic A — Infrastructure and look and feel

Spec §9.1. Sprint order is dependency order: nothing here depends on
anything later.

### SL-A1 — The app exists, and it is walled off ✅

Marker: `sprsl1`

- [x] Django app `sensorlab`: `models.py`, `views.py`, `urls.py`, `apps.py`,
      `errors.py`, `migrations/`. No migration yet — nothing is modelled
      until SL-A2, and an empty `0001` would be noise.
- [x] Mounted in `mysite/urls.py` as `sensorlab/` with namespace
      `sensorlab`, **before** the catch-all `app.urls` include.
- [x] `sensorlab/errors.py` with `PREFIX = "/sensorlab/"` and its own
      403/404/500, composed into `mysite/errors.py` by prefix — following
      `memz/errors.py` exactly, so no app learns about another.
- [x] Own `templates/sensorlab/` and `static/sensorlab/`. Own
      `base.html` — never extends babook's, no link back out (Rule 3).
- [x] A shell home view at `/sensorlab/` rendering that base.
- [x] **Isolation test**: nothing under `sensorlab/` imports `app`,
      `matazim`, `ustrip` or `memz`, and no SensorLab template extends or
      includes one of theirs. The encapsulation rule made enforceable
      rather than remembered.
- [x] **Error-wall test**, both directions: an unknown path under
      `/sensorlab/` renders SensorLab's 404, **and** a 404 anywhere else on
      the site does not start rendering SensorLab's shell.
- [x] **Link-containment test**: every `href` on every SensorLab page stays
      under `/sensorlab/`, or is a static/media asset, an in-page anchor, or
      the one deliberate exception — `/accounts/`, the shared allauth flow
      that is how Google sign-in works for every app here.

- [x] **Template-syntax test**: no `{#`/`{%` survives into the rendered
      body. See the bug below — this one was written *after* the failure,
      the way the good tests in this repo usually are.

**Done:** 11 tests, red first (8 failing on a missing module, 2 passing
vacuously as the guards they are, 1 added mid-sprint for the bug below),
then green. `manage.py check` clean. Full regression was started and
**stopped at ~85% by decision, not completed** — it was green to that
point; the real gate is now the end of Epic A. Demo:
`docs/sensorlab/design/sl-a1-shell.png`, rendered at 390px.

*The bug that only rendering caught.* Django's `{# ... #}` is a
**single-line** comment. Spanning one across several lines does not comment
anything out — the engine renders it verbatim, so two explanatory notes in
`base.html` printed as body text across the top of the shell. **Every
assertion in the suite passed while it was broken**: the leaked text never
contained "babook", the screen marker was present, the status was 200, and
no link pointed out of the walls. It was found by looking at the page,
which is exactly why `the_manager.md` requires a screen to be rendered and
looked at once rather than merely asserted about. A guard test now exists.

*Worth considering for `building_an_app.md`* — it generalises beyond this
app, but that file is Avi's to add to, so it is noted here rather than
written there.

*A second, smaller trap, for whoever debugs the next one:* `runserver`
here uses Django's cached template loader, so a template edit is **not**
picked up by a running dev server even with `--noreload`. The fix looked
like it had failed when it had actually worked — the test client (a fresh
process) was green the whole time. Restart the server before disbelieving
a template fix.

*Decision recorded:* CSS in this sprint is the shell minimum only. Tokens
for both modes are declared in `static/sensorlab/css/sensorlab.css` but
used by almost nothing, because anything styled before SL-A4 is something
SL-A4 has to undo. Logical properties (`padding-inline`, …) are used from
the first line so SL-A5's mirroring is automatic.

### SL-A2 — Auth in SensorLab's own chrome, and the profile ✅

Marker: `sprsl2`

- [x] `SensorLabProfile` (one-to-one with `User`): `language`, streak
      fields, per `data_model.md` §2. Migration `0001_initial`, applied
      with `migrate sensorlab` (Rule 5), not a blanket migrate.
- [x] Created **on demand** via `profiles.profile_for()`, not a `post_save`
      signal. Accounts here predate SensorLab by years: a signal covers
      only people who sign up after it is installed and needs a backfill
      for everyone else, and it can be installed in the wrong order.
      `get_or_create` at the point of use cannot. Tested both ways — twice
      in a row yields one row, and an account made before the app existed
      gets a profile simply by arriving.
- [x] Login / signup / logout in SensorLab's own look, against the shared
      `User`, with Google via the site's shared allauth flow.
- [x] Anonymous visitors meet **SensorLab's** login page. `login_url` is
      passed explicitly rather than leaning on the project-wide
      `LOGIN_URL` — which is unset here, so Django's default would have
      sent them to babook's `/accounts/login/`. There is a test for exactly
      that redirect.
- [x] **Decision recorded:** no extra Group gate. A login is what "closed"
      means for now; if that changes the reason gets written down then.
- [x] **Decision recorded:** `/sensorlab/` stays **open** as a front door
      that says what this is and offers a way in. Everything past it —
      starting with `/sensorlab/lab/` — needs an account. This is the one
      place the app is deliberately not closed.

**Done:** 17 tests (13 red first), plus SL-A1's 11 still green — 29 total.
`manage.py check` clean. Demo: `sl-a2-landing/login/signup/lab.png`,
rendered at 390px, signed in through the real form rather than
`force_login`.

*The bug that only rendering caught — again.* The login page's field labels
came out in Hebrew: "שם משתמש", "סיסמה". This project is Hebrew-first
(`LANGUAGE_CODE = "he"`), so Django's own `AuthenticationForm` and
`UserCreationForm` render their built-in labels through the **site's**
catalogue, inside a page whose `<html lang>` said `en`. Every test passed
while it was broken.

The finding is bigger than the labels, and it changes SL-A5's scope:
**SensorLab cannot inherit the site's language at all.** Its default is
English, its real language is per-profile, and the project's global setting
is neither. SensorLab's forms now own their copy outright. What is *not*
fixed: Django's validation messages ("This field is required") still come
from the site's catalogue, because they are raised inside Django rather
than declared by us — so **SL-A5 must activate the profile's language for
the request**, which is now a requirement of that sprint rather than an
implementation detail of it.

### SL-A3 — The REST platform 🔵 next

Marker: `sprsl3`

- [ ] `sensorlab/api/` package following `memz/api/`: `serializers.py`,
      `viewsets.py`, `permissions.py`, `schema.py`.
- [ ] URL convention fixed: everything under `/sensorlab/api/`.
- [ ] DRF configured for this app: permission classes, pagination, and one
      consistent error shape.
- [ ] **Documented** (Rule 6): browsable API + a schema endpoint at a
      stated path.
- [ ] `GET/PATCH /sensorlab/api/profile/me/` — proves the stack end to end,
      and is where the language switch will persist.
- [ ] Test: an anonymous request is refused, an authenticated one gets its
      own profile and can change its language.

**Done when:** the API root is reachable and documented, and `profile/me/`
round-trips a language change.

### SL-A4 — The design system ⬜

Marker: `sprsl4`

Spec §7, made real. Mockups: `docs/sensorlab/design/`.

- [ ] Tokens as CSS custom properties, one set per mode — pedagogical and
      instrument — with instrument mode as a single scoping class that swaps
      the set, so a screen opts in rather than restyling itself.
- [ ] Rubik loaded with its fallback stack; the type scale; a
      tabular-numerals utility for every live or measured number.
- [ ] Components: step rail, card, primary/secondary button, chip, stat
      readout, chart frame (axes/grid/legend primitives), bottom nav.
- [ ] **Logical CSS properties throughout** (`padding-inline`, …) from the
      start, so SL-A5's mirroring is automatic rather than a second pass.
- [ ] Every chart primitive wraps itself `dir="ltr"` (§7.7) — the rule lives
      in the component, not in each caller's memory.
- [ ] A **design reference page** inside the app rendering every component
      in both modes and both directions.
- [ ] `sensorlab.toast()` / `.confirm()` / `.editInPlace()` — no native
      `alert`/`confirm`/`prompt` anywhere (§7.4).
- [ ] **Guard test: no tap target under 44×44px.** matazim and ustrip both
      have one; ustrip's exists *because* "phone-first" was an intention
      with nothing checking it, and it shipped 20px checkboxes.
- [ ] **Guard test: no native dialog ever fires** — driven through a real
      browser with a dialog listener armed, the way ustrip's does, since
      nothing else catches that regression.

**Done when:** the design reference page renders every component in both
modes and both directions, and both guard tests are green.

### SL-A5 — Bilingual plumbing ⬜

Marker: `sprsl5`

- [ ] Django i18n for interface strings + the Hebrew catalogue. (Authored
      *content* is `_en`/`_he` model fields instead — that arrives in SL-B1.)
- [ ] **Activate the profile's language for the request** (found in SL-A2).
      Without it, Django's own strings — form labels, validation errors —
      render in the *site's* language (`he`) regardless of what SensorLab
      is serving. SensorLab's language is neither the site setting nor the
      browser's guess. Must not leak across requests: activation belongs in
      SensorLab's own middleware or a `with translation.override(...)`,
      never a bare `activate()` in a view.
- [ ] `dir` driven by the profile's language; the language switch control
      wired to `PATCH profile/me/`.
- [ ] Mirroring verified across every component on the reference page.
- [ ] Test: the same screen in both languages, asserting the chrome mirrors
      **and** that a chart's axis/numerals do not (§7.7).

**Done when:** the app runs end to end in Hebrew with the layout mirrored,
charts unmirrored, and the switch persisting across sessions.

---

## Epic B — Curriculum and authoring

Spec §9.2.

### SL-B1 — The content models and admin authoring ⬜

Marker: `sprsl6`

- [ ] `Track`, `Lab`, `ContentBlock`, `PredictionQuestion`,
      `PredictionChoice`, `ExperimentConfig`, `SensorRequirement`,
      `AnalysisConfig` per `data_model.md` §3–4, each authored string as
      `_en` + `_he` with the language-resolving helper (falls back to the
      other language rather than rendering blank).
- [ ] `Lab.mode` and the sensor list as `TextChoices`, not tables.
- [ ] `Lab.prerequisite_lab` self-FK for unlocking.
- [ ] Admin with **inlines so one Lab is authored on one page**.
- [ ] **Decision needed from Avi:** are `ContentBlock` bodies plain text,
      Markdown, or a restricted HTML subset? Cheaper to settle before
      content is written than after.
- [ ] **Decision recorded:** admin-only authoring for now; no in-app
      author/teacher role (`data_model.md` §12).

### SL-B2 — The curriculum API ⬜

Marker: `sprsl7`

- [ ] Documented CRUD for all eight resources, nested where the shape calls
      for it.
- [ ] `GET /sensorlab/api/tracks/` — the track list.
- [ ] `GET /sensorlab/api/labs/<slug>/` — one lab with **all five steps
      assembled in a single response**, the endpoint Epic D's runner will
      consume.

### SL-B3 — Free Fall, seeded once ⬜

Marker: `sprsl8`

- [ ] The Free Fall / measuring-g lab as real content in **both
      languages** — the same content the mockups show.
- [ ] A management command that is a **one-time import**: checks whether the
      content exists, leaves it alone if it does, and logs that it did.
      Not a preference — `render.yaml`'s start command re-runs every seed
      command on **every deploy**, and ustrip's version deleted and
      recreated rows each time, which would have destroyed real edits the
      moment anyone could edit that table.
- [ ] **A test that runs the command twice** and asserts nothing the app
      could have created or changed is touched the second time. A test that
      only checks the first run does not catch this.

### SL-B4 — The first real screens ⬜

Marker: `sprsl9`

- [ ] Track list and lab overview, built on SL-A4's design system, with
      real seeded content.
- [ ] Screen-contract tests for both, in both languages and both
      directions, in their empty and populated states.

---

## Open decisions

Carried here so they are not lost in prose.

1. **`ContentBlock` body format** — plain text / Markdown / restricted HTML.
   Needed by SL-B1.
2. **Group gate** — recorded as "not for now" (SL-A2). Revisit only with a
   stated reason.
3. **Authoring role** — admin-only for now (SL-B1). An in-app teacher role
   is unmodelled and would be its own epic.
4. **Epic J (video motion tracking)** — flagged in spec §9.3 as the
   strongest candidate to cut. Decide before Epic H closes, not at J's gate.
