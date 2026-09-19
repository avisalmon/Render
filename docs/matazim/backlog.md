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

> **A note on vocabulary, 2026-09-11.** Sprints before SPR-M.12 say "admin" and
> "adminship". Those records are left as written, because they describe what was
> decided under the words in use at the time. Everywhere in the product and from
> here on, that role is the **program manager** (מנהל/ת התוכנית), and "admin"
> and "site admin" are retired: see spec §4.3 for why, which is that they
> pointed at two different people depending on who was speaking.

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
| ACT-M.6 | Grant the program-manager role to נעמי (אביב dropped 2026-09-11: "we focus on נעמי only") at babook.co.il/matazim/staff/admins/. You hold every power already as site owner, so you do not need granting. Either at babook.co.il/admin/ under פרופילי מט״צים, ticking מנהל/ת התוכנית, or by setting `MATAZIM_ADMINS` in Render so every deploy re-applies it | Admins existing in production. The build is done | OPEN |

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

## SPR-M.16 — המסלול שלי  `DONE`

**The only role in this system with no screen of its own.** Count them: a leader
has five screens, the program manager now has seven, and the fourteen-year-old
the whole thing exists for has four, two of which are privacy plumbing built in
SPR-M.10. A student who passes the entrance test and joins a leader still has
nowhere that says where they are and what to do next. Their leader can see their
progress through both Scratch courses. They cannot see it themselves.

REQ-M.12 calls this screen "the product". REQ-M.5a is its acceptance test, in
Litala's words: *every member sees immediately where they are, what they have
completed, and what their next task is.*

### What it can honestly show, and what it cannot

The requirement as written promised five cards, three of which name things that
have no model: the next submission due (REQ-M.19), the next יום שיא (REQ-M.27),
and any new feedback. Those are deferred rather than faked. **An empty card that
will never fill is worse than no card**, because it teaches the reader that the
screen does not know things.

What is real today is more than enough for the screen to do its job: the path,
the required track lesson by lesson, the three certification conditions seen
from the member's own side, and who their leader is.

### The idea that shapes it

The leader's screen and the member's screen answer the same question from
opposite ends, and they must never disagree. So this reads through
`matazim.progress` and `matazim.certification`, the same two modules SPR-M.8
built, rather than computing anything of its own. A member being told they have
finished four lessons while their leader is told three is the failure that
matters here, and the only reliable defence is one source.

The certification conditions are the interesting half. The leader's version of
that panel is a decision aid. The member's version is the answer to "what do I
have to do", which is the same three facts arranged for somebody who can act on
them rather than somebody judging them.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.16.1 | המסלול שלי: the five stages as a path, the current one marked | REQ-M.12, REQ-M.5a | DONE |
| F-M.16.2 | Where they stand: what is done, what is next, in one line each | REQ-M.5a | DONE |
| F-M.16.3 | The required track, lesson by lesson, read from the shared reader | REQ-M.12, REQ-M.74 | DONE |
| F-M.16.4 | The three conditions, from the member's side: what *they* must do | REQ-M.76 | DONE |
| F-M.16.5 | Their leader, and the way forward when they have none | REQ-M.43, REQ-M.65 | DONE |
| F-M.16.6 | A standing entry, and the phone | REQ-M.5b, REQ-M.75 | DONE |

### What it turned out to need

**A member without a `Student` row still has learning.** Somebody who registered
and watched three Scratch lessons but has not joined a leader has real progress,
and `cohort_progress` is keyed by user rather than by student row, so the screen
asks about them with a lightweight stand-in rather than growing a second reader
with a different signature. Showing them nothing until they join would have been
the easy version and the wrong one.

**The next step is one sentence, not a list.** Ordered the way the programme is
ordered, so the answer is always the earliest thing still open. A teenager given
five things to do does none of them.

**Ready is not certified, and the page must not blur them.** What it can
honestly say is that the part they control is finished and the decision is now
somebody else's. The test for this initially failed on the section heading
"כדי להיות מט״צ מוסמך", which is the page correctly naming the goal: the
assertion was scoped to the badge rather than the phrase.

The phone guard caught an inline link at 19px, which is the third time an inline
link has been the thing a thumb misses. The rule now covers the conditions list
as well as legal prose.

**Not in this sprint:** lessons rendering inside the מט״צים shell (REQ-M.13).
That is a bigger piece of work and this screen can link out to the course in
babook's own player meanwhile, which is honest about where the learning lives.

## SPR-M.17 — The cohort, and the school report  `DONE`

REQ-M.24, the last screen the spec names for the program manager, and the one it
calls Litala's: the funnel by stage and by leader, grouped by school, with an
export.

**The judgement call is what "export it" means.** Read literally it could be a
spreadsheet of named teenagers, which is also the version somebody would ask for
first. It is the wrong one. Spec §4.10 exists because this product holds data
about minors, and a CSV of their names is the one artefact that leaves the
system entirely: it lands in a download folder, gets mailed to a colleague, and
outlives every access rule we wrote. A school-level report does not need it. So
**the export is aggregate**: counts by stage, by leader, by school, and no
individual is named in it. The named detail stays behind the screens that check
who is asking, which is exactly where SPR-M.9 put the uploads and for the same
reason.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.17.1 | The funnel: how many at each of the five stages, in her world | REQ-M.24, REQ-M.88 | DONE |
| F-M.17.2 | By leader: who has how many, and how far along | REQ-M.24 | DONE |
| F-M.17.3 | By school, which is what Litala's brief actually asks for | REQ-M.24 | DONE |
| F-M.17.4 | Export, aggregate only, no minor named | REQ-M.24, §4.10 | DONE |
| F-M.17.5 | Root sees across worlds; a program manager sees one | REQ-M.88 | DONE |

### Two things the counting turned out to need

**A leader with nobody is the row she most needs to see**, and a report built by
grouping students drops them entirely. The by-leader breakdown is therefore
built from the leaders and joined to counts, not grouped from students.

**A student in no class has to land somewhere.** School lives on the class, and
a class is offered and never required (Q14), so grouping through classes loses
anybody in none. They are counted under a named bucket rather than dropped,
because a school report that silently undercounts the programme is worse than
one that admits an unfiled group. A test asserts the school totals still sum to
the funnel total.

Seen live on the dev demo, the report showed 13 where 14 students exist. That
was not an error: one belongs to a leader owned by a different program manager,
so tenancy excluded them exactly as SPR-M.13 intended. Worth recording because
an off-by-one in an aggregate is the shape a real leak would also take, and this
is what it looks like when the mechanism is working.

**The risk is arithmetic that disagrees with the screens.** A funnel is a lot of
counting, and a count computed here rather than read from the same place as the
roster is a third opinion about the same teenagers. It reads through
`access.visible_students` and the SPR-M.8 modules, and a test compares a total
on this page against the roster it came from.

## SPR-M.18 — Every transition logged  `DONE`

REQ-M.21, and it was the last thing on the buildable list that genuinely did not
exist.

Five places set `Student.status`, and exactly one recorded who had done it:
certification, because REQ-M.78 made that transition's author part of the
record. The other four were anonymous. Every other table in this product answers
"what is true now"; this one answers "who decided, and when", which for a system
holding data about minors is the difference between answering a parent's
question and having to say we do not know.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.18.1 | `StatusLog`, append-only, and `history.set_status` as the one door | REQ-M.21 | DONE |
| F-M.18.2 | Every existing transition routed through it, including the seeder | REQ-M.21 | DONE |
| F-M.18.3 | A guard that fails if anything assigns `.status` outside `history.py` | REQ-M.21 | DONE |
| F-M.18.4 | The history shown on the student's page | REQ-M.21 | DONE |

**The single door is the whole design.** `set_status` writes the field and the
log in one call, which is the only arrangement where the two cannot disagree,
and that holds exactly as long as nothing goes round it. So the guard is the
load-bearing test, the same shape as RULE-3: the rule is only real while
something checks.

The guard caught the demo seeder immediately. Rather than exempt it, the seeder
now goes through the same door, so demo students carry a real history and the
fixture cannot drift from the transitions it is imitating.

## SPR-M.19 — The member can actually learn  `DONE`

REQ-M.13 and REQ-M.14, and it closes a dead end that shipped yesterday.

**המסלול שלי tells a member "להתחיל בסקראץ׳ 1" and gives them no way to start
it.** The next-step card renders a button only when it has a destination, and a
course step has none. The screen the spec calls "the product" is a dead end,
which is the exact failure this product fights everywhere else. It shipped
because the screen was rendered and the copy read without anyone asking what
happens when you click.

There is nowhere legal to send them either. RULE-1 forbids linking out of
`/matazim/`, and REQ-M.13, which says lessons render inside our shell, was TODO.
So today a member can see they are 0/19 with no route to lesson one.

**And a second gap underneath it, found while planning.** The in-shell lesson
renderer built in SPR-M.3 records *no progress at all*: there is no heartbeat in
the template, only an iframe. Generalising it as it stands would let somebody
watch all nineteen lessons inside our walls and stay at 0/19 for ever, with
their leader's roster agreeing. REQ-M.14 is explicit that watching writes
through babook's own path, and this is where that becomes true rather than
stated.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.19.1 | The lesson renderer generalised from one hardcoded slug to the track | REQ-M.13 | DONE |
| F-M.19.2 | Watching reports to babook's existing heartbeat, not a second path | REQ-M.14 | DONE |
| F-M.19.3 | The next step on המסלול שלי actually goes somewhere | REQ-M.12, REQ-M.5a | DONE |
| F-M.19.4 | The track list links lesson by lesson | REQ-M.12 | DONE |
| F-M.19.5 | Scoped to the track: not a general reader for every babook course | REQ-M.47 | DONE |

**F-M.19.5 is the restraint.** It would be one line to let this render *any*
course, and that would quietly turn מט״צים into a second front end for the whole
of babook, with no owner and no design. It renders the courses the programme
requires, and refuses the rest.

### What it cost, and the same mistake twice more

**The RULE-1 guard caught the word "babook" in a JavaScript comment.** A JS
comment ships; a Django `{% comment %}` does not. Naming the parent product in
source a visitor can view is exactly what RULE-2 forbids, however small, and the
reasoning is now in a template comment where it stays with the code and off the
wire.

**The phone guard was measuring a 404.** Its fixture had no courses, so
`/matazim/learn/scratch/` answered 404 and the guard cheerfully checked the
error page's layout. That is the identical failure to the silent sign-in in
SPR-M.8, repeated within an hour of writing it into the_manager.md. It now
asserts the response status. The first attempt at *that* assertion checked the
page title for "404" and passed with the courses removed, because מט״צים's error
page is branded and says no such thing: proving a guard against the case it
exists for is the only way to find that out.

**And a third class-name collision.** `.mz-lessons`, `.mz-lesson-n` and
`.mz-lesson-title` have belonged to the entrance-test lesson list since SPR-M.3,
so every row of the new track list quietly wore that component's border and
radius on top of its own. Renamed to `mz-track-*`.

Three collisions now, and the written discipline did not stop the third. An
attempt to automate it did not survive contact: any rule loose enough to catch a
collision also flagged legitimate cases like `.mz-field` declaring `display` in
two places, and a guard that cries wolf gets suppressed. What replaced it is the
precise mirror image, `test_every_class_a_template_uses_actually_exists`, which
found a real orphan on its first run.

**On RULE-1 and the heartbeat.** Posting to babook's `/api/video-progress/` from
a מט״צים page is not an outbound link: RULE-1 governs navigation, and a member
never leaves the walls. It is the shared engine the charter describes, and
REQ-M.14 requires exactly this rather than a second way of recording the same
fact.

## SPR-M.20 — The certificate  `DONE`

REQ-M.20 and REQ-M.28, and the same shape of gap as the dead end SPR-M.19 just
closed: the system says you have achieved something and hands you nothing.

A leader certifies a student, `Student.status` flips, and the member's screen
says "הוסמכתם ב־11.9.2026. מזל טוב." That is the whole payoff of the programme,
as a sentence on a page nobody else can see. REQ-M.20 says certifying *produces
a printable certificate*, and nothing does.

It matters more than it sounds. A מט״צ certification is the thing a
fourteen-year-old shows a parent, a school puts in a file, and somebody attaches
to an application two years later. A status flag you can only see by logging in
is not that.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.20.1 | A certificate exists as a record, with a stable public id | REQ-M.20 | DONE |
| F-M.20.2 | A page worth printing, in מט״צים's own design | REQ-M.20 | DONE |
| F-M.20.3 | Verifiable by that id, so a school can check one is real | REQ-M.20 | DONE |
| F-M.20.4 | Reachable from המסלול שלי and from the leader's view of a student | REQ-M.28 | DONE |
| F-M.20.5 | Revoking certification invalidates it, and says so | REQ-M.78 | DONE |

**The privacy judgement, and it is the interesting one.** A verification page has
to be readable by somebody with no account: that is the entire point, since a
school checking a certificate is not a member. But the person on it is a minor,
and §4.10 governs. So the public view shows the least that still verifies: the
name on the certificate, the date, and that it is valid. No email, no school, no
progress, no leader, and nothing that lets the id be walked to find other
children. The id is a UUID for exactly that reason.

**F-M.20.5 is the one that is easy to forget.** Certification is revocable
(REQ-M.78), so a certificate is not a permanent fact but a current one. A
printed copy will outlive a revocation, which is unavoidable, but the verifiable
one must tell the truth at the moment it is asked.

### Three found by looking, and one invariant that had already broken

**The demo's certified students had no certificate**, because the seeder set the
status through `set_status` rather than `certify()`, and `certify()` is what
issues one. So the screen 404d for somebody who *was* a certified מט״צ. That is
precisely the state a real member must never reach, and there is now a guard:
nothing outside `certification.py` may write `Student.CERTIFIED`. It was proved
by reintroducing the bug and watching it fail.

**The printed verification URL was reordered by RTL.** A left-to-right URL in a
right-to-left paragraph has its trailing slash moved to the front, so the line
read `/http://…/verify/054be…`. On a page whose entire purpose is to be printed
and typed back in, that is a dead link rather than a nit. `dir="ltr"` isolates
it.

**The prototype welcome modal blocked the verification page.** A school checking
a certificate had to dismiss a notice about joining the programme before it
could read the answer. REQ-M.39 is for somebody arriving at the product; a
verifier is joining nothing. Only visible by loading the page as a stranger.

**And a bug the tests caught that production would not have.** The name on a
certificate was read through `user.profile`, which babook's post-save signal
populates blank, so an in-memory User can carry a cached empty name while the
row has the real one: the certificate would have been issued to an email
address. The name is queried now.

**Reuse, per Avi.** babook renders course certificates already, with a print
stylesheet and a UUID-addressed verify page. The *pattern* is worth copying and
the page is not: a מט״צ certification says something different from "you
finished a course", and RULE-1 means it cannot be babook's page anyway.

## SPR-M.21 — Every screen through the contract  `DONE`

A consolidation sprint rather than a feature one, and the number is the argument
for it: **41 screens exist and 21 were in the contract.** Twenty-two had never
been rendered by it.

Given the record — thirteen sprints, and every screen actually rendered had a
defect no test had caught — twenty-two unrendered screens is not a clean slate.
It is a backlog of defects nobody has looked at. Some are covered by the phone
guard for layout, but nothing had checked them for the content faults that kept
recurring: raw database keys, labels stretched to banner width, text repeated
because a list looped the wrong thing, copy that is wrong in the empty state.

The buildable feature work had also run out. Four small requirements remain that
need no decision from Avi; the rest are blocked on defining what submissions,
events and notifications are. So this is a natural stopping point rather than an
interruption.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.21.1 | The contract renders anonymously, for the public screens | §4.10 | DONE |
| F-M.21.2 | All 22 uncovered screens added, in the states they can be in | Step 4a | DONE |
| F-M.21.3 | Whatever that finds, fixed | — | DONE |
| F-M.21.4 | The contract asserts the screen it landed on | Step 4a | DONE |
| F-M.21.5 | Contrast measured on every screen, against WCAG AA | §4.10 | DONE |

### What it found  `DONE 2026-09-12`

**The first finding was the contract itself.** All 44 entries passed on the
first run. That was not a clean sweep: `member/apply` was signed in as a member
who already had a leader, so `apply` redirected and the entry spent its life
measuring the profile page. Correct product behaviour, broken test, and the
**fourth** time in this project a guard has passed while looking at the wrong
page. `_assert_landed` now fails the run when a screen redirects, and with it
turned on exactly one of the 44 was lying. Two entries were also only rendering
their empty state (`member/test-task` and `pm/targets` had no targets in the
fixture), which is the same fault in a quieter form: the entry claims a screen
and covers a corner of it.

Then, from actually rendering them:

