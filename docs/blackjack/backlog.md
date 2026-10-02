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

## EPIC-B.3 — Progress  `TODO`

**Goal:** the person can see what they are good at, what they are not, and
whether they are improving. All free, all deterministic.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.3.1 | `Mastery`, updated per attempt, plus the rebuild command and its test | REQ-B.5.2, B.5.7 | **DONE 2026-10-02** |
| SPR-B.3.2 | The mastery grid: 340 cells, four states, weakest named | REQ-B.5.2 | **DONE 2026-10-02** |
| SPR-B.3.3 | History, and replaying a hand | REQ-B.5.1 |
| SPR-B.3.4 | `Session`, named, and reset meaning a fresh one | REQ-B.5.5, B.5.6 |
| SPR-B.3.5 | `BatchNote` every twenty hands, written deterministically | REQ-B.5.3 |
| SPR-B.3.6 | The accuracy graph | REQ-B.5.4 |
| SPR-B.3.7 | Recently missed cells come back | REQ-B.5.7 | **DONE 2026-10-02** |

---

## EPIC-B.4 — The gate  `TODO`

**Goal:** paid access exists and is provable. No AI yet; this epic is the lock,
not what is behind it.

Deliberately before the AI features. A gate built after the thing it guards is
a gate with a hole in it, because the paths were written while nothing was
stopping them.

| Sprint | What | Traces |
|---|---|---|
| SPR-B.4.1 | `Coupon` and `Grant`, and `ai_is_open` asking babook's `Entitlement` | REQ-B.6.2, B.6.4, B.6.5 |
| SPR-B.4.2 | The trial: thirty minutes from first use | REQ-B.6.3 |
| SPR-B.4.3 | Redemption by link and by QR | REQ-B.6.4 |
| SPR-B.4.4 | The sweep: every AI entry point enumerated from the URL conf, each refusing a free account | REQ-B.6.6 |
| SPR-B.4.5 | Expiry closes the paid surfaces and loses nothing | REQ-B.6.7 |
| SPR-B.4.6 | Admin: generate coupons, see activity, root only, no private hands shown | REQ-B.7.1 to B.7.4 |

---

## EPIC-B.5 — The teacher  `TODO`

**Goal:** what people are paying for.

| Sprint | What | Traces |
|---|---|---|
| SPR-B.5.1 | Adaptive drilling, by the scheduler, deterministic | REQ-B.8.2 |
| SPR-B.5.2 | AI feedback over this person's own attempts, through babook's client | REQ-B.8.1, B.8.5 |
| SPR-B.5.3 | Deeper explanation on demand | REQ-B.8.3 |
| SPR-B.5.4 | Mnemonics for the cells this person keeps missing | REQ-B.8.4 |
| SPR-B.5.5 | Streaks, sharing, following | REQ-B.8.7 |

---

## EPIC-B.6 — The table with other people  `LATER`

The simulator, playing with friends, the champion league. Not designed until
the core works. REQ-B.9.*.

---

## Open questions

| # | Question | Blocks |
|---|---|---|
| Q2 | Reuse babook's `Follow`, or keep our own? | SPR-B.5.5 |
| Q3 | Free tier genuinely without streaks, sharing and following? | SPR-B.5.5 |

Answered 2026-10-01: **Q1**, charts are database tables, so Rule 1 stands with
no exception; **Q4**, the app is `blackjack` at `/blackjack/`.
