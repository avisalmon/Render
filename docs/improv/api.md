# improv API

Everything is under `/improv/api/`, JSON, session authentication. This file is
checked by a test: every model in the app must have an endpoint, and every endpoint
must be listed here (`tests/test_spri_1_4.py`).

## Access

One rule for every endpoint: signed in and in the group `improv_players`, or a
superuser. **Anyone else gets a plain 404**, anonymous visitors included, so the API
does not announce that it exists. The rule is enforced twice: by the gate middleware
before routing, and again by the `IsPlayer` permission class on every view, so the
API stays closed even if the middleware is ever removed or reordered.

## Conventions

- Short reference tables come back whole, as a JSON list, with no paging.
- Reference rows (chord qualities, scales, chord scales, tags, lessons, exercises) are read-only here.
  They are edited in the Django admin. A write verb (POST, PUT, PATCH, DELETE)
  answers 405.
- Content a player can own (styles, progressions, phrases) is writable for the player's own
  rows only; see "Your own content" below.
- Filters are query parameters and an unknown value gives an empty list, not an error.

## Index

`GET /improv/api/` lists every endpoint below with its URL.

## Reference (read-only)

### Chord qualities

`GET /improv/api/chord-qualities/` and `GET /improv/api/chord-qualities/{id}/`

One row per chord type: `id`, `symbol` (`m7`), `name`, `family`, `intervals`
(semitones above the root), `roles` (semitone to role, `{"3": "third"}`),
`aliases` (other spellings the chart parser accepts), `sort_order`, and `scales`:
the scales that fit the chord, first choice first, each with `slug`, `name`,
`intervals`, `preference`, `note`.

### Scales

`GET /improv/api/scales/` and `GET /improv/api/scales/{id}/`

`id`, `slug`, `name`, `family`, `intervals`, `parent_slug` (the scale this is a mode
of, or null) and `mode_number`.

### Chord scales

`GET /improv/api/chord-scales/` and `GET /improv/api/chord-scales/{id}/`

The pairing of a chord quality with a scale: `id`, `chord_quality`, `quality_symbol`,
`scale`, `scale_slug`, `preference` (1 is the first choice), `note`.

Filters: `?quality=m7` (by symbol), `?scale=dorian` (by slug). Ordered by chord, then
preference.

### Tags

`GET /improv/api/tags/` and `GET /improv/api/tags/{id}/`

`id`, `name`, `slug` and `progressions`, the number of progressions with that tag
that you can see (presets plus your own). Read-only: tags are the library's
vocabulary and are edited in the admin, so "every minor ii-V" stays one query.

## Your own content: styles and progressions

These two are the first endpoints with writes. The rules are the same for both:

- The list is the **presets plus your own rows**, whole, with no paging. Another
  player's rows do not exist for you: a read, change or delete of one is a 404.
- **Presets are read-only.** Changing or deleting one answers 403, whoever you are,
  the site admin included. Presets are edited in the Django admin, because a change
  to one is a change for every player.
- Creating a row makes it yours. `owner`, `is_preset` and `slug` are not accepted
  from the client: the server sets the owner to you, `is_preset` to false, and the
  slug from the name (`my-groove`, `my-groove-2`, ...). The slug does not change
  when the name does, so links keep working.
- The payload says `is_mine`, never who the owner is.
- A bad value is a 400 naming the field.

### Styles

`GET, POST /improv/api/styles/` and `GET, PUT, PATCH, DELETE /improv/api/styles/{id}/`

A groove for the browser band. `id`, `name`, `slug`, `genre` (jazz, blues, pop, rock,
gospel, latin, funk), `feel` (swing, straight, shuffle), `swing_ratio` (0.50 to 0.75;
0.50 is straight), `time_signature` (`2/4` to `12/4`), `default_tempo`, `min_tempo`,
`max_tempo` (20 to 300, default between min and max), `drums`, `bass`, `comp`,
`is_preset`, `is_mine`.

