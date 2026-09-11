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
- **RULE-3: one version of the truth about learning.** מט״צים keeps **no
  parallel record** of what anyone has learned: no progress table of its own, no
  mirrored enrolment, no cached completion. It never writes `UserVideoProgress`
  or issues a `CourseCertificate` by hand, because both sit behind real logic
  (watch thresholds, review gates) and a second way to set them is a second
  truth. Enrolling someone in a course they are actually taking is allowed and
  goes through the same one-liner babook's own lesson view uses.

  *Amended 2026-09-10.* The rule first read "never writes them", which the guard
  test correctly threw at the first lesson we rendered: you cannot watch a
  lesson without an enrolment, so the original wording made REQ-M.13 impossible
  and contradicted REQ-M.14. The danger was never enrolment, it was divergence.
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
| One generic `Program` abstraction, מט״צים as its first instance | **Dropped 2026-09-10.** There is one program and no second network in sight, so `Program` was a table doing nothing. It becomes a table on the day a second one exists. |

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
- **A phone is the default screen, not an afterthought.** Every page works at
  390px with nothing wider than the viewport, and every tappable thing is at
  least 36px tall. `tests/test_matazim_mobile.py` drives a real browser and
  fails when that stops being true, because a one-off look does not hold.

## 4. Data model

Settled with Avi on 2026-09-10, after two rounds of cutting. An earlier draft
had `Program` and `School` as tables. Both were doing work a field can do, for a
single program with no second network in sight, so both are gone.

**מט״צים owns people and program state. babook owns learning. `User` is the
pivot between them, and nothing is copied across.**

### 4.1 What babook owns, and מט״צים only reads

`Course`, `Video`, `Enrollment`, `UserVideoProgress`, `CourseCertificate`,
`TeacherClass`, `ClassMembership`.

מט״צים adds no progress model, no completion model and no certificate model.
That is RULE-3: one version of the truth about learning. Enrolling someone goes
through the same one-liner babook's own lesson view uses.

### 4.2 What מט״צים owns

```
MemberProfile     OneToOne → User                      built
  entered_via_matazim, first_seen_at,
  welcome_accepted_at, entrance_test_passed_at
  is_admin                                  ADMIN. Assigns leaders.

Leader            OneToOne → User
  contact, join_code                        the link they hand out
  is_active, assigned_by, assigned_at

StudyClass        FK → Leader
  name, school_name, year, is_active
  (`class` is a reserved word, hence the name)
  Gains attributes as the program needs them.

Student           FK → User, FK → Leader  (NULL until someone takes them)
  status            מתמיינים → לומדים → יוצרים → מדריכים → משפיעים
  cohort_year
  classes           M2M → StudyClass
  unique(user, cohort_year)

EntranceTarget, EntranceAttempt                        built

later: Application, Submission, Practicum, StudyStage, Milestone,
       Notification, Event, Post, StatusLog
```

**School sits on the class, not the leader** (Avi, 2026-09-10). A leader running
classes at two schools works without a second leader record, and the label lands
where the students actually sit. בתי הספר המשתתפים is then the distinct set of
`StudyClass.school_name`, and a student's school is their class's.

**A student can exist before any leader has them.** `Student.leader` is nullable
on purpose: someone registers, passes the entrance test, and is nobody's yet.
From there it goes either way, and both happen: they ask to join a leader
(REQ-M.10), or a leader invites them through their link (REQ-M.9).

**Role precedence is admin, then leader, then student.** One person can hold
more than one, and the access function's ordering decides it rather than leaving
it to accident.

`MemberProfile` and `Student` are deliberately separate. The profile is about a
person meeting this site once: they came through this door, they were told it is
a prototype, they proved they can model in Tinkercad. The `Student` row is about
being in a cohort, and a person can be in more than one. Passing the entrance
test belongs to the person, not to the year.

### 4.3 Four roles, four different things

| Role | How it is known | Sees |
|---|---|---|
| Root | `User.is_superuser` | Everything, plus the prototype tools |
| Admin | `MemberProfile.is_admin` | Every student, every leader, all progress |
| Leader | Having a `Leader` row | Their own students, and nothing else |
| Student | Having a `Student` row | Themselves |

