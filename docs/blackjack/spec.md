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
- A play simulator, playing with friends, and a champion league.

**Streaks, sharing and following are free** (Avi, 2026-10-02, reversing his own
earlier call). They are what brings somebody back on a Tuesday and what
spreads the app, and under the old rule only paying users could spread it.
They also need no model, so they sit on the free side of the line without
weakening it.

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
| Q2 | Does following reuse babook's `Follow`, or does this app keep its own? | **Answered 2026-10-02: reuse.** Following a person is about identity, which babook owns (main_spec 0.3), so blackjack reads that graph and never grows a second one. The cost, accepted: following somebody here also follows them in babook's community. |
| Q3 | Is the free tier really without streaks, sharing and following? | **Answered 2026-10-02: no, they are free**, reversing his 2026-10-01 call that everything from that point was advanced. They need no model, so the free tier still has no path to one, and the paid tier is still defined by exactly the thing arithmetic cannot do. |
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
| REQ-B.5.9 | The history graph has its numbers on it | Avi, 2026-10-02: "make numbers there to see my percentage and time." Every batch carries its percentage on the point, the axis names the first and last batch's date and time, and touching or arrowing across the plot reads out the exact percentage and time of any one batch. The floor of the scale is the lowest batch rounded down, then twenty lower, so somebody who never drops below 90 sees their wobble and the axis says where the floor is. Always old to new, left to right, even on a right-to-left page. | **DONE 2026-10-02**. Positions are worked out by the server (`_graph`), the readout is `graph.js`, and without the script the numbers and the dates are all still there. |
| REQ-B.5.10 | Videos on the learning screen | Avi, 2026-10-02: "find good youtube explaining the game and hand gestures and embed them in the training section." Five, in two groups (how the game works, how to signal the dealer), on the sheet under `#videos`, each a row in `Clip` that root can reword, reorder or switch off at `/blackjack/api/clips/`. Nothing is requested from YouTube until a card is pressed, the player is `youtube-nocookie.com`, and the card is a real link to YouTube without the script. English, from outside channels, and the page says so. | **DONE 2026-10-02**. Chosen by oEmbed (embeddable) and by reading each transcript against the line written under it. |
| REQ-B.5.8 | Streaks, sharing and following, free | Avi, 2026-10-02, reversing his earlier call: these three are what brings somebody back on a Tuesday and what spreads the app, and under the old rule only paying users could spread it. Following **reuses babook's `Follow`** (Q2), because following a person is about identity, which babook owns; blackjack reads that graph and never grows a second one. | **DONE 2026-10-02**. All three free, all three built. Following is babook's `Follow`, written through `blackjack/friends.py`, which is the only place in the app that touches it. |

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
| REQ-B.8.7 | Streaks, sharing, following | **Moved to REQ-B.5.8 on 2026-10-02.** Avi reversed himself and put these in the free tier. Kept here as a pointer so the renumbering is visible rather than silent. | MOVED |

## Chapter 9 — Later

Sketched so the shape is known. Not designed until the core works.

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.9.1 | Play simulator | Full hands with a bankroll. Play money only. Each decision inside is an ordinary attempt. **Built 2026-10-02 at `/blackjack/play/`.** Free for everybody signed in (Avi: "free for all, no ai api needed"): it never asks the gate and calls no model; the explanation after a decision is the chart cell's own sentence. A real multi-deck shoe shuffled with the operating system's entropy, a cut card at 65 to 78 percent and a reshuffle before the next round. The shoe and the dealer's down card stay on the server. Bets 10 to 500 in tens, 1,000 chips to start, a free refill when the stack is gone. Insurance is offered on an ace and is never scored (it is a bad bet and the answer is always no). A pair is judged as a pair only while it can be split; otherwise by its total. A double the table forbids is judged by the cell's fallback. Chips are private, cannot be bought or withdrawn, and are never ranked. | **DONE 2026-10-02** |
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

## Chapter 11 — The strategy lab

