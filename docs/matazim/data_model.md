# מט״צים — the data model

`docs/building_an_app.md` Rule 4: every app gets a data-model document separate
from its spec. The spec explains what the app does and why. This explains the
shape of the data on its own, so somebody can reason about the database without
reading a hundred requirements first.

Written 2026-09-14, at Avi's instruction to stop and bring this app onto the
methodology's principles. It is a retrofit: מט״צים was built over thirty-three
sprints before Rule 4 existed, and its data model lived as §4 of the spec, which
is the arrangement that rule exists to prevent. The spec's §4 stays where it is
and remains the place decisions are argued; this file is the structure.

Twenty models (eighteen when this file was written; `TeachingSession` and
`Institution` came after), one Django app, one migration chain. Source of truth
is `matazim/models.py`; if the two disagree, the code is right and this file is
stale.

---

## 1. The one thing that is not ours

`User` is babook's, and it is the only table shared in either direction
(RULE-4: babook never imports מט״צים). Everything else here belongs to this app.

Anything מט״צים needs to know about a person that babook does not is a field on
`MemberProfile`, never a new column on `User`. That is Rule 2, and it is also
why this app can be read on its own: follow a `User` FK out and you have left.

`app.UserProfile` (babook's) holds the display name. מט״צים reads it and never
writes a second copy, because a person with two names is a person whose name is
wrong on one screen.

---

## 2. The shape, in one picture

```
Institution ──m:n── User (babook, as .managers)
 ├─1:n─ Leader ──1:n── StudyClass
 │        │                 │
 │        │                 └─── m:n ── Student.classes
 │        └─1:n── Student (leader, and pending_leader)
 │                  ├─1:n── StatusLog
 │                  ├─1:n── Application
 │                  ├─1:1── MatazCertificate
 │                  ├─1:n── TeachingSession
 │                  └─1:n── Submission ──1:n── Feedback
 │                             └─1:n── Post (kind=work)
 ├─1:n─ Event  ── m:n ── Leader, StudyClass
 ├─1:n─ Post (as author's institution)
 ├─1:n─ LeaderInvite
 └─1:n─ RetentionRun (as ran_by, a User)

User (babook)
 ├─1:1─ MemberProfile ──1:n── EntranceAttempt ──n:1── EntranceTarget (by target_id, not FK)
 ├─1:n─ Notification
 └─1:n─ Request ──1:n── RequestMessage
```

Three things in that diagram are the whole design:

**`Institution` is the tenancy root** (REQ-M.144, §6). Every scoping question in
this product resolves to it: a student belongs to a leader, a leader belongs to
an institution, and that chain is what `matazim/access.py` walks. Until
2026-09-14 the root was a `User` (`Leader.program_manager` and three FKs like
it) rather than its own row, on the argument that a second network becomes a
table the day one exists and a second *manager* of the same one was not
expected to matter (spec §4.8). It mattered: the day a manager leaves, and the
day two people run one programme together, both real from the start (Litala's
brief describes צוות התכנית as two people). §6 has the full history.

**`Student.leader` is nullable and that is normal.** Somebody registers, passes
the entrance test, and belongs to nobody yet (REQ-M.65). Every query has to
survive it, which is why `access.unclaimed_students()` exists.

**There is no table about the children a מט״צ teaches.** The programme's whole
output is teenagers teaching younger children, and not one of those children is
a row anywhere here (REQ-M.29), `TeachingSession` included: it counts them and
names none. Teaching is recorded as the מט״צ's own declared activity. A guard
test walks every field on every model in this app and fails on a name that looks
like a record about a child, so the property is checked
against the schema rather than against one screen.

---

## 3. The models

### 3.1 People and roles

**`Institution`** — the tenancy root (REQ-M.144, full design and history in §6).
`name` and `managers` (m:n `User`). Being a program manager means being in that
m:n; there is no flag anywhere that could disagree with it. `Leader`, `Event`,
`LeaderInvite` and `Post` all carry a required `institution` FK.

**`MemberProfile`** — one row per person מט״צים has met, 1:1 with `User`.

| Field | Type | Notes |
|---|---|---|
| `user` | 1:1 User | the only link out of this app |
| `entered_via_matazim` | bool | REQ-M.35, which door they came through |
| `first_seen_at`, `welcome_accepted_at` | datetime | REQ-M.39/40, told once and it is recorded |
| `entrance_test_passed_at` | datetime | the gate to joining a leader (REQ-M.36) |
| `is_program_manager` | bool | the role; granted only through `roles.grant_program_manager` |
| `birth_year` | int, blank | year only, never a full date (REQ-M.84) |
| `guardian_name`, `guardian_email`, `guardian_consent_at` | | REQ-M.84 |
| `guardian_consent_recorded_by` | FK User, null | the staff member who entered a paper consent, null when a parent typed it here (REQ-M.85) |

A blank `birth_year` counts as a minor, deliberately. Reading blank as "adult"
would exempt the entire pre-existing population in a way nobody would notice.

The year rather than a date is the privacy trade: it is off by up to one
depending on their birthday, and it buys not holding a child's date of birth.

**`Leader`** — the adult. 1:1 with `User`. Having the row *is* the role; there is
no role column anywhere that could disagree with it.

| Field | Type | Notes |
|---|---|---|
| `user` | 1:1 User | |
| `join_code` | char, unique | REQ-M.9, the link a member uses to attach |
| `is_active` | bool | deactivating removes them from the join list, destroys nothing |
| `approved_at`, `approved_by` | | REQ-M.93. Unapproved is a real state: `access.leader_of()` refuses an unapproved row, so it grants nothing at all rather than merely looking different on a screen |
| `program_manager` | FK User | **the tenancy root** |
| `assigned_by`, `assigned_at` | | who put them in this world |

`is_active` and `approved_at` are different facts. Unapproved means nobody has
said yes yet; inactive means somebody said yes and later stopped it.

**`StudyClass`** — a leader's group at one school.

`school_name` is free text and lives here rather than on `Leader`, so a leader
running classes at two schools needs no second leader record and the label lands
where the students actually sit. בתי הספר המשתתפים is the distinct set of these.
Avi closed the question on 2026-09-14: a school is an attribute of a leader and
never a table.

**`Student`** — the מט״צ. One row per person per cohort.

| Field | Type | Notes |
|---|---|---|
| `user` | FK User | FK not 1:1, because a person can return in a later cohort |
| `leader` | FK Leader, **null** | REQ-M.65, belonging to nobody is normal |
| `pending_leader` | FK Leader, null | they asked; that leader has not answered |
| `status` | char | five public stages plus two ways out, defined once in `STATUS_CHOICES` |
| `cohort_year` | int | |
| `certified_at`, `certified_by` | | REQ-M.78, a person decides |
| `classes` | m:n StudyClass | |

**`status` is never assigned directly.** It goes through
`matazim.history.set_status`, which writes the `StatusLog` row in the same
breath. A guard test fails on any `something.status = ...` assignment outside
that function, and it has caught three sprints in a row.

### 3.2 The entrance test

**`EntranceTarget`** — one object in the bank. The geometry lives in files a
management command generated offline: an STL, a dimensioned drawing, and an
answer key the web process never exposes. This row exists so a *person* can take
an object out of circulation without anything being deleted (REQ-M.55).

**`EntranceAttempt`** — one go, by one member, at one target.

A retry is a **new row**, never an edit, because the history is the point:
somebody who missed, read the feedback and came back has shown more of what this
programme selects for than somebody who passed first time (REQ-M.53).

`model_file` is a minor's own work and is stored outside `MEDIA_ROOT` under a
random name, reachable only through a view that asks who is looking (REQ-M.80).
`MEDIA_ROOT` is served with no authentication at all, and school work is
routinely named after the pupil.

`target_id` is a string rather than an FK to `EntranceTarget`, because the bank
is generated files and the row is the curation layer over them.

### 3.3 Joining

**`LeaderInvite`** — two shapes (REQ-M.91, M.92). *Personal* is named to a
person by the program manager and single-use; the label may be wrong and that is
fine, because the real name arrives when they register. *Open* is a link that
can be used many times and creates candidates rather than leaders.

`token` is random and long: a sequential integer would let somebody walk the
endpoint into a harvest of join codes, and a join code attaches its holder to a
leader with no confirmation (REQ-M.79).

**`Application`** — what somebody wrote when they asked to join: their grade,
why they want in, what they have built. It existed in the spec and not in the
database for several sprints; the form asked a fourteen-year-old three questions,
validated two of them, and discarded all three, so the leader deciding saw a name
and an email.

### 3.4 The record of decisions

**`StatusLog`** — every change to a student's stage, and who made it (REQ-M.21).

**Append-only.** Nothing in this product updates or deletes one, and a guard test
asserts no code path tries. Every other record here answers "what is true now";
this one answers "who decided, and when".

It carries `from_leader`/`to_leader` as well as the statuses, so a transfer
between leaders is legible a year later.

**`MatazCertificate`** — 1:1 with a certified student. `public_id` is a UUID, so
the verification URL a school types off a printed page is unguessable and
reveals nothing by being incremented. `revoked_at` rather than deletion: a
certificate that was issued and withdrawn is a different fact from one that never
existed.

`name_on_certificate` and `awarded_by_name` are **copies taken at issue time**,
not joins. A certificate is a document about a moment, and it must not silently
change because somebody edited their display name two years later.

**`RetentionRun`** — one approved deletion and who approved it (REQ-M.87).
Retention runs behind a review rather than on a timer, because deletion is the
one action here where an unattended bug is irreversible.

### 3.5 The work, and the feedback that is the point

**`Submission`** — a member puts work in front of their leader (REQ-M.19).

`leader` is stored beside the row as well as being reachable through
`student.leader`, because `Student.leader` can change (REQ-M.98) and "who gave
this feedback" must still answer correctly a year later.

`answers` is a self-FK: a resubmission answers a returned one and **both are
kept** (REQ-M.125). Overwriting would destroy the thing the feedback was about,
and a member reading "you should change the base" wants the version that had
the base.

Either a `work_file` or a `link` or both: a Scratch project is a link and an STL
is a file, and a teenager should not have to care which kind the product prefers.

**`Feedback`** — what the leader said, its own table rather than a field, because
a leader may say more than one thing and the thing a member returns to read is
the words, dated and attributed. **Never edited or deleted.**

### 3.6 Telling people, and the room they are in

**`Notification`** — a pointer, not a record. The truth is the submission, the
feedback, the roster row; this says where to look. That is what makes it safe to
delete one or expire the lot, and it is the difference between a bell and a
second inbox nobody keeps in step with the first.

`url` is validated to stay inside `/matazim/` (RULE-1).

**`Event`** — a יום שיא. Owned by a program manager, so another institution's
diary is not merely hidden but unreachable. Aimed rather than broadcast:
`for_everyone`, or named `leaders`, or named `classes`. `is_public` is a tick and
never a default, because a public page about a programme for fourteen-year-olds
is a public statement of when and where children gather. `cancelled_at` rather
than deletion, because somebody arranged their week around it.

**`Post`** — קהילת מט״צים (§4.12). `program_manager` is stamped at write time
rather than read back through the author, because `Student.leader` can change and
a post must not move school when a teenager does. `hidden_at`/`hidden_by`/
`hidden_reason` rather than deletion: a post that vanishes teaches its writer
nothing.

### 3.7 The improvement loop

**`Request`** — what the person who runs the programme actually asked for
(§4.11). **The text is hers and is never edited** (REQ-M.112). The assessment,
the recommendation, the sprint id and the outcome are all fields *beside* her
words, never rewrites of them.

**`RequestMessage`** — one turn of the conversation behind a request. The chat
may propose new wording; it never gates submission and never replaces what she
typed unless she takes the proposal.

---

## 4. Rules that live in the data rather than in a screen

Collected here because they are the ones a new query is most likely to break.

| Rule | Where it lives | What breaks without it |
|---|---|---|
| Scope is a property of the queryset | `matazim/access.py`, one function per model | A view that forgets to filter reads another institution's children |
| A status change writes its log | `matazim.history.set_status` | The record of who decided disappears, silently |
| An append-only table is append-only | `StatusLog`, `Feedback` | The history becomes editable, which is the same as having none |
| Taken down, never deleted | `Event.cancelled_at`, `Post.hidden_at`, `MatazCertificate.revoked_at` | Somebody is left holding a date, a moderation, or a credential nobody will explain |
| A minor's file is not in `MEDIA_ROOT` | `matazim/storage.py` | Schoolwork named after the pupil is served to anyone who guesses |
| A name on a certificate is a copy | `MatazCertificate` | A document about a moment changes years later |
| Nothing records a child | every model | The programme's own privacy charter (REQ-M.29) |

---

## 5. The REST API over this model

`docs/building_an_app.md` Rule 6: full documented CRUD per model, DRF, and the
screens built on the API rather than beside it. `matazim/api.py` and
`matazim/serializers.py`.

**Every viewset's queryset comes from `matazim/access.py`.** That is the single
most important property of the API, and the reason it is stated here rather than
only in the code: an API that derived its own scope would be a second answer to
"who may see this", free to drift from the one the screens use, and the drift is
invisible until somebody reads another child's words.

**Fields that decide ownership are read-only everywhere** and set on the server
from `request.user`: authors, institutions, join codes, tokens, public ids, and
the timestamps that record who decided what. A client that could name its own
author could post as another teenager; a client that could name its own
`institution` could write into another institution's world.

**Some verbs are refused, and the refusal is the requirement.** Full CRUD is the
default; where a verb is forbidden, the viewset says so in words and a test holds
it. The complete list, so nobody has to find out by trying:

| Model | Refused | Why |
|---|---|---|
| `StatusLog` | create, update, delete | Append-only, written only by `history.set_status` (§4.7) |
| `Feedback` | update, delete | Never edited or deleted (REQ-M.123) |
| `RetentionRun` | create, update, delete | A record of a job that a person approved, not an editable row (REQ-M.87) |
| `Notification` | create | Creating one through the API is forging somebody else's bell |
| `MatazCertificate` | create, delete | Issued by `certification.certify` and revoked, never deleted (REQ-M.78) |
| `Request` | update of `body` by anyone but its author | Her words are hers (REQ-M.112) |
| `RequestMessage` | update, delete | A conversation is not rewritten after the fact |
| `EntranceAttempt` | update, delete | A retry is a new row; the history is the point (REQ-M.53) |
| `Student.status` | direct write | Goes through `history.set_status`, which logs it (§4.7) |
| `Post` | delete of somebody else's | Deletion is withdrawal by its author; moderation is `hide` (REQ-M.131) |
| `Institution` | create, delete, write to `managers` | No screen makes a second one yet (REQ-M.144); the role is granted on the root-only screen through `roles.py`, never by an m:n write here |

Read the browsable API at `/matazim/api/` as the documentation; DRF renders
every route, its verbs and its fields, which is the call this site already made
for ustrip.

---

## 6. Built: the `Institution` row (REQ-M.144)

**Status: done, 2026-09-14.** Written up here as a proposal, then Avi: "Go."
Built the same day. Kept in its original shape below (the problem, the design,
the cost, the payoff) because that is the record of why it exists; only the
status line and this note are new.

**The problem it closed.** The tenancy root was a person. `Leader.program_manager`,
`Event.program_manager`, `LeaderInvite.program_manager` and `Post.program_manager`
all pointed at the `User` who ran the programme, and `access.py` scoped every
screen by that user. §4.8 argued that a second network becomes a table on the
day one exists, and never considered the day the first manager leaves. On that
day her successor would sign in to an empty programme and every row she owned
would be stranded. The review of 2026-09-14 named this the largest structural
risk in the model.

**What existed before this, as a stopgap.** `manage.py matazim_handover old new
--apply` moved everything one manager owned to another, atomically, and left
the records of who did what untouched. It worked, needed somebody to remember
to run it, and left "who runs this institution" a fact living in nobody's
table. Superseded by this model rather than kept alongside it: see REQ-M.143.

**The model.** One small table:

| Field | Type | Notes |
|---|---|---|
| `name` | char | the institution as it names itself, e.g. רשת עתיד |
| `managers` | m:n User | who runs it; more than one is allowed and is the point |
| `created_at` | datetime | |

`Institution.default()` returns the earliest-created row, for the one callers
that don't yet need to ask "which one" (`roles.grant_program_manager`'s ordinary
path, the seed commands). The four `program_manager` FKs became `institution`
FKs, `institution_of()` returns the row instead of a user, and
`is_program_manager(user)` reads `Institution.objects.filter(managers=user)`
rather than a flag. `MemberProfile.is_program_manager` is gone: the m:n is the
role, and a flag beside it would have been a second copy of one fact.