| Found | Where | Why no test saw it |
|---|---|---|
| Footer floated mid-screen with dead grey below | every short page | nothing measured page height |
| `{# … #}` rendered as visible English | the entrance-test upload panel | Django's `{# #}` is single-line only; mine was not |
| The file picker said "Choose File / No file chosen" | the entrance test | the browser's own widget, in the browser's own language |
| Two CSS variables that were never defined | the new picker | an undefined `var()` drops the declaration silently |
| `leader@example.com` where a name belongs | המידע שלי, and the downloaded file | a staff address disclosed to a minor |
| "0 הדרכות שהתחלתם, 1 תעודות" | המידע שלי | counted `Enrollment` only, so watching did not count |
| "עוד לא ניגשתם" to somebody who had passed | המידע שלי | read the attempt rows, not the profile field |
| A button underlined and forced back to `display: inline` | המידע שלי | `.mz-legal p a:not(.mz-linkbtn)` forgot `:not(.mz-btn)` |
| **Another institution's children in נעמי's counts** | ניהול | `Student.objects.count()`, unscoped |
| All four learners called מט״צים | ניהול | one had earned it (§4.9) |
| "מסכי המובילים ... ייבנו בספרינטים הבאים" | ניהול | shipped scaffolding; those screens exist now |
| **15 pieces of text under WCAG AA contrast** | across the product | nothing had ever measured it |

The contrast finding is the largest. The muted grey carrying most of the
explanatory copy in this product measured **3.08:1** against a 4.5:1 standard,
and it was carrying the account-deletion control the law requires us to offer.
The ✓ that means "you passed" was **2.37:1**. The hero headline on the public
front page was **2.09:1** against a 3:1 standard for text that size.

**Three checks were added to the contract, not just three fixes**, because each
of these was invisible to it: where the page landed, unrendered template syntax
in visible text, and measured contrast. A fourth went into the smoke gate: a
grep for `var(--x)` with no definition, which costs nothing and runs on every
push.

**The hero colour is the one open question.** `--mz-teal` is the brand, and at
67px it only has to clear 3:1; it was at 2.09:1. It now uses `--mz-teal-deep`,
which is 3.08:1 — the smallest change that meets the standard. A deeper teal
would be more comfortable and is Avi's call, not mine.

**What this is not.** It is me checking my own work again, which has twice been
said here to be unrepeatable. The difference is that the contract makes it
mechanical rather than a matter of my attention: the screens are enumerated, the
properties are asserted, and a screen missing from the list is now visible as a
gap rather than invisible as an oversight.

**The validation this still does not replace** is somebody real using the
product. Production has zero leaders and zero students; every screen has been
judged by me, against data I invented, in states I chose.

## SPR-M.22 — The student detail page, for a leader  `DONE 2026-09-16`

Hangs off F-M.15.3. Avi: "we will define it later." Later arrived on
2026-09-16, with the definition handed over: "You define leader detail page."

**What the page is for.** The screen a leader opens when one teenager is the
subject, rather than a queue or a roster. It answers four questions in order:
where are they and what is outstanding; what have they made and what did I say
about it; what have they taught; and who moved them, when.

Three of those were already here. The missing one is the one the programme is
actually about.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.22.1 | Their work on their page, every attempt, newest first | REQ-M.19, M.125 | DONE |
| F-M.22.2 | The feedback quoted on the page, not behind a click | REQ-M.123 | DONE |
| F-M.22.3 | A leader sees their own students, never the school's | REQ-M.145 | DONE |

### The hole this closes

A leader's only route to a submission was the queue on האזור שלי, and
`waiting_for` filters `status=WAITING`. So the moment a leader answered a piece
of work it left every screen they have. Nothing linked to it from the roster,
from the student's page, or from anywhere else: the only way back was typing
`/matazim/work/<id>/` from memory.

Which means the person who signs the certificate could not look back over the
body of work they were certifying. On a page whose docstring says "one person,
in as much detail as a leader needs", the detail that was missing was the work.

The words are quoted on the page rather than linked, because REQ-M.19 says the
feedback is the point rather than the flag, and a leader about to certify
somebody should be reminded what they already told them.

### The visibility question, closed after nine sprints

Avi, the same day: **"מוביל רואה את כל התלמידים הקשורים אליו. לא לפי בית ספר."**

That answers Litala's צפייה בכל תלמידי בית הספר, which SPR-M.37 found had been
neither accepted nor refused since her brief arrived. It is refused, and it is
now REQ-M.145.

No code changed: `visible_students` already filtered on `leader=leader`. What
changed is that the rule is chosen rather than incidental, and tested at the
seam it is actually about. Every existing tenancy test puts the two leaders in
different institutions; this one puts them in the same school, which is the
case Litala was asking about and the only one that could have quietly drifted.




Every leader, every student, the funnel, grouped by `school_name` for the
school-level report Litala's brief asks for.

Shape decided ahead of time (closing Q10): the admin lands on **counts**, by
leader and by school, and drills down. Not a list of every student, which is a
usable landing page for forty people and a useless one for twelve hundred.
Unclaimed students are a queue on this screen, not an error state (REQ-M.65).

## SPR-M.23 — What the coherence pass found  `DONE`

Item 2 of the review: read the spec end to end after roughly eight mid-flight
amendments and make it tell the truth. The structure was sound — 107
requirements, no duplicate ids, no gaps in the numbering, no reference to a
requirement or section that does not exist — so the corrections were all about
meaning rather than bookkeeping.

**Five corrected in the spec, no code needed.**

1. **REQ-M.18 named the wrong person.** It said the program manager moves
   `applied` to `in_training`, which contradicts REQ-M.10 (the leader confirms)
   and contradicts the code, which has done it the leader's way since SPR-M.6.
   It sat TODO while the work was shipped by somebody else. Now says the leader,
   and is DONE.
2. **REQ-M.31 was two requirements wearing one number.** "A student picks their
   leader" shipped with the open door. "A leader can be swapped, and the change
   is logged" never did. One status cannot be true for both, so the swap is
   REQ-M.98 now.
3. **REQ-M.43 waited on a table that was deliberately killed.** "Until
   `Membership` exists" could never be satisfied: `Membership` was dropped in
   §4.8 on purpose.
4. **REQ-M.62, M.68 and M.69 still said "admin"** where §4.3 renamed the role to
   program manager. Django's own admin keeps the word, because that is what it
   is called.
5. **REQ-M.16 was marked DONE and is not.** See below; this one has a product
   behind it.

**Three that need building.**

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.23.1 | The application is stored and shown to the leader deciding | REQ-M.16 | DONE |
| F-M.23.2 | Return to intent, with the destination treated as untrusted | REQ-M.8 | DONE |
| F-M.23.3 | A student can be moved to another leader, and it is logged | REQ-M.98 | DONE |
| F-M.23.4 | The contract can reach a screen that needs an id | Step 4a | DONE |

### What building it turned up  `DONE 2026-09-12`

**The catalogue could not name a detail screen at all.** Every path in
`SCREENS` was a plain string, so any screen whose URL carries a database id was
structurally impossible to add: the student detail page a leader reads, the
leader detail page a program manager reads, the public certificate
verification. SPR-M.21 reported that 41 screens were catalogued and all of them
passed. It was 41 **static** screens, and the detail pages had never been
rendered by anything. Paths may be callables over the world now, and the
catalogue is 50 entries.

Two things that found, both the same shape as the `member/apply` defect:

- **The certified student in the fixture had no certificate.** The world set
  the status directly, so `student.certificate` did not exist and the public
  verify page could not be catalogued. It goes through `certify()` now. This is
  the same mistake the demo seeder made, which is twice.
- **The move control rendered nowhere.** The world has one leader, so there was
  nobody to move a student to and the control was correctly hidden — an entry
  covering the screen without ever drawing the thing just built. There is a
  `second_leader` state now.

And one from reading the paint rather than the tests: the new file picker used
two CSS variables that do not exist. `var(--mz-accent)` is not an error, the
declaration is simply dropped, so a wrong colour reads as a design choice. The
smoke-gate grep added in SPR-M.21 caught it in a tenth of a second, which is
the first time one of these guards has paid for itself on the sprint after it
was written.

**F-M.23.1 is the one that matters.** REQ-M.16 says applying creates a `Student`
row "plus an `Application`". There is no such table in either app. The form
still asks a fourteen-year-old for their grade, why they want to join, and what
they have built; it requires the first two, validates them, and then discards
all three. The leader being asked to accept that person sees a name and an
email. So we make a child write why they want in, throw the answer away, and
then have somebody decide about them with nothing to read. It is a broken
promise and a decision taken blind, and it is the clearest example yet of the
pattern this whole review keeps finding: the screen renders, the test passes,
and nobody had followed the data to the end.

**F-M.23.2 is smaller but has a trap in it.** The login view already honours
`request.POST.get("next")` and no template has ever sent it, so the line cannot
fire and the feature reads as done in the code. Whoever builds it must treat the
destination as untrusted and follow it only inside `/matazim/`, or
return-to-intent becomes an open redirect straight out of the walls (RULE-1).

**What this pass did not do** is check the spec against a person. It checks the
spec against itself and against the code. Item 3 is still the one that finds the
things neither of those can.

## SPR-M.24 — Every role's own journey  `DONE`

Avi, 2026-09-12: walk each role through every view it sees and check five
things — was it intuitive to find, is it self-explanatory, is the information
that role needs there or one clear click away, is it designed well, and do all
the pages that role needs exist. Then, mid-review: "hide everything this role
does not need to see. Make everything on a need-to-know basis."

Answered mechanically rather than by opinion. A crawler signs in as each of
**nine** roles, starts at their entry point, and follows only the links that
role can actually see; anything a role may open but never reach by clicking is a
screen findable only by knowing the URL. Then every screen rendered at 390px
and looked at. Full write-up in the review file; the short version follows.

### Three things were already broken and are fixed

**The phone guard's overflow check could not fail.** It has claimed since
SPR-M.7 that nothing is wider than the screen at 390px. It compared
`scrollWidth` against `window.innerWidth` inside a mobile-emulated context, and
Chromium grows the layout viewport to fit content that does not fit: on the
program manager's team screen `innerWidth` became **501** in a 390px window, so
the comparison was 501 against 501. The page really was 500px wide, so נעמי had
to scroll sideways to reach the reject button, and the guard called it fine.
Now measured against `clientWidth`. Verified by putting the defect back.

**Roster rows could not wrap.** `.mz-training li` is a flex row with no
`flex-wrap` and its actions are `flex: none`, so any row with wide actions
pushes the page over. The candidate row carries an approve button *and* a reject
link and was the widest row in the product.

**The phone fixture had no candidate leader**, which is why the two above
survived together: the widest row only exists while somebody is waiting, so it
never rendered. Fifth time this session a defect turned out to live in a state
no fixture creates.

### What the review found

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.24.1 | A candidate leader gets a screen that knows they are waiting | REQ-M.99 | DONE |
| F-M.24.2 | האזור האישי belongs to whoever is reading it | REQ-M.100 | DONE |
| F-M.24.3 | The menu is the role's menu | REQ-M.101, M.5b | DONE |
| F-M.24.4 | Need-to-know as a property of every screen | REQ-M.102 | DONE |
| F-M.24.5 | The teachers' door gets a link | REQ-M.103 | DONE |
| F-M.24.6 | The entrance task stops depending on the teaching content | REQ-M.104 | DONE |
| F-M.24.7 | The review is kept as a test, not left as a pass | Step 4a | DONE |

### What building it turned up  `DONE 2026-09-12`

**The review is now `tests/test_role_journeys.py`.** It checks both directions
for nine roles: that each can click its way to everything it needs, and that
its menu carries nothing it has no use for. It earned its place within minutes
of being written, twice.

First, **trimming the menu orphaned the public sections.** I moved them "behind
אודות התכנית" on the assumption that אודות links them. It does not, so בתי הספר
and המסלול השנתי became unreachable for every signed-in role. The audit caught
it on the first run after the change; without it this would have shipped as a
quieter version of the same bug the review was written to find. They live in the
footer now, which is on every page.

Second, and worse, **the profile view had a second copy of "is this a member".**
`shell()` lets a view's context win, so the weaker copy — which forgot about
staff — silently overrode the correct answer, and נעמי carried a pupil's menu on
האזור האישי while carrying the right one on every other page. Exactly the shape
RULE-3 exists to prevent for learning, and it turns out roles need the same
rule. There is one `_is_member` now.

Also restored during the sprint: **hiding מבחן הכניסה once passed was wrong.**
REQ-M.63 says a passed test is *marked*, not hidden, and hiding it also made the
whole test chain unreachable for anyone who had passed. Marked with a ✓ and kept.

One thing deliberately not done: a leader can still open `/matazim/learn/scratch/`
by typing it. Nothing about anyone else is exposed there, and blocking a teacher
from reading the material their students are learning would be need-to-know
applied past the point of sense. What changed is that it is no longer *offered*
to them, which was the actual defect.

**The candidate leader is the worst-served role in the product**, and it is the
one a real teacher meets first. REQ-M.93 creates the state on purpose and
nothing acknowledges it exists. כניסת מובילים tells them "already invited? sign
in with the email you gave the team, and this page will take you straight to
your area" — they are signed in, with that email, and it takes them nowhere.
Their profile then shows them, an adult teacher, a **parental-consent panel**,
tells them their leader is not assigned yet, that they have not joined the
programme, that they have not sat the entrance test, and offers them a button
into the pupil journey. From their side, registering through the invitation
appears to have done nothing.

An approved leader with four students sees the same profile. That is the
clearest need-to-know failure here: not a permission breach, but a product that
does not know who is reading it.

**The menu never changes for a role.** Eight marketing items on every page for
everybody, forever. A student mid-programme reads nine of which two are theirs;
a leader and a program manager both carry המסלול שלי, a pupil's screen, when
§4.9 is explicit that a leader is not a mataz. REQ-M.5b has promised two navs
since SPR-M.1 and is still WIP.

**One robustness finding worth more than it looks.** The entrance-test task
button lives inside `{% if lessons %}`, and those lessons are babook's
`tinkercad` course. Unpublish that course and the gate to the whole programme
becomes unreachable while the task itself still works. Nothing in the deploy
guarantees it: not in `load_course_from_manifest`, only read by `seed_matazim`.

### What this review could not do

It checked the product against itself: nine synthetic roles, walked by a
crawler, judged by me. It cannot say where a real fourteen-year-old gives up, or
what נעמי tries that has no screen at all. Item 3 of the earlier review is
still the only thing that answers that.

## SPR-M.25 — The improvement loop  `DONE`

Avi, 2026-09-12: נעמי gets a way to say anything about the app from wherever she
is standing in it. It lands in a log. He reads it and approves with one press.
When he says so, a sprint is built from what is approved, and when it ships a
summary goes to both of them. "A customer auto improve process. Just small
guard of me in the middle."

This is the answer to the sentence every review in this project has ended on:
each one checks the product against itself, and none of them can say what a
real person tried to do and could not.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.25.1 | The `Request` model, with the screen it was sent from | REQ-M.105, M.112 | DONE |
| F-M.25.2 | The lamp, on every screen the owning roles use | REQ-M.106 | DONE |
| F-M.25.3 | The form, three fields and a warning about names | REQ-M.105, M.113 | DONE |
| F-M.25.4 | Her log: what she asked, and what happened to it | REQ-M.107, M.111 | DONE |
| F-M.25.5 | Avi's screen: read, assessment, approve or decline in one press | REQ-M.108 | DONE |
| F-M.25.6 | The assessment, through the site's existing model path | REQ-M.109 | DONE |
| F-M.25.7 | The summary mail when a sprint ships a request | REQ-M.111 | DONE |
| F-M.25.8 | A guard that the queue cannot start work | REQ-M.110 | DONE |

### What building it turned up  `DONE 2026-09-12`

**The assessment took three versions of the prompt, tested against three real
requests each time.** This is the part worth reading, because the first two
versions would both have shipped looking fine.

Version one said **"good idea" to all three**, including one that REQ-M.24
already covers and one that is plainly out of scope. An assessment that agrees
with everything is worse than none, because it looks like a second opinion.

Version two added a scope boundary and the line "most requests are out of
scope". It then said **"out of scope" to all three**, including the good one. A
small model handed a strong steer repeats the steer.

Version three works: it must **name the closest requirement ids before giving a
verdict**. Grounding the judgement in something specific fixed the accuracy, and
it also made the output checkable — Avi reads "כבר קיים · REQ-M.24" and can
verify that in a second, instead of taking a verdict on faith. It also needed
the requirement **bodies**, not just the titles: asked about exporting the
cohort report it said out of scope, while REQ-M.24 [DONE] says "and can export
it" in text the model had never been shown, because "export" is in the body and
the title is only "Cohort view and reporting". And it runs on `gpt-4o` rather
than the site default, because matching a Hebrew sentence against a hundred and
twenty English summaries is past what the mini model does reliably. On the three
test requests the final version answers: לצמצם citing REQ-M.33 and M.19 (she
asked for email, notifications are already specified and unbuilt), כבר קיים
citing REQ-M.24, and מחוץ לתחום.

**The safety guard needed rewriting too.** REQ-M.110's source check first
grepped for words like "schedule" and failed on the docstring that explains the
rule. It parses with `ast` now and looks at imports and calls, which is what the
requirement is actually about. Verified by adding a `threading.Thread` on
purpose: it names both the import and the call.

**Two existing guards caught me**, which is the first time this has happened on
the sprint after they were written. The class-name check found `mz-alert-bad`,
which does not exist in the stylesheet, and the comment check found a
multi-line `{# #}` — my fourth this session. I found the second one seven
minutes into a browser run when the smoke grep would have found it in a fifth
of a second, so the order is now written down in the_manager.md: smoke, then
the sprint marker, then screens.

