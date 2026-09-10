# מט״צים — Spec

> **Status: charter agreed 2026-09-09. Build starts clean.**
> A first version exists in the repo and in production as a *section of babook*
> (`main_spec.md` Chapter 10, commit `fbd6ffc`). That version is superseded and
> will be retired, not evolved. See `inventory.md` for the retirement plan.

---

## 1. The charter

מט״צים is **its own site**, reached at `babook.co.il/matazim`, run for רשת
החינוך עתיד. A visitor who lands there should have no way of telling, and no
reason to care, that babook is underneath.

**The one-line rule:** babook is the engine room, מט״צים is the building, and
the engine room has no door onto the street.

Three consequences, and everything else follows from them.

1. **Autonomous presentation.** Its own base template, header, footer,
   navigation, typography, colour, logo, tone of voice, error pages, and login
   surface. It does not extend babook's `base.html` and it does not inherit
   babook's drawer, top nav, search, or footer.
2. **No route back.** No link, breadcrumb, logo, "powered by", nav entry, or
   footer credit pointing at babook or any of its sections. The exit from
   מט״צים is the browser back button or the address bar, nothing we render.
   Symmetric: babook does not advertise מט״צים either.
3. **Shared infrastructure, invisible from the front.** The Django project, the
   database, the user accounts, the deploy pipeline, the media storage, the
   admin, and above all **the course engine** are the same ones babook uses. We
   build no second course player, no second progress tracker, and no second
   certificate system. We reuse the machinery and re-dress it.

## 2. The separation contract

The line between shared and separate is the most load-bearing thing here, so it
is written out rather than left to taste.

### 2.1 Shared (reused, never duplicated)

| Thing | Why it stays shared |
|---|---|
| Django project, settings, deploy (`render.yaml`) | One app, one deploy, one prod database. A second service is cost and drift for no gain. |
| `User` accounts and auth backend | A מט״צ is a real person with one account. Two account systems means two password resets and two support paths. |
| Course engine: `Course`, `Lesson`, `Enrollment`, `UserVideoProgress`, `CourseCertificate` | This is the whole reason מט״צים lives on babook. Learning is tracked once, by code that already works. |
| Classrooms: `TeacherClass`, `ClassMembership` | A מט״צ who teaches opens a real class with the real tool. |
| Media storage, mail, moderation, backups, the admin dashboard | Plumbing. Invisible either way. |

### 2.2 Separate (built new, owned by this spec)

A **new Django app named `matazim`**, added to `INSTALLED_APPS`, with its own
models, its own migration chain starting at `0001`, its own URLs, templates,
static files, and tests. Nothing about מט״צים lives in `app/` any more.

```
matazim/                     templates/matazim/        static/matazim/
  models.py                    base.html                 matazim.css
  views/                       ...                       ...
  urls.py
  entrance/                  tests/test_matazim.py
  management/commands/
  migrations/0001_initial.py
```

Separate: base template and full page chrome, design tokens and stylesheet, the
URL space under `/matazim/`, navigation and information architecture, the auth
surface, the course reading experience, and every model this space writes.

### 2.3 The rules that keep it separate over time

- **RULE-1: no outbound links.** A test asserts that no template under
  `templates/matazim/` renders an `href` to a non-`/matazim/` app URL (static,
  media, and external links excepted).
- **RULE-2: no shared chrome.** No template under `templates/matazim/` extends
  `templates/base.html` or includes a babook partial.
- **RULE-3: no writes to learning state.** מט״צים reads `Enrollment`,
  `CourseCertificate`, `TeacherClass` and friends. It never writes them. The
  only rows it owns are its own tables.
- **RULE-4: babook does not depend on מט״צים.** Removing the `matazim` app from
  `INSTALLED_APPS` leaves babook fully working. The dependency arrow points one
  way, and a test asserts no import from `app/` into `matazim/` in reverse.

## 3. What the program actually is

Carried forward from Chapter 10, because the product understanding was right
even though the packaging was wrong.

**מט״צים = מובילי טכנולוגיה צעירים.** Roughly 20 to 40 teenagers per cohort,
each of whom learns technology and then teaches a group of 10 to 20 younger
kids. Five stages:

**מתמיינים → לומדים → יוצרים → מדריכים → משפיעים**

- The space manages the מט״צים **as people**: recruitment, entrance test,
  acceptance, training, certification, community, recognition, reporting.
- The **kids are outside the system entirely**. They get a YouTube link. They
  do not sign up, are not members, are not modelled, and nothing about them or
  their learning is stored or inferred. We track מט״צים and nothing else.
