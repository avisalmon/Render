# blackjack — Spec

> **Status: full spec, 2026-10-01.** Chapter 1 is the introduction from the
> kickoff interview; the rest was written once the [data model](data_model.md)
> was settled. Requirements are `REQ-B.n`. Q1 and Q4 of 1.7 are answered;
> Q2 and Q3 are still open and marked where they bite.

---

## Chapter 1 — What this is

### 1.1 In one paragraph

A blackjack app whose product is not the game. The table is the surface; the
thing being sold is a **teacher**. A person learns basic strategy from cheat
sheets built out of the rules they chose, drills it hand after hand against a
real dealt table, and is told after every decision what the correct play was
and why. Everything about how they are doing is kept, so the app can say what
they are good at, what they keep getting wrong, and whether they are improving.

Avi, opening the interview, before saying what it is:

> "This is not just another online blackjack game. That does not interest me."

### 1.2 The three sections

**Learning.** Cheat sheets generated from the active rule set, splittable into
views a person can hold in their head: weak dealer, strong dealer, doubles.
Four actions on screen: hit, stand, double, split.

**Practice.** A real table with cards and animation, dealt in casino order:
player, dealer, player, then the hole card. A situation appears, the person
chooses, and then gets the correct play with the reasoning. It never ends.
Every hand is recorded. Every twenty hands, a note on that batch and the trend.

**Advanced.** The paid tier, and the only part that uses AI.

### 1.3 Free and paid, and why the line is where it is

**Everything in learning and practice is free, and contains no AI at all.** Not
a guarded path to a model: no path. The cheat sheets, the drill, the
explanations, the statistics, the full history and the note every twenty hands
are deterministic, computed in the browser against data shipped with the page.

That makes the rule provable rather than enforced. A free account cannot reach
a language model because nothing in the free product talks to one.

**Paid is a teacher that remembers you:**

- AI feedback and monitoring over the person's own history.
- Drilling that adapts to their weak areas.
- Explanations deeper than the canned reason attached to each cell.
- Tricks to remember, built for the hands *they* keep missing.
- Sharing, following, and gamification such as streaks.
- A play simulator, playing with friends, and a champion league.

Three ways to hold paid access: a **subscription**, through babook; a **coupon**
from Avi, worth one week; and **thirty minutes** from first use, for anybody new.

The subscription is babook's, not this app's. babook already has `Entitlement`,
and Avi intends one payment to eventually cover every app on the site, so this
app asks rather than stores. The day that change happens, nothing here changes.

### 1.4 What it refuses to be

These are refusals, not unbuilt features. Each one survives future requests.

- **Never real gambling.** No buying chips with money, no cash-out, no prizes
  with real value anywhere, including the league. The subscription buys
  coaching, never chips. This protects more than this app: it is the same
  payment account that takes babook's course payments, and the line between
  "a teaching app" and "a gambling site" is one feature wide.
- **No sound effects.** People practise on a train, in a waiting room, next to
  a sleeping child. An app that chirps is an app they cannot open.
- **No ads.** The loudest complaint about the apps already in this market is
  ads every seven hands.
- **No card counting in v1.** Decided 2026-10-01, and said out loud rather than
  implied: several competitors promise a counting trainer and one of them has
  an app store full of people angry that it never arrived. It is a different
  product with twice the surface. Not never, just not now.
- **The chart is never asked of a language model.** Basic strategy is
  deterministic. A tutor that is right 97 percent of the time teaches the wrong
  play once an hour and the learner cannot tell which time.

### 1.5 The one promise worth making on the front page

Users of competing trainers report that the drill's "correct" answer sometimes
disagrees with the app's own strategy card. In a teaching product that is the
worst possible defect: it teaches a mistake and destroys the trust that makes
the rest worth anything.

**Here the chart and the drill are the same data, and a test proves it.** That
is a sentence no competitor can currently write, and it is free to us because of
how the thing is built.

### 1.6 Shape of the thing

- Phone first, works on a desktop. The cheat sheet splits into narrow tables
  because a ten-column chart is unreadable in a hand.
- The drill runs in the browser against data shipped with the page, so it is
  instant and works with no signal. Attempts are recorded to the server behind
  it, because a person who changes phone must not lose a year of practice.
- Open to anyone on babook. Sign-up required; there is no anonymous product.

### 1.6a How we work on this app

Avi, 2026-10-01, setting the cadence before the first line of code:

> "Let me review after every epic. No need for full regression. It will slow
> things down. Run full regression only when i tell u."

So:

- **Review gate is the epic, not the sprint.** Sprints land without stopping;
  an epic ends by going to Avi.
- **Tests run scoped by default**: this app's own suite, plus whatever a change
  actually touches. That is what runs before every commit.
- **The full suite runs when Avi asks for it, and not otherwise.** It takes
  twelve minutes, and twelve minutes per sprint is a tax on the wrong thing.
