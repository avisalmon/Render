# blackjack — Data model

> **Status: proposed 2026-10-01, waiting for Avi's approval.** Step 3 of the
> kickoff sequence in [building_an_app.md](../building_an_app.md), and the step
> that waits: everything else gets built on this, and getting the shape wrong
> here is expensive to unwind later. No code exists yet.

---

## The one sentence version

**Everything in this app is a read over one table.** `Attempt` is one decision a
person made at one dealt situation under one rule set, and the statistics, the
history, the mastery grid, the trend notes and the AI coaching are all views of
it. Nothing else stores a second copy of "how is this person doing", because a
second copy drifts, and the day it drifts the app is lying to a learner about
their own progress.

---

## 1. The rules a hand was dealt under

### `RuleSet`

The table's rules. A model rather than a settings blob, for one reason that is
worth stating plainly: **the correct play only exists relative to a rule set.**
Flip dealer-stands-soft-17 to hit and a batch of chart cells change. An attempt
stored without its rules is an attempt nobody can ever judge again, which would
quietly poison the statistics, the mastery grid and every claim the app makes
about whether somebody is improving.

| Field | Type | Notes |
|---|---|---|
| `name` | char | "Vegas 6 deck", or a person's own label |
| `decks` | int | 1, 2, 4, 6, 8 |
| `dealer_hits_soft_17` | bool | the single most chart-changing rule |
| `double_any_two` | bool | otherwise 9/10/11 only |
| `double_after_split` | bool | DAS |
| `max_splits` | int | default 4 hands |
| `resplit_aces` | bool | |
| `hit_split_aces` | bool | |
| `surrender` | choice | none / late / early |
| `blackjack_pays` | choice | `3:2` or `6:5` |
| `dealer_peeks` | bool | |
| `is_preset` | bool | shipped presets vs a person's own |
| `created_by` | FK User, null | null for presets |

**The default**, and the common case so nobody must fill in a form to play:
6 decks, dealer stands on soft 17, double any two, DAS allowed, split to 4,
aces split once and get one card, no surrender, 3:2, dealer peeks.

**Immutability.** A `RuleSet` that any `Attempt` points at is never edited in
place. Changing your table makes a new row. Otherwise editing a rule silently
rewrites the correct answer for thousands of hands already played.

---

## 2. The person

### `Player`

The app's own profile, one-to-one with the shared `User`. Methodology Rule 2:
an app never adds fields to babook's user, it keeps its own row.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOne User | the shared account |
| `rule_set` | FK RuleSet | the table they are currently playing |
| `first_used_at` | datetime, null | **set once, on the first drilled hand.** The 30-minute trial is measured from here, not from signup, so somebody who signs up and returns on Thursday still gets their half hour |
| `created_at` | datetime | |

---

## 3. The heart of it

### `Attempt`

One decision. Written once, never updated. Everything else is a read over this.

| Field | Type | Notes |
|---|---|---|
| `player` | FK Player | |
| `session` | FK Session, null | see §5 |
| `rule_set` | FK RuleSet | what was correct *then* |
| `cell_kind` | choice | `hard` / `soft` / `pair` |
| `cell_player` | int | the total for hard/soft, the rank for a pair |
| `cell_dealer` | int | dealer upcard, 2..11 where 11 is an ace |
| `player_cards` | json | the actual cards dealt, for replaying the hand in history |
| `chosen` | choice | H / S / D / P |
| `correct` | choice | H / S / D / P |
| `correct_fallback` | choice | what to do when the chosen action is unavailable, see below |
| `is_correct` | bool | denormalised from chosen == correct, because every query wants it |
| `answer_ms` | int | how long they took. Hesitation is a weak cell that has not failed yet |
| `source` | choice | `random` / `adaptive` / `simulator` |
| `created_at` | datetime | |

**`cell_kind` + `cell_player` + `cell_dealer` is the cell key**, and it is the
join between a hand somebody played and the 270 decisions basic strategy
contains. It is stored on the row rather than derived from the cards, because
deriving it later means re-implementing the derivation and getting it subtly
different.

**Why `correct_fallback` exists.** `D` is ambiguous and the ambiguity bites
exactly where beginners live. On hard 9 it means "double, and if you may not,
hit". On soft 18 against a 3 it means "double, and if you may not, **stand**".
Same letter, opposite fallback, and the fallback is the case after a split or
with three cards. Four letters stay on screen; the truth underneath is richer.

---

## 4. Mastery, and what comes next

### `Mastery`

One row per person per cell: at most 270 rows each. This is both the mastery
grid Avi approved and the scheduler state for spaced repetition.

| Field | Type | Notes |
|---|---|---|
| `player` | FK Player | |
| `cell_kind`, `cell_player`, `cell_dealer` | | the same key as `Attempt` |
| `seen` | int | |
| `correct` | int | |
| `streak` | int | consecutive correct, reset by a miss |
| `last_seen_at` | datetime | |
| `due_at` | datetime | when this cell should come back |
| `strength` | float | the interval multiplier; grows when right, collapses when wrong |

Unique together on player + the three key fields.

**Why a table and not a query.** Everything except `due_at` and `strength` is
derivable from `Attempt`, and those two are not: they are *scheduling state*,
which depends on the order things happened and cannot be recomputed from
counts. Keeping the counts here too is a deliberate, named denormalisation so
the grid renders in one query rather than 270. `Attempt` stays the truth; this
is a cache plus a scheduler, and a management command can rebuild the cached
half from `Attempt` at any time. **That rebuild command is a test, not a
promise.**

