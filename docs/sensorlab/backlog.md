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
| **C — Sensor access layer** | SL-C1 … SL-C2 | 🔵 in progress — spike passed |
| B — Curriculum and authoring | SL-B1 … SL-B4 | 🔶 SL-B1 done |
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

### SL-A3 — The REST platform ✅

Marker: `sprsl3`

- [x] `sensorlab/api/`: `__init__.py` (the router), `serializers.py`,
      `pagination.py`, `profile.py`, `schema.py`.
- [x] URL convention fixed: everything under `/sensorlab/api/`.
- [x] Pagination fixed once for the app (25, max 100) so SL-B2's resources
      do not each invent their own.
- [x] **Documented** (Rule 6): the browsable API, plus a schema endpoint
      **derived from the router registry** rather than hand-written — so
      registering a resource in SL-B2 documents itself with no edit here.
- [x] `GET/PUT/PATCH /sensorlab/api/profile/me/`, proven end to end against
      a running server, not only the test client: signed in through the
      real form, `PATCH {"language": "he"}` returned `he` and flipped
      `text_direction` to `rtl` — the exact mechanism SL-A5 drives.
- [x] 10 tests (9 red first).

**Decisions recorded:**

- **The error shape is DRF's own, adopted rather than re-invented.** A
  custom envelope would need `EXCEPTION_HANDLER` in *project-wide*
  settings, which Rule 2 forbids — changing it would change memz and
  matazim too. So the convention is to match what DRF already does
  consistently and to **say so in the schema**, rather than to build a
  SensorLab-only wrapper every client and test then has to know about.
- **No `viewsets.py` or `permissions.py` yet.** The backlog listed them
  because memz has them; creating them empty would be scaffolding for its
  own sake. They arrive in SL-B2 with the first resource that needs them.
- **`profile/me/` resolves from `request.user`, and there is no
  `/profiles/<id>/` route at all.** One person's row is not a URL guess
  away from another's, and the view needs no object-level permission class
  to guarantee it. Tested.
- **Streaks, freezes and scores are read-only through the API.** A client
  that can PATCH its own streak makes Epic L's leaderboards fiction. The
  browsable API's HTML form shows this visually: `Language` is the only
  editable field on the page (`sl-a3-browsable-api.png`).

*Nothing surprising in the render this time* — the first sprint of the
three where looking at it did not find a bug. The one Hebrew string on the
API page is `עברית`, the Hebrew language's own name in the switch, which
is correct in any locale.

### SL-A4 — The design system ✅

Marker: `sprsl4`

Spec §7, made real. Mockups: `docs/sensorlab/design/`.

- [x] Tokens as CSS custom properties, one set per mode, with instrument
      mode as a **single scoping class that swaps the same token names** —
      a screen opts in rather than restyling itself. A test forbids a
      parallel `--sl-dark-*` set, which would defeat the whole idea.
- [x] Rubik with its fallback stack; the type scale; `.sl-tnum` for every
      live or measured number.
- [x] Components: step rail, card, primary/quiet/danger buttons, chip,
      stat readout, chart frame, bottom nav, plus form fields and the
      toast/dialog surfaces.
- [x] **Logical properties throughout, enforced by a test** rather than
      remembered — `padding-left` survives a mirror still pointing the old
      way, silently, and SL-A5 is about to mirror everything.
- [x] The chart rule lives in a **`{% chart %}` block tag**, not a CSS
      class: `dir="ltr"` is emitted by the component, so a lab written in
      Epic G cannot forget §7.7. Tested over every chart on the page.
- [x] `/sensorlab/design/` — every component in both modes, behind the gate.
- [x] `sensorlab.toast()` / `.confirm()` / `.editInPlace()`, and no native
      `alert`/`confirm`/`prompt` anywhere.
- [x] **Guard: no tap target under 44×44px** across all five pages. It was
      red against the SL-A1–A3 pages before this sprint's CSS, so it caught
      something real rather than passing vacuously.
- [x] **Guard: no native dialog ever fires** — real browser, dialog listener
      armed, SensorLab's own confirm asserted to appear instead.
- [x] **Guard: no page scrolls sideways at 390px.** A phone-only app that
      scrolls sideways is broken, not imperfect.

**Done:** 10 tests. Demo: `sl-a4-reference.png`, `sl-a4-instrument.png`,
`sl-a4-confirm.png`.