`drums`, `bass` and `comp` are checked as a whole before anything is saved, by one
function that the model, the admin and this endpoint all use
(`improv/grooves.py`), so a groove the band cannot play is refused, not stored. The
shapes are in [data_model.md](data_model.md) under Style.

Filters: `?genre=`, `?feel=`, `?mine=1`.

### Progressions

`GET, POST /improv/api/progressions/` and `GET, PUT, PATCH, DELETE /improv/api/progressions/{id}/`

A chord chart plus how to play it. `id`, `title`, `slug`, `genre`, `tags` (a list of
tag slugs; an unknown tag is a 400, tags are not made here), `chart`, `home_key`
(`C`, `Eb`, `F#m`), `time_signature`, `default_tempo`, `default_style` (a style id
you can see: a preset or one of yours, or null), `difficulty` (1 to 5),
`description`, `is_preset`, `is_mine`, `created_at`, `updated_at`.

The server checks that the chart is there and not absurdly long (20 000
characters). It does **not** parse it: the grammar below lives in one place, in
`static/improv/chart.js`, and the editor shows the parse error where the cursor is.
The presets are guarded by a test that parses every one of them.
A client that skips the editor can therefore store a chart that does not parse; Play
then shows the error and will not start it. This is a recorded gap.

Filters: `?genre=`, `?tag=<slug>`, `?difficulty=<1-5>`, `?mine=1`, `?q=<text>`
(title or description). Easiest first, then by title. An unknown value, or a
difficulty that is not a number, gives an empty list.

### Phrases

`GET, POST /improv/api/phrases/` and `GET, PUT, PATCH, DELETE /improv/api/phrases/{id}/`

A short run of notes: a lesson's demo, the prompt in call and response, or a lick of your
own. `id`, `name`, `slug`, `kind` (demo, call, answer, lick), `notes` (a list of
`{midi, beat, length, velocity}`), `length_beats` (0.25 to 64), `chart_context` (the chords
it needs underneath, or empty), `written_in_key` (so it can be moved with the chart),
`is_preset`, `is_mine`. The same rules as styles and progressions apply: presets are read-only,
yours are yours.

The notes are checked before anything is saved, by one function (`improv/teaching.py`) that
the model, the admin and this endpoint share: at least one and at most 200 notes, `midi` a
whole number 0 to 127, `beat` from 0 and inside `length_beats`, `length` above 0, `velocity`
a whole number 1 to 127. A phrase the page could not place is refused, not stored.

Filter: `?kind=`.

## Lessons and exercises (read-only)

These are content written during development and seeded once (`seed_improv_lessons`), the
same as the presets, so there is no write here: POST, PUT, PATCH and DELETE answer 405.
They are edited in the Django admin. The six starter lessons (one per scored track, 18
exercises, 6 demo phrases) come from `improv/seed_data/lessons.json`; `seed_improv_lessons`
adds what is missing and never overwrites, and each is seeded with `authorship` set to
`ai_drafted` until Avi has read it.

A lesson is **hidden until it is published**. A member gets the published lessons and
nothing else, and a draft is a 404 by id, not only missing from the list. A superuser gets
the drafts too, which is how a lesson is read before it is published.

### Lessons

`GET /improv/api/lessons/` and `GET /improv/api/lessons/{id}/`