### The four properties this is built around

**The log is the customer voice; the backlog stays the plan of record.** Her
words are stored verbatim and never edited by me. A sprint that takes a request
writes the sprint and feature id onto the row. It must not become a second plan:
this file says what is being built, and this codebase has paid twice in one week
for two copies of one truth — RULE-3, and the two `is_member` calculations in
SPR-M.24 that had נעמי carrying a pupil's menu on exactly one page.

**The queue cannot start work.** Approving marks a row ready and summons
nobody. Nothing here triggers a sprint, schedules anything, or sends me a task.
The trigger is Avi in conversation, every time. Written as REQ-M.110 rather than
left as a habit, because a self-executing queue is a different product with a
different risk profile and the difference is invisible from the screens. It gets
a test, because a property nothing checks is a property that erodes.

**The assessment advises and never decides.** Each row carries a written view:
good idea, duplicate of something already asked or already specified, out of
scope, and what it would touch. Generated through `app.ai_chat.call_openai`, the
same path the rest of the site already uses, with the requirement titles and the
open requests as context. Labelled as machine-written, because it will sometimes
be wrong, and Avi's press is the decision. Fail-open like the content-safety
code: no model, no assessment, request still saved.

**The loop closes where it started.** She sees received, approved, done in
sprint N, and what was built. A request log whose requester cannot see the end
of it is a suggestion box.

### Decisions taken up front

**Scoped to the role, not to נעמי.** Avi said "only we", and today that is
exactly the two of them because she is the only program manager. But the product
is built for many institutions, so this is gated on the program-manager role
with each manager seeing their own requests and root seeing all — the same
scoping as every other staff screen (§4.4). The second institution then works
without a rewrite.

**A lamp rather than a nav item.** The value is that it is there at the moment
she notices something. A menu entry she has to go and find is one she uses once,
and SPR-M.24 just finished cutting her menu down to six items.

**Avi's own requests arrive approved.** Asking him to approve his own request is
a ceremony with no reader.

**Two smaller ones.** The summary mail goes to root and to the requester's own
account address under the standing 20-per-day cap, which means נעמי's demo
account at `@demo.invalid` can never receive it, correctly. And the form says
not to name a student: free text about a programme is one sentence away from
free text about a child, and that would otherwise be a new category of personal
data sitting outside everything §4.10 describes.

## SPR-M.26 — Retention for request rows  `DONE`

Caught while checking whether SPR-M.25 was ready to push, and worth recording
as a near miss: REQ-M.113 says feedback rows fall under REQ-M.86 like
everything else, "a stated retention period, enforced by a command". Only the
first half shipped, the warning on the form that stops a student's name arriving
in the first place. `matazim/retention.py` still covers failed entrance attempts
and nothing else, so no period is stated or enforced for `Request` rows.

I had marked REQ-M.113 DONE. That is precisely the fault the SPR-M.23 coherence
pass existed to find, made two sprints after finding it, which says something
about how easily a requirement gets marked done on the strength of its most
visible half.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.26.1 | A stated retention period for request rows | REQ-M.113, M.86 | DONE |
| F-M.26.2 | The retention screen counts them, and a person approves the purge | REQ-M.87 | DONE |

**Needed a number from Avi**, which is why this sprint held instead of guessing
one. A request and its outcome are the record of why the product changed,
which argues for keeping them a long time; they are also free text written by
a member of staff, which argues for not keeping them forever. The suggestion
written here was to keep the request and what was built indefinitely as
product history, and hold the retention rule over *declined* rows and anything
never acted on, at the same 365 days as everything else.

**Built two sprints later, under SPR-M.36, with a different number than the
suggestion above.** `REQUEST_DAYS = 730`: a closed request (done or declined
alike, no split between them) is purged 730 days after `decided_at`, whole row
and its conversation with it; an open request is never purged, however old.
See SPR-M.36 for the reasoning. This row was left `PLANNED` after that shipped
— the same stale-status mistake this sprint's own opening paragraph is about —
until the next full backlog read (2026-09-15) caught it.

## SPR-M.27 — Proposing a change is a conversation  `DONE`

Avi, 2026-09-13, the evening SPR-M.25 shipped: "I want the experience of
proposing an improvement to be like a chat, so she will write what she wants,
you will comment and suggest and discuss, and there will be a button סיים שיחה
ושלח בקשה when she just want to submit. For me, when approving, I want to see
your recommendation."

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.27.1 | `RequestMessage`, and a request that can be a draft | REQ-M.115, M.117 | DONE |
| F-M.27.2 | The conversation screen, one turn at a time | REQ-M.115 | DONE |
| F-M.27.3 | סיים שיחה ושלח בקשה, live from the first moment | REQ-M.116 | DONE |
| F-M.27.4 | A recommendation for Avi, built from the whole conversation | REQ-M.118 | DONE |
| F-M.27.5 | The transcript on the approval card, her words first | REQ-M.117, M.112 | DONE |
| F-M.27.6 | A proposed wording she can adopt or ignore | REQ-M.119 | DONE |
| F-M.27.7 | The mini gate never calls OpenAI; the full regression may | — | DONE |
| F-M.27.8 | The prompt carries the rules, the design and every screen | REQ-M.120 | DONE |
| F-M.27.9 | A scripted model, so the loop can be tested without a key | REQ-M.121 | DONE |

### The prompt, and how it is built  `DONE 2026-09-13`

Avi: "How do you plan to build the prompt for this chat so it will know the spec
and the design of the site?" The honest answer at the time was that it knew the
spec and not the design: 129 requirements and nothing about the shape of the
product, so the model would have discussed a sidebar that does not exist or a
link to babook that RULE-1 forbids.

It now carries, in about 51,000 characters:

- **§2.3, §3.2, §4.3 and §4.4 verbatim** — the four rules, the design system,
  the roles, and tenancy.
- **Every screen that exists**, read from the URL resolver. 44 of them.
- The requirement list, the open requests, the screen she opened from, and the
  conversation.

**Everything derived, nothing hand-copied.** A paragraph pasted into a prompt
string is a second copy of the truth that drifts the first time somebody edits
the spec, and a screen added next month has to reach the model without anybody
remembering that a prompt exists.

**Verified live rather than assumed.** Asked for a link to the main site, the
model refuses and names RULE-1. Asked for a sidebar, it says there is none today
and asks where she would want one. Neither answer was possible before.

**And it caught a false rule on the way in.** I was about to tell the assistant
"the site says הדרכות, never קורסים" and checked first: מט״צים says הדרכות 14
times and קורסים 6, including the nav item every member reads. That is logged
for Avi rather than papered over in a prompt.

### The scripted model  `DONE 2026-09-13`

Avi: "you can actually imitate it as if you are your AI. You can get the prompt
and say what you would have responded." `matazim/model_script.py` holds replies
written by hand after reading the real assembled prompt, each naming the fact it
depends on, so that if that fact stops reaching the model the fixture is a lie
and the comment says where to look.

A fixture written against an imagined prompt tests a parser. One written against
the real prompt tests whether the model was given enough to answer, which is the
part that is actually hard. It runs only under `MATAZIM_SCRIPTED_AI=1`, never in
production, and says in the log that the words are not a model's.

### What building it turned up  `DONE 2026-09-13`

**The suite was making real OpenAI calls on every run.** Found while running
the SPR-M.25 tests: `matazim.assess` reads `settings.OPENAI_API_KEY` and the
developer machine has a real one, so the gate that runs after every change was
paying for chat completions and depending on somebody else's uptime. Avi's
rule, given the same evening: "In full regression you can call real openai. But
not regular mini regression." The key is blanked unless `MATAZIM_LIVE_AI=1`,
which the daily full run sets. Blanking is not avoidance: every caller here
fails open when there is no model, so the quiet run exercises the path that has
to work anyway.

**Avi's amendment sharpened the design.** "Her words stays. The chat can
propose new wording." Those two only hold together if a proposal is an offer
rather than an edit: the assistant may end a turn with a suggested phrasing, it
renders as a control rather than as prose, and nothing changes until she presses
it. Adopting stores the text as a turn of **hers**, because she chose it, and
her original stays as the opening line of the conversation. Both are on the
card, and anybody reading it later can see which is which.

**The rule most likely to rot got the strongest test.** REQ-M.116 says the
conversation may never stand between her and the button, which is exactly the
kind of rule that dies quietly to one reasonable-looking clarifying question.
`test_she_can_send_before_the_assistant_says_anything` was verified by adding
such a gate on purpose and watching it fail.

### The three decisions this rests on

**The conversation never gates the request.** The send button is there before
the assistant has said anything and stays there after any number of turns. This
is the one that could quietly go wrong: an assistant that asks one more
clarifying question before letting somebody complain is a suggestion box with
extra steps, and she would use it once. It gets its own test.

**Her words stay verbatim.** REQ-M.112 does not bend for this. Every message she
writes is stored exactly as typed and the request body is hers, not a summary of
her. What the conversation adds is context around it, and the assistant's turns
are labelled as the assistant's so nobody reads them back as hers a year later.

**A draft is not a request.** A conversation she starts and abandons is not
work anybody owes her an answer on. Drafts stay out of Avi's queue entirely and
appear on her own log only as drafts she can resume or discard.

### Why a conversation is worth the build

Roughly half of what anyone asks for in a product this age either already
exists or is three sentences from being buildable. SPR-M.25's own assessments
showed both shapes on the first three test requests: one was already covered by
REQ-M.24, and one proposed a specific mechanism (an email) for a need that was
already specified more broadly as notifications. A form collects those as
requests and spends a sprint discovering it. A conversation finds out while she
is still typing, and she gets the answer to the first kind immediately rather
than in a fortnight.

## Decided: מט״צים says הדרכות  `DONE 2026-09-13`

Avi, one word: "הדרכות". Swept through every template a reader sees — the nav
item on every page, the section title, and five sentences that called the
entrance test a קורס. URLs, view names and model slugs stay `course`, because
that is babook's vocabulary for its own tables and nobody reads it.

Guarded in the smoke gate, because copy drifts back the moment nobody is
looking, and told to the request assistant, which can now say it because it is
finally true.

## Was open: מט״צים calls the same thing two names

Found 2026-09-13, while building the context for the request conversation. I was
about to teach the assistant "the site says הדרכות, never קורסים", which is the
brand rule for babook, and checked first. מט״צים does not follow it: its own
templates say **הדרכות 14 times and קורסים 6**, and the nav item every member
reads on every page says **הקורסים**. The spec is split the same way, 7 against 4.

So the rule went out of the prompt rather than into it. An assistant that
corrects her vocabulary to something the screen beside her contradicts is worse
than one that says nothing, and a prompt is the wrong place to fix a product's
copy anyway.

Needs a decision from Avi, and it is a small one with a visible result: either
מט״צים adopts הדרכות like the rest of the site, or it keeps קורסים deliberately
as its own voice and the four stray הדרכות get changed. Either way the assistant
can then be told the truth.

## SPR-M.28 — יוצרים: submissions and the feedback that matters  `DONE`

Avi, 2026-09-13, choosing the order: the five stages of the programme are
מתמיינים, לומדים, יוצרים, מדריכים, משפיעים, and two of them exist. This is the
third.

**Why this one first.** A leader can currently accept a student, look at a
roster and certify them. That is administration, not mentoring. The spec has
said the important part since it was written: *"the feedback is the interaction
that matters here, not the approve flag."* Until a member can put work in front
of their מוביל and read what they said about it, נעמי's leaders have nothing to
do between accepting somebody and certifying them, and מט״צים is a completion
tracker with a 3D test on the front.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.28.1 | `Submission` and `Feedback`, with the file kept privately | REQ-M.19, M.122 | DONE |
| F-M.28.2 | The member hands work in, and sees what came back | REQ-M.19, M.123 | DONE |
| F-M.28.3 | The leader reads it, returns it with words, or approves it | REQ-M.19, M.123 | DONE |
| F-M.28.4 | Work waiting on a leader is counted where they stand | REQ-M.124 | DONE |
| F-M.28.5 | A returned submission can be answered with a new version | REQ-M.125 | DONE |
| F-M.28.6 | Submitting moves the student to יוצרים, logged | REQ-M.74 | DONE |

### What building it turned up  `DONE 2026-09-13`

**The leader could not open the work.** The first version of the review screen
showed a member's project link as dead text, on the theory that RULE-1 forbids
outbound links. It does not: the rule governs this product's own navigation and
its test excepts external links for exactly this case. So a leader was being
asked to copy and paste a URL in order to do the thing the screen exists for.
Clickable now, with `rel="noopener noreferrer"` because the address was typed
by a fourteen-year-old, and the address stays visible underneath so nobody is
asked to click something they cannot read. Found by rendering the screen, which
is now four sprints in a row.

**Handing in another project would have un-certified a מט״צ.** The obvious way
to write the stage move is unconditionally, and a certified member showing
their leader a new project would have gone back to יוצרים. It moves forward
only from מתמיינים or לומדים.

**The terminology decision reached further than the templates.** Renaming
הקורסים to ההדרכות in the nav broke `test_logged_out_nav_matches_the_prototype`,
which had been asserting Litala's original labels since SPR-M.1. Updated rather
than loosened: the order is what that test is really protecting, and it still
checks it.

### Decisions taken up front

**A return with no words is refused.** "Returned" on its own tells a
fourteen-year-old they failed and not what to change, which is the exact
opposite of what this stage is for. Approving may carry words and does not have
to, because "well done" is optional and "here is what to fix" is not.

**The file is a minor's work and is kept like one.** Outside `MEDIA_ROOT`, under
a random name, reachable only through a view that asks who is looking — the same
path the entrance test uses, for the same reason it was moved there: §4.10 P2
found those files sitting in public `/media/` under names like `יובל כהן
מודל.stl`. Reusing that machinery rather than writing a second one.

**It does not gate certification.** Certification is the entrance test, two
הדרכות, and a leader's approval, and Avi settled that definition. יוצרים is the
stage after, so a submission moves the student's stage and leaves the
certification rule alone.

**Each version is its own row.** A resubmission that overwrote the first would
destroy the very thing the feedback was about.

## SPR-M.29 — The written lesson, in our own chrome  `DONE`

Avi, 2026-09-13: "I want the trainings based on babook infrastructure but the
views are matazim dedicated. It's a matazim experience."

The structure already held — one record of progress, no way out of the walls —
but the experience did not, and checking rather than assuming found a live
defect rather than a latent one.

**The lesson page rendered `notes_markdown|truncatewords:60` into a grey
paragraph.** Raw markdown, hashes and asterisks included, cut off after sixty
words. Eighteen of the nineteen סקראץ׳ lessons carry written notes and all
nineteen carry a summary, so a מט״צ was reading a fragment of the lesson
rendered as source code while a learner on the other product read the whole
thing — inside the product that is supposed to be the better experience.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.29.1 | The notes rendered properly, in מט״צים's typography | REQ-M.126 | DONE |
| F-M.29.2 | The quiz, when a lesson has one | REQ-M.126, M.14 | DONE |
| F-M.29.3 | The reflection, when a lesson has one | REQ-M.126 | DONE |
| F-M.29.4 | One rendering of notes, shared with the other product | RULE-3 | DONE |

### What it rests on

**One rendering, not two.** The alternative was eight lines copied out of the
other product's view. `app/lesson_notes.py` now holds it and both call it, so a
lesson's notes look the same wherever they are read and an improvement reaches
both. This codebase has paid for a second copy of one truth twice in a week.

**The quiz writes through the shared endpoint.** `quiz_passed` is a field on the
progress row, so an answer rides the same `/api/video-progress/` call the
heartbeat uses. A second write of our own would be exactly the divergence RULE-3
exists to prevent, and it would be invisible: the member and their leader would
each read a different truth and both would look correct.

**Content may link out; the page may not.** RULE-1 governs this product's own
navigation. A link inside a lesson's notes is content somebody wrote, and it
opens in its own tab so a learner does not lose their place.

### Two things caught while building

**A script comment is served to the reader.** The RULE-1 guard failed because a
`<script>` comment explaining where the write goes named the other product.
Django comments are not rendered; script comments are. Reworded to "the shared
engine".

**The contract's fixture had no lesson in it.** Every lesson row was a bare
video, so the catalogue rendered a lesson page with none of the lesson on it and
called the screen covered. The first lesson now carries notes, a summary, a quiz
and a reflection prompt, and lesson 2 stays bare so both states are drawn.

## SPR-M.30 — The bell  `DONE`

REQ-M.33, and built now rather than earlier on purpose. Before SPR-M.28 the only
events in this product were joining and being certified, and a bell for two
lifetime events is furniture. Now a leader writes feedback, returns work and
approves it, so there is finally something worth ringing about.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.30.1 | `Notification`, ours, and a `notify()` that every event goes through | REQ-M.33, M.127 | DONE |
| F-M.30.2 | The bell in the header, with a count, for every signed-in role | REQ-M.33 | DONE |
| F-M.30.3 | The list, and reading one takes you to the thing itself | REQ-M.33 | DONE |
| F-M.30.4 | The events that exist today, wired at their source | REQ-M.33 | DONE |
| F-M.30.5 | Nothing is discoverable only through a bell | REQ-M.128 | DONE |