- **Certification is status, not permission.** It unlocks nothing technical. It
  is granted by hand, by program staff, and it is meant to be scarce.
- **Retroactive credit.** On the day someone is certified, everything they have
  already done counts, with no backfill step.

### 3.1 What changed with autonomy

| Chapter 10 said | This spec says |
|---|---|
| The shell extends the site base, so `/matazim` inherits babook layout, drawer, search and mobile for free | The shell stands alone. All of it is built for מט״צים. |
| A member gets a "מט״צים" entry in the main site nav | No entry. The babook nav does not mention it. |
| The מט״צ learns "on babook, through the existing course engine" | The מט״צ learns **inside מט״צים**, through the same engine, rendered by our own screens. |
| Apply through the babook `/join/` wall | Own register, login and join screens over the shared `User` table. |
| One generic `Program` abstraction, מט״צים as its first instance | Still true and still worth keeping: a second network must be data, not code. |

## 3.2 The design system

Settled by Litala's three prototype screens (`prototype/README.md`), which are a
finished design rather than sketches. Full reading is in that file; the rules
that bind the build:

- **Teal is identity, purple is action.** Teal carries the wordmark, the hero,
  completed states. Purple carries primary buttons and the current step. Dark
  blue is the secondary action, dark navy is text. This is also what fixes the
  old contrast problem: teal never has to carry small text or a button label.
- White cards on near-white, generous radius, soft shadow, wide spacing.
- One teal-to-purple gradient band, used once, for the public stats.
- Illustrated 3D objects (cube, robot, laptop, trophy, flag) as section marks.
- **Status is always a word plus a colour**, never a colour alone.
- Progress appears as a ring on a card, a bar for the overall figure, and a
  donut in a sidebar. All three exist; use each where the screens use it.
- Avatars default to initials. A photo is opt-in, never the default for a minor.

## 4. Data model

Owned by the `matazim` app (the only rows it writes):

- **`Program`** — `slug`, `name`, branding, `current_cohort_year`, `is_active`.
  The space is driven by this record; a second network is a second row.
- **`School`** — `name`, `city`, contact, `join_code` (unguessable, rotatable),
  `is_open`.
- **`Membership`** — `user`, `program`, `school`, `school_join_status`
  (`pending`/`confirmed`), `cohort_year`, `status`, plus accepted/certified
  who-and-when-and-note. Cohort members only; the adults who run the program
  never get one.
  - `status`: `applied` (מתמיינים) / `in_training` (לומדים) /
    `project_submitted` (יוצרים) / `certified` (מדריכים) / `alumnus` /
    `rejected` / `revoked`. Litala's five-stage funnel **is** this field.
- **`Application`** — three answers only (grade, why, what have you built).
- **`EntranceAttempt`** — target, uploaded model, measurements, issues, passed.
- **`StatusLog`** — append-only audit of every transition.
- **`Submission`** — the deliverable, its reviewer, status, and written feedback.
- **`Practicum`** — what the מט״צ is teaching, to which group, when, and how far
  through. Declared by them. Holds no row about any child.
- **`Stage`** — the course groupings drawn on screen 2: יסודות הטכנולוגיה,
  תלת-ממד, קורסי בחירה, הדרכה ומיומנויות, פרקטיקום. Ordered, with an advance
  rule (screen 2 shows "השלימו עוד 2 קורסים כדי לעבור לשלב הבא"), and each stage
  points at shared `Course` rows rather than owning content.
- **`Milestone`** — one node on the member's path: type (entrance test,
  acceptance, course, deliverable, יום שיא, פרקטיקום), order, target date,
  status, and a link to whatever it points at. Explained below.
- **`MemberProfile`** — one row per `User` who has met מט״צים, holding only what
  this space is entitled to know: `entered_via_matazim`, `first_seen_at`,
  `welcome_accepted_at`, and `entrance_test_passed_at`. It is a **companion to**
  babook's `UserProfile`, never a replacement: name, avatar and everything about
  identity stay in the shared profile and are edited through it, so a person has
  one name across both products. This is what keeps RULE-3 true while still
  meeting "use the same profile model": the shared facts stay shared, and only
  מט״צים's own flags are מט״צים's.
  - `entrance_test_passed_at` is provisional. It is a stored flag while the test
    is a placeholder, and becomes **derived** from `EntranceAttempt` the moment
    REQ-M.17 lands. Read it through a method, never the column, so that swap is
    invisible to every caller.
