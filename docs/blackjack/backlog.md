# blackjack — Backlog

> Tracks delivery of [spec.md](spec.md), on the data model in
> [data_model.md](data_model.md). Hierarchy: **Epic → Sprint → Feature**.
> Features trace to `REQ-B.*`.
>
> **Review cadence, Avi 2026-10-01:** he reviews **after every epic**, not every
> sprint. Sprints land without stopping. Scoped tests run before every commit;
> the full suite runs only when he asks for it.

---

## EPIC-B.1 — The spine  `DONE 2026-10-02, awaiting review`

**Goal:** the app exists, has its own chrome, knows the rules, and can show a
correct cheat sheet. Nothing is drilled yet.

The point of doing the sheet before the drill is that the sheet is the chart
made visible. If the chart is wrong, a cheat sheet shows it immediately, while
a drill hides it behind a hand nobody checks.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.1.1 | The Django app, its own base template and nav, mounted at `/blackjack/`, plus the portal card so it is reachable | REQ-B.10.5, REQ-B.6.1 | **DONE 2026-10-01** |
| SPR-B.1.2 | `RuleSet` and `Player`, the default preset, the rule-picker screen | REQ-B.2.1, B.2.2, B.2.3 | **DONE 2026-10-01** |
| SPR-B.1.3 | `Chart` and `Cell`, seeded once, all 340 decisions with their reasons | REQ-B.2.5, B.3.4 | **DONE 2026-10-01** |
| SPR-B.1.4 | The cheat sheet screen: split views, tap a cell for its reason | REQ-B.3.1 to B.3.5 | **DONE 2026-10-01** |
| SPR-B.1.5 | The DRF API over everything so far | REQ-B.10.6 | **DONE 2026-10-02** |

**The load-bearing test of this epic** is REQ-B.3.5: what the sheet renders and
what the drill will later answer come from the same rows, proven rather than
claimed. It is written in SPR-B.1.3, before the screen that it guards exists.

---

## EPIC-B.2 — The drill  `DONE 2026-10-02`

**Goal:** the product. A real table, a decision, the answer, and a record of it.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.2.1 | The table: cards, casino deal order, animation, reduced motion, no sound | REQ-B.4.1, B.4.5, B.4.7, B.4.8 | **DONE 2026-10-02** |
| SPR-B.2.2 | Decide then learn: four buttons, the answer and its reason after | REQ-B.4.2, B.4.3 | **DONE 2026-10-02** |
| SPR-B.2.3 | `Attempt` recorded per hand, judged on the server | REQ-B.4.4, B.6.3 | **DONE 2026-10-02** |
| SPR-B.2.4 | Offline queue: attempts survive a tunnel and sync after | REQ-B.4.6 | **DONE 2026-10-02** |
| SPR-B.2.5 | Phone measurement pass: 390/1024/1280, thumb reach, no idle work | REQ-B.10.1 to B.10.4 | **DONE 2026-10-02** |

---

## EPIC-B.3 — Progress  `DONE 2026-10-02`

**Goal:** the person can see what they are good at, what they are not, and
whether they are improving. All free, all deterministic.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.3.1 | `Mastery`, updated per attempt, plus the rebuild command and its test | REQ-B.5.2, B.5.7 | **DONE 2026-10-02** |
| SPR-B.3.2 | The mastery grid: 340 cells, four states, weakest named | REQ-B.5.2 | **DONE 2026-10-02** |
| SPR-B.3.3 | History: the hands, the notes, the graph on one screen | REQ-B.5.1 | **DONE 2026-10-02** |
| SPR-B.3.4 | `Session`, named, and reset meaning a fresh one | REQ-B.5.5, B.5.6 | **DONE 2026-10-02** |
| SPR-B.3.5 | `BatchNote` every twenty hands, written deterministically | REQ-B.5.3 | **DONE 2026-10-02** |
| SPR-B.3.6 | The accuracy graph | REQ-B.5.4 | **DONE 2026-10-02** |
| SPR-B.3.7 | Recently missed cells come back | REQ-B.5.7 | **DONE 2026-10-02** |

---

## EPIC-B.4 — The gate  `DONE 2026-10-02`

**Goal:** paid access exists and is provable. No AI yet; this epic is the lock,
not what is behind it.

