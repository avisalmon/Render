# SensorLab — Spec

> **Status: kickoff complete through step 4** of the sequence in
> `docs/building_an_app.md`. §1–6 are the capability picture (step 2,
> enriched from a competitive/landscape research pass), §7 is the visual
> design system, §8 the encapsulation contract, and §9 the build plan in
> epics (step 4) — written on Avi's go-ahead of 2026-09-18, which takes
> `docs/sensorlab/data_model.md` (step 3) as accepted.
>
> Epics A and B in §9 are specified to the point where development can
> start. C–N carry a title and scope only, each to be detailed at the gate
> before it begins. **Next: `backlog.md` + the app dashboard (step 5).**

## 1. What SensorLab is

SensorLab is a live, gamified physics-experiment lab that runs entirely in
a phone's browser — no native app, no install. Its lab equipment is
whatever the phone already carries: camera, accelerometer, gyroscope,
magnetometer, barometer, light/proximity sensors, microphone, GPS. A
physics lab in your pocket.

The closest existing analog is **phyphox** (RWTH Aachen University) — free,
open, ~70 built-in experiments, and the reference point for what a
phone-sensor physics app is expected to do. SensorLab's ambition is to
match that sensor/analysis depth while adding two things no reviewed
competitor has: **a persistent AI tutor**, and a **structured
predict → experiment → analyze pedagogy** built in from the start rather
than left to the teacher.

The app is **bilingual, English and Hebrew, with a switch the user can flip
at any time** — not a build-time choice of one locale, and not inferred
only from the browser once and then fixed. Every screen, every track,
every lab, and the chat companion itself all need to work in both
languages, including the layout direction (LTR for English, RTL for
Hebrew) that comes with the switch.

It is mobile-web only — Android phones specifically, not desktop and not
iOS/Safari. That is a decision made before the first line of code, from
real browser-API limits: iOS requires a permission prompt behind a direct
user gesture for every motion-sensor read, and has no Generic Sensor API
at all for some of the sensors labs will want. Building for Android only
means the app can rely on sensor access working the same way everywhere,
rather than branching its entire design around a platform gap.

**No fallback tier for old or low-end phones.** SensorLab targets a
reasonably modern Android device and does not try to gracefully degrade
labs around a missing sensor on older hardware. That is a deliberate
scope decision, not an oversight — it keeps every lab's design simple
("this phone has what this lab needs") instead of branching every
experiment around device fragmentation.

## 2. Sensing through the web is the advantage, not a limitation

Doing all of this in a browser tab, with no app-store install, is
SensorLab's actual bet — and the thing worth getting right on purpose
rather than treating as a constraint to work around:

- **Getting Android's browser sensor permission UX right is a deliberate
  product goal.** Research surfaced a real, documented problem in this
  space: some mobile browsers have historically exposed motion/orientation
  data with **no permission prompt at all**, which is how fingerprinting
  and covert tracking demos work. A native app never has to think about
  this — the app-store install screen handles consent once, up front.
  SensorLab, as a web app, inherits that exposure and turns solving it
  cleanly (explicit, visible, per-sensor consent, never silent access)
  into a trust feature worth being visibly good at, not a footnote.
- **No install, no app-store review cycle, one link to share** — a teacher
  or a curious user is one tap away from a running experiment. This is
  the actual leverage of doing it through the web at all, and it is why
  solving the sensor-access problem well is worth the effort instead of
  retreating to a native app.

## 3. Shape: tracks, labs, and a fixed methodology

Content is organized into **tracks** (מסלולים) — each track is one
physics topic. A track holds one or more **labs**, each lab being a single
experiment. Every lab follows the same five-part shape, whatever the
subject — a structure grounded in **Predict-Observe-Explain (POE)**, an
established physics-education pedagogy, extended with an explicit
teaching step before the prediction is asked for:

1. **Intro** — what the topic is, before touching the phone at all: the
   hook, the everyday framing of why this is worth an experiment.
2. **Learn** — the actual instructional content: the concept, the theory,
   the formula, worked examples — taught before the participant is asked
   to commit to anything. Predicting without having learned the concept
   is a guess; predicting after learning it is a hypothesis.
