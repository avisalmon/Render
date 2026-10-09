# improv: Spec

> **Status: full spec, written 2026-10-04.** Step 4 of the kickoff sequence in
> [building_an_app.md](../building_an_app.md). The data model
> ([data_model.md](data_model.md)) is approved. Chapters 1 and 2 are the intro
> and Avi's direction; chapters 3 to 9 are the high-level spec. Next is the
> backlog. No code exists yet.

---

## Chapter 1. What it is

improv is a practice tool for a pianist who wants to improvise. You play your
own electric piano; the app plays the band around you, tells you what you are
playing, teaches you what to try next, and listens to whether you did it.

It is **built for Avi first**, as a tool he practices with, and **built as a
product from the start**: every choice is made so that other people can use it
later without a rewrite. It was private to him until it was stable; since 2026-10-08 it is open to anyone who signs up, free, so that
people can try it and tell him what they think (chapter 7).

### Who it is for

An intermediate player. Someone who reads chords and plays songs and wants to
improvise but does not know what to play over a chord. Not a beginner course and
not a conservatory course.

### What it is not

- Not a song-learning app. There is no sheet music to follow and no catalogue of
  songs. The unit of work is a **progression**, not a tune.
- Not a synthesizer or a recorder. It makes no sound for your own playing: the
  piano makes the piano sound. (Demos and take playback are sent to the piano as
  MIDI, or as a plain tone if the player prefers; see chapter 6.)
- Not a service that calls out to anything. The band is generated in the
  browser; no API, no audio files, no network needed to practice.

### How it connects

```
electric piano ──USB MIDI──► laptop browser (Web MIDI)
                                  │
                                  ├─ listens: what notes, when
                                  └─ plays the band through the laptop's audio out
                                          │
                       speakers / headphones, or a cable back into the piano
```

- Input is MIDI from the piano over USB. The sound you hear from your own
  playing comes from the piano itself.
- The backing band comes from the laptop, and may be fed back into the piano's
  audio input so everything comes out of one place.
- The app never hears the piano's audio, only its MIDI. Timing is therefore
  measured against the app's own clock, with a per-player calibration for the
  laptop's audio delay.
- Primary target: the laptop, in a browser that supports Web MIDI (Chrome or
  Edge). iPad over USB is a later check, not a v1 promise. iPhone has no Web MIDI
  and gets the on-screen keyboard later.

### Language and look

English only. Its own base template and menu, like every app here.

---

## Chapter 2. Direction, as Avi set it (2026-10-04)

Feature numbers are from the feature list in the chat of that day; the list is
reproduced here so the document stands alone.

**A. Foundation**
1. On-screen keyboard, for when no keyboard is attached; also the route to iPhone.
2. Chord and note recognition: name what is being played, such as Dm7/F or a C Dorian run.
   (The MIDI connection check is implied by "input comes from the piano" and is
   kept. The built-in piano sound was dropped: the piano is the sound.)

**B. Backing tracks**
5. A band generated in the browser, with no API: bass, drums and comping, with tempo, key, swing or straight.
6. A chord chart editor: type `| Dm7 | G7 | Cmaj7 |`, with bars, repeats and key changes.
7. A library of about 40 common progressions tagged by style.
8. Loop a section, count-in, metronome-only, transpose to any key.

**C. Teaching**
9. Lessons in order for an intermediate player: chord tones, guide tones, scales and modes over chords, approach notes, rhythm motifs, call and response, voicings and left-hand comping.
10. Every lesson is the same cycle: short explanation, demo, then play it over a backing track.
11. Chord and scale reference for any key, shown on the keyboard.
12. Ear training inside the lessons.

**D. Practice and feedback**
13. Live feedback: chord tone, scale tone or outside note.
14. Timing feedback against the beat.
15. Take recording: save what you played as MIDI and play it back over the same track.
16. Practice timer, daily goal, practice log.
17. A weakness report.
18. Play-along: the app plays a phrase and you answer it, or the reverse.

**E. Game layer**
19. Challenges with a score.
20. Levels and unlocks across the lesson path, plus XP.
21. Streak and daily workout.
22. Ear and speed mini-games.

**F. Product layer, later**
23. Accounts and progress sync (babook login). 24. Subscription and free tier,
payment off until Avi says. 25. Share a progression or a take. 26. Teacher mode.
27. Phone version. 28. Hebrew and English.

### Version 1

Features 1 and 2, 5 to 8, 9 to 11 (about six lessons), 13, 14, 15, 16, 19, 21, and
the account and access work of 23. In one line: **choose a progression, play over
a band, get feedback, and see your streak.** Everything else is built after that
loop has proved itself on Avi's own playing.

### Decisions already made

| Decision | Answer |
|---|---|
| Interface language | English |
| Who can open it | Avi only, until it is stable; linked from babook for him alone |
| Styles | Jazz first; pop, rock, gospel, blues and the rest as well |
| Where lessons come from | Drafted by AI during development, reviewed, and shipped as seeded content. The app never generates a lesson while running. |
| Band | Synthesized in the browser; no API |
| Piano sound | From the piano itself |

### Decided here, and approved by Avi on 2026-10-04

- Access was a Django group with a superuser bypass and a 404 for everyone else. **Superseded 2026-10-08:** anyone who signs in may use everything, free; a visitor sees the front door (chapter 7).
- The progression library is generic patterns, not named songs.
- The browser judges live and the server stores the result (revisit for any
  leaderboard or paid tier).
- Unkept takes lose their events after 30 days and keep their score.
- The name is improv.

---

## Chapter 3. The band

**Job:** turn a chart and a style into sound, in the browser, on time, with no
network and no audio files.

### From text to a timeline

The chart text (`Progression.chart`) is parsed on the page into a flat list of
bars, each bar a list of chords with their beat positions. The grammar is small
and written down in the API docs because the editor, the library and the
recognizer all share it:

- `| Dm7 | G7 | Cmaj7 | % |` : bars between pipes, `%` repeats the last bar.
- Two chords in one bar split it evenly: `| Dm7 G7 |`.
- Repeats `|: ... :|`, first and second endings `[1 ... ] [2 ... ]`.
- A key change marker, `{key: Eb}`, moves everything after it.
- Chord symbols are read through `ChordQuality.symbol` and `.aliases`, so `Dm7`,
  `Dmin7` and `D-7` are the same chord. Slash chords (`C/E`) keep their bass note.
- A bad chart never plays half of itself. The parser returns the line and bar of
  the first error, and the editor shows it where the cursor is.

Transposing is a function of the parsed timeline plus a target key, applied at
play time. Nothing transposed is ever stored.

### From a style to notes

A `Style` is a groove, not a recording. Each bar is built fresh from the chord:

| Part | What it does |
|---|---|
| Drums | the step grid at 16th resolution from `Style.drums`, with swing applied to the off-beat steps by `swing_ratio` |
| Bass | the rule in `Style.bass` (root and fifth, walking, tumbao ...) turned into notes from the chord's intervals, landing on the next chord's root on the last beat |
| Comping | the rhythm in `Style.comp` with a voicing built from `ChordQuality.roles`: for jazz the third and seventh with a color tone, kept inside a fixed register and moved the shortest distance from the last chord |

Band timing is **exact**: swing is the only displacement, and variation comes
from velocity, never from random timing. The judging in chapter 5 measures the
player against the same grid the band plays on, so a band that wanders would
make every timing score wrong.

### Making the sound

All of it comes from Web Audio, synthesized on the page: noise and oscillator
drum voices, a filtered oscillator bass, a soft electric-piano-like comp voice.
It does not have to sound like a record. It has to be clear, steady and not
tiring over twenty minutes.

### Scheduling

One `AudioContext` clock runs everything. A look-ahead scheduler queues the next
fraction of a second of events onto that clock, which is the standard way to keep
a browser band from drifting when the page is busy. The same clock is the
reference the MIDI timestamps are mapped onto (chapter 4).

### Rules in v1

What the band does, exactly. Each rule is a pure function of the chart and the
style, and the tests in `tests/js/spri23.test.js` pin every line of it.