**No role column, and `is_admin` is not one.** The rule that matters is that a
role must have exactly one source. A `role` field on `Student` would compete
with the `leader` FK and the two could disagree, which is how one leader ends up
seeing another's students. `is_admin` competes with nothing: it is the only
place adminship is recorded.

### 4.4 The whole permission model

```python
def visible_students(user):
    if user.is_superuser or is_admin(user):
        return Student.objects.all()
    if leader := Leader.objects.filter(user=user).first():
        return Student.objects.filter(leader=leader)
    return Student.objects.filter(user=user)
```

A leader cannot see another leader's students because **the query cannot reach
them**, not because a view remembered to check. Every screen asks this one
question and then works with what comes back.

### 4.5 Progress crosses the boundary in one join

```python
Enrollment.objects.filter(user__matazim_student__leader=me)
```

`Student` points at `User`, `User` has `Enrollment`. The same join serves one
student, one leader's roster, or the whole program, with a different filter.
This query is the reason learning stays in babook's tables: had we built our own
progress model, it would not exist and we would be reconciling two sets of
numbers forever.

### 4.6 Derived, never stored

הדרכות taken and completed, classes opened, kids taught, and every figure on
every dashboard. All live queries over the shared tables.

### 4.7 The track is milestones, not a status field

Litala's screen 3 draws a path of roughly fourteen typed, dated,
individually-statused nodes, with the current one badged המשימה הנוכחית, and it
is the centre of the whole product.

`Student.status` survives as the coarse stage, because reporting thinks in
מתמיינים through משפיעים. But it becomes **derived from the milestones**, not the
source of truth. Milestone statuses are their own set, drawn with a word and a
colour and never a colour alone: הושלם, בתהליך, דורש תיקון, ממתין לבדיקה, טרם
התחיל.

A milestone never duplicates learning state. A course milestone reads its
percentage live from `Enrollment` and `UserVideoProgress`; it stores only its
place in the path and its target date.

### 4.8 What is deliberately not modelled

**No `Program` table.** There is one program. A second network becomes a table
and a migration on the day one exists, and not before. This retires REQ-M.4.

**No `School` table.** `Leader.school_name` carries the label, so per-school
reporting is a grouping rather than a join. The cost is honest and recorded: a
typo makes a second school, and two leaders at one school can drift apart. If
Litala's school-level reports matter enough, a `School` table is about ten lines
and one FK, and promoting the field is one migration.

**No group inside a group.** `StudyClass` belongs to a leader and that is the
only nesting. Whether classes are needed at all is Q14's decision: forty
students across the network means a leader has one or two and school *is* the
group; twelve hundred means a leader has forty-five and needs to split them.

## 5. Requirements

