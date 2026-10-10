# improv: Data model

> **Status: approved by Avi, 2026-10-04.** Step 3 of the kickoff sequence in
> [building_an_app.md](../building_an_app.md). The four open points in section
> 11 are answered. No code exists yet. Two fields were added after approval,
> `Player.demo_output` and `Player.timezone`, because the spec chapters needed
> them; both are marked below.

---

## The one sentence version

**Everything the person does is a `Take`, and everything the app tells them
about their playing is a read over takes.** The streak, the XP, the level, which
lessons are unlocked, the weakness report and the daily workout are all
computed from takes and completions. Nothing stores a second copy of "how is
this person doing", because a second copy drifts, and the day it drifts the app
is lying to a learner about their own progress. (Same lesson as blackjack's
`Attempt`.)

The other half of the app is content: chords, scales, band grooves, chord
charts, lessons. That is all rows too, seeded once and editable afterwards.

---

## 0. Who may open it

Not a model, but it shapes the models, so it is stated first.

- **Changed 2026-10-08:** the app is open to anyone who signs in, free. The check is one function: signed in.
  The group `improv_players` and the 404-for-strangers design (as first approved) are gone; a visitor
  sees improv's own front door and the API answers a visitor with 401/403.
- babook's portal lists it with `audience=EVERYONE`, `listed=True, card_admin_only=True`: the card is shown to the owner only, the link is shared. A person keeps at most 1000 of their own rows of each kind (the owner is unlimited).
- Every API endpoint sits behind the same check; a person's own rows are filtered to them.

---

## 1. Music theory reference (seeded once, read by everything)

The chord recognizer, the live feedback, the reference screens and the lessons
all ask the same questions: what notes are in Dm7, which scale fits it, is this
note a chord tone. If those answers live in three places they disagree, so they
live in these three tables and nowhere else.

### `ChordQuality`

| Field | Type | Notes |
|---|---|---|
| `symbol` | char, unique | `m7`, `maj7`, `7`, `m7b5`, `dim7`, `sus4`, `7alt` ... |
| `name` | char | "minor seventh" |
| `intervals` | JSON list of ints | semitones above the root, `[0,3,7,10]` |
| `roles` | JSON map | semitone to role: `{"0":"root","3":"third","10":"seventh"}`; the guide tones are the third and seventh |
| `aliases` | JSON list of strings | `["min7","-7","mi7"]`, read by the chart parser and the recognizer |
| `family` | choice | major / minor / dominant / diminished / half-diminished / suspended / augmented |
| `sort_order` | int | |

About 25 rows.

### `Scale`

| Field | Type | Notes |
|---|---|---|
| `name` | char | "Dorian" |
| `slug` | slug, unique | |
| `intervals` | JSON list of ints | `[0,2,3,5,7,9,10]` |
| `family` | choice | major modes / melodic minor modes / harmonic minor modes / pentatonic / blues / symmetric |
| `parent_scale` | FK self, null | Dorian's parent is Major |
| `mode_number` | int, null | Dorian is mode 2 |

### `ChordScale`

Which scales fit which chord quality. This is what makes "scale tone or outside
note" a lookup instead of an opinion.

| Field | Type | Notes |
|---|---|---|
| `chord_quality` | FK | |
| `scale` | FK | |
| `preference` | int | 1 is the first choice; a dominant 7 has several |
| `note` | char | "avoid the 4th", "tension option" |

Unique on (`chord_quality`, `scale`). **Known limit, stated now so it is not a
surprise:** Dm7 is Dorian as a ii chord and Aeolian as a vi chord, so a lookup
by quality alone is right most of the time and wrong sometimes. v1 accepts
that; a per-chord override written into the chart (`Dm7{aeolian}`) is the likely
fix and does not change these tables.

---

## 2. The band

### `Style`

One groove for the browser band: drums, bass, comping. A row rather than a
settings blob because grooves are content a person will want to add and tune.