**Swing.** Positions are written as straight sixteenths. The first half of every
beat maps onto the first `swing_ratio` of the beat and the second half onto the
rest, so the off-beat eighth of a 0.67 groove lands at 0.67 of the beat and the
beat itself never moves. A ratio of 0.50 is straight. This is the only
displacement in the band; a click and the band always agree on the beat.

**Bass rules.** The first note of a chord is its bass note, so a slash chord
(`C/E`) puts the E underneath. Every note is kept inside `Style.bass.range`.

| Rule | What it plays |
|---|---|
| `walking` | one note a beat: the root nearest the last note, then chord tones climbing (third, fifth, seventh), and on the last beat of the chord a half step from the next root. At the end of a looping chart that root is the first chord's |
| `two_feel` | the root on beat 1 and the fifth on beat 3, each held about four fifths of its length |
| `root_fifth` | the same two notes, left ringing |
| `eighths` | the root on every eighth, the beats a little stronger |
| `bossa` | the root on the beat, the fifth a beat and a half later, repeating every two beats |
| `boogie` | the eighth pattern root, third, fifth, sixth, flat seven, sixth, fifth, third, with the minor third on a minor chord |

**Voicings.** Placed inside `Style.comp.register`.

| Voicing | Notes |
|---|---|
| `shell` | the third, the seventh (or the sixth, or the fifth when there is no seventh) and one color tone, the ninth, left out when the chord already alters it or is suspended |
| `triad` | the root, third and fifth of the chord's quality |
| `seventh` | all the chord tones, thinned to four for the big chords while keeping the third and the seventh |

For each chord the placer tries every inversion in every octave of the register
and keeps the one whose notes move the least from the last chord, so voices glide
instead of jumping. A chord that repeats reuses its notes exactly. A comping hit
that crosses a chord change is cut at the change and the new chord starts its own
articulation.

**Drums.** One event for every non-zero step of every grid, with the step's
strength as the velocity, swung like the rest.

**Refusals.** The band says why it cannot play instead of playing something odd:
a chart whose beats per bar do not match the groove's signature, a style with a
rule or voicing it does not know, a chord quality it has no row for, a swing ratio
outside 0.50 to 0.75, an empty bar range.

**The scheduler.** The timer is never trusted with the beat. Every 30 ms it asks
which bars start in the next 150 ms (the look-ahead) and queues their events on
the audio clock; the clock keeps the time, so a late timer cannot move a note. A
bar more than a quarter of a second behind, because the page was busy or hidden,
is restarted just ahead of now instead of firing a burst of old notes, and is
counted. A tempo change applies from the next bar that has not been queued, which
is the next bar line; a bar already queued keeps its length. Tempo is held to 20
to 300 beats per minute.

**The voices.** Drums are bursts of filtered noise and short tones; the bass is a
sawtooth with a sine under it through a closing lowpass; the comp is a sine with a
short bright tine. Each part has its own level and mute, and everything passes
through one gentle limiter so a full chord, the bass and the ride on the same beat
cannot clip. A note whose start time has already passed is heard now, not dropped.

### Controls

Tempo, key, swing or straight, count-in, metronome-only, loop a bar range, and
per-instrument volume with mute (mute the comping to hear your own harmony).
Changing tempo or key while playing takes effect at the next bar line, never
mid-bar.

### Where the band comes out

The page plays through the browser's default output. Where the browser allows
it, there is an output picker, because Avi's wiring may be a cable into the
piano and not the laptop speakers. The cable to the piano is the player's
wiring; the app does not manage it.

---

## Chapter 4. Reading the piano

**Job:** know what the player is pressing, when, and what it is called.

### The MIDI connection

- Web MIDI, with the browser's permission prompt. Chrome and Edge are the
  supported browsers. Anywhere else the page says plainly that MIDI is not
  available and offers the on-screen keyboard.
- The last keyboard used is remembered in `Player.midi_input_name` and reconnected
  on load. Unplugging and replugging mid-practice is handled, not a reload.
- Messages used: note on (a velocity of 0 counts as note off), note off, and the
  sustain pedal. Channel is ignored. Everything else is dropped.
- Every note event is stamped with the MIDI message's own timestamp, mapped onto
  the `AudioContext` clock, not with the time the page got around to handling it.

### The on-screen keyboard

Clicking it, touching it, or the computer keys all produce the same events as
the piano, marked as a different source. It exists so the app is usable with no
keyboard attached and so a phone version is possible later. Timing from it is
less trustworthy, so takes made on it are scored but not given a timing grade.

### Chord recognition

Input: the notes currently held. Output: the best name for them.

1. Reduce the held notes to pitch classes and note the lowest one as the bass.
2. Try every `ChordQuality` over every root, and score each by how many of its
   intervals are present and how many extra notes there are.
3. Prefer the reading whose root is the bass. If the bass is not the root, it is
   a slash chord (`Dm7/F`), not a different chord.
4. Two to four notes with no root (a third and a seventh, a common jazz shell)
   still get a name, shown as a best guess with the alternatives beside it,
   because those notes really are ambiguous.
5. Fewer than three distinct notes are shown as notes and interval, not forced
   into a chord name.

### Scale hints

For a run of single notes, the page collects the pitch classes of the last few
seconds and lists the `Scale` rows that contain all of them, best fit first. It
only says "fits C Dorian" once at least five different pitch classes have been
heard, because three notes fit a dozen scales and naming one would be a guess
dressed as an answer.

### Calibration

The app hears the piano only through MIDI, and the band leaves through the laptop,
a cable or speakers, each with its own delay. So "on the beat" means nothing until
the player's setup is calibrated.

- The calibration screen plays a click track through the same output as the band
  and asks the player to tap one key in time with what they hear, sixteen times.
- The mean of the gaps between each tap and the click it was meant for is
  `Player.latency_offset_ms`. The spread is shown too, so a result that is
  all over the place is visible rather than silently stored.
- Judging subtracts the offset from every note time.
- It is redone when the wiring changes. A Bluetooth headphone adds enough delay to
  be worth a warning on the screen, not a quiet bad score.

---

## Chapter 5. Judging a take

**Job:** say, note by note and then overall, whether the playing fit the harmony
and the beat. This is the heart of the app, so its rules are written out here.

### One function, used live and at the end

The judge is a pure function: the notes played, the chart snapshot, the key, the
tempo and swing, the exercise's scoring kind and parameters, and the latency
offset go in; per-note classifications, metrics and a score come out. It has no
page, no clock and no network in it.

**The live display and the final score come from the same function**, run
incrementally for the first and once over the whole take for the second, so the
screen cannot show one thing while the score says another. That is also the
reason it can later move to the server for a leaderboard without being rewritten:
it already takes stored events and returns a result. `Take.judge_version`
records which version of these rules produced a score.

### Classifying a note

For each note-on, find the chord sounding at that moment (looking half a beat
ahead, so a player who anticipates the change is judged against the new chord),
then classify:

| Class | Meaning | Colour on the keyboard |
|---|---|---|
| Chord tone | in the chord (`ChordQuality.intervals`); guide tones (third, seventh) are flagged inside this class | green, guide tones brighter |
| Scale tone | not in the chord, but in the chord's first-choice `Scale` | blue |
| Approach note | outside, within one semitone of a chord tone, and followed by that chord tone within a beat | amber |
| Outside | none of the above | red, soft |

An approach note cannot be known until the next note arrives, so it shows as
amber-pending and settles into approach or outside when the next note lands or
the beat runs out. "Outside" is information, not a failure: good players play
outside on purpose. The score only penalizes it where an exercise asks for it.

### Timing

Each note-on is compared with the nearest point on the exercise's grid (the beat,
the eighth, or the swung eighth, according to the exercise), after the latency
offset. The result per note is early or late in milliseconds. Over a take:
mean offset (rushing or dragging), spread, and the share within a tolerance that
scales with tempo (a tenth of a beat). The learner is told in words: "you
rush by 18 ms", not given a number to decode.

### Scoring kinds

`Exercise.scoring_kind` picks which dimensions count and how much, with weights
in `scoring_params`:

| Kind | What earns the score |
|---|---|
| Chord tones on beats | share of notes on the named beats that are chord tones |
| Guide tones | share of notes that are the third or seventh, and that move by step into the next chord's guide tone |
| Scale only | share of notes that are chord or scale tones |
| Approach notes | share of the planned targets reached by an approach from a half step |
| Rhythm motif | onsets matching the target rhythm within tolerance, pitch free |
| Call and response | the answer matches the phrase in rhythm and contour (exact notes if the params say so) |
| Comping voicings | chord held at the bar start that the recognizer names as the chart chord, in the left-hand register |
| Free play | no pass or fail, only the metrics |

Score is 0 to 100. `pass_score` is the exercise's own bar. A take is judged only
over the bars the exercise asks for, from the end of the count-in.

### What the server does with the result

The page posts the take and the score it computed. The server checks that the
shape and ranges are sane, and **the server decides whether it counts**: it
creates the `Completion` itself when the posted score reaches the exercise's
pass score and none exists, and it takes the XP from the exercise row, not from
anything the page said. The page cannot award itself XP; it can only report a take
that, for now, the server believes. That is the accepted browser-judging limit
(data model, section 11).

### Proving the judge

Golden fixtures: a set of small, hand-checked takes (events plus chart) with the
exact classifications, metrics and scores expected. The test suite runs the
JavaScript judge over them under Node, so any change to the rules shows up as a
fixture diff and a deliberate `judge_version` bump. Node being absent fails the
suite loudly, not quietly skipped.

---

## Chapter 6. The lesson path and the game layer

### Tracks and the first lessons

Seven tracks, from the data model: chord tones, guide tones, scales and modes,
approach notes, rhythm motifs, call and response, voicings and comping. Version 1
shipped six lessons, one from each of the first six tracks. Voicings and comping, ear
training and the rest follow later.

**As built (SPR-I.5.3).** The call-and-response lesson is taught over a four-bar pop
progression, not a blues: a call and its answer need an even four-beat bar on a straight
groove, and the judge reads the answer bar only. The lessons live in
`improv/seed_data/lessons.json` and are seeded by `seed_improv_lessons` as drafted by AI
and not yet read; every exercise has been passed by a model player through the real judge
in the tests. Avi reads each lesson before it is passed off as taught.

### The path: twenty lessons in three levels (SPR-I.10.2, Avi 2026-10-09)

"Build the lessons not randomly, with real logic behind the progress, from beginner to
intermediate; maybe 20." The curriculum is twenty lessons, each one idea with three exercises
that get harder (slower to faster, fewer to more targets, one chart to a longer one). The path
is numbered one to twenty (`Lesson.path_order`) and interleaves the tracks, so no two lessons
of one kind come in a row, and every prerequisite comes earlier in the path.

- **Level 1, beginner (7).** Chord tones on the beat over four easy triads; rhythm motifs;
  scales that fit the chord (white keys over a two five one); chord tones through the
  twelve-bar blues; syncopation; call and response; chord tones in a two five one with
  seventh chords.
- **Level 2, moving on (7).** Guide tones (thirds and sevenths); approach notes; when the
  scale changes (one new note per chord); bossa rhythms; guide tones round the turnaround;
  answering with the shape; approach notes through the blues.
- **Level 3, intermediate (6).** Chord tones through the jazz blues (two chords in a bar);
  the minor two five one (locrian, altered, dorian); guide tones through secondary dominants;
  funk rhythms; approach notes at tempo; longer calls with eighth notes.

Rules the content keeps, each checked by a test: an exercise is set in its chart's own key;
rhythm motifs sit only on straight grooves, because the motif judge matches a straight grid;
a lesson's demo phrase names only chords of its own chart; the hardest exercise of a lesson
is never a daily-workout pick; the whole course is worth a handful of levels; the words are
plain. The six original lessons kept their slugs and their exercise slugs, so nobody loses a
pass they earned.

`seed_improv_lessons --refresh-drafts` (the way the deploy runs it) also brings every lesson
still marked `ai_drafted` up to date with the file, exercises and demo phrase included, so a
draft improves until the day Avi reads it. A lesson marked reviewed or written by Avi is never
touched, nothing is ever deleted, and `path_order` is kept right for every lesson because the
order of the path is structure, not words.

### Start anywhere (SPR-I.10.1, Avi 2026-10-09)