### 5.1 The space itself

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.1 | Autonomous shell | `templates/matazim/base.html` stands alone: own header, nav, footer, fonts, colour, favicon and page title. It never extends or includes a babook template. Hebrew RTL, works from 360px up. | DONE |
| REQ-M.2 | Own error pages | 403, 404 and 500 raised under `/matazim/` render in the מט״צים shell, not the babook one, and babook's own errors are untouched. Django's handlers are project-wide, so this dispatches on the path. Found live: a 403 was serving babook's page with its title and drawer, because the guard tests read templates and successful pages and an error page is neither. | DONE |
| REQ-M.3 | Sealed both ways | No template under `templates/matazim/` links outside the prefix; no babook template, nav, drawer, search result, sitemap entry or context processor mentions מט״צים. Enforced by tests, not by care. | DONE |
| REQ-M.4 | ~~Driven by data~~ | **Retired 2026-09-10** with the `Program` table. It existed so a second network would be data rather than code; there is no second network, and inventing one cost a table, a foreign key on everything, and a concept on every screen. See spec §4.8. | DROPPED |
| REQ-M.5 | The nine sections | The information architecture is Litala's, from the brief: דף הבית, המסלול השנתי, מבחן הכניסה, הקורסים שלי, הגשת תוצרים, ימי שיא, בתי הספר המשתתפים, קהילת מט״צים, אזור אישי. The first two and בתי הספר המשתתפים are open logged out and double as recruitment material; the rest are member surfaces. | DONE |
| REQ-M.5a | Where am I, always | Her central emphasis, quoted: every member sees immediately where they are, what they have completed, and what their next task is. This is the acceptance test for the home screen and the personal area, not a nice-to-have. | TODO |
| REQ-M.5b | Nav changes with state | Logged out: אודות התכנית, המסלול השנתי, הקורסים, מבחן הכניסה, בתי הספר, קהילת מט״צים, ימי שיא. Logged in: המסלול **שלי**, הקורסים, הגשות ותוצרים, ימי שיא, בתי הספר, קהילת מט״צים, plus notifications and the member menu. Same site, two navs. | WIP |
| REQ-M.5c | Two front doors | The public home offers כניסת תלמידים and כניסת מובילים as separate calls to action, and each lands the person where their role belongs. One auth underneath, two doors on the street. | WIP |
| REQ-M.5d | The entrance test is public | מבחן הכניסה is a hero CTA and a nav item, reachable with no account. Signing up happens around the test, not before it. | WIP |
| REQ-M.5e | Public showcase | תוצרים נבחרים on the home page: selected member projects with a photo, a title and a school, and no student named. Publishing any project requires the member's opt-in **and** a staff decision, and either can be withdrawn. **Held: the section is off the page until real projects and real consent exist, and a test asserts its absence.** | HELD |
| REQ-M.5g | Partners carry weight | שותפים מרכזיים לעשייה is a section of the page, directly under the hero and above איך זה עובד, showing the partners' own marks rather than a line of small print in the footer. Each mark is drawn at its own optical size, and no caption repeats a name the logo already carries. Room is kept for the partners not yet named. | DONE |
| REQ-M.5f | Public counters | The stats band (students, schools, projects, leaders, ימי שיא) is aggregate only and computed, never typed in by hand. **Held: the band is off the page until something computes it, and a test asserts its absence.** | HELD |

### 5.1a The rest of the front

Litala's nine sections, finished. SPR-M.1 built דף הבית and left the other eight
pointing back at it, which is worse than a missing link: a menu item that
silently reloads the page you are on reads as broken.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.56 | No dead nav | Every item in the menu goes somewhere that says something true. Nothing points at the page it is already on, and nothing pretends a section exists when it does not. | DONE |
| REQ-M.57 | אודות התכנית | What מט״צים is, who it is for, who runs it, and what a member actually does. Open logged out. This is the page a parent reads. | DONE |
| REQ-M.58 | המסלול השנתי | The **five** stages as a path, with what happens at each and roughly when. מתמיינים is included here even though the home page shows four: the teaser sells the journey, this page is the journey. | DONE |
| REQ-M.59 | הקורסים | The training path. Honest about what is open: מבחן הכניסה is real and reachable today, the rest of the track opens as the cohort moves, and the page says so rather than listing courses nobody can start. | DONE |
| REQ-M.60 | The sections that need data say so | בתי הספר, קהילת מט״צים and ימי שיא have no `Leader`, `Post` or `Event` behind them yet. Each gets a real page in our voice explaining what will live there, rather than a dead link or invented content. | DONE |