| Field | Type | Notes |
|---|---|---|
| `name`, `slug` | char, slug | "Medium swing", "Bossa nova", "Pop ballad" |
| `genre` | choice | jazz / blues / pop / rock / gospel / latin / funk |
| `feel` | choice | swing / straight / shuffle |
| `swing_ratio` | decimal | 0.5 straight to about 0.67 hard swing |
| `time_signature` | char | `4/4` default |
| `default_tempo`, `min_tempo`, `max_tempo` | int | |
| `drums` | JSON | step grid per instrument at 16th resolution |
| `bass` | JSON | the rule (root-fifth, walking, tumbao ...) plus its parameters |
| `comp` | JSON | the comping rhythm and the voicing style |
| `is_preset` | bool | shipped vs the person's own |
| `owner` | FK User, null | null for presets |

**Why JSON columns here, stated because Rule 1 asks for a reason.** A groove is
one indivisible value that the audio engine reads whole and nothing ever queries
a single hit of. Modelling it as a table of drum hits would be thousands of rows
that no screen reads one at a time. The row is the real data; the column is the
shape of one cell of it, not a file standing in for a model.

**The shapes, checked in one place (`improv/grooves.py`).** The model, the admin and
the API all refuse a groove the band cannot play, so a bad one is caught when it is
saved and never when it is played. Time signatures run from `2/4` to `12/4`; a bar
has four steps (sixteenths) per beat, so 16 in 4/4 and 12 in 3/4.

- `drums`: `{instrument: [strength per step]}`. Instruments are `kick`, `snare`,
  `rim`, `hat`, `openhat`, `ride`, `shaker`, `clave`. Each grid has exactly one
  number from 0 (silent) to 1 (hard) per step. Swing is applied to the off-beat
  steps by the band from `swing_ratio`, never written into the grid.
- `bass`: `{"rule": ..., "range": [low, high]}`. Rules are `walking`, `two_feel`,
  `root_fifth`, `eighths`, `bossa`, `boogie`. The range is two whole MIDI notes
  inside 24 to 72, at least 12 semitones apart (an octave, so the band can reach every
  note name).
- `comp`: `{"rhythm": [[start, length], ...], "voicing": ..., "register": [low, high]}`.
  The rhythm is a list of hits in steps, in order, not overlapping, inside the bar.
  Voicings are `shell`, `triad`, `seventh`. The register is two MIDI notes inside 36
  to 96, at least 19 semitones apart (a voicing has to fit inside it).

Tempos run 20 to 300, `swing_ratio` 0.50 to 0.75, and `min_tempo <= default_tempo <=
max_tempo`.

The band is synthesized in the browser (Web Audio, no external service, no
API). The model holds what to play, never audio files.

---

## 3. Charts

### `Progression`

A chord chart plus how to play it. **The chart text is the only copy of the
harmony.** The parsed bars and the transposed key are computed on the page,
never stored, because a stored parse goes stale the moment the text is edited.

| Field | Type | Notes |
|---|---|---|
| `title`, `slug` | char, slug | "ii-V-I in major", "12-bar blues" |
| `genre` | choice | same list as `Style.genre` |
| `tags` | M2M `Tag` | "turnaround", "minor ii-V", "modal vamp", "key change" |
| `chart` | text | `\| Dm7 \| G7 \| Cmaj7 \| % \|`, with repeats, endings, key-change markers |
| `home_key` | char | the key the chart is written in, concrete; transposing is done at play time |
| `time_signature` | char | |
| `default_tempo` | int | |
| `default_style` | FK `Style`, null | |
| `difficulty` | int 1 to 5 | |
| `description` | text | what to listen for, where it appears |
| `is_preset` | bool | |
| `owner` | FK User, null | null for presets |
| `created_at`, `updated_at` | datetime | |

About 40 presets to start. **They are generic patterns, not named songs**:
"rhythm changes" and "autumn-leaves-style minor ii-V-I", not a catalogue of
copyrighted tunes. A progression is not a song, and keeping the library to
patterns is what lets this be a product later.

### `Tag`

`name`, `slug` (unique). Plain labels, so "show me every minor ii-V" is a query.

---

## 4. Teaching

