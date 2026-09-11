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


---

## SPR-M.3 — מבחן הכניסה  `DONE`

**Goal:** a stranger can walk in, learn Tinkercad, build the object we show
them, upload it, and have the student door open. The gate stops being a
promise on a placeholder page and becomes the thing the product is for.

**Why this is smaller than it looks.** The hard half already exists and is under
test: 120 generated targets, each with a dimensioned Hebrew drawing, an STL, a
written brief and a server-side answer key; the geometry engine that measures a
submission; `check()` returning Hebrew issues with real numbers in them; and
babook's `stl-viewer.js`, an ES module we can reuse rather than rebuild. What is
missing is screens and wiring.

**Decisions taken into this sprint (Avi, 2026-09-10):**

- The gate **selects and onboards at once**, and confirming the applicant has a
  computer is part of the point rather than a side effect.
- Use the **existing** `tinkercad` course lessons. Video and assignment only, no
  transcript.
- The final task is **added by us, not to their course**. babook's `tinkercad`
  course is live and must not grow a מט״צים assignment.
- Staff can see the whole bank and **retire** targets that are too hard.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.3.1 | Every door lands on the main view | REQ-M.46 | DONE |
| F-M.3.2 | The bank as data: `EntranceTarget`, seeded from the generated files | REQ-M.55 | DONE |
| F-M.3.3 | Staff curation: every target with its drawing and 3D, retire and restore | REQ-M.55 | DONE |
| F-M.3.4 | The course inside the walls: lesson list and lesson page, our chrome | REQ-M.47 | DONE |
| F-M.3.5 | Video and assignment only, no transcript, progress written once | REQ-M.48, REQ-M.49 | DONE |
| F-M.3.6 | The final task: drawing, 3D view and brief, with a target assigned and kept | REQ-M.50, REQ-M.51 | DONE |
| F-M.3.7 | Upload and measure, recorded as an attempt | REQ-M.52 | DONE |
| F-M.3.8 | The verdict: עבר or עוד לא, with the real numbers and a way back | REQ-M.53 | DONE |
| F-M.3.9 | Passing opens כניסת תלמידים | REQ-M.54 | DONE |

### Scope notes

**Read-only over babook's course.** We render `Course`/`Video` rows and write
`Enrollment`/`UserVideoProgress` through the shared path. We do not add a lesson,
change a project type, or touch that course in any way.

**Staff, for now, means `is_staff` or superuser.** *(Superseded 2026-09-10:
`Program` was dropped and adminship became `MemberProfile.is_admin`. Still a
one-line change, still the same screen. Spec §4.)*

**Retiring is reversible and never destructive.** A retired target stops being
assigned; attempts already measured against it keep working, because the
geometry lives in the files and the row only carries the decision.

**Out of scope, deliberately:** the three-sentence reflection, duplicate
detection across submissions, the staff commitment view, the application form
itself, `Membership` and `School`.

### ACT items

| ACT-ID | What Avi does | Blocks | Status |
|---|---|---|---|
| ACT-M.4 | Walk the bank and retire whatever is too hard for a 14-year-old | Nothing. The screen ships with everything active | OPEN |
| ACT-M.5 | Decide whether the drawings get regenerated in the current palette, or stay in the old matazim.co.il colours | Cosmetic only | OPEN |

### Definition of done

Nine features DONE, 20 tests green, the fast gate green at 85 tests, and the
journey walked in a browser.

**What the guard caught.** RULE-3 said מט״צים "never writes learning state", and
the test threw the moment we rendered a lesson: you cannot watch one without an
enrolment, and babook's own lesson view creates one with the identical
one-liner in six places. The rule was too blunt and contradicted REQ-M.14. It
now says what it always meant, that there is **one version of the truth about
learning**: no parallel table, no fabricated progress, no certificate issued by
hand. Enrolling someone in a course they are actually taking is the shared path,
not a breach of it. Spec §2.3 records the amendment and why.

---

## SPR-M.4 — The rest of the front  `DONE`

**Goal:** finish Litala's nine sections. Six of eight menu items currently
reload the home page, which reads as broken rather than unfinished.

**The rule for this sprint:** every page says something true. Where the data
exists we show it; where it does not we say what is coming, in our own voice.
No invented content, the same call we made about the stats band and the
showcase in SPR-M.1.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.4.1 | The five stages as shared data, not copy repeated per page | REQ-M.58 | DONE |
| F-M.4.2 | אודות התכנית | REQ-M.57 | DONE |
| F-M.4.3 | המסלול השנתי, the five stages as a path | REQ-M.58 | DONE |
| F-M.4.4 | הקורסים, honest about what is open today | REQ-M.59 | DONE |
| F-M.4.5 | בתי הספר, קהילת מט״צים and ימי שיא, each saying what is coming | REQ-M.60 | DONE |
| F-M.4.6 | The nav points at all of it, and nothing points at itself | REQ-M.56 | DONE |
| F-M.4.7 | מבחן הכניסה stops saying it is closed, and says what you need | REQ-M.61 | DONE |

