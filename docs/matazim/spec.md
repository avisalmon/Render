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

  **One narrow exception, added 2026-09-11: the legal pages may name the
  operator and give a working contact address.** A privacy policy has to say
  who actually holds the data and how to reach them, and `avi.salmon@gmail.com`
  is the inbox that is actually read. Inventing a מט״צים-branded address that nobody
  reads would be a dead contact on the one page where the contact is the point,
  and concealing the operator to preserve a branding illusion is not a thing a
  privacy policy is allowed to do. So RULE-1 keeps its grip on *navigation*, a
  member still cannot click their way out of `/matazim/`, and gives way on
  *disclosure*, only on `privacy.html` and `terms.html`. The guard enforces
  exactly that distinction rather than searching for a word.
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

### 4.3 Five roles, and what each of them is allowed to be confused with

Settled with Avi on 2026-09-11, after "admin" turned out to point at two
different people depending on who was speaking. The words below are the only
ones we use, in conversation and in code.

| We say | Hebrew on screen | How it is known | Sees |
|---|---|---|---|
| **root** | מנהל/ת מערכת | `User.is_superuser` | Everything, every app, every program. Cuts across tenancy. |
| **program manager** | מנהל/ת התוכנית | `MemberProfile.is_program_manager` | Their own leaders, and those leaders' students. One program, one world. |
| **leader** | מוביל/ה | Having an approved `Leader` row | Their own students, and nothing else. |
| **candidate** | מועמד/ת למוביל | A `Leader` row not yet approved | Nothing yet. They are waiting on a person. |
| **student** | מט״צ | Having a `Student` row | Themselves. |
| **visitor** | — | None of the above | The public pages. |

**Two words are retired**, because both caused real confusion and one of them
nearly caused a wrong grant of superuser:

- **"admin"** on its own. Avi runs several applications, so an unqualified
  "admin" reads as root. It is always **program manager** now.
- **"site admin"**. Avi used it for נעמי; the screen used it for Avi. It pointed
  at two different people depending on who was speaking.

**No role column, and `is_program_manager` is not one.** A role must have
exactly one source. A `role` field on `Student` would compete with the `leader`
FK and the two could disagree, which is how one leader ends up seeing another's
students. `is_program_manager` competes with nothing.

### 4.4 Tenancy: the worlds do not touch

Avi, 2026-09-11: several institutions will adopt this platform. A chain of
schools here, a different organisation there. **Each has its own program
manager, its own leaders, its own students, and they are separate worlds that
happen to share a database, a course engine and a login screen.**

This is the leader rule moved up one floor. A leader cannot reach another
leader's students; a program manager cannot reach another program manager's
leaders. Same mechanism, because it is the only one that holds: scope is a
property of the data, not a check somebody remembers to write.

```
root ──────────── sees across every world
 └── program manager ── owns leaders        (Leader.program_manager)
      └── leader ────── owns students       (Student.leader)
           └── student ─ owns themselves
```

**Ownership is by person, not by an organisation record.** `Leader.program_manager`
is a foreign key to a `User` and there is no `Organisation` table, consistent
with dropping `Program` and `School` in §4.8. The known cost, recorded here so
nobody rediscovers it in a panic: an institution therefore has exactly **one**
program manager, and if she leaves, her leaders need reassigning by root. The
day two people must share one world, that is when the organisation record earns
its place, and not before.

### 4.4a The whole permission model

```python
def visible_leaders(user):
    if user.is_superuser:
        return Leader.objects.all()                      # root crosses worlds
    if is_program_manager(user):
        return Leader.objects.filter(program_manager=user)
    if leader := leader_of(user):
        return Leader.objects.filter(pk=leader.pk)
    return Leader.objects.none()


def visible_students(user):
    if user.is_superuser:
        return Student.objects.all()
    if is_program_manager(user):
        # Their world, reached through the leaders they own, plus the students
        # nobody has claimed yet. That second clause is the Q15 seam: an
        # unclaimed student has no leader and therefore no world, and dropping
        # them would make a teenager who passed the entrance test invisible to
        # the only person who could help. With one program manager that is the
        # worse failure; with two, it costs one manager seeing a name bound for
        # the other's institution.
        return Student.objects.filter(
            Q(leader__program_manager=user) | Q(leader__isnull=True)
        )
    if leader := leader_of(user):
        return Student.objects.filter(leader=leader)
    return Student.objects.filter(user=user)
```