### `Phrase`

A short run of notes: the demo in a lesson, the prompt in call-and-response.

| Field | Type | Notes |
|---|---|---|
| `name` | char | |
| `kind` | choice | demo / call / answer / lick |
| `notes` | JSON list | `{midi, beat, length, velocity}` per note |
| `length_beats` | decimal | |
| `chart_context` | text | the chords underneath, if it only makes sense over them |
| `written_in_key` | char | so it can be transposed with the chart |
| `owner` | FK User, null | |

A phrase is a value read whole, the same argument as `Style`'s JSON columns.

### `Lesson`

One unit on one track. The explanation and the demo live here; the playing
tasks live in `Exercise`.

| Field | Type | Notes |
|---|---|---|
| `track` | choice | chord tones / guide tones / scales and modes / approach notes / rhythm motifs / call and response / voicings and comping |
| `order` | int | position within the track |
| `title`, `slug` | char, slug | |
| `level` | int 1 to 4 | 1 beginner, 2 moving on, 3 intermediate, 4 swing and feel |
| `summary` | char | one line for the card |
| `explanation` | text (markdown) | the short teaching text |
| `demo_phrase` | FK `Phrase`, null | |
| `progression` | FK `Progression`, null | the changes the lesson is taught over |
| `style` | FK `Style`, null | |
| `prerequisite` | FK self, null | |
| `authorship` | choice | ai_drafted / reviewed / avi_written |
| `status` | choice | draft / published |
| `path_order` | int, null, unique | the lesson's place in the whole path, across tracks (SPR-I.10.2). Set by the seed from the file's order, for every lesson, read or not. Empty sorts after every numbered lesson, by level, track and order. |
| `created_at`, `updated_at` | datetime | |

Unique on (`track`, `order`). **Lessons are drafted by AI during development,
reviewed, and seeded; the app never generates a lesson at runtime.** `authorship`
records which they are, so "what has Avi actually read" is a query and not a
memory.

### `Exercise`

A playing task with a way of being scored. This one table covers both a
lesson's practice step and a standalone challenge: **a challenge is an exercise
with no lesson.** "Hit chord tones on beats 1 and 3 for 8 bars" is one row.

| Field | Type | Notes |
|---|---|---|
| `lesson` | FK, null | null means a standalone challenge or daily-workout candidate |
| `order` | int | within the lesson |
| `title` | char | |
| `instructions` | text | |
| `progression` | FK | |
| `key` | char | |
| `tempo` | int | |
| `style` | FK, null | |
| `bars` | int | how much to play |
| `scoring_kind` | choice | chord tones on beats / guide tones / scale only / approach notes / rhythm motif / call and response / comping voicings / free play |
| `scoring_params` | JSON | `{"beats":[1,3],"min_ratio":0.8}`; its shape depends on the kind |
| `pass_score` | int | |
| `xp` | int | |
| `daily_eligible` | bool | may the daily workout pick it |

`scoring_params` is JSON for the same reason as above: each kind reads its own
shape, and nothing filters across kinds by a parameter.

**Added after approval, SPR-I.5.1.** Built as above, with these differences, each
found while building the lesson page and the API:

- `Phrase` has `slug` (unique) and `is_preset`. A phrase is the first teaching row a
  player may own, so it follows `Style` and `Progression`: presets seeded and read-only,
  the player's own rows writable. A lesson's demo and a challenge's prompt are presets.
- `Exercise` has `slug` (unique). The page opens Play on an exercise by `?exercise=<slug>`
  and a take names its exercise by slug, so a link survives a reseed that changes ids.
  It is also unique on (`lesson`, `order`). Its `progression` is PROTECT: a progression
  that a lesson is taught over cannot be deleted from under it.
- `Take.exercise` is SET_NULL. Deleting an exercise keeps the takes played for it, as free
  play, because a take is a record of what happened.
- `scoring_params` and a phrase's `notes` are checked when the row is saved, by
  `improv/teaching.py`, because they are JSON and Django cannot check them. The scoring
  check mirrors what `static/improv/judge.js` reads for each kind; a test keeps the two
  lists of kinds the same.