### What building it turned up  `DONE 2026-09-13`

**A bell tells people about their own actions unless you stop it.** The obvious
implementation notifies whoever the row belongs to, which is right for the
member and wrong for the leader answering their own queue: a leader who writes
feedback would have been told that feedback was written. `notify()` takes an
`actor` and refuses when it matches the recipient, in one place rather than at
each of the five call sites.

**RULE-1 has a blind spot and this is it.** The guard reads templates, and a
notification is not a template — nothing else in this product would ever look
at its `url`. A notification that navigated to `/courses/` would have walked a
member out of the walls from the one place nobody thinks to check. `notify()`
refuses a url outside `/matazim/` and logs it, and the test was verified by
removing the check and watching it fail.

**Marking read on open, not per row.** A bell whose count only clears when you
click each line is a bell people stop opening. Nothing is lost by it, because
REQ-M.128 means everything there is also on the screen it belongs to — but the
list still shows which were new when it opened, or it would give the reader no
way to tell.

### Three decisions

**A notification is a pointer, not a record.** The truth is the submission and
the feedback; this only says where to look. That is what makes it safe to
delete one, expire them, or lose the lot, and it is the difference between a
bell and a second inbox nobody maintains.

**מט״צים's bell is מט״צים's.** The shared engine has a `Notification` table and
we do not write to it. Not a RULE-3 question, because notifications are not
learning, but a separation one: that table feeds the other product's bell in
the other product's chrome, and a מט״צים event landing there puts this product
inside theirs — the mirror of what RULE-1 forbids. The cost is real and is
named rather than hidden: somebody using both products has two bells. For a
ninth-grader in this programme that is close to theoretical.

**Nothing is discoverable only through the bell.** Every event that raises one
also shows on the screen it belongs to. A bell is dismissed by accident
constantly, and a product where that loses information is a broken product. This
one gets a test, because it is the kind of rule that decays the first time
somebody adds an event in a hurry.

## SPR-M.31 — ימי שיא, and what is coming  `DONE`

REQ-M.27, REQ-M.129, REQ-M.130. The third of the placeholder pages to become
real, and the one that gives the bell the event type it is missing.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.31.1 | `Event`, owned by a program manager, aimed at an audience | REQ-M.27, §4.4 | DONE |
| F-M.31.2 | נעמי writes one, and can take it down | REQ-M.27 | DONE |
| F-M.31.3 | ימי שיא becomes a real public page that names nobody | REQ-M.129 | DONE |
| F-M.31.4 | What is close, on המסלול שלי, and the year on its own page | REQ-M.130 | DONE |
| F-M.31.5 | Announcing one rings the bell, for the people it is for | REQ-M.33 | DONE |

### Both load-bearing rules were verified by breaking them  `DONE 2026-09-13`

The two rules this sprint rests on are the two a tired afternoon would simplify
away, so each was tested by writing the simplification and watching it fail.

**Aimed, not broadcast.** Dropping the audience filter from `visible_events` —
the obvious "just show the institution's events" — put a day for one school's
ninth-graders on every member's screen. The test named it: *somebody was shown a
day they are not invited to*.

**Private unless ticked.** Replacing `public_events()` with a plain query on the
public page published the programme's internal diary to strangers. The test:
*the programme's own diary was published*.

A third rule got a test without needing a demonstration: a cancelled day leaves
the public page, because nobody should travel to something that is not
happening.

### One half deliberately not built

REQ-M.34 stays WIP. Announcing an event rings the bell; reminding somebody it is
tomorrow needs something running on a timer, and this product has exactly one
rule about unattended jobs (REQ-M.87: the machine proposes, a person decides).
That needs a decision from Avi about what may run without a person, so it is
named rather than marked done on the strength of its easy half.

### Decisions

**An event is aimed, not broadcast.** For everybody in the programme, or for
named leaders, or for named classes. A day for one school's ninth-graders
appearing on every member's screen as though they were invited is worse than
not telling them: it is an invitation that turns out not to be one.

**The public page names nobody and shows only what is marked for it.** A public
page about a programme for fourteen-year-olds is a public statement of when and
where children gather. Date, title, place, and a school at most (REQ-M.30a), and
only for events נעמי ticks as public — the default is that the programme's own
diary is the programme's own business.

**What is close goes where people already are.** המסלול שלי carries the next
thing; the whole year gets its own page for when somebody wants it. A calendar
you have to remember to visit tells nobody anything.

### One half deliberately not built

REQ-M.34 says "deadlines", and the reminder half of that is harder than it
looks. "A deadline is approaching" is a thing nobody does — it needs something
running on a timer, and this product has exactly one rule about unattended jobs
(REQ-M.87: the machine proposes, a person decides, and nothing deletes a
member's data unattended). Announcing an event rings the bell today. Reminding
somebody that it is tomorrow needs a scheduler and a decision from Avi about
what may run without a person, so REQ-M.34 stays WIP with that named rather
than marked done on the strength of its easy half.

## SPR-M.32 — קהילת מט״צים  `DONE 2026-09-14`

**Goal:** the last of the three SPR-M.1 placeholders becomes real. A feed inside
the walls carrying three kinds of row, and a public page that carries none.

**Specified in spec §4.12.** Read that first: every choice in this sprint is a
restriction, and the restrictions are the point.

**Built under `docs/building_an_app.md` Rule 6.** This is the first מט״צים
module with a DRF API. The rest of the app predates the rule and has none, which
is a recorded gap and not something this sprint retrofits.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.32.1 | `Post` model, owned by an institution, taken down rather than deleted | REQ-M.26, REQ-M.131, §4.4 | DONE |
| F-M.32.2 | `visible_posts(user)` in `access.py`, scope as a property of the queryset | REQ-M.26, §4.4 | DONE |
| F-M.32.3 | The feed screen: read, write, and the honest empty room | REQ-M.26, REQ-M.102 | DONE |
| F-M.32.4 | Moderation on the way in, take-down with a reason by the program manager | REQ-M.131, §2.1 | DONE |
| F-M.32.5 | Sharing an approved submission, and taking it back | REQ-M.132, REQ-M.30a | DONE |
| F-M.32.6 | The public page, which shows no rows | REQ-M.133, §4.10 | DONE |
| F-M.32.7 | DRF CRUD over the module, on the same queryset the screens use | REQ-M.134, Rule 6 | DONE |

### Out of scope, deliberately

**Comments.** Named in §4.12 as a real cost rather than an oversight. A feed
nobody can reply to is a noticeboard. Comments double the moderation surface and
multiply the places a child's name can be typed by somebody other than its
owner, and this version exists to find out whether anybody posts at all.

**A network-wide feed.** §4.4 holds. It becomes possible the day somebody decides
who moderates across institutions, and that person does not exist.

**A public gallery of work.** REQ-M.30a's public half stays WIP. An internal feed
and a consented public gallery are different products.

### What the build found

**One URL, two screens, rather than two URLs.** The menu has one קהילת מט״צים
entry and it is in every role's nav and in the footer. Serving the feed at a
second address would have meant either a dead entry for candidates and visitors
or a second thing for a member to learn. `institution_of(user)` decides, which
is also the function that decides whether a write is possible at all, so the
page somebody gets and the thing they can do on it cannot disagree.

**`institution_of` did not exist and four roles needed it.** A program manager
is their own institution, a leader belongs to theirs, a member to their
leader's, and a candidate to none. Four routes to one answer is exactly the
shape that produced the two `is_member` calculations in SPR-M.24, so it was
written once before any screen needed it twice.

**Two gaps the screenshots found, not the tests.**

A take-down could not be undone. Every test passed: hiding worked, the reason
reached the writer, the wrong roles were refused. `docs/building_an_app.md` asks
whether somebody can fix a mistake without going to /admin/, and the answer was
no, on the one action in this product aimed at a fourteen-year-old's own words.
`show_post` and the API's `show` action, with tests, and the way back is no
wider a door than the way out.

And the moderator's reason box sat open on every card, so a feed of three posts
read as a page of three forms. Behind a `<details>` summary now. Both of these
are the argument for looking at the thing as well as running the suite.

### Rules verified by writing the defect

**Tenancy.** Replacing `visible_posts`'s filter with `Post.objects.all()`:
*another institution's words were readable*.

**The take-down keeps the row.** Making `hide_post` call `delete()`: *the row
was destroyed instead of marked*. The test was rewritten first, because the
deleted row made it fail on a `DoesNotExist` traceback rather than on the
sentence that says what broke.

**The public page carries nothing.** Rendering the feed on it: *a minor's post
was published*.

**The API cannot reach further than the screen.** Giving the viewset its own
`Post.objects` queryset: *the API reached another institution's feed*. This is
the whole reason REQ-M.134 says the API reads `access`.

### Decisions

**Scoped to the institution.** §4.4 with no exception. A post is a
fourteen-year-old's words with their name on them. A network-wide feed becomes
possible the day somebody decides who moderates across institutions.

**Moderated on the way in, taken down by a person.** The moderation call fails
open and is therefore a filter, not a guarantee. What actually holds is the
take-down, that it carries a reason, that the reason reaches the writer, and
that it can be reversed.

**Nothing here is public.** The public page describes the community and shows no
rows. An internal feed and a consented public gallery are different products.

**No comments, and it is a real cost.** Written into §4.12 rather than left out
quietly. A feed nobody can reply to is a noticeboard. This version exists to
find out whether anybody posts at all.

### The methodology gaps this sprint did not close

`docs/building_an_app.md` Rule 4 asks every app for a dashboard and a data-model
document separate from the spec. מט״צים has neither: the data model is §4 of the
spec, which is the thing Rule 4 says not to do. Rule 6 asks every app for a DRF
API, and only this module has one. Both are recorded here rather than quietly
fixed, because retrofitting seventeen models is its own piece of work and
Avi's to schedule.

## SPR-M.33 — Four things Avi found by using it  `DONE 2026-09-14`

**Goal:** four corrections from him signing in and out of the live site. Not a
feature sprint. Spec §5.6a.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.33.1 | The guardian-consent gate behind a flag, off, with everything behind it intact | REQ-M.135, REQ-M.84 | DONE |
| F-M.33.2 | The signed-in person's name in the header | REQ-M.136 | DONE |
| F-M.33.3 | Granting the program-manager role approves a pending leader row | REQ-M.137, REQ-M.93, REQ-M.114 | DONE |
| F-M.33.4 | The prototype notice only after signing in, and only once | REQ-M.138, REQ-M.39 | DONE |

### What each one cost beyond the obvious change

**The consent flag was the easy half.** Off is trivial. What is easy to get
wrong over the following months is deleting the machinery behind a switch nobody
is watching, and finding out on the day it goes back on that a safeguard for
fourteen-year-olds has rotted. So the five SPR-M.10 tests that describe the gate
now ask for it explicitly by name (`gate_on`), and a new pair holds both halves:
the gate is off and nobody is stopped, and the recording, the form and the
switch all still work.

**The role grant was hiding a worse bug than the one reported.** Avi asked not
to wait for an approval. The actual state was that `leader_of()` refuses an
unapproved row, so somebody made a program manager while their leader row was
pending held the highest role in the product *and could not reach their own
students*, while being shown the screen that says they are waiting on a decision
the granter had just made. Fixed in one function used by both the screen and the
bootstrap command, since the command is how the first program manager is made
and she is the likeliest of all of them to already be a pending leader.

**The notice change deleted code, which is the point.** Once a stranger is never
shown the notice, nobody can accept it while signed out, so the session flag had
no writer and the acceptance-carried-across-registration path could never fire.
Leaving them would have meant two functions and a session key that look live and
are not. Three SPR-M.2 tests were rewritten rather than deleted, because the
requirement changed and the tests should say what it changed to.

### Rules verified by writing the defect

**The grant approves.** Making `grant_program_manager` set the flag and stop:
*a program manager was left waiting for approval*.

**Strangers are not nagged.** Restoring the anonymous branch of
`welcome_is_pending`: *a signed-out visitor was nagged on matazim:home*.

### Still open from this list

Avi's feedback arrived as five numbered items and the fifth came through empty.
Four are done. The fifth is unknown and is not guessed at here.

## SPR-M.34 — The methodology retrofit  `DONE 2026-09-14`

**Goal:** Avi stopped feature work. "I need us to pause and stick to the
principles there. I.e. have a model document and have DRF and CRUD for all app
models." Spec §5.6b, and `docs/matazim/data_model.md`.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.34.1 | `docs/matazim/data_model.md`, separate from the spec | REQ-M.140, Rule 4 | DONE |
| F-M.34.2 | Eighteen `visible_*` functions in `access.py`, one per model | REQ-M.139, §4.4 | DONE |
| F-M.34.3 | Serializers for every model, ownership fields read-only | REQ-M.139 | DONE |
| F-M.34.4 | Eighteen viewsets on `access.py` querysets, registered from `ROUTES` | REQ-M.139, Rule 6 | DONE |
| F-M.34.5 | The refusals, each naming the requirement it protects | REQ-M.21, M.53, M.78, M.87, M.112, M.123, M.124 | DONE |
| F-M.34.6 | A dashboard for this app | REQ-M.141, Rule 4 | DONE (F-M.36.5) |

### The test that found things

`test_no_endpoint_reaches_another_institution` builds two complete
institutions, plants a word in every free-text field of each, and then asks all
eighteen endpoints for everything as three different readers from inside the
first. It is a sweep rather than eighteen hand-written cases on purpose: a
hand-written suite covers the endpoints somebody remembered, and the endpoint
that leaks is the one they did not.

It found one on the first run, in code written an hour earlier. `visible_
retention_runs` returned every institution's deletion history to any program
manager, because holding the role read as enough. "Manager X deleted N rows at
time T" is an operational record about somebody else's programme, and the fact
that it names no teenager does not make it ours to read. Scoped by `ran_by`.

It also found that creating a leader through the API crashed on a NOT NULL
constraint rather than answering, because the serializer had no writable way to
name the account. That is a 500 where a refusal belongs, and it is now the same
rule `staff_admins` already had from the other side: a typo must never conjure a
record holding a role.

`test_every_model_has_an_endpoint` is the sweep's other half. A sweep only
covers what is registered, so something has to fail when a model is added and
its route is not.

### The one deliberate exception, written down rather than hidden

The entrance-test bank is shared across institutions: generated geometry, the
same cube for everybody, seeded by a management command. `test_the_bank_is_
shared_on_purpose` asserts that rather than the sweep quietly skipping it, and
names the cost: a program manager retiring a target retires it everywhere. With
one programme that is correct. The day there are two, that test is what has to
change, and it will be looked at because it says so out loud.

### Rules verified by writing the defect

Dropping the tenancy filter from `visible_submissions` produced *another
institution's rows came back from: ['submissions', 'feedback']*, which is the
sweep catching a second endpoint the change was not even aimed at. Putting the
retention leak back produced *['retention-runs']*. Removing a model's route
produced *models with no REST endpoint: ['RequestMessage']*.

### A mistake worth recording

`git checkout matazim/api.py` to undo a deliberately-introduced test defect
reverted the file to its last commit, discarding an afternoon of uncommitted
work on it. Restoring a file under test needs a copy taken first, not a git
command that cannot tell the perturbation from the work.

### Still open

REQ-M.141, the dashboard, is Rule 4's third item and is not built. Recorded as
TODO rather than quietly dropped.

## SPR-M.35 — פרקטיקום, the teaching itself  `DONE 2026-09-14`

**Goal:** REQ-M.32, the stage the whole programme exists to produce and the last
one with no model behind it. Before this a leader could read a roster, approve
work and sign a certificate without ever seeing what that teenager had taught.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.35.1 | `TeachingSession`, counts and never names | REQ-M.32, REQ-M.29 | DONE |
| F-M.35.2 | הפרקטיקום שלי: log a session, see the year | REQ-M.32 | DONE |
| F-M.35.3 | The totals on המסלול שלי | REQ-M.32 | DONE |
| F-M.35.4 | The sessions on the leader's page for that student | REQ-M.23, REQ-M.32 | DONE |
| F-M.35.5 | `visible_sessions` and a DRF viewset | REQ-M.139, Rule 6 | DONE |

### The constraint that shaped it

REQ-M.29 says nothing here creates, stores or infers a record about one of the
children a מט״צ teaches. This is the first model in the app where somebody
would reasonably expect otherwise, because it is literally about a class of
ten-year-olds. So `learners` is an integer, there is no field beside it a name
could go into, and the only relation on the whole model is to the מט״צ who ran
it. A test asserts all three, and it fails on a `pupils` text field being added.

The honest limit: `place`, `went_well` and `was_hard` are prose, and no schema
can stop a fourteen-year-old typing a name into prose. The form says so twice,
the same approach §4.11 takes with the request box, and the residual risk is
recorded rather than pretended away.

### Two decisions worth stating

**Declared, not verified.** Nobody counter-signs a session and no attendance is
taken, because verification would mean a record about the children. Their leader
reads it and talks to them about it, which is the mechanism this programme
actually runs on.

**Not added to the certification gate.** REQ-M.78's two automatic conditions are
unchanged. Adding a third would refuse every certification currently in flight,
and that is Avi's call rather than a side effect of building a model. The
practicum shows on the leader's page beside the eligibility panel, which is
where the conversation would happen anyway.

### A naming collision caught before it shipped

The screen was called ההדרכות שלי until it was read next to the nav, where
ההדרכות is this site's word for courses (the standing brand rule: הדרכות,
never קורסים). Two menu items one word apart meaning different things is the
kind of thing that reads fine to whoever wrote it. Now הפרקטיקום שלי.