3. **Predict** (formerly "Hypothesis") — a quiz, a question, a riddle, or
   (where the lab calls for it) **sketching a predicted curve directly on
   a graph's axes** before any data exists — the participant commits to a
   guess before the experiment runs, not after seeing the result.
4. **The experiment** — the live part: sensor readings, measurements,
   photos, video, or whatever else that specific lab needs from the phone.
5. **Analysis** — what the data actually showed, set directly against the
   prediction from step 3, including overlaying the predicted curve on the
   real one where a graph prediction was made.

A running experiment is also a **lab notebook**: freeform notes and photos
can be attached alongside the live data, so the record reads like an
actual lab report afterward, not just an exported chart.

## 4. Sensor and analysis capabilities

**Sensing:**

- Full sensor roster: accelerometer (raw and gravity-subtracted **linear**
  acceleration as a separate channel), gyroscope, magnetometer/compass,
  barometer, ambient light, proximity, microphone (amplitude and
  frequency/FFT), GPS, and the camera as a sensor (still photo and video).
- **Two sensors captured simultaneously** on one screen where a lab needs
  it (e.g. accelerometer + microphone for a drop/bounce experiment).
- **Signal generation, not just sensing** — tone generator, stroboscope,
  and color generator, for the class of experiments (resonant frequency,
  Doppler effect, strobe-frozen motion) that pure sensing cannot produce
  alone.
- Configurable sample rate, and **threshold-triggered** start/stop/snapshot
  recording (capture the moment of impact automatically, not by a
  student's manual timing).
- **Multi-device, remote/collaborative capture**: one phone's live data can
  be viewed from another browser on the same network — for a teacher
  displaying one student's live experiment to a whole class, or for
  synchronized multi-phone experiments (e.g. two phones measuring the
  speed of sound between them). This is phyphox's single most-cited
  distinctive capability in the field, and SensorLab is building it in
  rather than leaving it out.

### 4.1 Measured, not assumed: what a real phone gives us

Written after running `/sensorlab/sensor-check/` on the target device
(2026-09-18) rather than from documentation. The page reports what the
browser in your hand actually does, and the headline number is the one that
matters: **|a| = 9.81 m/s² at rest**, which is gravity, from real hardware,
through a web page. The premise this whole app rests on is proven.

| measured | value | consequence |
|---|---|---|
| `devicemotion` rate | **~63 Hz** | Not the 200 Hz assumed above and drawn on the mockups. Chrome caps this event near 60 Hz. |
| `\|a\|` at rest | 9.81 m/s² | Correct to three figures — the sensor is real and calibrated. |
| rotation rate | reported live | Gyroscope labs are viable. |
| Generic Sensor API | available | The route to a *higher* rate than `devicemotion` allows, if a lab needs one. |
| camera | 480×640 @ 60 fps | 60 fps is good for video tracking; the resolution is a default, not a ceiling. |
| explicit permission gesture | not required | Android behaves as expected; no iOS-style per-gesture prompt. |

**What this changes.** A free-fall drop of 1.20 m lasts 0.497 s, which at
63 Hz is about **31 samples** — ample to time the fall window, marginal for
resolving the shape of the impact spike, which is short and could alias.
Two consequences for Epic F: the achieved rate must be **measured and
recorded per recording** rather than assumed, and where a lab genuinely
needs more than ~60 Hz it must come from the Generic Sensor API rather than
`devicemotion`. Neither is a blocker; both are now facts instead of hopes.

**Analysis and visualization:**

- Live scrolling time-series graph with a synchronized data table.
- On-device analysis: FFT/frequency spectrum, curve fitting, slope
  (instantaneous rate of change), and area-under-curve tools.
- **Predict-then-overlay graphing**: the sketched prediction from the
  predict step is overlaid on the real measured curve for direct visual
  comparison during analysis.
- **Video motion-tracking as its own analysis mode**: record video, track
  a point frame-by-frame, and derive position/velocity/acceleration
  graphs from it — the standard method for teaching projectile motion,
  pendulums, and collisions, alongside (not instead of) raw live-sensor
  labs.
- Export: CSV/Excel/JSON, a shareable read-only web link to a result, and
  a portable export of a lab's full record (data, notes, and photos
  together).

