# CrashTech — UX review and user journeys

> Written after the data model was approved and **before** the full spec,
> so the spec describes screens somebody has already thought about using,
> rather than screens that merely expose the tables.
>
> Companion to [spec.md](spec.md) and [data_model.md](data_model.md).

---

## Part 1 — The UX review

### 1.1 The central finding: this is two products

CrashTech looks like one application and behaves like two, and the biggest
UX mistake available here is to build it as one.

| | **The planning tool** | **The event tool** |
| --- | --- | --- |
| Used over | Weeks and months | 24 hours |
| By | Admin, tech lead, researcher | Participants, judges, the kit desk |
| On | A laptop, sitting down, unhurried | A phone, standing up, at 3am, tired |
| Mistakes are | Recoverable, nobody is waiting | Expensive, a queue is forming |
| Density | High. Tables, forms, configuration | Low. One thing per screen, big targets |
| Success feels like | "I have not forgotten anything" | "That took four seconds" |

The same visual language can cover both. The same **layouts cannot**. A
settings form with fourteen fields is correct for configuring an event and
catastrophic at a hardware desk with thirty people waiting.

**The rule this produces:** every screen is tagged in the spec as
**planning** or **event**. Event screens get a different bar: one primary
action, reachable with a thumb, legible at arm's length, tolerant of bad
wifi.

### 1.2 The second finding: every role needs a different front door

Five roles share one event and almost nothing they do overlaps. A single
generic event page with everything on it forces each of them to hunt for
their own part.

**The organising principle for the whole product: one role-aware home that
answers "what do I do now".** Not a dashboard of statistics. A screen that
names the current milestone and the next action *this person* owns.

- Admin, two days before kit day: *"Hardware day is Thursday. 18 of 24
  teams have not collected. Open the desk."*
- Tech lead, during setup: *"4 challenges written. 2 have no deliverables
  defined and the event cannot go live until they do."*
- Participant, mid-event: *"Challenge 6 submitted. 3 untried. Submissions
  close in 4h 12m."*
- Judge, after close: *"9 creativity submissions need a grade. Nobody has
  looked at 5 of them."*
- Researcher: *"Milestone 3 questionnaire: 31 of 48 answered."*

Everything else is reachable from there, and nothing else belongs on it.

### 1.3 Risks, ranked by how much damage they do

**R1. Role assignment is blocked on people who do not exist yet.** The
admin's first real task is appointing a tech lead and judges. Those are
busy industry people and academics who have never heard of babook. Today a
role can only be granted to an existing user, so the admin's first action
depends on three prior steps by somebody else. **This is a model gap, not a
screen problem** (§4.1).

**R2. Twenty-four hours of submitting into silence.** The leaderboard
defaults to admins-only, which is the right default. But a team that
submits nine challenges and sees nothing back is using a dropbox, not
competing. The fix is a distinction the model already allows and the UX
must insist on: **a team always sees its own score; the standings are a
separate thing that may be hidden.** "My points" and "where I rank" are
different questions.

And the standings are hidden *for now*, not forever. **When judging is
final, an admin publishes them in one click and they become public
permanently**, living in the museum. So the live experience is "I know how
I am doing, I do not know where I stand", and it resolves into a public
result rather than fading out.

**R3. Creativity submissions look broken.** They carry no score until
judging finishes, which is correct and will be read as a bug at 2am. Any
screen showing one says *"Judged after the event"* where the number would
be, and **never shows `0`**.

Judging is a two-step pipeline that happens entirely after the event:
submissions are **shortlisted**, and only the shortlist is graded. 24 teams
across 3 creativity challenges is 72 submissions, and tired judges asked to
score all of them carefully will not. Fifteen finalists get real attention.
A shortlisted team should be told so, because "you are a finalist" is good
news and arrives during an otherwise quiet wait.