### Scope notes

**Five stages here, four on the home page.** The teaser sells the journey and
leaves מתמיינים out because the entrance test has its own call to action
(spec Q12). המסלול השנתי is the journey itself, so it shows all five.

**Out of scope:** `School`, `Post`, `Event` and everything they would carry.
Three of these pages exist to hold the shape until those arrive.

**Caught by Avi reading the live page.** SPR-M.3 built the entrance test and its
own front door went on saying עוד לא פתוח for half a day. Worse than an
unfinished page: it turns away the people the gate exists to let in. The page
now does the job the journey design gave it, and two tests hold it to that.

### Definition of done

Seven features DONE, the sprint's tests green, the fast gate green, every menu
item clicked once in a browser, and nothing anywhere pointing at the page it is
already on.

## SPR-M.5 — Small things that were wrong  `DONE`

Three from Avi, 2026-09-10, all found by using the site rather than reading it.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.5.1 | The bank gets a door, and only staff see it | REQ-M.62 | DONE |
| F-M.5.2 | A passed test carries a done mark everywhere it is offered | REQ-M.63 | DONE |
| F-M.5.3 | איפוס is staff only, hidden and refused | REQ-M.64 | DONE |

**Hidden is not refused.** F-M.5.3 does both: the panel disappears for members,
and the endpoint rejects them. A button that is only invisible is still a URL.

---

# EPIC-M-ROLES — who sees whom

**The model is settled** (spec §4, agreed 2026-09-10). Four roles, four
different things, and one function that answers every scope question:

```
MemberProfile.is_admin   ADMIN     assigns leaders, sees everyone
Leader (row per user)    LEADER    their own students, nothing else
StudyClass → Leader                name, school_name. A leader runs classes anywhere.
Student → User, Leader?  STUDENT   themselves. leader is NULL until someone takes them.
```

The reason to get the relations right first: permissions stop being checks
scattered through views and become a single queryset. A leader cannot reach
another leader's students because **the query cannot get there**.

Three sprints. The first has no screens at all, and that is the point.

## SPR-M.6 — The roles, and nothing else  `DONE`

**Goal:** the four models, the access module, the seed, and tests that prove a
leader cannot reach another leader's students. No screens. Everything after this
becomes a filtered queryset.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.6.1 | `Leader`, `StudyClass`, `Student`, and `is_admin` on the profile | spec §4.2 | DONE |
| F-M.6.2 | `matazim/access.py`: one function, four roles, stated precedence | REQ-M.22, spec §4.4 | DONE |
| F-M.6.3 | Seeding adminship from a named list, never self-served | REQ-M.68 | DONE |
| F-M.6.4 | A student with no leader is a normal state everywhere it is read | REQ-M.65 | DONE |
| F-M.6.5 | Deactivating a leader destroys nothing | REQ-M.67 | DONE |
| F-M.6.6 | The tests that make the rest trivial: no leader reaches another's students | REQ-M.22 | DONE |
| F-M.6.7 | מט״צים in Django admin, so adminship can be granted without a deploy | REQ-M.68 | DONE |
| F-M.6.8 | One ניהול door, and granting adminship from inside מט״צים | REQ-M.69, REQ-M.70 | DONE |
| F-M.6.9 | Error pages that stay inside the walls | REQ-M.2 | DONE |
| F-M.6.10 | The admin picker searches by name or email as you type | REQ-M.71 | DONE |

### Scope notes

**Found while deploying, not while planning.** Checking what a non-admin
actually gets served showed a 403 inside `/matazim/` rendering babook's page,
title and drawer included. A live RULE-2 break that four sprints of guard tests
had not caught, because they read templates under `templates/matazim/` and pages
we request successfully, and an error page is neither. REQ-M.2 had been sitting
at TODO since SPR-M.1 and this is exactly what it was for.

**F-M.6.6 is the feature, not the paperwork.** The whole architecture rests on
one claim, that scope is a property of the data. A test that builds two leaders
with students each and asserts neither queryset ever contains the other's is
what turns that claim into something we know.

**Progress crosses the boundary in this sprint too**, because it is one join and
proving it now is cheaper than discovering later that the relation names do not
line up: `Enrollment.objects.filter(user__matazim_student__leader=me)`.