### 5.2 Identity and access

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.6 | Own threshold | Register, log in, and log out at `/matazim/` URLs, in the מט״צים shell, writing to the shared `User` table. The word babook appears nowhere on these screens. | DONE |
| REQ-M.7 | Existing account, same door | Someone who already has a babook account signs in with it here and it just works. No second password, no linking step, no visible mention that the account is shared. | DONE |
| REQ-M.8 | Return to intent | Hitting a member page while logged out lands on the מט״צים threshold and returns to the intended page afterwards, newly registered or freshly logged in. One link works for new and existing users alike; no branching is written anywhere. | TODO |
| REQ-M.9 | The leader's invite link | Each **leader** carries a rotatable `join_code` powering a link and a QR they hand out. A logged-out visitor gets a landing page naming the leader and their school, not a bare login form: the link gets pasted into WhatsApp groups. Arriving this way attaches the student to that leader with no confirmation step, because the leader gave them the link and the assignment is already their decision. | DONE |
| REQ-M.10 | The open door | Applying without a link means choosing a leader from the list of participating schools; that leader then confirms them onto the roster. Both doors end at `applied`. | DONE |
| REQ-M.72 | An invite is never lost on the way | A link arrives by WhatsApp and gets tapped by someone with no account, or with an account but no entrance test. Neither is an error and neither may drop the invite: the leader's name is carried through registering and through the whole test, shown at each step, and the moment they are eligible the joining is one tap. Losing an invite silently is how a kid ends up in the program attached to nobody. | DONE |
| REQ-M.73 | A leader has somewhere to stand | כניסת מובילים lands a leader on their own page: their invite link and QR to hand out, and the students waiting for them to confirm. The roster proper is a later sprint; without this the open door is a dead end, because nobody can accept anyone. | DONE |
| REQ-M.11 | Member pages gated | Anything past the public front requires a `Student` row. A logged-in babook user without one sees the public front and the application, nothing else. | TODO |
| REQ-M.65 | Nobody's yet | A student with no leader is a normal state, not an error. They see their own progress, their entrance test, and one clear way forward: ask to join a leader, or wait for the invite link they were promised. The page never reads as though something has gone wrong, because nothing has. | DONE |
| REQ-M.66 | The leader door for someone who is not a leader | כניסת מובילים does not offer a registration form. Leader access is granted by the program team, so the page says that and offers a way to ask. A door labelled for one role must not quietly behave like the other. | DONE |
| REQ-M.46 | Signing in lands you on the main view | Every door ends in the same place: דף הבית, not the personal area. Someone who just signed in wants to see the program, not a form about themselves, and the personal area is one click away in the header whenever they want it. Today password login lands correctly while register and Google do not, which is the sort of inconsistency nobody notices until they use all three. | DONE |
| REQ-M.45 | Google is a door here too | המשך עם Google sits on the login and register screens, as it does on the wider platform, because for a 14-year-old it is the difference between joining and giving up on a password field. The link the page renders stays inside `/matazim/`: it goes to our own URL, which hands off to the provider and brings them back into the prefix. RULE-1 is not bent for it, and the visitor never lands on a babook page. | DONE |
| REQ-M.35 | Entry through this door is recorded | A visitor who arrives at a `/matazim` URL is marked as having come in through מט״צים, and signing in through this app's own button stamps it on their מט״צים profile. It answers "did this person find us here, or are they a babook member who wandered over", which is the only way to read the funnel later. | DONE |
| REQ-M.36 | The joining doors wait for the test | כניסת תלמידים is inactive until the visitor has passed the entrance test, and says why rather than simply refusing. **כניסת מובילים is not gated**: the test measures a teenager's commitment, and a teacher confirming students onto a roster has no reason to model a 3D object (Avi, 2026-09-10). | DONE |
| REQ-M.37 | The returning-user door is never gated | התחברות in the header always works. Without it the gate locks out everyone who already passed and came back, because we only learn that they passed after they sign in. The hero doors are for joining; the header is for returning. | DONE |
| REQ-M.38 | The entrance test has a home | מבחן הכניסה is a real page at its own URL, reachable with no account, and it is what the gated door points at. | DONE |
| REQ-M.69 | One door to the staff area | Admin tools live behind a single ניהול entry rather than accumulating one nav item each. Inside it, the target bank and the admin list, and whatever comes next. Only admins see the door, and every page behind it refuses everyone else on its own. | DONE |
| REQ-M.71 | Finding a person, not typing their address | The admin picker searches as you type, on **name or email**, so typing נעמ finds נעמי and a fragment of an address finds its owner. Nobody should have to remember an exact email to grant a role. It never matches on fewer than two characters and never returns everyone, so it cannot be used to walk the user table, and it says who is already an admin instead of offering them as if they were not. | DONE |
| REQ-M.70 | Adding an admin is a screen, not a deploy | An existing admin can grant and revoke adminship from inside מט״צים, by email. Every row says **which kind**: מנהל/ת התוכנית is מט״צים only and is what this screen grants, מנהל/ת האתר is the whole platform and is neither granted nor removed here. A page about who holds power has to answer what kind of power, or it cannot be read without reading the code. It never creates an account: a typo must not conjure one holding the highest role. Nobody can revoke themselves, because the likeliest way to lose every admin is by accident. This does not weaken REQ-M.68: the rule is that adminship is never **self**-served, and a screen you must already be an admin to open is not self-service. | DONE |
| REQ-M.62 | Staff reach the bank from the site | The target bank has a door. *(Narrowed by REQ-M.69: the header carries one ניהול entry and the bank sits one click inside it.)* An entry only admins see. A screen you have to know the URL for is a screen nobody uses, and it is the same class of mistake as a page that says it is closed. Members and visitors never see the entry, and the page itself still refuses them. | DONE |
| REQ-M.63 | A passed test says so, everywhere | Once someone has passed, every invitation to take the test carries a done mark instead of pretending they have not started: the nav, the hero, and every call to action on the public pages. The profile shows עבר. Nobody should be invited twice to something they finished. | DONE |
| REQ-M.64 | The replay control is for staff only | איפוס הודעת הפתיחה exists so the first-time experience can be tested. It is a tool, not a feature, and a member has no reason to reset a notice they already acknowledged. Staff only, hidden **and** refused, because hiding a button is not access control. | DONE |
| REQ-M.61 | And the door says it is open | The page sets expectations and then gets out of the way: what you will do, **what you need** (a computer, a free Tinkercad account, about an hour), what happens when it does not come out right, and what passing opens. It never says the test is closed while the test is open. Saying "you need a computer" belongs on this first screen, because confirming the applicant has one is part of what this gate is for. | DONE |

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
| REQ-M.43 | Where I stand in the program | The profile shows the student's leader and that leader's school, and whether they are already a certified מט״צ. Until `Membership` exists these read as "not yet assigned" rather than being hidden, so the shape of the page is honest about what is coming. | DONE |
| REQ-M.44 | Everything I have learned, anywhere | The profile lists every הדרכה the person has done or is doing **anywhere on babook**, completed and in progress, read live from `Enrollment`, `UserVideoProgress` and `CourseCertificate` and never copied (RULE-3). Learning done before מט״צים existed counts, with no backfill step. | DONE |