- `Lesson.demo_phrase`, `progression`, `style` and `prerequisite` are SET_NULL: deleting
  any of them leaves the lesson readable.
- A take counts for an exercise only while the progression and the loop match what it asks
  (from bar 1, to the exercise's `bars`). Anything else is saved with `exercise` null.

---

## 5. The person

### `Player`

One-to-one with the shared `User`. This is the app's own profile, as Rule 2
requires, not a change to `User`.

| Field | Type | Notes |
|---|---|---|
| `user` | 1-to-1 User | |
| `current_lesson` | FK `Lesson`, null, SET_NULL | the pointer: where the player chose to be in the path (SPR-I.10.1, Avi: "continue from the spot he chose"). Set by Start here on a lesson page and by playing an exercise of a lesson. Everything up to it is open; Today and Continue follow it. The only stored piece of progress besides completions. |
| `daily_goal_minutes` | int | default 15 |
| `latency_offset_ms` | int | **timing calibration**, default 0, see below |
| `midi_input_name` | char | the keyboard last used, to reconnect it |
| `note_names` | choice | sharps / flats |
| `demo_output` | choice | laptop / piano: where lesson demos and call-and-response phrases sound. Added after approval, see spec chapter 6. |
| `trainer_tempo` | int | the scale trainer's tempo in bpm, 30 to 160, default 60. Added with Epic I.8 (Avi: "default 60, can be changed, remembered for next time"). |
| `timezone` | char | IANA name, default `Asia/Jerusalem`. Added after approval: the site runs on UTC, and a streak is made of the player's own days, so the day boundary has to be theirs. |
| `created_at` | datetime | |

**Why `latency_offset_ms` is data.** The piano is heard from the piano; the band
comes out of the laptop, maybe through a cable into the piano, maybe through
speakers. The app never hears the piano's sound, only its MIDI. So "was that
note on the beat" is measured as MIDI timestamp against the app's own clock,
and the laptop's audio output delay shifts where the player feels the beat. One
calibration number, per player, per setup, and feature 14 (timing feedback) is
meaningless without it.

---

## 6. What the person did

### `PracticeSession`

| Field | Type | Notes |
|---|---|---|
| `player` | FK | |
| `started_at` | datetime | |
| `ended_at` | datetime, null | |
| `active_seconds` | int | time actually playing, not time the tab was open |

The practice log (feature 16) is this table. The daily goal is `active_seconds`
summed for a day against `Player.daily_goal_minutes`.

### `Take`

One play-through. The source of truth for everything the app says about how the
person plays.

| Field | Type | Notes |
|---|---|---|
| `player` | FK | |
| `session` | FK `PracticeSession` | |
| `exercise` | FK, null | null for free practice |
| `progression` | FK, null (SET_NULL) | |
| `chart` | text | **snapshot** of the chart as played |
| `home_key` | char | the key the chart text is written in. Added after approval (SPR-I.4.3): a snapshot that needs the progression row to be read is not a snapshot. |
| `key` | char | as played |
| `time_signature` | char | the bar length. Added after approval, same reason. |
| `tempo` | int | as played |
| `swing_ratio` | decimal | the feel, 0.50 to 0.75. Added after approval: replaying or re-judging a take needs it and it is not in the chart text. |
| `loop_from`, `loop_to` | int | which bars of the chart were played, 0-based, `loop_to` one past the last. Added after approval, same reason. |
| `style` | FK, null (SET_NULL) | |
| `started_at` | datetime | |
| `duration_ms` | int | |
| `bars` | int | |
| `events` | JSON list | `{t_ms, type: on/off, note, velocity}` as the MIDI arrived |
| `score` | int, null | what the person was told |
| `metrics` | JSON | chord-tone %, scale %, outside %, mean timing offset, spread |
| `judge_version` | int | which version of the judging code produced `score` |
| `is_kept` | bool | feature 15: saved on purpose vs kept only as history |

**Snapshots, for the same reason as blackjack's immutable `RuleSet`.** Whether a
note was right depends on the chart it was played over. Edit the progression
tomorrow and every old take would be re-judged against the wrong chords, so a
take carries its own chart, key and tempo. **`judge_version`** does the same job
for the judging code: when the rules for "approach note" change, old scores stay
explainable instead of silently disagreeing with new ones.

`events` is a JSON list rather than a row per note because it is replayed and
re-analysed whole, and nothing queries one note. The weakness report reads
across takes by decoding them, which is fine at one player's scale; **if it ever
is not, the answer is a rollup table built from takes, never a counter that
replaces them.**

### `Completion`

The first time a player passes an exercise. A fact, not a status.

| Field | Type | Notes |
|---|---|---|
| `player` | FK | |
| `exercise` | FK | |
| `take` | FK `Take` | the take that passed |
| `xp_awarded` | int | frozen at the time |
| `completed_at` | datetime | |

Unique on (`player`, `exercise`).

**Added after approval, SPR-I.5.2.** Built as above, with these differences:

- A completion is made **by the server**, in the same transaction as the take that earns it
  (`improv/progress.py`, `award`), and the API is read-only for it. The page can report a
  take, so it could not otherwise be stopped from awarding itself XP. A take earns a
  completion when it has a score at or above the exercise's `pass_score`, was played over
  the exercise's progression from the first bar for the exercise's `bars`, its lesson is not
  locked for the player, and the exercise is not already passed.
- `xp_awarded` is read from the exercise row when the completion is made, and then frozen.
- `take` is SET_NULL, not required. Takes are pruned after 30 days unless kept (Epic I.6),
  and a pruned take must not un-earn XP. `exercise` is CASCADE: a completion of an exercise
  that no longer exists is not worth keeping. `player` is CASCADE.
- `take` is one-to-one: a take passes at most one exercise.
- Total XP, level, a lesson's state (open, locked or done) and the counts on the summary are
  computed from the completions on every read (`progress.summary`, `progress.lesson_states`)
  and stored nowhere, as the table below says. A lesson with no exercises is never "done"
  and never holds up the lesson after it, unless it is itself locked, in which case
  everything behind it stays locked too.
- Levels: level n begins at 25 times (n - 1) times n XP, capped at 50. Both numbers are
  constants in `progress.py`.

**Added after approval, SPR-I.5.3.** The first six lessons are seeded by
`seed_improv_lessons` from `improv/seed_data/lessons.json`: 6 demo phrases (presets, kind
`demo`), 6 lessons and 18 exercises, one lesson to each scored track. The command adds what
is missing by slug, never overwrites, runs in one transaction and needs
`seed_improv_library` first. Every seeded lesson is `published` with `authorship` set to
`ai_drafted`, because that is the truth until Avi reads it; the pages say so on the card and
on the lesson. When Avi has read a lesson he sets it to `reviewed` or `avi_written` in the
admin, and a later seed run leaves it alone. The lessons are drafts that the app serves, and
they must be read before they are passed off as taught.

**Added after approval, SPR-I.5.4.** No new table and no new column. The practice log, the
daily goal and the streak are reads over `PracticeSession` and `Player`, computed in
`improv/practice.py`. A sitting belongs to the day it started on, read in the player's own
`timezone` (an unknown zone name reads as UTC). A day meets the goal when its sitting seconds
reach `daily_goal_minutes` times 60, using the goal as it is now for every day. The streak is
the run of goal days ending today, or ending yesterday while today is still short of the goal,
so an unfinished day never breaks it. The page, not the server, counts `active_seconds`: the
band running, or a note played in the last ten seconds, reported every thirty seconds and at
Stop and on leaving.

**Added after approval, SPR-I.5.5.** No new table and no new column. The daily workout is a read
over `Exercise` (its `daily_eligible` flag), `Completion` and `Take`, computed in
`improv/workout.py`. It is a function of the player, the date in the player's own `timezone` and
the completions made before that day began, so the same three show all day. Nothing about a
pick is saved: finishing one is a take, and "done today" is a take of that exercise from today
at or over the pass mark.

**Added after approval, SPR-I.5.6.** No new table and no new column. The weakness report
(`improv/weakness.py`) and the personal bests (`improv/bests.py`) are reads over `Take`, joined to
`ChordQuality.family`. The one change in what is stored is inside `Take.metrics`, which is a free
form dict: the judge now adds `byQuality`, a map from chord quality symbol to `{notes, chord,
scale, approach, outside}`. Older takes simply lack it and count toward every area but the chord
family one. Challenges are `Exercise` rows with no lesson, added by `seed_improv_challenges`.

---

## 6a. The scales and chords trainer (Epic I.8, added 2026-10-07)

Spec chapter 10. Three tables, all about what a player is taught or did.

### `ScaleFingering` (reference, read-only to a player)

The standard fingering of a major scale for one hand, one key. Seeded once from
`improv/seed_data/fingerings.json`.

| Field | Type | Notes |
|---|---|---|
| `scale` | FK Scale | Major (Ionian) for now; other scales add rows later |
| `root_pc` | int 0-11 | the key's tonic as a pitch class, C is 0 |
| `hand` | choice | `L` or `R` |
| `first_octave` | JSON, 7 numbers | finger for each scale degree in the first octave, 1 is the thumb |
| `next_octaves` | JSON, 7 numbers | the same for every later octave (it differs only where the hand starts on a different finger) |
| `last_note` | int | the finger on the final top note |
| `authorship` | choice | same meaning as on `Lesson`: `ai_drafted` until Avi has read it |

Unique on (`scale`, `root_pc`, `hand`). Descending is the ascending list reversed. **Why JSON columns
here:** a fingering is one seven-number cell that the screen reads whole and nothing queries by a single
finger; the row is the data. The numbers were checked against a published chart (masterpiano.com,
"Piano Scales") and against the standard exam fingerings; they are `authorship = ai_drafted` until Avi
has read them at the piano.

### `ScaleRun`

One attempt at a scale in time, with its score.

`player`, `scale`, `root_pc`, `octaves` (2 to 4), `notes_per_beat` (2 to 4), `tempo_bpm`,
`score` (0 to 100), `pitch_accuracy`, `timing_accuracy`, `mean_offset_ms` (negative is early),
`passed` (score at or above 80), `missed_steps` (JSON list of step numbers, a cell read whole),
`judge_version`, `created_at`.

### `DrillAttempt`

One prompt of a trainer drill: a chord and a position. One row per prompt, and every chord statistic is a
read over it. (It was modelled in v2 for ear-training games; the same shape serves this drill, so it is
built now with a few more fields.)

`player`, `kind` (`chord_position` now; later chord name, progression name, lick repeat),
`key_pc` (the key being drilled, 0 to 11, kept as a column so "weakest key" is a plain query),
`level` (1 to 3), `prompt` (JSON: degree, chord symbol, position, expected pitch classes and bass),
`answer` (JSON: the notes of the last try and what the recognizer called them),
`is_correct` (right with no wrong tries), `wrong_tries`, `hint_used`, `skipped`,
`response_ms` (null if skipped), `answered_at`.

---

## 6b. Feedback (added 2026-10-08)

### `Feedback`

A note from a person who is trying the app.

`player` (FK to Player, cascade: deleting the account deletes the notes), `kind` (`idea`, `problem`, `praise`,
`other`), `message` (text, 1 to 2000, not blank), `page` (where they were, up to 200, may be empty),
`created_at`. Newest first. A person reads and edits only their own; the owner reads all in the admin.

---

## 6c. The reading trainer (Epic I.12, added 2026-10-10)

Spec chapter 11. One table, and one field on `Player`.

### `Player.reading_tempo`

The reading trainer's tempo in bpm (30 to 160, default 72), remembered when it is changed on the screen, like
`trainer_tempo` for the scales.

### `ReadingTake`

One read-through of a generated exercise, in Flow or Step.

`player`, `key` (the major key as the ladder writes it: C, G, F, D, Bb, A, Eb, E, Ab, B, Db, F#), `hands` (`R`, `L`,
`B`), `difficulty` (1 to 3), `tempo_bpm` (30 to 160), `mode` (`flow` or `step`), `curtain` (whether the notes behind
the cursor were hidden), `seed` (the generator's seed: the same stage and seed give the same exercise), `notes` (JSON:
the exercise as written, `{hand, step, acc, midi, beat, dur}` per note, kept here because it was generated and exists
nowhere else), `events` (JSON: `{t_ms, type, note, velocity}` as the MIDI arrived), `results` (JSON: the judge's word on
every written note, `{state, timing, offset_ms, played}`, one per note), `score` (0 to 100), `pitch_accuracy`,
`timing_accuracy` (0 to 1), `passed` (the server's: a Flow take at 80 or above; a Step take never), `judge_version`,
`created_at`. Newest first.

**Why JSON columns here:** a take is read whole to be drawn again and re-judged, and nothing queries one note of it
except the weak-spot map, which is a read over the last month's takes. The ladder (which stage is next) and the map are
derived reads, never columns.

---

## 8. What is deliberately not stored

Each of these is a read, never a column:

| Thing | Where it comes from |
|---|---|
| Streak | days that have a `PracticeSession` with practice in it |
| Total XP | sum of `Completion.xp_awarded` |
| Level | a function of total XP |
| Lesson done | every `Exercise` of the lesson has a `Completion` |
| Lesson unlocked | its `prerequisite` is done |
| Weakness report | decoded `Take.events` across takes, joined to `ChordQuality` |
| Daily workout | picked from `daily_eligible` exercises by date and weakness |
| Parsed chart, transposed chart | the `chart` text, parsed on the page |
| Chord and scale tones | `ChordQuality.intervals` and `Scale.intervals` |

---

## 9. How it fits together

```
User ──1:1── Player
               │
               ├── PracticeSession ──┐
               │                     │
               └── Take ◄────────────┘ (session)
                     │  ├── Exercise ──── Lesson ──── Phrase (demo)
                     │  │       │            │
                     │  │       └────────────┴──── Progression ──── Style
                     │  └── snapshots chart/key/tempo      │
                     │                                    Tag (M2M)
                     └── Completion (player, exercise, passing take)

ChordQuality ──── ChordScale ──── Scale      (reference, read by judging and the recognizer)
```

`Take` is the hub. Content flows into it (exercise, progression, style) and
everything the app reports flows out of it.

---

## 10. Seeding and the API

- **Seeding is a one-time import** (building_an_app.md, "Data: everything real
  becomes a model"). Reference theory, the starter grooves, the 40 progressions
  and the lessons arrive from files written during development, and each seed
  command checks whether the row exists and leaves it alone if so. A test runs
  every seed command twice and asserts a row edited in between survives.
- **Rule 6:** every model above gets a DRF CRUD API under `/improv/api/`,
  documented, behind the group check. Presets and reference rows are read-only
  to a player; a player's own progressions, styles and phrases are fully
  editable. `Take` is created by the page through the API, not by a special
  endpoint. `Completion` is made by the server when it saves a take, and is read-only
  through the API (see "Added after approval, SPR-I.5.2").
- Own migration chain from `0001`, own templates and static files, own base
  template with its own English menu, and no link back to babook inside the app
  unless Avi asks for one.

---

## 11. Open points: all answered (Avi, 2026-10-04)

1. **The gate (superseded 2026-10-08, see section 0).** Group plus superuser bypass, 404 for everyone else, portal card
   for superusers and members only. **Accepted.**
2. **Who judges a take.** The browser judges live and the server stores the
   events and the score the page computed. **Accepted for v1.** The day there is
   a leaderboard or a paid tier it needs a server-side judge; `judge_version`
   plus stored events is what keeps that migration possible.
3. **Take retention.** Every play-through is recorded; `is_kept` marks the ones
   saved on purpose. Unkept takes are pruned after 30 days, but their score and
   metrics stay, since the weakness report needs those and not the raw events.
   **Accepted.**
4. **Name.** `improv`. **Accepted.**