*The bug that only rendering caught — three sprints out of four now.* In
instrument mode the big `9.81` readout was almost invisible: dark grey on
near-black. `.sl-instrument` redefined every token correctly and the
file-level token test passed, because **redefining a custom property is not
the same as using it**. `color` is inherited: `body` had already resolved
`var(--sl-ink)` to the light mode's dark ink, and that value inherited
straight through the dark scope. Every component that deliberately sets no
colour of its own — which is most of them — kept the wrong one. The scope
now applies its own tokens (`color`, `background`), and the guard measures
**computed luminance in a browser**, which is the only place the difference
between "declared" and "applied" shows up at all. Red first: text 0.101
against ground 0.065. After: 0.920 against 0.065.

*And one about the tests themselves.* The `--sl-dark-*` guard first failed
on the stylesheet comment **explaining** the rule it enforces. A guard that
reads the documentation instead of the code is worse than no guard, because
it fails for reasons unconnected to the thing it protects. It strips
comments now, and `_code()` carries that reasoning.

*Worth noting for the process:* SL-A1 leaked template syntax, SL-A2 showed
Hebrew labels on an English page, SL-A4 had invisible text. All three were
appearance, and unit tests have no opinion about appearance. The four
browser guards added here are the first things in this app that can fail
for those reasons.

### SL-A5 — Bilingual plumbing ✅ — Epic A complete

Marker: `sprsl5`

- [x] SensorLab's interface copy in `sensorlab/strings.py`, both languages
      side by side, read through a `{% t "key" %}` tag.
- [x] **Activate the profile's language for the request** — the requirement
      SL-A2 uncovered. `SensorLabLanguageMiddleware`, path-scoped to
      `/sensorlab/`, using `translation.override` so nothing leaks to the
      next request on the same worker. Tested from both sides: the language
      is restored afterwards, and no project-wide setting changes.
- [x] `dir` driven by the language; the switch reachable **without an
      account**, because otherwise the sign-in page itself could not be read
      in Hebrew. Signed in, it also writes the profile, so the choice
      follows the person to a new device.
- [x] Profile beats a stale session value; an unknown language is a 404.
- [x] Mirroring verified live: the switch sits at x=314 in English and x=16
      in Hebrew on a 390px page, 44px tall in both.
- [x] §7.7 proven: the chrome mirrors, and every chart still carries
      `dir="ltr"`.
- [x] 13 tests. Demo: `sl-a5-en.png`, `sl-a5-he.png`, `sl-a5-he-login.png`.

**Decision recorded: no gettext, deliberately.** `LOCALE_PATHS` is
configured on this project but there is no `locale/` directory, no `.po` or
`.mo` anywhere in the repo, and `msgfmt` is not installed here — the Hebrew
apps on this site are Hebrew because their templates are written in Hebrew.
Adding gettext for SensorLab would mean a build step needing GNU gettext
binaries present both here and on Render, for exactly two languages whose
copy this app already owns. So the interface uses the **same paradigm the
data model already chose for content** (`data_model.md` §11: two named
languages, stored side by side) — one bilingual mechanism in the app rather
than two. Django's *own* strings are the exception that genuinely needs the
real machinery, and the middleware is what gives it to them.

*A fix from SL-A2 became a bug here.* Giving the forms SensorLab's own copy
correctly stopped Django's Hebrew labels appearing on the English page — but
that copy was English-only, so the moment the rest of the app became
bilingual, the Hebrew sign-in page had Hebrew headings and buttons above
English field labels. Found by looking at it. The forms now read the same
catalogue as everything else and are told the request's language. The
general lesson: a fix is correct relative to the assumptions around it, and
those assumptions moved.

*And a test that emptied its own input.* The helper exempting "text marked
as another language" matched **any** element with a `lang` attribute —
including `<html lang="he">`, whose closing tag ends the document. It
stripped the whole page: the Hebrew assertion failed loudly, and the English
one **passed for the wrong reason**, with nothing left to search. A helper
that empties its input is the most dangerous kind of green, and it is only
visible when one assertion using it fails while another passes.

### SL-A4.1 — the invisible front door ✅ (fix, found live)

Marker: `sprsl4`