### 5.2c מבחן הכניסה

The gate, and the first thing anyone actually does here. It selects and it
onboards at once: passing it means you finished a course, produced a real file,
and therefore have a computer to do it on. **The practical requirement is part
of the point, not a side effect** (Avi, 2026-09-10), so the page says so up
front rather than letting a kid discover it at lesson four on a phone.

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.47 | The course, inside the walls | The nine lessons of babook's `tinkercad` course render in the מט״צים shell. **Read-only**: we never add a lesson to that course or change its project type, because it is live and its own learners would see it, and because מט״צים does not write babook's content. Same lessons, our chrome, their course untouched. | DONE |
| REQ-M.48 | Video and assignment, nothing else | A lesson shows the player and what to do. The transcript and the written summary are not rendered here. Avi, 2026-09-10: this is a doing course, and a wall of text between a teenager and the task is a reason to stop. | DONE |
| REQ-M.49 | Progress written once | Watching writes to `Enrollment` and `UserVideoProgress` through the shared code path, so it counts everywhere and needs no backfill. No parallel progress table (RULE-3). | DONE |
| REQ-M.50 | The final task is ours | A tenth step with no video: a formal dimensioned drawing, a rotatable 3D view of the same object, and the brief in words for anyone who cannot read a drawing. Owned by מט״צים, so the program can change what it asks for without touching a babook course. | DONE |
| REQ-M.51 | One target, assigned and kept | A member is assigned a target the first time they reach the task, and that is the one they are measured against. Shopping for an easier object is not possible. A retry draws a fresh target, which is what makes a downloaded model useless: nothing on the internet matches an object we invented. | DONE |
| REQ-M.52 | Upload and measure | STL upload with a size cap, measured against the assigned target on the five tessellation-proof measures. Tolerances live in config and are deliberately generous: the bar is "you clearly built the thing we showed you", never "you were precise". | DONE |
| REQ-M.53 | No machine rejection | The automatic verdict is **עבר** or **עוד לא**, never נדחה. A miss names the actual number ("הגובה שלך 43 במקום 40") and offers the way back into Tinkercad. Retries are unlimited and are read as commitment, not as a blemish. Every rejection in this program is made by a person. | DONE |
| REQ-M.54 | Passing opens the door | A pass stamps `entrance_test_passed_at` and כניסת תלמידים unlocks. The course certificate is theirs either way, so someone who never passes has still learned Tinkercad and has something to show for it. | DONE |
| REQ-M.55 | Staff curate the bank | Admins see all targets, each with its drawing and its 3D view, and can retire any that are too hard. A retired target is never assigned again, and retiring one never breaks an attempt already measured against it. Litala and Avi decide what a 14-year-old should be asked to build; the generator only proposes. | DONE |