### Rules verified by writing the defect

Dropping tenancy from `visible_sessions` showed one leader another's students.
Adding a `pupils` text field produced *a session records a child: {'pupils'}*.
Counting cancelled sessions in the totals produced *assert 3 == 2*.

## SPR-M.36 — Reminders, and how long a request lives  `DONE 2026-09-14`

**Goal:** the two decisions that had been sitting with Avi. He said "continue
with all of these", so both were taken, and the reasoning is written down rather
than left to be re-argued.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.36.1 | `matazim/reminders.py`, once per event, aimed like the event | REQ-M.34, REQ-M.27 | DONE |
| F-M.36.2 | `matazim_remind`, rehearsable, and a token endpoint | REQ-M.34 | DONE |
| F-M.36.3 | A daily GitHub Action firing it | REQ-M.34 | DONE |
| F-M.36.4 | `REQUEST_DAYS`, and the purge on the retention screen | REQ-M.113, REQ-M.86 | DONE |
| F-M.36.5 | A generated dashboard, guarded against going stale | REQ-M.141, Rule 4 | DONE |

### The decision about unattended jobs

REQ-M.87 reads "the machine proposes, a person decides", and it looked like it
forbade this. Reading it closely is the whole answer: it was written about
**deletion**, because deletion is the one action in this product where a bug is
irreversible. A purge that runs wrong at 04:00 has destroyed a teenager's work
by the time anybody reads the log.

A reminder is the opposite shape. It creates nothing a person did not already
decide, destroys nothing, and its worst failure is a duplicate bell. So
reminders run on a timer and purges still do not, and those are two different
shapes rather than one rule applied inconsistently.

`Event.reminded_at` is the guard, and it is a stamp on the row rather than a
window calculation on purpose: a job that runs twice, or a deploy that shifts
the schedule, must not ring the same bell again. A member told twice about one
day stops reading the bell, and the bell is how they hear about everything else.
The stamp is written *after* the sending, so a crash halfway leaves the event
unstamped and the next run finishes it. The cost is a possible duplicate for
those already told, which is the right way round.

### The number on a request row

730 days, from when a request is **closed** rather than from when it was filed.
An unanswered question is not stale data: a request nobody decided on, left for
three years, is a reproach rather than something to tidy away. Two years because
the log is also the record of why this product is shaped the way it is, and
somebody asking "why does the roster work like that" eighteen months later
should find the answer rather than a gap.

Approved on the same screen and by the same person as every other deletion here,
because a second deletion mechanism somewhere else is a second thing to forget.

### The dashboard is generated

A dashboard somebody maintains by hand is a third copy of a truth that already
lives in two places, and the copy nobody is looking at is the one that goes
wrong. `manage.py matazim_dashboard` renders it from the spec and the backlog,
and a smoke test regenerates and compares so drift fails the suite.

### Rules verified by writing the defect

Removing the `reminded_at` stamp produced *somebody was told the same thing
twice*. Replacing the audience query with every student produced *somebody was
reminded about a day they are not invited to*.

## SPR-M.37 — The leftovers, and what the review found  `DONE 2026-09-14`

**Goal:** Avi, 2026-09-14: "make a sprint of the leftovers. And are you sure
there's no big features? Go over the spec, I'm not sure that we're done."

So this is two things: the last three open requirements, and a read of the spec
against Litala's brief rather than against its own status column. The second
part found more than the first.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.37.1 | ההדרכות carries state, and stops contradicting המסלול שלי | REQ-M.12b, REQ-M.59, RULE-3 | DONE |
| F-M.37.2 | REQ-M.11's amended rule, tested on both halves | REQ-M.11 | DONE |
| F-M.37.3 | REQ-M.5b closed by REQ-M.101, and one rule held both ways | REQ-M.5b, REQ-M.101 | DONE |
| F-M.37.4 | Two dead placeholder views removed | REQ-M.60 | DONE |

### The defect that was hiding in the leftovers

ההדרכות told a signed-in member that nothing past the entrance test was
open. REQ-M.76 settled months ago that the required track is `scratch` and
`scratch-advanced`, and המסלול שלי showed the same person those two courses
with their progress. One member, two screens, two different answers about what
they were meant to be doing.

It survived because each screen was internally consistent and each had passing
tests. Only reading them side by side as one person found it, which is the class
of defect a screen-by-screen catalogue cannot see, however many screens it has.
The guard asserts the two screens **agree**, rather than asserting either one's
content, because the failure was never in one of them.

### Three duplications the same read turned up

`_eligibility_without_a_student` lived in `path_views` and was about to be
copied into `views`. It is now `certification.eligibility_for_user`, called by
both.

`_LooseMember` in `path_views` and `_JustAUser` in `views` were the same
four-line class under two names, which is the beginning of two behaviours. Now
`progress.JustAUser`.

`views.community` and `views.events` still existed, unreachable, with docstrings
asserting "no `Post` model yet" and "no `Event` model yet" after both had been
built. Removed.

### One rule, held in the direction that was wrong

המסלול שלי argues that a button leading to "this opens when you join
somebody" is a button that teaches people not to press, and gates the יוצרים
panel on having a leader. The פרקטיקום panel added in SPR-M.35 did the
opposite. The test was written assuming the product was wrong; the product was
right and the new panel was the thing breaking the rule.

And in the other direction: העבודות שלי bounced a member with no leader to
המסלול שלי with no word about why, which reads as a broken link. The copy
explaining it was already on the page, below the redirect that stopped anybody
reaching it.

### What the review found that is NOT built, and is Avi's to decide

Read against `brief-litala.md` rather than against the status column.

**Litala asked for צפייה בכל תלמידי בית הספר.** A leader sees their own
students and nobody else's. Two teachers at one school cannot see each other's.
That phrase appears in the brief and **nowhere in the spec**: it was never
accepted and never refused, it simply never got written down. It is a privacy
question as much as a feature one.

**Q8, פתיחת תכנים ומשימות by programme staff**, is still undecided and is
the largest unbuilt capability in her brief. Today staff open no content inside
מט״צים; babook's studio does it, and nothing here surfaces that.

**Two HELD requirements are now unblocked.** REQ-M.5f (public counters) was held
"until something computes it" — students, leaders, schools, events and now
practicum hours are all countable today. REQ-M.5e and REQ-M.30a's public half
(the showcase) were held until "real projects and real consent exist" — approved
submissions exist, and members already consent to share work into the community
feed, so the machinery is built and only the decision is missing.

Those three are the honest answer to "are we done": the member-facing product
is, the recruitment-facing public page is not, and one line of the client brief
was never decided either way.

## SPR-M.38 — The public front, held since SPR-M.1  `DONE 2026-09-14`

**Goal:** the two requirements that have been HELD longer than any others, and
correctly. Litala's prototype had a stats band of invented numbers and a
showcase of invented projects; Avi cut both on sight in SPR-M.1 and they have
waited for something real ever since.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.38.1 | `matazim/public.py`: figures counted, zeros dropped | REQ-M.5f | DONE |
| F-M.38.2 | Two yeses on a `Submission`, either revocable | REQ-M.5e, REQ-M.30a | DONE |
| F-M.38.3 | The maker's offer, on their own work and nobody else's | REQ-M.30a | DONE |
| F-M.38.4 | The programme's approval, program manager only | REQ-M.5e, §4.4a | DONE |
| F-M.38.5 | The band and the gallery on דף הבית | REQ-M.5e, REQ-M.5f | DONE |

### Why this file is almost all negative tests

This is the only code in מט״צים whose output is readable by anybody on the
internet, and it is about fourteen-year-olds. So the interesting cases are not
"does the work appear" but every way a thing could reach that page without
having earned it: one yes instead of two, a consent withdrawn, a leader
consenting for a member, work that was never approved, a second school that
starts to identify somebody, a private יום שיא inflating a public count.

### The decision that mattered most

**Sharing to the community is not consent to publish.** §4.12 already said an
internal feed and a public gallery are different products, and the tempting
shortcut here was to treat a `Post` of kind `work` as the member's opt-in. It
is not. A fourteen-year-old putting something in front of the people in their
programme has not agreed to put it in front of the internet, and reusing one
consent as the other would have been the worst misreading available in this
codebase. Two separate fields, and a test that creates the community share and
asserts the work stays off the public page.

**Withdrawing consent clears the staff yes too.** Otherwise a member who
withdraws and later changes their mind is republished the instant they
re-offer, on a decision somebody made about a different moment.

**No photograph.** The card is a title, a description and a school. A minor's
file lives outside `MEDIA_ROOT` behind a view that asks who is looking
(REQ-M.122), and publishing a picture of a child's project is a further
decision nobody has taken. Recorded here so the next person to ask "why is
there no image" finds the answer rather than adding one.

**A zero is not a figure.** "0 בתי ספר" is a true sentence that makes a claim a
counter is not for, so empty figures are dropped and an empty programme gets no
band at all, which is how the page has read for thirty-seven sprints.

### The test that was missing, found by trying to break the others

Removing the consent filter from `published_work` broke no test. Every existing
one went through the views, and the views were the only thing holding the rule:
a row published with no consent behind it can only arrive from a migration, the
admin, or a future view written by somebody who did not read this file, and
nothing would have caught it. `test_a_row_published_without_consent_still_never_
shows` builds that state directly. Fifth occurrence of this project's recurring
failure mode: **defects live in states no fixture creates.**

### A mistake repeated

`git checkout templates/matazim/home.html`, to undo a deliberately introduced
defect, reverted the whole of this sprint's work on that file. The same mistake
as SPR-M.34, two sprints ago, and the lesson was written down there and not
learned. Copy the file first; never use a git command that cannot tell a
perturbation from the work.

### The spec after this sprint

149 DONE, 1 HELD, 1 DROPPED, nothing WIP and nothing TODO. The one hold is
REQ-M.12a, superseded by REQ-M.76 and held on purpose.

What is still not built is not in the spec at all, and is recorded in SPR-M.37:
Litala's צפייה בכל תלמידי בית הספר, which was never accepted or refused, and
Q8's authoring surface, which is undecided.

## SPR-M.39 — The review's first four  `DONE 2026-09-14`

**Goal:** Avi asked for a review of everything built so far, then said "start
what you think first." These are the four I put first, in the order I put
them. The fifth and largest, an `Institution` row, is a data-model change and
waits for him: `data_model.md` §6 carries the proposal.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.39.1 | `matazim_handover`: everything one manager owns moves to another, atomically | REQ-M.143, §4.4, §4.8 | DONE |
| F-M.39.2 | The bell reaches the inbox for the things worth leaving the site for | REQ-M.142, REQ-M.33 | DONE |
| F-M.39.3 | The public band says פרקטיקום, not הדרכה | REQ-M.5f | DONE |
| F-M.39.4 | `school_name` normalised at the one door every write goes through | REQ-M.5f, §4.8 | DONE |
| F-M.39.5 | An `Institution` row | proposed, `data_model.md` §6 | HELD for Avi |

### What the handover is, and what it is not

The tenancy root is a person. The day נעמי leaves, her successor signs in to an
empty programme and every leader, event, invite and post she owned is stranded.
The command moves ownership and leaves history alone: a leader approved by
נעמי stays approved by נעמי after she has gone, and her requests stay hers,
because §4.11's log is her voice. The successor is made a program manager
through the same function the screen uses, so a pending leader row on them is
approved rather than left waiting (REQ-M.137). The old manager keeps her role,
because revoking is a separate decision and a handover that quietly demoted
somebody would be two decisions dressed as one.

It is a bandage, and the proposal says so. "Who runs this institution" still
lives in nobody's table.

### The mail is a pointer

Nothing reached a member outside the site until now. The mail carries the same
short line the bell carries and a link, and nothing else: no feedback text, no
work, no names beyond the reader's own. A minor's feedback is read inside the
walls, behind a login, not in an inbox that may be shared with a whole family.
`FEEDBACK` does not mail, because it accompanies a decision that already does,
and a second mail for one moment is how mail stops being opened.

### Three things the tests caught in my own work

**Every mail test was passing without the mail ever reaching the guard.** Django's
test runner swaps `EMAIL_BACKEND` for locmem at start-up, so a plain `send_mail`
in a test bypasses `GuardedEmailBackend`, and the cap test showed five mails
under a cap of three. Not because the guard was broken: nothing had gone
through it. The fixture now puts the guard back outermost. Until it did, six
green tests said nothing about production.

**The cap test passed alone and failed in the suite.** The counter is keyed by
address and date in a process-local cache that outlives a test, and other
tests mail the same address first. `cache.clear()` in the fixture. And a
finding for babook's guard, not fixed here: that cache is `LocMemCache` by
default, so in production the cap is per gunicorn worker and resets on every
deploy. It is a soft cap.

**A leader could not create their own class through the API.** The serializer
demanded `leader` before the viewset could fill it in, a 400 where the screen
just works. Found by a test written for something else. `leader` is optional
on the way in now, and the viewset still refuses anybody else's.

### Rules verified by writing the defect

Dropping `Post` from the handover's table list: the inheritance test named the
missing key. Removing the normalisation from `StudyClass.save()`: *'  עתיד
רמלה ' == 'עתיד רמלה'*. Both restored from copies and checked byte-for-byte
against them, which is the habit two `git checkout` mistakes should have
taught sooner.

### Not mine, but in the way

The shared smoke file now carries tests for `/memz/`, a third app another chat
is building, and those fail in my tree because the app is not in it. With the
ustrip template comments that is two products whose work turns this product's
gate red. Item 17 of the review, now biting twice.

## SPR-M.40 — The tenancy root becomes an institution  `DONE 2026-09-14`

**Goal:** Avi, on the review's recommendation to build the `Institution` row
now rather than leave it as a handover bandage: "Go." REQ-M.144.
`docs/matazim/data_model.md` §6 has the full design write-up, written as a
proposal and updated in place once it shipped.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.40.1 | `Institution` model: `name`, `managers` (m:n `User`) | REQ-M.144 | DONE |
| F-M.40.2 | Four migrations against real data: add nullable, backfill, drop the old fields, require | REQ-M.144 | DONE |
| F-M.40.3 | `access.py`, the views, the API and the admin all read `Institution.managers` | REQ-M.144, §4.4 | DONE |
| F-M.40.4 | `handover.hand_over` rewritten: add/remove a manager, not move rows | REQ-M.143 | DONE |
| F-M.40.5 | An `Institution` viewset (read + rename only) | REQ-M.139, REQ-M.144 | DONE |
| F-M.40.6 | Every test fixture that built a manager or a leader, fixed | — | DONE |

### The migration, in four steps, against a database with real rows

`0031` adds the table and four *nullable* `institution` FKs. `0032` is a data
migration: create the one institution production already implies (from
whoever held the old `is_program_manager` flag) and file every existing
`Leader`, `Event`, `LeaderInvite` and `Post` into it. `0033` drops the old
flag and the four `program_manager` user FKs, now that nothing reads them.
`0034` makes the four `institution` FKs required — written by hand rather than
by `makemigrations`, which stops to ask for a one-off default that `0032`
already made unnecessary, and there was nothing left to default once every row
was filled.

Four steps rather than one because the FK could not go straight from "does not
exist" to "required" without a moment in between where the data has to already
be right. Verified before writing `0034` by hand: zero rows with a null
`institution` on all four tables.

### What it cost, once the schema actually enforced the model

About thirty call sites across `access.py`, the views, the API and the admin —
mechanical, and done first. The real cost showed up afterward, in roughly
twenty test files, once `Leader.institution` went from optional to required
and every fixture that had been quietly relying on the old field being
nullable turned into a hard failure instead of a silent gap. That is exactly
the trade a required column is for, and three different shapes of gap turned
up:

**A leader with no owner at all.** `matazim/joining_views.py`'s `staff_leaders`
screen — "the thing an admin exists to do" per its own docstring — never set
`program_manager` when it created a `Leader`, and never set `approved_at`
either, which predates candidates (REQ-M.93, SPR-M.14) and was never updated.
A leader "assigned" from that screen belonged to nobody's institution and
stayed a candidate forever: `leader_of()` refuses an unapproved row, so the
admin's own action produced someone who could never sign in as a leader. Both
were real bugs, silently tolerated by two nullable fields, now fixed together
and held by a test.

**Two managers who ended up in two different worlds.** Several test files
build a manager and a leader independently and expect them to share one
institution (`_make_manager(boss); _one_world()` and similar). `_make_manager`
always creates a *new* institution; only `_one_world()`/`institution_of()`
finding an *existing* one and joining it is order-independent. Fixed by
replacing the pattern with `_one_world().managers.add(user)` everywhere it
appeared, in `test_spr_m_6.py`, `test_spr_m_7.py`, `test_spr_m_8.py`,
`test_spr_m_9.py`, `test_spr_m_10.py` and `test_spr_m_18.py`.

