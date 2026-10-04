# improv: Backlog

> Tracks delivery of [spec.md](spec.md), on the data model in
> [data_model.md](data_model.md). Hierarchy: **Epic, Sprint, Feature.**
> Sprints trace to the spec chapter that defines them and to Avi's feature
> numbers (chapter 2).
>
> **Process weight, decided for this app:** a product with one user today and
> more later, so a real spec and backlog and tests for everything that can break
> silently, but no REQ-ID bookkeeping. The judge, the chart parser and the gate
> get the heaviest tests. Review cadence follows blackjack: Avi reviews **after
> every epic**, sprints land without stopping, scoped tests run before every
> commit, the full suite runs only when he asks. Nothing is pushed until he says
> "Push".
>
> **Dev first.** Everything is built and played on the local dev server. Epics 1,
> 3 and 4 cannot be accepted without Avi at his piano, because MIDI and timing
> cannot be verified from a chat; those sprints are marked **at the piano**.

---

## EPIC-I.1: The skeleton and the proof  `DONE`

**Goal:** the app exists behind its gate, and the one risky assumption (the piano
and the laptop talk, and timing is usable) is proved before anything is built on
it.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.1.1 | The Django app `improv`, own base template and English menu, mounted at `/improv/`; group `improv_players` created by migration; the gate (404 for anonymous, non-members, every URL); portal card `GROUP` plus `admin_bypass`; the gate-sweep test and the portal sweep still green | ch. 7, feature 23 | DONE 2026-10-04 |
| SPR-I.1.2 | **The spike, at the piano.** A bare page: Web MIDI in with timestamps mapped onto the `AudioContext` clock, an on-screen keyboard that lights from either source, a click track, and a readout of how far each note landed from the click. Run on Avi's piano and laptop; the result (numbers, any browser problem) is written into the spec before moving on | ch. 3, 4, 9, features 1, 5 | DONE 2026-10-04 |
| SPR-I.1.3 | Theory reference: `ChordQuality`, `Scale`, `ChordScale`, seeded once from a reviewed file, seed run twice in a test | ch. 4, 5, features 2, 11 | DONE 2026-10-04 |
| SPR-I.1.4 | The DRF base for the app: the gate as a permission class, read-only reference endpoints, `docs/improv/api.md` started, the "every model has an endpoint" test | ch. 7 | DONE 2026-10-04 |
| SPR-I.1.5 | The dashboard, generated from this backlog, with a test that fails when it drifts | Rule 4 | DONE 2026-10-04 |

**The load-bearing test of this epic** is the gate sweep: every route the app
registers, hit three ways, anonymous, non-member and member. It is written in
SPR-I.1.1, before there is anything behind the gate worth hiding.

---

## EPIC-I.2: The band and the charts  `DONE`

**Goal:** pick a progression, press play, and a steady band plays it in any key
and tempo. No judging yet.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.2.1 | The chart parser: bars, `%`, repeats, endings, key change, aliases, slash chords, first-error position; transposition. Pure JS with golden fixtures run under Node | ch. 3, feature 6 | DONE 2026-10-04 |
| SPR-I.2.2 | `Style`, `Progression` and `Tag` models, the starter grooves and the first progressions seeded, API for all three | ch. 3, features 5, 7 | DONE 2026-10-04 |
| SPR-I.2.3 | The band engine: look-ahead scheduler, synthesized drums, bass and comp, swing, exact timing; a style per genre starting with medium swing, then blues, bossa, pop ballad, rock, gospel | ch. 3, feature 5 | DONE 2026-10-04 |
| SPR-I.2.4 | The Play screen v0: chart with the bar lit, transport, count-in, loop a bar range, tempo, key, swing or straight, metronome-only, per-instrument mix | ch. 3, 8, feature 8 | DONE 2026-10-04 |
| SPR-I.2.5 | The library: all ~40 progressions seeded as generic patterns, browse by genre, tag and difficulty; the chart editor with live parse and the error where it is | ch. 8, features 6, 7 | DONE 2026-10-04 |
| SPR-I.2.6 | Output picker where the browser allows it; changing tempo and key at the next bar line | ch. 3 | DONE 2026-10-04 |

---

## EPIC-I.3: Reading the piano  `TODO`

