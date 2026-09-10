# מט״צים — Backlog

Sprint by sprint. Only the sprint in flight is written out in detail. We decide
the next one when this one closes, not before, so this file never pretends to
know more than we do.

Process is [`docs/the_manager.md`](../the_manager.md), unchanged. Status truth
lives in [`spec.md`](spec.md) and here, updated together. Tests are planned in
[`test_plan.md`](test_plan.md) and registered in the repo-wide
[`docs/regression.md`](../regression.md), because pytest runs one suite over one
Django project.

Standing rule: dev first. Nothing reaches production without Avi's word.

---

## SPR-M.1 — The front door  `DONE, DEPLOYED 2026-09-09`

**Goal:** the app exists, it looks like מט״צים, and it is sealed off from
babook. Design first, functionality later: the home page is built to Litala's
screen 1 with every value hardcoded. No models, no forms, no logic.

**Decisions taken into this sprint (2026-09-09):** photographs supplied by Avi,
everything else drawn as SVG by hand. Typeface is **Rubik**, deliberately not
babook's Heebo, so the two read as different products on sight.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.1.1 | Sever the old presentation | RULE-1, RULE-2, RULE-4, REQ-M.3 | DONE |
| F-M.1.2 | New Django app `matazim`, own URL space at `/matazim/` | REQ-M.1, spec 2.2 | DONE |
| F-M.1.3 | Design system stylesheet: tokens, buttons, cards, chips, gradient | REQ-M.1, spec 3.2 | DONE |
| F-M.1.4 | Standalone base template: own header, nav, footer, RTL, from 360px | REQ-M.1, REQ-M.5b | DONE |
| F-M.1.5 | Public home page, all content hardcoded | REQ-M.5, M.5c, M.5d, M.5f | DONE |
| F-M.1.6 | Guard tests for the four separation rules | RULE-1 to RULE-4 | DONE |

### Scope notes

**F-M.1.1 removes presentation only.** Routes out of `app/urls.py`, both nav
entries out of `templates/base.html`, the `show_matazim` context processor, and
the files `app/matazim_views.py`, `templates/app/matazim/`, `static/matazim.css`,
`tests/test_spr_10_1.py`. It is forced rather than optional: the new app needs
`/matazim/`, which the old routes hold, and `base.html` reverses `matazim_home`.

**Nothing is destroyed.** `matazim_models.py`, migrations 0096 to 0098,
`seed_matazim`, and the entrance-test engine (`matazim_geometry`,
`matazim_check`, `matazim_targets`, and the passing `tests/test_spr_10_2.py`)
all stay exactly where they are. Dropping the production tables waits on ACT-M.2.

**Out of scope, deliberately:** login, the member nav, any real data, the other
eight sections, 404 and 500 pages, and the two logged-in screens.

**Cut during the sprint (Avi, 2026-09-09):** the prototype's stats band and its
תוצרים נבחרים showcase. Both were invented, and a public page does not carry
invented figures or invented children's work. The components stay in the design
system; the sections return when there is data and consent behind them, under
REQ-M.5f and REQ-M.5e. Tests now assert their absence rather than their shape.

### ACT items

| ACT-ID | What Avi does | Blocks | Status |
|---|---|---|---|
| ACT-M.1 | Hero photograph, supplied 2026-09-09 (`static/matazim/img/hero.png`). The project thumbnails are no longer needed: the showcase came off the page | Nothing | CLOSED |
| ACT-M.2 | Confirm whether any real person applied on the production tables | The table-drop, which is **not** in this sprint | OPEN |

### Definition of done

All six features DONE, 25 tests green, and live at babook.co.il/matazim.

**Regression gate.** The repo suite is not green and was not green before this
sprint: a clean checkout of the pre-sprint `HEAD`, run in a separate worktree,
fails 28 tests. After the sprint it fails 27, and a name-by-name diff shows
**no new failures** and one that went from fail to pass. That is the gate this
sprint was held to, since "all green" was never available to reach.

**Deployed 2026-09-09** on Avi's word. Smoke-tested in production: `/matazim/`
200 and rendering, no link out of the prefix except static assets, babook's own
pages carrying no mention of מט״צים, and every asset served.


---

## SPR-M.2 — Who you are here  `DONE`

**Goal:** a person can come in, be recognised, and see themselves. Login,
profile, the first-time welcome, and the gate that holds the joining door shut
until the entrance test is passed.

This is where מט״צים grows its first table. SPR-M.1 had no models on purpose;
"who am I in this program" cannot be answered without one.