**A mechanical sweep that typed a `User` where an `Institution` was wanted.**
The regex that rewrote most of the suite turned `program_manager=manager or
make_manager()` into `institution=_inst(manager) or make_manager()` — the
fallback branch still returned a `User`, which `ValueError`s the moment
`manager` is omitted. Found in `test_spr_m_18.py`, `test_spr_m_24.py`,
`test_spr_m_25.py` and `test_spr_m_28.py`, all fixed to `_inst(manager or
make_manager())` — resolve to one person first, then ask what they manage.

### The bug the review's own test caught, in code an hour old

`handover.hand_over`'s first version called
`roles.grant_program_manager(new, by=by)` with no institution named, which
joins whichever institution `Institution.default()` finds — the earliest
created, not necessarily the one being handed over. Every test database
carries a second institution, seeded by `0032`'s backfill, so the successor
ended up managing both, and `institution_of()` — which reads the earliest by
creation date — picked the seeded one over the one that actually owned
נעמי's rows. `visible_posts(successor)` came back empty.
`test_a_successor_inherits_the_whole_institution` (SPR-M.39, still testing the
pre-Institution handover shape at the time) caught it immediately. Fixed by
giving `grant_program_manager` an explicit `institutions=` argument, so a
handover never has to guess.

### A query-count test that found a dropped side effect

`test_spr_m_17.py`'s `make_manager` used to grant the role through
`MemberProfile.objects.update_or_create(..., defaults={"is_program_manager":
True})`, which created the `MemberProfile` row as a side effect. The
mechanical replacement, `_make_manager(user)`, only touches `Institution` —
the profile row is now created lazily on first touch by whatever view reads
it. `test_the_report_does_not_grow_a_query_per_leader` compares a query count
against itself before and after adding six leaders, and the *first* request
was paying three extra queries (SELECT miss, INSERT, re-SELECT) that the
second wasn't. Fixed by having `make_manager` create the profile explicitly,
same as it always implicitly did.

### One test retired, because the state it described is now impossible

`test_an_orphaned_leader_belongs_to_nobody_but_root` built a `Leader` with no
owner at all and checked that only root could see it — a safe fallback for a
real gap in the old nullable FK. `Leader.institution` is required now, so that
state cannot be reached: the gap is closed rather than merely defended
against. Rewritten as `test_a_leader_cannot_be_created_with_no_institution`,
asserting the stronger guarantee directly — the database refuses the row.

### One screen's wording, changed on purpose

כניסת מובילים and the profile page told a waiting candidate the name of the
specific manager they were waiting on. Under the old model there was always
exactly one. `Institution.managers` is deliberately more than one
(REQ-M.144), so naming a single manager is now arbitrary — there may be
several, and picking one to display would be picking one at random. Both
screens now name the institution instead ("צוות X"), which is still an honest
answer to "who am I waiting on." `test_a_waiting_candidate_is_told_they_are_
waiting` updated to match, with the reasoning written into the test rather
than left for someone to rediscover.

### Rules verified by writing the defect

Removing `institutions=theirs` from the handover's grant call reproduced the
bug above exactly. Reverting `grant_program_manager`'s `institutions=`
parameter and re-running the handover test failed on the same assertion it
failed on the first time, confirmed against a saved copy of the file and
restored byte-for-byte rather than by `git checkout` — the mistake recorded
twice already in this backlog, not repeated a third time.

## Also still open

- Retire the old production tables, once ACT-M.2 is answered.
- ~~The entrance-exam gap: REQ-M.17 says a leader reviews the attempt and
  decides, but what shipped passes automatically.~~ **Resolved 2026-09-11, and
  it was not a gap.** REQ-M.17 named a reviewer who cannot exist: REQ-M.36
  requires the test to be passed *before* anyone can join a leader, so at review
  time the candidate has no leader. Carried as a known deviation for four
  sprints when it was a contradiction. The requirement now says what is true and
  what is actually enforced.

## SPR-M.41 — What a full UX review measured  `DONE 2026-09-15`

**Goal:** Avi asked for a full review with attention to UX, graphic design and
clarity. This is what it found. Every screen was walked as every role in a real
browser at phone width and at 1440px, and the numbers below are measured rather
than looked at: effective tap area by probing `elementFromPoint` outward from
each control's centre, contrast against the resolved background rather than an
assumed white, overflow by finding the elements that actually stick out, and
queries per screen through the test client.

38 screens, four roles (visitor, מט״צ, מוביל, מנהלת תוכנית).

### What the measurements cleared

Worth writing down, so nobody spends a sprint fixing what is already right.

| Checked | Result |
|---|---|
| Effective tap area, every interactive control, 38 screens | 0 under 44px |
| Contrast, every text node, against resolved background | 0 below AA |
| Horizontal overflow at 390px | 0 elements, 0 screens |
| RTL progress fills | correct, anchored to the right edge |
| `dir="rtl"` / `lang="he"` | 38 of 38 |
| Exactly one `h1`, no heading-level jumps, no missing `<title>` | 38 of 38 |
| JS errors, failed requests | none |
| Queries per screen | 4 to 39, flat. 120 targets render in 24, so no N+1 |

The one apparent desktop overflow is `.mz-blob-a`, a decorative shape bled off
canvas on purpose, and `scrollWidth === clientWidth`, so nothing scrolls. The
file picker looked like an unstyled native control in a screenshot and is not:
it is the deliberate Hebrew `.mz-file` overlay, and the native English one is
hidden underneath by design.

The 403 page and the empty states are the best writing in the product. "אין לכם
הרשאה לראות אותו, וזה בסדר גמור" tells a person what happened, that they are not
in trouble, and who to ask. They should be the model for anything new.

### The findings

| F-ID | Finding | Traces | Status |
|---|---|---|---|
| F-M.41.1 | Two panels named הפרקטיקום שלי on המסלול שלי, and the first is not the practicum | REQ-M.130 | DONE |
| F-M.41.2 | קורסים in three pieces of live copy, against a recorded decision | assess.py:280 | DONE |
| F-M.41.3 | Prose runs 136 characters per line on nine screens at desktop width | REQ-M.5 | DONE |
| F-M.41.4 | The front door's strongest enabled button belongs to adults | REQ-M.5c, M.36 | DECIDED, NOT BUILT |
| F-M.41.5 | The lamp loses its label on phones | REQ-M.106, M.75 | DONE |
| F-M.41.6 | "not yet" is a bare middle dot, with no word and no text alternative | REQ-M.76 | DONE |
| F-M.41.7 | Three readonly copy fields have no accessible name | REQ-M.139 | DONE |
| F-M.41.8 | The brand tagline sits at 11.5px on every page | | DONE |
| F-M.41.9 | Five to seven identical role-resolution queries per request | | NOT TAKEN |

### F-M.41.1, the one that actually misleads somebody

`my_path.html` line 61 opens a panel headed הפרקטיקום שלי that lists `courses`
with lesson progress bars and a יש תעודה tag. Line 144 opens the real practicum
panel, headed הפרקטיקום שלי. Two identical headings on one screen, and the first
one names the wrong stage of the programme entirely.

A member reading their own path sees "הפרקטיקום שלי 23/34" above their Scratch
progress. 23/34 is lessons. The practicum is the teaching they have not started.
This is the screen whose whole job is telling a fourteen-year-old where they
are, so it is first on the list despite being a one-word fix.

### F-M.41.2, a decision the code records and the copy breaks

`assess.py` line 280 carries it: *"הדרכות", לא "קורסים" (החלטה של אבי,
13.9.26)*. The navigation, the page titles and `courses.html` all honour it.
Three strings do not:

- `content.py:32`, "רוכשים ידע טכנולוגי **בקורסים** מקוונים", on the public home
  page, whose own `detail` two lines later correctly says "מסלול **הדרכות**
  מקוון". One card, both words.
- `content.py:23`, "לומדים טינקרקאד **בקורס** קצר".
- `path_views.py:106`, "בסוף **הקורס** מקבלים תעודה", on the current-mission
  card at the top of המסלול שלי.

### F-M.41.3, the product already owns the fix

`.mz-legal` is `max-width: 720px` and `.mz-hero-text` is `max-width: 46ch`, so
the measure problem was solved twice and never applied to panel prose. The
result, at 1440px: 18 paragraphs across nine screens at 1088px wide, about 136
characters per line, against the 45 to 90 that is comfortable.

The worst affected are about, track, courses and schools, which are the pages a
parent or a principal reads before deciding anything. This is one CSS rule.

### F-M.41.4, the hierarchy points at the wrong person

For a visitor who has not taken the test, the three controls in the hero are:

1. כניסת תלמידים, `mz-btn-primary is-disabled`, pale with a padlock.
2. כניסת מובילים, `mz-btn-secondary`, solid teal. The strongest enabled thing
   on the page, and it is for adults.
3. מבחן הכניסה, `mz-btn-ghost`, an outline. The teenager's only real next step,
   styled as the weakest of the three.

The reasoning in the template is sound and says the test is "one click away".
The click is there; the weight is not. The path forward for the audience this
page exists to recruit is an outlined button plus an 11.5px inline link inside
`.mz-door-why`. Worth Avi's decision rather than a unilateral restyle, because
which door leads is a product question.

### F-M.41.5

`@media (max-width: 640px) { .mz-lamp-text { display: none } }`. On a phone the
lamp is a 52px purple circle with an icon. It carries `title` and `aria-label`,
so assistive tech is fine and a mouse gets a tooltip, but a phone has no hover,
and this is the only entrance to the improvement loop by design. The icon is
carrying a feature on its own.

### F-M.41.6

`my_path.html:101` renders `✓` when a requirement is met and `·` when it is not.
The palette comment in `matazim.css` states the rule this breaks: *status:
always a word plus a colour, never a colour alone*. A middle dot reads as a
bullet, not as "not yet", and neither glyph has a text alternative.

### Not raised as findings

The header is 120px on a phone for a signed-in member, 14% of the viewport, and
sticky. Measured because it looked worse than it is. It is defensible and is
recorded here only so the next reviewer does not re-measure it.

The public band says 13 מט״צים בתוכנית while the staff page says 19 לומדים
בתוכנית. Different labels counting different things (`public.py` counts three
statuses; staff counts every row), so this is correct, and noted only because it
reads like a contradiction until you check.

### F-M.41.4 is decided, and deliberately not built here

Avi, on reading the finding: the site should not put anybody on the spot by
asking which kind of person they are. It should assume a teenager arrived,
because that is who the product is for, and give them one path.

A leader is recognised by **how they arrived**: they come through their own
invite link, and that link already carries the fact that they are a leader, so
nobody has to be asked. The leader entrance stays visible, in the menu, rather
than as a door in the hero. His words: not hidden, seen, but in the menu.

That is a larger change than the rest of this sprint, and it reaches the locked
כניסת תלמידים door too, so it is written down here and left for its own sprint
rather than folded into a list of fixes.

### F-M.41.9 was measured and then declined

The 5 to 7 repeated queries are `is_program_manager`, `leader_of` and
`institution_of` resolving the same person several times per request. The
obvious fix is to memoise on the user instance, which is per-request because
`request.user` is.

Not taken, because the failure it invites is worse than the cost it removes.
`grant_program_manager` changes somebody's role inside a request that then goes
on rendering, and a cached "no" surviving that is a role change that appears not
to have happened. The queries are constant rather than N+1, which the numbers
show plainly: the targets bank renders 120 rows in 24 queries. Buying a handful
of trivial `EXISTS` lookups with a staleness bug in the permission layer is the
wrong trade, and it is recorded here so it is not rediscovered as an easy win.

### The fix that had to be measured twice

`.mz-check-todo` first used `--mz-idle`, which is what "not yet" obviously
wants. Re-running the contrast pass afterwards put it at 2.56:1 on the card:
this sprint would have introduced the product's only contrast failure, on the
screen it was fixing. `--mz-muted` is the measured 4.97:1 grey the rest of the
writing already uses. Re-measuring after a change is what caught it, not review.

### What the numbers say now

Re-walked, all 38 screens, after the changes: zero elements overflowing at
390px, zero tap targets under 44px, zero contrast failures, zero inputs without
an accessible name, and prose over 100 characters a line on no screen at all,
down from nine. Tests: 659 matazim tests plus the 8 written here, all passing,
and each of the new ones was confirmed by reintroducing the defect and watching
it fail.

## SPR-M.42 — One door, and it belongs to the teenager  `DONE 2026-09-15`

**Goal:** F-M.41.4, which SPR-M.41 recorded as decided and left for its own
sprint. Avi: the site should not even state that it is for students or leaders.
Assume a teenager arrived, because that is who this is for. A leader is
recognised by the link they arrived through, and the leader entrance stays
visible in the menu rather than standing in the hero. "It's not so pleasant" to
put somebody on the spot on arrival.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.42.1 | The hero carries one action, and it is the teenager's | REQ-M.5c superseded | DONE |
| F-M.42.2 | The locked door, and the CSS that dressed it, are gone | REQ-M.36 unchanged | DONE |
| F-M.42.3 | The leader door stays in the menu, where it already was | REQ-M.103 | DONE |
| F-M.42.4 | The passed test is marked without a ✓ in the menu | REQ-M.63 | DONE |

### What the page used to ask

Three controls, and the reader had to place themselves among them: a padlocked
כניסת תלמידים in the primary slot, a solid teal כניסת מובילים beside it, and
מבחן הכניסה third as an outline. SPR-M.41 measured the consequence: on a page
written to recruit fourteen-year-olds, the strongest enabled control was the one
for adults, and the teenager's actual next step was the weakest of the three
with its explanation in 11.5px grey underneath.

Now: one primary button. Before the test is passed it *is* the test, because the
test is the way in and a locked door with the key taped underneath it is still a
locked door. After it is passed it becomes להצטרף לתוכנית, with the pass
acknowledged beside it rather than the invitation repeated.

**REQ-M.36 has not moved.** Somebody who has not passed still cannot join, and
that rule lives where it always really lived, in `student_door_is_open()` and
the views that consult it, rather than in a greyed button. What was deleted is
the *drawing* of the gate, not the gate.

**The leader door needed no work at all.** It has been a nav item since
REQ-M.103, which is exactly the shape Avi asked for: seen, but not in front of
your eyes. The only change was removing its second copy from the hero.

### Three earlier tests had to be rewritten, on purpose

`test_two_front_doors_and_the_public_test` (SPR-M.1),
`test_without_a_passed_test_the_student_door_is_shut` (SPR-M.2) and
`test_passing_opens_the_student_door` (SPR-M.3) all asserted the fork. They
failed the moment the hero changed, which is what they were for. Each was
rewritten to assert the new rule rather than deleted, and each carries a note
saying what it used to assert and why that changed, so the history is readable
from the test rather than only from here.

### The ✓ in the menu

Avi, while this was being built: in the menu, מבחן הכניסה looks ugly with the ✓
added, and it ruins the look. A navigation bar is not a checklist. REQ-M.63 asks
that somebody who passed is never invited to take it again, and de-emphasis says
that without a badge: `.mz-nav-done` now goes muted and normal-weight. It stays
in the menu and stays reachable, because hiding it once made the whole test
chain unreachable for precisely the people who had passed.

### Still open from Avi's note

"A student should have an easier flow of user journey. The site should
flawlessly lead him on what he is expected to do in every stage." The front door
is now one such step. The rest of that, every stage saying what the next thing
is, is a pass over המסלול שלי, the הדרכות, יוצרים and the practicum, and it is
not in this sprint.

## SPR-M.43 — The journey says what to do next, at every stage  `DONE 2026-09-16`

**Goal:** Avi: "a student should have an easier flow of user journey. The site
should flawlessly lead him on what he is expected to do in every stage."

So the journey was walked as the member sees it, one signed-in account per
stage: signed up but untested, passed and waiting for a leader, in training,
and certified. On a phone, measuring where the next action actually sits rather
than whether a link exists somewhere on the page.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.43.1 | Waiting on a leader stops replacing learning already open to them | REQ-M.5a, M.65 | DONE |
| F-M.43.2 | A certified מט״צ is pointed at the practicum instead of nowhere | REQ-M.32 | DONE |
| F-M.43.3 | העבודות שלי explains itself before it asks for anything | REQ-M.19 | DONE |
| F-M.43.4 | הפרקטיקום explains itself above the form rather than below it | REQ-M.32 | DONE |

### What the walk measured

| Stage | Actions on the screen | After |
|---|---|---|
| Passed, waiting for a leader | **none at all** | one, above the fold |
| Certified | first one 1527px down | one, 413px down |

### F-M.43.1, the stage with nothing to do

A member who passed the entrance test and asked to join a leader was told
"לחכות לאישור", with no button, and "ברגע שיאשרו, תוכלו להתחיל". The whole
screen had nothing on it to press.

It was also untrue. The הדרכות are open to them at that moment, and the panel
immediately below the card was showing 6/19 in סקראץ' 1 while the card told them
to wait for permission to begin. The programme says so itself, in the copy on
its own front page: "כל מה שתלמדו נשמר ונספר לכם, גם אם למדתם לפני שהצטרפתם".

The ladder in `_next_step` was ordered "the earliest thing still open", and the
bug was counting somebody else's decision as a thing open to them. Waiting is
context, not a task. It moved below the courses, where it is reached only once
the learning is done, and at that point it says so: "סיימתם את ההדרכות".