- **`Event`** (ימי שיא) — title, date, location, target schools.
- **`Notification`** — the bell, the mail icon, and the משוב חדש card on screen
  3 all need somewhere to come from.
- Later: **`Post`** (cohort feed).

### 4.1 The track is milestones, not a status field

The single biggest thing the prototype changes. Chapter 10 modelled the funnel
as a five-value `status` on the membership. Screen 3 draws something else: a
path of roughly fourteen **typed, dated, individually-statused nodes**, with the
current one badged המשימה הנוכחית, and it is the centre of the whole product.

`Membership.status` survives as the coarse stage, because staff and reporting
think in מתמיינים through משפיעים. But it becomes **derived from the
milestones**, not the source of truth. Milestone statuses are their own set,
drawn with a word and a colour and never a colour alone: הושלם, בתהליך, דורש
תיקון, ממתין לבדיקה, טרם התחיל.

A milestone never duplicates learning state. A course milestone reads its
percentage live from `Enrollment` and `UserVideoProgress` (RULE-3); it stores
only its place in the path and its target date.

`Membership` also carries **`mentor`**, a nullable FK to the `User` who reviews
this member's work, chosen by the member (REQ-M.31). It is deliberately not the
same thing as `school`: the school says where you are, the mentor says who reads
your submissions, and a school with two teachers needs both.

**Roles are exactly two M2M relations and there is no third**: `Program.staff`
(the program admins, who alone may open a school, assign a leader, or grant the
status) and `School.leaders` (the teachers, whose scope is exactly the schools
they appear in). A `role` field on the membership is deliberately not added:
two sources of truth for one permission is how cross-school leakage happens.

**Derived, never stored**: הדרכות taken and completed, classes opened, and
counts of kids taught. All live queries over the shared tables.

## 5. Requirements

### 5.1 The space itself

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.1 | Autonomous shell | `templates/matazim/base.html` stands alone: own header, nav, footer, fonts, colour, favicon and page title. It never extends or includes a babook template. Hebrew RTL, works from 360px up. | DONE |
| REQ-M.2 | Own error pages | 404 and 500 raised under `/matazim/` render in the מט״צים shell, not the babook one. | TODO |
| REQ-M.3 | Sealed both ways | No template under `templates/matazim/` links outside the prefix; no babook template, nav, drawer, search result, sitemap entry or context processor mentions מט״צים. Enforced by tests, not by care. | DONE |
| REQ-M.4 | Driven by data | Branding, cohort year and copy come from the `Program` record. Adding a second program is data, not code. Nothing hardcodes the string `matazim` outside the seed. | TODO |
| REQ-M.5 | The nine sections | The information architecture is Litala's, from the brief: דף הבית, המסלול השנתי, מבחן הכניסה, הקורסים שלי, הגשת תוצרים, ימי שיא, בתי הספר המשתתפים, קהילת מט״צים, אזור אישי. The first two and בתי הספר המשתתפים are open logged out and double as recruitment material; the rest are member surfaces. | WIP |
| REQ-M.5a | Where am I, always | Her central emphasis, quoted: every member sees immediately where they are, what they have completed, and what their next task is. This is the acceptance test for the home screen and the personal area, not a nice-to-have. | TODO |
| REQ-M.5b | Nav changes with state | Logged out: אודות התכנית, המסלול השנתי, הקורסים, מבחן הכניסה, בתי הספר, קהילת מט״צים, ימי שיא. Logged in: המסלול **שלי**, הקורסים, הגשות ותוצרים, ימי שיא, בתי הספר, קהילת מט״צים, plus notifications and the member menu. Same site, two navs. | WIP |
| REQ-M.5c | Two front doors | The public home offers כניסת תלמידים and כניסת מובילים as separate calls to action, and each lands the person where their role belongs. One auth underneath, two doors on the street. | WIP |
| REQ-M.5d | The entrance test is public | מבחן הכניסה is a hero CTA and a nav item, reachable with no account. Signing up happens around the test, not before it. | WIP |
| REQ-M.5e | Public showcase | תוצרים נבחרים on the home page: selected member projects with a photo, a title and a school, and no student named. Publishing any project requires the member's opt-in **and** a staff decision, and either can be withdrawn. **Held: the section is off the page until real projects and real consent exist, and a test asserts its absence.** | HELD |
| REQ-M.5g | Partners carry weight | שותפים מרכזיים לעשייה is a section of the page, directly under the hero and above איך זה עובד, showing the partners' own marks rather than a line of small print in the footer. Each mark is drawn at its own optical size, and no caption repeats a name the logo already carries. Room is kept for the partners not yet named. | DONE |
| REQ-M.5f | Public counters | The stats band (students, schools, projects, leaders, ימי שיא) is aggregate only and computed, never typed in by hand. **Held: the band is off the page until something computes it, and a test asserts its absence.** | HELD |

