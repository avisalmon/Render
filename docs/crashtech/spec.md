# CrashTech — specification

A platform for running hardware hackathons, and for studying what happens
at them.

> **Status: data model approved, spec complete.** Chapter 1 is the thin
> introduction the kickoff sequence in
> [building_an_app.md](../building_an_app.md) asks for; chapters 2 to 14
> are the full spec, written after
> [data_model.md](data_model.md) was approved and after the UX work in
> [user_journeys.md](user_journeys.md). Those two documents are companions
> to this one, not drafts of it.

---

## 1. What CrashTech is

### 1.1 In one paragraph

CrashTech runs a hardware hackathon end to end: from the day the event is
announced, through handing out physical kits, through a sealed set of
challenges opened at kickoff, through 24 hours of building and submitting,
to judging, results, and a permanent public exhibition of what was made.
It is also a research instrument: every event can carry questionnaires and
collect behavioural data, because the standing question behind CrashTech is
how people actually behave in a timed hardware competition.

It is a **framework**, not a test rig. It never compiles anybody's code and
never measures anybody's hardware. Teams report their own results, and the
system is built around trusting them.

### 1.2 Where it comes from

Two things already exist and both are inputs to this build rather than
things being replaced blindly.

**The 2026 event.** CrashTech VLSI 2026 ran at the Technion on 4 June 2026:
24 hours, DE10-Lite FPGA plus an ESP32 kit, secret challenges, 79
participants who answered a feedback survey afterwards. Its public site
lives at `github.com/avisalmon/TechCrash2026` and holds the event
description, the hardware guide, a setup checklist, practice projects, AI
tooling guidance, sponsors, and the feedback summary. All of it is
hand-written static HTML with a hardcoded countdown.

**A first platform.** A working hackathon platform was built inside
babook's `app/` in June 2026, before this site's app-per-capability rules
existed. It has nine models, around thirty routes, eighteen templates and
thirty-six passing tests, and it is live. It is not being extended: it
predates the rules on encapsulation, its own chrome, its own docs and its
own API, and it conflates roles this spec separates. It is **reference**,
and several of its ideas are good enough to carry over named (§1.8).

### 1.3 What the 2026 feedback changed

79 participants answered. 90% praised the logistics without reservation,
and several explicitly separated that from their technical criticism. The
criticism was one complaint wearing five hats:

| Theme | Share | What they said |
| --- | --- | --- |
| AI did all the work | 26% | *"You could win hundreds of points without reading a single line of code."* |
| Want fewer, bigger, harder challenges | 18% | *"Should have been 1 big challenge instead of many small ones."* |
| No room for creativity | 15% | *"Most challenges were very structured... only challenge 8 did, and indeed every team produced a different result."* |
| Didn't learn or understand the code | 13% | *"I'm not sure if I know how the code works. But I definitely know I know how to use AI."* |
| Performance challenges were the best | 8% | They forced real understanding, because AI alone could not optimize. |

The format rewarded delegating to a model rather than engineering. The one
thing that resisted it was a **measurable target**, because a number is
either hit or not and cannot be talked into existing.

So this build does one deliberate thing in response, and declines to do
more: it makes **measured-result challenges first class**, with their own
reported metric and their own ranking. It does not try to force the
competition's shape. Fewer and bigger challenges is a design decision the
tech lead makes when authoring an event, and the platform's job is to make
that possible, not mandatory.

### 1.4 Who it is for

- **Participants** — the people who build. Technion students for the 2026
  event; the platform does not assume that.
- **The people running it** — a tech lead, admins, judges, and researchers,
  described in §1.6.
- **Everyone afterwards** — the public exhibition outlives the event and is
  open to people who were never there.

### 1.5 The event as a spine of milestones

Everything in CrashTech hangs off an ordered sequence of milestones. The
gaps between them are configurable: two weeks between kit and kickoff is
typical, one week is fine, the system should not care.