**A production bug, found by opening the deployed site rather than by any
test.** On `babook.co.il/sensorlab/` the primary call to action — the only
real action on the only public page — was ink text on an ink background: a
solid black rectangle with an invisible label, in both languages.

The cause was specificity in SensorLab's own stylesheet, not the token
system and not the deploy. `.sl-shell a` sets body-link colour and scores
(0,1,1); `.sl-button` scores (0,1,0). So `<a class="sl-button">` inside a
shell lost its colour, while `<button class="sl-button">` kept it. The
reset rule beside it handled only `text-decoration`.

**Why every check passed.** The tap-target guard measures size. SL-A4's
contrast guard looked only at instrument mode's readout. An invisible
button is exactly the right size and structurally perfect. And every
screenshot taken of a primary button through the whole epic happened to be
of a `<button>` — the login page and the design reference both use one. The
single place the app uses an anchor-as-button is the landing page, which is
the first thing a stranger sees.

The guard is therefore general rather than pointed at this page: **every
visible link and button, on every page, in both languages, must not be
written in its own background colour.** It walks up for the first
non-transparent ancestor background, so it catches inherited cases too.

*The wider lesson, and the third of its kind this epic:* structural
assertions have no opinion about appearance. This one is worse than the
earlier two, because it shipped — SL-A1's leaked template syntax and
SL-A2's wrong-language labels were caught before deploy. Looking at a page
is not a formality at the end of a sprint; it is the only check that can
fail for this reason.

---

## Epic A — complete

Five sprints, 49 tests of its own. The app exists and is sealed, has its own
front door, a documented API, a design system, and runs in two languages.

**What remains before the epic can be called done:** the full `pytest` run,
which is this project's epic gate (see "Process weight" above). Not yet run
— the last attempt was stopped at ~85% by decision, and nothing has
verified the whole suite since SensorLab landed.

## Epic C — Sensor access layer 🔵 in progress

Spec §9.3 and the measurements in §4.1. Taken before Epic B on purpose:
everything else assumes a phone will hand a web page its sensors, and that
assumption is cheap to test and expensive to be wrong about.

**The spike is already done and it passed.** `/sensorlab/sensor-check/`,
run on the target Android device (2026-09-18): **|a| = 9.81 m/s² at rest**,
rotation live, camera 480×640 @ 60 fps, no permission gesture demanded.
It also corrected the spec: `devicemotion` delivers **~63 Hz**, not the
200 Hz that had been assumed and drawn on the mockups.

### SL-C1 — one way to open a sensor ✅

Marker: `sprsl6` · 8 tests

- [x] `static/sensorlab/js/sensors.js`: a single way to open a sensor,
      read it, and stop it — so no lab ever talks to `devicemotion` or the
      Generic Sensor API directly.
- [x] **Generic Sensor API preferred, `devicemotion` as the fallback.**
      Not symmetry for its own sake: §4.1 measured `devicemotion` at ~63 Hz,
      and the Generic Sensor API is the only route to more when a lab needs
      it. The module picks, the lab does not.
- [x] Normalised readings regardless of source: `{t, x, y, z, magnitude}`,
      one shape, so analysis code never branches on which API supplied them.
- [x] **The achieved rate is measured, not declared.** A lab asks for a
      rate; the device gives what it gives; the recording records what
      actually arrived. §4.1 is exactly why: the assumed figure was three
      times the real one.
- [x] Capability detection per sensor, distinguishing the three states that
      matter — **present / absent / present-but-silent**. The last is the
      one that needs a name: the spike found `DeviceMotionEvent` exists on a
      desktop with no accelerometer in it and simply never fires.

*A test seam, stated rather than hidden.* `sensors.js` carries
`window.__slFake*` globals so a browser test can stand in a fake source.
Test hooks in shipping code are normally a smell; this one is deliberate
and documented in the file. The silent-sensor case cannot be reproduced on
a device where the sensor works, and no CI machine has an accelerometer at
all — so without a seam the single most important behaviour here would be
the least tested. Inert unless a test sets it. Worth revisiting as an
injected source factory if it ever grows.

*The same mistake, twice.* The guard forbidding raw sensor APIs in
templates failed on the comment in `base.html` **explaining why raw sensor
APIs are forbidden**. SL-A4's `--sl-dark-*` guard had already failed on the
stylesheet comment documenting its own rule. Named now as a shape rather
than patched again: **a guard that scans source text will eventually scan
the sentence describing it.** Explaining a rule beside the code it governs
is good practice, so the fix belongs in the guard every time — read code,
never prose. Both now strip comments first.