"Give the opportunity to unlock any lesson the user would like to start from and continue from
the spot he chose. If he goes back or jumps ahead, let him, and the progress keeps going from
the new point." So **nothing is locked.** A lesson whose prerequisite still has exercises to pass
is **ahead** of the player, not shut: it says what it builds on ("Builds on Chord tones on the
beat, which you have not finished. You can start here anyway"), every exercise links to Play, and
a pass there counts like any other.

The one stored thing is **`Player.current_lesson`, the pointer**: where the player chose to be.
It moves when they press **Start here** on a lesson page (`POST /improv/api/start-here/`) and
whenever they play an exercise of a lesson. Everything up to the pointer in the path is open.
Today and Continue follow the pointer: that lesson while it has exercises to pass, then the next
unfinished lesson after it, then whatever is left before it, then "finished". Without a pointer
the old rule holds (the first open lesson, a begun one first), and a lesson ahead is never
offered until the player goes there. The daily workout draws from the lessons up to the pointer
and never pushes a person into a lesson ahead. The Lessons screen groups the path by level,
marks the pointer "You are here", and the piano key opens that lesson.

### The cycle of a lesson

Every lesson is the same three steps, in this order, so the learner always knows
where they are:

1. **Read.** A short explanation (`Lesson.explanation`), a screen or less.
2. **Hear.** The demo phrase plays over the lesson's progression, with the notes
   lighting on the on-screen keyboard.
3. **Play.** The lesson's exercises, one after another, over the band, each judged
   as in chapter 5. A lesson is done when every exercise has a `Completion`.

A lesson whose `prerequisite` is done is open; one whose prerequisite is not is ahead
of the player, which is advice, not a lock (see "Start anywhere"). A standalone challenge
or free practice is always open.

### Where demos and answers sound

A demo, a call phrase, and the playback of a saved take are notes the app wants
to *play*, and the app makes no piano sound. So `Player.demo_output` chooses:
**piano** sends them as MIDI out to the piano, so it sounds right and in its own
voice (this needs the browser's MIDI output permission), or **laptop** plays a
plain tone through the band's output. Piano is the default whenever an output is
found.

### XP, level, streak

All derived, none stored:

- **XP** is the sum of `Completion.xp_awarded`, and it is awarded the first time
  an exercise is passed. Replaying earns nothing, so XP measures ground covered
  and cannot be farmed.
- **Level** is a function of total XP with a gentle curve. The thresholds are
  constants in one place, covered by a test.
- **Streak** is the number of consecutive days, in the player's own timezone
  (`Player.timezone`), on which the daily goal was met. Today shows as pending
  until the goal is met and does not break the streak until the day has ended.
- **Daily goal** is `Player.daily_goal_minutes`, default fifteen.

### The practice timer

`active_seconds` counts time the band is running or a note was played in the
last ten seconds, not time the tab is open. The page reports it every thirty
seconds to the open `PracticeSession`; a new session starts after thirty idle
minutes. The timer is the player's own log and counts toward nothing else.

**As built (SPR-I.5.4).** The page keeps a small clock (`static/improv/practice.js`): it
counts the band's running time plus ten seconds after each note, once, and never the open tab.
A note played with the band stopped opens a sitting too. It reports to the sitting every thirty
seconds, at Stop and when the page is left, and a sitting that went thirty minutes without
activity is closed and the next activity opens a new one. The server reads the log, today
against the goal and the streak from the sittings in `/improv/api/practice/`, in the player's
own timezone; a sitting belongs to the day it started on. The Play screen carries a one-line
"Today: 5 of 15 minutes" and the Practice screen shows the streak and the last thirty days.

### The daily workout

Three exercises, picked from the `daily_eligible` ones the player has unlocked:
one that targets the weakest area in the weakness report, one old completed
exercise as a review, and the next unfinished one. The pick is a function of the
player and the date, so the same three show all day and a reload does not
shuffle them.

**As built (SPR-I.5.5).** `improv/workout.py` reads the workout; nothing is stored. It is a
function of the player id, the date (the player's own day) and what had been passed before that
day began, so passing one during the day changes nothing about the other two. The slots, in
order: a weak spot (an eligible exercise of the first kind the weakness report names that has
one, with the kinds from the weakness report below), a review (one passed before today, chosen by a stable
hash of player, date and slot), the next one (the first not yet passed, in the order of the
tracks, then the lesson, then the exercise, with challenges last) and fresh ones to make up
three. An exercise is never offered twice, never from a draft or locked lesson, and never unless
it is marked for the workout, so a new player may get fewer than three. An item is done today
when a take of exactly that exercise, played today and at or over the pass mark, exists; a
review passed again is done but earns no XP. The Practice screen lists the three with a reason
for each and a Play link, from `/improv/api/workout/`.

### The weakness report

Read from the last thirty days of takes: per scoring dimension and per chord
family, where the player's chord-tone, scale, outside and timing numbers are
worst. It says nothing until there are enough notes behind a claim (twenty in a
bucket), because "you struggle with m7b5" from four notes is noise. It names at
most three things, in plain words, each with an exercise that works on it.

**As built (SPR-I.5.6).** `improv/weakness.py` reads the report; nothing is stored. The judge
now writes `metrics.byQuality` on each take (per chord quality: notes played, and how many were
chord, scale, approach or outside), which is what lets the server say "over minor chords" by
joining the quality to its family. The judge version stays 1 because no score changed. Takes in
the 30 days before now count, weighted by their notes, and anything in `metrics` that is not a
sensible number is ignored. Four areas, each needing 20 notes of its own: timing (under 60
percent close to the beat), chord tones (under 30 percent), outside (over 25 percent) and a
chord family (over 25 percent outside over that family). At most three are named, the furthest
from fine first, ties in the order timing, chord tones, outside, family. Each names the first
open exercise of a kind that works on it, preferring one not yet passed, or none. The daily
workout's weak slot takes its kinds from the report as it stood when the day began, so playing
badly today changes tomorrow's workout and not today's. The Progress screen shows it under
"Where to work", and says how many notes it still needs rather than guessing.

### Challenges and takes

A challenge is an exercise with no lesson; its personal best is the best take for
it, a read. A saved take (`is_kept`) is replayed from its events over the same
chart, key and tempo it was played at, through the demo output. Unkept takes lose
their events after thirty days and keep their score and metrics, which is all the
weakness report needs. Pruning happens when the same player saves their next take,
because Render's scheduled jobs cannot see the SQLite disk and a prune that needs
a scheduler would not run.

**As built (SPR-I.5.6).** The standalone challenges are five exercises with no lesson, seeded by
their own command, `seed_improv_challenges` (add-missing-by-slug, never overwrites, needs the
library first): chord tones through a twelve-bar blues, scale notes around a turnaround, guide
tones through a jazz blues, a bossa rhythm, and approach notes in a minor blues. They are always
open and offered to the daily workout. A personal best is a read, `improv/bests.py`: the highest
score among takes that count the way a completion counts, the earliest if two tie. The
Challenges screen lists every challenge with its best, and the bests in the lessons below.

---

## Chapter 7. Access, the portal link and the API

### The gate (open to anyone who signs in, 2026-10-08)

Avi, 2026-10-08: "enable login in the main page of this app and get everything free to anyone entering. I want
users to try and feedback." And: if he gives out `https://babook.co.il/improv/`, people "will not be directed to
babook, rather invited to login or signup; if they are logged in then go ahead to the site like me."

The rule is one function, `improv.access.is_player`: **signed in**. There is no group and no payment. It
delegates to `app.portal.may_enter`, where improv is `audience=EVERYONE`.

**A visitor** (not signed in) sees improv's own front door at `/improv/`, in improv's look and in English. Since
SPR-I.9.5 it is one step, not a form: a headline (draft copy, Avi may rewrite it: "Play over a real band and hear
what to fix."), a filled Sign up free button, Continue with Google, a quiet "Have an account? Log in" link, fine
print (free, works best in Chrome or Edge with a digital piano on USB), and a silent looping demo of a chart (Slow
blues in C, 90 bpm, the four chord cells lighting in turn, a piano strip, three lines on what you get). The demo is
CSS only and stands still under reduced motion. The log in form is its own page, `/improv/login/`, which also
carries the password reset link. The visitor header is a quiet Log in link and a filled Sign up free button. The
destination (`next`) is carried by every link. The public pages are exactly
`/improv/`, `/improv/login/`, `/improv/signup/` and `/improv/logout/` (POST only). Any other page redirects to
`/improv/?next=...`, and after signing in the person lands where they were going. `next` is honoured only if it
stays inside `/improv/`. The API answers a visitor with 401/403 (DRF), never with data.

**A signed-in person** goes straight to Today, like Avi. A `Player` row is created on the first visit.

**The menu (SPR-I.9.5).** The header shows only the everyday screens: Today, Play, Lessons, Scales, Chords. A
**More** menu holds Challenges, Library, Takes and Reference. The person's email is an **account menu** holding
Progress, Practice log, Setup (and Timing spike, for staff) and Log out (a POST form). **Feedback stays in plain
sight** in the bar, in the accent colour, because feedback is why the app was opened up and the front door promises
a Feedback link on every screen. Every screen is still one click or two away. The bar marks the screen you are on
(`aria-current="page"`; when it sits inside a menu, the menu's summary lights up). The menus are `<details>`
elements, closed by a click elsewhere, by Escape or by opening the other menu (`static/improv/menu.js`). They are
mouse and touch only and hold no `data-key-action` button, so C8, B7 and A#7 keep the jobs each screen gives them.
The "Piano keys C8 B7 A#7" hint stays in the bar (hidden under 40rem, where there is no room and rarely a piano).
An open menu overlays the screen and never makes the page scroll (guarded at 1280 by 720 and 1920 by 1080). The
login and sign-up pages offer only the other way in, not themselves.

**Accounts.** Sign up and log in are improv's own views (`improv/signin.py`) and create or use ordinary site
accounts: one email and password also works on babook, and Google sign-in goes through the site's own provider
and returns to `/improv/`. Nothing in improv shows babook pages or branding. Guards against abuse: a login lock
after ten failures per address and email for fifteen minutes, ten sign-ups per address per hour, a password check,
and a throttled feedback form.

**Staff only.** The Timing spike link is shown to staff only. The portal card is shown to the owner only
(`card_admin_only`); everyone else is given the link by hand.

**Static files are not behind the gate.** WhiteNoise serves `/static/improv/` before Django routing, so the
stylesheet and scripts are public. They are code, not data.

**How the gate is built.** `improv.middleware.GateMiddleware` adds the trailing slash (301) and sends a visitor on
a non-public page to the front door. `IsPlayer` repeats the check inside the API as defence in depth.
The old design (group `improv_players`, a 404 for everyone) is gone; the `improv_players` group, if it still
exists, means nothing.

**What strangers can and cannot do.** Presets, lessons, challenges and the reference tables are read-only to
everyone. Styles, progressions, phrases, takes, sessions, completions and feedback are the person's own and are
filtered to them in the queryset. A completion is still created only by the server, as the consequence of a take.

### Feedback

Every signed-in screen has a Feedback link (`/improv/feedback/?from=<page>`). The form takes a kind (idea,
something wrong, something liked, other) and a message up to 2000 characters; the page it came from is kept. A
person sees their own notes there. Avi reads everyone's in the admin, at `/admin/improv/feedback/`. **Every new
note is also emailed** to avi.salmon@gmail.com and avi.salmon@intel.com (fixed in `improv/feedback_mail.py`, not a
setting), with the sender as reply-to, the kind and the page. Editing a note sends nothing, and a mail failure is
logged and never loses the note. A person is limited to 20 notes an hour.

### The portal

One `App` entry, `audience=EVERYONE`, `listed=True`, `card_admin_only=True`: every signed-in person may enter, but
the card is shown to superusers only, so for everyone else the link is shared by hand. Nothing in improv links back.

### Limits

A person may keep up to **1000** of their own saved items of each kind (styles, progressions, phrases, takes,
feedback notes). Past that, saving answers 400 with a message that says to delete some first. Practice sessions, scale
runs and drill attempts, which pile up by themselves, have a ceiling of 20000. The owner (a superuser) has no limit.
The numbers are `MAX_OWN_ROWS` and `MAX_LOG_ROWS` in `improv/api.py`.

### The API

Every model in the data model has a full, documented CRUD endpoint under
`/improv/api/`, behind the same gate, written in DRF from the first sprint
(Rule 6). The rules that make it safe:

- Reference rows (`ChordQuality`, `Scale`, `ChordScale`, `Tag`) and presets (`Style`,
  `Progression`, `Phrase`, `Lesson`, `Exercise`) are read-only to a player. A
  player's own progressions, styles and phrases are fully editable.
- Everything a player owns is filtered to that player in the queryset, not in the
  page. One player cannot read or write another's takes.
- `Take` is created through the API by the page. `Completion` is **not** writable
  from outside: the server creates it as the consequence of a take (chapter 5), and
  the endpoint is read-only. That is the one deliberate departure from "full CRUD",
  and it is there because a client-writable completion would be a client-writable
  XP counter.
- Derived reads get their own endpoints, so the screens and any later app share
  one definition of them: summary (streak, XP, level, today's minutes), daily
  workout, weakness report.
- The API is documented in `docs/improv/api.md`, and a test fails if a model has
  no endpoint.

### Tests that guard the gate

A visitor and a signed-in person are each sent to every route the app registers, and the test asserts the
redirect to the front door or the 200, and 401/403 on every API endpoint for a visitor, so a route added next
month cannot quietly skip the gate (`tests/test_spri_9_1.py`).

---

## Chapter 8. Screens

The app has its own base template and its own English menu. Laptop first; other
sizes degrade to readable rather than being designed for.

### Two standing rules for every screen (Avi, 2026-10-06)

improv is a PC app used while sitting at the piano, hands on the keys, so two rules
apply to every screen, existing and future. They are not features of one screen.

1. **One screen, no scrolling.** Everything the player needs is visible at once in the
   browser window. No page scrolls vertically at 1280 by 720 or larger. Panels share
   the window in columns and rows instead of stacking down the page. The only
   scrolling allowed is inside one bounded list that can grow without limit (takes,
   the practice log, the library), never the page itself, and each such list shows
   its newest or first items without scrolling.
2. **The piano is a remote control.** Every activation button (start, stop, hear, save,
   continue, replay) can also be pressed from the piano. The top key of an 88-key
   piano (MIDI 108, C8) is the primary action of the screen. Its neighbours are the
   second and third actions. Each such button shows its key on its face.

**The control keys.**

| Key | MIDI | Action |
|---|---|---|
| C8 | 108 | primary: Play and Stop, Hear it, Continue, Save, Replay |
| B7 | 107 | secondary: the next most useful button on that screen |
| A#7 | 106 | tertiary |

- The mapping lives in `control.js` (pure, tested under Node). A page marks a button with
  `data-key-action="primary"`, `"secondary"` or `"tertiary"`; it does no MIDI itself. When a
  control key goes down, the first button of that action that is visible and enabled is
  clicked, so a button that is hidden or disabled is skipped and the next one is used.
- A control key is acted on at note-on only, and the same key twice within 400 ms counts once,
  so a heavy hand does not start and stop the band.
- The three keys are a control zone. They are never judged, never shown as played notes, never
  named in a chord and never recorded in a take. The Play screen leaves them out of the
  band's scoring entirely.
- The keys work on any connected MIDI input, not only the remembered one, and need no setup.
- A smaller keyboard has no C8. Making the control key settable is listed after v1.

**One-screen layout.** The shell (`improv.css`) gives the window to the page: a compact menu
on top and a main area that takes the rest of the height. A screen is a grid of panels in that
area. The Play screen puts the transport, chart and keyboard in the left column and the
settings and mix in a narrow right column. Every other screen is a root `im-screen` holding
a header line and a grid of columns (`im-cols`), each panel either sized to its content
(`im-flat`) or sharing what is left (`im-fill`). A list that can grow without limit carries
`data-bounded-list` and is the only kind of element that may scroll inside itself. Below
60rem wide or 34rem tall (a phone, a small window) the shell steps aside and the page flows
and scrolls like any page, because that is not the piano setup. Guard: a browser test
(`tests/test_spri_7_5_browser.py`) opens every screen at 1280 by 720 and 1920 by 1080 with a
month of practice, forty takes and the longest chart, and fails when the page is taller or
wider than the window or when anything unmarked scrolls inside itself. Today and Lessons
must also fit without their lists scrolling at 1280 by 720.

| Screen | What it is for |
|---|---|
| **Today** | the landing page: the streak, the daily goal as a progress ring, the three workout exercises, and a "continue" to the lesson in progress |
| **Play** | the main screen. The chart with the current bar lit, transport (play, count-in, loop, tempo, key, swing, band mix), the keyboard with live note colours, the recognized chord, and the timing strip. Free practice and exercises use the same screen |
| **Progressions** | browse the library by genre, tag and difficulty; open one in Play; make your own |
| **Chart editor** | type the chart text, see it parsed bar by bar, hear it, and get the first error where it is |
| **Lessons** | the path as a map: tracks, locked and done states, level; one lesson page does Read, Hear, Play |
| **Reference** | any chord or scale in any key, lit on the keyboard, with its intervals and the scales that fit it |
| **Progress** | the practice log, streak calendar, XP and level, the weakness report, personal bests |
| **Takes** | saved takes with replay over the same band, and delete |
| **Setup** | MIDI input and output choice, calibration, demo output, daily goal, sharps or flats |

**Today and Progress (SPR-I.6.1).** Today is the page at `/improv/` and the first item in the menu.
It holds the daily goal as a ring (a conic gradient set from one CSS variable, with the minutes
written inside it), the streak, the three workout exercises each with a Play link, and a button into
the lesson in progress. The lesson to go on with is its own read, `GET /improv/api/continue/`
(`progress.continue_lesson`): an open lesson with some exercises passed comes first, otherwise the
first open lesson in the order of the path, never a draft, a locked lesson or one with nothing to
play, and when everything is done the page says so instead. Progress is at `/improv/progress/`: the
level and XP with a bar, the streak and a five-week calendar (Monday first, the last week holding
today; a gold day met the goal, an outline day had some practice), the weakness report, and the five
best takes. The words and the calendar are pure functions in `static/improv/today.js`, tested under
Node, and each page only reads derived endpoints, so it says what every other screen says. The
Practice screen stays as the plain log and the workout; the weakness panel moved off it to Progress,
where the spec put it. Nothing new is stored.

**Retention and the deploy (SPR-I.6.2).** A take not kept loses its events once it is more than
thirty days old and keeps its score, metrics, chart, key and judge version, which is everything the
weakness report and the bests read. The prune is `retention.prune(player)`, run inside the same
transaction that saves the player's next take, and only for that player: a read never prunes, and a
save that fails prunes nothing. A kept take is never pruned. The Takes screen says "The notes were
cleared after 30 days. The score stays." on such a take and turns off Replay and Keep, and the API
answers 400 to a request to keep one, since a kept take with nothing to replay would be a lie. The
deploy runs all four seed commands, theory, library, lessons and challenges, each as
`(python manage.py <name> || true)` after the ordinary `migrate`, so a seed that fails never keeps the
site down, and each adds only the rows that are missing.

**Play in version 1 so far (SPR-I.2.4).** `/improv/play/` loads the progressions, the
styles and the chord qualities from the API, so it plays whatever the library holds.
It has the chart as a grid of bars, four to a row, with the playing bar lit and a
bar-long progress line; Play and Stop (Space does the same); the progression and the
band; the key (twelve keys in the progression's major or minor, the chart redrawn in
that key); tempo held to the band's own range; swing or straight; a count-in of none,
one or two bars of click, played once and never again when the loop comes round;
a loop over a range of bars (typed 1-based, blank means the whole chart, the bars
outside the loop dimmed); metronome only, which is a click on every beat of the same
bars; and a mix with a level and a mute for the drums, the bass, the comping and the
click. The shape of the take locks while it plays (the progression, the count-in, the
loop range and the metronome switch) and the rest stays live, which is SPR-I.2.6 below.
The logic is `static/improv/play.js`, tested under Node; the page script is only glue.

**Changes while it plays, and the output picker (SPR-I.2.6).** The key, the tempo, the
feel (swing or straight) and the band stay live while it plays. Each change is built into a
new plan at once and handed to the scheduler, which swaps it in at the first bar not yet
queued, so nothing sounds mid-bar and there is no gap and no overlap; a tempo change goes in
at that same bar line. The chart is redrawn when that bar line arrives, not when the control is
touched, so the screen and the sound agree. A change that would alter the shape of the take is
refused with a plain message and the band plays on as it was; Stop drops a change that was still
waiting. The output picker ("Sound goes to") lists the audio outputs the browser reports, with
the system default first, and sends the sound there with `AudioContext.setSinkId`, also while it
plays. It never asks for the microphone, so Chrome and Edge may only give numbered names
("Output 2") until the site has been allowed one; the page says so. If the chosen output is
unplugged, or the browser refuses it, the sound goes back to the system default and the page
says so. Where the browser has no `setSinkId` (Safari, and so an iPad), the picker is not shown
and a note says to choose the output in the device's sound settings; Play works the same. The
rules are `scheduler.js` (`setPlan`), `play.js` (`canGoLive`) and `output.js`, tested under Node.

**Setup in version 1 so far (SPR-I.3.1).** `/improv/setup/` is where a person's own
profile lives, made on their first visit to any improv page rather than by a signal on
the account. It asks the browser for MIDI without sysex, never for the microphone, and
lists the keyboards it finds, plugged-in ones first. The keyboard is remembered **by
name**, not by port id, because an id is not promised to be the same next session while
the name is what the player recognises; so the same piano is picked up again after a
replug even on a new id. Unplugging and replugging is handled where it happens, with a
sentence saying what changed, and never needs a reload. Pressing keys shows the note
names, which is how a player can tell the wiring works before trusting a score. The
screen also holds the note spelling, where demos sound, the daily goal and the timezone,
each checked on the page before the server sees it. Where there is no Web MIDI the page
says so plainly and everything else on it still works. The rules are
`static/improv/setup.js`, tested under Node; the page script is only glue.

**Reading the piano in version 1 so far (SPR-I.3.2 to I.3.5).** What is held down is named
on the Setup screen as it is played: every chord quality in the table is tried over every
root and scored by how much of it is being held and how much is left over, so the table stays
the only thing that says what a chord is. The bass is preferred as the root; a root that is
not the bass makes a slash chord rather than a different chord (C, E and G over an E is C/E);
a complete reading beats an incomplete one with the bass as its root (C, E and A is Am/C, not
a C6 with no fifth); and a reading that leaves a note of the chord out, or that has to treat
the lowest note as a foreign bass, is shown as a best guess with the other readings of the
same notes beside it. Fewer than three notes are never forced into a chord name: they are
shown as notes and the interval between them, except that a tritone is offered as the two
dominant sevenths it is the third and seventh of, which is the rootless shell a player
actually holds. A run of single notes is matched against the scale table over a few seconds,
and nothing is claimed until five different notes have been heard, because three notes fit a
dozen scales; the closest fit comes first, counting the notes of the scale left unplayed, and
a minor pentatonic is told from its relative major pentatonic by which note the run started
on. The Reference screen (`/improv/reference/`) does the same work in reverse: any chord or
scale, in any of the twelve keys, lit on a drawn keyboard with the interval written on each
key, its notes named, and the scales that fit a chord or the chords that fit a scale listed in
the order the theory table prefers. Everything follows the player's own sharps-or-flats
setting. The rules are `static/improv/recognize.js` and `reference.js`, tested under Node with
golden cases, including one that every row of both tables can be reached by playing it.

**The judge in version 1 so far (SPR-I.4.1).** `static/improv/judge.js` is one pure function,
judge_version 1. The notes played, the chart they were played over, the tempo, feel and grid,
the scoring kind and the player's latency offset go in; a class for every note, the timing, the
metrics and the score come out. Run with `now` while it plays and without it at the end, so the
screen and the score come from the same rules. The chord sounding at a moment is found with the
half-beat look-ahead and the judged bars loop; the four classes are as the table above says,
with the approach note pending until the next note lands or a beat runs out; timing is against
the beat, the eighth or the swung eighth (the swung off-beat where the band's own swing puts it),
with a tolerance of a tenth of a beat and the result in words. Notes before the first judged
downbeat by more than half a beat are the count-in and are not judged. Three scoring kinds so
far: chord tones on the named beats, scale only (chord or scale tones, so an approach note does
not count), and free play, which has metrics and no score. The golden takes are
`tests/js/fixtures/takes.json`, every one a hand-checked judgement over a real chart with the
app's own theory table, so a change to the rules is a fixture diff and a deliberate version bump.

**Live feedback in version 1 so far (SPR-I.4.2).** The Play screen hears the piano while the
band plays. Each note is put on the take's own clock (milliseconds from the first judged
downbeat, the count-in negative, the second time round the loop carrying on) through the anchor
between the MIDI clock and the audio clock, never the wall clock, and the judge runs over the
take as it grows. The held keys wear the judge's colours (green for a chord tone, brighter for
the third and seventh; blue in the scale; amber for an approach note or one still being decided;
red, soft, for outside), the chord being held is named, and a running sentence says how many
notes, how many chord tones, and whether you rush or drag. At Stop the same judge settles
everything. Free play only, until the exercises arrive.

**Sessions and takes in version 1 so far (SPR-I.4.3).** A sitting is a `PracticeSession`,
opened the first time the band starts and closed, with the time the band ran, when the page is
left. Every play-through with a note in it is a `Take`, posted whole at Stop: the chart text,
the key it is written in and the key it was played in, the bar length, the tempo, the feel and
the bars played (the snapshot, self-contained), the events as the MIDI arrived, and the verdict
with the judge version that gave it. The server checks shape and range and keeps it; it does
not re-judge, which is the accepted limit of browser judging (data model, section 11). A run
with nothing played is not a take. Only `is_kept` may change afterwards. `/improv/api/sessions/`
and `/improv/api/takes/` are the player's own and nobody else's.

**Takes in version 1 so far (SPR-I.4.4).** `/improv/takes/` lists every take, newest first, in
words (where, what, how many notes, how it went), kept ones marked; Keep is one click, Delete
is two. Replay rebuilds the band from the take's own snapshot with `buildPlan`, exactly as Play
builds it, so a progression edited or deleted since changes nothing: one bar of count-in, the
chart lit bar by bar, and the player's notes sent either to the piano over MIDI (the output with
the piano's own name, every note with a timestamp on the clock the sound comes out on, every
note let go at Stop) or as a plain tone from the laptop, as `Player.demo_output` says.

**The scoring kinds in version 1 so far (SPR-I.4.5).** All seven of the table above except
comping voicings, which is v2 and is refused rather than scored as nought. Guide tones: a point
for every note that is a third or seventh, and a point for every chord change where the last
note before it and the first after it are both guide tones a step apart (a tone or less), which
is what "the guide tones connect" means at the piano. Approach notes: the targets are the chord
tones landing on the named beats (the downbeat unless the exercise says), and a target is
reached when the note before it was an approach note, which the judge already requires to be a
semitone away and within a beat. Rhythm motif: the pattern is beats inside the bar, repeated for
every bar played; an onset is matched by a note within the tolerance, and extra notes count
against, because hammering every eighth would otherwise match any pattern. Call and response:
the answer is what was played in the answer bar; each onset of the phrase in time is a point and
each step of the phrase whose direction the answer follows is a point, or, when exact notes are
asked for, each note that is the same note in any octave. Each kind says what it counted beside
the score, so a lesson can explain the mark. Adding kinds changed no existing score, so
judge_version stays 1. The golden cases are `tests/js/fixtures/scoring.json`.

**Calibration in version 1 so far (SPR-I.3.4).** The Setup screen plays four clicks to find
the pulse and sixteen more to tap against. Each tap is matched to the click nearest it on the
performance clock, with the clicks placed where they are *heard* (through
`getOutputTimestamp`), not where they were scheduled, which is the trap the timing spike
found. Two taps on one click count once, as a bounce. The mean is stored in
`Player.latency_offset_ms` and the spread is shown beside it; a run spread over more than
30 ms, or fewer than eight taps, is refused with a reason rather than quietly stored. Nothing
throws a tap away for being far from its click, because a tap is always within half a beat of
*some* click, so a filter like that could only ever fire on the setup with a huge delay that
most needs reporting. An output that reports more than 100 ms of its own delay is called out,
because one number cannot put Bluetooth right. The maths is the spike's `timing.js`;
`calibrate.js` adds only the calibration's own rules. **This sprint is accepted at the piano
and nowhere else.**

**Library and Editor in version 1 so far (SPR-I.2.5).** `/improv/library/` lists the forty
seeded progressions (and the player's own) as cards: title, level, genre, key, tempo,
bar count, the first eight bars as chord names, the tags, and Play or Edit (a preset
offers "Make my copy" instead). It filters by genre, tag, level, free text and "mine",
sorts by level, title or genre, shows a count beside each menu choice so a menu never
offers a choice that finds nothing, and keeps the filters in the address so a view can
be bookmarked. `/improv/editor/` is a text box for the chart with a live check: it shows
"OK: 12 bars" and the chart drawn as bars, or the line, the column and the bar of the
first mistake with a caret under it and a button that selects the word. Save stays off
until the chart parses and the form is valid. A preset opens as a copy, titled "(my
copy)", and saves as a new row of the player's own; the preset is never changed. A
row of the player's own can be saved again or deleted (two clicks). The server only
checks that a chart is not blank, so a client other than this editor could store a
chart that does not parse; Play then explains the error and will not start. This is a
recorded gap, not a bug, because the grammar lives in one place (`chart.js`). The logic
is `library.js` and `editor.js`, tested under Node; the page scripts are only glue.

The Play screen is the only complicated one. Its rule is that **nothing on it
needs a click during playing**: the learner's hands are on the piano, so
everything that has to be adjusted is adjusted before or between takes, and the
live display only shows.

### The trainer screens

`/improv/scales/` and `/improv/chords/` are specified in chapter 10 and follow both standing rules above.

---

## Chapter 9. Risks, named now

| Risk | What v1 does about it |
|---|---|
| Web MIDI or audio timing is worse in practice than on paper | Sprint 1 is a spike that proves MIDI in, band out and a timing readout on Avi's real piano and laptop before anything else is built on them |
| The laptop's audio delay makes timing scores nonsense | Calibration is a first-class screen and a stored number, not an afterthought |
| Chord naming is ambiguous for partial voicings | Show best guess plus alternatives; never claim certainty the notes do not support |
| "Outside note" feels like criticism of good playing | It is shown as information and only penalized where the exercise asks for it |
| Browser-side judging can be cheated | Accepted while the app is a free trial; the pure judge plus stored events and `judge_version` is the path to a server-side judge |
| AI-drafted lessons teach something wrong | `authorship` records what Avi has read; v1 lessons are all read before they are published |
| Scope: the feature list is long | v1 is the one loop (chapter 2); everything else waits until that loop has proved itself on Avi's playing |

### Spike result (SPR-I.1.2)

**Run on 2026-10-04, on the production page, Avi's own piano and laptop.**

- **Setup.** Chrome 154 on Windows 10/11, a Yamaha Clavinova over USB, listed by Web
  MIDI as "Clavinova (Yamaha Corp.)". Audio at 48 kHz, `baseLatency` 0.010 s,
  `outputLatency` 0.048 s, and `getOutputTimestamp()` available. MIDI note timestamps
  and the audio clock could be put on one timeline.
- **Steadiness of the pipeline.** Sixteen single eighth notes at 90 bpm (a 333 ms
  gap): the gaps between notes had a mean of 332 ms and a spread of 15 ms. That is
  an upper bound on the piano and browser jitter, because it includes Avi's own
  unevenness. Two notes struck together arrived 2 to 33 ms apart.
- **Offset against the click, on the eighth-note grid.** The page was left on the
  quarter-note grid for that run, so the figures here are worked out by hand from
  the sixteen offsets: on-beat notes averaged about -52 ms, off-beat notes about
  -44 ms against the half-beat, together about -48 ms (early) with a spread of about
  13 ms. One stored offset describes it.
- **Verdict.** The path works and is steady enough for a single per-player offset.
  The 30 ms threshold stays as the "usable" line: a steady human sits at about half
  of it, so it flags real trouble without failing a good take.
- **A coincidence to watch, not a finding.** The mean offset (about -48 ms) is close
  to `outputLatency` (48 ms). Either Avi leads the click by that much, as players
  tapping to a click usually lead it by 20 to 50 ms, or the page is placing the click
  too late by the output latency. One run cannot tell them apart. Epic 3 (calibration)
  settles it with a test that does not depend on how Avi plays: the app compares the
  piano's own sound with the click, or lets him slide the offset until it feels right.
- **Lessons that change the build.**
  1. A note must be judged against the grid of its exercise (quarters, eighths,
     triplets), never only the quarter click: eighth-note playing read 300 ms late
     against quarter clicks. The judge takes a grid parameter from day one.
  2. Notes must be compared with beats that are not yet scheduled, not only the ones
     inside the look-ahead window. The first version missed this.
  3. Chords arrive as separate notes up to about 30 ms apart; the judge groups notes
     struck within that window.
- **Not tested.** Unplugging and replugging the piano, a Bluetooth output (adds a
  large and variable delay), a background tab, and Edge. Treat Bluetooth audio as
  unsupported for scored takes until it is measured.

---

## Chapter 10. The scales and chords trainer (Epic I.8, Avi 2026-10-07)

Avi asked to focus on chord training. This chapter is what was agreed, in his words first.

> A scales and chords teacher and trainer. You get a scale, say D#, and play it with two
> hands in tempo: first two octaves with two notes per beat, then three octaves with three
> notes per beat, then four octaves with four notes per beat. It grades my accuracy and shows
> the fingering expected over the scale. That is the scale part. Then it teaches me all the
> chords of that scale and their positions, and trains me to identify them by letter. In the
> C scale it challenges me on "C7, first position", then "Cmaj7, second position", and when I
> hit it right it marks it and shows the next one. It measures how long I take to identify
> the chord, and shows it visually if I press a hint button.

His answers to the two open questions: the chord drills run **all twelve keys in circle-of-fifths
order starting from G** (changed after his live check, see "The live check" below: it starts at C), and the scale tempo
**defaults to 60 bpm, can be changed, and is remembered for next time**. Everything else below
was proposed back to him and accepted ("all the rest you got it").

Both screens follow the two standing rules of chapter 8: one screen with no scrolling, and the
piano's top keys as the buttons (C8 Start, B7 Hint, A#7 Skip).

### The scale trainer (`/improv/scales/`)

**What the player does.** Chooses a key (a major scale for now), a level, and a tempo. Presses
Start (or C8). Four clicks count in, then the click keeps the beat and the player plays the scale
**with both hands in parallel motion, up and then back down**, finishing on the tonic.

**Levels.** They are selectable, not locked, so Avi can start anywhere.

| Level | Octaves | Notes per beat | Steps up and down |
|---|---|---|---|
| 1 | 2 | 2 (eighths) | 29 |
| 2 | 3 | 3 (triplets) | 43 |
| 3 | 4 | 4 (sixteenths) | 57 |

A step is one note in each hand, so the player plays two keys at the same moment. Steps are 14 times
the octaves, plus one. The right hand plays an octave above the left. The left hand starts on the
tonic two octaves below middle C (MIDI 36 plus the root) for every length; the player can pick another octave on the screen (see "The live check"). The
right hand always stays below A#7 (MIDI 106), because the top three keys are the control keys: where
the top note would reach it (B and Bb in four octaves) the whole scale moves down an octave. **Four
octaves needs an 88-key piano.** The screen says so on that level, rather than failing silently on a
smaller keyboard.

**Fingering.** Shown for both hands as a strip of cells, one per step: the note name above and the
finger number below, the current step lit. It is data, not a calculation: a `ScaleFingering` row per
key and hand (data model, section 6a), taken from the standard published fingerings, thumb is 1. The
descending fingering is the ascending one reversed. A key with no stored fingering says so and can
still be played; a fingering is never guessed.

**Grading.** Pitch and timing, both against the grid.

- Each step expects its two notes at `start + step * beat / notes_per_beat`, with the player's
  `latency_offset_ms` taken off every note, as in chapter 5.
- A played note counts for an expected note when it is the same MIDI number and falls within half
  a step of the expected time. Notes that match nothing are *extra* (wrong or doubled keys).
- **Pitch accuracy** is the matched notes divided by (expected notes plus extra notes).
- **Timing accuracy** is the share of matched notes within the tolerance of the grid: 40% of a step,
  never less than 50 ms and never more than 120 ms.
- **Score** is 0 to 100: 70% pitch, 30% timing. **Pass at 80.**
- The result lists the steps that were missed or wrong and the average offset (early or late), so the
  report says where to work, not only a number.
- The judge is a pure function (`scale.js`), like the chapter 5 judge, and a run is stored with the
  `judge_version` that scored it.

**Tempo.** The tempo is a field on the screen, 30 to 160 bpm, default 60. Changing it saves it to
the player (`Player.trainer_tempo`), so the next visit opens at the last tempo used.

**Key names.** Standard spelling for each key (Db, Eb, Ab, Bb); F#/Gb follows the player's
sharps or flats setting. Avi's "D#" is shown as Eb, which is the same key.

### The live check (SPR-I.8.7, Avi 2026-10-07)

After playing the pushed trainer Avi said: C8 did not start anything; start with C and then G, D, A,
E; ask for the next length immediately, 2, 3, 4 notes a beat; the scale should start lower, or follow
where he wants to start; and on the Play screen the backing track drowns his own playing. What changed:

- **The circle starts at C**, then G, D, A, E, B, F#/Gb, Db, Ab, Eb, Bb, F, for both screens and for the
  "work on this" line.
- **Keep going.** A checkbox, on by default and remembered. A passed run goes straight on to the next
  length in the same key (2 octaves and 2 notes a beat, then 3 and 3, then 4 and 4) after a two second
  pause, with the usual four-click count-in. Pressing Start or C8 during the pause starts at once.
  A pass at four octaves moves to the next key at two octaves and waits, because the hands have to
  move. A run that did not pass stays where it is and waits. Stop with C8 or the Stop button.
- **Where it starts.** The left hand's tonic defaults to two octaves below middle C (C2 for C). A
  select, "Left hand starts on", offers every octave the scale fits in without leaving the piano or
  touching the control keys; the choice is remembered in the browser and kept when the key changes,
  and a start a key cannot fit is moved to the nearest one that can.
- **Heard keys.** The header shows the last key the browser heard from the piano ("heard C8 (108)"),
  so a key that does nothing can be told apart from a key that never arrived. The control layer also
  keeps hold of its MIDI access: Chrome stops delivering a port's messages once nothing references
  its access object, which fits "it worked, then C8 did nothing".
- **A quieter band.** The Play mix starts at 25 to 40 percent (it was 70 to 90) and each level and mute
  is remembered in the browser.
- **The Reference screen.** A scale with stored fingering (the major scale, in every key) now shows a
  strip with the right hand and left hand finger under each note, running up two octaves; coming down
  is the same in reverse. A scale with none says so. The chord menu names each chord as it is written
  in the chosen key, then what it is called: "Cmaj7  -  Major seventh", "Cm  -  Minor triad".

### Show me (SPR-I.8.9, Avi 2026-10-08)

On the bossa challenge Avi asked for "a button show me so you can demonstrate to me what you expect".
An exercise on the Play screen now has a **Show me** button (A#7, the third piano key) next to the
back link. It plays the answer over the band and the count-in, lights the bar and the keys as it
goes, and stops by itself at the end of the bars.

- **What can be shown.** Every kind with an answer: scale only, chord tones on beats, guide tones,
  approach notes, rhythm motif and call and response. Free play has no answer, so the button is
  hidden there. It is greyed out while a take is running or when the chart or bars were changed so it
  is no longer the exercise, and the button's tooltip says so.
- **What is played.** `static/improv/demo.js` (pure, tested under Node) builds the notes from the
  same chart and chord table the judge reads. A rhythm is played on the exact written beats in
  chord tones, moving to the nearest tone of each chord. A line under the keys says in words what
  is being shown ("In every bar, a chord tone on beat 1, the and of 2, beat 3 and the and of 4").
- **Proof it asks the right thing.** The Node tests run the demonstration for all 23 seeded
  exercises through the real judge and require a pass. The demonstration is therefore a passing take
  by construction and cannot drift from the exercise.
- **Where it sounds.** Over MIDI out on the piano when the profile says so and an output port
  exists, otherwise a plain tone from the laptop, the same as the lessons. The band stays on the laptop.
- **What it is not.** It is not a take. Nothing is recorded, judged or saved, no session or practice
  clock starts, and no XP is earned. While it plays the settings are locked. Play (or C8) ends it and
  starts a real take; the button, or the third key, stops it early and lifts every note.

### The chord trainer (`/improv/chords/`)

**The pool for a key.** The seven diatonic triads and the seven diatonic seventh chords of the major
key, and the two borrowed dominants **I7 and IV7**. The borrowed ones are there because Avi's own
example, "C7 in C", is not diatonic: it is the dominant of F, and a trainer that refused to ask it
would be wrong about what he wants. In C: C, Dm, Em, F, G, Am, Bdim; Cmaj7, Dm7, Em7, Fmaj7, G7,
Am7, Bm7b5; C7, F7.

**Positions.** The same chord in its inversions. Avi's wording is *first position, second
position*, so: **first position is root position, second is the first inversion, third is the
second inversion, and fourth (sevenths only) is the third inversion.** The screen shows both
names. The lowest note must be the expected bass for the answer to be right.

**Modes.**

- **Learn.** Pick a key; all its chords and positions are listed, and any one can be shown on the
  keyboard. Nothing is scored.
- **Drill.** One key. Each prompt is a chord and a position, for example "Cmaj7, second position". The
  prompt stays until it is answered; hitting the right chord marks it and moves on.
- **Circle.** The same drill through all twelve keys in the order above, one prompt per chord of the
  level's pool in each key, each with a random position: 84 prompts at levels 1 and 2, 108 at level 3
  (nine chords a key). The key changes on screen.

**Levels.** 1: triads in their three positions. 2: sevenths in four positions. 3: sevenths plus I7 and
IV7, the dominant colours.

**What counts as right.** The set of pitch classes is the chord's, any octave, either hand, and the
lowest note sounding is the expected bass. A **wrong chord** shows what was played (the recognizer
of chapter 4 names it), counts as a miss for this prompt, and the prompt stays. A prompt's `is_correct`
is true only when it was answered with no wrong tries. The **response time** runs from the prompt
appearing to the right chord, and includes the wrong tries, because the time to know it is what is
measured.

**Hint.** The Hint button (B7) lights the answer on the on-screen keyboard. The attempt is stored with
`hint_used`, so a hinted answer is visible in the history and does not count as a clean one. **Skip**
(A#7) moves on, stored as a miss without a time.

**What is kept.** Every answered or skipped prompt is a `DrillAttempt` (data model, section 7),
and every scale run is a `ScaleRun`. A derived read, `GET /improv/api/trainer/`, returns the best score
per key and level, the slowest chords and the weakest keys, and the screens show them as "work on this".