### 5.3 Learning inside the walls

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.12 | המסלול שלי | The member's path drawn as an ordered run of typed milestones, each with a status word, a colour and a date, the current one badged המשימה הנוכחית. Above it, five live cards: overall progress, the next task, the next submission due, the next יום שיא, and any new feedback. Below it, the course in progress with its lesson checklist, submissions with their state, and upcoming events. This screen is the product. | TODO |
| REQ-M.12a | Stage-grouped, gated courses | הקורסים שלי groups courses by stage (יסודות הטכנולוגיה, תלת-ממד, קורסי בחירה, הדרכה ומיומנויות, פרקטיקום), filterable by stage and status. Courses in a stage the member has not reached show a padlock, and the sidebar states the advance rule plainly ("השלימו עוד 2 קורסים כדי לעבור לשלב הבא"). A lock is never a dead end without a reason next to it. | TODO |
| REQ-M.12b | Course cards carry state | Every card shows a progress ring, a status word, and an action that matches the state: התחל, המשך, צפה שוב. | TODO |
| REQ-M.13 | Lessons render in the shell | Opening a lesson keeps the member inside `/matazim/`, in the מט״צים chrome. Video, text, quizzes and practice cells work as they do on babook, because they are the same components, not copies. | TODO |
| REQ-M.14 | Progress written once | Watching and completing writes to `UserVideoProgress`, `Enrollment` and `CourseCertificate` exactly as babook does, through the same code path. No parallel progress table, no divergence. | TODO |
| REQ-M.74 | Progress read once, too | REQ-M.14 keeps writing honest; this keeps reading honest. A roster shows many students at once, which is the inverse shape of babook's own screens and the exact place a second, subtly different definition of "done" gets invented. The cohort reader answers with the same rule babook's `_catalog_progress` uses, and a test asserts the two agree for the same person on the same course. If they ever disagree, one of them is lying to a leader about a teenager. | TODO |
| REQ-M.75 | Everything works on a phone | Avi, 2026-09-10: "make sure everything we develop is adaptive to phone." This is a standing rule over every screen in this product, not a task in one sprint. No horizontal overflow at 390px and no tap target under 24px, enforced by a real browser on every page rather than by looking once. A phone is the default screen for a ninth-grader, so a break here is not a degraded experience, it is the experience. | DONE |
| REQ-M.15 | Reads, never writes program state onto learning | Training figures shown anywhere in מט״צים are live queries. Nothing is copied, mirrored, or cached into program tables. | TODO |