### SL-C2 — asking, refusing, and being refused ✅ — Epic C complete

Marker: `sprsl7` · 16 tests

Marker: `sprsl7`

- [x] The consent flow spec §2 commits to: explicit, visible, per-sensor,
      never silent — the trust feature, not a footnote.
- [x] A denied permission is a first-class state with a way back, not an
      error page.
- [x] A lab that needs a sensor this device lacks is **refused clearly**
      (spec §1: no degradation tier) rather than started and broken.
- [x] The capability report becomes a real screen, replacing the spike page.

**The gate this app imposes on itself.** On Android the browser asks
nothing — a page may read the accelerometer the moment it loads, which the
spike confirmed. `request()` therefore refuses with `needs-consent` and
takes **zero readings** before permission exists. That is the assertion
that matters: if the sensor starts and a dialog appears afterwards, the
data was already collected and the gate is theatre.

`SensorConsent` is per sensor, and a withdrawal **keeps the row** and
stamps `revoked_at` — "agreed Tuesday, withdrew Friday" is the honest
record, and deleting it would read as though they never agreed at all.

*Three bugs, all found by looking at the screen, all the same species —
something true in the markup or the model, quietly overridden elsewhere:*

1. **The screen built to refuse honestly was lying.** It told a machine
   with a camera and microphone that it had neither, because the module
   knew four sensors while the model knew ten and anything unlisted fell
   through to `absent`. A hardware claim the code had never checked. All
   fourteen tests passed while it was true, because none asked what the
   *page says* about a sensor the module cannot probe.
2. **A missing vocabulary made it guess.** `enumerateDevices()` reports
   device kinds with no permission and no labels, so camera presence *is*
   knowable — but knowing hardware exists is not knowing it works, so
   `working` and `silent` would have been inventions too. Hence a fourth
   state, **`present`**: it is there, we have not opened it, and saying
   more would be making things up. It is also the right state for consent
   to sit behind — "there, needs your permission to test".
3. **`[hidden]` did not hide.** `.sl-button` sets `display: inline-flex`,
   which outranks the browser's own `[hidden] { display: none }` — so
   **every** button in the app was immune to being hidden, and the sensors
   screen offered "Allow" on sensors that were not answering. The same
   shape as SL-A4.1's invisible front door: our stylesheet defeating what
   the markup said. Fixed app-wide, with a guard.

*And two wasted diagnostic cycles worth remembering.* I grepped a **login
redirect** for a string and concluded the template was stale — the page is
behind the gate, so curl never saw it. Then I trusted an HTTP 200 from a
**zombie server** while a second one held the port. Both are the same error
as the bugs themselves: measuring something adjacent to the thing I
actually wanted to know.

---

## Epic C — complete

Two sprints, 24 tests, plus the public spike that started it. The premise
is proven on real hardware, the layer exists, and nothing is read from a
person's phone without them saying yes.

---

## Epic B — Curriculum and authoring

Spec §9.2.

### SL-B1 — The content models and admin authoring ✅

Marker: `sprsl8` — 14 tests, all green.

**A note on the markers in this epic.** They originally read `sprsl6` and
`sprsl7`, written when B was expected to run before C. C ran first, took
those numbers, and left B's plan quietly pointing at another epic's tests.
Renumbered here rather than left to be discovered by whoever ran
`-m sprsl6` expecting content models and got the sensor layer.

- [x] `Track`, `Lab`, `ContentBlock`, `PredictionQuestion`,
      `PredictionChoice`, `ExperimentConfig`, `SensorRequirement`,
      `AnalysisConfig` per `data_model.md` §3–4, each authored string as
      `_en` + `_he` with the language-resolving helper (falls back to the
      other language rather than rendering blank).
- [x] `Lab.mode` and the sensor list as `TextChoices`, not tables.
- [x] `Lab.prerequisite_lab` self-FK for unlocking.
- [x] `Track.published` / `Lab.published` managers — authoring happens
      against the live database, so "written" and "shown" have to be
      different states or a student meets a lab mid-sentence.