### 5.2 Identity and access

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.6 | Own threshold | Register, log in, and log out at `/matazim/` URLs, in the מט״צים shell, writing to the shared `User` table. The word babook appears nowhere on these screens. | DONE |
| REQ-M.7 | Existing account, same door | Someone who already has a babook account signs in with it here and it just works. No second password, no linking step, no visible mention that the account is shared. | DONE |
| REQ-M.8 | Return to intent | Hitting a member page while logged out lands on the מט״צים threshold and returns to the intended page afterwards, newly registered or freshly logged in. One link works for new and existing users alike; no branching is written anywhere. | TODO |
| REQ-M.9 | School invite link | Each school carries a rotatable `join_code` powering a link and a QR that its teacher hands out. A logged-out visitor gets a landing page naming the school, not a bare login form: the link gets pasted into WhatsApp groups. Arriving this way attaches them to that school with no confirmation step. | TODO |
| REQ-M.10 | The open door | Applying without a link means choosing a school from the list; its leader then confirms them onto the roster. Both doors end at `applied`. | TODO |
| REQ-M.11 | Member pages gated | Anything past the public front requires an active `Membership`. A logged-in babook user with no membership sees the public front and the application, nothing else. | TODO |
| REQ-M.46 | Signing in lands you on the main view | Every door ends in the same place: דף הבית, not the personal area. Someone who just signed in wants to see the program, not a form about themselves, and the personal area is one click away in the header whenever they want it. Today password login lands correctly while register and Google do not, which is the sort of inconsistency nobody notices until they use all three. | TODO |
| REQ-M.45 | Google is a door here too | המשך עם Google sits on the login and register screens, as it does on the wider platform, because for a 14-year-old it is the difference between joining and giving up on a password field. The link the page renders stays inside `/matazim/`: it goes to our own URL, which hands off to the provider and brings them back into the prefix. RULE-1 is not bent for it, and the visitor never lands on a babook page. | DONE |
| REQ-M.35 | Entry through this door is recorded | A visitor who arrives at a `/matazim` URL is marked as having come in through מט״צים, and signing in through this app's own button stamps it on their מט״צים profile. It answers "did this person find us here, or are they a babook member who wandered over", which is the only way to read the funnel later. | DONE |
| REQ-M.36 | The joining doors wait for the test | כניסת תלמידים is inactive until the visitor has passed the entrance test, and says why rather than simply refusing. **כניסת מובילים is not gated**: the test measures a teenager's commitment, and a teacher confirming students onto a roster has no reason to model a 3D object (Avi, 2026-09-10). | DONE |
| REQ-M.37 | The returning-user door is never gated | התחברות in the header always works. Without it the gate locks out everyone who already passed and came back, because we only learn that they passed after they sign in. The hero doors are for joining; the header is for returning. | DONE |
| REQ-M.38 | The entrance test has a home | מבחן הכניסה is a real page at its own URL, reachable with no account, and it is what the gated door points at. This sprint it is a placeholder that explains what is coming; the Tinkercad task itself is REQ-M.17. | DONE |

### 5.2a First contact

Everything a person meets before they are anyone here.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.39 | Welcome, once | On a first visit the space greets the visitor and states plainly that this is a **prototype**: not an official Intel site, experimental, and carrying no obligation on anyone who uses it. Dismissing it is an explicit acknowledgement, not a stray click on the background. | DONE |
| REQ-M.40 | The acknowledgement is kept | For a signed-in person the acceptance is stored with a timestamp on their מט״צים profile, so we can show who was told and when. A visitor who is not signed in still sees it, and their dismissal survives the visit; it simply cannot be attributed to anyone. | DONE |
| REQ-M.41 | Replay the first time | The profile carries a control that clears the flag so the first-time experience can be walked through again from scratch. Built for testing, and it stays while the site is a prototype. | DONE |