**No screens.** Not the roster, not the admin view, not the leader door. The
existing `is_site_staff` helper switches to `is_admin` and that is the only
visible change.

### ACT items

| ACT-ID | What Avi does | Blocks | Status |
|---|---|---|---|
| ACT-M.6 | Grant adminship to נעמי and אביב at babook.co.il/matazim/staff/admins/. You hold every power already as site owner, so you do not need granting. Either at babook.co.il/admin/ under פרופילי מט״צים, ticking מנהל/ת התוכנית, or by setting `MATAZIM_ADMINS` in Render so every deploy re-applies it | Admins existing in production. The build is done | OPEN |

## SPR-M.7 — How anyone becomes anyone  `DONE` — deployed 2026-09-11 (`d121299`)

**Goal:** the roles stop being unpopulatable. Today nothing in the app creates a
`Leader` or a `Student` at all, Django admin is the only way in, and passing the
entrance test unlocks a door that sends you to a registration form you already
filled in.

**Avi's brief: the UX is the feature.** Four different people walk four
different paths through this, and each one has to know where they are and what
happens next at every step. No dead ends, and nothing silently dropped.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.7.1 | `Student.pending_leader`, so asking and being accepted are different things | REQ-M.10 | DONE |
| F-M.7.2 | Admin assigns a leader, and manages their link | REQ-M.25 | DONE |
| F-M.7.3 | The leader's invite link and QR, and the landing page it opens | REQ-M.9 | DONE |
| F-M.7.4 | Apply: three questions, and the row that finally makes someone a student | REQ-M.16 | DONE |
| F-M.7.5 | The open door: pick a leader, and wait to be confirmed | REQ-M.10 | DONE |
| F-M.7.6 | A leader has somewhere to stand, and can confirm people | REQ-M.73 | DONE |
| F-M.7.7 | The invite survives registering and the entrance test | REQ-M.72 | DONE |
| F-M.7.8 | Every door leads somewhere true, including כניסת מובילים | REQ-M.66 | DONE |

### The four journeys, which are the actual specification

**A student with a link**, the common case. Tap the WhatsApp link, see who is
inviting you and to which school, and then whichever of these is true: open an
account, or take the entrance test, or join in one tap. The leader's name is on
screen at every one of those steps, so the invite never feels lost.

**A student without a link.** Pass the test, and כניסת תלמידים opens onto the
application rather than a form they already filled in. Three questions, choose a
leader, and then a page that says plainly they are waiting to be confirmed and
by whom.

**An admin.** ניהול, מובילים, pick a person with the search we already built,
and they are a leader. Their link and QR are on their page, rotatable, and they
can be deactivated without anything being destroyed.

**A leader.** כניסת מובילים lands on their own page: the link to hand out, and
the people waiting for them to say yes.

### Scope notes

**Asking is not being accepted.** `Student.leader` is who has them;
`pending_leader` is who they asked. An invite link sets `leader` directly,
because the leader handed out the link and the choice is already theirs
(REQ-M.9). The open door sets `pending_leader` and waits (REQ-M.10).

**The invite is kept in the session**, not in a column. A WhatsApp link survives
being tapped again, which is the real recovery path, and a column would need a
migration to hold something that lives for twenty minutes. The leader's name is
shown throughout so nobody has to trust that it is still there.

**Out of scope:** the roster with progress, the admin master view, and the
funnel. F-M.7.6 builds only what makes confirmation possible, because without it
the open door has no exit.

### Definition of done

Eight features, 20 tests, the fast gate green, the phone guard green, and all
four journeys walked end to end in a real browser.

**Two things the walkthrough caught that the tests did not.** A leader could
reach their own area only through the כניסת מובילים door on the public home
page, which is a strange way to ask someone to return to their own desk; they
now have a nav entry, and nobody else sees it. And the staff area had no link to
the leaders screen, the same mistake as the target bank having no door.

## SPR-M.8 — The leader's students  `DONE`

**Goal:** a leader opens their page and sees who they have, where each person
is, and what to do next. SPR-M.7 gave them a desk with an invite link and a
confirm queue; the desk is still empty the moment the queue is cleared.

**Why now:** this is the first screen that consumes `access.visible_students`,
and the first that reads babook's learning data instead of writing our own.
Both of those are contracts, and a contract is only real once something depends
on it.

### The thing that can go wrong

A roster is the inverse shape of every babook screen. Babook asks *one user,
many courses*; a roster asks *many users, one track*. `app/views._catalog_progress`
answers the first shape and cannot answer the second without being called once
per student, which is a query per teenager on every page load.