**Goal:** the app knows what you are playing, names it, and knows your setup's
delay.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.3.1 | `Player` model and profile created on first visit; the Setup screen; MIDI input remembered and reconnected; hot-plug handled | ch. 4, 8, feature 23 | TODO |
| SPR-I.3.2 | Chord recognition: pitch classes, bass, slash chords, shell guesses with alternatives, fewer than three notes shown as notes. Golden fixtures under Node | ch. 4, feature 2 | TODO |
| SPR-I.3.3 | Scale hints: five pitch classes before a name, best fit first | ch. 4, feature 2 | TODO |
| SPR-I.3.4 | **At the piano.** Calibration: sixteen taps against the click, mean offset stored in `Player.latency_offset_ms`, spread shown, Bluetooth warning | ch. 4, 9, feature 14 | TODO |
| SPR-I.3.5 | The Reference screen: any chord or scale in any key lit on the keyboard | ch. 8, feature 11 | TODO |

---

## EPIC-I.4: Judging and takes  `TODO`

**Goal:** you play over the band and are told, live and at the end, how you did.
The most important epic in the app.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.4.1 | The judge as a pure function: chord sounding at a time (half a beat lookahead), the four classes, approach settling, timing metrics, the score for the first scoring kinds (chord tones on beats, scale only, free play). Golden fixtures run under Node, `judge_version` 1 | ch. 5, feature 13 | TODO |
| SPR-I.4.2 | Live feedback on the Play screen: key colours per note, the timing strip, the recognized chord, all driven by the same judge | ch. 5, 8, features 13, 14 | TODO |
| SPR-I.4.3 | `PracticeSession` and `Take`: the page records events and posts the take; snapshots of chart, key, tempo; server-side range checks; API | ch. 5, 6, feature 15 | TODO |
| SPR-I.4.4 | Saved takes and replay over the same band through the demo output (MIDI out to the piano or a plain tone); the Takes screen | ch. 6, 8, feature 15 | TODO |
| SPR-I.4.5 | The remaining scoring kinds: guide tones, approach notes, rhythm motif, call and response; comping voicings is v2 | ch. 5, features 18, 19 | TODO |
| SPR-I.4.6 | **At the piano.** Avi plays real takes; the judge is tuned against what he knows he did right and wrong, and the fixtures grow from his cases | ch. 5, 9 | TODO |

---

## EPIC-I.5: Lessons and the game layer  `TODO`

**Goal:** a path to follow and a reason to come back tomorrow.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.5.1 | `Phrase`, `Lesson`, `Exercise` models, API, the lesson page doing Read, Hear, Play | ch. 6, features 9, 10 | TODO |
| SPR-I.5.2 | `Completion` created by the server from a passing take; XP from the exercise row; level and unlock as reads | ch. 5, 6, features 19, 20 | TODO |
| SPR-I.5.3 | The six v1 lessons, AI-drafted, each read and corrected by Avi before it is published, seeded once with `authorship` set truthfully | ch. 6, feature 9 | TODO |
| SPR-I.5.4 | The practice timer, daily goal, the practice log, the streak with its timezone rule | ch. 6, features 16, 21 | TODO |
| SPR-I.5.5 | The daily workout: three picks, stable for the day | ch. 6, feature 21 | TODO |
| SPR-I.5.6 | The weakness report with its twenty-note floor; standalone challenges and personal bests | ch. 6, features 17, 19 | TODO |

---

## EPIC-I.6: Today, polish, and getting it live for Avi  `TODO`

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.6.1 | The Today and Progress screens | ch. 8 | TODO |
| SPR-I.6.2 | Pruning of unkept takes on the next save, with its test; the full API documented; the seed commands wired into the deploy with the same `\|\| true` pattern as the other apps | ch. 6, 7 | TODO |
| SPR-I.6.3 | Scoped migrate, push on Avi's word, live check of a page and an API route the old build could not have, and a check that a non-member still gets 404 on the live site | Rule 5 | TODO |

---

## After v1, in the order Avi sees fit

Ear training inside lessons (12), the weakness-driven extras, ear and speed
mini-games (22) with `DrillAttempt`, voicings and comping lessons, play-along as
its own mode, then the product layer: accounts beyond Avi, subscription, sharing,
teacher mode, a phone version, Hebrew. The server-side judge is a prerequisite
for any leaderboard or paid tier.