Every screen asks one of these two questions and then works with what comes
back. Nobody is refused by a check; they are refused by a queryset that never
contained the row.

**The open door needs scoping too.** `joinable_leaders()` currently lists every
active leader on the platform, which under tenancy would show one institution's
staff to another institution's applicants. A student reaching the open door
without an invite has not yet declared which world they are in, and that is an
unsolved question rather than an oversight (Q15).

### 4.4b How someone becomes a leader

Three doors, described by Avi on 2026-09-11. All three end at the same place: a
**person presses approve**. Nothing here makes a leader automatically, because a
leader can see named minors' progress and that is not a role to hand out on the
strength of holding a URL.

```
LeaderInvite   FK → program_manager    kind (personal | open)
                                       token, label, email
                                       used_at, used_by, revoked_at
                                       expires_at
```

**1. They already have an account.** The program manager searches by name, email
or a fragment of either, clicks the person, and approves. They receive an email
saying they have been made a leader, by whom, and what to do next.

**2. They do not.** She generates a **personal invite**: one token yielding a
link, a QR and an optional email if she has an address. Two properties Avi was
specific about:

- **The label is a label.** She names who it is for, and she may get it wrong.
  The real name arrives when they register and set it themselves. Nothing
  validates the label and nothing depends on it.
- **Single use.** It may be forwarded, and that is tolerated, but the moment
  anyone registers through it the token is spent and the link is dead.

**3. A whole team at once.** An **open invite** is the same three artefacts with
no person attached, handed to a staff room. It is reusable by design, and this
is exactly why it cannot confer leadership: anyone holding it would be a leader.
Whoever uses it becomes a **candidate**, appearing in her list as "invited,
signed up, waiting on you", and she presses approve exactly as she would for
someone she found by search.

So `Leader` gains two fields: `program_manager` (who owns them) and an approval
marker distinguishing a candidate from a leader. An unapproved `Leader` row
grants nothing at all: `leader_of()` must not return it, or a candidate would
have a roster before anyone said yes.

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

### 4.9 Two kinds of leader, and what to call them in English

Hebrew keeps these apart without effort and English does not, which has already
cost us clarity in this document.

| In the product | In English, here and in code | Who |
|---|---|---|
| מוביל / מובילה | **leader** | The adult. Has classes, has students, approves and certifies. |
| מט״צ (plural מט״צים) | **mataz** (plural **matazim**) | The teenager. A certified mataz is what the whole program produces. |

Avi, 2026-09-11: "קשה לומר מט״צ באנגלית, so I will now refer to young leader as
mataz." Note that *young leader* and *mataz* are the same thing, so a sentence
with both "leader" and "young leader" in it is a sentence about two different
people and is worth rewriting. The Hebrew interface is unaffected: it says
מוביל and מט״צ and always did.

### 4.10 Privacy, consent, and the law

Written 2026-09-11 at Avi's request, after auditing what this product actually
holds and who can actually reach it. Two of the findings below are live defects,
not policy gaps.

**None of this is legal advice.** It is the common practice and the plain reading
of the obligations, written so a lawyer can be handed something concrete rather
than a blank page. The parts that turn on judgement are marked.

#### Who the data subjects are

Ninth-graders. Thirteen to fifteen years old. That single fact governs
everything else: the appetite for risk is not the same as for an adult
professional learning Django on babook, and the consent of a fourteen-year-old
is not, on its own, the consent the law is looking for.

#### What we hold about them

| Data | Where | Why we have it |
|---|---|---|
| Email, display name | `User`, `app.UserProfile` | The account. Email is the login. |
| Entrance test pass, timestamp | `MemberProfile` | The first gate. |
| Uploaded 3D model, measurements, issues | `EntranceAttempt` | Scoring the entrance test. **Their own work product.** |
| Which leader, which classes, school name | `Student`, `StudyClass` | The program's structure. |
| Stage, certification, who granted it | `Student` | The funnel. |
| Every lesson watched, quiz answer, certificate | babook's tables | The learning itself (RULE-3). |