### 5.2b The profile inside the walls

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.42 | One identity, a מט״צים view of it | A profile page at a `/matazim/` URL showing only what matters here. Name and the rest of the personal details are the **shared** babook profile, edited here and changed everywhere, because a person has one identity and one name. | DONE |
| REQ-M.43 | Where I stand in the program | The profile shows the school the member belongs to and whether they are already a certified מט״צ. Until `Membership` exists these read as "not yet assigned" rather than being hidden, so the shape of the page is honest about what is coming. | WIP |
| REQ-M.44 | Everything I have learned, anywhere | The profile lists every הדרכה the person has done or is doing **anywhere on babook**, completed and in progress, read live from `Enrollment`, `UserVideoProgress` and `CourseCertificate` and never copied (RULE-3). Learning done before מט״צים existed counts, with no backfill step. | DONE |

### 5.3 Learning inside the walls

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.12 | המסלול שלי | The member's path drawn as an ordered run of typed milestones, each with a status word, a colour and a date, the current one badged המשימה הנוכחית. Above it, five live cards: overall progress, the next task, the next submission due, the next יום שיא, and any new feedback. Below it, the course in progress with its lesson checklist, submissions with their state, and upcoming events. This screen is the product. | TODO |
| REQ-M.12a | Stage-grouped, gated courses | הקורסים שלי groups courses by stage (יסודות הטכנולוגיה, תלת-ממד, קורסי בחירה, הדרכה ומיומנויות, פרקטיקום), filterable by stage and status. Courses in a stage the member has not reached show a padlock, and the sidebar states the advance rule plainly ("השלימו עוד 2 קורסים כדי לעבור לשלב הבא"). A lock is never a dead end without a reason next to it. | TODO |
| REQ-M.12b | Course cards carry state | Every card shows a progress ring, a status word, and an action that matches the state: התחל, המשך, צפה שוב. | TODO |
| REQ-M.13 | Lessons render in the shell | Opening a lesson keeps the member inside `/matazim/`, in the מט״צים chrome. Video, text, quizzes and practice cells work as they do on babook, because they are the same components, not copies. | TODO |
| REQ-M.14 | Progress written once | Watching and completing writes to `UserVideoProgress`, `Enrollment` and `CourseCertificate` exactly as babook does, through the same code path. No parallel progress table, no divergence. | TODO |
| REQ-M.15 | Reads, never writes program state onto learning | Training figures shown anywhere in מט״צים are live queries. Nothing is copied, mirrored, or cached into program tables. | TODO |

### 5.4 The funnel

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.16 | Apply | Three questions only (grade, why, what have you built). The application is not what assesses them, the entrance test is, so every extra field is only a teenager who does not finish the form. Creates a `Membership` at `applied` plus an `Application`. | TODO |
| REQ-M.17 | Entrance test | A Tinkercad replication task measuring commitment, not skill: the candidate reproduces a given model and uploads it, and the geometry is checked automatically. Retryable, and there is no machine rejection, only "not yet". The automatic check is advice, not a verdict: a school leader reviews the attempt (בדיקת מבחן הכניסה in the brief) and decides. | TODO |
| REQ-M.18 | Acceptance by hand | Program staff move `applied` to `in_training`. Selectivity is the product, not an obstacle to it. | TODO |
| REQ-M.19 | Submissions and feedback | The יוצרים stage: the member uploads a deliverable, their מוביל sees it, approves or returns it, and **writes feedback the member can read**. The feedback is the interaction that matters here, not the approve flag. | TODO |
| REQ-M.20 | Certification and certificate | Only program staff grant מדריך status, and doing so produces a printable certificate. It unlocks nothing technical and credits everything already done, retroactively. | TODO |
| REQ-M.21 | Every transition logged | `StatusLog` records who, when, from, to, and note. Append-only. Revocation is a transition like any other. | TODO |
| REQ-M.31 | The member chooses their מוביל | From the brief: a student picks the leader who will review their work. This is a relation on the membership, separate from the school roster: the school says where you are, the mentor says who reads your submissions. A leader can be swapped, and the change is logged. | TODO |
| REQ-M.32 | פרקטיקום | The מדריכים stage, the actual teaching, is visible to the member, to their מוביל, and to program staff: what they are running, when, and how far through. It is both a course stage (there are courses that prepare for it) and a tracked activity. Recorded as the מט״צ's own declared activity, never as data about the children (REQ-M.29). | TODO |
| REQ-M.33 | Notifications | A bell and a message icon in the member header, and the events that feed them: feedback received, a submission approved or returned, a deadline approaching, a יום שיא announced, a stage unlocked. A new piece of feedback surfaces on המסלול שלי without the member going looking for it. | TODO |
| REQ-M.34 | Deadlines and the calendar | Milestones and events carry dates, the personal area shows what is close, and לוח הזמנים shows the whole year. | TODO |

