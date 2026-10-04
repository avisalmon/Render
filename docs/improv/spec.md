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
later without a rewrite. Until it is stable it is private to him, and nobody
else can see the link or the app.

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

- Access is a Django group with a superuser bypass; everyone else gets a 404.
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
ships about six lessons, one from each of the first six tracks, in this order of
difficulty:

1. Chord tones over a ii-V-I.
2. Guide tones: the third and seventh, and how they connect.
3. A scale for each chord: Dorian, Mixolydian, Major.
4. Approach notes from a half step.
5. A rhythm motif, repeated and varied.
6. Call and response over a blues.

Voicings and comping, ear training and the rest follow after v1.

### The cycle of a lesson

Every lesson is the same three steps, in this order, so the learner always knows
where they are:

1. **Read.** A short explanation (`Lesson.explanation`), a screen or less.
2. **Hear.** The demo phrase plays over the lesson's progression, with the notes
   lighting on the on-screen keyboard.
3. **Play.** The lesson's exercises, one after another, over the band, each judged
   as in chapter 5. A lesson is done when every exercise has a `Completion`.

A lesson unlocks when its `prerequisite` is done. Nothing else locks content: a
standalone challenge or free practice is always open.

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

### The daily workout

Three exercises, picked from the `daily_eligible` ones the player has unlocked:
one that targets the weakest area in the weakness report, one old completed
exercise as a review, and the next unfinished one. The pick is a function of the
player and the date, so the same three show all day and a reload does not
shuffle them.

### The weakness report

Read from the last thirty days of takes: per scoring dimension and per chord
family, where the player's chord-tone, scale, outside and timing numbers are
worst. It says nothing until there are enough notes behind a claim (twenty in a
bucket), because "you struggle with m7b5" from four notes is noise. It names at
most three things, in plain words, each with an exercise that works on it.

### Challenges and takes

A challenge is an exercise with no lesson; its personal best is the best take for
it, a read. A saved take (`is_kept`) is replayed from its events over the same
chart, key and tempo it was played at, through the demo output. Unkept takes lose
their events after thirty days and keep their score and metrics, which is all the
weakness report needs. Pruning happens when the same player saves their next take,
because Render's scheduled jobs cannot see the SQLite disk and a prune that needs
a scheduler would not run.

---

## Chapter 7. Access, the portal link and the API

### The gate

As the data model, section 0: one function, signed in and in the Django group
`improv_players`, superuser bypass, and **404 for everyone else**, including
anonymous visitors and including every URL under `/improv/` and the API. The
group is created by a migration. At launch it is empty; Avi is in by being a
superuser.

**Static files are not behind the gate.** WhiteNoise serves `/static/improv/` before
Django routing runs, so the stylesheet and scripts are public. That is accepted:
they are code, not data, and no player's content is ever a static file. The
consequence is that the improv code can be read by anyone who guesses its path;
nothing private is in it.

**How the gate is built.** `improv.middleware.GateMiddleware` stops every request
under `/improv` before routing, CSRF and the views. It sits late in the middleware
stack so a refusal has had everything done to it that a real 404 gets (session,
first-visit strip, cookies). It answers with the site's own 404 and points the
request at an empty urlconf so Django's append-slash redirect cannot reveal that
`/improv/` exists. **There is deliberately no improv-branded 404 page**: a branded
page would tell a stranger what they found. This is a recorded exception to the
rule that each app owns its error pages. The gate is covered by a sweep over every
route the app registers and by a test that a refusal is the same page, with the
same cookies, as a URL that does not exist. A DRF permission class repeats the check
inside the API as defence in depth (SPR-I.1.4).

### The portal

One `App` entry with `audience=GROUP`, `key="improv_players"`, `admin_bypass=True`:
the card shows for superusers and group members and for nobody else. The existing
portal sweep test already fails if a card is ever shown to someone the door would
turn away. The link goes from babook to improv; nothing in improv links back.

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

An anonymous request, a signed-in non-member and a member are each sent to every
route the app registers, and the test asserts the 404 or the 200, so a route
added next month cannot quietly skip the gate.

---

## Chapter 8. Screens

The app has its own base template and its own English menu. Laptop first; other
sizes degrade to readable rather than being designed for.

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

---

## Chapter 9. Risks, named now

| Risk | What v1 does about it |
|---|---|
| Web MIDI or audio timing is worse in practice than on paper | Sprint 1 is a spike that proves MIDI in, band out and a timing readout on Avi's real piano and laptop before anything else is built on them |
| The laptop's audio delay makes timing scores nonsense | Calibration is a first-class screen and a stored number, not an afterthought |
| Chord naming is ambiguous for partial voicings | Show best guess plus alternatives; never claim certainty the notes do not support |
| "Outside note" feels like criticism of good playing | It is shown as information and only penalized where the exercise asks for it |
| Browser-side judging can be cheated | Accepted while the app is private; the pure judge plus stored events and `judge_version` is the path to a server-side judge |
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