## 5. The chat companion

Every track carries its own persistent chat: a saved conversation between
the user and an AI tutor, scoped to that track's topic and aware of the
user's progress and everything they have said in it so far. Its job is to
guide — hints, questions, direction — never to hand over the answer. A
tutor, not an oracle, modeled explicitly on the Socratic contract used by
tools like Khan Academy's Khanmigo: ask what the student has tried, where
they are stuck, and what concept might apply, rather than stating the
answer.

The tutor sees the student's **actual sensor data and results for that
lab**, not just the question text — so its hints can reference the
student's own graph, their own anomaly, their own numbers. No reviewed
competitor has an AI tutor at all; this is SensorLab's clearest
differentiator, not a checkbox feature.

## 6. Individual by default, social by choice

A user works through tracks and labs on their own account by default. On
top of that:

- **Groups** — join others and run an experiment together, including the
  classroom-scale shared/live-view capability described in §4.
- **Sharing** — show a result to someone else via a shareable link.
- **Statistics** — computed over experiments, which means a real result
  gets stored per attempt, not just a pass/fail.
- **Leaderboards, scoped per group** rather than global — the gamification
  research reviewed found leaderboards measurably outperform badges alone
  for motivation.
- **Streaks with a "freeze"/grace mechanism** so a single missed day does
  not tank a user's motivation or standing — the fix Duolingo made after
  learning streak pressure without it drives dropout.
- **Badges** tied to lab-completion milestones and track mastery, as a
  supplement to leaderboards, not a replacement for them.
- An explicit intent to track actual learning signals (hypothesis accuracy
  improving over time, mastery on retakes) alongside engagement metrics,
  so the gamification layer supports the pedagogy instead of hollowing it
  out.

## 7. Design

Settled in conversation and then drawn: seven phone screens of the free-fall
lab exist as a mockup canvas, with the working artboards in
`docs/sensorlab/design/` (`*.dc.html` + `canvas.json`). The canvas is the
picture; this chapter is the rule set, so the rules survive the mockup.

### 7.1 One system, two modes

SensorLab is two products sharing a flow. Intro, Learn, Predict and Analysis
are **learning** screens: warm off-white (`#FAF9F7`), generous spacing,
encouraging. The Experiment step is a **scientific instrument**: near-black
(`#0E1113`), dense, tabular, credible.

Designing all five as a friendly learning app makes the measurements feel
like a toy; designing all five as an instrument makes the teaching cold. So
the mode switches mid-flow — and **the switch is itself the pedagogical
cue**: going dark means you are now taking a real measurement. It is also
practical, since a bright trace on dark reads better outdoors and costs less
battery on OLED during a long capture.

### 7.2 Colour carries meaning, never decoration

The central rule, and the one most likely to be eroded by a well-meaning
later edit:

| | colour | line |
|---|---|---|
| **Prediction** | warm amber `#D08616` | **dashed** |
| **Measured reality** | cool cyan `#0E8E9B` (`#2DD4E0` on dark) | **solid** |
| **Everything structural** | ink `#1A1A18` | — |

Buttons, step rails, progress bars, nav, badges and streaks are **ink**.
Amber and cyan are reserved so completely that when they do appear, they
mean something. The whole pedagogy is "compare what you guessed to what
happened", so that comparison gets the only two accent colours in the
system and nothing else may borrow them.

Two consequences:

- **Dash pattern is load-bearing, not styling.** Predicted curves are
  dashed and measured curves are solid *in addition to* being different
  hues, because roughly 8% of viewers will not reliably separate amber from
  cyan, and for them colour alone would destroy the one comparison the app
  exists to make.
- **Cyan may extend to measurement *apparatus*** — the instrument-mode
  badge, an active sensor chip, the capture control, the trigger line — but
  not to chrome that merely happens to sit nearby. Progress through a
  track is not a measurement.

### 7.3 Type

**Rubik**, one family, loaded from Google Fonts with a system fallback
stack. It was chosen for a reason that outranks taste: it has genuinely
good **Hebrew and Latin** in one family, which a bilingual app needs more
than it needs a display face.