So the reader gets rewritten for the cohort shape, and the moment it is
rewritten there are two definitions of "done" in the codebase. That is exactly
the divergence RULE-3 exists to prevent, and it would not announce itself: it
would quietly tell a leader that a kid has finished four lessons while the kid's
own screen says three. F-M.8.1 is therefore built with a test that pins the two
readers against each other, not merely a test that the new one returns numbers.

### What the track is

Answered by Avi on 2026-09-11, so this is no longer a placeholder. The required
core is exactly two babook courses, `scratch` and `scratch-advanced`, both of
which exist today, are published, and issue certificates. Together with the
entrance test they are the whole automatic half of becoming a mataz.

It lives as a slug list in `matazim/content.py`: no migration, no field on
babook's `Course`, and RULE-4 holds because babook still knows nothing about us.
Anything beyond those two is encouraged and shown, but never a substitute.

### Becoming a mataz

The sprint grew by one screen, and it is the important one. A roster without it
is a report; with it, it is where a leader does their job.

Three conditions (REQ-M.76). The entrance test, the two Scratch certificates,
and the leader's own approval. The first two מט״צים only **reads**: a
`CourseCertificate` row is babook's fact, issued by babook's Finish button, and
nothing here re-derives what a certificate means.

The two halves pull in opposite directions on purpose, and this is the part to
get right. The automatic check is **binding**: a leader cannot certify someone
who has not met it, the action is absent rather than discouraged, and the server
refuses the post independently of what the page rendered (REQ-M.77). The human
check is **the decision**: meeting the prerequisites earns the right to be
considered and never the status itself, and nobody is promoted automatically on
a certificate count (REQ-M.78). Note this is the exact inverse of the entrance
test, where the machine advises and never rejects. Here the machine only ever
refuses, and only a person can grant.

An ineligible student is an explained state, not a missing button: the screen
says which of the three is outstanding and links to it.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.8.1 | `matazim/progress.py`: progress for many students in a fixed number of queries, pinned to babook's rule by a test | REQ-M.74, REQ-M.14 | DONE |
| F-M.8.2 | The track: `scratch` + `scratch-advanced`, named in `content.py` | REQ-M.23, REQ-M.76 | DONE |
| F-M.8.3 | The roster: every student the leader has, with stage, track progress and class | REQ-M.23, REQ-M.22 | DONE |
| F-M.8.4 | Classes: create, rename, put students in them. Offered, never required | REQ-M.23, Q14 | DONE |
| F-M.8.5 | One student, seen by their leader: the three conditions, per-course progress, classes | REQ-M.23 | DONE |
| F-M.8.6 | Search and paging on the roster from the first commit | REQ-M.23 | DONE |
| F-M.8.7 | The whole thing on a phone | REQ-M.75 | DONE |
| F-M.8.8 | Eligibility: the three conditions, computed and never stored | REQ-M.76 | DONE |
| F-M.8.9 | A leader certifies a mataz, and the gate refuses on the server | REQ-M.77, REQ-M.78 | DONE |

### What shipped, and what it cost

Three things the tests were green for and a browser found anyway, which is now
the third sprint running where that has been true.

**The phone guard was passing on the wrong page.** It had only ever walked
pages reachable logged out, so pointing it at the leader's screens meant
signing in, and the sign-in silently failed: the welcome notice carries its own
submit button and sits *before* the login form in the DOM, so a bare
`button[type=submit]` dismissed the welcome and never touched the login. Every
check then passed against the login page, which fits a phone perfectly well.
The guard now asserts where it landed, because a guard that cannot tell you it
failed is worse than no guard.

**Three tap targets under the floor**, found the moment the guard could
actually see a signed-in page. None of them were new: `.mz-linkbtn` was 29px
everywhere, and יציאה in the header measured 35.6px on every signed-in page in
the product. The guard had simply never had a signed-in page to look at.

**Every student sat at מתמיינים forever.** Nothing in the app ever advanced
`Student.status`, so a roster showing four people in four different states
showed one word four times, and the word was wrong: מתמיינים is the selection
stage and these are people a leader has already accepted. Now being taken on,
by either route, makes someone לומדים.

**Course slugs were leaking into Hebrew sentences.** `scratch-advanced` is an
identifier, not something to put in front of a reader, and the "what is
missing" line was built out of them. The title now travels with the progress
numbers, because every screen that shows progress also has to name the course.

One deliberate non-change: `app.views._catalog_progress` was left alone. It has
seven call sites across babook including certificate verification and no test
coverage of its own, so refactoring it to share a rule with the new reader
would have put babook's catalog and certificates at risk to remove a
twenty-line duplication. The pin test is the cheaper guarantee, and it is
incidentally the first coverage that function has ever had.