### F-M.43.2, the end of the road

"אתם מט״צ מוסמך. מכאן מדריכים אחרים." named the next stage of the programme and
went nowhere, on the one screen whose job is pointing at the next thing.
הפרקטיקום already existed. It points there now.

### F-M.43.3 and F-M.43.4, two screens that asked before they explained

העבודות שלי, with nothing submitted, went from a subtitle promising "מה שהגשתם,
ומה שהמוביל/ה כתב/ה עליו" straight into an empty form. It described a list that
was not there and never said what happens after you press הגשה, on the feature
whose entire point (REQ-M.19) is that a person reads your work and writes back.

הפרקטיקום had the words but at the bottom, under the seven fields they were
about, so a first-timer met the form and found out what it was for underneath it.

### A metric that got worse while the screen got better

הפרקטיקום's submit button moved from 1182px down the page to 1385px, because
the explanation now sits above the form. "First action above the fold" is the
wrong question for a form: the form *is* the action, its fields start above the
fold, and the reader needs to know what they are filling in before they fill it.
Recorded because the number is still in the table above and looks like a
regression.

### The measurement that lied, and why

One screen appeared to have its action buried at 1092px. It is covered by the
first-visit welcome overlay, whose own button is the real first action. Nothing
was wrong with it. A number from an automated pass is a place to look, not a
finding, and this one was only settled by opening the screenshot.

### Perturbation can leave the dev server wrong

Verifying these tests by reintroducing each defect writes the defect to disk,
and the shared dev server autoreloads onto it. After restoring the file, the
server was still serving the perturbed code: a screenshot taken minutes later
showed the old "ברגע שיאשרו, תוכלו להתחיל" that no longer existed in source,
which is how it was caught. Rewriting the file to trip autoreload fixed it.

Avi runs several sessions against this one dev server. A perturbation left
running there is not a private mistake, so: after perturbation testing, touch
the file and confirm the server is serving the restored code before trusting
anything you see on it.

## Avi's answers on the open actions  `2026-09-16`

Five of the six ACT items had been waiting on him. He closed four in one go,
and the wording of each answer matters more than a status column, so it is here.

**ACT-M.2, the old production tables: leave them.** "Leave all in production,
even if they are demo users, just leave them as is. I will re-remove them later.
I need them for testing." So the table-drop that has been waiting on this since
SPR-M.13 is not happening, and this is not a deferral to chase later: the rows
are in use. `CLOSED, leave as is`.

**ACT-M.4, curating the target bank: nothing is retired.** "Nothing is hard for
a 14-year-old kid. Leave everything there." The bank ships with all 120 active,
which is what it already did. REQ-M.55's retire mechanism stays built and
unused, which is the right way round: the screen exists for the day somebody
disagrees with this. `CLOSED, retire nothing`.

**ACT-M.5, the drawings: leave them.** "Leave whatever I dropped, leave them
dropped." Read as: no cosmetic regeneration, the old matazim.co.il colours stay.
Recorded as an interpretation rather than a quote because the sentence arrived
through dictation; if it meant something else the correction costs nothing,
since nothing was built either way. `CLOSED, no regeneration`.

**ACT-M.6, נעמי's role: granted.** "Nomi is granted as a program." Done in
production by Avi. `CLOSED`.

**ACT-M.3, the disclaimer: still open, and now asked properly.** He asked what
signing it off meant, which is fair: the item said "confirm the wording" without
ever showing him the wording. It is the blocking modal every new visitor reads:

> **שימו לב: האתר הזה הוא אב טיפוס.** זהו אתר ניסיוני, שאינו אתר רשמי של אינטל
> ואינו מייצג אותה. אין בשימוש באתר או במידע שבו כל התחייבות או מחויבות מצד אף
> גורם.

It names Intel and disclaims representing them, in front of parents and
fourteen-year-olds, which is why it is his sentence and not ours. `OPEN`.

### A note on how these were closed

Four of five answers were "leave it as it is". That is worth recording because
the items read like a backlog of pending work and were mostly a backlog of
pending *permission*, three of them for cosmetic or curation changes nobody had
asked for. The one that was real, ACT-M.6, he had already done.

## SPR-M.44 — The leader's journey says what to do next, too  `DONE 2026-09-16`

**Goal:** SPR-M.43 walked the member's journey. This is the same walk for the
adult, signed in at each stage they pass through: a teacher waiting to be
approved, a leader with people waiting on them, and a leader on an ordinary day
with an empty queue, which is most days.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.44.1 | A waiting teacher is taken to their status, not refused | REQ-M.93, M.99 | DONE |
| F-M.44.2 | The page says what is true today rather than one fixed line | REQ-M.73 | DONE |
| F-M.44.3 | Once there is a group, the group comes before the join link | REQ-M.73 | DONE |

### The ordinary day was the one that was wrong

A leader with a group and nothing pending opened האזור שלי to a first screen
that was the join link and a QR code, with their own people below the fold,
under a subtitle promising "המט״צים שמחכים לאישור" when nobody was waiting.

Recruiting is occasional. Looking in on your group is why you opened the page.
So once there is a group the group goes first, and the link keeps its place for
the leader who has nobody yet and needs it most. Done with `order` in the
stylesheet rather than a second copy of the markup, so the two states cannot
drift apart.

Measured on a phone, for a leader with four students: המט״צים שלי moved from
below the fold to 276px, and the link panel to 812px.

The ordering when something *is* waiting was already right, and was left alone:
work first, then approvals, then the group, then the link.

### A candidate was treated as a stranger

A teacher whose leader row is not yet approved got the same 403 as anybody
else, and that page reads "אם לדעתכם זו טעות, דברו עם המוביל שלכם בבית הספר".
For a fourteen-year-old that is the right sentence. For a teacher waiting on the
programme team it is advice to go and ask themselves, and it says nothing about
the only thing they want to know, which is whether their request has been
answered.

ההרשאה שלי is that screen and already existed, reachable from their menu. Now
landing on the leader area sends them there instead of refusing them. Everyone
else is still refused: the redirect asks `candidate_of`, which is the unapproved
row and not a way in, and there is a test for somebody with no row at all.

### Checked and left alone

The roster and the notices screen have no single primary action, and should not:
every row is the action, and adding a headline button to a list of teenagers
would be inventing a job for the page to do. The manager's cohort report puts
its export at the bottom, which is where it belongs on a page you read first.

### The measurement could not see this sprint's main fix

"First primary action above the fold" did not move for any of these screens,
because the roster link on האזור שלי is styled as secondary and the reorder
changed what is *above* it rather than what it is. The fix was real and the
number was blind to it, which is the second time in two sprints this metric has
needed a human to look at the screenshot. Recorded rather than quietly dropped:
it is a good tripwire and a poor verdict.

## SPR-M.45 — A lesson reaches nobody until somebody presses play  `DONE 2026-09-16`

**Goal:** walk the screens where a מט״צ actually spends their hours. Every
review so far had covered the hubs: the front door, המסלול שלי, the roster, the
staff area. Nobody had opened a lesson and asked anything of it.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.45.1 | The player is built on the first click, not on page load | §4.10 | DONE |
| F-M.45.2 | The page says where the video comes from, before it goes | §4.10 | DONE |

### What opening a lesson used to do

Ten third-party hosts, measured, before anybody pressed anything:

| Host | What it is |
|---|---|
| `assets.mediadelivery.net`, `iframe.mediadelivery.net` | the Bunny player, as scripts |
| `vz-b521cf57-68f.b-cdn.net` | video segments, 24 requests, 1080p, unasked |
| `rum-metrics.bunny.net`, `metrics-bunny.net`, `1785c05b.metrics-bunny.net` | performance telemetry |
| `edgezone-auc…`, `edgezone-ke…`, `edgezone-in…` | latency probes to edge zones worldwide |
| `fonts.bunny.net` | fonts |

Every other screen in מט״צים contacts nobody. That is not luck: SPR-M.21
self-hosted Rubik precisely so a Google Fonts link would not send a
fourteen-year-old's IP address to Google "before they have agreed to anything
and with nothing on screen saying so".

And the privacy page says, in bold:

> אין כאן גוגל אנליטיקס, אין פיקסל של פייסבוק, **ואין שום סקריפט של חברה אחרת.**

and then uses that to explain why the site asks for no cookie consent. On the
lesson screen, which is where a member spends most of their time, that sentence
was not true.

`loading="lazy"` was already on the iframe and did nothing, because the player
sits at the top of the page and is therefore in the viewport.

### What it does now

A still, a play button, and one line: *הווידאו מגיע משרת חיצוני (Bunny). עד
שתלחצו, לא נשלח לשם כלום.* The iframe is created by the click.

Measured after: **0 third-party hosts on load, 12 after the click.** Reaching
Bunny on play is unavoidable, because that is where the video is. The change is
that it now happens because a reader chose it, and the screen said so first
rather than a policy page saying so later.

The whole frame is the button (298×190 on a phone), not a glyph, because a play
control the size of a triangle is the tap-target defect SPR-M.41 swept out.

### What is still not true, and is Avi's sentence

Pressing play still contacts another company, so "אין שום סקריפט של חברה אחרת"
remains wrong for anybody who watches a lesson, which is everybody. The code now
makes the claim true for *reaching* the page and honest at the moment it stops
being true, and that is as far as code can take it. The policy needs a sentence
about the video, and a privacy policy read by minors is not ours to word. Held
with ACT-M.3, the disclaimer, as the second thing waiting on Avi.

### A stale allowlist, found by the guard that caught this

`test_every_class_a_template_uses_actually_exists` failed on `mz-player-idle`,
correctly: it is a state hook with no styling. Adding it to `STATE_ONLY` showed
that `mz-door-locked` was still listed there, three sprints after SPR-M.42
deleted the locked door. Removed. An allowlist that keeps names nothing uses
stops being a list of deliberate exceptions and becomes a list of things nobody
reviewed.

### The method that nearly hid this

The first walk reported two lesson pages as timing out. They were not: they
render in 0.1 seconds, and `networkidle` simply never arrives on a page whose
video player streams continuously. The wrong number pointed at the right screen
for the wrong reason, and only opening the request log turned "these pages are
slow" into "these pages are talking to ten strangers".

## SPR-M.46 — The privacy page says what the product does  `DONE 2026-09-16`

**Goal:** the half of SPR-M.45 that was Avi's. He read the finding and said
"ok", so the paragraph that was not true now says what actually happens.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.46.1 | The page names the video service and the click that gates it | REQ-M.81 | DONE |
| F-M.46.2 | The page names the graphics library too | REQ-M.81 | DONE |
| F-M.46.3 | A test that fails on any future undisclosed third party | §4.10 | DONE |

### What the guard found on its first run

The test written for this sprint does not check "does the page mention Bunny".
It reads every external host out of every מט״צים template and fails on any whose
owner the privacy page does not name. Naming Bunny fixes today; the way this
breaks again is somebody embedding a map or a widget next year.

It failed immediately, on **`cdn.jsdelivr.net`**, which nobody had written down
anywhere. `test_task.html` and `staff_targets.html` both load three.js from it,
and measured on the real screens that is three scripts fetched eagerly, with no
click and no notice. `test_task.html` is מבחן הכניסה, which is the first thing a
fourteen-year-old does here.

So the sprint written to disclose one third party disclosed two, and the second
was found by the tripwire rather than by anybody noticing it.

### What the page says now

Two named items in a list rather than one buried sentence: the video from Bunny,
gated behind the click, and three.js from jsDelivr on the entrance test's 3D
view, which loads as soon as the screen opens. Then the part that matters and
was never said: these are **files loaded into your browser, not information sent
about you**; neither sets a cookie; nothing you told us is passed to them; and
what they do see, like any server a file comes from, is your IP address.

The cookie sentence survives because it was measured rather than assumed: zero
third-party cookies before the click and after sixteen seconds of playback.

### The fix that is not in this sprint

Disclosure is the honest minimum, not the best answer. SPR-M.21 did not disclose
Google Fonts, it **removed** them, and said why: a font link sends a
fourteen-year-old's IP to Google before they have agreed to anything. three.js
from jsDelivr is the same shape and deserves the same answer, which is vendoring
it into `static/matazim/` and pointing the import map at ourselves.

Not done here because it is a bigger change than a sentence: the 3D viewer is
what מבחן הכניסה is, and breaking it breaks the way into the programme. It wants
its own sprint, with the viewer actually exercised in a browser afterwards.

Bunny cannot be removed the same way, because that is where the video is. The
click is the right answer there and it already shipped.

## SPR-M.47 — The newcomer is not greeted as a returning member  `DONE 2026-09-17`

**Goal:** Avi, looking at the site logged out: "מבחן הכניסה פעיל ומזמין גם כשאני
לא מחובר. הכיצד?"

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.47.1 | The login page knows whether it was reached or chosen | REQ-M.5d | DONE |

### The answer to "how come", and the bug behind it

It is deliberate and recorded. REQ-M.5d: מבחן הכניסה is reachable with no
account, because signing up happens *around* the test rather than before it.
`/matazim/test/` and `/matazim/test/lessons/` are open; the lesson itself and the
task require an account.

Walked with no account, which is how the actual defect surfaced:

עמוד המבחן → "מתחילים" → רשימת השיעורים → tap the first lesson →
`/matazim/login/?next=/matazim/test/lesson/1/`, headed התחברות, subtitled
**"שמחים לראות אתכם שוב"**.

They had never been here. The product invites a stranger in on purpose, walks
them through two screens, stops them at a wall, and greets them as somebody
coming back. Nothing on that page said why an account had appeared in their way.

`next` is what tells the two readers apart, and the view had been passing it for
sprints. Somebody who was *sent* here was reaching for something and the page
can now say what and why; somebody who came to log in really is coming back and
keeps the old line.

Reaching for the test says: "כדי לשמור את מה שתעשו במבחן צריך חשבון. זה לוקח
דקה, וזה גם החשבון שתמשיכו איתו בתוכנית."

### Also asked, and answered in the data model rather than here

Avi's second question was what the spec defines for taking הדרכות and following
progress. REQ-M.12b, M.13, M.14, M.74 and M.126, and measured against the real
screens they hold: status word, percentage, and an action matching the state
(להתחיל / להמשיך / צפייה שוב).

The gap is not in those. ההדרכות says *"שאר ההדרכות באתר פתוחות לכם תמיד"* and
shows exactly two, with no route to any other, because `learn_course` refuses
every slug outside the required pair and RULE-1 forbids sending anybody to
babook's catalogue. A promise with no path.

That is what `data_model.md` §7 now proposes a shape for, and it is awaiting
Avi's approval rather than being built. He has already settled its sharpest
question: the courses a leader adds are a **recommendation**, not a requirement,
so REQ-M.76 and `certification.py` do not change at all.

## Finding: the certification path does not close inside מט״צים  `OPEN, 2026-09-17`

Found while scoping Avi's course-selection request, by asking what the two
required הדרכות actually need in order to issue their certificates.

**REQ-M.76 says a מט״צ מוסמך is the entrance test, a `CourseCertificate` for
both `scratch` and `scratch-advanced`, and the leader's approval.** Measured,
here is what those two certificates require and what מט״צים offers.

| What babook's gate requires | What מט״צים provides |
|---|---|
| `requires_project = True`, `project_min_count = 2` Scratch project links, per course | no upload form anywhere in the app |
| ≥ 80% of lessons complete (`cert_min_pct`) | provided: the heartbeat writes `UserVideoProgress` |
| the final-lesson view that runs the gates and issues the certificate | never called: `learn_lesson` has no such path |

`/api/video-progress/`, which is what מט״צים's done button posts to, sets
`progress.completed_at` and nothing else. `matazim/certification.py` only ever
**reads** `CourseCertificate`; nothing in the app issues one.

**So a member who does everything מט״צים offers cannot be certified.** They can
watch all 34 lessons, answer every quiz, write every reflection, and there is
still no route to either certificate, because the two things that issue it, a
project upload and the gate behind the final lesson, exist only on babook's own
lesson page.

### Why this was not visible

Nine `CourseCertificate` rows exist in the dev database against four Scratch
project submissions in total, so most were seeded rather than earned. Every
screen downstream reads those rows and looks right: המסלול שלי shows יש תעודה,
the roster shows progress, `eligibility` computes cleanly. The hole is upstream
of everything that displays it, which is why sprints of screen work never met it.

REQ-M.14 is also, narrowly, still true: progress *is* written through babook's
code path. What nobody checked is that the certificate is issued through a
different code path, and that one מט״צים does not walk.

### This is why Avi's request is bigger than it looked

He asked for מט״צים to show more of the main site's courses, "הכל מתנגן אצלנו
עם כל הפיצ'רים שיהיו במרכזי". Measured against `templates/app/lesson.html`,
1474 lines against our 304, the features a course may carry include a materials
sidebar, an ask-about-this-lesson panel, runnable practice cells (`py-runner.js`),
Scratch project upload, Tinkercad model upload, notebook submission, and the
certificate gates themselves.

The two courses מט״צים already requires use one of those, and we do not have it.
Adding more courses without closing this first means offering a wider shelf of
things that also cannot be finished here.

### Not decided, and Avi's to decide

