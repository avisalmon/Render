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

## EPIC-I.3: Reading the piano  `IN PROGRESS`

**Goal:** the app knows what you are playing, names it, and knows your setup's
delay.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.3.1 | `Player` model and profile created on first visit; the Setup screen; MIDI input remembered and reconnected; hot-plug handled | ch. 4, 8, feature 23 | DONE 2026-10-05 |
| SPR-I.3.2 | Chord recognition: pitch classes, bass, slash chords, shell guesses with alternatives, fewer than three notes shown as notes. Golden fixtures under Node | ch. 4, feature 2 | DONE 2026-10-05 |
| SPR-I.3.3 | Scale hints: five pitch classes before a name, best fit first | ch. 4, feature 2 | DONE 2026-10-05 |
| SPR-I.3.4 | **At the piano.** Calibration: sixteen taps against the click, mean offset stored in `Player.latency_offset_ms`, spread shown, Bluetooth warning. Built and green 2026-10-05; stays IN PROGRESS until Avi taps it on his own piano | ch. 4, 9, feature 14 | IN PROGRESS |
| SPR-I.3.5 | The Reference screen: any chord or scale in any key lit on the keyboard | ch. 8, feature 11 | DONE 2026-10-05 |

---

## EPIC-I.4: Judging and takes  `IN PROGRESS`

**Goal:** you play over the band and are told, live and at the end, how you did.
The most important epic in the app.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.4.1 | The judge as a pure function: chord sounding at a time (half a beat lookahead), the four classes, approach settling, timing metrics, the score for the first scoring kinds (chord tones on beats, scale only, free play). Golden fixtures run under Node, `judge_version` 1 | ch. 5, feature 13 | DONE 2026-10-05 |
| SPR-I.4.2 | Live feedback on the Play screen: key colours per note, the timing strip, the recognized chord, all driven by the same judge | ch. 5, 8, features 13, 14 | DONE 2026-10-05 |
| SPR-I.4.3 | `PracticeSession` and `Take`: the page records events and posts the take; snapshots of chart, key, tempo; server-side range checks; API | ch. 5, 6, feature 15 | DONE 2026-10-05 |
| SPR-I.4.4 | Saved takes and replay over the same band through the demo output (MIDI out to the piano or a plain tone); the Takes screen | ch. 6, 8, feature 15 | DONE 2026-10-05 |
| SPR-I.4.5 | The remaining scoring kinds: guide tones, approach notes, rhythm motif, call and response; comping voicings is v2 | ch. 5, features 18, 19 | DONE 2026-10-05 |
| SPR-I.4.6 | **At the piano.** Avi plays real takes; the judge is tuned against what he knows he did right and wrong, and the fixtures grow from his cases | ch. 5, 9 | TODO |

---

## EPIC-I.5: Lessons and the game layer  `DONE`

**Goal:** a path to follow and a reason to come back tomorrow.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.5.1 | `Phrase`, `Lesson`, `Exercise` models, API, the lesson page doing Read, Hear, Play | ch. 6, features 9, 10 | DONE 2026-10-05 |
| SPR-I.5.2 | `Completion` created by the server from a passing take; XP from the exercise row; level and unlock as reads | ch. 5, 6, features 19, 20 | DONE 2026-10-05 |
| SPR-I.5.3 | The six v1 lessons, AI-drafted, each read and corrected by Avi before it is published, seeded once with `authorship` set truthfully | ch. 6, feature 9 | DONE 2026-10-05 |
| SPR-I.5.4 | The practice timer, daily goal, the practice log, the streak with its timezone rule | ch. 6, features 16, 21 | DONE 2026-10-05 |
| SPR-I.5.5 | The daily workout: three picks, stable for the day | ch. 6, feature 21 | DONE 2026-10-05 |
| SPR-I.5.6 | The weakness report with its twenty-note floor; standalone challenges and personal bests | ch. 6, features 17, 19 | DONE 2026-10-05 |

---

## EPIC-I.6: Today, polish, and getting it live for Avi  `IN PROGRESS`

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.6.1 | The Today and Progress screens | ch. 8 | DONE 2026-10-05 |
| SPR-I.6.2 | Pruning of unkept takes on the next save, with its test; the full API documented; the seed commands wired into the deploy with the same `\|\| true` pattern as the other apps | ch. 6, 7 | DONE 2026-10-05 |
| SPR-I.6.3 | Scoped migrate, push on Avi's word, live check of a page and an API route the old build could not have, and a check that a non-member still gets 404 on the live site. Ready 2026-10-05: migrations 0004 to 0007 match the models, the scoped migrate and seeds run clean on dev, `collectstatic` passes with `DEBUG=False`, and the new pages and routes are gated (tests/test_spri_6_3.py). Stays IN PROGRESS until Avi says Push and the live check is made | Rule 5 | IN PROGRESS |