### Rules this sprint is under

- **REQ-M.29.** A roster records the מט״צ and nothing about any child they
  teach. Teaching is the מט״צ's own declared activity, never a row about a kid.
- **REQ-M.22.** No screen here asks "may I". Every one of them starts from
  `visible_students(request.user)` and a leader's queryset cannot reach anyone
  else's student, so there is nothing to forget.
- **Q14 defaulted.** A class is offered and never required. A leader with six
  students should never have to invent a filing system to see them.
- Search and paging ship in the first commit rather than "when we need them",
  because they cost nothing at this size and are the only thing that makes the
  screen survive the larger number.

## SPR-M.9 — Close the holes, then say what we do  `DONE`

Avi, 2026-09-11: act as a privacy expert, put the legal and privacy aspects in
the spec, plan sprints, and do it. The audit is spec §4.10; this sprint is the
half of it that cannot wait.

Ordered by what is actually dangerous, not by what is easiest to write. Two of
these are live defects and one is a fourteen-year-old being asked for their
email with nothing on the screen telling them where it goes.

**The QR endpoint is the sharpest.** `/matazim/leader/<id>/qr.png` has no
authentication and no authorization, and the id is a sequential integer. Walk it
and you have every leader's join code. A join code is not a convenience, it is a
bearer credential: REQ-M.9 says an invite link attaches its holder to that
leader **with no confirmation**, deliberately, because the leader handed the
link out. So this is not an information leak, it is an unauthenticated write to
somebody else's roster. It is unexploited today only because production has no
leaders yet, which is luck rather than design.

**The uploads are the most embarrassing.** A teenager's entrance-test model is
written straight into `MEDIA_ROOT` under the name of the file they chose, and
`/media/` is served with no authentication at all. `settings.py` even says so in
a comment. School work is named after the pupil roughly always.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.9.1 | The QR endpoint authenticates and authorises like every other leader screen | REQ-M.79 | DONE |
| F-M.9.2 | Uploads leave `MEDIA_ROOT`, get unguessable names, and are served through a view that checks | REQ-M.80 | DONE |
| F-M.9.3 | Privacy policy and terms, ours, inside the walls, linked from every footer | REQ-M.81 | DONE |
| F-M.9.4 | The registration screen says what happens to the data, including that a leader will see it | REQ-M.82 | DONE |
| F-M.9.5 | Cookies disclosed in the policy; no banner, and a test that keeps it that way | REQ-M.83 | DONE |

### What the audit found once it could see rendered pages

Two things beyond the planned five, both found by doing the work rather than by
reading the code.

**Google Fonts was leaking every visitor to Google.** `base.html` carried a
`<link>` to `fonts.googleapis.com`, which sends the visitor's IP to Google on
every page load, before they have agreed to anything, on a site whose visitors
are fourteen. It also made the privacy policy's "no third parties here" not
quite true, which is a bad property for a sentence in a legal document. Rubik is
now served from our own disk, Hebrew and Latin subsets only, and the guard
checks every fetching tag rather than only scripts.

**RULE-1 had to give way an inch, and the shape of the inch mattered.** A
privacy policy must name who holds the data and give a contact that works, and
`privacy@babook.co.il` is the inbox that exists. Inventing a מט״צים-branded
address would put a dead contact on the one page where the contact is the point.
So the rule keeps its grip on navigation and yields on disclosure, only on the
two legal pages, and the guard now asserts that distinction instead of grepping
for the word "babook" (which is what would have pushed someone into inventing
the dead address).

Also: the phone guard caught two of my own inline links at 18px, and the fix for
those caught a second bug. Horizontal padding on an inline link detaches it from
what it abuts, and in Hebrew that is constant: a prefix letter glued to the
front (ב + עמוד) and a full stop at the end both ended up floating.

**Deliberately not in this sprint:** a cookie consent banner. מט״צים sets two
cookies, `sessionid` and `csrftoken`, both strictly necessary, and loads no
analytics and no third-party script. Strictly necessary cookies are disclosed,
not consented to. A banner asking permission for cookies we set regardless is
consent theatre, and it lands on a teenager's phone where it costs real screen.
F-M.9.5 therefore ships a **test that fails if a third-party script ever appears
under `/matazim/`**, because that is the day the judgement flips and a real gate
becomes owed.

## SPR-M.10 — Consent, rights, and an end date  `DONE`