**Milestone 1 — Publication.** The event becomes known. Dates are set and
visible, people can sign up to take part, and the event can be added to a
calendar. Challenges do not exist yet as far as anyone outside can tell.

**Milestone 2 — Hardware and practice.** Registered people are given a date
to **collect their kit in person**. A kit is allocated to a **team**, one
per team by default and configurable, and any member may be the one who
turns up for it. There is no shipping: the audience is international and
travels to the event, and posting FPGA boards across borders is a different
business. Because kits belong to teams, **teams have to exist by this
milestone**, so team formation happens at registration or here, not at the
event. The kit is
**defined by the organizer per event**: FPGA plus ESP32 plus sensors today,
a Raspberry Pi next time if that is the decision. Distribution is tracked and an admin confirms receipt. At the
same moment a **supporting repository** opens, holding the example
projects, the skills, and the methodology for operating the hardware and
the software. The real challenges stay sealed, and nobody outside the tech
lead knows what they are.

The repository is **a pointer, not content the system owns**. It may be a
fresh repo per event or one reused across several; the system stores a URL
and does not care which.

**Milestone 3 — Kickoff.** The 24 hours begin. Every challenge opens at
once, with its brief and its scoring visible. Teams build, and submit as
they go. A submission carries the **proof** the challenge asks for (a
video, an image, or a reported result in text or as a number) and the
**artifacts** the challenge requires (a Quartus project, controller code,
whatever that task defines). Points land **immediately and tentatively** on
the team's own report. Nothing waits for a human.

**Creativity challenges are the one exception, and not because of
distrust.** They have no number to report and nothing a later check could
compare against, so they score only when a judge grades them. A team cannot
report its own originality any more than it could report its own final
placing.

**Milestone 4 — Close and judging.** Submissions lock, and **all judging
happens here, none of it during the event**. Creativity submissions are
**shortlisted** and only the shortlist is graded, because seventy-odd
submissions get a rubber stamp while fifteen finalists get real attention.
Measured top scores get a **spot check, not an audit**: the scores that
decide the winners are looked at, the artifacts are the evidence, and the
rest stands on trust.

**Milestone 5 — Publishing, and the museum.** When judging is final an
admin publishes, in **one click with three permanent effects**: the
standings become public, the museum opens, and both stay that way forever.

The museum is a permanent public page: the photos, an exhibition of the
projects and videos, the final standings, and the feedback. It is also
**participatory**, not curated. Anyone signed in may add photos and anyone
may download them, because the good pictures from any event are on the
participants' phones rather than the organiser's.

That last point carries a constraint large enough to be an architecture
decision rather than a detail: **nothing a user uploads is stored on this
site's own disk.** One event's raw demo videos are around 26 GB against a
1 GB disk shared by every app here.

**A demo video is a URL, and there is no upload path for one at all.**
YouTube, Vimeo, a Drive share, anywhere: the system stores a link and never
accepts video bytes. That single decision turns 26 GB per event into zero,
removes the upload machinery entirely, and gives better playback than this
site could offer. Participants are told at kit pickup, two weeks ahead,
because demanding a hosted video is only fair if it is knowable in advance.

Everything else, images and source artifacts, goes to **Google Cloud
Storage**, which this site already has configured, in its own bucket. That
comes to roughly 650 MB an event. The arithmetic, and why Drive is the
wrong Google product for it, are in [data_model.md](data_model.md) §9.

### 1.5.1 Where things live

One rule, so there is never a question about where something belongs.

| Lives in | What | Why |
| --- | --- | --- |
| **The supporting GitHub repo** | Example projects, skills, methodology, how to drive the hardware and the toolchain | Open by design. People clone it, build it, and practise before the event. It is also the natural home for things that are code |
| **The system** | The challenges, and only the challenges | They are secret until kickoff. A repo cannot keep a secret from the people who were given the repo |
| **The system's database** | Everything about *this* event: dates, kit definition, sign-ups, schedule, sponsors, submissions, results, the museum, research | Per event, editable by an admin, so the next event needs no developer |