**Live and measured numbers use tabular numerals** (`font-variant-numeric:
tabular-nums`). Without them a readout counting through `9.81 → 10.02`
shifts horizontally as the digit widths change, and a jittering number
reads as a broken instrument.

### 7.4 Phone-first, inherited from ustrip

This app is Android-phone-only, so §0a.1 of `docs/ustrip/spec.md` applies
here as a baseline rather than being re-learned: **44×44px minimum for
anything tappable**, no browser-native `alert`/`confirm`/`prompt`, no
`location.reload()` after an interaction, and every network action
disables its own control until it returns.

Two additions specific to this app:

- **No fake phone chrome.** No painted status bar, no drawn keyboard. On a
  real phone the real ones render on top and a painted copy looks doubled.
- **Feedback you do not have to look at.** Capture start, stop and
  threshold-trigger all fire **haptic + tone**. During a free-fall lab the
  phone is in mid-air or taped to a pendulum; visual-only feedback is
  useless in precisely the moment that matters.

### 7.5 Charts must not lie

Two rules that came out of reviewing the first mockups, where both were
broken:

1. **The geometry must match the arithmetic.** The free-fall band was drawn
   0.481 s wide while labelled 0.497 s — the same number the whole result
   is computed from. A chart that contradicts its own figures teaches the
   student to distrust the app, which is fatal for a measuring instrument.
2. **An axis must be able to contain the event it is armed for.** The live
   chart topped out at 20 m/s² while waiting for an impact spike that
   reaches ~27 — the one moment of interest would have clipped off the top.
   A live axis is sized for the event, not for the resting state.

### 7.6 The instrument is never gamified

Streaks, badges, leaderboards, celebration: all of it belongs **between**
labs — on the home screen, the profile, the result screen. None of it
appears on the Experiment screen.

An oscilloscope with confetti on it stops being believable, and the
credibility of the measurement is the product. This is a hard line, not a
preference.

### 7.7 Bilingual: the chrome mirrors, the data does not

When the language flips to Hebrew the interface becomes RTL: the back
chevron reverses direction and moves to the right, the step rail fills from
the right, text right-aligns, the language pill swaps its active side.

**Charts, numbers and notation do not mirror.** A velocity-vs-time axis
still runs left to right in Hebrew, numerals stay Latin, and `g = 2h / t²`
stays LTR — mirroring any of those would make the physics wrong rather
than localised. The nuance: **words inside a plot are translated, the
geometry is not.** Every chart is wrapped `dir="ltr"` inside an otherwise
RTL page.

A student's own words — notebook entries, free-text predictions, chat
messages — are never translated; they are stored and shown in whatever
language the person wrote them (see `data_model.md` §11).

## 8. Where it sits on this site

SensorLab is a fully encapsulated app on babook's Django project, per this
site's standing rules (`docs/building_an_app.md`): its own Django app, own
templates and static files, own base template and navigation, own docs
directory. Login reuses babook's shared account system (username/password,
Google sign-in) — a user signs in with the account they already have — but
nothing else crosses the wall: no navigation out to babook from inside
SensorLab, no babook chrome inside it.

A SensorLab-specific profile (progress, completed labs, unlocked content,
saved results, comments, streaks, badges) lives in SensorLab's own models,
one-to-one with the shared `User` — never as new fields added to babook's
`User` model.

---

## 9. Build plan — epics

Step 4 of the kickoff sequence, written on Avi's go-ahead of 2026-09-18
("we can now write the spec"), which takes `data_model.md` as accepted.
Epics A and B are specified in enough detail to start development; C–N
carry a title and scope only, and each gets its detail at the review gate
before it starts.

### 9.0 Where the REST API lives

**The API is not an epic. It is part of the definition of done for every
epic that introduces a model** (Rule 6 in `docs/building_an_app.md`):
Epic A builds the API *platform*, and from then on each epic ships its own
models' endpoints as part of itself, with the screens built on top of those
endpoints rather than beside them. This app leans on that harder than
ustrip did — the screens are the API's first consumer by design, not a
retrofit.

Four places plain CRUD does not fit, named now rather than discovered
later:

1. **Sensor payloads.** A 60-second capture at the ~63 Hz this device
   actually delivers is roughly 11,000 readings in one request (the figure
   here was 36,000, computed from an assumed 200 Hz — see §4.1). Consistent with `data_model.md` §6 (one row, the
   payload on it), but the transport needs a deliberate call: one inline
   POST versus a chunked upload, plus a hard size limit. Decided in Epic F.
2. **Verbs, not resources.** "Compute the analysis", "grade this
   prediction", "start a remote session", "ask the tutor". These are DRF
   `@action` routes, named on purpose — never smuggled in as odd `PATCH`es.
3. **Leaderboards have no model behind them** (`data_model.md` §10 —
   computed, not stored), so they are a read-only endpoint backed by an
   aggregate query, not a ViewSet.
4. **Live streaming is not REST at all.** Epic K's REST surface is only the
   session record; the frames are websockets. Nobody should be polling an
   endpoint at sensor rate.

---

### 9.1 Epic A — Infrastructure and look and feel

**What it unblocks:** everything. No other epic can start without the app
existing, and no screen can be built twice because the design system
arrived late.

This epic deliberately carries **both** the plumbing and the visual system.
Splitting them would mean building screens against provisional styling and
revisiting every one of them later.

#### A.1 The isolated app

- Django app `sensorlab`: own `models.py`, `views.py`, `urls.py`, own
  migration chain starting at `0001`.
- Mounted in `mysite/urls.py` **before** the catch-all `app.urls` include.
- Own templates under `templates/sensorlab/`, own static under
  `static/sensorlab/`.
- Own `handler403/404/500`, **composed into the project's single set** of
  error handlers — Django allows only one project-wide handler each, so this
  is a merge, not an addition. This is the step the isolated-app pattern
  specifically warns about.
- **No import of, reference to, or link to any other app** (Rule 2, Rule 3).
  The test: this folder could be lifted into a different site and still work,
  given the one shared login.

#### A.2 Auth

- Reuses babook's shared `User` and auth backend — a person signs in with
  the account they already have (username/password and Google).
- Login, signup and logout pages are rendered **inside SensorLab's own
  chrome**, so nobody sees another app's branding mid-flow.
- `SensorLabProfile` (one-to-one with `User`) ships in this epic rather than
  later, because the language switch needs somewhere to persist and auth
  needs the profile to exist on first login.
- **Decision to make:** is SensorLab open to any authenticated account, or
  gated by a Django auth `Group` created in a migration (the pattern ustrip
  uses)? Spec §1 calls the app "closed", which a login satisfies on its own.
  Recommendation: **no extra group gate for now** — add one when there is a
  reason, and record the reason at the time.

#### A.3 The REST platform

- DRF installed and configured: permission classes, authentication,
  pagination, and a consistent error shape.
- URL convention fixed here: everything under `/sensorlab/api/`.
- **Documented**, per Rule 6: the browsable API plus a generated schema at a
  stated path, so the API can be read without reading view code.
- One real endpoint to prove the stack end to end:
  `GET/PATCH /sensorlab/api/profile/me/` — which is also where the language
  switch persists.

#### A.4 The design system (§7, made real)

- **Tokens as CSS custom properties**, one set per mode: the pedagogical
  palette (`#FAF9F7` ground, ink `#1A1A18`) and the instrument palette
  (`#0E1113` ground), plus the two semantic accents — amber `#D08616` for
  prediction, cyan `#0E8E9B` / `#2DD4E0` for measurement. Instrument mode is
  a single scoping class or attribute that swaps the token set, so a screen
  opts into it rather than restyling itself.
- **Type**: Rubik loaded with its fallback stack, the type scale, and a
  tabular-numerals utility for every live or measured number (§7.3).
- **Components**, built once and reused by every later epic: step rail,
  card, primary/secondary button, chip, stat readout, chart frame
  (axes/grid/legend primitives), bottom nav.
- **A design reference page inside the app** rendering every component in
  both modes and both text directions. Cheap to build, and it makes a
  regression visible instead of theoretical.
- **Enforced, not merely stated** (§7.4): a guard test asserting no tap
  target under 44×44px — matazim and ustrip both have one, and ustrip's
  exists precisely because "phone-first" had been an intention with nothing
  checking it.