The half that is policy becoming machinery. Slower work, and none of it is a
live hole, which is why it is second.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.10.1 | Year of birth at registration, and a parent's consent recorded for anyone under 18 | REQ-M.84 | DONE |
| F-M.10.2 | An admin records a school's paper consent, rather than it being assumed | REQ-M.84 | DONE |
| F-M.10.3 | Everything we hold about you, on one screen in your own profile | REQ-M.85 | DONE |
| F-M.10.4 | Export it. Deletion **reuses** `app.views.delete_account`, reached from our own screen | REQ-M.85 | DONE |
| F-M.10.5 | Retention periods, as a `purge_matazim_attempts` command in babook's existing `purge_*` pattern | REQ-M.86 | DONE |

**Reuse, per Avi mid-SPR-M.9.** F-M.10.4 shrank from "build deletion" to "reach
the deletion that exists": `User.delete()` already cascades into every מט״צים
table, so a second path would only be a second thing to keep in step. F-M.10.5
follows `purge_security_events` rather than inventing a scheduler. What is not
reused is the *pages*: RULE-1 means a member cannot reach babook's, and they
describe a different kind of processing. Shared plumbing, separate promises.

One thing the reuse already caught, fixed in SPR-M.9 rather than deferred:
`delete_account` removed every row and left the uploaded model on the disk,
because Django stopped deleting files on row deletion in 1.3.

### What the retrofit actually cost

The gate landed exactly where it was predicted to, which is the useful part.
Seven tests across SPR-M.2, M.3, M.7 and M.8 went red the moment consent
existed, because every one of their fixtures builds a member with no birth year
and then joins them to a leader. That is not the tests being wrong, it is the
tests encoding a world where this rule did not exist, and the red was the proof
that the gate bites rather than decorating.

They were updated rather than relaxed: the registration POSTs now send the
fields the form actually requires, and the joining fixtures now build the person
those tests were always about, a fourteen-year-old whose parent has said yes.
The gate itself is tested on its own in `test_spr_m_10.py`, so nothing is
checking consent by accident.

Two things found by looking rather than by testing. The registration page still
promised "שלושה פרטים, וזהו" while asking for up to seven, which is a small lie
on the one screen where trust is being asked for. And the new copy said קורסים
where מט״צים's own body copy says הדרכות; the product turns out to use both
deliberately, הקורסים as Litala's section name and הדרכות in prose, which is
defensible and is now written down in Q9 instead of being folklore.

The judgement call in F-M.10.1 is what to do with someone who is already
registered when consent arrives as a requirement. Retrofitting a gate in front
of existing members locks out the people already doing the entrance test. The
plan is to ask at the next sign-in and block joining a leader rather than block
the account, so nobody loses work they have already done.

## SPR-M.11 — Retention with a person in front of it  `DONE`

Avi, 2026-09-11: "What is this retention? Is there a manual approvals process?"

The question found a hole in what SPR-M.10 had just shipped. `purge_matazim_attempts`
deletes only when a human types `--apply`, and **nothing scheduled it**: not
`render.yaml`, not a workflow. So the privacy page stated a 365-day period that
the system would never enforce on its own. The machinery existed, the promise
was published, and the two had never been connected.

Nothing was at risk yet, since the oldest possible attempt was a month old. But
a public page should not claim something the system will not do.

**The fork, and why this side of it.** Automate it and the promise becomes true
without anyone remembering, at the cost of an unattended irreversible delete.
Put a person in front of it and the delete is reviewed, at the cost of a job
that does not run while the person is busy. Avi had no preference, so this took
the shape the rest of the product already has: the machine refuses or proposes,
a person decides, and the decision carries a name. Certification works this way
(REQ-M.78), retiring a target works this way (REQ-M.55), deactivating a leader
destroys nothing (REQ-M.67). Deletion is the one action here that cannot be
undone, which is the strongest case for a pair of eyes rather than the weakest.

The cost of that choice is paid for explicitly: the staff area carries a
standing count of what is overdue, and shouts only when something is. Otherwise
"we have a retention policy" quietly becomes "we kept everything".

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.11.1 | A review screen listing what is due, and whose it is | REQ-M.87 | DONE |
| F-M.11.2 | Approving is what deletes; opening the page never does | REQ-M.87 | DONE |
| F-M.11.3 | `RetentionRun` records who approved, when, and how many | REQ-M.87 | DONE |
| F-M.11.4 | A standing overdue count in the staff area | REQ-M.87 | DONE |
| F-M.11.5 | The privacy page describes the review rather than implying a timer | REQ-M.86 | DONE |

One test in this sprint passed for the wrong reason before being tightened. It
checked that the privacy page mentions צוות התוכנית anywhere, and the page
happens to say that in the section about uploaded files, so it agreed with
itself without ever reading the retention paragraph. It is now scoped to that
paragraph by id.