- **The honest cost, stated once and then not repeated:** a scoped run cannot
  see a break in a part of the site this app never mentions. The baseline diff
  against `docs/regression_baseline.txt` is what catches that, so it is worth
  asking for a full run before any push that matters, rather than on a timer.

Process weight otherwise follows the heavy end, as מט״צים does, because this is
a public product with strangers as users and money involved: numbered
requirements, a spec in chapters, a backlog with sprints, tests written first,
and a generated dashboard.

### 1.7 Decisions

| # | Question | Answer, or why it matters |
|---|---|---|
| Q1 | Does the strategy chart ship as static data rather than database rows? | **Answered 2026-10-01: "charts are tables."** So Rule 1 stands and there is no exception to write down. The 340 decisions and their reasons are rows, and the page ships a serialised copy of the one chart it needs, which is what "all in js and ready data" asked for. One source, two readers, and the promise in 1.5 gets stronger: the sheet and the drill are literally the same rows. |
| Q2 | **OPEN.** Does following reuse babook's `Follow`, or does this app keep its own? | babook already has a member-follows-member graph, used by its community feed. Reusing it means following somebody at the blackjack table also follows them in the community, which a person may not expect. Keeping our own means two follow lists on one site. Bites in SPR-B.5.5. |
| Q3 | **OPEN.** Is the free tier really without streaks, sharing and following? | Avi's call and a coherent one: the free tier is a tool, the paid tier is a habit. Recorded because those three are usually what brings a free user back and what spreads the app, and only paying users would be able to spread it. Bites in SPR-B.5.5. |
| Q4 | The app's public name. | **Answered 2026-10-01: `blackjack`**, at `/blackjack/`. A product name can still sit on top of both without a migration. |

---

## Chapter 2 — The table and its rules

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.2.1 | A rule set is a row | Decks, S17/H17, doubling, DAS, splits, surrender, payout, peek. Presets ship; a person may make their own. | TODO |
| REQ-B.2.2 | The default is the common case | 6 decks, S17, double any two, DAS, split to 4, aces once, no surrender, 3:2, peek. Nobody fills in a form before playing a hand. | TODO |
| REQ-B.2.3 | A rule set in use is never edited in place | Changing a rule makes a new row. Editing one would silently rewrite the correct answer for every hand already played against it. | TODO |
| REQ-B.2.4 | Every stored hand carries its rule set | Without it the hand can never be judged again, and every statistic built on it is unfalsifiable. | TODO |
| REQ-B.2.5 | An unsupported combination is refused, not approximated | If no chart exists for a rule set, the app says so. A near-enough chart is a tutor teaching the wrong play. | TODO |

## Chapter 3 — Learning: the cheat sheets

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.3.1 | The sheet is generated from the active rule set | Not a picture, not a fixed table. Change the rules, the sheet changes. | TODO |
| REQ-B.3.2 | Four actions | H, S, D, P on screen. The fallback for an unavailable action lives underneath and is shown when it applies. | TODO |
| REQ-B.3.3 | Splittable views | Weak dealer (2-6), strong dealer (7-A), doubles, soft hands, pairs. A ten-column chart is unreadable on a phone; five columns is a thumb. | TODO |
| REQ-B.3.4 | Every cell can explain itself | Tapping a cell shows the canned reason. Free, instant, identical every time, attached to the row. | TODO |
| REQ-B.3.5 | The sheet and the drill are the same rows | The promise in section 1.5, held by a test that compares what the screen renders with what the drill answers for the same cell. | TODO |

## Chapter 4 — Practice: the drill

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.4.1 | A real table | Cards dealt with animation in casino order: player, dealer, player, hole card. | TODO |
| REQ-B.4.2 | Decide, then learn | The person picks an action; the correct play and its reason appear after, never before. | TODO |
| REQ-B.4.3 | It never ends | No level gate, no lives, no session limit. | TODO |
| REQ-B.4.4 | Every hand is recorded | One Attempt row: situation, rule set, chosen, correct, time taken. | TODO |
| REQ-B.4.5 | Answers are instant and work offline | The chart for the active rule set ships with the page. The server is never asked what the right play was. | TODO |
| REQ-B.4.6 | Attempts survive a lost connection | Queued locally and sent when the connection returns. A person's practice is not lost to a tunnel. | TODO |
| REQ-B.4.7 | No sound, ever | Section 1.4. | TODO |
| REQ-B.4.8 | Motion respects the reader | prefers-reduced-motion stops the cards flying. They still arrive. | TODO |