`id`, `track` (chord_tones, guide_tones, scales_modes, approach_notes, rhythm_motifs,
call_and_response, voicings_comping), `order` (inside the track), `title`, `slug`, `level`
(1 to 3), `summary` (one line for the card), `explanation` (markdown, a small subset:
`##` and `###` headings, paragraphs, `-` and `1.` lists, bold, italic, code; the page
draws it as text and never as markup), `demo_phrase` (a phrase id or null), `progression`
(id or null) and `progression_slug`, `style` (id or null), `prerequisite` (a lesson slug
or null), `exercises` (the slugs of its exercises, in order), `authorship` (ai_drafted,
reviewed, avi_written: who wrote it, so the page can say a lesson has not been read yet),
`status` (draft, published), `created_at`, `updated_at`; and three fields that are
**yours**, read from your completions and never stored on the lesson: `state` (`open`,
`locked` or `done`), `exercises_done` and `exercises_total`. A lesson is `locked` while the
lesson it follows still has an exercise you have not passed (a locked lesson keeps every
lesson after it locked too, even one with nothing to play), `done` when it has exercises and
you have passed them all, and `open` otherwise. A locked lesson can still be read and heard.

In the order a player meets them: the tracks in the order above, then `order`.

Filter: `?track=`.

### Exercises

`GET /improv/api/exercises/` and `GET /improv/api/exercises/{id}/`

One playing task and how it is scored. `id`, `slug`, `lesson` (a lesson slug, or null for a
standalone challenge), `order`, `title`, `instructions`, `progression` (id) and
`progression_slug`, `key`, `tempo`, `style` (id or null), `bars` (how much to play),
`scoring_kind` (chord_tones_on_beats, guide_tones, scale_only, approach_notes,
rhythm_motif, call_and_response, comping_voicings, free_play), `scoring_params`, `pass_score`
(0 to 100), `xp`, `daily_eligible`; and two fields that are yours: `completed` (you have
passed it) and `locked` (its lesson is locked for you; a challenge is never locked).

`scoring_params` is checked when the row is saved, because a typo there would otherwise
surface as a take that can never pass. Its shape is the one `static/improv/judge.js` reads:
`chord_tones_on_beats {beats}`, `approach_notes {beats}`, `guide_tones {step}`,
`rhythm_motif {pattern}`, `call_and_response {phrase, answerBar, exact}`; `scale_only` and
`free_play` take none. `comping_voicings` is a later version and is refused as a scored kind.
The kinds the Python knows are tested to be the kinds the judge scores. A parameter the
kind does not take, a beat outside the bar, or an `answerBar` outside the exercise's own
bars is refused with a sentence saying which.

An exercise of an unpublished lesson is hidden the same way the lesson is. A challenge has
no lesson and is always visible.

Filters: `?lesson=<slug>`, `?challenge=1` (no lesson), `?daily=1` (may be picked by the
daily workout).

## Your own profile

### Player

`GET, PUT, PATCH /improv/api/player/`

Your own profile, and the one endpoint with **no id in the route**. There is exactly
one row per person, made on your first visit to the app, so there is nothing to list
and nothing to create; an id in the route would only invite asking for somebody
else's row, which this app will not answer. There is no DELETE either: it would throw
away the calibration that makes timing mean anything. POST and DELETE answer 405.