Two lines matter here, and the second one is a decision rather than an
observation.

**If it can be practised, it is in the repo. If it must stay sealed, it is
in the system.** That is the secrecy boundary.

**The system never restates what the repo holds.** No hardware guide, no
setup checklist, no AI guidance, no list of practice projects as content:
the event page links to the repo and stops. A database describing a
repository is a second source of truth, and the two drift the first time
somebody fixes a pin number in only one of them.

### 1.5.2 Teams, and how big they are

**A team is one or more people, and how many is an admin's decision.**
`team_size_max` defaults to 2 and has no ceiling: set it to 1 and the event
is individual, set it to 5 and it is five. The software does not have an
opinion about the right number, because the right number depends on the
event.

**A team has no captain.** Every member holds every authority: any of them
may submit, upload, collect the kit, or change anything the team owns.

**A person is on exactly one team per event, and on many teams across
events.** Someone who competes three years running has three, which is the
point of a platform rather than a single event. Within one event, two teams
for one person would mean two scores, two kits, and a leaderboard nobody
can read.

A team of one is still a team. That sounds like pedantry and is not: it is
what stops the leaderboard, the certificates, the blind judging and the
museum from each having to ask whether they are looking at a person or a
group.

**But the research is about individuals, and teamwork does not hide them.**
The system records who submitted each thing, who collected the hardware,
and who answered each questionnaire. The team is how work is scored; the
person is how behaviour is measured, and those are deliberately separate.

### 1.5.3 Language and audience

**English only. No Hebrew anywhere, in any surface, at any time.**

This is not a localisation decision deferred until later, it is the
decision: CrashTech is built for an international audience and English is
the single language of the product. There is no RTL layout, no Hebrew
strings, no bilingual templates, and no language switcher.

It is worth recording what this costs and what it buys, because the 2026
platform did the opposite. Its screens were Hebrew and its certificates
carried Hebrew labels, which means **none of its templates or UI strings
carry over**. Only its structure does. In exchange, the app never has to
grow a second direction of layout, which is the single most expensive
thing to retrofit into a design and the thing most often done badly.

The 2026 public site was already English. The platform is now catching up
to it rather than the other way round.

### 1.6 Roles

Roles are **per event**. A person can hold several on one event, and
different ones across events.

| Role | Count | What they own |
| --- | --- | --- |
| **Tech lead** | one | Everything technical: the hardware definition, the example project, the secret challenges, what each challenge requires as proof and artifacts, and the judging criteria. |
| **Admin** | several | Everything administrative: sign-ups, handing out hardware and confirming receipt, announcements, running the process. |
| **Judge** | several | Reviewing submissions, grading the creativity challenges, and running the due-diligence spot check before results are published. |
| **Participant** | many | Signs up, joins a team, collects the kit, builds, submits, competes. |
| **Researcher** | several | Defines what is being studied, authors the questionnaires attached to each milestone, and reads the data the event produces. May work across several events. |

Mentors exist at the event and are deliberately **not** a role in the
system. They are people in a room, not rows.

The clean separation of **tech lead from admin** is deliberate and is the
main structural difference from the 2026 platform, which had a single
"organizer" owning both the challenges and the logistics.

They are different **jobs**, not necessarily different people. One person
may hold both roles, and on a small event usually will. Separating them
keeps the permissions and the screens distinct so a bigger event can split
the work; it never forces a one-person event to pretend to be two.

### 1.7 Research is a first-class purpose, not a report

CrashTech exists partly to study how people behave in events like this.
That is not a feature bolted on at the end.

- A study carries its **thesis**, its research questions and its **literature
  review**, as data rather than as a file in somebody's drive. A study that
  spans three events spans three years, and the reasoning behind the
  questions is the first thing lost in that time.
- A researcher attaches a **questionnaire to a milestone**, so questions
  are asked at the moment they are about rather than all at the end.
