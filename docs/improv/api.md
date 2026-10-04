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
- Reference rows (chord qualities, scales, chord scales, tags) are read-only here.
  They are edited in the Django admin. A write verb (POST, PUT, PATCH, DELETE)
  answers 405.
- Content a player can own (styles, progressions) is writable for the player's own
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

## Still to come

Phrases, lessons, exercises, takes, completions and the
derived reads (summary, daily workout, weakness report) arrive with the sprints
that add their models. A model cannot ship without its endpoint and its entry
here; the test above enforces it.