- **No native `alert` / `confirm` / `prompt`**: SensorLab's own toast,
  confirm and edit-in-place helpers, following the pattern ustrip landed in
  its Sprint 15 — including a test that drives a real browser with a dialog
  listener armed, since that is the only thing that catches a regression
  here.

#### A.5 Bilingual plumbing

The *plumbing* lives in this epic; the *content* fields arrive with the
models in Epic B.

- Django i18n for interface strings, with the Hebrew catalogue.
- The `dir` attribute driven by the profile's language, and the language
  switch control + the endpoint that persists it.
- **Logical CSS properties** (`padding-inline`, `margin-inline-start`, …)
  throughout, so mirroring is automatic rather than a second stylesheet.
- The standing exception written into the base chart component: every chart
  is wrapped `dir="ltr"` (§7.7) — geometry and numerals never mirror.

#### A.6 Definition of done

A fresh clone, migrated, serves the SensorLab shell at `/sensorlab/`:
a person can sign in through SensorLab's own pages, switch between English
and Hebrew with the layout mirroring correctly, and reach a design
reference page that renders every component in both modes and both
directions. The API root is reachable and documented. The 44px guard test
and the no-native-dialog test are green. Nothing outside `sensorlab/` was
touched except the one URL include and the merged error handlers.

#### A.7 Out of scope for A

Any lab content, any sensor code, any of the five steps, any chart with
real data in it.

---

### 9.2 Epic B — Curriculum and authoring

**What it unblocks:** everything downstream. Until a real lab exists in the
database, none of the runner, capture or analysis work can be tested
against anything.

#### B.1 Models

Per `data_model.md` §3–4: `Track`, `Lab`, `ContentBlock`,
`PredictionQuestion`, `PredictionChoice`, `ExperimentConfig`,
`SensorRequirement`, `AnalysisConfig`.

- Every authored user-facing string carries `_en` and `_he` fields (§11),
  with the single language-resolving helper on each model — falling back to
  the other language rather than rendering blank.
- `Lab.mode` and the sensor list are `TextChoices`, not tables: which
  modalities and sensors the platform supports is a code capability, not
  content someone edits.
- `Lab.prerequisite_lab` (self-FK, nullable) is what backs unlocking, so a
  track can branch later without a migration.

#### B.2 Authoring

- Django admin with **inlines, so one Lab is authored on one page**: its
  content blocks, its prediction questions and their choices, its
  experiment config and sensor requirements, its analysis config.
- **Decision to make:** admin-only authoring, or an in-app author role?
  `data_model.md` §12 flags that no teacher/author role is modelled.
  Recommendation: **admin only for now**, and say so out loud rather than
  discovering the gap when a teacher asks.
- **Decision to make:** are `ContentBlock` bodies plain text, Markdown, or a
  restricted HTML subset? This affects both the authoring experience and
  rendering safety, and it is cheaper to settle before content is written
  than after.

#### B.3 API

- Full documented CRUD for all eight resources, nested where the shape calls
  for it (choices under questions, requirements under the experiment config).
- Two read endpoints shaped for the screens rather than the tables:
  - `GET /sensorlab/api/tracks/` — the track list.
  - `GET /sensorlab/api/labs/<slug>/` — one lab with **all five steps
    assembled in a single response**, which is what the runner in Epic D
    consumes.

#### B.4 The first real lab, seeded once

Free Fall — Measuring g, in both languages: the same content the mockups
show.

- Loaded by a management command that is a **one-time import**: it checks
  whether the content already exists and leaves it alone if it does,
  logging that it did. This is not a style preference — on this site
  `render.yaml`'s start command re-runs every seed command on **every
  deploy**, and ustrip's version of this wholesale-deleted and recreated
  rows each time, which would have silently destroyed a real person's edits
  the moment the app let anyone edit that table.
- **A test that runs the seed command twice** and asserts nothing the app
  itself could have created or changed is touched on the second run. A test
  that only checks the first run does not catch this.

#### B.5 First real screens

The track list and the lab overview, built on Epic A's design system — the
first screens with real data in them, in both languages and both
directions.

#### B.6 Definition of done