### 5.4 The funnel

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.16 | Apply | Three questions only (grade, why, what have you built). The application is not what assesses them, the entrance test is, so every extra field is only a teenager who does not finish the form. Creates a `Student` row at `applied` plus an `Application`. | DONE |
| REQ-M.17 | Entrance test | A Tinkercad replication task measuring commitment, not skill: the candidate reproduces a given model and uploads it, and the geometry is checked automatically. Retryable, and there is no machine rejection, only "not yet". The automatic check is advice, not a verdict: a school leader reviews the attempt (בדיקת מבחן הכניסה in the brief) and decides. | TODO |
| REQ-M.18 | Acceptance by hand | Admins move `applied` to `in_training`. Selectivity is the product, not an obstacle to it. | TODO |
| REQ-M.19 | Submissions and feedback | The יוצרים stage: the member uploads a deliverable, their מוביל sees it, approves or returns it, and **writes feedback the member can read**. The feedback is the interaction that matters here, not the approve flag. | TODO |
| REQ-M.20 | Certification and certificate | Only program staff grant מדריך status, and doing so produces a printable certificate. It unlocks nothing technical and credits everything already done, retroactively. | TODO |
| REQ-M.21 | Every transition logged | `StatusLog` records who, when, from, to, and note. Append-only. Revocation is a transition like any other. | TODO |
| REQ-M.31 | The student chooses their מוביל | From the brief: a student picks the leader who will review their work. With `School` gone this is one relation rather than two, `Student.leader`, which is both who sees them and who reads their submissions. Simpler, and it still answers Litala's ask exactly. A leader can be swapped, and the change is logged. | TODO |
| REQ-M.32 | פרקטיקום | The מדריכים stage, the actual teaching, is visible to the member, to their מוביל, and to program staff: what they are running, when, and how far through. It is both a course stage (there are courses that prepare for it) and a tracked activity. Recorded as the מט״צ's own declared activity, never as data about the children (REQ-M.29). | TODO |
| REQ-M.33 | Notifications | A bell and a message icon in the member header, and the events that feed them: feedback received, a submission approved or returned, a deadline approaching, a יום שיא announced, a stage unlocked. A new piece of feedback surfaces on המסלול שלי without the member going looking for it. | TODO |
| REQ-M.34 | Deadlines and the calendar | Milestones and events carry dates, the personal area shows what is close, and לוח הזמנים shows the whole year. | TODO |

### 5.5 Admins and leaders

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.22 | Scope is the data | A leader sees exactly their own students, and this is a property of the `Student.leader` FK rather than a rule anyone remembers: the query cannot reach anyone else's. Admins see everyone. One function answers this for every screen (§4.4). | DONE |
| REQ-M.23 | Roster | Leaders confirm students onto their roster, sort them into classes, and see each one's stage and training progress. Nothing about any child they teach, ever (REQ-M.29). | TODO |
| REQ-M.24 | Cohort view and reporting | Admins see the funnel by stage and by leader, grouped by `school_name` for the school-level report Litala's brief asks for, and can export it. This is her screen. | TODO |
| REQ-M.25 | Leader management | Assign a leader, rotate their join code, deactivate them. Admins only, and it is the thing an admin exists to do. | DONE |
| REQ-M.67 | Deactivating a leader destroys nothing | A deactivated leader stops appearing in the join list, stops taking new students, and loses the leader view. Their existing students keep pointing at them, so no roster is lost and no history disappears; an admin moves them deliberately. Same principle as retiring a target. | DONE |
| REQ-M.68 | Who is an admin | Adminship is granted here and seeded in production, not self-served: there is no screen that makes someone an admin, because the first one could never use it. Two ways in, and both need someone who already has the keys: `manage.py matazim_admins` reads `MATAZIM_ADMINS` on every deploy, and Django's admin, which only a site superuser can reach, allows flipping it by hand. Django's admin is babook's plumbing and is not a מט״צים surface, so nothing is bent by it being the escape hatch. | DONE |

### 5.6 Community and recognition

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.26 | Cohort feed | Announcements and posts, inside the walls. | TODO |
| REQ-M.27 | ימי שיא | Program events with dates, locations, and which leaders or classes they are for. | TODO |
| REQ-M.28 | The status is visible | Certification shows inside מט״צים and on anything printed or presented. Whether it also shows on public babook surfaces is Q4 below, still open. | TODO |