- The system **collects behavioural data** as a side effect of running the
  event: when people submitted, how often, what they attempted, what they
  abandoned.
- The museum's feedback section is **produced from this data**. The 2026
  feedback page was assembled by hand; it should not have to be again.

**Consent is separate and comes first.** Research on people is not the same
promise as publishing somebody's photo. What is collected, what it is for,
whether it is identifiable, and whether a person can withdraw afterwards
all have to be recorded per participant per study, from the first event.
Consent is the one thing that cannot be added later, because data gathered
without it cannot be made usable retroactively. At the Technion this will
probably also want ethics approval before any data is collected; that is a
process question, not a code question, but the model must not be the thing
standing in the way.

### 1.8 What carries over from the 2026 platform

Named explicitly, so this is reuse of thinking rather than accident.

- **The lifecycle state machine.** An event moves through a fixed sequence
  of states ending in a permanent public one, and every surface gates on
  it. The idea is right and survives; the state names are rewritten to match
  the milestones (`setup`, `published`, `kits`, `live`, `closed`,
  `museum`).
- **Challenge secrecy.** Challenges are invisible until kickoff, and
  kickoff flips them all open in one move. The best-built part of the old
  system.
- **QR video upload.** A per-team, per-challenge token encodes a URL, so a
  phone can upload a demo video without being logged in. Solves a real
  problem at 3am and is kept.
- **Blind judging.** Teams carry a stable anonymous label so judges can
  review without knowing whose work they are looking at.
- **Consent captured up front, with a post-event opt-out**, for the
  exhibition.
- **Certificates** for participation and for the top places.

### 1.9 What CrashTech is not

- **Not a test harness.** It never compiles, simulates, flashes or measures
  anything. Results are reported by the people who achieved them.
- **Not a judge of truth.** Trust is the default. The audit is narrow,
  late, manual, and aimed only at the scores that decide the outcome.
- **Not a prescriber of format.** It does not enforce fewer or bigger
  challenges. It makes measured-result challenges possible and leaves the
  shape of the competition to the tech lead.
- **Not part of babook.** Its own app, its own base template, its own
  navigation, its own docs, its own API. A visitor inside CrashTech has no
  reason to know babook exists. The only thing shared is the user account
  people sign in with.
- **Not a single event.** The 2026 event is one instance. Hardware,
  challenges, content, questionnaires and milestones all belong to an
  event, so the next one needs no code.

---

---

## 2. The app and its boundaries

### 2.1 An isolated Django app

CrashTech is its own Django app (`crashtech`), following the standing
pattern in [building_an_app.md](../building_an_app.md): own `models.py`,
`views.py`, `urls.py`, own migration chain from `0001`, own templates under
`templates/crashtech/`, own static files under `static/crashtech/`.

Rule 2.1.1: **the only thing shared with the rest of the site is
`auth.User`**, for sign-in. Nothing else crosses the wall in either
direction. CrashTech never reads or writes another app's models.

Rule 2.1.2: **two named adapters are permitted**, the same shape memz uses,
and no others. One for the site's content-safety check (museum uploads,
Rule 9.3), one for outbound email. Each lives in exactly one file, so that
"cross-app reach is rare, deliberate and named" stays true.

Rule 2.1.3: mounted at **`/crashtech/`** in `mysite/urls.py`, before the
catch-all `app.urls` include.

### 2.2 Its own front door

Rule 2.2.1: **own base template and own navigation.** CrashTech never
extends `base.html` and never inherits babook's header, footer or menu.

Rule 2.2.2: **own authentication screens.** Sign in, sign up, sign out and
password reset are CrashTech's own pages in CrashTech's own look, posting
against the one shared `User` table underneath. A visitor never sees
another product's branding mid-flow.