**R4. The readiness cliff.** `status` advances in one click, and going
`live` reveals every challenge irreversibly. If the tech lead has not
finished, the event opens half-written in front of everyone at once.
**The advance control must not be a button. It must be a checklist that
becomes a button** (§4.2).

**R5. Research questionnaires standing between a person and what they came
for.** A questionnaire in the way at kickoff produces garbage answers and
resentment, and the resentment lands on the event rather than on the study.
Questionnaires are offered, never blocking, and never between a participant
and a submission.

**R6. The kit desk is the only physical queue in the system.** It is also
the only admin task done standing up with people waiting. If it takes more
than about five seconds per team it loses to a paper list, and the data
arrives late or never.

**R7. The museum is a chore after everyone has gone home.** It is also the
only thing that outlives the event and the only reason anyone hears about
the next one. If publishing it is a twenty-minute job on no sleep, it does
not happen. It has to be nearly written by the time the event ends: the
exhibition, the standings and the feedback are already in the system, so
the human adds photos and a paragraph.

It is also **participatory**: once open, anyone signed in may add photos
and anyone may download them. The people who were there have the good
pictures and the admin has twenty of the four hundred that exist.

**R8. Media volume can take the whole site down.** One event's raw demo
videos are about **26 GB**, against a 1 GB disk shared by every app on this
site. This is not a tuning problem, it is an architecture decision, and it
is settled in data_model.md §9: **a demo video is a URL and cannot be
uploaded at all**, which turns 26 GB into zero, and everything else goes to
Google Cloud Storage rather than the app disk.

The UX consequence is a promise made early: participants are told at **kit
pickup**, two weeks ahead, that their demo has to be hosted somewhere and a
link pasted in. Discovering that at 3am would be a trap.

### 1.4 What "intuitive" has to mean here

Four rules, each of them falsifiable:

1. **Never show a control that cannot be used yet.** A disabled button with
   no explanation is worse than no button. Either explain the condition or
   do not render it.
2. **The current milestone is always on screen.** Every role, every page.
   It is the one piece of context that changes what everything else means.
3. **Say what is missing, not that something is missing.** "Upload the
   Quartus project and record the measured Fmax" beats "Submission
   incomplete". The `Deliverable` model exists precisely so this is
   possible.
4. **Irreversible actions state what they will break.** Going live reveals
   every challenge to everyone, forever. That sentence belongs on the
   confirmation, not in a manual.

---

## Part 2 — The journeys

Each journey is what the person is trying to do, in order, with the moments
that matter called out. Screens are named so the spec can reference them.

### 2.1 Admin

The admin owns everything administrative and is the role the event cannot
start without. Their work is 95% slow planning and 5% a fast physical
queue, and those two parts need opposite designs.

#### Stage A — Getting in at all (the cold start)

Somebody has to be the first admin, and no admin exists to appoint them.

- A **site superuser** creates the event and is its first admin. That is
  the only place the chain can start, and it is a deliberate documented
  exception rather than an accident.
- From then on **an admin may appoint other admins**, so the superuser is
  needed exactly once per event.

*Screen: `event/new` (planning).* Name, dates, timezone. Nothing else.
Everything that can be decided later is decided later: an event with four
fields filled is a real thing somebody returns to, and a thirty-field form
is a thing they abandon.

#### Stage B — Assigning roles, which is the real first task

This is where the admin spends their first hour, and where R1 bites.

*Screen: `event/people` (planning).* One list grouped by role, each row a
person and their status.

The flow has to work for somebody who **does not yet have an account**:

1. Admin types an email address and picks a role.
2. If a user with that email exists, the role is granted immediately.
3. If not, an **invitation** is recorded and sent. The row shows
   *"Invited, not yet joined"*.
4. When that person signs up or signs in with that email, the role is
   already waiting. They land on their own role home, never on a generic
   page wondering what they are looking at.