1. Build the project upload and the certificate gate inside מט״צים, which is the
   reading of REQ-M.126 that keeps everything in our walls.
2. Or let these specific actions happen on babook and reflect back, which is
   what he already said should be true for a member who wanders over there
   anyway, and which costs RULE-1 for that one hop.

Whichever, this comes before the course picker in `data_model.md` §7.

## SPR-M.48 — The improvement loop reaches the chat that runs the sprints  `DONE 2026-09-17`

**Goal:** Avi, after talking to נעמי: she will send a lot of feedback, and he
wants to read it, approve it and turn it into a sprint from a chat while working
remote, and then have her told what shipped and how to see it.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.48.1 | A narrow key for the queue: read, decide, record | REQ-M.105, M.110 | DONE |
| F-M.48.2 | The summary mail says how to see it | REQ-M.111 | DONE |
| F-M.48.3 | And thanks her, because it is true | REQ-M.111 | DONE |

### What already existed, and what actually did not

Most of the loop was built. `Request` carries status, `decided_by`, `sprint`,
`outcome` and `summary_sent_at`; `manage.py matazim_requests` reads and closes
rows and mails the summary. Checking before building saved a sprint of
rebuilding what was there.

The one thing that did not work was the part he asked about. Measured:
`GET https://babook.co.il/matazim/api/requests/` answers **403, authentication
credentials were not provided**. That API takes a session cookie, and an agent
in a chat has none and must never be handed one.

So `/matazim/internal/requests/` is the narrow key, built to the BKM in
`docs/building_an_app.md` that came out of ustrip's family endpoint.

### What a stolen token can do, and what it cannot

It can read staff feedback about a website and mark it decided. It cannot reach
a student, a leader, a submission, a certificate or any user account, and that is
asserted rather than described: `test_the_endpoint_touches_nothing_but_requests`
fingerprints every user, student and leader row before and after running every
verb the endpoint has.

Three verbs only, because the loop has three: read what is waiting, decide it,
record what was built. **No create**, deliberately: a request is somebody's own
words about their own experience, and a key that could write one could
manufacture a mandate for work nobody asked for. **No edit of `body`** either,
because REQ-M.112 says the text is hers and is never rewritten, and there is a
test that sends a new body along with an approval and checks it was ignored.

Approving still starts nothing (REQ-M.110). The test asserts the row moves and
that `sprint`, `done_at` and `summary_sent_at` stay empty.

### Two rules that behaviour cannot demonstrate

Running the perturbation pass on the guards produced two honest misses, and they
are worth recording because the instinct is to treat a miss as a hole.

**Constant-time comparison.** Swapping `constant_time_compare` for `==` was
caught by nothing, correctly: the two behave identically and differ only in how
long the wrong answer takes. No functional test can see that.

**Failing shut.** Deleting the `if not expected` guard also changed no outcome,
because an empty secret cannot match anything anyway: the comparison is already
guarded by `bool(presented)`. The check stays because the next person to edit
this function should meet the intent rather than deduce it from two interacting
conditions.

Both are now locked by reading the source, which is the only place the
difference is visible.

### The guard that caught me

`test_the_single_door_stays_single` from SPR-M.18 failed on the new module: any
`.status =` outside `history.py` must say, on the line, which model it assigns
and why. That rule exists so a real student transition cannot hide inside a
module that was exempted by name. The opt-out costs a sentence and leaves it in
the diff, which is exactly right, and it is now on both lines here.

### The mail

It already quoted her words verbatim and said what was done. It now also says
**how to see it**, because "it is fixed" asks the person who reported a confusing
screen to go hunting through it again, and the demo line is omitted rather than
invented when nobody wrote one.

And it thanks her. Not decoration: every review in this project has ended on the
same admission, that it can check the product against itself and cannot say what
a real person tried to do and could not. These rows are the only thing that
answers that.

### What Avi has to do before this works in production

Set `MATAZIM_ADMIN_TOKEN` in Render to a long random string. Unset means closed,
so until he does, the endpoint answers only a logged-in superuser and nothing
else changes. The secret never appears in this repo, in this backlog, or in a
chat transcript.

## SPR-M.49 — מצב לילה, and the first sprint the queue produced  `DONE 2026-09-18`

**Goal:** the two requests sitting approved in the queue since 13.09, read from
a chat through the key SPR-M.48 built:

> #1  "להוסיף מצב לילה ויום"
> #2  "מצב לילה אוטומתי לפי שעות היום"

One feature with two halves, plus a third state neither request names and the
product needs: a person overriding the clock.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.49.1 | A night palette, as tokens only | request #1 | DONE |
| F-M.49.2 | The clock chooses it, before the page paints | request #2 | DONE |
| F-M.49.3 | A switch, beside the bell, that outranks the clock | request #1 | DONE |
| F-M.49.4 | The screen contract stops reading the wall clock | | DONE |

### Only the tokens change

Every screen already draws itself from `:root`, so night mode is a palette swap
rather than a second stylesheet, and a screen written next year is dark without
anybody remembering to make it dark. `test_every_colour_token_has_a_night_value`
is what keeps that true: it reads both blocks and fails if a colour is added to
one and not the other.

Each dark value was measured against the surface it sits on, the same way the
light palette was. Dark is where this goes wrong quietly, because grey on grey
looks restful and is unreadable.

### Decided before the paint, on the reader's own clock

The choice is made by an inline script in the head. That is the one place a
blocking script earns its keep: decide after the stylesheet paints and somebody
opening the site at night gets a white flash first, which is the single most
common reason people distrust a night mode.

The hour comes from the reader's clock, not the server's. UTC is what the server
knows, and a member reading at 21:00 in Israel is not in the same evening as a
server that thinks it is 18:00. Night runs 19:00 to 06:00, and a page left open
across the boundary follows it.

A press of the switch stores a choice and the clock stops arguing. There is
deliberately no third press back to automatic: a three-state toggle nobody can
predict is worse than a two-state one.

### What the measuring found, and the gap that matters

The sprint's own contrast sweep covered eight screens and reported **zero**
failures. The screen contract, run with the dark palette pinned, covered 84 and
found **38**.

That gap is the whole argument for the screen contract, restated: eight screens
were the ones I thought to check, and 84 are the ones that exist.

Four root causes, all the same shape, a token doing a job it was not measured
for:

| What broke | Why |
|---|---|
| Every link, 2.65:1 | purple is an excellent button and poor text on a dark ground |
| Every secondary button label, 4.05:1 | the blue was *lightened* for the dark page, which lowers the contrast of the white sitting on it |
| The מסלול step markers, 1.79:1 | `--mz-teal-text` means "teal you read", and here it was a surface under white text |
| Tags, `.mz-btn-done`, `.mz-chosen`, 2.18:1 | hardcoded ink that could not follow the palette anywhere |

So there are now three teals with three jobs: identity, text, and a surface that
carries white. The same distinction the light palette already drew between
`--mz-teal` and `--mz-teal-text`, extended one step further.

### Two mistakes of mine worth recording

A blanket replace of `color: var(--mz-purple)` missed the one occurrence written
with `!important`, and broke a different one that was already correct:
`.mz-lamp-count` is a white pill on the purple lamp, so its ink must stay the
dark purple. The night contract caught both.

And `test_the_choice_is_made_before_the_page_paints` passed three times on code
that had lost the thing it checks. First because the phrase survived in a
comment; then because the once-a-minute timer contains an identical
`setAttribute` call. It now pins `setAttribute("data-theme", decide())`, which
is the pre-paint decision and nothing else. A test that cannot fail is worse
than no test, because it is counted.

### A suite that read the wall clock

The screen contract picks up whatever the clock chose, so it measured the light
palette before 19:00 and the dark one after. It was passing in the morning and
failing at night, and the failure was real both times.

It is pinned to light now, with `MZ_THEME` selecting the palette, and
`test_matazim_night_mode.py` runs the whole catalogue again in the dark. 84
screens pass in each.

### Still hardcoded, on purpose

`.mz-qr` stays white in both palettes. A QR code is read by a camera looking for
dark on light, and a dark one does not scan.

## SPR-M.50 — The second full review, and its five fixes  `DONE 2026-09-19`

**Goal:** Avi, 2026-09-19: "review all the project done so far. Focus on UX,
functionality, quality and more."

SPR-M.41, four days earlier, measured screens. Four sprints have shipped since
and each was measured on its way in, so repeating that walk would find what it
found. This review goes where nothing had looked: whether journeys close end to
end, what the bytes on disk actually are, and which code the 727 tests never
execute.

### What was measured

| Check | Method | Result |
|---|---|---|
| Code shape | line counts, module sizes, TODO markers | 11,048 lines, 44 modules, largest 1,351; zero real TODOs |
| Test coverage | pytest-cov over 727 tests | 88%; the 0% modules are commands run in a subprocess |
| Reachability | every named route vs every template, script and redirect | 80 of 83 reached; 3 are not |
| Read-only dependency on babook | every `app.models` import, reads vs writes | one true gap, and it is the known one |
| Page weight | gzip of everything a phone fetches | CSS 21KB; one asset is 102KB |
| Typography | md5 and OS/2 weight class of all six font files | all six are one file |
| Contrast, tap targets, overflow, both palettes | the standing suites | 84 screens × 2 palettes, 7 phone checks, all pass |

### The findings

| F-ID | Finding | Traces | Status |
|---|---|---|---|
| F-M.50.1 | ~~Every heavier weight is fake~~ **Wrong.** Six font files where two would do | REQ-M.5, SPR-M.21 | DONE |
| F-M.50.2 | 1.47MB of images on a recruitment page, 1.3MB of it one PNG photograph | REQ-M.5 | DONE |
| F-M.50.3 | `staff_consent` is an action with no door | REQ-M.84 | DONE |
| F-M.50.4 | The API's write paths are refused correctly and otherwise untested | REQ-M.139, Rule 6 | DONE |
| F-M.50.5 | Two endpoints nothing reaches and nothing tests | | DONE |
| F-M.50.6 | The certification path still does not close, and it is the only gap of its kind | REQ-M.76 | DECISION |
| F-M.50.7 | A member could write the feedback about their own work | REQ-M.19, M.123 | DONE |
| F-M.50.8 | A member can delete work a leader has answered, feedback and all | REQ-M.125 | DECISION |

### F-M.50.1 — one font, three names, six files

`md5sum` over `static/matazim/fonts/`: the Hebrew 400, 500 and 700 files are
byte-identical, and so are the Latin three. Opening any of them with fontTools:
**OS/2 weight class 300, subfamily "Regular".** All six are Rubik *Light*.

So the product has no medium and no bold. Every `font-weight: 500` and `700` in
the stylesheet, which is every heading, every button label and every emphasis,
is the browser thickening the light face on its own. It has been invisible
because synthesised bold looks roughly like bold, and nobody had put a real one
beside it.

SPR-M.21 self-hosted Rubik for a good reason and copied one file three times.
The fix is the real 400, 500 and 700 faces in those six slots, and a test that
reads the weight class out of each file so it cannot happen again.

### F-M.50.2 — a 102KB wordmark drawn at 34px

`logo.png` is 850×293 pixels and renders at 34px tall in the header. It is
102KB, does not compress, and is fetched on every page. The whole stylesheet is
21KB gzipped. An SVG, or a PNG at twice its rendered size, is a few kilobytes.

### F-M.50.3 — a screen with no door

`staff_consent` records guardian consent that a school collected on paper, so
the record carries who said so (REQ-M.84). Admin only, deliberately. No template
links to it, and the only test posts straight at the URL, which is how a screen
stays green while nobody can reach it.

The consent gate is switched off today, so this blocks nothing yet. The day it
is switched on, a program manager will need this screen and have no way to it.
Recorded now because "we will find it when we need it" is exactly how it stays
unfound.

### F-M.50.4 — the API is locked, and that is most of what is tested

The uncovered lines in `api.py` are `perform_create` (30 of them),
`perform_update`, `_decide`, `retire`, `restore`, `revoke`, `hide`, `show`,
`mark_read` and `perform_destroy`. SPR-M.34's sweep proved every endpoint
refuses the wrong reader and scopes every read; that was the right thing to
prove first. But whether creating a row through the API produces the right row,
with ownership set from the session and nothing client-supplied trusted, is
executed by almost nothing.

The API is Rule 6 infrastructure and the surface an agent uses. Its writes
deserve the same treatment its refusals got.

### F-M.50.5 — two leftovers

`clear_notices` marks everything read; so does opening the notices page, which
is why nothing links to it. `say_more` adds words to decided work; the review
screen's own form does that, which is why nothing links to it. Neither has a
test. Remove both.

### F-M.50.6 — confirmed unique, still Avi's

A sweep of every babook model מט״צים imports, reads against writes:
`UserVideoProgress` and `LessonReflection` are written through babook's own
endpoints on purpose (REQ-M.14), and `Course`, `Video`, `LessonQuiz` are babook's
content. `CourseCertificate` is the one model the programme *requires* its
members to earn and provides no way to earn. Nothing else has that shape.

Unchanged from 2026-09-17: build the project upload and the gate inside our
walls, or let those two actions happen on babook and reflect back. The course
picker in `data_model.md` §7 waits behind this.

### What this review did not find, and looked for

No module over 1,400 lines. No TODO that is real. No route that 404s. No
N+1 (the targets bank still renders 120 rows in 24 queries). No contrast, tap or
overflow regression in either palette. No second read-only gap. No stale
allowlist. 727 tests green.

### F-M.50.1 was wrong, and the correction is the interesting part

The review reported that all six Rubik files are byte-identical and declare
weight class 300, and concluded that every bold on the site is the browser
faking it. The first half is true. The conclusion was not, and it was stated
with more confidence than the evidence carried.

Rubik ships from Google as a **variable font**: `fvar` with a `wght` axis
running 300 to 900, and `usWeightClass` reports only the default instance. All
three weights point at one URL because one file covers the axis.

Settled in a browser rather than by reading the spec. The same string rendered
at several weights, once normally and once with `font-synthesis: none`:

| weight | width | with synthesis off |
|---|---|---|
| 400 | 427.30 | 427.30 |
| 500 | 442.70 | 442.70 |
| 700 | 457.84 | 457.84 |

Three distinct widths, unchanged by disabling synthesis. The weights were always
real; the browser was pinning the axis from each `@font-face` and downloading
the same file three times to do it.

**The real finding, six times smaller and still worth fixing:** 134KB of fonts
fetched per page where 45KB says the same thing. One declaration per subset with
`font-weight: 300 900` gives two requests instead of six, identical rendering
(the widths above are unchanged after the change), and 300 and 900 become
available as a side effect.

A measurement can be right and its conclusion wrong. md5 plus a weight class
looked like proof and was two facts about a file that does not work the way the
conclusion assumed.

### F-M.50.2 — the recruitment page weighed 1.6MB

| | before | after |
|---|---|---|
| `hero.png` | 1,322 KB | 92 KB as WebP |
| `logo.png` | 100 KB, 850×293 | 22 KB, 302×104 |
| `hemed_logo.png` | 46 KB, 530×468 | 15 KB, 226×200 |
| the home page, everything | ~1.6 MB | **270 KB** |

The hero was a photograph stored as PNG, which is what cost 1.3MB; it renders at
350×240 on a phone. WebP is safe here because `.mz-photo` already paints a
gradient underneath, so a browser too old for it shows a designed surface rather
than a hole. The two logos were simply larger than anything ever drew them.

### F-M.50.3 — the door

`staff_consent` is an action, not a screen, which the review got half right. It
takes a profile and records that a school collected consent on paper (REQ-M.84),
and nothing in the product ever called it.

The panel is on the student's page, because consent is a fact about one teenager
and that is the page about one teenager. Program managers only, and the view
still checks the role itself rather than trusting the template to have hidden
the form. While the gate is off it says so plainly instead of implying a
consequence that does not exist today.

### F-M.50.4 and F-M.50.7 — the sweep, and what it found on its first run

`test_no_endpoint_lets_a_caller_write_in_somebody_elses_name` hands every
writable endpoint a body naming somebody else as the owner and asserts the row
belongs to the caller. It matters more here than on most products: this API is
what an agent in a chat uses, and a locked door beside an open window is worse
than either alone.

Ownership held everywhere. What did not:

**A member could write the feedback about their own work.** `visible_submissions`
includes a member's own, correctly, because they have to read what was said, and
creation was scoped to the same queryset. So the person the feedback is *about*
could add rows to it under their own name. REQ-M.123 calls that table "what the
leader said". Now the same rule `_decide` has always had: saying and deciding are
both a leader's.

Nothing had ever run that path. That is the whole argument for testing writes
and not only refusals.

### F-M.50.8 — a question, not a bug, and Avi's to answer

A member can delete their own submission after a leader has answered it, and the
`Feedback` rows cascade away with it.

No rule is broken. REQ-M.125 keeps every attempt so that feedback keeps the
version it was about, which argues one way. A fourteen-year-old's right to
remove their own work argues the other. Inventing the answer in a test would
have been a decision made by whoever wrote the test, so the test pins today's
behaviour instead and the question comes here.

### F-M.50.5 — removed

`clear_notices` marked everything read; so does opening the page. `say_more`
added words to decided work; the review screen's own form does that. Neither had
a test, and nothing linked to either.
