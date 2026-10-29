# design3d: Data model

Status: **approved by Avi ("Start"), 2026-10-28.** Spec:
[spec.md](spec.md).

## 1. The picture

```
User (babook's, shared) ──1:1── Maker (status: pending / approved / declined)
                                   │
                                   └── Design (title, shared or not)
                                         │
                       ┌─────────────────┼──────────────────────┐
                       │                 │                      │
                    Message           Version ──── Parameter    │
                (the chat, in order)  (one build:  (a slider:   │
                       │               code, STL,   name, value,│
                       └── Picture      preview)    range)      │
                     (images sent)       │                      │
                                         └── parent Version (what it continued from)
```

One row per person who asked to come in (Maker), their designs, and inside
each design two timelines side by side: the conversation (Message, with the
pictures sent) and the builds it produced (Version, with its sliders).

## 2. Models

### Maker

The app's own record of a person (Rule 2: nothing is added to babook's
`User`). One per user who ever asked.

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | cascade |
| display_name | char 80 | shown on shared designs |
| status | choice | `pending`, `approved`, `declined`; a declined person may ask again, which sets it back to `pending` |
| reason | char 300, blank | what they wrote when asking |
| is_admin | bool | Avi (a superuser is admin regardless) |
| daily_limit_usd | decimal, null | null: the default, $2 a day; ignored for admins |
| requested_at | datetime | |
| decided_at | datetime, null | |
| decided_by | FK → User, null | |

### Design

One project.

| Field | Type | Notes |
|---|---|---|
| owner | FK → Maker | cascade |
| title | char 100 | the chat proposes one; the owner can rename |
| current | FK → Version, null | the version shown when the design opens |
| is_shared | bool | off by default |
| shared_at | datetime, null | |
| copied_from | FK → Design, null | for "make a copy" (planned right after the first release) |
| created_at, updated_at | datetime | |

### Message

One turn of the chat, from the person or from the model, in order. The
history sent to the model is built from these rows.

| Field | Type | Notes |
|---|---|---|
| design | FK → Design | cascade |
| role | choice | `person`, `assistant` |
| state | choice | `thinking`, `building`, `done`, `failed` (an assistant turn runs in the background; the page polls it) |
| step | char 80, blank | what a running turn is doing now, shown on the page (added 2026-10-28) |
| pin | JSON, null | a point the person tapped: {x, y, z, nx, ny, nz, version}, mm in the code's coordinates (added 2026-10-29) |
| trail | JSON list, blank | how the turn went: [seconds from the start, what happened], opened under "How this turn went" (added 2026-10-28) |
| text | text | what was said |
| assumptions | JSON list, blank | the assistant's list of what it assumed (shown to the person, so they can correct it) |
| version | FK → Version, null | the build this assistant turn produced, if any |
| model | char 40, blank | e.g. `gpt-6.1-terra` |
| tokens_in, tokens_cached, tokens_out | int | from the API's usage |
| cost_usd | decimal | what this turn cost; the daily limit sums these |
| created_at | datetime | |

### Picture

An image the person sent with a message: a sketch, a drawing, a photo.

| Field | Type | Notes |
|---|---|---|
| message | FK → Message | cascade |
| image | image | private folder, served only to the design's owner, never shown with a shared design |
| width, height | int | stored when saved, never measured on a page (methodology 37) |
| created_at | datetime | |

Made at most 2000 px on the long side, location data removed, and checked
by the site's shared image check before the model sees it.

### Version

One build of the part. Built from the chat, or from moving a slider.

| Field | Type | Notes |
|---|---|---|
| design | FK → Design | cascade |
| number | int | 1, 2, 3... within the design |
| parent | FK → Version, null | the version it was changed from (continuing from an old version branches) |
| made_by | choice | `chat`, `sliders` |
| code | text | the whole OpenSCAD file |
| status | choice | `building`, `ready`, `failed` |
| error | text, blank | the builder's message when it failed |
| stl | file, blank | private folder |
| preview | image, blank | a still picture for the design's card |
| size_mm | char 40, blank | the bounding box, e.g. `100 x 80 x 27` |
| build_seconds | decimal, null | |
| checks | JSON list, null | print-ready findings [{level warn/note, code, text, fix}]; [] = ready to print, null = not checked yet (added 2026-10-28) |
| created_at | datetime | |