**Why this matters more than it sounds.** The tech lead and the judges are
the people least likely to tolerate friction and most likely to be busy: an
academic, an engineer at a sponsor. *"Create an account on a site you have
never heard of, tell me when you are done, then I will give you access"*
loses people. *"Click this link"* does not.

The same screen handles removing a role, seeing who holds what, and the
fact that **one person may be both tech lead and admin**, which shows as
two chips on one row rather than two rows.

#### Stage C — Shaping the event

*Screen: `event/settings` (planning).* Each configuration decision with its
consequence stated beside it rather than in a help page:

- **Team size** — *"1 makes this an individual event."*
- **Kits per team** — *"Teams must exist before hardware day."*
- **Leaderboard visibility** — *"Admins only. Participants still see their
  own score."*
- **Supporting repository** — *"Examples and methodology live here.
  Challenges never do."*

*Screen: `event/milestones` (planning).* The five milestones and their
dates as a timeline. This is where hardware day gets its date, which is the
single date participants care about most before the event.

#### Stage D — Opening registration

Advancing to `published` makes the event public.

**The confirmation says what becomes true**, not "are you sure": *"The
event page becomes public and anyone may apply. Challenges stay hidden."*

*Screen: `event/registrations` (planning).* Applications arrive. Accept or
decline, with a note. Bulk accept for the common case. Accepting grants the
participant role, which is what lets them form a team.

#### Stage E — Hardware day, the one event-tool screen the admin owns

A different product from everything above. Thirty people in a corridor, one
admin, a box of boards.

*Screen: `event/kit-desk` (**event**, phone-first).*

- A single search field, focused on load. Three letters of a team or a
  person's name.
- Results are big rows: team, members, kit status.
- One tap marks the kit collected. The admin picks **which member** is
  standing there, because that is recorded.
- The screen returns to the empty search field ready for the next person,
  with a confirmation that does not need dismissing.

**Target: under five seconds per team, two taps, no scrolling, no typing
beyond the search.** Slower than a paper list means it loses to the paper
list. It must also work badly connected, because a corridor in a university
building is the worst wifi of the event.

#### Stage F — Going live

*Screen: `event/readiness` (planning).* Not a button. A checklist:

- Challenges exist, and each has at least one required deliverable
- At least one judge is assigned
- Kit collection: 22 of 24 teams *(a warning, not a blocker)*
- Milestone dates are in order

Each failing item links to the screen that fixes it. When the blockers
pass, the checklist becomes the **Go live** action, whose confirmation says
the irreversible thing: *"Every challenge becomes visible to every
participant. This cannot be undone."*

#### Stage G — During the event

Mostly watching and announcing. The admin is the only role that can see the
standings while the event runs, which is less fun than it sounds: they are
also the only person who knows and cannot say.

#### Stage H — Closing, judging, and the one big click

*Screen: `event/results` (planning).* After submissions lock, this screen
is the admin's map of what stands between now and publishing:

- Creativity challenges needing a shortlist
- Finalists not yet graded, and by whom
- Disputed submissions
- Measured top scores not yet spot-checked *(a prompt, not a blocker)*

**Publishing is one click with three permanent effects**: the final
standings become public, the museum opens, and both stay that way forever.
So the button does not exist until judging is actually final, and its
confirmation says exactly that rather than "are you sure".

This is the most meaningful action an admin takes in the whole product and
it should feel like it. Everything before it was preparation.

#### Stage I — The museum

The museum opens with publishing, already most of the way written: the
exhibition, the standings and the feedback summary come from the system.
The admin adds photos and a paragraph.

After that it is **not theirs alone**. Anyone signed in may add photos,
anyone may download them, and the admin's remaining job is moderation when
something needs removing rather than curation of everything that goes up.

### 2.2 Tech lead

One person owning everything technical, working mostly in `setup`, mostly
alone, against a deadline nobody else can see.

1. **Define the kit.** What hardware this event uses: names, photos,
   quantities. This is also what appears on the public page, so it is
   content as much as inventory.