## Chapter 5 — Progress

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.5.1 | Full history per person | Every attempt, forever, replayable. | TODO |
| REQ-B.5.2 | Mastery per decision, not one percentage | All 270 decisions tracked separately: "41 of 270 solid, these 12 cost you the most". The complaint competing apps get is that a person cannot tell which hands are their weak ones. | TODO |
| REQ-B.5.3 | A note every twenty hands | That batch's accuracy, the trend against the batch before, the cells that cost the most. Free and deterministic. | TODO |
| REQ-B.5.4 | Accuracy over time, as a graph | Asked for repeatedly by users of competing apps, and free to us because every attempt is already stored. | TODO |
| REQ-B.5.5 | Named sessions | Drill one thing without polluting lifetime numbers. | TODO |
| REQ-B.5.6 | Reset means start fresh, never destroy | A reset opens a new session. The history stays. | TODO |
| REQ-B.5.7 | Recently missed cells come back | The weak form of spaced repetition, free. The real scheduler is paid (REQ-B.8.2). | TODO |

## Chapter 6 — Access

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.6.1 | Sign-up required, open to anyone | No anonymous product. Portal audience: everyone. | TODO |
| REQ-B.6.2 | One gate, asked everywhere | ai_is_open(user) is the only answer to "may this person use AI", and every AI path asks it. | TODO |
| REQ-B.6.3 | Thirty minutes from first use | Not from signup. Somebody who signs up and returns on Thursday still gets their half hour. | TODO |
| REQ-B.6.4 | A coupon is bearer and one-time | A link or QR, shareable on WhatsApp. The first account to redeem claims it; then it is spent. Worth seven days. | TODO |
| REQ-B.6.5 | The subscription is babook's | This app stores none. It asks Entitlement. When one payment covers every app, nothing here changes. | TODO |
| REQ-B.6.6 | The free product has no path to a model | Not a guarded path: none. Proven by a sweep that enumerates AI entry points from the URL conf and refuses a free account at every one. | TODO |
| REQ-B.6.7 | Expiry is silent and kind | When access ends, the paid surfaces close without losing anything. History, mastery and notes stay. | TODO |

## Chapter 7 — Admin

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.7.1 | Generate coupons | In the app, not in Django admin. A code, a label, a link and a QR to send. | TODO |
| REQ-B.7.2 | See activity | Who is playing, how much, accuracy, trials running, coupons out and redeemed. | TODO |
| REQ-B.7.3 | Admin is root only | Not staff, not a tier. | TODO |
| REQ-B.7.4 | The admin screen never shows a person's hands | Counts and accuracy, never a named person's history. A teacher's dashboard, not surveillance. | TODO |

## Chapter 8 — Advanced: the paid tier

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.8.1 | Feedback over your own history | What the AI sees is this person's attempts, not a generic lesson. | TODO |
| REQ-B.8.2 | Adaptive drilling | Cells chosen by the scheduler. Deterministic arithmetic, not a model call: instant, and free of per-hand cost. | TODO |
| REQ-B.8.3 | Deeper explanation on demand | Beyond the canned reason: why this cell, why it feels wrong, what the margin is. | TODO |
| REQ-B.8.4 | Tricks to remember | Mnemonics built for the cells this person keeps missing. | TODO |
| REQ-B.8.5 | Every model call goes through babook | app/ai_chat.py owns the client, the usage log and the monthly cost cap. No second client, no second budget. | TODO |
| REQ-B.8.6 | The chart is never asked of a model | The model explains the answer; it never decides it. | TODO |
| REQ-B.8.7 | Streaks, sharing, following | Paid, per Avi. Q3 of section 1.7 records the argument against and his decision. Following reuses babook's graph pending Q2. | TODO |

## Chapter 9 — Later

Sketched so the shape is known. Not designed until the core works.

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.9.1 | Play simulator | Full hands with a bankroll. Play money only. Each decision inside is an ordinary attempt. | LATER |
| REQ-B.9.2 | Play with friends | A room, seats, a shared shoe. | LATER |
| REQ-B.9.3 | Champion league | Ranked by decision accuracy, never by chips won. Ranking winnings ranks luck, and a leaderboard that rewards a hot shoe teaches the opposite of the product. | LATER |

## Chapter 10 — How it must behave

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.10.1 | Phone first | Built and measured at 390px before it is looked at on a desktop. | TODO |
| REQ-B.10.2 | Nothing scrolls sideways | Measured in a real browser at 390, 1024 and 1280, not eyeballed. | TODO |
| REQ-B.10.3 | The action buttons are reachable with one thumb | They are tapped hundreds of times per session. Size and position are measured. | TODO |
| REQ-B.10.4 | No idle work | The drill does no animation frame loop while waiting for an answer. A trainer that drains a battery is a trainer nobody opens twice. | TODO |
| REQ-B.10.5 | Its own chrome | Own base template, own nav. No link back to babook unless asked for. | TODO |
| REQ-B.10.6 | Full CRUD REST API | Methodology Rule 6, on DRF, over every model this app owns. | TODO |