Each version keeps its whole code, so any version can be rebuilt,
downloaded, or continued from without the ones around it.

### Parameter

One slider of a version: a key size the chat named at the top of the code.

| Field | Type | Notes |
|---|---|---|
| version | FK → Version | cascade |
| name | char 40 | the variable in the code, e.g. `wall_thickness` |
| label | char 60 | for people, e.g. "Wall thickness" |
| value | decimal | |
| minimum, maximum, step | decimal | a sensible range the chat proposes |
| unit | char 8 | `mm`, `deg`, or blank |
| position | int | order on the screen |

Moving sliders writes the new values into a copy of the code and builds a
new Version (`made_by = sliders`) with no call to the model.

## 3. What is shared, and what is not

- Shared with babook: the `User` table and sign-in only.
- Files (pictures, STLs, previews) live on the persistent disk in design3d's own
  private folder, never under the public media folder, created on first
  write (methodology 17). An STL is about 250 KB.
- A shared design shows its current version's preview, 3D view and STL to
  other approved people. Its messages and pictures stay its owner's.
- The OpenAI key is the site's; every call is counted in Message, so the
  admin screen and the daily limit read from the database.

## 4. The REST API (Rule 6)

Under `/design3d/api/`: `makers` (your own; all for Avi, with approve and
decline), `designs` (yours; shared ones read-only for others), `messages`
(of your designs; posting one is how a chat turn starts), `pictures`,
`versions` (with a `build` action for slider changes), `parameters`.

## 5. Decided

1. Shared designs never show the pictures or the chat (Avi, 2026-10-28).
2. A declined person may ask again; their row goes back to `pending`.

## Part (approved by Avi 2026-10-29)

One part of a version that has several (Chapter 7). A version with one part
has no Part rows and works as today. `Version.stl` stays the file people
download and share: for several parts it is the print plate.

| Field | Type | Meaning |
|---|---|---|
| version | FK Version | the version it belongs to (cascade) |
| name | char 40 | the module name in the code (`lid`), unique in the version |
| label | char 80 | what people read ("Lid") |
| position | int | order in the list |
| count | int, default 1 | how many to print (4 clips) |
| printed | bool, default true | false for hardware the person buys (a screw, a magnet): shown and fit-checked, never on the plate |
| stl | file, private | the part in its assembled place (for the assembled view and the fit check) |
| print_stl | file, private, blank | the part turned flat for printing (printed parts only) |
| orientation | char 20 | how it was turned for printing: the model's hint or the side the server chose |
| size_mm | char 40 | its size |
| checks | JSON, null | its print check |
| color | char 7 | its colour in the assembled view (set by the server) |

### Version gets

| Field | Type | Meaning |
|---|---|---|
| file_3mf | file, private, blank | every printed part as its own object, on the plate |
| fit | JSON, null | the fit findings between parts, in the same shape as `checks` |

### Message.pin gets

A `part` key (the part's name) when the tapped point is on a part of a
several-part version. No schema change: `pin` is JSON.

### What is shared

Unchanged: a shared design shows the model only. For several parts that is
the parts, the plate and the 3MF; never the chat or the pictures.

## Invite (added 2026-10-29, at Avi's request)

One invitation to one person. Its token is the key in the link; the first
person who opens it signed in is let in and the token is burned
(`used_at`, `used_by`). Methodology 55: that person may come back.

| Field | Type | Meaning |
|---|---|---|
| email | email | who it was sent to |
| name | char 80, blank | for the email's greeting |
| token | char 64, unique | the one-time key (secrets.token_urlsafe) |
| created_by | FK User, null | who sent it (Avi) |
| created_at, expires_at | datetime | sent, and 14 days later it ends |
| used_at, used_by | datetime, FK User, null | when and by whom it was used |
| revoked_at | datetime, null | Avi withdrew it |

`status` (a property): open, used, revoked or expired.