2. **Point at the repository.** One URL. Examples, skills and methodology
   live there (spec §1.5.1).
3. **Write the challenges**, which is the real work, and the work with no
   deadline pressure until suddenly there is.

*Screen: `event/challenges` (planning).* A list showing, per challenge, the
one thing that matters: **is it finished**. A challenge with no deliverables
is not finished, and the list must say so rather than looking identical to
a finished one.

*Screen: `challenge/edit` (planning).* Brief, kind, points, deliverables.
The kind picker is the most consequential control in the product and
explains itself inline:

- **Completion** — pass or fail, scored on the team's own report.
- **Measured** — a number. Ranks teams and pays by position. *"This is the
  kind that resists being solved by prompting alone."*
- **Creativity** — judged by people. *"Scores only after judges grade it.
  Teams see no points until then."*

**Preview is not optional.** The tech lead writes something nobody can see,
which goes in front of everyone at once, irreversibly. They need to look at
exactly what a participant will see, deliverable checklist included, while
it can still be changed.

4. **Judging criteria** for creativity challenges, which judges read later
   and which is the only thing between "creativity" and "whatever the judge
   felt like that night".

### 2.3 Participant

The role with the most people in it and the least patience.

#### Before the event

- **Find the event and apply.** One form. The public page answers what,
  when, where and what you need, above the fold.
- **Be accepted**, and be told.
- **Form a team.** Create one and invite, or join one by name. The size
  limit is shown as a fact, not discovered as an error: *"Teams of up to 3.
  Yours has 2."*
- **Collect the kit.** They need three things: **the date, the place, and
  what they are being given.** The most-read screen before the event, and
  it should be almost entirely those.
- **Practise.** A link to the repository, and the honest sentence that the
  real challenges are secret.

#### At kickoff

The moment the event goes live the challenge list appears. This is the best
moment in the product and should feel like it: the list was empty and now
it is full.

*Screen: `challenges` (**event**).* Every challenge, its kind, its points,
and whether this team has submitted. Nothing competing for attention.

#### Submitting

*Screen: `challenge/submit` (**event**, phone-first).*

The deliverables are a **checklist, not a form**. Each line is a thing to
provide and is satisfied or not. The submit control explains itself when it
cannot be used: *"Still needed: the measured Fmax, and the Quartus
project."*

The QR upload carries over from 2026 and earns its place for **images**:
the phone that photographs the bench is not the laptop that is signed in.

**Video is different and the screen must be honest about it early.** There
is no upload button for a demo video, only a field for a link. A team
discovering this at the deadline would be a trap, so it is said at kit
pickup and repeated on the challenge brief, not sprung at submission.

**On submit the points land and the screen says so.** For completion and
measured work this is the reward moment and should feel like one. For
creativity it says *"Submitted. Judges score this after the event."* and
never shows a zero.

#### Throughout

A quiet persistent answer to **how am I doing, and how long is left**. Own
score always. Standings only if the admin opened them.

#### After

There is a **wait**, and it should be explained rather than endured:
submissions are in, judges are shortlisting and grading, results come when
that is done. A team that was shortlisted is told so, because it is good
news arriving during a quiet stretch.

Then results, a certificate, and the museum. The question a participant has
after an event like this is *"where is my stuff"*, and the answer is one
link that still works in a year.

The museum is **theirs too**: they can add their own photos and download
anybody's. Most of the good pictures from any event are on the
participants' phones, not the organiser's.

### 2.4 Judge

**Judges do nothing during the 24 hours.** That is deliberate and worth
stating on their own home screen, or they will wonder. Grading live would
mean judging the first submission against a different field from the last.

All of their work happens after the event closes, in three modes.

**Mode 1: shortlisting.** Read the creativity submissions for a challenge
and mark the finalists. Fast, comparative, done in one sitting per
challenge. The screen shows them side by side, because shortlisting is a
comparison and a one-at-a-time queue makes it impossible.

