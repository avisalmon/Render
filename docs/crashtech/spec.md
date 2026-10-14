# CrashTech — specification

A platform for running hardware hackathons, and for studying what happens
at them.

> **Status: chapter 1 only.** This is the thin introductory chapter the
> kickoff sequence in [building_an_app.md](../building_an_app.md) calls
> for: what the app is, in plain terms. The data model comes next, as its
> own document, and waits for approval before anything else is written.
> The remaining chapters come after that.

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

**Milestone 4 — Close and judging.** Submissions lock. Judges review.
Verification is a **spot check, not an audit**: the scores that decide the
winners get looked at, the artifacts are there as evidence, and the rest
stands on trust. Creativity challenges are different and always need a
human grade, because there is no number to report. Then results are
published.

**Milestone 5 — The museum.** A permanent public page for the event: the
photos, an exhibition of the projects and videos that were submitted, and
the feedback. It does not expire.

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

## Open questions

None. Every question raised during the interview has been answered; the
full list and its answers are at the end of
[data_model.md](data_model.md).