Deliberately before the AI features. A gate built after the thing it guards is
a gate with a hole in it, because the paths were written while nothing was
stopping them.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.4.1 | `Coupon` and `Grant`, and `ai_is_open` asking babook's `Entitlement` | REQ-B.6.2, B.6.4, B.6.5 | **DONE 2026-10-02** |
| SPR-B.4.2 | The trial: thirty minutes from first use | REQ-B.6.3 | **DONE 2026-10-02** |
| SPR-B.4.3 | Redemption by link and by QR | REQ-B.6.4 | **DONE 2026-10-02** |
| SPR-B.4.4 | The sweep: every paid door enumerated from the URL conf, each refusing a free account | REQ-B.6.6 | **DONE 2026-10-02** |
| SPR-B.4.5 | Expiry closes the paid surfaces and loses nothing | REQ-B.6.7 | **DONE 2026-10-02** |
| SPR-B.4.6 | Admin: generate coupons, see activity, root only, no private hands shown | REQ-B.7.1 to B.7.4 | **DONE 2026-10-02** |

---

## EPIC-B.5 — The teacher  `DONE 2026-10-02`

**Goal:** what people are paying for.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.5.1 | Adaptive drilling, by the scheduler, deterministic | REQ-B.8.2 | **DONE 2026-10-02** |
| SPR-B.5.2 | AI feedback over this person's own attempts, through babook's client | REQ-B.8.1, B.8.5, B.8.6 | **DONE 2026-10-02** |
| SPR-B.5.3 | Deeper explanation on demand | REQ-B.8.3, B.8.6 | **DONE 2026-10-02** |
| SPR-B.5.4 | Mnemonics for the cells this person keeps missing | REQ-B.8.4, B.8.6 | **DONE 2026-10-02** |

---

## EPIC-B.6 — The table with other people  `LATER`

The simulator, playing with friends, the champion league. Not designed until
the core works. REQ-B.9.*.

---

## EPIC-B.7 — the social half  `TODO`

**Goal:** the three things that bring somebody back on a Tuesday. Free, per
Avi on 2026-10-02, reversing his own call of the day before.

It is its own epic rather than a sprint inside EPIC-B.5 because that epic's
goal is "what people are paying for", and a free sprint sitting inside it
would make the goal a lie. Moving it keeps each epic's sentence true.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.7.1 | Streaks: days in a row, and what breaks one | REQ-B.5.8 | **DONE 2026-10-02** |
| SPR-B.7.2 | Sharing a result, as a link somebody can open | REQ-B.5.8 | **DONE 2026-10-02** |
| SPR-B.7.3 | Following, **reading babook's `Follow`**, never a second graph | REQ-B.5.8, Q2 | TODO |

**SPR-B.7.2, what was decided.** A shared link is a frozen snapshot, not a
live page. Recomputing on read is the obvious implementation and it turns one
shared evening into a standing feed of somebody's results to a group chat they
have stopped thinking about. `blackjack/sharing.py` decides once what leaves
the account, the public page renders that dict and reaches through to nothing,
so a field added to `Player` next month cannot appear on a link shared last
month.

It is the only screen in the app a signed-out stranger can open. It has to be:
a link that asks you to sign in before it shows you anything is a sign-up wall,
and nobody forwards one of those. The name on it is the first name babook
holds and nothing else, because usernames here are email addresses. Links are
revocable and the row survives revocation.

**SPR-B.7.1, what was decided.** A streak runs up to the last day played and
stays alive through today, so somebody who played yesterday and opens the app
at nine in the morning still sees their run rather than a zero. Counting
naively is the obvious implementation and it greets a returning user by telling
them they lost the thing the app is asking them to keep. The badge is muted and
dashed while today is unplayed and gold once it is: the app marks the open day
by looking different, and never writes a sentence nagging about it.

Derived from `Attempt` every time, never stored, like everything else here. A
stored counter drifts the first time the drill's offline queue posts yesterday's
hands after today's, which it does by design.

---

## Questions, all answered

| # | Question | Answer |
|---|---|---|
| Q1 | Charts as static data or rows? | Rows. "Charts are tables", 2026-10-01. Rule 1 stands, no exception. |
| Q2 | Reuse babook's `Follow`? | **Reuse**, 2026-10-02. Following a person is identity, which babook owns. |
| Q3 | Streaks, sharing, following paid? | **Free**, 2026-10-02, reversing the 2026-10-01 call. |
| Q4 | The name? | `blackjack` at `/blackjack/`, 2026-10-01. |