## The program manager epic

Settled with Avi across 2026-09-11. Four sprints, ordered so that each one is
demoable on its own and nothing is built on vocabulary or scope that is about to
change underneath it.

The order is not negotiable in one respect: **the rename comes first and the
tenancy comes second**, because every screen in the epic is scoped by tenancy
and named by the vocabulary. Building the screens first would mean renaming and
re-scoping a half-finished feature, which is how a leader ends up seeing the
wrong institution's students.

## SPR-M.12 — Say what we mean  `DONE`

**Goal:** the code calls things what Avi calls them. No behaviour changes at
all, so that if anything breaks it is unambiguous what caused it.

"admin" pointed at root in conversation and at נעמי on screen, and that
ambiguity already produced one wrong grant of superuser. The Hebrew has said
מנהל/ת התוכנית since SPR-M.6, so this mostly aligns the English to the Hebrew
that already shipped.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.12.1 | `access.py`: `ADMIN` → `PROGRAM_MANAGER`, `is_admin()` → `is_program_manager()` | §4.3 | DONE |
| F-M.12.2 | `MemberProfile.is_admin` → `is_program_manager`, with a `RenameField` migration | §4.3 | DONE |
| F-M.12.3 | Root's label becomes מנהל/ת מערכת; "site admin" retired everywhere | §4.3 | DONE |
| F-M.12.4 | `matazim_admins` command reads **both** env var names | §4.3 | DONE |

**What it touched:** 29 call sites across six modules, 30 references in nine
test files, the Django admin registration, the people picker, and two labels.
The Hebrew needed almost nothing, because the screen has said מנהל/ת התוכנית
since SPR-M.6. Only root's label moved, from מנהל/ת האתר to מנהל/ת מערכת.

**The migration was written by hand.** `makemigrations` asks interactively
whether a removed field and an added field are the same field, and answering
wrong, or letting `--no-input` answer, produces a `RemoveField` plus an
`AddField`. That pair is not a rename: it drops the column and creates a new one
with the default, which in production would silently strip נעמי of the role on
the next deploy and leave nobody able to grant it back except through Django
admin. A `RenameField` carries the data across, and `makemigrations --check`
confirms Django agrees nothing is outstanding.

**The one real hazard is F-M.12.4.** `matazim_admins --from-env` runs on every
deploy and is what keeps נעמי in her role in production. Rename the variable
without setting the new one in Render and the next deploy silently stops
granting it. So the command accepts the old name and the new one for now, and
the old one is dropped only once Render is confirmed updated.

## SPR-M.13 — The worlds do not touch  `DONE`

**Goal:** `Leader.program_manager`, and every query in the product learning
about it. Still no new screens.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.13.1 | `Leader.program_manager`, backfilled to נעמי for every existing row | REQ-M.88 | DONE |
| F-M.13.2 | `visible_leaders` and `visible_students` scope by ownership; root crosses worlds | REQ-M.88 | DONE |
| F-M.13.3 | Every existing screen re-checked against the narrowed scope | REQ-M.88 | DONE |
| F-M.13.4 | A guard test: two program managers, and neither can reach the other's anything | REQ-M.88 | DONE |

**F-M.13.4 is the point of the sprint.** Everything else is mechanical. A test
that builds two complete worlds and asserts that every screen, every queryset
and every POST refuses to cross between them is what makes tenancy true rather
than intended, and it is the test that will still be earning its keep in a year.

**Four real leaks, found by the guard rather than by reading.** Every one was a
screen building its own queryset instead of asking the access module: the leader
list, the single-leader page and its writes, the QR endpoint, and the class
filing form, which let a program manager file a student into any class on the
platform. All four now go through `visible_leaders`, so the scope arrives with
the object rather than being checked afterwards.

**One semantic conflict, resolved the conservative way round.** A pure ownership
join drops students nobody has claimed yet, because an unclaimed student has no
leader and therefore no world. Nothing in the product surfaces them separately,
so dropping them would make a teenager who passed the entrance test invisible to
the only person who could help. That is the worse failure with one program
manager, so they stay in view and the `Q` object is marked as the line Q15 will
change.

**The RULE-3 guard caught the demo seeder** on the day it was written, for
writing `UserVideoProgress` directly. It was right to: the rule exists to stop
product code inventing a second way to record learning. The answer was a named
exemption with the reason attached, not a looser pattern, since fabricating
progress is the seeder's entire job and it never runs for a real user.

**Q15 is open and this sprint does not close it.** The open door lists every
active leader on the platform, which under tenancy would show one institution's
staff to another's applicants. Production has one program manager, so nothing is
wrong today; the second one breaks it. Flagged, not fixed.