> **Status: built 2026-10-16 (SPR-B.12), awaiting Avi's review in dev.** Specified
> from Avi's description and answers the same day, then built as written. The
> open questions at the end of 11.4 were settled by the defaults stated there.

### 11.1 What it is

The play simulator (REQ-B.9.1) answers "what is this hand?". The strategy lab
answers "what does this way of playing do over a very long time?". Avi sets the
conditions, the lab plays tens or hundreds of thousands of hands with no cards
on screen, and the result is drawn as graphs.

Avi, 2026-10-16: "I give the conditions: the amount of card decks in the
shuffle, the rules, and I can manipulate the classical table ... it's a
specific manipulation of the table for that simulation. It doesn't change the
rules, the classical rules. And you run like 10,000 hands, 100,000 hands,
whatever, and we graph the results. I also choose the initial amount of money
and the policy of my gambling."

### 11.2 The two things that are easy to confuse

**The rules** are the casino's: decks, dealer on soft 17, double after split,
and the rest of the rule set the app already has. They decide what is legal and
what a hand pays.

**The table** is the chart: for each situation, the play a person makes. The
lab lets Avi override single cells of the chart for one run, for example "never
split eights". An override changes the player's decision, never a rule, and
never anything outside that run.

### 11.3 Requirements

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.11.1 | Conditions are chosen per run | Number of decks, the rule set and the starting bankroll. A day lasts up to 100,000 hands by default and ends early if the money is gone (Avi: "100,000 until you bust and lose all the money"). Defaults are the person's own rules and basic strategy. **Built 2026-10-16.** | DONE |
| REQ-B.11.2 | One blackjack, held to the same answers | Dealing, legality and payouts in the lab must be exactly those of `engine.py`, so a lab hand and a table hand cannot disagree about a rule. Because the lab runs in the browser (REQ-B.11.23) it needs a JavaScript copy of the engine; that copy is allowed only with a guard: a fixed set of card orders is played through both, and every round must match to the chip, for every rule the lab offers. A rule added to one and not the other fails the build. **Built 2026-10-16.** | DONE |
| REQ-B.11.3 | Table overrides | Any cell of the chart (hard, soft or pair, against a dealer card) can be set to another action for the run. The override is stored with the run and shows beside its results. The classic chart, the person's saved rule set and their history are never touched. An override naming an action the rules do not allow in that spot falls back the way the chart already does, and the run says how often that happened. **Built 2026-10-16.** | DONE |
| REQ-B.11.4 | Starting money | Chosen per run; the default is 1,000. Play money only; no link to the simulator's chips (REQ-B.9.1) in either direction. **Built 2026-10-16.** | DONE |
| REQ-B.11.5 | The gambling policy has two blocks | A **bet ladder** (REQ-B.11.13 to B.11.15) says how much to bet on each round. A **freeze rule** (REQ-B.11.16) says when to set winnings aside untouched. Both are settings of the run, both are optional, and a policy with neither is a flat bet. **Built 2026-10-16.** | DONE |
| REQ-B.11.13 | The bet ladder | An ordered list of bet sizes, chosen by the person, with as many rungs as they like. The default is 15, 50, 150, 500. The run starts on the first rung and, after each lost round, moves to the next rung. A rung is a number of chips, not a multiple of the last one, so any sequence can be entered. **Built 2026-10-16.** | DONE |
| REQ-B.11.14 | After a win, and after a push | After a won round the ladder goes back to the first rung. That is the default (Avi: "the default is jumping again to the beginning"). The person can instead choose to stay on the same rung, or step back one rung. A push is neither a win nor a loss: the rung does not change. A round is won or lost by its net result, so a split or doubled round that nets chips counts as a win and one that loses chips as a loss. **Built 2026-10-16.** | DONE |
| REQ-B.11.15 | At the end of the ladder, and when the money is short | Two edges, each with a chosen behavior. **Table limit** (a setting of the run, since a table has a maximum bet): when the next rung is above the limit, or the last rung was lost, the person picks to keep betting the top rung, to start the ladder again from the first rung, or to stop the run. **Not enough money:** when the next bet is more than the playing stack, the person picks to bet what is left, to go back to the first rung, or to stop. The default for both is to bet the top allowed rung and then what is left. **Built 2026-10-16.** | DONE |
| REQ-B.11.16 | The freeze rule is a list of chunks | Avi: "the first chunk will be 1,000, then the second chunk 500, and I can choose whatever I like as I go. So it must be flexible." The money is split into a **frozen** amount and a **playing** amount. The freeze rule is an ordered list of chunk sizes. Step one waits until the playing amount has grown by the first chunk, moves exactly that profit to the frozen amount, and play continues from the starting playing amount. Step two then waits for the second chunk, and so on. The person adds, removes and edits steps freely, with as many as they like. Frozen money is never bet again. **Built 2026-10-16.** | DONE |
| REQ-B.11.18 | The defaults are Avi's own run | Starting money 1,000; table minimum 15; table limit 500; bet ladder 15, 50, 150, 500, back to 15 after a win; freeze steps 500, 500, 1,000, 2,000. Read as Avi described it: at 1,500 freeze 500 and play on from 1,000; at 1,500 again freeze 500 and play on from 1,000; at 2,000 freeze 1,000 and play on from 1,000; at 3,000 freeze 2,000 and play on from 1,000. Raising the table limit unlocks the next rungs the person has entered; rungs above the limit are not used. Every default can be changed on the conditions screen, and every list can be lengthened or shortened without limit. **Built 2026-10-16.** | DONE |
| REQ-B.11.19 | What a run reports | The question Avi asks of the defaults is how long the playing money lasts: "until I lose this 1,000 dollars, and I want to see how much it will take to lose them." Each run reports the number of hands until bust (or "survived all 100,000"), money frozen by then, the highest the playing amount reached, the lowest it fell to, and the final total (frozen plus playing). The same figures are shown for the classic twin. **Built 2026-10-16.** | DONE |
| REQ-B.11.20 | The table is chosen per run | Every rule the app already keeps in a rule set (REQ-B.2.1) can be set for a run: number of decks, whether the dealer hits or stands on soft 17, what a blackjack pays (3:2 or 6:5), double on any two cards or only some, double after split, how many splits and whether aces may be resplit or hit, surrender, and whether the dealer peeks. Avi, 2026-10-16: "the table limit, how much it pays, 2 to 3 or 5 to 6, the dealer policy of soft 17, does he hit or not, etc." The **table minimum and table limit** (default 15 and 500) are settings of the run beside the rules, not part of the rule set, because they change what can be bet and never what a hand is worth. The default rules are the app's common case (REQ-B.2.2): 6 decks, dealer stands on soft 17, 3:2. **Built 2026-10-16.** | DONE |
| REQ-B.11.21 | Mode one: many days at the casino | Avi: "one run of a policy doesn't mean anything ... take this policy, take these rules, and run it 10, 20, 30 times, and how many of those tries I won, and the final count at the end. It simulates like if I went with the same policy X days in a row to a casino, how many of those days I took money home, how much." The person sets everything and the number of days. Each day starts from the starting money, plays until bust or until the day's hand limit, and ends with a result. The report: days finished ahead out of days played, the total and average taken home, the best and the worst day, how long the playing money lasted on each day, and the days drawn as lines on one graph with a histogram of how the days ended. Each day is played again with the classic chart on the same shuffles (REQ-B.11.12), so the report also says how many days the change helped and how many it hurt. **Built 2026-10-16.** | DONE |
| REQ-B.11.22 | Mode two: find a better policy | Avi: "you analyze and try policies and figure out what you would have done, like a gradient descent on policies." Given the rules and a goal, the lab tries many policies and reports the best it found. What it may change: the bet ladder, the table-limit behavior, the freeze steps, and (as a later step) table overrides. The goal is chosen from: most days finished ahead, highest average result, longest-lasting playing money, or a weighted mix of the three (REQ-B.11.27). Because results are random and the choices are whole numbers and lists, a literal gradient does not exist; the search tries a policy, nudges it, keeps what scores better, and every policy is scored on the same shuffles so the comparison is fair. The best policy is then re-scored on shuffles it has never seen, and both scores are shown, so a policy that only fits the shuffles it was tuned on is exposed. The result states plainly what no policy can change: the house edge on each hand. A found policy can be saved as the person's own and run in mode one. **Built 2026-10-16.** | DONE |
| REQ-B.11.23 | It runs in the browser, in the background | Avi: "if you do everything in JavaScript and scripts in the background, it's not high compute ... make sure it's not so slow." The runs execute in a Web Worker in the person's own browser, so the page stays responsive, the server does no simulation work, and no shuffle ever needs to be sent. Measured on the server's engine first: about 50,000 hands a second in Python on this machine, which would make 30 days of 100,000 hands, each played twice, take about two minutes of one shared server's time. Only settings and summary figures are sent to the server to be kept (REQ-B.11.7). **Built 2026-10-16.** | DONE |
| REQ-B.11.24 | The limits | Set in one place and shown on the screen: hands per day (default 100,000), days per run, how many policies the search tries, and a time budget after which the search stops and reports the best so far. Defaults are proposed in 11.4 and set after timing a real run. **Built 2026-10-16.** | DONE |
| REQ-B.11.25 | A saved run is a summary, never a notebook | Avi, 2026-10-16: "keep all the simulation in the user history, but don't bombard the database ... just save the results: the policy, the trending graph of the wins or loses, a minimum set of data, because I don't want to overflow the database." Every hand, every day's line and every policy a search tried stays in the page that ran it and is gone when it closes. What is stored is the conditions and policy (so the run can be set up again) and a summary: counts, a 60-point trend line for the run and for the classic chart, and a 20-bar histogram, about 2 KB. The server rebuilds the summary field by field, refuses anything outside the list or over 6,000 bytes, and keeps a person's newest 50 runs. A saved run is renamed or deleted, never edited. **Built 2026-10-16.** | DONE |
| REQ-B.11.26 | The base chart is a choice: classic, or calculated | Avi, 2026-10-16, asked whether the lab should offer only the rules the classic chart covers or work out the best play itself: "both as options". **Classic** is the published chart the rest of the app teaches (REQ-B.2.5, 4, 6 or 8 decks). **Calculated** works out the best play for the rules chosen, in the browser, by exact arithmetic over the shoe left after the player's two cards and the dealer's up card are removed; it is offered for any number of decks from 1 to 8 and for every rule the engine plays, and it never replaces the classic chart anywhere else in the app. Whichever is chosen is the chart the run's comparison line plays by, and the run says which it was. A calculated chart for rules the classic chart covers must agree with it in nearly every cell, and where it differs the two plays must be nearly tied in value: a test holds this, so the calculator is checked against the published chart and not only against itself. Measured on nine covered rule sets: 340 of 340 cells in eight of them, and 339 of 340 in the ninth, differing by 0.0009 of a bet. Rules the engine does not play at all (surrender, a dealer who does not peek, doubling on some totals only) are not offered until the engine does; that is engine work, listed as a later step. **Built 2026-10-16.** | DONE |
| REQ-B.11.27 | A mixed goal for the search | Avi, 2026-10-16: "both as options". The search can be told to chase a weighted mix of the three goals (days finished ahead, average result, how long the playing money lasts), with a weight of 0 to 10 for each. The score is the weighted average of the three after each is put on a 0-to-1 footing: days ahead as a share, the average result as a share of the starting money, and the hands survived as a share of the day. The weights are kept with the run. **Built 2026-10-16.** | DONE |
| REQ-B.11.17 | What a bust means with a freeze | The run ends when the playing amount cannot cover the smallest bet the policy would make. Frozen money is not at risk and is kept in the result: the graph shows playing and frozen as two layers, and the final result is their sum. The classic twin (REQ-B.11.12) uses the same policy and freeze, and ends on its own bust. **Built 2026-10-16.** | DONE |
| REQ-B.11.6 | Results are graphed, always against the classic | Every run is drawn with the classic chart's run beside it on one graph: bankroll over hands played, both lines, and the final result of each. Avi: "every manipulation that I do, you compare it with the classic ... I see how my updated policy ruined or maybe improved against the classical one." More graphs once the policy is known. The numbers behind each graph are shown, as on the history graph. **Built 2026-10-16.** | DONE |
| REQ-B.11.12 | The comparison is fair | The classic run and the run with overrides play the same shuffles in the same order, with the same rules, starting money and gambling policy, so the only difference between the two lines is the overridden cells. The classic run is made on every run, whether or not any cell was overridden. Each line ends on its own bust. **Built 2026-10-16.** | DONE |
| REQ-B.11.7 | Runs are kept | A finished run is stored with its conditions, overrides, seed and both results (the run and its classic twin), so it can be reopened and its settings reused. **Built 2026-10-16.** | DONE |
| REQ-B.11.8 | Reproducible | Every run records its random seed. The same conditions and seed give the same graph. **Built 2026-10-16.** | DONE |
| REQ-B.11.9 | Free, and no AI | Avi, 2026-10-16: the lab is free. Like the drill and the table, it calls no model and asks nothing of the gate. **Built 2026-10-16.** | DONE |
| REQ-B.11.10 | A long run never freezes the page | Every run, including many days and the search, shows progress, can be cancelled, and can be left running while the person looks at something else (REQ-B.11.23). Measured on a phone, not assumed. **Built 2026-10-16.** | DONE |
| REQ-B.11.11 | Phone first, full REST API | As Chapter 10: built at 390px first, and every model the lab owns has a DRF CRUD API (Rule 6). **Built 2026-10-16.** | DONE |

