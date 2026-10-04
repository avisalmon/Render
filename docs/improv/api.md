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
- Reference rows are read-only here. They are edited in the Django admin. A write
  verb (POST, PUT, PATCH, DELETE) answers 405.
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

## Still to come

Styles, progressions, phrases, lessons, exercises, takes, completions and the
derived reads (summary, daily workout, weakness report) arrive with the sprints
that add their models. A model cannot ship without its endpoint and its entry
here; the test above enforces it.