Rule 2.2.3: **babook links to CrashTech; CrashTech does not link back.**
A deliberate exception to the usual default, stated by Avi: CrashTech is
public and production-worthy, and babook's portal routes people to it. The
reverse stays forbidden, because a Technion participant has no reason to
know babook exists.

Rule 2.2.4: **English only, LTR.** No Hebrew strings, no RTL, no language
switcher, anywhere, including the auth screens.

### 2.3 The REST API

Rule 2.3.1: every model gets full documented CRUD over Django REST
Framework (building_an_app.md Rule 6), gated by the role rules in chapter
4. Screens are built on the API rather than instead of it.

Rule 2.3.2: **no anonymous writes.** Reading is open where Rule 8.4 and
chapter 9 say it is; writing always requires a signed-in user holding a
role on that event.

---

## 3. The event and its lifecycle

Rule 3.1: an event moves through `setup`, `published`, `kits`, `live`,
`closed`, `museum`, in that order and never backwards. Every surface gates
on it.

Rule 3.2: **entering `live` makes every challenge visible at once**, and it
cannot be undone.

Rule 3.3: **entering `museum` publishes the results**, permanently and
publicly, and opens the museum. One action, three effects (Rule 8.5).

Rule 3.4: **advancing is a checklist, not a button.** Before `live` the app
computes what is outstanding: challenges exist, each has a required
deliverable, at least one judge is assigned, milestone dates are ordered.
Blockers prevent the advance and link to the screen that fixes them;
warnings, such as kits not all collected, do not. The control appears only
when blockers clear, and its confirmation states the irreversible effect in
words.

Rule 3.5: readiness and publish-readiness are **computed, never stored**. A
stored flag is a second source of truth that goes stale the moment somebody
deletes a challenge.

Rule 3.6: milestones are rows with dates, not fixed offsets. The gap
between kit pickup and kickoff is whatever the dates say.

---

## 4. Roles and permissions

Rule 4.1: roles are **per event**: `tech_lead`, `admin`, `judge`,
`participant`, `researcher`. One person may hold several on one event and
different ones across events; holding two is two rows.

Rule 4.2: **a site superuser creates an event and becomes its first
admin.** The only place the chain can start, and a deliberate named
exception. After that an admin may appoint other admins.

Rule 4.3: **roles may be granted to an email address before that person has
an account.** Redeeming on sign-up or sign-in creates the role, and the
invitation remains as the record of who invited whom. Without this,
appointing a judge waits on three prior steps by somebody who has never
heard of this site.

Rule 4.4: what each role may do.

| | Tech lead | Admin | Judge | Participant | Researcher |
| --- | --- | --- | --- | --- | --- |
| Event settings, milestones | | yes | | | |
| Grant roles, invite | | yes | | | |
| Define the kit | yes | | | | |
| Distribute kits | | yes | | | |
| Decide registrations | | yes | | | |
| Author challenges | yes | | | | |
| Read challenges before `live` | yes | yes | yes | **no** | |
| Submit | | | | yes | |
| Shortlist, grade, verify | | | yes | | |
| Watch judging progress | | yes | yes | | |
| Advance lifecycle, publish | | yes | | | |
| Study, questionnaires | | | | | yes |
| Read research data | | | | | yes |

Rule 4.5: **judges may read challenges before the event.** They are not
participants and the secrecy rule is not about them.

Rule 4.5.1: **reading judging is not judging.** An admin may watch grading
progress and may not shortlist, grade or verify. Added in C.5 because the
publish screen tells an admin what is blocking publication and links them
at the screen that clears it, and that link was refusing them.

Rule 4.6: a participant sees only their own team's submissions, never
another team's, until the museum opens.

---

## 5. Registration and teams

Rule 5.1: **people apply; they are not invited.** An application is its own
record with its own status, kept apart from the role, so that "who asked"
survives independently of "who is in". Accepting grants the participant
role.

Rule 5.2: a team is one or more people, up to `team_size_max`, which
defaults to 2 and has no ceiling. `1` makes the event individual.