`id`, `username` (read-only), `daily_goal_minutes` (5 to 240, default 15),
`latency_offset_ms` (-500 to 500, default 0, written by calibration and subtracted
from every note time when a take is judged), `midi_input_name` (the keyboard last
used, **by name**: a MIDI port's id is not promised to be the same next session),
`note_names` (`sharps` or `flats`), `demo_output` (`piano`, over MIDI, or `laptop`,
as a plain tone), `trainer_tempo` (30 to 160, default 60, the scale trainer's tempo, saved when it is changed), `timezone` (an IANA name, default `Asia/Jerusalem`, because the
site runs on UTC and a streak is made of your own days), `created_at`.

Whose profile it is cannot be changed: `username` and `id` are read-only, and the
row you get is always the one belonging to the person signed in.

## Your own playing: sessions and takes

These rows are the player's own and nobody else's. Another player's session or take
does not exist for you: a read, change or delete of one is a 404. A new row is yours.

### Sessions

`GET, POST /improv/api/sessions/` and `GET, PUT, PATCH, DELETE /improv/api/sessions/{id}/`

One sitting at the piano. `id`, `started_at` (set by the server), `ended_at` (null until
the sitting ends), `active_seconds` (time the band was running or a note was played, not
time the tab was open; at most a day). POST with an empty body opens a session; the page
closes it with PATCH when it leaves. The practice log (feature 16) reads this table.

### Takes

`GET, POST /improv/api/takes/` and `GET, PATCH, DELETE /improv/api/takes/{id}/`

One play-through, whole. `id`, `session` (one of yours), `progression` and `style` (a
preset or one of yours, or null), `exercise` (the slug of the exercise the take was played
for, or null for free play; a draft lesson's exercise is refused like one that does not
exist, and it cannot be changed after the take is posted), then the **snapshots**: `chart` (the chart text as
played), `home_key` (the key that text is written in), `key` (the key it was played in),
`time_signature` (`2/4` to `12/4`), `tempo` (20 to 300), `swing_ratio` (0.50 to 0.75), `loop_from` and
`loop_to` (the bars of the chart that were played, 0-based, `loop_to` one past the last),
`bars` (`loop_to - loop_from`), `started_at`, `duration_ms`; the playing: `events`, a list
of `{t_ms, type: "on" | "off", note 0..127, velocity 0..127}` as the MIDI arrived, `t_ms`
being whole milliseconds from the first judged downbeat (the count-in is negative time);
and the verdict: `score` (0 to 100, or null for free play), `metrics` (an object: chord
tone, scale, approach and outside shares, mean timing offset, spread), `judge_version` (the
version of `static/improv/judge.js` that produced the score), `is_kept`, `created_at`, and
`completion` (read-only: `{id, xp_awarded}` when this take passed an exercise for the first
time, otherwise null; see "Your own progress").

**The server checks shape and range and does not re-judge.** It believes the score the
page computed, which is the accepted browser-judging limit (data model, section 11); the
events are kept so a later judge can disagree with a reason, and `judge_version` says which
rules a score came from. After a take is posted only `is_kept` may change: a PATCH with
anything else answers 403, because a take is a record of what happened. A take with no
events at all is still a take.

**Retention.** A take that is not kept loses its `events` (they become `[]`) once its
`started_at` is more than 30 days old; everything else on it stays. The server does this when
the same player saves their next take (`POST`), never on a read and never for another player,
and a kept take is never touched. A PATCH `{"is_kept": true}` on a take whose notes were
cleared after 30 days answers 400 with a message saying so, because there is nothing to
replay.

Filters: `?kept=1` (saved on purpose), `?progression=<slug>`, `?exercise=<slug>`. Newest first.

## Your own progress

### Completions

`GET /improv/api/completions/` and `GET /improv/api/completions/{id}/`

The exercises you have passed, newest first. **Read-only: POST, PUT, PATCH and DELETE answer
405**, because a completion is a fact the server records, not something the page reports.
When a take is posted with an `exercise`, the server makes the completion itself if all of
these hold: the take has a score at or above the exercise's `pass_score`; it was played over
the exercise's progression, from the first bar, for as many bars as the exercise asks; the
exercise's lesson is not locked for you; and you have not passed that exercise before. The
XP is read from the exercise row at that moment, so nothing the page sends can change it, and
it is kept on the completion, so editing the exercise later does not change XP already earned.
Passing again earns nothing. Another player's completions do not exist for you.

`id`, `exercise` (slug), `exercise_title`, `lesson` (slug, or null for a challenge), `take`
(the take that passed it, or null once that take has been pruned: the XP stays),
`xp_awarded`, `completed_at`. Filters: `?exercise=<slug>`, `?lesson=<slug>`.

### Practice

`GET /improv/api/practice/` (optional `?days=N`, 1 to 366, default 30; anything else reads as 30)

The practice log, today against the daily goal, and the streak, computed from your sessions and
your profile each time and stored nowhere. A day is your own day in your `timezone` (an unknown
zone reads as UTC), and a session belongs to the day it started on. `timezone`, `today` (a date),
`goal_minutes` (your `daily_goal_minutes`, applied to every day), `today_seconds`,
`today_minutes`, `goal_met`, `streak` (the run of days that met the goal, ending today, or
ending yesterday while today is still short, so an unfinished day does not break it),
`best_streak`, and `log`: the days in the last `days` that had practice, plus today, newest
first, each with `date`, `seconds`, `minutes`, `goal_met` and `sessions` (sittings with practice
in them). Read-only: POST, PUT, PATCH and DELETE answer 405. The numbers come from the sessions
resource above, which the page keeps up to date.

### Workout

`GET /improv/api/workout/`

Today's workout: up to three exercises, computed from your completions, your takes and your
profile each time and stored nowhere. The picks are a function of you, the date and what you had
passed before that day began, so a reload shows the same three, passing one during the day does
not change the other two, and tomorrow is a different set. The date is your own day in your
`timezone`. Only exercises marked `daily_eligible` are offered, never one in a draft or locked
lesson; a challenge (no lesson) is always open. `date`, `timezone`, `total`, `done_today` (how
many of the picks you have passed today), `complete`, and `items`, each with `slot` (`weak`,
`review`, `next` or `fresh`), `exercise` (slug), `title`, `lesson` (slug, or null for a
challenge), `lesson_title`, `scoring_kind`, `xp`, `xp_available` (0 for one you passed before
today, because replaying earns nothing), `pass_score` and `done_today` (a take of exactly that
exercise, from today, at or over the pass mark). With no unlocked exercise the list is empty and
the answer is still 200. Read-only: POST, PUT, PATCH and DELETE answer 405.

### Weakness

`GET /improv/api/weakness/`

Where to work, read from the takes you made in the last 30 days and stored nowhere. It is
careful about what it claims: each area needs 20 notes of its own before it is named, and under
that the answer says how many notes are still needed instead of guessing. `days` (30), `floor`
(20), `notes` (the notes behind your takes in the window), `enough` (`notes` has reached the
floor), `notes_needed` and `claims`: at most three, the furthest from fine first. Each claim has
`area`, `family`, `family_label`, `percent`, `notes`, `kinds`, `exercise`, `exercise_title` and
`lesson_title`. The areas are `timing` (fewer than 60 percent of notes close to the beat),
`chord_tones` (fewer than 30 percent of notes on chord tones), `outside` (more than 25 percent of
notes outside the chord and its scale) and `family` (more than 25 percent outside over one family
of chords, such as `minor` or `dominant`, named in `family`; it needs the take's
`metrics.byQuality`, which the judge writes). `percent` is the share behind the claim and `notes`
how many notes it rests on. `kinds` are the scoring kinds that work on it, best first, and
`exercise` is the first one of those you can play and have count, preferring one you have not
passed yet, or null when none is open. The same kinds fill the weak slot of the daily workout, as
the report stood when the day began. Read-only: POST, PUT, PATCH and DELETE answer 405.

### Bests

`GET /improv/api/bests/`

Your best take of each exercise, read from your takes and stored nowhere. Only a scored take of
exactly what the exercise asks (its progression, from the first bar, for its bars) counts, the
same rule a completion uses. Every challenge is listed, played or not; an exercise in a lesson is
listed once you have a take of it, and never one in a draft lesson. The order is the path's, with
challenges last. `items`, each with `exercise` (slug), `title`, `lesson` (slug, or null),
`lesson_title`, `scoring_kind`, `pass_score`, `xp`, `is_challenge`, `best_score` (null before a
try), `best_take` (its id, the earliest if two tie), `best_at` (when it was started), `attempts`
(counting takes) and `passed` (the best reached the pass mark). Read-only: POST, PUT, PATCH and
DELETE answer 405.

### Continue

`GET /improv/api/continue/`

The lesson to go back to, computed from your completions each time and stored nowhere. Only
published lessons with something to play count: a lesson with nothing to play is read and never
ticked off. `state` is `continue` (an open lesson you have passed some of, the first in the order
of the path), `start` (no lesson begun, so the first open one), `finished` (every lesson is done) or
`none` (no lesson to play yet). `lesson` (slug), `title`, `track`, `exercises_done` and
`exercises_total` describe the lesson, and are null, empty and 0 for `finished` and `none`. A locked
lesson and a draft are never offered. Today draws it as a button. Read-only: POST, PUT, PATCH and
DELETE answer 405.

### Summary

`GET /improv/api/summary/`

What the screens show about your progress, computed from your completions each time and
stored nowhere. `xp` (the sum of `xp_awarded`), `level` (1 to 50, a function of `xp`: level
n begins at 25 times (n - 1) times n XP, so 0, 50, 150, 300, 500 and so on), `level_floor` (the XP
this level began at), `next_level_at` (the XP the next level begins at, null at the top),
`exercises_done`, `lessons_done` and `lessons_total` (published lessons only). Read-only.

## Chart grammar

A chart is plain text. It is what a progression stores in its `chart` field, what
the editor shows, and what `static/improv/chart.js` parses in the browser. One
grammar, written here once.

**Bars.** Chords between bar lines: `| Dm7 | G7 | Cmaj7 |`. The leading and the
closing bar line are optional, `||` and a closing `|]` read as bar lines, and a
chart can run over many lines (a bar line that opens a line right after one that
closed the line before is one bar line). `//` starts a comment to the end of the
line.

**Chords in a bar.** One chord fills the bar. Two or more split it evenly (`Dm7 G7`
is two beats each in four-four; `C F G` is thirds of the bar). More chords than
beats is an error. The default is four beats a bar; the page can say three.

**`%`** repeats the bar before it, whatever it held. It has to stand alone in its
bar and cannot be the first bar.

**Chord names.** Root `A` to `G` with an optional `#` or `b`, then a quality, then an
optional slash bass (`C/E`, `Dm7/C`). A bare root is a major triad. The quality is a
`symbol` or any `alias` from the chord-quality reference above, so `Dm7`, `Dmin7`,
`D-7` and `Dmi7` are one chord, and `CM7`, `Cmaj7`, `CΔ` too. The parser is given
that vocabulary; it has no list of its own. A name is stored in the chart as typed
and shown by its canonical symbol.

**Repeats.** `|: ... :|` plays the section twice. A `:|` with no `|:` before it
repeats from the top, or from the last repeat. `:|:` closes one and opens the next.

**Endings.** `|: A | B | [1 C :| [2 D |` plays A B C, then A B D. `[3` and more
follow the same rule and have to come in order. `]` can close the last ending. A
repeat that has only `[1` treats the music after its `:|` as the second ending.

**Key.** `{key: Eb}` or `{key: Am}`, between bars. It says what key the bars after it
are in, until the next marker. Before any marker the key is the progression's home
key, or none. Chords stay concrete: the marker does not change a chord's name, it
tells the player where the tonic is, and it moves with the chords when the chart is
transposed.

**Transposition** is computed at play time and never stored. `transposeToKey(chart,
from, to)` moves every root, bass and key marker by the shorter way round (the
distance between the two tonics, so C to Am is down three). The spelling follows the
target key: flat keys (F, Bb, Eb, Ab, Db, Gb and the minors of those, plus Dm, Gm,
Cm, Fm) use flats, the others use sharps.

**Playing order and positions.** Parsing gives the bars in the order they are
played, repeats and endings expanded, each with the written bar it came from, its
line and column, and which pass it is on, so the screen can light the right place in
the text. A chart is capped at 2000 played bars.

**The first error.** A chart that does not parse returns the first error only, with
a plain message, its line, its column and its bar number (0 when the whole chart is
the problem), and never a half-parsed chart.

## Pages

These are screens, not API, listed so the route list is complete. Each answers 404 to
anyone outside the gate, like everything else.

- `/improv/`: Today, the landing page: the daily goal as a ring, the streak, today's workout, and a
  way back into the lesson in progress (the continue read below).
- `/improv/progress/`: level and XP with a bar, a five-week practice calendar, where to work (the
  weakness report) and your best takes.
- `/improv/lessons/`: the lessons by track, with your level and XP and where you stand in each.
- `/improv/lessons/{slug}/`: one lesson, Read, Hear, Play. It draws a shell for any slug
  and says "No such lesson" when the API does not give it back, which also keeps a draft
  lesson from being told apart from one that does not exist.
- `/improv/practice/`: today's workout, today against the daily goal, the streak, and the last
  thirty days as a list.
- `/improv/challenges/`: the standalone challenges with your best score on each, and your bests
  in the lessons.
- `/improv/scales/`: the scale trainer: pick a key, a level and the tempo, play it with both hands in time against the
  fingering strip, and get the score.
- `/improv/chords/`: the chord trainer: Learn, Drill and Circle, the hint, and the time of each answer.
- `/improv/play/?exercise={slug}`: Play opened on an exercise: the progression, key, tempo,
  feel and loop are set from it, and a take played over exactly that loop is scored by the
  exercise's own kind and posted with `exercise` set.

## The scales and chords trainer

### Scale fingerings

`GET /improv/api/scale-fingerings/`, `GET /improv/api/scale-fingerings/{id}/`. Read-only reference (405 on a write).
Each row is `id`, `scale` (slug), `root_pc`, `hand` (`L` or `R`), `first_octave`, `next_octaves`, `last_note`.
Filters: `?root_pc=7`, `?hand=R`.

### Scale runs

`GET, POST /improv/api/scale-runs/`, `GET, PUT, PATCH, DELETE /improv/api/scale-runs/{id}/`. Your own runs only. Newest first.
`scale` (slug, default Major), `root_pc` (0 to 11), `octaves` (2 to 4), `notes_per_beat` (2 to 4), `tempo_bpm` (30 to 160),
`score` (0 to 100), `pitch_accuracy`, `timing_accuracy` (0 to 1), `mean_offset_ms`, `passed` (read-only: the server sets it, score 80 or more), `missed_steps` (a list of
step numbers), `judge_version`, `created_at` (read-only). Filters: `?root_pc=`, `?octaves=`.

### Drill attempts

`GET, POST /improv/api/drill-attempts/`, `GET, PUT, PATCH, DELETE /improv/api/drill-attempts/{id}/`. Your own attempts only. Newest first.
`kind` (`chord_position`), `key_pc` (0 to 11), `level` (1 to 3), `prompt`, `answer` (JSON objects), `is_correct`, `wrong_tries`,
`hint_used`, `skipped`, `response_ms` (blank when skipped), `answered_at` (read-only). Filters: `?key_pc=`, `?kind=`.

### Trainer

`GET /improv/api/trainer/`. Read-only (405 on a write), your own data only, stored nowhere. Both trainer screens show it as
"work on this".
- `scales`: the best run for each key and octave count, ordered by key then octaves: `root_pc`, `octaves`, `score`,
  `tempo_bpm`, `passed`, `runs` (how many runs of that key and length) and `at`.
- `slowest_chords`: up to five chords (a chord in a position, in a key) with the longest median response time, each with at
  least three timed answers: `title`, `key_pc`, `position`, `median_ms`, `attempts`. Skipped prompts have no time and are left out.
- `weakest_keys`: keys with at least five prompts, ordered by the share missed (a wrong try or a skip counts as missed; a hint
  alone does not): `key_pc`, `attempts`, `missed`, `miss_share`.
- `totals`: `runs`, `passes`, `attempts`, `clean` (answers with no wrong try and no hint).

## Still to come

Nothing is planned beyond what is above for the first version. A model cannot ship without its
endpoint and its entry here; the test above enforces it.