### 5.5 Staff and school leaders

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.22 | Scope is the data | A school leader sees exactly the schools they lead, and this is a property of the M2M, not a rule to remember. Program staff see the whole cohort. | TODO |
| REQ-M.23 | Roster | Leaders confirm members onto their school roster, see each member's stage and training progress, and nothing about any child. | TODO |
| REQ-M.24 | Cohort view and reporting | Program staff see the funnel by stage and by school, and can export it. This is Litala's screen. | TODO |
| REQ-M.25 | School management | Open a school, assign a leader, rotate a join code, close registration. Staff only. | TODO |

### 5.6 Community and recognition

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.26 | Cohort feed | Announcements and posts, inside the walls. | TODO |
| REQ-M.27 | ימי שיא | Program events with dates, locations and target schools. | TODO |
| REQ-M.28 | The status is visible | Certification shows inside מט״צים and on anything printed or presented. Whether it also shows on public babook surfaces is Q4 below, still open. | TODO |

### 5.7 Privacy (non-negotiable)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.29 | One tracked population | Nothing in this product creates, stores, or infers a record about a child. The kids a מט״צ teaches are not users, not members, not rows. Teaching is recorded as the מט״צ's own declared activity. | TODO |
| REQ-M.30 | Minors' data stays minimal | The people in this system are teenagers in כיתה ט'. We hold what the program needs to run and nothing more, and it is not exposed outside the school leader and program staff scopes. | TODO |
| REQ-M.30a | Nothing about a minor is public by default | The public gallery names a school, never a student. A photo avatar is opt-in; initials are the default. Publishing a project takes the member's consent and a staff decision, and either can be withdrawn later. | WIP |

## 6. Open questions

| # | Question | Why it matters |
|---|---|---|
| Q4 | Does the מט״צ badge appear on public babook surfaces (profile, community, class pages)? | Chapter 10 argued yes, on the grounds that invisible status is not status. Full separation argues no. Not blocking: it only affects REQ-M.28. |
| Q5 | Litala's sign-off on the core change. Note her brief asks for **הקורסים שלי** as a site section, so she expects the site to *hold* the learning, not merely reflect it. The autonomy decision now gives her exactly that, which likely closes this rather than blocking it. Confirm with her. | Was blocking everything past the entrance funnel. Probably resolved. |
| Q6 | Production already has the old tables and, possibly, real rows. Confirm nobody has applied before we drop them. | Blocks the retirement migration in SPR-M.1. |
| Q8 | "פתיחת תכנים ומשימות" by program staff: do they get an authoring surface inside מט״צים, or do they author in babook's studio and only publish here? | An authoring UI inside the walls is a large piece of work. Authoring in the studio is free but means Avi and Litala cross into babook, which members never do. |
| Q9 | Terminology: her brief says תלמידים and מובילים, our docs say מט״צים and מובילי בית ספר. | Cosmetic but pervasive; settle before SPR-M.2 writes the copy. |
| Q10 | **Scale.** The prototype's stats band says 1,250 students, 120 leaders, 28 schools. Our scoping said 20 to 40 teenagers per cohort. Are those numbers real or filler? | Everything rests on this. Certification granted by hand by two people, and status that is deliberately scarce, are designs for 40 people, not 1,250. If the figures are real, school leaders have to carry the granting and the staff screens need bulk tools. |
| Q11 | The public gallery publishes minors' work. Who consents, and does a parent sign anything? | Blocks REQ-M.5e. My default in the spec is opt-in by the member plus a staff decision, both withdrawable, but consent for a ninth-grader may need a parent. |
| Q12 | The public path shows four stages (לומדים, יוצרים, מדריכים, משפיעים) while the program has five, with מתמיינים first. Deliberate? | Cosmetic if deliberate, confusing if not. My reading is deliberate: מתמיינים is the entrance test, which has its own CTA. |

**Closed:** Q1 start clean, new Django app (2026-09-09). Q2 מט״צים-branded auth
over shared accounts (2026-09-09). Q3 courses render inside the shell
(2026-09-09). Q7 brand direction, settled by Litala's three prototype screens
(2026-09-09), read in `prototype/README.md` and summarised in section 3.2.

## 7. Reference

Superseded material, kept for history: `docs/main_spec.md` Chapter 10,
`docs/backlog.md` EPIC-10, the site brief from Litala Aviv of 2026-08-03, and
the scoping conversation of 2026-08-08.