**Mode 2: grading the shortlist.** Real work, requires thought, one
submission at a time. Blind: the team's anonymous label only.

*Screen: `judge/queue` (planning-paced).* Ordered by what needs attention
most, which is **finalists nobody has graded**, not submission order. The
criteria the tech lead wrote sit on the screen, not behind a link, because
a judge who cannot see the criteria invents their own.

**Mode 3: due diligence on the top measured scores.** Not grading.
Checking. The reported number and the artifacts side by side.

*Screen: `judge/verify`.* Three outcomes: verified, disputed, or left
alone. **Left alone is the normal answer**, and the screen must not imply
otherwise, or judges feel obliged to check everything and the trust model
collapses back into the 2026 model it replaced.

Judges may read the challenges **before** the event. They are not
participants and the secrecy rule is not about them.

### 2.5 Researcher

The only role whose work spans several events, and the only one whose
interests can quietly damage everyone else's experience (R5).

1. **Define the study**: the thesis, the research questions, the literature
   review. Long-form writing, done once, revisited rarely.
2. **Build questionnaires**, each attached to a milestone, so a question
   about the kit is asked when the kit arrives rather than six weeks later.
3. **Watch responses arrive**, per milestone, as a completion rate.
4. **Read the data across events**, which is the entire point of a study
   not belonging to one hackathon.

**Consent is the researcher's first screen, not their last.** What is
collected, what for, whether it is identifiable, how to withdraw. A
participant sees it once, early, in plain language, and can revisit it
without hunting for it.

**The researcher never gets a blocking question.** The platform's
obligation to the participant outranks the study's convenience. A
questionnaire is an invitation on the role home; it is never a gate in
front of a submission, and declining costs the participant nothing.

### 2.6 The visitor who is not signed in

**Not a role, and the most important audience in the product.** Everyone in
§2.1 to §2.5 is already inside. This is everyone who is not, which is
everybody who has not heard of CrashTech yet, and the journeys above
quietly assumed them away.

They arrive three ways and want different things each time.

**From a poster, a QR code, a lecturer, a tweet, before the event.**

*Screen: `event` (public).* This is the whole funnel and it has one job:
answer, above the fold, **what is this, when, where, who can come, what do
I need, and how do I apply.** The 2026 static site answered these well and
that page is the thing to beat, not to ignore.

What they must not meet: a sign-in wall. Requiring an account to find out
what the event *is* loses people who would have come. Sign-in is for
applying, not for reading.

What they cannot see: challenges. Not a hint, not a count, not a greyed-out
list. Secrecy is the format.

**During the 24 hours.** Mostly nothing, and that is correct: the
leaderboard is gated and the work is unfinished. A quiet "this event is
running now, it ends at X" is enough, and it is also an advertisement.

**Years later, from a search engine or a shared link.**

*Screen: `museum` (public, permanent).* This is where a stranger meets
CrashTech for the first time and decides whether the next one is worth
their weekend. It is the single best piece of marketing the project will
ever have, and it costs nothing extra because it is made of what the event
already produced.

So the museum is **readable with no account at all**: the projects, the
videos, the final standings, the photos, the feedback. Signing in buys one
thing, the ability to **add** photos.

**The one real tension, and it resolves in the visitor's favour.** A
permanent public page naming people and showing their faces is exactly
where consent has to have been real. It was: teams consent up front and may
withdraw afterwards (`exhibition_consent`), and withdrawal removes the work
from display without deleting anything. The public page shows what people
agreed to show, which is why that flag exists.

### 2.7 Email, and when the system is allowed to interrupt

The journeys above all assume somebody is looking at the site. Most of the
time nobody is, and **the gaps between milestones are weeks long**. Email is
how the system reaches across them, and it is also the fastest way to make
people resent an event.

**The rule: email only for something that happened while they were not
looking, and that they need to act on or would be upset to miss.** Nothing
else. No digests, no engagement, no "here is what you missed".