## SPR-M.14 — How a leader gets made  `DONE`

**Goal:** the three doors, all ending at a person pressing approve.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.14.1 | A standing leader-management entry, not buried in ניהול | REQ-M.89 | DONE |
| F-M.14.2 | Search, click, approve, for someone who already has an account | REQ-M.90 | DONE |
| F-M.14.3 | That approval sends them an email: you are a leader, under whom, what next | REQ-M.90 | DONE |
| F-M.14.4 | `LeaderInvite`: personal, single-use, link + QR + optional email | REQ-M.91 | DONE |
| F-M.14.5 | Open invite: reusable, produces candidates and never leaders | REQ-M.92 | DONE |
| F-M.14.6 | Candidates wait in the list; approval is always a human press | REQ-M.93 | DONE |

**What it cost, and what it caught.**

The unapproved row was the trap, and it was real: adding the candidate state
turned every existing leader into a candidate until the backfill went in, and
sixteen tests across four suites went red because their fixtures created leaders
that had never been approved. That red was the filter working. `leader_of`
refuses an unapproved row, which is what stops somebody who followed a link off
a noticeboard from having a roster and a view of named minors before anyone said
yes.

A name collision cost an hour of confusion: `shell()` already binds `invite` to
a *student* invite (REQ-M.72) and `base.html` reads `invite.user` off it, so
passing a `LeaderInvite` under the same key broke every page that rendered one.
The leader invitation is `leader_invite` now.

**The trap here is the unapproved row.** A candidate is a `Leader` row that is
not yet approved, so `leader_of()` must refuse to return it. Miss that and a
candidate has a roster, an invite link and a view of named minors before anyone
said yes — which is the same class of mistake as the QR endpoint in SPR-M.9,
arriving by a different road.

The mail cap was raised from 10 to 20 per recipient per day (Avi, 2026-09-11) to
leave room for re-sending an invitation. The screen still has to say an invite
was already sent rather than pretend every click worked.

## SPR-M.15 — Her leaders, and one of them in full  `DONE`

**Goal:** the two views she actually lives in.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.15.1 | The leader list: one line each, name, school, students, certified, waiting | REQ-M.94 | DONE |
| F-M.15.2 | Candidates in the same list, marked, not on a screen she must remember | REQ-M.94 | DONE |
| F-M.15.3 | One leader in full: details, statistics, and their students underneath | REQ-M.95 | DONE |
| F-M.15.4 | Seeded demo world, so the views can be judged on real-looking data | — | DONE |

**Found by looking at the demo, not by a test.** A leader with two classes in
one school rendered "עתיד רמלה · עתיד רמלה", because the line was built by
looping classes rather than schools. On a list meant to be scanned, a repeated
word reads as two different things. `Leader.school_names` now mirrors
`Student.school_names`, which had already solved exactly this.

And a pre-existing coin flip was removed from the gate while passing through:
`test_a_miss_says_not_yet_and_never_rejected` uploaded a *different target's*
model to force a miss, but the bank is drawn from at random and two targets can
be close enough that the substitute measures as a pass, at which point the test
was asserting an encouragement message against a success page. It now uploads a
1mm tetrahedron, which cannot match anything, and asserts the attempt actually
failed before reading the words.

**F-M.15.3 reuses rather than rebuilds.** SPR-M.8 already has a roster with
search, paging, track progress and the three certification conditions. The
program manager's view of a leader's students is that screen read through a
wider scope, not a second one, because a duplicate roster is a thing that
drifts.

**On F-M.15.4 and fake users.** Avi wants a demo world to judge the views by,
eventually in production via the Render API. Local seeding comes first and needs
no key. When it does reach production, the accounts must be unmistakably demo
and removable in one command: they would otherwise sit beside real teenagers in
a database that now carries consent records and a retention process. babook's
`purge_demo_data` is the pattern.

## SPR-M.16 — The student detail page  `NOT PLANNED`

Hangs off F-M.15.3. Avi: "we will define it later."




Every leader, every student, the funnel, grouped by `school_name` for the
school-level report Litala's brief asks for.

Shape decided ahead of time (closing Q10): the admin lands on **counts**, by
leader and by school, and drills down. Not a list of every student, which is a
usable landing page for forty people and a useless one for twelve hundred.
Unclaimed students are a queue on this screen, not an error state (REQ-M.65).

## Also still open

- Retire the old production tables, once ACT-M.2 is answered.
- The entrance-exam gap: REQ-M.17 says a leader reviews the attempt and decides,
  but what shipped passes automatically with no human in the loop.
