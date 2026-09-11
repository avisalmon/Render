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

## SPR-M.8 — The leader's students  `PLANNED`

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

### What the track even is

There is no set of courses that constitutes מט״צים training today. `/matazim/courses/`
honestly says so. A roster cannot show progress through a track that does not
exist, so F-M.8.2 names one, as a list of slugs in `matazim/content.py`: no
migration, no field on babook's `Course`, and RULE-4 stays intact because babook
still knows nothing about us. Avi names the courses; until he does, a short
placeholder list drives the screens and the page says the track is provisional.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.8.1 | `matazim/progress.py`: progress for many students in a fixed number of queries, pinned to babook's rule by a test | REQ-M.74, REQ-M.14 | TODO |
| F-M.8.2 | The track is a named list of courses | REQ-M.23 | TODO |
| F-M.8.3 | The roster: every student the leader has, with stage, track progress and class | REQ-M.23, REQ-M.22 | TODO |
| F-M.8.4 | Classes: create, rename, put students in them. Offered, never required | REQ-M.23, Q14 | TODO |
| F-M.8.5 | One student, seen by their leader: stage, lesson-level progress, entrance attempt | REQ-M.23 | TODO |
| F-M.8.6 | Search and paging on the roster from the first commit | REQ-M.23 | TODO |
| F-M.8.7 | The whole thing on a phone | REQ-M.75 | TODO |

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

## SPR-M.9 — The admin's view  `NOT PLANNED`

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