#### The legal frame

Israeli law, since these are Israeli minors in Israeli schools.

- **חוק הגנת הפרטיות, התשמ״א-1981**, as amended by **תיקון 13**, in force since
  August 2025. The amendment sharpened data-subject rights, added breach
  notification, and attached real administrative fines. It also narrowed database
  *registration*, and on the current reading this database does not require it:
  registration now bites mainly on public bodies, data brokers, and sensitive
  data at large scale.
- **§11, חובת יידוע.** The duty to tell a person, *at the point of collection*,
  whether they are obliged to give the data, what it will be used for, and to
  whom it will be handed. This is the clearest single obligation we are failing
  today, and it is failing at the exact screen where a fourteen-year-old types
  their email.
- **תקנות הגנת הפרטיות (אבטחת מידע), התשע״ז-2017.** Security duties scaled to
  the database. Our headcount is small, so the basic level is the plain reading,
  but the regulations care about the *nature* of the data too, and data about
  minors is handled cautiously by the Privacy Protection Authority. Treating this
  as the medium level costs us very little and is the defensible choice.
- **A DPO (ממונה על הגנת הפרטיות) is not required** at this scale on the current
  reading. Worth revisiting if the program ever reaches the numbers Litala's
  prototype claimed.
- Schools bring their own layer (חוזר מנכ״ל on pupils' data), which is a reason
  to record consent rather than assume the school has handled it.

#### The separation paradox

RULE-1 forbids any outbound link from `templates/matazim/` to babook. Babook has
a privacy policy, terms, and a cookie banner. **A מט״צים member cannot reach any
of them**, and would not be covered by them if they could: babook's policy
describes a person learning on their own, and says nothing about a teacher being
shown a named minor's progress.

So the separation contract, which exists for good reasons, manufactured a
compliance gap. מט״צים needs its own legal surface, inside the walls, written
for this product. That is not a workaround for RULE-1, it is RULE-1 working
correctly: an autonomous product carries its own terms.

#### Cookies: a notice, not a banner

מט״צים sets exactly two cookies, `sessionid` and `csrftoken`, both strictly
necessary to log in and to submit a form safely. There is **no analytics, no
tag manager, and no third-party script anywhere under `/matazim/`** (checked,
2026-09-11), which is a genuinely better starting position than most sites.

Strictly necessary cookies require **disclosure, not opt-in**. So the right
answer here is a clear cookie section in the policy and no consent banner.
Building a banner that asks permission for cookies we would set regardless is
both dishonest and worse for a teenager on a phone. The day anything analytic or
third-party is added to this product, that judgement flips and a real consent
gate is owed.

#### Need to know, by role

Scope is already a property of the data (§4.4), which is most of the work. What
follows is the *narrowing* question: not "can they reach it" but "should they".

| Role | Sees | Judgement |
|---|---|---|
| student | Themselves | Correct. |
| leader | Their own students: name, email, track progress, entrance status, stage | Justified. A teacher who cannot identify their own pupil cannot teach them. Email is the identifier we have. |
| leader | Any student who is not theirs | Impossible by construction. Correct. |
| admin | Every student, every leader | Justified for running the program and for support, and it is three named people. |
| root | Everything on the platform, via Django admin | Unavoidable, and the reason the role is granted as `MemberProfile.is_program_manager` and never as `is_superuser`. |
| anyone | A leader's name and school, from an invite link | Acceptable. It is what makes the invite legible, and it is adult staff data. |

The one thing a leader does **not** get, and must never get, is anything about
the children their mataz teaches (REQ-M.29). That population does not exist in
this system.

#### Reuse babook's infrastructure

Avi, 2026-09-11, mid-sprint. The charter already says babook is the engine room,
and that applies to privacy machinery as much as to the course engine. What it
does **not** extend to is babook's privacy *pages*: RULE-1 means a member cannot
reach them, and they describe someone learning alone rather than a teacher being
shown a named minor's progress. Shared plumbing, separate promises.

| Need | Reused from babook | Rather than |
|---|---|---|
| Account deletion | `app.views.delete_account` (REQ-7.2.10). `User.delete()` cascades into `MemberProfile`, `Student` and `EntranceAttempt`. | A second deletion path that would drift from the first |
| Retention jobs | The `purge_*` management-command pattern already established by `purge_security_events` and `purge_unconfirmed_newsletter` | Inventing a scheduler |
| Contact for requests | `avi.salmon@gmail.com` (Avi, 2026-09-11), the inbox that is actually read | A role address nobody monitors |
| Accounts, sessions, CSRF | Django's, through babook's settings | Anything of our own |

Reuse found a defect on its first reading, which is the argument for it. Django
has not deleted files on row deletion since 1.3, so `delete_account` removed
every row belonging to a member and left their uploaded model on the disk: the
one artefact that is unmistakably theirs. A `post_delete` receiver on
`EntranceAttempt` now closes it.

#### Findings from the audit

| # | Finding | Severity |
|---|---|---|
| P1 | `/matazim/leader/<id>/qr.png` has no authentication and no authorization. The id is a sequential integer, so the endpoint can be walked to harvest **every leader's join code**, and a join code is a bearer credential: REQ-M.9 attaches the holder to that leader with no confirmation. | **High** |
| P2 | Minors' entrance-test uploads are written to `MEDIA_ROOT` and served from `/media/` with no authentication, under the uploaded file's own name. School work is routinely named after the pupil, so this publishes a minor's name and their work to anyone who guesses the path. | **High** |
| P3 | No privacy policy, no terms, and no cookie notice anywhere under `/matazim/`, and RULE-1 forbids linking to babook's. §11 יידוע is not met at the point of collection. | **High** |
| P4 | No parental consent anywhere, for a programme of fourteen-year-olds. Open as Q11 since day one. | Medium |
| P5 | No retention limit and no deletion or export path. Nothing in the product can answer "show me what you hold about me" or "delete it". | Medium |
| P6 | No record of a certification being revoked or a roster being read. Granting is recorded (REQ-M.78); nothing else is. | Low |

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
| REQ-M.69 | One door to the staff area | Program-manager tools live behind a single ניהול entry rather than accumulating one nav item each. Inside it, the target bank and the admin list, and whatever comes next. Only admins see the door, and every page behind it refuses everyone else on its own. | DONE |
| REQ-M.71 | Finding a person, not typing their address | The people picker searches as you type, on **name or email**, so typing נעמ finds נעמי and a fragment of an address finds its owner. Nobody should have to remember an exact email to grant a role. It never matches on fewer than two characters and never returns everyone, so it cannot be used to walk the user table, and it says who is already an admin instead of offering them as if they were not. | DONE |
| REQ-M.70 | Adding a program manager is a screen, not a deploy | An existing program manager can grant and revoke the role from inside מט״צים, by email. Every row says **which kind**: מנהל/ת התוכנית is מט״צים only and is what this screen grants, מנהל/ת מערכת is the whole platform and is neither granted nor removed here. A page about who holds power has to answer what kind of power, or it cannot be read without reading the code. It never creates an account: a typo must not conjure one holding the highest role. Nobody can revoke themselves, because the likeliest way to lose every admin is by accident. This does not weaken REQ-M.68: the rule is that the role is never **self**-served, and a screen you must already be an admin to open is not self-service. | DONE |
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
| REQ-M.55 | Staff curate the bank | Program managers see all targets, each with its drawing and its 3D view, and can retire any that are too hard. A retired target is never assigned again, and retiring one never breaks an attempt already measured against it. Litala and Avi decide what a 14-year-old should be asked to build; the generator only proposes. | DONE |

### 5.3 Learning inside the walls

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.12 | המסלול שלי | The member's path drawn as an ordered run of typed milestones, each with a status word, a colour and a date, the current one badged המשימה הנוכחית. Above it, five live cards: overall progress, the next task, the next submission due, the next יום שיא, and any new feedback. Below it, the course in progress with its lesson checklist, submissions with their state, and upcoming events. This screen is the product. | TODO |
| REQ-M.12a | Stage-grouped, gated courses | הקורסים שלי groups courses by stage (יסודות הטכנולוגיה, תלת-ממד, קורסי בחירה, הדרכה ומיומנויות, פרקטיקום), filterable by stage and status. Courses in a stage the member has not reached show a padlock, and the sidebar states the advance rule plainly ("השלימו עוד 2 קורסים כדי לעבור לשלב הבא"). A lock is never a dead end without a reason next to it. | TODO |
| REQ-M.12b | Course cards carry state | Every card shows a progress ring, a status word, and an action that matches the state: התחל, המשך, צפה שוב. | TODO |
| REQ-M.13 | Lessons render in the shell | Opening a lesson keeps the member inside `/matazim/`, in the מט״צים chrome. Video, text, quizzes and practice cells work as they do on babook, because they are the same components, not copies. | TODO |
| REQ-M.14 | Progress written once | Watching and completing writes to `UserVideoProgress`, `Enrollment` and `CourseCertificate` exactly as babook does, through the same code path. No parallel progress table, no divergence. | TODO |
| REQ-M.74 | Progress read once, too | REQ-M.14 keeps writing honest; this keeps reading honest. A roster shows many students at once, which is the inverse shape of babook's own screens and the exact place a second, subtly different definition of "done" gets invented. The cohort reader answers with the same rule babook's `_catalog_progress` uses, and a test asserts the two agree for the same person on the same course. If they ever disagree, one of them is lying to a leader about a teenager. | DONE |
| REQ-M.75 | Everything works on a phone | Avi, 2026-09-10: "make sure everything we develop is adaptive to phone." This is a standing rule over every screen in this product, not a task in one sprint. No horizontal overflow at 390px and no tap target under 24px, enforced by a real browser on every page rather than by looking once. A phone is the default screen for a ninth-grader, so a break here is not a degraded experience, it is the experience. | DONE |
| REQ-M.76 | What makes a מט״צ | Three things, and all three are required. One: the entrance test is passed (`MemberProfile.entrance_test_passed_at`). Two: babook has issued a `CourseCertificate` for **both** `scratch` and `scratch-advanced`. Three: their leader has approved them by hand. The first two are facts babook already owns and מט״צים only reads, so nothing here re-implements what a certificate means (RULE-3). A student may complete any number of further courses and that is encouraged, but nothing substitutes for the two. | DONE |
| REQ-M.77 | The gate is a gate, not advice | A leader **cannot** certify a student who has not met the two automatic prerequisites. The action is absent, not merely discouraged, and the server refuses it independently of what the page offered, because a button that is only hidden is a button that gets posted anyway. The screen states which of the three is outstanding and links to it, so an ineligible student is an explained state rather than a missing button. | DONE |
| REQ-M.78 | The judgment is human | Meeting the prerequisites earns a student the right to be considered, never the status itself. The leader who has taught them decides, and the system never promotes anyone automatically on the strength of a certificate count. This is the opposite of the entrance test, where the machine's check is advice and there is no machine rejection; here the machine's check is binding and only the machine's *refusal* is final. Certification records who granted it and when, and is revocable by the same hand. | DONE |
| REQ-M.15 | Reads, never writes program state onto learning | Training figures shown anywhere in מט״צים are live queries. Nothing is copied, mirrored, or cached into program tables. | TODO |

### 5.4 The funnel

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.16 | Apply | Three questions only (grade, why, what have you built). The application is not what assesses them, the entrance test is, so every extra field is only a teenager who does not finish the form. Creates a `Student` row at `applied` plus an `Application`. | DONE |
| REQ-M.17 | Entrance test | A Tinkercad replication task measuring commitment, not skill: the candidate reproduces a given model and uploads it, and the geometry is checked automatically. Retryable, and there is no machine rejection, only "not yet". The automatic check is advice, not a verdict: a school leader reviews the attempt (בדיקת מבחן הכניסה in the brief) and decides. | TODO |
| REQ-M.18 | Acceptance by hand | The program manager moves `applied` to `in_training`. Selectivity is the product, not an obstacle to it. | TODO |
| REQ-M.19 | Submissions and feedback | The יוצרים stage: the member uploads a deliverable, their מוביל sees it, approves or returns it, and **writes feedback the member can read**. The feedback is the interaction that matters here, not the approve flag. | TODO |
| REQ-M.20 | Certification and certificate | Only program staff grant מדריך status, and doing so produces a printable certificate. It unlocks nothing technical and credits everything already done, retroactively. | TODO |
| REQ-M.21 | Every transition logged | `StatusLog` records who, when, from, to, and note. Append-only. Revocation is a transition like any other. | TODO |
| REQ-M.31 | The student chooses their מוביל | From the brief: a student picks the leader who will review their work. With `School` gone this is one relation rather than two, `Student.leader`, which is both who sees them and who reads their submissions. Simpler, and it still answers Litala's ask exactly. A leader can be swapped, and the change is logged. | TODO |
| REQ-M.32 | פרקטיקום | The מדריכים stage, the actual teaching, is visible to the member, to their מוביל, and to program staff: what they are running, when, and how far through. It is both a course stage (there are courses that prepare for it) and a tracked activity. Recorded as the מט״צ's own declared activity, never as data about the children (REQ-M.29). | TODO |
| REQ-M.33 | Notifications | A bell and a message icon in the member header, and the events that feed them: feedback received, a submission approved or returned, a deadline approaching, a יום שיא announced, a stage unlocked. A new piece of feedback surfaces on המסלול שלי without the member going looking for it. | TODO |
| REQ-M.34 | Deadlines and the calendar | Milestones and events carry dates, the personal area shows what is close, and לוח הזמנים shows the whole year. | TODO |

### 5.5 Program managers and leaders

| REQ-ID | Title | Expectation | Status |
|---|---|---|---|
| REQ-M.22 | Scope is the data | A leader sees exactly their own students, and this is a property of the `Student.leader` FK rather than a rule anyone remembers: the query cannot reach anyone else's. **Amended 2026-09-11 by REQ-M.88:** a program manager does *not* see everyone, only their own leaders and those leaders' students. Root crosses every world. Two functions answer this for every screen (§4.4a). | DONE |
| REQ-M.23 | Roster | Leaders confirm students onto their roster, sort them into classes, and see each one's stage and training progress. Nothing about any child they teach, ever (REQ-M.29). | DONE |
| REQ-M.24 | Cohort view and reporting | A program manager sees the funnel by stage and by leader **within their own world** (REQ-M.88), grouped by `school_name` for the school-level report Litala's brief asks for, and can export it. Root sees it across worlds. | TODO |
| REQ-M.25 | Leader management | Assign a leader, rotate their join code, deactivate them. Program managers only, and it is the thing the role exists to do. **Widened by REQ-M.90 to M.93:** assigning is now three doors (search, personal invite, open invite) and every one of them ends at a person pressing approve. | DONE |
| REQ-M.67 | Deactivating a leader destroys nothing | A deactivated leader stops appearing in the join list, stops taking new students, and loses the leader view. Their existing students keep pointing at them, so no roster is lost and no history disappears; an admin moves them deliberately. Same principle as retiring a target. | DONE |
| REQ-M.88 | A leader belongs to a program manager | `Leader.program_manager` is who owns them, and it is what makes two institutions two worlds rather than one shared list. A program manager sees their own leaders and those leaders' students; another program manager's are not merely hidden but unreachable, because the queryset never contained them. Root crosses every world. Supersedes the old "admins see everyone". | DONE |
| REQ-M.89 | The program manager has a standing door | Leader management is a named entry she sees on every page, not a tool buried one click inside ניהול. It is the thing her role exists to do, and REQ-M.62 already taught us that a screen you must know the URL for is a screen nobody uses. | DONE |
| REQ-M.90 | Assigning someone who already has an account | Free-text search over name, email, or a fragment of either. She clicks a person and approves them, and that approval is the whole act: no form, no second step. They are emailed that they are now a leader, under whom, and where to go next. A role granted in silence is a role nobody knows they have. | DONE |
| REQ-M.91 | A personal invite for someone with no account | One token, three artefacts: a link, a QR, and an optional email if she has an address. She labels it with who it is for, and **the label is a label**: she may be wrong, and the real name arrives when they register. **Single use** — it may be forwarded, which is tolerated, but the first registration spends it and the link dies. | DONE |
| REQ-M.92 | An open invite for a whole staff room | The same three artefacts with nobody named, reusable by design. Precisely because anyone holding it could use it, it confers nothing: whoever registers through it becomes a **candidate**. | DONE |
| REQ-M.93 | Approval is always a person | A candidate has no students, no roster and no leader view. They wait in the program manager's list marked as waiting, and she presses approve, the same act as approving someone found by search. Same shape as REQ-M.78 and REQ-M.87: the machine proposes and refuses, a person grants. An unapproved `Leader` row must grant nothing, or a candidate has a roster before anyone said yes. | DONE |
| REQ-M.94 | The leader list reads in one line | Her leaders, one line each, light enough to scan: name, school, how many students, how many certified, and whether anything is waiting on her. Enough to answer "who needs me today" without opening anything. Candidates sit in the same list, marked, because a separate screen for them is a screen she forgets to visit. | DONE |
| REQ-M.95 | One leader, in full | That leader's details and statistics, and their students listed underneath. Not a second roster: the leader's own roster screen from SPR-M.8, read through the program manager's scope, because a duplicate is a thing that drifts. A student detail page hangs off it, defined later. | DONE |
| REQ-M.68 | Who is an admin | Program-manager rights are granted here and seeded in production, never self-served: there is no screen that makes someone an admin, because the first one could never use it. Two ways in, and both need someone who already has the keys: `manage.py matazim_admins` reads `MATAZIM_ADMINS` on every deploy, and Django's admin, which only a site superuser can reach, allows flipping it by hand. Django's admin is babook's plumbing and is not a מט״צים surface, so nothing is bent by it being the escape hatch. | DONE |

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
| REQ-M.30 | Minors' data stays minimal | The people in this system are teenagers in כיתה ט'. We hold what the program needs to run and nothing more, and it is not exposed outside their own leader and their own program manager. | TODO |
| REQ-M.30a | Nothing about a minor is public by default | The public gallery names a school, never a student. A photo avatar is opt-in; initials are the default. Publishing a project takes the member's consent and a staff decision, and either can be withdrawn later. | WIP |
| REQ-M.79 | An invite link is not public | The QR endpoint authenticates and authorises like every other leader screen: the leader themselves, or an admin. A sequential integer id must not be walkable into a harvest of join codes, because a join code attaches its holder to that leader with no confirmation (REQ-M.9). Finding P1. | DONE |
| REQ-M.80 | A minor's work is not served from a public directory | Entrance-test uploads leave `MEDIA_ROOT` and are served only through a view that checks who is asking: the member themselves, their leader, or an admin. Stored under an unguessable name, never the name of the file a teenager chose, because school work is routinely named after the pupil. Finding P2. | DONE |
| REQ-M.81 | מט״צים carries its own terms | A privacy policy and terms of use, inside the walls, in our own shell, written for this product and these people. Not a link to babook's, which RULE-1 forbids and which does not describe this processing anyway. Reachable from the footer of every page and from the registration screen. Finding P3. | DONE |
| REQ-M.82 | Told before they type | §11 חובת יידוע, met where it is owed: at the point of collection. The registration screen says plainly what we collect, what it is for, and **that their leader will see their name, their progress and their status**. That last clause is the one a teenager would actually want to know and the one a generic policy always buries. Finding P3. | DONE |
| REQ-M.83 | Cookies disclosed, not negotiated | The policy names the two cookies this product sets and says both are strictly necessary. No consent banner, because there is nothing here to consent to: no analytics, no third-party script, nothing that would be set for our benefit rather than the member's. If that ever changes, this requirement inverts and a real gate is owed before the script ships. Finding P3. | DONE |
| REQ-M.84 | A parent says yes | Registration asks for year of birth, and anyone under 18 gives a parent's or guardian's name, email and affirmative consent, recorded with a timestamp. A school that has collected consent on paper is recorded the same way by an admin, rather than assumed. Nobody joins a leader without it. Finding P4, closes Q11. | DONE |
| REQ-M.85 | See it, take it, or have it deleted | Inside the profile: everything we hold about this person on one screen, an export of it, and a deletion request that reaches an admin. Deletion removes the מט״צים record and the uploaded work; the babook account is the member's own and is not silently destroyed from here. Finding P5. | DONE |
| REQ-M.86 | Nothing is kept forever | A stated retention period for each kind of data, and a command that enforces it rather than a sentence that promises it. Entrance attempts that never passed, and the files attached to them, are the shortest-lived thing here: they are a failed audition, not a record worth keeping for years. Finding P5. | DONE |
| REQ-M.87 | A person deletes, the machine only ever asks | Retention runs behind a review, not on a timer. A staff screen lists exactly what is due and who it belongs to, an admin approves, and the run is recorded with who approved it, when, and how many rows went. Nothing in this product deletes a member's data unattended. This is the same shape as REQ-M.78 and REQ-M.55: the machine refuses or proposes, a person decides, and the decision has a name on it. The counterweight is that a job needing a human is a job that does not run when the human is busy, so the staff area carries a standing count of what is overdue rather than waiting to be asked. | DONE |

## 6. Open questions

| # | Question | Why it matters |
|---|---|---|
| Q4 | Does the מט״צ badge appear on public babook surfaces (profile, community, class pages)? | Chapter 10 argued yes, on the grounds that invisible status is not status. Full separation argues no. Not blocking: it only affects REQ-M.28. |
| Q5 | Litala's sign-off on the core change. Note her brief asks for **הקורסים שלי** as a site section, so she expects the site to *hold* the learning, not merely reflect it. The autonomy decision now gives her exactly that, which likely closes this rather than blocking it. Confirm with her. | Was blocking everything past the entrance funnel. Probably resolved. |
| Q6 | Production already has the old tables and, possibly, real rows. Confirm nobody has applied before we drop them. | Blocks the retirement migration in SPR-M.1. |
| Q8 | "פתיחת תכנים ומשימות" by program staff: do they get an authoring surface inside מט״צים, or do they author in babook's studio and only publish here? | An authoring UI inside the walls is a large piece of work. Authoring in the studio is free but means Avi and Litala cross into babook, which members never do. |
| Q9 | Terminology: her brief says תלמידים and מובילים, our docs say מט״צים and מובילי בית ספר. **Also קורסים vs הדרכות**, noted 2026-09-11: babook's standing brand rule is הדרכות and never קורסים, but Litala's information architecture names the section הקורסים שלי and REQ-M.5 and REQ-M.59 encode that. The product currently does both, and not at random: **הקורסים is the section name, הדרכות is the body copy**. That is defensible, and it is also exactly the kind of split that decays into randomness once four people are writing screens. | Cosmetic but pervasive. The section-name-versus-body-copy split needs to be either written down as the rule or collapsed into one word. |
| Q14 | **Is a class load-bearing?** At forty across the network a leader has one or two students per school and `school_name` *is* the group, so nobody needs to create a class. At twelve hundred a leader carries about forty-five and has to split them. | Decides whether class creation belongs in a leader's first run. Defaulted rather than blocked: a class is offered and never required, which is correct in the small world and merely incomplete in the large one. Revisit the day any single leader passes about twenty students. |
| Q15 | **Which world does an uninvited student land in?** Two places feel it. `joinable_leaders()` lists every active leader on the platform, so the open door would show one institution's staff to another's applicants. And `visible_students` currently folds unclaimed students into every program manager's view, because the alternative makes a teenager invisible to the only person who could help them. Someone arriving by invite is already inside a world; someone arriving cold has not declared one. | Blocks nothing today, because production has one program manager. Blocks the second one. Options: the open door lists nobody and joining is invite-only, or a student picks an institution first, or the door is per-program-manager at its own URL. |
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
The two real questions inside it are now Q13 and Q14.
Q11 minors' consent (2026-09-11): a parent or guardian consents for anyone under
18, recorded with a timestamp, and a school's paper consent is recorded by an
admin rather than assumed. Written as REQ-M.84.
Q13 who grants certification (2026-09-11): **the leader does**, not Avi and Naomi.
A leader certifies their own student by hand, gated on the entrance test and the
two Scratch certificates (REQ-M.76 to REQ-M.78). This is the answer that scales:
the people doing the granting grow with the cohort, because they are the same
people doing the teaching. The 1,250 / 120 / 28
figures came from Litala's prototype stats band, which Avi had stripped off the
home page as invented numbers.

## 7. Reference

Superseded material, kept for history: `docs/main_spec.md` Chapter 10,
`docs/backlog.md` EPIC-10, the site brief from Litala Aviv of 2026-08-03, and
the scoping conversation of 2026-08-08.