---

## EPIC-I.7: The piano is the remote, and every screen fits the window  `DONE`

Avi, 2026-10-06, said as a general rule for the whole app: it is a PC app used at the piano, so all
information fits one screen with no scrolling, and every start or stop button can be pressed from
the piano, starting with the top key of the 88. Spec: ch. 8, "Two standing rules for every screen".

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.7.1 | The control keys: `control.js` (C8 primary, B7 secondary, A#7 tertiary, note-on only, 400 ms debounce, pick the first visible enabled button), the page layer that listens on every MIDI input, the key printed on each marked button, and the control zone left out of judging, chord naming and takes. Node tests, browser test with a faked piano | ch. 4, 8 | DONE 2026-10-07 |
| SPR-I.7.2 | Mark every screen's buttons with their action: Play, Lesson, Today, Takes, Setup, Editor, Spike, and the first item of the lists (lessons, challenges, practice, library) | ch. 8 | DONE 2026-10-07 |
| SPR-I.7.3 | The one-screen shell and the Play, Lesson and Takes layouts | ch. 8 | DONE 2026-10-07 |
| SPR-I.7.4 | One-screen layouts for Today, Lessons, Challenges, Library, Editor, Practice, Progress, Reference, Setup and Spike | ch. 8 | DONE 2026-10-07 |
| SPR-I.7.5 | The guard: every screen at 1280 by 720 and 1920 by 1080 with real data does not scroll; ready to push | ch. 8 | DONE 2026-10-07 |

---

## EPIC-I.8: The scales and chords trainer  `DONE 2026-10-07`

Avi, 2026-10-07: "I want to focus on chord training capabilities." A scale trainer (two hands in tempo, three
levels, accuracy graded, fingering shown) and a chord trainer (every chord of a key and its positions, named by
letter, timed, with a hint), in circle-of-fifths order from C (G at first, C after the live check), tempo default 60 and remembered. Spec: ch. 10.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.8.1 | `ScaleFingering` model and seed (checked against a published chart), `Player.trainer_tempo`, the scale layout in `scale.js` (steps, ranges, fingering for both hands up and down, key spelling), Node and Django tests | ch. 10 | DONE 2026-10-07 |
| SPR-I.8.2 | The scale judge (pure, in `scale.js`), `ScaleRun` with its endpoint, tests for pitch, timing, extras and the pass line | ch. 5, 10 | DONE 2026-10-07 |
| SPR-I.8.3 | The scales screen: key, level, tempo (remembered), count-in, fingering strip, on-screen keyboard, live judge, result, C8 Start, one screen | ch. 8, 10 | DONE 2026-10-07 |
| SPR-I.8.4 | The chord pool, positions and matcher (pure, `drill.js`), the circle order, `DrillAttempt` with its endpoint | ch. 10 | DONE 2026-10-07 |
| SPR-I.8.5 | The chords screen: Learn, Drill, Circle, the timer, wrong chord shown, Hint (B7), Skip (A#7), one screen | ch. 8, 10 | DONE 2026-10-07 |
| SPR-I.8.6 | The trainer read (best per key, slowest chords, weakest keys) shown on both screens, menu items, both screens in the layout guard, scoped regression, ready to push | ch. 7, 8, 10 | DONE 2026-10-07 |
| SPR-I.8.7 | Avi's live check: circle starts at C, keep going through 2, 3, 4 octaves, a lower and choosable start octave, the header shows the key heard and the MIDI access is kept, a quieter and remembered Play mix | ch. 10 | DONE 2026-10-07 |
| SPR-I.8.8 | Reference: running-scale fingering for both hands, and chord menu lines like "Cmaj7  -  Major seventh" | ch. 10 | DONE 2026-10-07 |

---

## After v1, in the order Avi sees fit

Ear training inside lessons (12), the weakness-driven extras, ear and speed
mini-games (22) on the `DrillAttempt` table that Epic I.8 builds, voicings and comping lessons, play-along as
its own mode, then the product layer: accounts beyond Avi, subscription, sharing,
teacher mode, a phone version, Hebrew. The server-side judge is a prerequisite
for any leaderboard or paid tier.