**How it shipped against a database with real rows.** Four migrations rather
than one, because the FK could not go straight from "does not exist" to
"required": `0031` adds the table and four *nullable* FKs; `0032` is a data
migration that creates the one institution production already implies (from
whoever held the old flag) and files every existing `Leader`, `Event`,
`LeaderInvite` and `Post` into it; `0033` drops the old flag and the four user
FKs now that nothing reads them; `0034` makes the four `institution` FKs
required, written by hand rather than by `makemigrations` (which stops to ask
for a one-off default that `0032` had already made unnecessary).

**What it cost.** About thirty call sites in `access.py`, the views, the API and
the admin, and every test fixture that built a manager or a leader — several
hundred lines across roughly twenty test files, most of it mechanical and some
of it not: a handful of fixtures had silently relied on the old FK being
nullable (a leader "orphaned" with no owner at all, or created through a screen
that never set the field), and the required FK turned each of those from a
silent gap into a test failure, which is exactly the trade a required column is
for. The sweep in `test_spr_m_34.py` (REQ-M.139) is what made the whole change
safe to make: it asks all eighteen endpoints for everything from inside one
institution and fails the moment a second one's rows answer.

**What it bought.** A manager can be added or removed without moving a row.
Two managers can share one institution, which is what Litala's brief describes
for צוות התכנית (Avi and Litala) and which a single-owner FK could never
represent. The day a second network arrives, it is a second row, not a
redesign.

**A defect this caught in itself.** The first version of `handover.hand_over`
called `roles.grant_program_manager(new)` with no institution named, which
joins whichever institution `Institution.default()` finds — the earliest
created, not necessarily the one being handed over. Every test database
carries a second institution from `0032`'s backfill (the seeded row), so the
successor ended up managing both, and `institution_of()` picked the seeded one
over the one that actually owned the predecessor's rows.
`test_a_successor_inherits_the_whole_institution` failed on exactly that, which
is why `grant_program_manager` now takes an explicit `institutions=` argument
rather than always assuming the default.