Rule 5.3: **a person is on exactly one team per event**, enforced by the
database, and on many teams across events.

Rule 5.4: **no captain.** Every member holds every authority: any may
submit, upload, collect the kit, or change anything the team owns.

Rule 5.5: teams must exist by the hardware milestone, because kits are
allocated to teams.

---

## 6. Hardware

Rule 6.1: **the kit is defined per event** as a list of items with names,
descriptions, photos and quantities. FPGA and ESP32 today, a Raspberry Pi
next time, with no code change.

Rule 6.2: kits are **allocated to a team**, `kits_per_team` of them,
defaulting to 1.

Rule 6.3: kits are **collected in person**, by any member, and the system
records which member turned up and which admin confirmed it. There is no
shipping.

Rule 6.4: the kit desk is an **event screen**: one search field, big rows,
two taps, under five seconds per team, working on bad wifi. If it is slower
than a paper list it loses to the paper list, and then the data never
arrives.

---

## 7. Challenges and submissions

Rule 7.1: challenges are **invisible until kickoff**. Not a hint, not a
count, not a greyed-out list.

Rule 7.2: three kinds, and a challenge is exactly one of them.

- **Completion** — pass or fail, flat points, scored on the team's report.
- **Measured** — a reported number, ranked against other teams, paying by
  finishing position. The kind that resists being solved by prompting
  alone, and the one real product response to the 2026 feedback.
- **Creativity** — graded by people, after the event.

Rule 7.3: **each challenge declares in advance what a submission must
contain**: the proof (video, image, text or a number) and the artifacts (a
Quartus project, controller code, whatever that task needs). Because the
requirement is declared, the app can say what is still missing *before* a
team submits rather than after.

Rule 7.4: **points land immediately and tentatively on the team's own
report**, for completion and measured challenges. Nothing waits for a
human. Creativity is the exception and scores only when judged.

Rule 7.5: **a demo video is a URL and there is no upload path for one.**
Any host. Participants are told at kit pickup, two weeks ahead, because
discovering it at the deadline would be a trap.

Rule 7.6: the QR upload carries over from 2026 for images: the phone that
photographs the bench is not the laptop that is signed in.

Rule 7.7: submissions lock at the deadline, which may fall before the event
itself ends.

---

## 8. Judging, results, publishing

Rule 8.1: **judges do nothing during the event.** Grading live would score
the first submission against a different field from the last. All judging
happens while the event is `closed`.

Rule 8.2: creativity judging is **two steps**: shortlist, then grade the
shortlist. Seventy submissions get a rubber stamp; fifteen finalists get
real attention. A shortlisted team is told, because it is good news during
a quiet wait.

Rule 8.3: measured top scores get a **spot check, not an audit**: the
reported number and the artifacts side by side, with three outcomes,
verified, disputed, or **left alone, which is the normal answer**. If a
screen implies otherwise, judges check everything and the trust model
collapses into the 2026 one it replaced.

Rule 8.4: **the leaderboard is computed, never stored**, and its visibility
is a per-event setting defaulting to `admins`. A team **always** sees its
own score regardless. "My points" and "where I rank" are different
questions, and twenty-four hours of submitting into silence is a dropbox,
not a competition.

Rule 8.5: **publishing is one gated click.** It requires every finalist
graded, nothing left disputed, and every creativity challenge with
submissions shortlisted. It makes the standings public permanently and
opens the museum.

Rule 8.6: certificates for participation and for the top places, each at an
unguessable permanent URL.

---

## 9. The museum, and where media lives

Rule 9.1: the museum opens on publishing and is **permanent and public**.
It carries the photos, the exhibition of projects and videos, the final
standings and the feedback. Most of it assembles itself from what the event
already produced; the human adds photos and a paragraph.

Rule 9.2: **reading needs no account.** Signing in buys one thing, the
ability to add photos. This is the page where a stranger meets CrashTech
for the first time, years later, and decides whether the next one is worth
a weekend.