**What free and paid get from the same table.** Free: the grid, and recently
missed cells coming back. Paid: the real scheduler, `due_at` driving selection.
The adaptation itself is arithmetic, not a model call, so it is instant and
costs nothing per hand.

---

## 5. Sessions and notes

### `Session`

A named run of practice, so somebody can drill soft hands for ten minutes
without polluting their lifetime numbers, and so "reset my stats" means
starting fresh rather than destroying history.

| Field | Type | Notes |
|---|---|---|
| `player` | FK Player | |
| `name` | char | "soft hands", "before Vegas" |
| `started_at`, `ended_at` | datetime | |

### `BatchNote`

The note every twenty hands. Stored rather than computed on the fly, because
the note is a thing a person was told at a moment, and the trend it describes
only makes sense against the numbers as they were then.

| Field | Type | Notes |
|---|---|---|
| `player` | FK Player | |
| `session` | FK Session, null | |
| `from_attempt`, `to_attempt` | FK Attempt | the batch's edges |
| `accuracy` | float | this batch |
| `previous_accuracy` | float, null | the batch before, for the trend |
| `weakest_cells` | json | the cells that cost the most in this batch |
| `text` | text | |
| `is_ai` | bool | **false for free, true for paid.** The same model, two writers |

---

## 6. Paid access

### `Coupon`

Bearer, one-time, shareable by WhatsApp link or QR.

| Field | Type | Notes |
|---|---|---|
| `code` | char, unique, indexed | what goes in the link and the QR |
| `days` | int | default 7 |
| `label` | char | Avi's note to himself about who it was for |
| `created_by` | FK User | |
| `created_at` | datetime | |
| `redeemed_by` | FK User, null | **null means unspent.** The first account to redeem claims it |
| `redeemed_at` | datetime, null | |

### `Grant`

A window of AI access. **The trial and the coupon are the same thing**, which
is why there is one model and not two: a grant with a source and an end.

| Field | Type | Notes |
|---|---|---|
| `player` | FK Player | |
| `source` | choice | `trial` (30 minutes, created on first use) / `coupon` / `gift` |
| `coupon` | FK Coupon, null | |
| `starts_at`, `ends_at` | datetime | |

**The subscription is not here, on purpose.** babook owns `Entitlement`, and
Avi intends one payment to eventually cover every app on the site. This app
asks babook and stores nothing, so that change costs nothing here.

### The gate

One function, `blackjack/access.py`:

```
ai_is_open(user) -> (bool, reason)
    subscriber, asked of babook's Entitlement
    or any Grant where starts_at <= now < ends_at
```

Every AI path asks it. Because the free product contains no AI at all, this is
the only gate in the app that matters, and it should be the most tested thing
in the codebase: a sweep proving that every AI entry point, page and API alike,
refuses a free account, with the test enumerating the entry points from the
URL conf rather than from a list somebody maintains by hand.

---

## 7. Sketched, not modelled yet

Named so the shape is known, deliberately not designed until the core works.

- **Simulator**: a played round has a bet, an outcome and a payoff, and each
  decision inside it is an ordinary `Attempt` with `source="simulator"`. Play
  money only, see the spec's refusals.
- **Play with friends**: a room, seats, a shared shoe.
- **Champion league**: a season and an entry. **Ranked by decision accuracy,
  never by chips won.** Ranking by winnings ranks luck, and a leaderboard that
  rewards a hot shoe teaches the opposite of the product.
- **Following**: Q2 in the spec. babook already has a `Follow` graph; this app
  should read it rather than grow a second one, pending Avi's answer.

---

## 8. The charts themselves

Avi, 2026-10-01, asked whether the charts ship as static data instead of rows:

> "Charts are tables."

So **Rule 1 stands and there is no exception to write down.** The chart is
database rows, and the page ships a serialised copy of the one chart it needs
to the browser, which is what "all in js and ready data" asked for. One source,
two readers.

### `Chart`

One chart is the full answer for one rule set.

| Field | Type | Notes |
|---|---|---|
| `rule_set` | FK RuleSet | what makes this chart correct |
| `source` | char | where the chart came from, e.g. a published table or a solver run, so a cell can be defended |
| `created_at` | datetime | |

### `Cell`

One of the 270 decisions.

| Field | Type | Notes |
|---|---|---|
| `chart` | FK Chart | |
| `kind` | choice | `hard` / `soft` / `pair` |
| `player` | int | total, or the rank for a pair |
| `dealer` | int | 2..11, where 11 is an ace |
| `action` | choice | H / S / D / P |
| `fallback` | choice | what to do when the action is unavailable (§3) |
| `reason` | text | the canned explanation shown free, after every hand |

Unique together on chart + kind + player + dealer.

**Seeded once, never resynced.** The methodology's costliest recorded mistake
was a seed command wired to run on every deploy that wholesale replaced rows
from a file. Here the import checks before creating, leaves existing rows
alone, says so in its output, and a test runs it twice and asserts the second
run changes nothing.

**Why this is better than a file, now that it is written down.** A chart in the
database can be corrected without a deploy, can carry its source per cell, can
be diffed when a rule set changes, and is reachable from the admin. And the
promise in spec §1.5 gets stronger rather than weaker: the cheat sheet screen
and the drill's correct answer are literally the same rows, and the test that
proves it compares what the screen renders against what the API returns for the
same cell.

**How it reaches the browser.** The drill page serialises its chart into the
page payload. The client then answers instantly and offline, and the server
never needs asking what the right play was. The serialiser is one function and
is covered by the same equality test, so a chart that renders one way and
serialises another fails rather than teaching somebody the wrong play.