- [x] Admin with **inlines so one Lab is authored on one page**.
      `SensorRequirement` is the one exception: it hangs off
      `ExperimentConfig`, not `Lab`, and Django does not nest inlines, so
      the sensor list is one click deeper. Same for a question's choices.
- [x] **Decision settled (was: needed from Avi).** Avi left this to me
      three times, so I decided it — see below.
- [x] **Decision recorded:** admin-only authoring for now; no in-app
      author/teacher role (`data_model.md` §12).
- [x] **The authoring page is opened, not just registered.** `manage.py
      check` validates an inline's field names, and the registration
      assertion checks the four inlines are attached — neither loads the
      page. Seven bugs in this app so far passed every structural assertion
      and were obvious the moment somebody looked, so the one screen this
      sprint ships has a test that renders it and looks for each section by
      the name an author will read. It also asserts the old
      `default_sample_rate_hz` label is gone, because a rename that misses
      the admin label renames nothing an author can see.

#### The rename: `default_sample_rate_hz` → `requested_hz`

Carried out of SL-C1. Spec §4.1 asked a real phone for 200 Hz and got 63,
and `sensors.js` already keeps `requestedHz` and `achievedHz` apart for
exactly that reason. The data-model name predated the measurement and read
like a setting the app controls; it never was one. A field name is the
documentation most people actually read, so it now says "asked for".
`data_model.md` §4.3 and its ER diagram were amended in place rather than
left to disagree with the code.

#### Decision: `ContentBlock` bodies are Markdown, with raw HTML escaped

Open decision 1, closed. Implemented in `sensorlab/models.py`
(`render_markdown`) and asserted by `test_authored_html_is_inert`.

**Markdown, not plain text**, because teaching prose needs emphasis, lists
and the occasional table, and because `markdown` is already a dependency of
this site — `app/blog.py` and `app/forum_views.py` both use it with the same
three extensions. Nothing new to install, and one Markdown dialect across
the whole site rather than two.

**Raw HTML escaped, not sanitised.** The usual answer is to allow a
restricted HTML subset and clean it with `bleach`. **`bleach` is not
installed here, and adding a dependency is not mine to do**, so the choice
was between shipping unsanitised HTML and shipping none. Escaping `& < >`
*before* Markdown converts means no HTML is ever produced from author
input, so there is nothing to sanitise. Markdown reads `&lt;` as an entity
and passes it through untouched, which is why the escape survives
conversion — checked against the real library rather than assumed.

**Why bother, when only admins can author?** Because that is temporary.
`data_model.md` §12 anticipates a teacher role, and by then the course will
be written. A content format is cheap to choose now and expensive to change
once there is content in it — which is the whole reason this decision was
flagged as blocking rather than deferred.

**What Markdown does *not* carry.** Formulas, images, video and callouts
stay their own `ContentBlock.kind` values, not markup inside prose. A
formula that is a `kind` can be rendered differently in instrument mode,
translated independently, and restyled later; a formula that is HTML inside
a paragraph is frozen the day it is typed.

### SL-B2 — The curriculum API ⬜

Marker: `sprsl9`

- [ ] Documented CRUD for all eight resources, nested where the shape calls
      for it.
- [ ] `GET /sensorlab/api/tracks/` — the track list.
- [ ] `GET /sensorlab/api/labs/<slug>/` — one lab with **all five steps
      assembled in a single response**, the endpoint Epic D's runner will
      consume.

### SL-B3 — Free Fall, seeded once ⬜

Marker: `sprsl10`

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

Marker: `sprsl11`

- [ ] Track list and lab overview, built on SL-A4's design system, with
      real seeded content.
- [ ] Screen-contract tests for both, in both languages and both
      directions, in their empty and populated states.

---

## Open decisions

Carried here so they are not lost in prose.

1. ~~**`ContentBlock` body format**~~ — **closed in SL-B1**: Markdown, with
   raw HTML escaped before conversion. Reasoning under SL-B1.
2. **Group gate** — recorded as "not for now" (SL-A2). Revisit only with a
   stated reason.
3. **Authoring role** — admin-only for now (SL-B1). An in-app teacher role
   is unmodelled and would be its own epic.
4. **Epic J (video motion tracking)** — flagged in spec §9.3 as the
   strongest candidate to cut. Decide before Epic H closes, not at J's gate.