### 5.7 Privacy (non-negotiable)

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.29 | One tracked population | Nothing in this product creates, stores, or infers a record about a child. The kids a מט״צ teaches are not users, not members, not rows. Teaching is recorded as the מט״צ's own declared activity. | TODO |
| REQ-M.30 | Minors' data stays minimal | The people in this system are teenagers in כיתה ט'. We hold what the program needs to run and nothing more, and it is not exposed outside their own leader and the admins. | TODO |
| REQ-M.30a | Nothing about a minor is public by default | The public gallery names a school, never a student. A photo avatar is opt-in; initials are the default. Publishing a project takes the member's consent and a staff decision, and either can be withdrawn later. | WIP |

## 6. Open questions

| # | Question | Why it matters |
|---|---|---|
| Q4 | Does the מט״צ badge appear on public babook surfaces (profile, community, class pages)? | Chapter 10 argued yes, on the grounds that invisible status is not status. Full separation argues no. Not blocking: it only affects REQ-M.28. |
| Q5 | Litala's sign-off on the core change. Note her brief asks for **הקורסים שלי** as a site section, so she expects the site to *hold* the learning, not merely reflect it. The autonomy decision now gives her exactly that, which likely closes this rather than blocking it. Confirm with her. | Was blocking everything past the entrance funnel. Probably resolved. |
| Q6 | Production already has the old tables and, possibly, real rows. Confirm nobody has applied before we drop them. | Blocks the retirement migration in SPR-M.1. |
| Q8 | "פתיחת תכנים ומשימות" by program staff: do they get an authoring surface inside מט״צים, or do they author in babook's studio and only publish here? | An authoring UI inside the walls is a large piece of work. Authoring in the studio is free but means Avi and Litala cross into babook, which members never do. |
| Q9 | Terminology: her brief says תלמידים and מובילים, our docs say מט״צים and מובילי בית ספר. | Cosmetic but pervasive; settle before SPR-M.2 writes the copy. |
| Q13 | **Who grants certification.** Spec §5 has it granted by hand, by Avi and Naomi. | The one part of Q10 that was real. Hand-granting works for forty people and is physically impossible for twelve hundred, where the authority has to move down to leaders. This is a policy and a permission change, not a screen. Not blocking SPR-M.8 or M.9: it is one requirement to rewrite, and until it is rewritten hand-granting stands. |
| Q14 | **Is a class load-bearing?** At forty across the network a leader has one or two students per school and `school_name` *is* the group, so nobody needs to create a class. At twelve hundred a leader carries about forty-five and has to split them. | Decides whether class creation belongs in a leader's first run. Defaulted rather than blocked: a class is offered and never required, which is correct in the small world and merely incomplete in the large one. Revisit the day any single leader passes about twenty students. |
| Q11 | The public gallery publishes minors' work. Who consents, and does a parent sign anything? | Blocks REQ-M.5e. My default in the spec is opt-in by the member plus a staff decision, both withdrawable, but consent for a ninth-grader may need a parent. |
| Q12 | The public path shows four stages (לומדים, יוצרים, מדריכים, משפיעים) while the program has five, with מתמיינים first. Deliberate? | Cosmetic if deliberate, confusing if not. My reading is deliberate: מתמיינים is the entrance test, which has its own CTA. |

**Closed:** Q1 start clean, new Django app (2026-09-09). Q2 מט״צים-branded auth
over shared accounts (2026-09-09). Q3 courses render inside the shell
(2026-09-09). Q7 brand direction, settled by Litala's three prototype screens
(2026-09-09), read in `prototype/README.md` and summarised in section 3.2.
Q10 scale (2026-09-11): the wrong question. The data model is scale-invariant,
so nothing about the schema or the roster screens hangs on the cohort size.
Build for the larger number wherever it is cheap and reversible (search, paging,
and an admin who lands on counts rather than on a list of every student), all of
which reads correctly at forty and is the only usable option at twelve hundred.
The two real questions inside it are now Q13 and Q14. The 1,250 / 120 / 28
figures came from Litala's prototype stats band, which Avi had stripped off the
home page as invented numbers.

## 7. Reference

Superseded material, kept for history: `docs/main_spec.md` Chapter 10,
`docs/backlog.md` EPIC-10, the site brief from Litala Aviv of 2026-08-03, and
the scoping conversation of 2026-08-08.