**Decisions taken into this sprint (Avi, 2026-09-10):**

- The test gates **כניסת תלמידים only**. כניסת מובילים stays open, because the
  test measures a teenager's commitment and a teacher confirming a roster has no
  reason to model a 3D object.
- **התחברות in the header is never gated.** Otherwise the gate locks out
  everyone who already passed and came back, since we only learn they passed
  after they sign in. Hero doors are for joining, the header is for returning.
- מט״צים's flags live in **its own table**, 1:1 to `User`. Name, avatar and
  training stay in babook's shared `UserProfile` and are read and edited there.
  Same identity, same data models, and RULE-3 stays true.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.2.1 | `MemberProfile`, the app's first model and migration | REQ-M.35, spec 4 | DONE |
| F-M.2.2 | Own threshold: login and logout at `/matazim/` URLs, מט״צים screens over the shared `User` | REQ-M.6, REQ-M.7 | DONE |
| F-M.2.3 | Register here, and be stamped as having entered through this door | REQ-M.6, REQ-M.35 | DONE |
| F-M.2.4 | Welcome and prototype disclaimer, shown once, acknowledged explicitly | REQ-M.39, REQ-M.40 | DONE |
| F-M.2.5 | Profile view: shared personal details, program standing, and every הדרכה read live | REQ-M.42, M.43, M.44 | DONE |
| F-M.2.6 | Replay control: clear the flag and meet the site as a stranger again | REQ-M.41 | DONE |
| F-M.2.7 | The gate: student door waits for the test, leader door and header login do not | REQ-M.36, REQ-M.37 | DONE |
| F-M.2.8 | מבחן הכניסה placeholder page at its own URL | REQ-M.38 | DONE |
| F-M.2.9 | Google sign-in, handed off and returned without leaving the prefix | REQ-M.45 | DONE |

### Scope notes

**The profile is a view over two records.** Shared identity from babook's
`UserProfile`, מט״צים's own flags from `MemberProfile`, program standing from
`Membership` once it exists. Editing the name edits the shared profile, because
a person has one name.

**School and מט״צ status read "not yet assigned"** this sprint. `Membership`
does not exist yet, and showing an honest placeholder beats hiding the row and
redesigning the page later.

**The welcome for a visitor who is not signed in.** They still see it, and the
dismissal survives the visit through the session. It simply cannot be attributed
to anyone, which is the point of storing it on the profile for people who are.

**The test placeholder** says what the test will be and why it exists. It does
not fake a pass. How a passed test is recorded for someone who has not yet
registered is REQ-M.17's problem, not this sprint's.

**Google without breaking the seal.** A direct link to the provider would leave
`/matazim/` and break RULE-1, so the page links to our own URL, which hands off
to the provider and names a return address back inside the prefix. Coming back
runs the same stamping and welcome-carry as a password sign-in, because how
someone got in should not change what we record about them.

**Out of scope, deliberately:** `Membership`, `School`, the application form,
the school invite link and QR, the member nav, and the entrance test itself.

### ACT items

| ACT-ID | What Avi does | Blocks | Status |
|---|---|---|---|
| ACT-M.3 | Confirm the disclaimer wording is what he wants standing on a live public page | The exact copy in F-M.2.4, not the build | OPEN |

### Definition of done

Eight features DONE, 26 tests green, no new failures against the pre-sprint
baseline, and the flow walked end to end in a real browser.

**What the flow-walk caught that the tests did not.** Dismissing the welcome as
a stranger and then registering showed it a second time, because the new profile
carried no acceptance and the session's was thrown away. Nobody should be told
the same thing twice, and REQ-M.40 is supposed to keep that timestamp, so the
acknowledgement now moves onto the profile at sign-in. Covered by T-F-M.2.4-5.

---

## Carried into the next sprint

| Item | Why | Traces |
|---|---|---|
| Signing in lands on דף הבית, from every door | Avi, 2026-09-10, found in the demo. Password login already does; register and Google drop you on the personal area instead | REQ-M.46 |

## Candidates for the sprint after this one

Not planned, not committed, just the obvious neighbours. We pick one when
SPR-M.1 closes.

- The rest of the public front: המסלול השנתי, בתי הספר המשתתפים, אודות התכנית.
- The threshold: מט״צים-branded register and log in over the shared `User`.
- The member shell: logged-in nav, and המסלול שלי as a static design pass.
- Retire the production tables, once ACT-M.2 is answered.