Free Fall exists in the database in English and Hebrew, seeded
idempotently with the twice-run test proving it, fully authorable in admin,
readable through the documented API, and rendering as a track list and lab
overview in both languages and both directions.

#### B.7 Out of scope for B

Running a lab, the sketch interaction, capture, analysis. B produces
content and the means to author it, not the experience of doing a lab.

---

### 9.3 Epics C–N — titles and scope

Each gets its detail written at the gate before it starts.

**C — Sensor access layer.** ⚠ The technical risk spike and the app's
actual differentiator. Browser permission UX done deliberately (§2), the
Generic Sensor API with a `DeviceMotion`/`DeviceOrientation` fallback,
per-sensor capability detection, and a clean refusal when a device lacks a
sensor a lab requires (§1: no degradation tier). **Built and proven
standalone, before any flow depends on it** — if real Android devices hold
a nasty surprise, it should surface in week one. *API: none of its own; it
is client-side.*

**D — The lab runner.** The five-step shell — Intro, Learn, Predict,
Experiment, Analysis — with attempt state, the step rail, and
resume-where-you-left-off. *API: `LabAttempt`, plus the step/resume state.*

**E — Predict.** The quiz kinds (multiple choice, numeric, free text) and
the sketch-your-curve-on-empty-axes interaction, which is a custom control
and may warrant its own sprint. Predictions lock when the experiment
starts. *API: `PredictionAnswer`, plus a grade action.*

**F — Capture.** Instrument mode in earnest: live chart, configurable
sample rate, threshold-triggered capture, haptic and tone feedback, the
signal generators (tone, strobe, colour), and persisting a recording. Where
the sensor-payload transport decision in §9.0 gets made. *API:
`SensorRecording`.*

**G — Analysis.** The computations (peak, mean, slope, period, FFT peak,
curve fit, area), expected-versus-measured with tolerance, the
predicted-versus-measured overlay, and export (CSV/JSON plus the shareable
read-only result link). *API: `AnalysisResult` (read + a compute action),
export endpoints.*

**H — Lab notebook.** Notes and photos attached to a running attempt, each
individually editable and deletable. Small. *API: `NotebookEntry`.*

**I — AI tutor.** One persistent thread per track, the Socratic constraint
(guide, never answer), and the tutor seeing the attempt's **actual** sensor
data rather than only the question text — recorded via `context_attempt` so
the conversation is still readable weeks later. *API: `ChatThread`,
`ChatMessage`, plus a send-and-reply action.*

**J — Video motion tracking.** The second analysis modality: video capture,
frame stepping, point tracking, scale calibration, derived
position/velocity/acceleration. **The largest optional epic, and the one to
consider cutting** — it is a second way to do what F and G already do.
*API: `VideoTrackingSession` + file upload.*

**K — Remote / multi-device capture.** One phone captures, other browsers
watch live: join codes, the session record, classroom display, and
synchronised multi-phone experiments. *API: `RemoteSession` for the record
only — the live frames are websockets.*

**L — Groups, sharing and gamification.** `StudyGroup` and membership,
sharing links, streaks with the freeze grace mechanism, badges as a
database catalogue, group-scoped leaderboards, and the learning-signal
metrics that keep the gamification honest (§6). The instrument screen stays
free of all of it (§7.6). *API: `StudyGroup`, `GroupMembership`, `Badge`,
`BadgeAward`, plus a computed leaderboard endpoint with no model behind it.*

**M — Content build-out.** Authoring the rest of the labs — pendulums,
sound and waves, rotation. Content work rather than code, but real work and
on the plan rather than assumed.

**N — PWA and deploy.** Add-to-home-screen installability, an offline shell
where it makes sense, and a deploy scoped to this app (Rule 5: `manage.py
migrate sensorlab`, not a blanket migrate, and no unrelated apps bundled
into the push).

---

### 9.4 What ships first

**A through G is the shippable core**: one track, a few labs, no tutor, no
groups, no video — already a working product worth putting in front of a
student. H through L is where this plan should expect to be re-cut, once
there is something real to react to.

---

*Next: `docs/sensorlab/backlog.md` and the app's dashboard (step 5, Rule 4),
breaking Epics A and B into sprints.*