Rule 9.3: uploads are **moderated** through the one named adapter. A
permanent public page anyone may post to is a permanent public page anyone
may post anything to.

Rule 9.4: the exhibition is **computed from consent**, not copied. Only
teams that gave `exhibition_consent` appear, and withdrawing removes the
work from display without deleting anything.

Rule 9.5: **no user upload touches the application disk.** Images and
artifacts go to a dedicated Google Cloud Storage bucket, separate from the
backups bucket, through `django-storages`. Images are resized on upload,
artifacts are size-capped, and deleting a row deletes its file on commit.

---

## 10. Research

Rule 10.1: a **study spans events**, carries its thesis, its research
questions and its literature review, and cites its sources as rows.

Rule 10.2: questionnaires attach to **milestones**, so a question about the
kit is asked when the kit arrives.

Rule 10.3: **research never blocks.** A questionnaire is an invitation on
the role home. It is never a gate in front of a submission, and declining
costs the participant nothing. The platform's obligation to the participant
outranks the study's convenience.

Rule 10.4: **consent is per person, per study, per event, versioned and
withdrawable.** It is the only thing in this system that cannot be added
afterwards, because data collected without it cannot be made usable
retroactively.

Rule 10.5: behavioural data is a by-product of running the event, never a
separate instrument: when people submitted, how often, what they attempted,
what they abandoned.

---

## 11. Screens, and the two products

Rule 11.1: **every screen is tagged planning or event**, and designed to
that bar. A fourteen-field settings form is correct for configuring an
event and catastrophic at a hardware desk with thirty people waiting.

Rule 11.2: **event screens are phone-first**: one primary action, thumb
reachable, legible at arm's length, tolerant of bad wifi, 44px tap targets
minimum.

Rule 11.3: **every role lands on its own home**, naming the current
milestone and the next action that person owns. Not a dashboard of
statistics.

Rule 11.4: the current milestone is on screen on every page for every role.
It is the one piece of context that changes what everything else means.

Rule 11.5: **never show a control that cannot be used yet.** Either explain
the condition or do not render it.

Rule 11.6: **name what is missing**, never "incomplete".

Rule 11.7: **irreversible actions state their consequence** in the
confirmation, in words, not "are you sure".

Rule 11.8: **creativity never renders a zero.** It renders "judged after
the event".

---

## 12. Email

Rule 12.1: email is sent **only** for something that happened while the
person was not looking and that they must act on or would be upset to miss.
Six triggers, listed in [user_journeys.md](user_journeys.md) section 2.7.
No digests, no engagement mail.

Rule 12.2: **email is never the only channel.** Every fact it carries is
also on the person's role home. A mail that does not arrive must not cost
anyone the event.

Rule 12.3: the audience is international. Every message names which event
it is about, and the non-essential ones carry an unsubscribe.

Rule 12.4: this is **not a notification system**. No model, no preferences
screen, no inbox, until it deliberately becomes one.

---

## 13. Retiring the 2026 platform

Rule 13.1: the existing CrashTech inside `app/` is **reference, not a
dependency**. Nothing in the new app imports it.

Rule 13.2: it currently owns `/crashtech/` and holds **seeded demo data
only**, no real event. The new app takes that path when it is ready, and
the old routes are removed in the same change.

Rule 13.3: the old models are **left in place and unused** rather than
deleted, until the retirement has been live long enough to be sure. Its 36
tests keep running until its routes go.

---

## 14. Process

Rule 14.1: spec and backlog are the two sources of truth and are updated
together, in the commit that acts on them.

Rule 14.2: tests for whatever can break silently. The two things most
likely to: the lifecycle gates, such as a challenge visible before kickoff,
and the permission matrix in Rule 4.4.

Rule 14.3: **every screen is looked at as an image, once.** HTML-reading
tests cannot see layout, and layout is most of what a person experiences.

Rule 14.4: dev first. Nothing is pushed without Avi's word.