### 11.4 Decisions and open questions

Decided by Avi, 2026-10-16:

1. **Free** for everybody signed in (REQ-B.11.9).
2. **Up to 100,000 hands per run, ending early on bust** (REQ-B.11.1).
3. **Always compared with the classic chart**, on the same shuffles
   (REQ-B.11.6, REQ-B.11.12).
4. **A section of its own** in the app, not a page inside the simulator.

Still open:

1. **How long is a day.** Avi's original ceiling was 100,000 hands "until you
    bust". Thirty days of that is three million hands, which is fine for the
    worker but is not what an evening at a casino looks like. Assumed: hands
    per day is a setting, default 100,000, and a person who wants a realistic
    evening sets it to a few hundred.
2. **How many days.** Proposed ceiling 500 days per run, to be set after
    timing in a real browser.
3. **What the search may change first.** Proposed: the ladder and the freeze
    steps, then table overrides. Overrides multiply the search space, so they
    wait.

4. **Rules the chart does not cover.** The classic chart exists only for 4, 6
   or 8 decks, double on any two cards, a peeking dealer and no surrender
   (REQ-B.2.5, `strategy.supports`). Avi's "etc." probably includes a single
   deck, a deck or two, and a table with surrender. For those rules there is no
   classic chart to compare with, and the app refuses to invent one. Two
   options: the lab offers only the covered rules at first, or the lab works
   out the best play for any rule set itself, by exact calculation, and uses
   that as the classic chart. The second is more work and would also widen
   Practice. Assumed: the first, with the rest listed as a later sprint.
   **Avi to choose.**

5. **After the last freeze step.** Avi's default list ends at 2,000 and then
   "I play endlessly" until the 1,000 is lost. Assumed: once the list is used
   up, nothing more is frozen. The alternative is to repeat the last step. A
   setting for it costs one switch, so it is offered either way.
6. **"My updated policy."** The comparison against the classic (REQ-B.11.12)
   changes only the table overrides and shares the gambling policy. Comparing
   two gambling policies on the same shuffles (for example the ladder against a
   flat bet) is a natural second use, and is held until he asks for it.
7. **Fewer hands.** Assumed: fewer than 100,000 is allowed, 100,000 is the
   ceiling.
8. **How many runs a person keeps.** Proposed: 50. To be set after timing a
   real run.