That gives a short and complete list:

| Trigger | To | Why it survives the rule |
| --- | --- | --- |
| **Role invitation** | the invitee | They cannot act without it; this is the whole mechanism (§4.1) |
| **Registration accepted or declined** | the applicant | They asked a question and are waiting for the answer |
| **Kit pickup, a few days before** | accepted participants | A date and a place they must physically attend. The one email nobody minds |
| **The event is live** | participants | The challenges just opened and the clock is running |
| **Shortlisted** | the team | Good news, arriving during an otherwise silent wait |
| **Results published** | everyone who took part | The thing they have been waiting for, with the museum link |

Everything else a participant might want to know is on their role home,
which they are looking at anyway during the event.

**Three constraints the list implies.**

The audience is **international**, so every email carries a plain
unsubscribe for the non-essential ones and says which event it is about,
because somebody who competed three years running has three.

Email is **never the only channel** for anything that matters. Every fact
in the table above is also on the person's role home. An email that does
not arrive, and they do, must not cost anyone the event.

And it is **not a notification system**. There is no model for it, no
preferences screen, no inbox. Six triggers, sent at the moment they happen.
If that ever grows, it grows deliberately and gets a model then.

---

## Part 3 — Cross-cutting rules these journeys produced

1. **Role-aware home.** Every signed-in person lands on a screen naming the
   current milestone and their next action. Five roles, five homes.
2. **Planning or event.** Every screen is one or the other and is designed
   to that bar. Event screens are phone-first, one action, bad-wifi
   tolerant.
3. **Own score is not the leaderboard.** A team always sees its own points.
   Standings are gated during the event and published permanently after.
4. **Creativity never shows a zero.** It shows "judged after the event".
5. **Judges work only after the event**, and in two steps: shortlist, then
   grade the shortlist.
6. **Publishing is one gated click** with three permanent effects, and it
   says so.
7. **Video is a link, never an upload.** Everything else goes to GCS, never the app disk (data_model.md §9).
8. **Missing things are named.** Never "incomplete".
9. **Irreversible actions state their consequence** in the confirmation.
10. **Research never blocks.**
11. **The museum assembles itself**, the human adds photos and a paragraph,
    and then everyone else adds theirs.
12. **Reading never needs an account.** The event page and the museum are
    public. Signing in is for applying and for adding, never for finding
    out what this is.
13. **Email only for what happened while they were away**, and never as the
    only channel.

---

## Part 4 — What the journeys demand that the data model does not have

Two findings. The first is a real gap. The second is behaviour, not schema.

### 4.1 `RoleInvitation` — a role granted to an email, not a user

**Required.** R1: an admin cannot appoint a tech lead or a judge who does
not yet have an account, and those are exactly the people least likely to
create one on request.

| Field | Type | Notes |
| --- | --- | --- |
| `hackathon` | FK | CASCADE |
| `email` | EmailField | who is being invited |
| `role` | choice | the same choices as `EventRole` |
| `invited_by` | FK User | |
| `token` | CharField, unique | in the link |
| `sent_at` | DateTime | |
| `accepted_at` | DateTime, null | |
| `accepted_user` | FK User, null | who redeemed it |

Unique on (`hackathon`, `email`, `role`). Redeeming creates the matching
`EventRole`; the invitation remains as the record of who invited whom.

It also fixes something subtler: the people screen can show **invited but
not joined**, which is the state that actually matters two days before an
event when a judge has not appeared.

### 4.2 Readiness is computed, not stored

**No schema change.** R4 wants a checklist before going live, and every item
on it is already answerable from existing rows: do challenges exist, does
each have a required deliverable, is there a judge, how many kits are out,
are the milestone dates ordered.

So readiness is a function, not a field, for the same reason the
leaderboard is computed: a stored "ready" flag is a second source of truth
that goes stale the moment somebody deletes a challenge.
