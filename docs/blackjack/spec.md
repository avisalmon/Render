# blackjack — Spec

> **Status: chapter 1 only, written 2026-10-01 from the kickoff interview.**
> This is step 2 of the sequence in [building_an_app.md](../building_an_app.md):
> a thin introductory chapter, enough to say what the app is. The full spec in
> chapters comes after the [data model](data_model.md) is approved.

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

### 1.7 Decisions still open

| # | Question | Why it matters |
|---|---|---|
| Q1 | Does the strategy chart ship as static data rather than database rows? | Methodology Rule 1 says real data is database rows; a strategy chart is a constant of the game, like a multiplication table, and must be instant and offline. The rule allows exceptions **written down at the time**, so this needs an explicit yes. Asked 2026-10-01, not yet answered. |
| Q2 | Does following reuse babook's `Follow`, or does this app keep its own? | babook already has a member-follows-member graph. Reusing it means following someone here also follows them in babook's community, which a person may not expect. |
| Q3 | Is the free tier really without streaks, sharing and following? | Avi's call and a coherent one: the free tier is a tool, the paid tier is a habit. Recorded because those three features are usually what brings a free user back and converts them. |
| Q4 | The app's public name. | `blackjack` is the Django label and `/blackjack/` the path. A product name can sit on top of both without a migration. |
