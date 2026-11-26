# breakout: Data model

> **Status: approved by Avi, 2026-11-26.** The open questions in section 7
> were not answered separately; the build takes the defaults written there
> (publish at once, curator hides afterwards; A4; a Run is public unless the
> teacher keeps it private; signed-in only) until Avi says otherwise. This is the shape of the data on its own, kept apart from
> the spec on purpose ([building_an_app.md](../building_an_app.md), Rule 4).
> What the app is and why: [spec.md](spec.md) chapter 1. The model example
> every row below should be able to hold: "המחשב שנכבה" (spec, chapter 0).

Four things shape everything here:

1. **Everything is a row.** An experience, a station, a hint, a material, a
   printable page, a like, a comment: each is a model with its own fields,
   never a blob of text or a file the app keeps reading. Avi's flagship
   experiences are seeded once from a file and then live only in the
   database.
2. **The printable kit is derived, not stored.** The teacher's guide, the
   player pages and the shopping list are built from the rows each time
   they are asked for. A teacher may also attach ready-made pages (a drawn
   logic board, a cut-out sheet) as files, and those are rows that point to
   files.
3. **The genre boundary is a table.** Materials come from a shared
   catalogue. An experience lists which ones it needs and how many; a new
   material is a request a curator approves.
4. **Only the author edits; everyone else reacts.** An experience has one
   author who edits every field in the app. Others like, comment, download
   and report a run. A curator can hide, never edit.

---

## 0. The map

```text
User ──1 Profile                       (display name, curator flag)

Experience ──* Station ──* Hint
                       ──* StationMaterial ──1 Material
                       ──* Printable
Experience ──* Printable               (kit-level pages: cover, teacher guide extras)
Experience ──* ExperienceSubject ──1 Subject
Experience ──1 FinalLock

Experience ──* Like
Experience ──* Comment
Experience ──* Run                     (a teacher ran it and reported back)
Experience ──* Download                (a kit was downloaded or printed)

Material ──* MaterialRequest           (a teacher asks for a new material)
Experience / Comment ──* Report        (flag content for a curator)
```

---

## 1. People

| Model | What it is | Main fields |
| --- | --- | --- |
| **Profile** | The app's own one-to-one to the site's shared `User`. Created on a person's first visit. Never adds fields to `User` | user, display_name (what other teachers see; defaults to the first name), school (optional, free text), is_curator, joined_at |

Who can do what is decided by two facts: `request.user == experience.author`
and `profile.is_curator`. A superuser is a curator (so the site admin is not
locked out; written here on purpose).

---

## 2. The experience and its parts

| Model | What it is | Main fields |
| --- | --- | --- |
| **Experience** | One breakout experience, the unit of the library | author (User), title, slug, tagline (one line for the library card), story (what the teacher reads to the group at the start; the "robot crashed" text), teacher_notes (how to set up the room, how long to prepare), audience_from / audience_to (ages or grades), group_size_min / group_size_max, duration_minutes, prep_minutes, difficulty: `easy` / `medium` / `hard`, status: `draft` / `published` / `hidden`, hidden_reason, is_flagship, cover (image file, optional), created_at, updated_at, published_at, version (bumps on every published edit) |
| **Station** | One puzzle in the chain. Ordered. In the example: Memory, Processor, The bug, Network, Algorithm | experience, order, name, story_text (what the kids read at this station), puzzle_text (the riddle itself, as printed for the kids), solution (the answer), solution_explained (teacher-facing: how one gets there), contribution (what this station adds to the final code: a digit, a letter, a word, an instruction), mechanic: `decode` / `logic` / `find_the_error` / `order` / `sort` / `cipher` / `assemble` / `other`, estimated_minutes, setup_notes (how to prepare this station physically) |
| **Hint** | A hint the teacher can give at a station. Ordered, from gentle to nearly the answer | station, order, text |
| **FinalLock** | How the experience ends. One per experience | experience, description (the envelope with four paper locks), code_rule (how the stations' contributions combine into the code, in words), final_code, final_message (what is inside when it opens), setup_notes |
| **Subject** | A school subject or theme, seeded, extendable by curators: programming, computers, math, history, language, science, general | name, slug, order |
| **ExperienceSubject** | Many-to-many through | experience, subject |

A station's `contribution` and the lock's `code_rule` are text, on purpose:
the ways a code is built are endless and the teacher explains theirs. The
generated teacher's guide prints both.

---

## 3. Materials, the genre boundary

| Model | What it is | Main fields |
| --- | --- | --- |
| **Material** | One thing from the office-supply shop, in a shared catalogue. Seeded: A4 paper, bristol board, scissors, printer, envelopes, stapler, safety pins, insulating tape, sticky notes, string, markers, glue, paper clips, rubber bands, zip-lock bags | name, unit (sheet, piece, roll, pack), category: `paper` / `tool` / `fastener` / `writing` / `container` / `other`, approx_cost_ils (optional), where_to_get (optional), is_active |
| **StationMaterial** | What a station needs, how much, and what for | station, material, quantity, note (e.g. "cut into 20 strips") |
| **MaterialRequest** | A teacher's request for a material that is not in the catalogue. A curator approves it (a Material is created) or declines with a reason | requested_by, name, why, status: `open` / `approved` / `declined`, decided_by, decided_at, reason, created_material (nullable) |

The experience's shopping list is the sum of its StationMaterial rows, grouped
by material, scaled by how many groups the teacher enters when printing.

---

## 4. Printables

| Model | What it is | Main fields |
| --- | --- | --- |
| **Printable** | A ready-made page or file the author attaches: a drawn logic board, a cut-out sheet, an answer card. Belongs to a station or to the whole experience | experience, station (nullable), kind: `player_page` / `cut_out` / `teacher_page` / `image`, title, file (PDF or image, private media under the app's folder), page_count, width_px / height_px (images, kept at upload so a page is never measured while rendering), order, uploaded_at |

The generated kit (teacher's guide, player pages per station, shopping list)
is a view over the rows above and is not stored. A download of it is recorded
(section 5), the file is not.

---

## 5. The community around an experience

| Model | What it is | Main fields |
| --- | --- | --- |
| **Like** | One per person per experience | experience, user, created_at (unique together) |
| **Comment** | A flat comment on an experience. Author may edit and delete; a curator may hide | experience, author, text, created_at, edited_at, is_hidden, hidden_by |
| **Run** | A teacher ran this experience with a real group and reports back. The most useful signal the library has | experience, user, ran_on (date), group_count, kids_count, actual_minutes, rating (1 to 5), what_worked, what_to_change, is_public (shown to others or kept as the teacher's own note), created_at |
| **Download** | One kit download or print, for the counter and for "who uses this" | experience, user, groups (how many groups the kit was scaled for), created_at |
| **Report** | Flagging an experience or a comment to a curator | reporter, experience (nullable), comment (nullable), reason, created_at, status: `open` / `resolved`, resolved_by, resolved_at, note |

Counts shown in the library (likes, runs, downloads, comments) are computed
from these rows, with the counting done before any filter on the same
relation (mistake 20).

---

## 6. What is deliberately not here

- **No AI tables** in the first version (no conversations, no usage): spec
  1.5. If a writing helper is added later it gets its own section and its
  own cost cap.
- **No kid, group or session data.** The teenagers are never in the
  database; a Run holds counts, never names.
- **No versions table.** `Experience.version` bumps on a published edit so a
  downloaded kit can say which version it was; the old text is not kept. If
  teachers ask for history, it becomes a table then.
- **No ChangeLog.** Ownership is simple (one author) and edits are the
  author's own; a curator's actions (hide, approve a material, resolve a
  report) are recorded on the row they act on.

## 7. Open questions for Avi

1. **Publishing gate:** publish is immediate for any signed-in user, with a
   curator able to hide afterwards (as drafted), or does a first experience
   wait for a curator before it shows? The site's shared moderation
   (`app/safety.py`) could screen texts and images at publish time; using it
   is a conscious crossing of the app boundary and needs your word.
2. **Printable sizes:** A4 only?
3. **Runs public by default,** or private to the teacher by default?
4. **Download without an account?** The spec says signed-in only for
   everything. If a teacher wants to send a kit to a colleague without an
   account, that is a later feature (a share link), not in this model.
